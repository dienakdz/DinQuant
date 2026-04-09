"""
Polymarket Prediction Market Analyzer
Analyze prediction markets and generate AI predictions and trading opportunity recommendations
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from app.data_sources.polymarket import PolymarketDataSource
from app.services.llm import LLMService
from app.services.market_data_collector import get_market_data_collector
from app.utils.db import get_db_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PolymarketAnalyzer:
    """Prediction Market AI Analyzer"""

    def __init__(self):
        self.llm_service = LLMService()
        self.data_collector = get_market_data_collector()
        self.polymarket_source = PolymarketDataSource()

    def analyze_market(
        self, market_id: str, user_id: int = None, use_cache: bool = True, language: str = "zh-CN", model: str = None
    ) -> Dict:
        """
        Analyze a single prediction market

        Args:
            market_id: Market ID
            user_id: User ID (optional, for user-specific analysis)
            use_cache: whether to use cached analysis results (default True)
            language: language setting ('zh-CN' or 'en-US'), used to generate AI analysis results in the corresponding language

        Returns:
            Analysis results dictionary
        """
        try:
            # 1. Get market data
            market = self.polymarket_source.get_market_details(market_id)
            if not market:
                return {"error": "Market not found", "market_id": market_id}

            # 2. If cache is used, check whether there are cached analysis results (valid for 30 minutes)
            if use_cache:
                cached_analysis = self._get_cached_analysis(market_id, user_id)
                if cached_analysis:
                    cache_minutes = 30  # Cache for 30 minutes
                    if self._is_analysis_fresh(cached_analysis, max_age_minutes=cache_minutes):
                        logger.debug(f"Using cached analysis for market {market_id}")
                        return cached_analysis

            # 3. Collect relevant data
            related_news = self._get_related_news(market["question"])
            related_assets = self._identify_related_assets(market["question"])
            asset_data = self._get_asset_data(related_assets)

            # 4. AI analysis
            ai_result = self._ai_predict_probability(
                question=market["question"],
                current_market_prob=market["current_probability"],
                related_news=related_news,
                asset_data=asset_data,
                language=language,
            )

            # 5. Calculate opportunity scores
            opportunity_score = self._calculate_opportunity_score(
                ai_prob=ai_result["predicted_probability"],
                market_prob=market["current_probability"],
                confidence=ai_result["confidence"],
            )

            # 6. Generate recommendations
            recommendation = self._generate_recommendation(
                divergence=ai_result["predicted_probability"] - market["current_probability"],
                confidence=ai_result["confidence"],
            )

            # 7. Construct analysis results
            analysis_result = {
                "market_id": market_id,
                "ai_predicted_probability": ai_result["predicted_probability"],
                "market_probability": market["current_probability"],
                "divergence": ai_result["predicted_probability"] - market["current_probability"],
                "recommendation": recommendation,
                "confidence_score": ai_result["confidence"],
                "reasoning": ai_result["reasoning"],
                "key_factors": ai_result.get("key_factors", []),
                "risk_factors": ai_result.get("risk_factors", []),
                "related_assets": related_assets,
                "risk_level": self._assess_risk(market, ai_result),
                "opportunity_score": opportunity_score,
            }

            # 8. Save to database
            self._save_analysis_to_db(analysis_result, user_id)

            return analysis_result

        except Exception as e:
            logger.error(f"Failed to analyze market {market_id}: {e}", exc_info=True)
            return {"error": str(e), "market_id": market_id}

    def generate_asset_trading_opportunities(self, market_id: str) -> List[Dict]:
        """
        Generate trading opportunities for related assets based on prediction markets

        Args:
            market_id: prediction market ID

        Returns:
            List of asset trading opportunities
        """
        try:
            # 1. Analyze prediction markets
            market_analysis = self.analyze_market(market_id)
            if market_analysis.get("error"):
                return []

            # 2. Identify relevant assets
            related_assets = market_analysis.get("related_assets", [])
            if not related_assets:
                return []

            # 3. Perform technical analysis on each asset
            opportunities = []
            for asset in related_assets:
                try:
                    # Infer market type
                    market_type = self._infer_market(asset)

                    # Get asset data
                    asset_data = self.data_collector.collect_all(
                        market=market_type,
                        symbol=asset,
                        timeframe="1D",
                        include_polymarket=False,  # avoid loops
                    )

                    # technical analysis
                    technical_analysis = self._analyze_technical(asset_data)

                    # Incorporate Predictive Market Signals
                    if market_analysis["recommendation"] == "YES":
                        # Predicted event probability is high → related assets may rise
                        signal = "BUY" if technical_analysis.get("trend") == "bullish" else "HOLD"
                    elif market_analysis["recommendation"] == "NO":
                        # The probability of the predicted event is low → the related assets may fall
                        signal = "SELL" if technical_analysis.get("trend") == "bearish" else "HOLD"
                    else:
                        signal = "HOLD"

                    # Calculate overall confidence
                    confidence = (
                        market_analysis["confidence_score"] * 0.6 + technical_analysis.get("confidence", 50) * 0.4
                    )

                    if signal != "HOLD" and confidence > 60:
                        opportunities.append(
                            {
                                "asset": asset,
                                "market": market_type,
                                "signal": signal,
                                "confidence": round(confidence, 2),
                                "reasoning": f"预测市场分析：{market_analysis['reasoning'][:200]}。技术面：{technical_analysis.get('summary', '')[:200]}",
                                "related_prediction": {
                                    "market_id": market_id,
                                    "question": market_analysis.get("question", ""),
                                    "ai_probability": market_analysis["ai_predicted_probability"],
                                    "market_probability": market_analysis["market_probability"],
                                },
                                "entry_suggestion": technical_analysis.get("entry_suggestion", {}),
                            }
                        )
                except Exception as e:
                    logger.debug(f"Failed to analyze asset {asset} for market {market_id}: {e}")
                    continue

            # Save opportunity to database
            if opportunities:
                self._save_opportunities_to_db(market_id, opportunities)

            return opportunities

        except Exception as e:
            logger.error(f"Failed to generate asset opportunities for {market_id}: {e}")
            return []

    def _ai_predict_probability(
        self, question: str, current_market_prob: float, related_news: List, asset_data: Dict, language: str = "zh-CN"
    ) -> Dict:
        """Using AI to predict event probabilities"""
        try:
            # Build prompt based on language settings
            is_english = language.lower() in ["en", "en-us", "en_us"]

            # build prompt
            news_text = "\n".join([f"- {n.get('title', '')[:100]}" for n in related_news[:5]])

            asset_text = ""
            if asset_data:
                price_data = asset_data.get("price", {})
                indicators = asset_data.get("indicators", {})
                if price_data:
                    if is_english:
                        asset_text = f"""
Related Asset Data:
- Current Price: {price_data.get("current_price", "N/A")}
- 24h Change: {price_data.get("change_24h", 0):.2f}%
- RSI: {indicators.get("rsi", {}).get("value", "N/A")}
- MACD: {indicators.get("macd", {}).get("signal", "N/A")}
"""
                    else:
                        asset_text = f"""
相关资产数据：
- 当前价格: {price_data.get("current_price", "N/A")}
- 24h涨跌幅: {price_data.get("change_24h", 0):.2f}%
- RSI: {indicators.get("rsi", {}).get("value", "N/A")}
- MACD: {indicators.get("macd", {}).get("signal", "N/A")}
"""

            if is_english:
                prompt = f"""Analyze the following prediction market event and assess its probability of occurrence:

Question: {question}
Current Market Probability: {current_market_prob}%

Related News:
{news_text if news_text else "No related news available"}

{asset_text}

Please analyze based on the following dimensions:
1. Success rate of similar historical events
2. Current news and trends
3. Related asset price movements and technical indicators
4. Macro environment factors (VIX, DXY, interest rates, etc.)
5. Market sentiment indicators

Output JSON format:
{{
    "predicted_probability": 72.5,  // Your predicted probability (0-100)
    "confidence": 75.0,  // Confidence level (0-100)
    "reasoning": "Detailed analysis...",
    "key_factors": ["Factor 1", "Factor 2"],
    "risk_factors": ["Risk 1", "Risk 2"]
}}

IMPORTANT: All text in the JSON response (reasoning, key_factors, risk_factors) must be in English."""

                system_prompt = "You are a professional market analyst specializing in prediction market analysis. Please objectively assess the probability of events occurring based on the provided data. Respond in English."
            else:
                prompt = f"""分析以下预测市场事件，评估其发生的概率：

问题：{question}
当前市场概率：{current_market_prob}%

相关新闻：
{news_text if news_text else "暂无相关新闻"}

{asset_text}

请基于以下维度分析：
1. 历史类似事件的成功率
2. 当前新闻和趋势
3. 相关资产价格走势和技术指标
4. 宏观环境因素（VIX、DXY、利率等）
5. 市场情绪指标

输出JSON格式：
{{
    "predicted_probability": 72.5,  // 你预测的概率（0-100）
    "confidence": 75.0,  // 置信度（0-100）
    "reasoning": "详细分析...",
    "key_factors": ["因素1", "因素2"],
    "risk_factors": ["风险1", "风险2"]
}}

重要提示：JSON响应中的所有文本（reasoning、key_factors、risk_factors）必须使用中文。"""

                system_prompt = "你是一个专业的市场分析师，擅长分析预测市场事件。请基于提供的数据，客观评估事件发生的概率。请使用中文回答。"

            # Call LLM
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]

            result = self.llm_service.call_llm_api(messages=messages, use_json_mode=True, temperature=0.3)

            # Parse results
            if isinstance(result, str):
                result = json.loads(result)

            # Validation and normalization
            predicted_prob = float(result.get("predicted_probability", current_market_prob))
            predicted_prob = max(0, min(100, predicted_prob))  # Limit to 0-100

            confidence = float(result.get("confidence", 70))
            confidence = max(0, min(100, confidence))

            return {
                "predicted_probability": round(predicted_prob, 2),
                "confidence": round(confidence, 2),
                "reasoning": result.get("reasoning", ""),
                "key_factors": result.get("key_factors", []),
                "risk_factors": result.get("risk_factors", []),
            }

        except Exception as e:
            logger.error(f"AI prediction failed: {e}", exc_info=True)
            # Return to default value
            return {
                "predicted_probability": current_market_prob,
                "confidence": 50.0,
                "reasoning": f"分析失败: {str(e)}",
                "key_factors": [],
                "risk_factors": [],
            }

    def _calculate_opportunity_score(self, ai_prob: float, market_prob: float, confidence: float) -> float:
        """
        Calculate opportunity rating (0-100)

        logic:
        - The greater the difference between AI and the market, the better the opportunity
        - The higher the confidence, the better the chance
        """
        divergence = abs(ai_prob - market_prob)
        # The bigger the difference, the better the chance (maximum 40 points)
        divergence_score = min(divergence * 2, 40)
        # The higher the confidence level, the better the chance (maximum 60 points)
        confidence_score = confidence * 0.6

        return round(divergence_score + confidence_score, 2)

    def _generate_recommendation(self, divergence: float, confidence: float) -> str:
        """
        Generate recommendations: YES/NO/HOLD

        logic:
        - AI Probability > Market Probability + 5% and Confidence > 60 → YES
        - AI probability < market probability - 5% and confidence level > 60 → NO
        - Others → HOLD
        """
        if divergence > 5 and confidence > 60:
            return "YES"
        elif divergence < -5 and confidence > 60:
            return "NO"
        else:
            return "HOLD"

    def _assess_risk(self, market: Dict, ai_result: Dict) -> str:
        """Assess risk level"""
        confidence = ai_result.get("confidence", 50)
        divergence = abs(ai_result.get("predicted_probability", 50) - market.get("current_probability", 50))

        if confidence < 50 or divergence > 30:
            return "high"
        elif confidence < 70 or divergence > 15:
            return "medium"
        else:
            return "low"

    def _get_related_news(self, question: str) -> List[Dict]:
        """Get news on relevant issues"""
        # Extract keywords

        # Here you can call the news API and temporarily return an empty list
        # In actual implementation, existing news services can be called
        return []

    def _identify_related_assets(self, question: str) -> List[str]:
        """Identify related assets mentioned in the question"""
        assets = []

        # Cryptocurrency Keyword Mapping
        crypto_keywords = {
            "BTC": ["BTC", "Bitcoin", "bitcoin", "btc"],
            "ETH": ["ETH", "Ethereum", "ethereum", "eth"],
            "SOL": ["SOL", "Solana", "solana", "sol"],
            "BNB": ["BNB", "Binance", "binance", "bnb"],
            "XRP": ["XRP", "Ripple", "ripple", "xrp"],
            "ADA": ["ADA", "Cardano", "cardano", "ada"],
            "DOGE": ["DOGE", "Dogecoin", "dogecoin", "doge"],
            "AVAX": ["AVAX", "Avalanche", "avalanche", "avax"],
            "DOT": ["DOT", "Polkadot", "polkadot", "dot"],
            "MATIC": ["MATIC", "Polygon", "polygon", "matic"],
        }

        question_upper = question.upper()
        for symbol, keywords in crypto_keywords.items():
            if any(kw in question_upper for kw in keywords):
                assets.append(f"{symbol}/USDT")

        # Remove duplicates
        return list(set(assets))

    def _get_asset_data(self, assets: List[str]) -> Optional[Dict]:
        """Get asset data (get the first asset)"""
        if not assets:
            return None

        try:
            asset = assets[0]
            market_type = self._infer_market(asset)
            return self.data_collector.collect_all(market=market_type, symbol=asset, timeframe="1D")
        except Exception as e:
            logger.debug(f"Failed to get asset data for {assets}: {e}")
            return None

    def _analyze_technical(self, asset_data: Dict) -> Dict:
        """simple technical analysis"""
        if not asset_data:
            return {"trend": "neutral", "confidence": 50, "summary": "数据不足", "entry_suggestion": {}}

        indicators = asset_data.get("indicators", {})

        # Simple trend judgment
        rsi = indicators.get("rsi", {}).get("value", 50)
        macd_signal = indicators.get("macd", {}).get("signal", "neutral")

        trend = "neutral"
        if rsi > 60 and macd_signal == "bullish":
            trend = "bullish"
        elif rsi < 40 and macd_signal == "bearish":
            trend = "bearish"

        confidence = 60 if abs(rsi - 50) > 15 else 50

        return {
            "trend": trend,
            "confidence": confidence,
            "summary": f"RSI: {rsi:.1f}, MACD: {macd_signal}",
            "entry_suggestion": {},
        }

    def _infer_market(self, symbol: str) -> str:
        """Infer market type"""
        if "/" in symbol:
            return "Crypto"
        elif len(symbol) <= 5 and symbol.isupper():
            return "USStock"
        else:
            return "Crypto"  # default

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords"""
        # Simple keyword extraction
        words = re.findall(r"\b[A-Z][a-z]+\b|\b[A-Z]{2,}\b", text)
        return [w.lower() for w in words if len(w) > 2]

    def _get_cached_analysis(self, market_id: str, user_id: int = None) -> Optional[Dict]:
        """Get cached analysis results"""
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                query = """
                    SELECT ai_predicted_probability, market_probability, divergence,
                           recommendation, confidence_score, opportunity_score,
                           reasoning, key_factors, related_assets, created_at
                    FROM qd_polymarket_ai_analysis
                    WHERE market_id = %s
                """
                params = [market_id]

                if user_id:
                    query += " AND user_id = %s"
                    params.append(user_id)
                else:
                    query += " AND user_id IS NULL"

                query += " ORDER BY created_at DESC LIMIT 1"

                cur.execute(query, params)
                row = cur.fetchone()
                cur.close()

                if row:
                    # RealDictCursor returns the dictionary, accessed using keys
                    key_factors_raw = row.get("key_factors")
                    key_factors = []
                    if key_factors_raw:
                        try:
                            if isinstance(key_factors_raw, str):
                                key_factors = json.loads(key_factors_raw)
                            else:
                                key_factors = key_factors_raw if isinstance(key_factors_raw, list) else []
                        except Exception as e:
                            logger.debug(f"Failed to parse key_factors: {e}")
                            key_factors = []

                    return {
                        "market_id": market_id,
                        "ai_predicted_probability": float(row.get("ai_predicted_probability") or 0),
                        "market_probability": float(row.get("market_probability") or 0),
                        "divergence": float(row.get("divergence") or 0),
                        "recommendation": row.get("recommendation") or "HOLD",
                        "confidence_score": float(row.get("confidence_score") or 0),
                        "opportunity_score": float(row.get("opportunity_score") or 0),
                        "reasoning": row.get("reasoning") or "",
                        "key_factors": key_factors,
                        "related_assets": row.get("related_assets") if row.get("related_assets") else [],
                        "created_at": row.get("created_at"),
                    }
        except Exception as e:
            logger.debug(f"Failed to get cached analysis: {e}")

        return None

    def _is_analysis_fresh(self, analysis: Dict, max_age_minutes: int = 30) -> bool:
        """检查分析结果是否新鲜"""
        created_at = analysis.get("created_at")
        if not created_at:
            return False

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        age = (datetime.now() - created_at.replace(tzinfo=None)).total_seconds() / 60
        return age < max_age_minutes

    def _save_analysis_to_db(self, analysis: Dict, user_id: int = None, language: str = "en-US", model: str = None):
        """
        Save analysis results to database

        Args:
            analysis: dictionary of analysis results
            user_id: user ID
            language: language settings
            model: model used
        """
        try:
            with get_db_connection() as db:
                cur = db.cursor()

                # 1. Save to qd_polymarket_ai_analysis table (Polymarket special table)
                cur.execute(
                    """
                    INSERT INTO qd_polymarket_ai_analysis
                    (market_id, user_id, ai_predicted_probability, market_probability,
                     divergence, recommendation, confidence_score, opportunity_score,
                     reasoning, key_factors, related_assets, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                    (
                        analysis["market_id"],
                        user_id,
                        analysis["ai_predicted_probability"],
                        analysis["market_probability"],
                        analysis["divergence"],
                        analysis["recommendation"],
                        analysis["confidence_score"],
                        analysis["opportunity_score"],
                        analysis["reasoning"],
                        json.dumps(analysis.get("key_factors", [])),
                        analysis.get("related_assets", []),
                    ),
                )

                # 2. Save to the qd_analysis_tasks table at the same time (for administrator statistics and unified historical record viewing)
                market_info = analysis.get("market", {})
                market_title = (
                    market_info.get("question", "")
                    or market_info.get("title", "")
                    or f"Polymarket Market {analysis['market_id']}"
                )
                result_json = json.dumps(
                    {
                        "market_id": analysis["market_id"],
                        "market_title": market_title,
                        "analysis": analysis,
                        "market": market_info,
                        "type": "polymarket",  # Mark as Polymarket analysis
                    },
                    ensure_ascii=False,
                )

                cur.execute(
                    """
                    INSERT INTO qd_analysis_tasks
                    (user_id, market, symbol, model, language, status, result_json, error_message, created_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING id
                """,
                    (
                        int(user_id) if user_id else 1,
                        "Polymarket",  # market field
                        str(analysis["market_id"]),  # symbol field stores market_id
                        str(model) if model else "",
                        str(language),
                        "completed",
                        result_json,
                        "",
                    ),
                )
                task_row = cur.fetchone()
                task_id = task_row["id"] if task_row else None

                db.commit()
                cur.close()

                if task_id:
                    logger.debug(
                        f"Saved Polymarket analysis to both tables: task_id={task_id}, market_id={analysis['market_id']}"
                    )
        except Exception as e:
            logger.error(f"Failed to save analysis to DB: {e}")

    def _save_opportunities_to_db(self, market_id: str, opportunities: List[Dict]):
        """保存交易机会到数据库"""
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                for opp in opportunities:
                    cur.execute(
                        """
                        INSERT INTO qd_polymarket_asset_opportunities
                        (market_id, asset_symbol, asset_market, signal, confidence,
                         reasoning, entry_suggestion, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                        (
                            market_id,
                            opp["asset"],
                            opp["market"],
                            opp["signal"],
                            opp["confidence"],
                            opp["reasoning"],
                            json.dumps(opp.get("entry_suggestion", {})),
                        ),
                    )
                db.commit()
                cur.close()
        except Exception as e:
            logger.error(f"Failed to save opportunities to DB: {e}")
