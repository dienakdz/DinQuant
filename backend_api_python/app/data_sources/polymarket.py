"""
Polymarket prediction market data source
Get prediction market data from Polymarket
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from app.utils.db import get_db_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PolymarketDataSource:
    """Polymarket prediction market data source"""

    def __init__(self):
        # Polymarket official API endpoint (according to official documentation)
        # Gamma API: markets, events, tags, searches, etc. (fully public, no authentication required)
        self.gamma_api = "https://gamma-api.polymarket.com"
        # Data API: User positions, transactions, activities, etc. (fully public, no authentication required)
        self.data_api = "https://data-api.polymarket.com"
        # CLOB API: Order book, prices, trading operations (public endpoints require no authentication)
        self.clob_api = "https://clob.polymarket.com"
        self.cache_ttl = 300  # 5 minutes cache
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "application/json"}
        )

    def get_trending_markets(self, category: str = None, limit: int = 50) -> List[Dict]:
        """
        Get popular prediction markets

        Args:
            category: category filter (crypto, politics, economics, sports, all)
            limit: return quantity limit

        Returns:
            Prediction market list
        """
        try:
            # Read from database cache first
            cached = self._get_cached_markets(category, limit)
            if cached:
                return cached

            # Fetch from real API - Fetch data from multiple categories to ensure diversity
            all_markets = []

            if category and category != "all":
                # If a category is specified, only data for that category will be obtained
                markets = self._fetch_markets_from_api(category, limit * 2)
                all_markets.extend(markets)
            else:
                # Retrieve all events (without specifying a category to avoid duplicate requests)
                markets = self._fetch_from_gamma_api(category=None, limit=100)
                all_markets.extend(markets)

            # 去重（按market_id）
            seen = set()
            unique_markets = []
            for market in all_markets:
                market_id = market.get("market_id")
                if market_id and market_id not in seen:
                    seen.add(market_id)
                    unique_markets.append(market)

            # Sort by transaction volume
            unique_markets.sort(key=lambda x: x.get("volume_24h", 0), reverse=True)

            # Save to database cache
            if unique_markets:
                self._save_markets_to_db(unique_markets)
                return unique_markets[:limit]

            # If the API fails, an empty list is returned (sample data is no longer used)
            logger.warning("Polymarket API unavailable, returning empty list")
            return []

        except Exception as e:
            logger.error(f"Failed to get trending markets: {e}", exc_info=True)
            return []

    def get_market_details(self, market_id: str) -> Optional[Dict]:
        """Get individual market details"""
        try:
            # Make sure market_id is a string
            market_id = str(market_id).strip()
            if not market_id:
                logger.warning("Empty market_id provided")
                return None

            # Read from database first
            try:
                with get_db_connection() as db:
                    cur = db.cursor()
                    cur.execute(
                        """
                        SELECT market_id, question, category, current_probability,
                               volume_24h, liquidity, end_date_iso, status, outcome_tokens
                        FROM qd_polymarket_markets
                        WHERE market_id = %s
                    """,
                        (market_id,),
                    )
                    row = cur.fetchone()
                    cur.close()

                    if row:
                        # RealDictCursor returns the dictionary, accessed using keys
                        db_market_id = str(row.get("market_id") or market_id)
                        # Parse outcome_tokens (may be a JSON string)
                        outcome_tokens = {}
                        outcome_tokens_raw = row.get("outcome_tokens")
                        if outcome_tokens_raw:
                            try:
                                if isinstance(outcome_tokens_raw, str):
                                    outcome_tokens = json.loads(outcome_tokens_raw)
                                else:
                                    outcome_tokens = outcome_tokens_raw if isinstance(outcome_tokens_raw, dict) else {}
                            except Exception as e:
                                logger.debug(f"Failed to parse outcome tokens for market {market_id}: {e}")
                                outcome_tokens = {}

                        return {
                            "market_id": db_market_id,
                            "question": row.get("question") or "",
                            "category": row.get("category") or "other",
                            "current_probability": float(row.get("current_probability") or 0),
                            "volume_24h": float(row.get("volume_24h") or 0),
                            "liquidity": float(row.get("liquidity") or 0),
                            "end_date_iso": row.get("end_date_iso"),
                            "status": row.get("status") or "active",
                            "outcome_tokens": outcome_tokens,
                            "polymarket_url": self._build_polymarket_url(row.get("slug"), db_market_id),
                            "slug": row.get("slug")
                            if row.get("slug") and not str(row.get("slug", "")).isdigit()
                            else None,
                        }
            except Exception as db_error:
                logger.warning(f"Database query failed for market {market_id}: {db_error}")
                # Continue trying to get it from the API

            # If the database does not exist, get it from the API
            logger.info(f"Market {market_id} not in database, fetching from API")
            market = self._fetch_market_from_api(market_id)
            if market:
                try:
                    self._save_markets_to_db([market])
                except Exception as save_error:
                    logger.warning(f"Failed to save market to DB: {save_error}")
                return market

            logger.warning(f"Market {market_id} not found in API")
            return None

        except Exception as e:
            logger.error(f"Failed to get market details for {market_id}: {e}", exc_info=True)
            return None

    def get_market_history(self, market_id: str, days: int = 30) -> List[Dict]:
        """Get historical market price data."""
        # Here you need to implement historical data acquisition logic
        # Temporarily returns an empty list
        return []

    def search_markets(self, keyword: str, limit: int = 20, use_cache: bool = True) -> List[Dict]:
        """
        Search related prediction markets
        Priority is given to obtaining real-time data from the API, and the database is only used as an optional cache.

        Args:
            keyword: search keyword
            limit: limit on the number of returned results
            use_cache: whether to use database cache (should be set to False during AI analysis to obtain the latest data)
        """
        try:
            logger.info(f"Searching Polymarket markets for keyword: '{keyword}' (limit={limit}, use_cache={use_cache})")

            # If caching is allowed, try searching from the database first
            if use_cache:
                with get_db_connection() as db:
                    cur = db.cursor()
                    # Improved search: search question and slug fields at the same time, also support market_id exact matching
                    keyword_lower = keyword.lower()
                    is_numeric = keyword_lower.isdigit()
                    has_hyphens = "-" in keyword_lower

                    if is_numeric:
                        # If it is a pure number, it may be market_id, an exact match
                        cur.execute(
                            """
                            SELECT market_id, question, category, current_probability,
                                   volume_24h, liquidity, end_date_iso, status, slug
                            FROM qd_polymarket_markets
                            WHERE market_id = %s AND status = 'active'
                            ORDER BY volume_24h DESC
                            LIMIT %s
                        """,
                            (keyword, limit),
                        )
                    elif has_hyphens:
                        # If it contains a hyphen, it may be a slug, and the slug will be matched first.
                        cur.execute(
                            """
                            SELECT market_id, question, category, current_probability,
                                   volume_24h, liquidity, end_date_iso, status, slug
                            FROM qd_polymarket_markets
                            WHERE (slug ILIKE %s OR question ILIKE %s) AND status = 'active'
                            ORDER BY
                                CASE WHEN slug ILIKE %s THEN 1 ELSE 2 END,
                                volume_24h DESC
                            LIMIT %s
                        """,
                            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit),
                        )
                    else:
                        # Normal text search
                        cur.execute(
                            """
                            SELECT market_id, question, category, current_probability,
                                   volume_24h, liquidity, end_date_iso, status, slug
                            FROM qd_polymarket_markets
                            WHERE (question ILIKE %s OR slug ILIKE %s) AND status = 'active'
                            ORDER BY volume_24h DESC
                            LIMIT %s
                        """,
                            (f"%{keyword}%", f"%{keyword}%", limit),
                        )

                    rows = cur.fetchall()
                    cur.close()

                    if rows:
                        logger.info(f"Found {len(rows)} markets in database for keyword '{keyword}'")
                        return [
                            {
                                "market_id": str(row.get("market_id") or ""),
                                "question": row.get("question") or "",
                                "category": row.get("category") or "other",
                                "current_probability": float(row.get("current_probability") or 0),
                                "volume_24h": float(row.get("volume_24h") or 0),
                                "liquidity": float(row.get("liquidity") or 0),
                                "end_date_iso": row.get("end_date_iso"),
                                "status": row.get("status") or "active",
                                "polymarket_url": self._build_polymarket_url(
                                    row.get("slug"), row.get("market_id") or ""
                                ),
                                "slug": row.get("slug")
                                if row.get("slug") and not str(row.get("slug", "")).isdigit()
                                else None,
                            }
                            for row in rows
                        ]

            # Obtain and filter directly from Gamma API (used during AI analysis)
            logger.info(f"Fetching from API for keyword '{keyword}' (use_cache={use_cache})...")

            # Optimization: If the keyword looks like a slug, try direct query first (avoid fetching the full amount)
            import re

            keyword_lower = keyword.lower().strip()
            is_slug_like = "-" in keyword_lower and not keyword_lower.isdigit()

            if is_slug_like:
                # Try to query directly through slug (most efficient, according to Polymarket API documentation)
                direct_market = self._fetch_market_by_slug(keyword_lower)
                if direct_market:
                    logger.info(f"Found market directly by slug (no need to fetch all markets): {keyword_lower}")
                    return [direct_market]

            # If direct query fails, get more data so that there is enough room for selection
            # Make multiple requests to get more markets (up to 100 events each time, but each event may contain multiple markets)
            all_markets = []
            max_requests = 3  # Request up to 3 times to get 300 events (about 4500 markets)
            for page in range(max_requests):
                page_markets = self._fetch_from_gamma_api(category=None, limit=100)
                if not page_markets:
                    break
                all_markets.extend(page_markets)
                # If enough markets have been acquired, you can stop early
                if len(all_markets) >= 3000:  # Get up to 3000 markets
                    break
                logger.info(f"Fetched page {page + 1}/{max_requests}, total markets: {len(all_markets)}")
                # Short delay to avoid API current limit
                if page < max_requests - 1:
                    time.sleep(0.5)
            logger.info(f"Fetched {len(all_markets)} markets from API, filtering for keyword '{keyword}'...")

            # Filter by keyword (supports multiple keyword matching)
            # If the keyword looks like a slug (contains a hyphen), also try to match the slug
            keyword_is_slug = "-" in keyword_lower
            # Extract keywords (remove common stop words and punctuation)
            # Extract keywords: remove punctuation, retain alphanumeric characters and hyphens
            keyword_words = re.findall(r"\b\w+\b", keyword_lower)
            # Filter out words that are too short (less than 3 characters) and common stop words
            stop_words = {
                "the",
                "a",
                "an",
                "and",
                "or",
                "but",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "with",
                "by",
                "is",
                "are",
                "was",
                "were",
                "be",
                "been",
                "will",
                "would",
                "should",
                "could",
                "may",
                "might",
                "can",
                "must",
            }
            keyword_words = [w for w in keyword_words if len(w) >= 3 and w not in stop_words]

            # If no keywords are extracted, use the original keywords
            if not keyword_words:
                keyword_words = [keyword_lower]

            logger.info(f"Extracted keywords: {keyword_words} from '{keyword}'")

            filtered = []
            scored_markets = []  # Used to store scored results
            top_candidates = []  # Used to store close matching candidates (for debugging)

            for market in all_markets:
                question = market.get("question", "").lower()
                slug = (market.get("slug") or "").lower()
                market_id = str(market.get("market_id") or "")

                score = 0
                match_reason = ""

                # 1. Exact match (highest priority, score 100)
                if keyword_lower in question:
                    score = 100
                    match_reason = "exact_match_question"
                elif keyword_lower == slug:
                    score = 100
                    match_reason = "exact_match_slug"

                # 2. If the keyword looks like a slug, check the slug field
                if score < 100 and keyword_is_slug:
                    if keyword_lower == slug:
                        score = 100
                        match_reason = "exact_slug_match"
                    elif keyword_lower in slug or slug in keyword_lower:
                        score = 90
                        match_reason = "partial_slug_match"

                # 3. If the keyword is a pure number, check market_id
                if score < 90 and keyword_lower.isdigit():
                    if keyword_lower == market_id:
                        score = 100
                        match_reason = "market_id_match"

                # 4. Keyword matching: Check whether all keywords are in the question
                if score < 90 and keyword_words:
                    # Calculate the number of matching keywords
                    matched_words = sum(1 for word in keyword_words if word in question or word in slug)
                    if matched_words > 0:
                        # Match rate
                        match_ratio = matched_words / len(keyword_words)
                        # Lower the threshold: from 60% to 40% to improve the matching rate
                        if match_ratio >= 0.4:
                            score = int(60 + match_ratio * 30)  # 60-90 minutes
                            match_reason = f"keyword_match_{matched_words}/{len(keyword_words)}"
                        else:
                            # Log close matching candidates (for debugging)
                            if matched_words >= 1 and len(top_candidates) < 5:
                                top_candidates.append(
                                    (match_ratio, market.get("question", "")[:80], matched_words, len(keyword_words))
                                )

                # 5. Partial matching: Check whether the main part of the keyword is in the question
                if score < 60 and keyword_words:
                    # If the keyword contains multiple words, try to match the main part
                    if len(keyword_words) > 1:
                        # Take the first 3 most important words (usually nouns)
                        important_words = keyword_words[:3]
                        matched_important = sum(1 for word in important_words if word in question or word in slug)
                        # Lower the requirement: match at least 1 important word
                        if matched_important >= 1:
                            score = 50
                            match_reason = f"important_words_match_{matched_important}/{len(important_words)}"

                if score >= 50:  # Lower the minimum score requirement from 60 to 50
                    scored_markets.append((score, market, match_reason))
                    logger.debug(f"Matched (score={score}, reason={match_reason}): {market.get('question', '')[:60]}")

            # Sort by score, take the first limit
            scored_markets.sort(key=lambda x: x[0], reverse=True)
            filtered = [market for score, market, reason in scored_markets[:limit]]

            # Output debugging information
            if len(scored_markets) == 0 and top_candidates:
                logger.warning("No exact matches found. Top candidates (partial matches):")
                for ratio, question, matched, total in top_candidates:
                    logger.warning(f"  - {question} (matched {matched}/{total} keywords, ratio={ratio:.2f})")

            logger.info(
                f"Filtered {len(filtered)} markets matching keyword '{keyword}' from API (from {len(all_markets)} total markets, {len(scored_markets)} scored matches)"
            )
            if len(scored_markets) > 0:
                logger.info(f"Top match: {filtered[0].get('question', '')[:80]} (score={scored_markets[0][0]})")
            return filtered

        except Exception as e:
            logger.error(f"Failed to search markets: {e}", exc_info=True)
            return []

    def _get_cached_markets(self, category: str = None, limit: int = 50) -> Optional[List[Dict]]:
        """Read market data from the database cache."""
        try:
            with get_db_connection() as db:
                cur = db.cursor()

                # Check cache is fresh (within 5 minutes)
                cutoff_time = datetime.now() - timedelta(seconds=self.cache_ttl)

                query = """
                    SELECT market_id, question, category, current_probability,
                           volume_24h, liquidity, end_date_iso, status, outcome_tokens
                    FROM qd_polymarket_markets
                    WHERE status = 'active' AND updated_at > %s
                """
                params = [cutoff_time]

                if category:
                    query += " AND category = %s"
                    params.append(category)

                query += " ORDER BY volume_24h DESC LIMIT %s"
                params.append(limit)

                cur.execute(query, params)
                rows = cur.fetchall()
                cur.close()

                if rows:
                    result = []
                    for row in rows:
                        market_id = str(row.get("market_id") or "")
                        slug = row.get("slug")
                        # Make sure to use the correct URL building method
                        polymarket_url = self._build_polymarket_url(slug, market_id)
                        result.append(
                            {
                                "market_id": market_id,
                                "question": row.get("question") or "",
                                "category": row.get("category") or "other",
                                "current_probability": float(row.get("current_probability") or 0),
                                "volume_24h": float(row.get("volume_24h") or 0),
                                "liquidity": float(row.get("liquidity") or 0),
                                "end_date_iso": row.get("end_date_iso"),
                                "status": row.get("status") or "active",
                                "outcome_tokens": row.get("outcome_tokens") if row.get("outcome_tokens") else {},
                                "polymarket_url": polymarket_url,
                                "slug": slug if slug and not str(slug).isdigit() else None,
                            }
                        )
                    return result

            return None
        except Exception as e:
            logger.debug(f"Failed to get cached markets: {e}")
            return None

    def _fetch_markets_from_api(self, category: str = None, limit: int = 50) -> List[Dict]:
        """
        Retrieve market data from the Polymarket Gamma API
        Use the officially recommended /events endpoint
        """
        try:
            # Use the /events endpoint of Gamma API (official recommended method)
            markets = self._fetch_from_gamma_api(category, limit)
            if markets:
                # Sort by volume_24h in descending order (because the API does not support the order parameter, local sorting is required)
                markets.sort(key=lambda x: x.get("volume_24h", 0), reverse=True)
                return markets[:limit]  # Return the first limit after sorting

            # If the API returns an empty list, record a warning (it may be that the API is temporarily unavailable, network problems or throttling)
            logger.warning(
                f"Gamma API failed to fetch markets for category '{category}' (possible reasons: API is temporarily unavailable, network problems, current limiting or returning empty data)"
            )
            return []

        except Exception as e:
            logger.error(f"Failed to fetch markets from API: {e}", exc_info=True)
            return []

    def _fetch_from_gamma_api(self, category: str = None, limit: int = 50) -> List[Dict]:
        """
        Retrieve market data from the Polymarket Gamma API
        Use the officially recommended /events endpoint
        """
        try:
            # Use the /events endpoint to obtain active markets (recommended method)
            # According to official documentation: https://docs.polymarket.com/market-data/fetching-markets
            # Supported values ​​for the order parameter: volume_24hr, volume, liquidity, competitive, start_date, end_date
            # But some endpoints may not support it, try without the order parameter first.
            url = f"{self.gamma_api}/events"
            params = {
                "active": "true",
                "closed": "false",
                "limit": min(limit * 2, 100),  # Get more data for sorting and filtering
            }

            # Try adding sorting parameters (if supported by API)
            # According to the documentation, possible sorting fields: volume_24hr, volume, liquidity, etc.
            # If the API is not supported, it will be removed after a 422 error.

            # If a category is specified, it needs to be filtered by tag_id
            # Note: You need to get the tag_id first, and use keywords to infer it here.
            if category:
                # You can try filtering by search or tags
                # Get them all temporarily, then filter when parsing
                pass

            logger.info(f"Fetching from Gamma API: {url} with params: {params}")
            response = self.session.get(url, params=params, timeout=15)

            logger.info(f"Gamma API response status: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.debug(
                        f"Gamma API returned data type: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'list'}"
                    )

                    # The Gamma API may return a list or an object containing a data field
                    if isinstance(data, list):
                        logger.info(f"Gamma API returned list with {len(data)} items")
                        markets = self._parse_gamma_events(data, category)
                        logger.info(f"Parsed {len(markets)} markets from Gamma API")
                        return markets
                    elif isinstance(data, dict):
                        # Possibly {"data": [...]} format
                        if "data" in data:
                            events_list = data["data"]
                            logger.info(
                                f"Gamma API returned dict with 'data' field containing {len(events_list) if isinstance(events_list, list) else 'non-list'} items"
                            )
                            markets = self._parse_gamma_events(events_list, category)
                            logger.info(f"Parsed {len(markets)} markets from Gamma API")
                            return markets
                        # Or directly the event object
                        elif "id" in data or "slug" in data:
                            logger.info("Gamma API returned single event object")
                            markets = self._parse_gamma_events([data], category)
                            logger.info(f"Parsed {len(markets)} markets from Gamma API")
                            return markets
                        else:
                            logger.warning(f"Gamma API returned dict with unexpected keys: {list(data.keys())}")
                            logger.debug(f"Full response: {str(data)[:500]}")

                    logger.warning(f"Gamma API returned unexpected format: {type(data)}")
                    return []
                except json.JSONDecodeError as je:
                    logger.error(f"Gamma API returned invalid JSON: {je}")
                    logger.error(f"Response text (first 500 chars): {response.text[:500]}")
                    return []

            # Non-200 status code
            status_code = response.status_code
            if status_code == 429:
                logger.warning(
                    "Gamma API rate limited (429). Suggestion: Try again later or reduce the request frequency"
                )
            elif status_code == 503:
                logger.warning("Gamma API service unavailable (503). Polymarket API may be under maintenance")
            elif status_code >= 500:
                logger.warning(
                    f"Gamma API server error ({status_code}). The Polymarket server may be temporarily unavailable"
                )
            else:
                logger.warning(f"Gamma API returned status {status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            logger.debug(f"Response text (first 500 chars): {response.text[:500]}")
            return []

        except requests.exceptions.Timeout:
            logger.warning(
                "Gamma API request timeout after 15 seconds (possible reason: network delay or slow API response)"
            )
            return []
        except requests.exceptions.ConnectionError as ce:
            logger.warning(
                f"Gamma API connection error: {ce} (Possible reason: network connection problem or Polymarket API is unreachable)"
            )
            return []
        except Exception as e:
            logger.warning(
                f"Gamma API failed: {e} (Possible reasons: API format change, network problem or service abnormality)"
            )
            return []

    def _parse_gamma_events(self, events_data: List[Dict], category_filter: str = None) -> List[Dict]:
        """
        Parse event data returned by the Gamma API
        The /events endpoint of the Gamma API returns event objects, each containing associated market data

        According to the official documentation, the event object structure is:
        - The event object contains a markets array
        - Each market contains fields such as clobTokenIds and outcomePrices
        """
        parsed = []
        if not events_data:
            logger.warning("_parse_gamma_events received empty events_data")
            return parsed

        logger.info(f"Parsing {len(events_data)} events from Gamma API")

        # Record the key of the first event for debugging
        if events_data:
            first_event_keys = list(events_data[0].keys())[:10]
            logger.info(f"First event keys: {first_event_keys}")
            logger.debug(f"First event sample: {str(events_data[0])[:500]}")

        for idx, event in enumerate(events_data):
            try:
                # Gamma API event object structure
                # The event may have multiple markets (markets field), or directly contain market information
                markets = event.get("markets", [])

                # If the event does not have a markets field, the event itself may be market data.
                if not markets:
                    # Check whether it is a market object directly (with question or title field)
                    if "question" in event or "title" in event or "slug" in event:
                        markets = [event]
                    else:
                        if idx < 3:  # Only record the details of the first 3
                            logger.debug(
                                f"Event {idx} has no markets and doesn't look like a market. Keys: {list(event.keys())[:10]}"
                            )
                        continue

                if idx < 3:  # Only record the details of the first 3
                    logger.debug(f"Processing event {idx} with {len(markets)} markets")

                for market_idx, market in enumerate(markets):
                    # Extract basic market information
                    market_id = market.get("id") or market.get("slug") or event.get("id") or event.get("slug", "")
                    question = (
                        market.get("question") or event.get("question") or market.get("title") or event.get("title", "")
                    )

                    if idx < 3 and market_idx < 2:  # Record detailed information of the first few markets
                        logger.info(
                            f"Event {idx}, Market {market_idx}: id={market_id}, question={question[:50] if question else 'None'}, event_slug={event.get('slug')}, market_slug={market.get('slug')}, keys={list(market.keys())[:10]}"
                        )

                    if not question:
                        if idx < 3:
                            logger.warning(
                                f"Event {idx}, Market {market_idx}: No question found, skipping. Market keys: {list(market.keys())[:10]}"
                            )
                        continue

                    # Infer category
                    inferred_category = self._infer_category(question)

                    # If category filtering is specified, filter
                    if category_filter and inferred_category != category_filter:
                        continue

                    # Get probability and outcome data
                    current_probability = 50.0
                    outcome_tokens = {}

                    # Method 1: Get real-time prices from CLOB API (most accurate)
                    try:
                        condition_id = market.get("conditionId") or event.get("conditionId")
                        if condition_id:
                            prices = self._get_market_prices_from_clob(condition_id)
                            if prices:
                                yes_price = prices.get("YES", 0)
                                no_price = prices.get("NO", 0)
                                if yes_price > 0:
                                    current_probability = yes_price * 100 if yes_price <= 1 else yes_price
                                    outcome_tokens["YES"] = {
                                        "price": yes_price if yes_price <= 1 else yes_price / 100,
                                        "volume": 0,
                                    }
                                if no_price > 0:
                                    outcome_tokens["NO"] = {
                                        "price": no_price if no_price <= 1 else no_price / 100,
                                        "volume": 0,
                                    }
                    except Exception as e:
                        logger.debug(f"Failed to get prices from CLOB API: {e}")

                    # Method 2: Process the outcomePrices field (may be a JSON string)
                    if current_probability == 50.0:
                        outcome_prices_str = market.get("outcomePrices") or event.get("outcomePrices")
                        if outcome_prices_str:
                            try:
                                if isinstance(outcome_prices_str, str):
                                    outcome_prices = json.loads(outcome_prices_str)
                                else:
                                    outcome_prices = outcome_prices_str

                                # outcomePrices is usually in the format ["0.65", "0.35"], corresponding to YES and NO
                                if isinstance(outcome_prices, list) and len(outcome_prices) >= 2:
                                    yes_price = float(outcome_prices[0]) if outcome_prices[0] else 0
                                    no_price = float(outcome_prices[1]) if outcome_prices[1] else 0
                                    current_probability = yes_price * 100 if yes_price <= 1 else yes_price
                                    outcome_tokens["YES"] = {
                                        "price": yes_price if yes_price <= 1 else yes_price / 100,
                                        "volume": 0,
                                    }
                                    outcome_tokens["NO"] = {
                                        "price": no_price if no_price <= 1 else no_price / 100,
                                        "volume": 0,
                                    }
                            except Exception as e:
                                logger.debug(f"Failed to parse outcomePrices: {e}")

                    # Get outcomes from market or event
                    # outcomes may be an object array, a string array, or need to be parsed from other fields
                    outcomes = market.get("outcomes") or market.get("tokens") or event.get("outcomes") or []

                    # Process the outcomes array (may be an object or a string)
                    for outcome in outcomes:
                        try:
                            # If outcome is a string, skip or try to parse
                            if isinstance(outcome, str):
                                # May be a simple string identifier such as "YES" or "NO"
                                outcome_upper = outcome.upper()
                                if "YES" in outcome_upper:
                                    if "YES" not in outcome_tokens:
                                        outcome_tokens["YES"] = {"price": 0.5, "volume": 0}
                                elif "NO" in outcome_upper:
                                    if "NO" not in outcome_tokens:
                                        outcome_tokens["NO"] = {"price": 0.5, "volume": 0}
                                continue

                            # outcome is an object
                            if not isinstance(outcome, dict):
                                continue

                            title = str(outcome.get("title") or outcome.get("name", "")).upper()
                            # Get the price (may be price, probability or currentPrice)
                            price = float(
                                outcome.get("price") or outcome.get("probability") or outcome.get("currentPrice") or 0
                            )

                            if "YES" in title or title == "YES" or outcome.get("outcome") == "Yes":
                                current_probability = price * 100 if price <= 1 else price
                                outcome_tokens["YES"] = {
                                    "price": price if price <= 1 else price / 100,
                                    "volume": float(outcome.get("volume", outcome.get("volume24hr", 0)) or 0),
                                }
                            elif "NO" in title or title == "NO" or outcome.get("outcome") == "No":
                                outcome_tokens["NO"] = {
                                    "price": price if price <= 1 else price / 100,
                                    "volume": float(outcome.get("volume", outcome.get("volume24hr", 0)) or 0),
                                }
                        except Exception as e:
                            logger.debug(f"Failed to parse outcome: {e}")
                            continue

                    # If outcomes are not found, try to get probabilities from other fields
                    if current_probability == 50.0:
                        # Try to get it from the probability field of the market
                        prob = market.get("probability") or market.get("yesProbability") or event.get("probability")
                        if prob:
                            current_probability = float(prob) * 100 if float(prob) <= 1 else float(prob)

                    # Get trading volume and liquidity
                    volume_24h = float(
                        market.get("volume_24hr")
                        or market.get("volume24hr")
                        or market.get("volume_24h")
                        or event.get("volume_24hr")
                        or event.get("volume24hr")
                        or 0
                    )

                    liquidity = float(
                        market.get("liquidity") or market.get("totalLiquidity") or event.get("liquidity") or 0
                    )

                    # Parse end date
                    end_date_iso = None
                    end_date = (
                        market.get("endDate") or market.get("end_date") or event.get("endDate") or event.get("end_date")
                    )
                    if end_date:
                        try:
                            if isinstance(end_date, (int, float)):
                                end_date_iso = datetime.fromtimestamp(end_date).isoformat() + "Z"
                            elif isinstance(end_date, str):
                                # Try to parse the ISO format string
                                end_date_iso = end_date
                        except Exception as e:
                            logger.debug(f"Failed to parse end date: {e}")

                    # Get the slug used to build the URL
                    # According to Polymarket API documentation: slug should be obtained directly from the data returned by the API
                    # URL format: https://polymarket.com/event/{slug}
                    # slug is a string identifier, not a numeric ID
                    slug = None

                    # Get the slug from the event first (because the event contains markets)
                    if event.get("slug"):
                        slug_str = str(event.get("slug", "")).strip()
                        # If the slug is not a pure number and contains letters or hyphens, it is a valid slug
                        if (
                            slug_str
                            and not slug_str.isdigit()
                            and ("-" in slug_str or any(c.isalpha() for c in slug_str))
                        ):
                            slug = slug_str

                    # If the event does not have a valid slug, try to get it from the market
                    if not slug and market.get("slug"):
                        slug_str = str(market.get("slug", "")).strip()
                        if (
                            slug_str
                            and not slug_str.isdigit()
                            and ("-" in slug_str or any(c.isalpha() for c in slug_str))
                        ):
                            slug = slug_str

                    # If there is still no valid slug, try to obtain it through API query
                    if not slug and market_id:
                        try:
                            # Use the markets endpoint to query by ID to obtain complete slug information
                            detail_market = self._fetch_market_detail_by_id(market_id)
                            if detail_market and detail_market.get("slug"):
                                slug_str = str(detail_market.get("slug", "")).strip()
                                if (
                                    slug_str
                                    and not slug_str.isdigit()
                                    and ("-" in slug_str or any(c.isalpha() for c in slug_str))
                                ):
                                    slug = slug_str
                        except Exception as e:
                            logger.debug(f"Failed to fetch slug for market {market_id}: {e}")

                    # Build URL (using unified helper methods)
                    polymarket_url = self._build_polymarket_url(slug, market_id)
                    if not slug:
                        logger.warning(f"Market {market_id} has no valid slug, using markets endpoint as fallback")

                    market_data = {
                        "market_id": market_id,
                        "question": question,
                        "category": inferred_category,
                        "current_probability": round(current_probability, 2),
                        "volume_24h": volume_24h,
                        "liquidity": liquidity,
                        "end_date_iso": end_date_iso,
                        "status": "active" if market.get("active", event.get("active", True)) else "closed",
                        "outcome_tokens": outcome_tokens,
                        "polymarket_url": polymarket_url,
                        "slug": slug if slug else None,  # Save slug (if not a number)
                    }

                    parsed.append(market_data)

                    if idx < 3 and market_idx < 2:  # Record successfully parsed markets
                        logger.info(
                            f"Successfully parsed market: {question[:50]}, prob={current_probability:.1f}%, volume={volume_24h}"
                        )

            except Exception as e:
                logger.warning(
                    f"Failed to parse event {idx} (id={event.get('id', event.get('slug', 'unknown'))}): {e}",
                    exc_info=True,
                )
                continue

        logger.info(f"Successfully parsed {len(parsed)} markets from {len(events_data)} events")
        return parsed

    def _parse_rest_markets(self, markets_data: List[Dict]) -> List[Dict]:
        """Parse REST API data"""
        parsed = []
        for market in markets_data:
            try:
                # Extract basic information
                market_id = market.get("id") or market.get("slug") or market.get("market_id", "")
                question = market.get("question") or market.get("title", "")

                # Calculate probability
                current_probability = 50.0
                outcome_tokens = {}

                if "outcomes" in market:
                    for outcome in market["outcomes"]:
                        title = str(outcome.get("title", "")).upper()
                        price = float(outcome.get("price", outcome.get("probability", 0)) or 0)
                        if "YES" in title or title == "YES":
                            current_probability = price * 100
                            outcome_tokens["YES"] = {"price": price, "volume": float(outcome.get("volume", 0) or 0)}
                        elif "NO" in title or title == "NO":
                            outcome_tokens["NO"] = {"price": price, "volume": float(outcome.get("volume", 0) or 0)}

                volume_24h = float(market.get("volume_24h", market.get("volume", 0)) or 0)
                liquidity = float(market.get("liquidity", 0) or 0)

                # inferred category
                category = self._infer_category(question)

                # parse end date
                end_date_iso = market.get("end_date") or market.get("endDate")
                if isinstance(end_date_iso, (int, float)):
                    try:
                        end_date_iso = datetime.fromtimestamp(end_date_iso).isoformat() + "Z"
                    except Exception as e:
                        logger.debug(f"Failed to parse end date for market {market_id}: {e}")
                        end_date_iso = None

                # Get the slug used to build the URL
                slug = None
                slug_str = str(market.get("slug", "")).strip() if market.get("slug") else ""

                # Check if the slug is valid (not a number and contains letters or hyphens)
                if slug_str and not slug_str.isdigit() and ("-" in slug_str or any(c.isalpha() for c in slug_str)):
                    slug = slug_str
                else:
                    # If the slug is invalid, try to obtain it through API query
                    try:
                        detail_market = self._fetch_market_detail_by_id(market_id)
                        if detail_market and detail_market.get("slug"):
                            slug_str = str(detail_market.get("slug", "")).strip()
                            if (
                                slug_str
                                and not slug_str.isdigit()
                                and ("-" in slug_str or any(c.isalpha() for c in slug_str))
                            ):
                                slug = slug_str
                    except Exception as e:
                        logger.debug(f"Failed to fetch slug for market {market_id}: {e}")

                # Build URL (using unity helper methods)
                polymarket_url = self._build_polymarket_url(slug, market_id)
                if not slug:
                    logger.warning(f"Market {market_id} has no valid slug, using markets endpoint as fallback")

                parsed.append(
                    {
                        "market_id": market_id,
                        "question": question,
                        "category": category,
                        "current_probability": round(current_probability, 2),
                        "volume_24h": volume_24h,
                        "liquidity": liquidity,
                        "end_date_iso": end_date_iso,
                        "status": "active" if market.get("active", True) else "closed",
                        "outcome_tokens": outcome_tokens,
                        "polymarket_url": polymarket_url,
                        "slug": slug if slug else None,
                    }
                )
            except Exception as e:
                logger.debug(f"Failed to parse market {market.get('id')}: {e}")
                continue

        return parsed

    def _infer_category(self, question: str) -> str:
        """Infer categories from questions"""
        question_lower = question.lower()

        # Cryptocurrency Keywords
        crypto_keywords = [
            "btc",
            "bitcoin",
            "eth",
            "ethereum",
            "sol",
            "solana",
            "crypto",
            "token",
            "coin",
            "defi",
            "nft",
        ]
        if any(kw in question_lower for kw in crypto_keywords):
            return "crypto"

        # political keywords
        politics_keywords = [
            "election",
            "president",
            "trump",
            "biden",
            "senate",
            "congress",
            "vote",
            "political",
            "democrat",
            "republican",
        ]
        if any(kw in question_lower for kw in politics_keywords):
            return "politics"

        # economic keywords
        economics_keywords = [
            "gdp",
            "inflation",
            "unemployment",
            "fed",
            "federal reserve",
            "interest rate",
            "economic",
            "economy",
            "recession",
            "gdp growth",
            "cpi",
            "ppi",
        ]
        if any(kw in question_lower for kw in economics_keywords):
            return "economics"

        # Sports keywords
        sports_keywords = [
            "nfl",
            "nba",
            "mlb",
            "soccer",
            "football",
            "basketball",
            "baseball",
            "championship",
            "world cup",
            "olympics",
            "super bowl",
            "stanley cup",
            "world series",
        ]
        if any(kw in question_lower for kw in sports_keywords):
            return "sports"

        # Technology keywords
        tech_keywords = [
            "ai",
            "artificial intelligence",
            "chatgpt",
            "openai",
            "tech",
            "technology",
            "apple",
            "google",
            "microsoft",
            "meta",
            "tesla",
            "ipo",
            "startup",
        ]
        if any(kw in question_lower for kw in tech_keywords):
            return "tech"

        # financial keywords
        finance_keywords = [
            "stock",
            "s&p",
            "dow",
            "nasdaq",
            "market cap",
            "earnings",
            "revenue",
            "profit",
            "bank",
            "banking",
            "financial",
            "trading",
        ]
        if any(kw in question_lower for kw in finance_keywords):
            return "finance"

        # geopolitical keywords
        geopolitics_keywords = [
            "war",
            "conflict",
            "russia",
            "ukraine",
            "china",
            "taiwan",
            "north korea",
            "iran",
            "israel",
            "palestine",
            "middle east",
            "nato",
            "sanctions",
        ]
        if any(kw in question_lower for kw in geopolitics_keywords):
            return "geopolitics"

        # Cultural keywords
        culture_keywords = [
            "movie",
            "film",
            "oscar",
            "grammy",
            "award",
            "celebrity",
            "music",
            "album",
            "tv show",
            "series",
            "netflix",
            "disney",
        ]
        if any(kw in question_lower for kw in culture_keywords):
            return "culture"

        # climate keywords
        climate_keywords = [
            "climate",
            "global warming",
            "temperature",
            "carbon",
            "emission",
            "renewable",
            "solar",
            "wind energy",
            "paris agreement",
            "cop",
        ]
        if any(kw in question_lower for kw in climate_keywords):
            return "climate"

        # Entertainment keywords
        entertainment_keywords = [
            "game",
            "gaming",
            "esports",
            "tournament",
            "streaming",
            "youtube",
            "twitch",
            "podcast",
            "comic",
            "anime",
            "manga",
        ]
        if any(kw in question_lower for kw in entertainment_keywords):
            return "entertainment"

        return "other"

    def _build_polymarket_url(self, slug: Optional[str], market_id: str) -> str:
        """
        Build Polymarket URL based on slug
        Reference: https://docs.polymarket.com/market-data/fetching-markets

        Args:
            slug: slug obtained from API or database (may be None or numeric string)
            market_id: Market ID (as an alternative)

        Returns:
            Polymarket URL string
        """
        if slug:
            slug_str = str(slug).strip()
            # Check if the slug is valid (not a number and contains letters or hyphens)
            if slug_str and not slug_str.isdigit() and ("-" in slug_str or any(c.isalpha() for c in slug_str)):
                import re

                slug_clean = re.sub(r"[^a-zA-Z0-9\-]", "-", slug_str)
                slug_clean = slug_clean.strip("-")
                if slug_clean:
                    return f"https://polymarket.com/event/{slug_clean}"

        # If there is no valid slug, try to obtain the slug through the API
        if market_id:
            try:
                detail_market = self._fetch_market_detail_by_id(market_id)
                if detail_market:
                    # Try to get the slug from detail
                    event_slug = detail_market.get("slug")
                    if event_slug:
                        slug_str = str(event_slug).strip()
                        if (
                            slug_str
                            and not slug_str.isdigit()
                            and ("-" in slug_str or any(c.isalpha() for c in slug_str))
                        ):
                            import re

                            slug_clean = re.sub(r"[^a-zA-Z0-9\-]", "-", slug_str)
                            slug_clean = slug_clean.strip("-")
                            if slug_clean:
                                return f"https://polymarket.com/event/{slug_clean}"

                    # If the event does not have a slug, try to get it from markets
                    markets = detail_market.get("markets", [])
                    if markets:
                        for m in markets:
                            market_slug = m.get("slug")
                            if market_slug:
                                slug_str = str(market_slug).strip()
                                if (
                                    slug_str
                                    and not slug_str.isdigit()
                                    and ("-" in slug_str or any(c.isalpha() for c in slug_str))
                                ):
                                    import re

                                    slug_clean = re.sub(r"[^a-zA-Z0-9\-]", "-", slug_str)
                                    slug_clean = slug_clean.strip("-")
                                    if slug_clean:
                                        return f"https://polymarket.com/event/{slug_clean}"
            except Exception as e:
                logger.debug(f"Failed to fetch slug for market {market_id}: {e}")

        # If all else fails, return to the search page (more reliable)
        # Note: Polymarket's URL format may have changed, use search as fallback
        return f"https://polymarket.com/search?q={market_id}"

    def _fetch_market_detail_by_id(self, market_id: str) -> Optional[Dict]:
        """
        Get market details from API by market ID (used to get slug)
        Reference: https://docs.polymarket.com/market-data/fetching-markets
        """
        try:
            # Method 1: Try querying through the events endpoint (recommended because events include markets)
            url = f"{self.gamma_api}/events"
            params = {"active": "true", "closed": "false", "limit": 100}
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                events = response.json()
                if isinstance(events, list):
                    for event in events:
                        markets = event.get("markets", [])
                        if not markets and ("question" in event or "slug" in event):
                            markets = [event]

                        for market in markets:
                            m_id = market.get("id") or market.get("slug") or ""
                            e_id = event.get("id") or event.get("slug") or ""
                            # Match market_id or event_id
                            if str(m_id) == str(market_id) or str(e_id) == str(market_id):
                                # Return event (because event contains slug)
                                return event
                elif isinstance(events, dict):
                    if "data" in events:
                        events_list = events["data"]
                        for event in events_list:
                            markets = event.get("markets", [])
                            if not markets and ("question" in event or "slug" in event):
                                markets = [event]

                            for market in markets:
                                m_id = market.get("id") or market.get("slug") or ""
                                e_id = event.get("id") or event.get("slug") or ""
                                if str(m_id) == str(market_id) or str(e_id) == str(market_id):
                                    return event

            # Method 2: Try querying through the markets endpoint
            url = f"{self.gamma_api}/markets"
            params = {"id": market_id, "limit": 1}
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                elif isinstance(data, dict) and "id" in data:
                    return data

            return None
        except Exception as e:
            logger.debug(f"Failed to fetch market detail by ID {market_id}: {e}")
            return None

    def _fetch_market_by_slug(self, slug: str) -> Optional[Dict]:
        """
        Query the market directly through slug (the most efficient way)
        According to Polymarket API documentation: https://docs.polymarket.com/market-data/fetching-markets
        You can use /markets?slug=xxx to query directly
        """
        try:
            # Method 1: Try querying the slug directly through the markets endpoint
            url = f"{self.gamma_api}/markets"
            params = {"slug": slug, "limit": 10}
            logger.info(f"Fetching market by slug from Gamma API: {url} with params: {params}")
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    # Parse the returned market data
                    markets = self._parse_gamma_events(data)
                    # Exact match slug
                    for market in markets:
                        market_slug = market.get("slug", "").lower()
                        if market_slug == slug.lower() or slug.lower() in market_slug:
                            logger.info(f"Found market by slug: {slug}")
                            return market
                    # If there is no exact match, return the first
                    if markets:
                        logger.info(f"Found market by slug (fuzzy match): {slug}")
                        return markets[0]
                elif isinstance(data, dict):
                    # single market object
                    markets = self._parse_gamma_events([data])
                    if markets:
                        logger.info(f"Found market by slug: {slug}")
                        return markets[0]

            # Method 2: Try to query through the events endpoint (events may contain slug information)
            url = f"{self.gamma_api}/events"
            params = {"active": "true", "closed": "false", "limit": 100}
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                events = data if isinstance(data, list) else (data.get("data", []) if isinstance(data, dict) else [])

                # Find the matching slug in the returned event
                for event in events:
                    event_slug = (event.get("slug") or "").lower()
                    if event_slug == slug.lower() or slug.lower() in event_slug:
                        parsed = self._parse_gamma_events([event])
                        if parsed:
                            logger.info(f"Found market by slug via events: {slug}")
                            return parsed[0]

            logger.warning(f"Market with slug '{slug}' not found via direct query")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch market by slug {slug}: {e}", exc_info=True)
            return None

    def _fetch_market_from_api(self, market_id: str) -> Optional[Dict]:
        """
        Get individual market data from Gamma API
        Support query by slug or id
        """
        try:
            # Determine whether it is slug or market_id
            is_slug = not market_id.isdigit() and ("-" in market_id or any(c.isalpha() for c in market_id))

            # If it is a slug, the direct query method is preferred.
            if is_slug:
                market = self._fetch_market_by_slug(market_id)
                if market:
                    return market

            # Method 1: Query through markets endpoint (supports id and slug)
            url = f"{self.gamma_api}/markets"
            params = {"id": market_id, "limit": 10} if not is_slug else {"slug": market_id, "limit": 10}
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    markets = self._parse_gamma_events(data)
                    if markets:
                        return markets[0]
                elif isinstance(data, dict):
                    markets = self._parse_gamma_events([data])
                    if markets:
                        return markets[0]

            # Method 2: Search via events endpoint (as an alternative)
            url = f"{self.gamma_api}/events"
            params = {"active": "true", "closed": "false", "limit": 100}
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                events = data if isinstance(data, list) else (data.get("data", []) if isinstance(data, dict) else [])

                # Find matching markets in returned events
                for event in events:
                    markets = event.get("markets", [])
                    if not markets:
                        markets = [event]

                    for market in markets:
                        m_id = market.get("id") or market.get("slug") or event.get("id") or event.get("slug", "")
                        if str(m_id) == str(market_id) or market.get("slug") == market_id:
                            parsed = self._parse_gamma_events([event])
                            if parsed:
                                return parsed[0]

            return None

        except Exception as e:
            logger.error(f"Failed to fetch market {market_id}: {e}", exc_info=True)
            return None

    def _save_markets_to_db(self, markets: List[Dict]):
        """Save market data to database"""
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                for market in markets:
                    # Get the slug, but don't use it if it's a number (numbers are not valid slugs)
                    slug = market.get("slug") or None
                    # If the slug is a number, it means it is not a valid slug and is set to None.
                    if slug and str(slug).isdigit():
                        slug = None
                    # Clean slug, keep only alphanumerics and hyphens
                    import re

                    if slug:
                        slug = re.sub(r"[^a-zA-Z0-9\-]", "-", str(slug))
                        slug = slug.strip("-")
                        # If it is empty or still a number after cleaning, set to None
                        if not slug or slug.isdigit():
                            slug = None

                    cur.execute(
                        """
                        INSERT INTO qd_polymarket_markets
                        (market_id, question, category, current_probability, volume_24h,
                         liquidity, end_date_iso, status, outcome_tokens, slug, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (market_id) DO UPDATE SET
                            question = EXCLUDED.question,
                            category = EXCLUDED.category,
                            current_probability = EXCLUDED.current_probability,
                            volume_24h = EXCLUDED.volume_24h,
                            liquidity = EXCLUDED.liquidity,
                            end_date_iso = EXCLUDED.end_date_iso,
                            status = EXCLUDED.status,
                            outcome_tokens = EXCLUDED.outcome_tokens,
                            slug = EXCLUDED.slug,
                            updated_at = NOW()
                    """,
                        (
                            market.get("market_id"),
                            market.get("question"),
                            market.get("category", "other"),
                            market.get("current_probability", 50.0),
                            market.get("volume_24h", 0),
                            market.get("liquidity", 0),
                            market.get("end_date_iso"),
                            market.get("status", "active"),
                            json.dumps(market.get("outcome_tokens", {})),
                            slug,
                        ),
                    )
                db.commit()
                cur.close()
        except Exception as e:
            logger.error(f"Failed to save markets to DB: {type(e).__name__}: {e}", exc_info=True)

    def _get_sample_markets(self, category: str = None, limit: int = 50) -> List[Dict]:
        """
        Get sample market data (deprecated)
        You should now use real API data.
        """
        # No longer returns sample data, returns an empty list
        logger.warning("Sample data method called, but real API should be used instead")
        return []
