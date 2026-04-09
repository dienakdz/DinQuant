"""
Polymarket prediction market API routing
Provide on-demand analysis interface (read-only, no transactions involved)
"""

import json
import re

from flask import Blueprint, g, jsonify, request

from app.data_sources.polymarket import PolymarketDataSource
from app.utils.auth import login_required
from app.utils.db import get_db_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)

polymarket_bp = Blueprint("polymarket", __name__)

# Initialize service
polymarket_source = PolymarketDataSource()


@polymarket_bp.route("/analyze", methods=["POST"])
@login_required
def analyze_polymarket():
    """
    Analyze Polymarket prediction market (user enters link or title)

    POST /api/polymarket/analyze
    Body: {
        "input": "https://polymarket.com/event/xxx" or "market title",
        "language": "zh-CN" (optional)
    }

    process:
    1. Parse market_id or slug from input
    2. Get market data from API
    3. Check billing and deduct points
    4. Call AI analysis
    5. Return analysis results
    """
    try:
        from decimal import Decimal

        from app.services.billing_service import BillingService
        from app.services.polymarket_analyzer import PolymarketAnalyzer

        user_id = getattr(g, "user_id", None)
        if not user_id:
            return jsonify({"code": 0, "msg": "User not authenticated", "data": None}), 401

        data = request.get_json() or {}
        input_text = (data.get("input") or "").strip()
        language = data.get("language", "zh-CN")

        if not input_text:
            return jsonify({"code": 0, "msg": "Input is required (Polymarket URL or market title)", "data": None}), 400

        # 1. Parse market_id or slug
        market_id = None
        slug = None

        # Try to extract from URL
        url_patterns = [
            r"polymarket\.com/event/([^/?]+)",
            r"polymarket\.com/markets/(\d+)",
            r"polymarket\.com/market/(\d+)",
        ]

        for pattern in url_patterns:
            match = re.search(pattern, input_text)
            if match:
                extracted = match.group(1)
                # If it is a number, it is market_id; otherwise it is slug
                if extracted.isdigit():
                    market_id = extracted
                else:
                    slug = extracted
                break

        # If not extracted from the URL, try searching the market
        if not market_id and not slug:
            # Try searching by title
            logger.info(f"Searching for market by title: {input_text[:100]}")
            search_results = polymarket_source.search_markets(input_text, limit=5)
            if search_results:
                # Use first search result
                market_id = search_results[0].get("market_id")
                logger.info(f"Found market via search: {market_id}")

        if not market_id and not slug:
            return jsonify(
                {
                    "code": 0,
                    "msg": "Could not parse market ID or slug from input. Please provide a valid Polymarket URL or market title.",
                    "data": None,
                }
            ), 400

        # 2. Obtain market data
        if market_id:
            market = polymarket_source.get_market_details(market_id)
        elif slug:
            # Find the market by slug (need to search first)
            search_results = polymarket_source.search_markets(slug, limit=10)
            market = None
            for result in search_results:
                if result.get("slug") == slug or slug in (result.get("question") or ""):
                    market = result
                    market_id = result.get("market_id")
                    break

            if not market and search_results:
                # Use first search result
                market = search_results[0]
                market_id = market.get("market_id")

        if not market:
            return jsonify({"code": 0, "msg": "Market not found. Please check the URL or title.", "data": None}), 404

        if not market_id:
            market_id = market.get("market_id")

        if not market_id:
            return jsonify({"code": 0, "msg": "Invalid market data", "data": None}), 400

        # 3. Check billing
        billing = BillingService()
        cost = 0

        if billing.is_billing_enabled():
            cost = billing.get_feature_cost("polymarket_deep_analysis")

            if cost > 0:
                user_credits = billing.get_user_credits(user_id)
                if user_credits < Decimal(str(cost)):
                    return jsonify(
                        {
                            "code": 0,
                            "msg": "Insufficient credits",
                            "data": {
                                "required": cost,
                                "current": float(user_credits),
                                "shortage": float(Decimal(str(cost)) - user_credits),
                            },
                        }
                    ), 400

                # Deduct points (use check_and_consume method, it will automatically get the cost from the configuration)
                success, error_msg = billing.check_and_consume(
                    user_id=user_id, feature="polymarket_deep_analysis", reference_id=f"polymarket_{market_id}"
                )

                if not success:
                    # Check whether it is an error due to insufficient points
                    if error_msg.startswith("insufficient_credits"):
                        parts = error_msg.split(":")
                        if len(parts) >= 3:
                            current_credits = parts[1]
                            required_credits = parts[2]
                            return jsonify(
                                {
                                    "code": 0,
                                    "msg": "Insufficient credits",
                                    "data": {
                                        "required": float(required_credits),
                                        "current": float(current_credits),
                                        "shortage": float(Decimal(required_credits) - Decimal(current_credits)),
                                    },
                                }
                            ), 400
                    return jsonify({"code": 0, "msg": f"Failed to deduct credits: {error_msg}", "data": None}), 500

        # 4. Perform AI analysis (pass language and model parameters)
        analyzer = PolymarketAnalyzer()
        model = request.get_json().get("model")  # Optional: Get model parameters from request
        analysis_result = analyzer.analyze_market(
            market_id, user_id=user_id, use_cache=False, language=language, model=model
        )

        if analysis_result.get("error"):
            return jsonify({"code": 0, "msg": analysis_result.get("error", "Analysis failed"), "data": None}), 500

        # 5. Get remaining points
        remaining_credits = 0
        if billing.is_billing_enabled():
            remaining_credits = float(billing.get_user_credits(user_id))

        return jsonify(
            {
                "code": 1,
                "msg": "success",
                "data": {
                    "market": market,
                    "analysis": analysis_result,
                    "credits_charged": cost,
                    "remaining_credits": remaining_credits,
                },
            }
        )

    except Exception as e:
        logger.error(f"Polymarket analyze API failed: {e}", exc_info=True)
        return jsonify({"code": 0, "msg": str(e), "data": None}), 500


@polymarket_bp.route("/history", methods=["GET"])
@login_required
def get_polymarket_history():
    """
    Get user's Polymarket analysis history.

    GET /api/polymarket/history?page=1&page_size=20
    """
    try:
        user_id = g.user_id
        page = request.args.get("page", 1, type=int)
        page_size = min(request.args.get("page_size", 20, type=int), 100)
        offset = (page - 1) * page_size

        with get_db_connection() as db:
            cur = db.cursor()

            # Get total
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM qd_analysis_tasks
                WHERE user_id = %s AND market = 'Polymarket'
            """,
                (user_id,),
            )
            total_row = cur.fetchone()
            total = total_row["total"] if total_row else 0

            # Get history
            cur.execute(
                """
                SELECT
                    t.id,
                    t.symbol AS market_id,
                    t.model,
                    t.language,
                    t.status,
                    t.created_at,
                    t.completed_at,
                    t.result_json
                FROM qd_analysis_tasks t
                WHERE t.user_id = %s AND t.market = 'Polymarket'
                ORDER BY t.created_at DESC
                LIMIT %s OFFSET %s
            """,
                (user_id, page_size, offset),
            )
            rows = cur.fetchall() or []
            cur.close()

        # Parse results
        items = []
        for row in rows:
            result_json = row.get("result_json", "{}")
            try:
                result_data = json.loads(result_json) if result_json else {}
            except Exception as e:
                logger.debug(f"Failed to parse result JSON for task {row.get('id')}: {e}")
                result_data = {}

            market_data = result_data.get("market", {})
            analysis_data = result_data.get("analysis", {})

            created_at = row.get("created_at")
            completed_at = row.get("completed_at")
            if created_at and hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            if completed_at and hasattr(completed_at, "isoformat"):
                completed_at = completed_at.isoformat()

            items.append(
                {
                    "id": row.get("id"),
                    "market_id": row.get("market_id"),
                    "market_title": market_data.get("question")
                    or market_data.get("title")
                    or f"Market {row.get('market_id')}",
                    "market_url": market_data.get("polymarket_url"),
                    "ai_predicted_probability": analysis_data.get("ai_predicted_probability"),
                    "market_probability": analysis_data.get("market_probability"),
                    "recommendation": analysis_data.get("recommendation"),
                    "opportunity_score": analysis_data.get("opportunity_score"),
                    "confidence_score": analysis_data.get("confidence_score"),
                    "status": row.get("status"),
                    "created_at": created_at,
                    "completed_at": completed_at,
                }
            )

        return jsonify(
            {
                "code": 1,
                "msg": "success",
                "data": {
                    "items": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            }
        )

    except Exception as e:
        logger.error(f"Get Polymarket history failed: {e}", exc_info=True)
        return jsonify({"code": 0, "msg": str(e), "data": None}), 500
