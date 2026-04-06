"""
Market data collection service - dedicated to AI analysis

Design concept:
1. Data is king - first obtain data well and make it stable
2. Unified data source - completely reuse DataSourceFactory and kline_service
3. Reuse the global financial sector - reuse the cache of global_market.py for macro data and sentiment data
4. Fast and stable - does not rely on slow external services (such as Jina Reader)

Data source mapping:
- Price/K-line: DataSourceFactory (verified, consistent with K-line module and self-selected list)
- Macro data: reuse global_market.py (VIX, DXY, TNX, Fear&Greed, etc., with cache)
- News: Finnhub API (structured data, no in-depth reading required)
- Fundamentals: Finnhub (US stocks) / Fixed description (crypto)
"""

import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

import yfinance as yf
import pandas as pd

from app.data_sources import DataSourceFactory
from app.services.kline import KlineService
from app.utils.logger import get_logger
from app.config import APIKeys

logger = get_logger(__name__)


class MarketDataCollector:
    """
    Market data collector
    
    Responsibilities: Provide complete, accurate and timely market data for AI analysis
    
    Data level:
    1. Core data (must succeed): price, K-line
    2. Analyze data (enhanced): technical indicators, fundamentals
    3. Macro data (optional): reuse global_market.py (VIX, DXY, TNX, Fear&Greed, etc.)
    4. Sentiment data (optional): news, market sentiment
    """
    
    def __init__(self):
        self.kline_service = KlineService()
        self._finnhub_client = None
        self._ak = None
        self._init_clients()
    
    def _init_clients(self):
        """Initialize external API client"""
        # Finnhub
        finnhub_key = APIKeys.FINNHUB_API_KEY
        if finnhub_key:
            try:
                import finnhub
                self._finnhub_client = finnhub.Client(api_key=finnhub_key)
            except Exception as e:
                logger.warning(f"Finnhub client init failed: {e}")
        
        # akshare (optional, for supplementary data)
        try:
            import akshare as ak
            self._ak = ak
        except ImportError:
            logger.info("akshare not installed")
    
    def collect_all(
        self,
        market: str,
        symbol: str,
        timeframe: str = "1D",
        include_macro: bool = True,
        include_news: bool = True,
        include_polymarket: bool = True,  # New: Whether to include prediction market data
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Collect all market data
        
        Args:
            market: market type (USStock, Crypto, Forex, Futures)
            symbol: target code
            timeframe: K-line cycle
            include_macro: whether to include macro data
            include_news: whether to include news
            include_polymarket: whether to include prediction market data
            timeout: total timeout (seconds)
            
        Returns:
            Complete Market Data Dictionary
        """
        start_time = time.time()
        
        data = {
            "market": market,
            "symbol": symbol,
            "timeframe": timeframe,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            # core data
            "price": None,
            "kline": None,
            "indicators": {},
            # Fundamentals
            "fundamental": {},
            "company": {},
            # Macro
            "macro": {},
            # mood
            "news": [],
            "sentiment": {},
            # prediction market
            "polymarket": [],
            # metadata
            "_meta": {
                "success_items": [],
                "failed_items": [],
                "duration_ms": 0
            }
        }
        
        # === Phase 1: Core data (parallel acquisition) ===
        with ThreadPoolExecutor(max_workers=4) as executor:
            core_futures = {
                executor.submit(self._get_price, market, symbol): "price",
                executor.submit(self._get_kline, market, symbol, timeframe, 60): "kline",
            }
            
            # If fundamentals are needed, also obtain them in parallel
            if market == 'USStock':
                core_futures[executor.submit(self._get_fundamental, market, symbol)] = "fundamental"
                core_futures[executor.submit(self._get_company, market, symbol)] = "company"
            elif market == 'Crypto':
                # Cryptocurrency 'fundamentals' are fixed description
                core_futures[executor.submit(self._get_crypto_info, symbol)] = "fundamental"
            
            try:
                for future in as_completed(core_futures, timeout=15):
                    key = core_futures[future]
                    try:
                        result = future.result(timeout=3)
                        if result:
                            data[key] = result
                            data["_meta"]["success_items"].append(key)
                        else:
                            data["_meta"]["failed_items"].append(key)
                    except Exception as e:
                        logger.warning(f"Core data fetch failed ({key}): {e}")
                        data["_meta"]["failed_items"].append(key)
            except TimeoutError:
                logger.warning(f"Core data fetch timed out for {market}:{symbol}")
        
        # Calculate technical indicators (local calculation, no external API required)
        if data.get("kline"):
            data["indicators"] = self._calculate_indicators(data["kline"])
            data["_meta"]["success_items"].append("indicators")
        
        # === Stage 2: Macro data (if required) ===
        if include_macro:
            try:
                data["macro"] = self._get_macro_data(market, timeout=10)
                if data["macro"]:
                    data["_meta"]["success_items"].append("macro")
            except Exception as e:
                logger.warning(f"Macro data fetch failed: {e}")
                data["_meta"]["failed_items"].append("macro")
        
        # === Stage 3: News/Sentiment (if needed) ===
        if include_news:
            try:
                # Get company name to improve search
                company_name = None
                if data.get("company"):
                    company_name = data["company"].get("name")
                
                news_result = self._get_news(market, symbol, company_name, timeout=8)
                data["news"] = news_result.get("news", [])
                data["sentiment"] = news_result.get("sentiment", {})
                
                if data["news"]:
                    data["_meta"]["success_items"].append("news")
            except Exception as e:
                logger.warning(f"News fetch failed: {e}")
                data["_meta"]["failed_items"].append("news")
        
        # === Stage 4: Prediction market data (if required) ===
        if include_polymarket:
            try:
                polymarket_events = self._get_polymarket_events(symbol, market)
                data["polymarket"] = polymarket_events
                if polymarket_events:
                    data["_meta"]["success_items"].append("polymarket")
            except Exception as e:
                logger.debug(f"Polymarket data fetch failed: {e}")
                data["_meta"]["failed_items"].append("polymarket")
        
        # Record the total time spent
        data["_meta"]["duration_ms"] = int((time.time() - start_time) * 1000)
        logger.info(f"Market data collection completed for {market}:{symbol} in {data['_meta']['duration_ms']}ms")
        logger.info(f"  Success: {data['_meta']['success_items']}")
        logger.info(f"  Failed: {data['_meta']['failed_items']}")
        
        return data
    
    # ==================== Core data acquisition ====================
    
    def _get_price(self, market: str, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get live prices - use kline_service (same as watchlist)
        """
        try:
            price_data = self.kline_service.get_realtime_price(market, symbol, force_refresh=True)
            if price_data and price_data.get('price', 0) > 0:
                # Safe conversion to float, handling None values
                def safe_float(val, default=0.0):
                    if val is None:
                        return default
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return default
                
                price = safe_float(price_data.get('price'))
                return {
                    "price": price,
                    "change": safe_float(price_data.get('change')),
                    "changePercent": safe_float(price_data.get('changePercent')),
                    "high": safe_float(price_data.get('high'), price),
                    "low": safe_float(price_data.get('low'), price),
                    "open": safe_float(price_data.get('open'), price),
                    "previousClose": safe_float(price_data.get('previousClose'), price),
                    "source": price_data.get('source', 'unknown')
                }
        except Exception as e:
            logger.warning(f"Price fetch failed for {market}:{symbol}: {e}")
        
        # If kline_service fails, try to get the price from the last K-line
        try:
            klines = DataSourceFactory.get_kline(market, symbol, "1D", 2)
            if klines and len(klines) > 0:
                latest = klines[-1]
                price = float(latest.get('close', 0))
                if price > 0:
                    prev_close = float(klines[-2].get('close', price)) if len(klines) > 1 else price
                    change = price - prev_close
                    change_pct = (change / prev_close * 100) if prev_close > 0 else 0
                    
                    logger.info(f"Price fetched from K-line fallback for {market}:{symbol}: ${price}")
                    return {
                        "price": price,
                        "change": round(change, 6),
                        "changePercent": round(change_pct, 2),
                        "high": float(latest.get('high', price)),
                        "low": float(latest.get('low', price)),
                        "open": float(latest.get('open', price)),
                        "previousClose": prev_close,
                        "source": "kline_fallback"
                    }
        except Exception as e:
            logger.warning(f"K-line fallback price fetch also failed for {market}:{symbol}: {e}")
        
        return None
    
    def _get_kline(
        self, market: str, symbol: str, timeframe: str, limit: int = 60
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get K-line data - use DataSourceFactory (consistent with K-line module)
        """
        try:
            klines = DataSourceFactory.get_kline(market, symbol, timeframe, limit)
            if klines and len(klines) > 0:
                return klines
        except Exception as e:
            logger.warning(f"Kline fetch failed for {market}:{symbol}: {e}")
        return None
    
    def _calculate_indicators(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate technical indicators (local calculation, no external dependencies)
        
        The return format meets the expectations of the front-end FastAnalysisReport.vue.
        Caliber description (aligned with common market terminals):
        - RSI(14): Wilder smoothing (the average amplitude of the first period is the simple average of the previous 14 periods, and then recursively).
        - MACD: Closing EMA12/EMA26 (first value = SMA of the previous N days), signal line = EMA9 of MACD (SMA seed).
        - MA: SMA. Pivot: H/L/C of the previous king. Swing High and Low: Near 20 H/L window extremes.
        - Bollinger: 20 closing SMA ± 2× population standard deviation. ATR(14): Wilder (first ATR = simple average of TR in the first 14 periods, followed by recursion).
        """
        if not klines or len(klines) < 5:
            return {}
        
        try:
            closes = [float(k.get('close', 0)) for k in klines]
            highs = [float(k.get('high', 0)) for k in klines]
            lows = [float(k.get('low', 0)) for k in klines]
            volumes = [float(k.get('volume', 0)) for k in klines]
            
            if not closes:
                return {}
            
            current_price = closes[-1]
            indicators = {}
            
            # ========== RSI ==========
            if len(closes) >= 15:
                rsi_value = self._calc_rsi(closes, 14)
                if rsi_value < 30:
                    rsi_signal = "oversold"
                elif rsi_value > 70:
                    rsi_signal = "overbought"
                else:
                    rsi_signal = "neutral"
                indicators['rsi'] = {
                    'value': round(rsi_value, 2),
                    'signal': rsi_signal,
                }
            
            # ========== MACD (SMA seed EMA, consistent with common terminals) ==========
            if len(closes) >= 34:
                macd_raw = self._calc_macd(closes)
                macd_val = macd_raw.get('MACD', 0)
                macd_sig = macd_raw.get('MACD_signal', 0)
                macd_hist = macd_raw.get('MACD_histogram', 0)
                
                if macd_val > macd_sig and macd_hist > 0:
                    macd_signal = "bullish"
                    macd_trend = "golden_cross" if macd_hist > 0 else "bullish"
                elif macd_val < macd_sig and macd_hist < 0:
                    macd_signal = "bearish"
                    macd_trend = "death_cross" if macd_hist < 0 else "bearish"
                else:
                    macd_signal = "neutral"
                    macd_trend = "consolidating"
                
                indicators['macd'] = {
                    'value': round(macd_val, 6),
                    'signal_line': round(macd_sig, 6),
                    'histogram': round(macd_hist, 6),
                    'signal': macd_signal,
                    'trend': macd_trend,
                }
            
            # ========== Moving Average ==========
            ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else current_price
            ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else current_price
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else current_price
            
            if current_price > ma5 > ma10 > ma20:
                ma_trend = "strong_uptrend"
            elif current_price > ma20:
                ma_trend = "uptrend"
            elif current_price < ma5 < ma10 < ma20:
                ma_trend = "strong_downtrend"
            elif current_price < ma20:
                ma_trend = "downtrend"
            else:
                ma_trend = "sideways"
            
            indicators['moving_averages'] = {
                'ma5': round(ma5, 6),
                'ma10': round(ma10, 6),
                'ma20': round(ma20, 6),
                'trend': ma_trend,
            }

            # Calculate the Bollinger Bands first and use them to synthesize support/resistance below (key name BB_upper / BB_lower)
            bb_for_levels: Dict[str, Any] = {}
            if len(closes) >= 20:
                bb_for_levels = self._calc_bollinger(closes, 20, 2) or {}
            
            # ========== Support/Resistance Level (Several Methods Comprehensive) ==========
            # Method 1: Pivot Points - Use previous day's data
            if len(klines) >= 2:
                prev_high = float(klines[-2].get('high', highs[-2]) if len(highs) >= 2 else current_price * 1.02)
                prev_low = float(klines[-2].get('low', lows[-2]) if len(lows) >= 2 else current_price * 0.98)
                prev_close = float(klines[-2].get('close', closes[-2]) if len(closes) >= 2 else current_price)
                
                pivot = (prev_high + prev_low + prev_close) / 3
                r1 = 2 * pivot - prev_low  # Resistance level 1
                s1 = 2 * pivot - prev_high  # Support level 1
                r2 = pivot + (prev_high - prev_low)  # Resistance Level 2
                s2 = pivot - (prev_high - prev_low)  # Support level 2
            else:
                pivot = current_price
                r1 = r2 = current_price * 1.02
                s1 = s2 = current_price * 0.98
            
            # Method 2: Recent highs and lows
            recent_highs = highs[-20:] if len(highs) >= 20 else highs
            recent_lows = lows[-20:] if len(lows) >= 20 else lows
            swing_high = max(recent_highs) if recent_highs else current_price * 1.05
            swing_low = min(recent_lows) if recent_lows else current_price * 0.95
            
            # Method 3: Bollinger upper and lower rails (consistent with the _calc_bollinger return field)
            bb_upper = bb_for_levels.get('BB_upper', swing_high)
            bb_lower = bb_for_levels.get('BB_lower', swing_low)
            
            # Comprehensive value: average/weighted by multiple methods
            resistance = round((r1 + swing_high + bb_upper) / 3, 6)
            support = round((s1 + swing_low + bb_lower) / 3, 6)
            
            indicators['levels'] = {
                'support': support,
                'resistance': resistance,
                'pivot': round(pivot, 6),
                's1': round(s1, 6),
                'r1': round(r1, 6),
                's2': round(s2, 6),
                'r2': round(r2, 6),
                'swing_high': round(swing_high, 6),
                'swing_low': round(swing_low, 6),
                'method': 'pivot_swing_bb_avg'  # Label calculation method
            }
            
            # ========== ATR and volatility (Wilder ATR, the whole sequence is recursively recursed to the latest one) ==========
            atr = 0.0
            if len(klines) >= 14:
                atr = float(self._calc_atr_wilder(klines, period=14))
                volatility_pct = (atr / current_price * 100) if current_price > 0 else 0
                
                if volatility_pct > 5:
                    volatility_level = "high"
                elif volatility_pct > 2:
                    volatility_level = "medium"
                else:
                    volatility_level = "low"
            else:
                volatility_level = "unknown"
                volatility_pct = 0
            
            indicators['volatility'] = {
                'level': volatility_level,
                'pct': round(volatility_pct, 2),
                'atr': round(atr, 6),  # Add ATR absolute value
            }
            
            # ========== Take Profit and Stop Loss Recommendations (Based on ATR and Support/Resistance) ==========
            # Stop Loss: Based on 2x ATR or support, whichever is more conservative
            atr_stop_loss = current_price - (2 * atr) if atr > 0 else current_price * 0.95
            support_stop = indicators['levels']['support']
            suggested_stop_loss = max(atr_stop_loss, support_stop * 0.99)  # Just below support
            
            # Take Profit: Based on 3x ATR or resistance level, considering risk reward ratio
            atr_take_profit = current_price + (3 * atr) if atr > 0 else current_price * 1.05
            resistance_tp = indicators['levels']['resistance']
            suggested_take_profit = min(atr_take_profit, resistance_tp * 1.01)  # Just above resistance
            
            # risk reward ratio
            risk = current_price - suggested_stop_loss
            reward = suggested_take_profit - current_price
            risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0
            
            indicators['trading_levels'] = {
                'suggested_stop_loss': round(suggested_stop_loss, 6),
                'suggested_take_profit': round(suggested_take_profit, 6),
                'risk_reward_ratio': risk_reward_ratio,
                'atr_multiplier_sl': 2.0,  # Stop loss using 2x ATR
                'atr_multiplier_tp': 3.0,  # Take profit using 3x ATR
                'method': 'atr_support_resistance'
            }
            
            # ========== Bollinger Bands (additional, same calculation as bb_for_levels) ==========
            if bb_for_levels:
                indicators['bollinger'] = bb_for_levels
            
            # ========== Volume (Additional) ==========
            if len(volumes) >= 20:
                avg_vol = sum(volumes[-20:]) / 20
                indicators['volume_ratio'] = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0
            
            # ========== Price Position (Additional) ==========
            if len(closes) >= 20:
                high_20 = max(highs[-20:])
                low_20 = min(lows[-20:])
                if high_20 > low_20:
                    indicators['price_position'] = round((current_price - low_20) / (high_20 - low_20) * 100, 1)
                else:
                    indicators['price_position'] = 50.0
            
            # ========== Overall Trends (Additional) ==========
            indicators['trend'] = ma_trend
            indicators['current_price'] = round(current_price, 6)
            
            return indicators
            
        except Exception as e:
            logger.warning(f"Indicator calculation failed: {e}")
            return {}
    
    def _calc_rsi(self, closes: List[float], period: int = 14) -> float:
        """Wilder RSI: The average amplitude of the first period is a simple average of the rise and fall of the previous period, and then it is smoothed by Wilder."""
        if len(closes) < period + 1:
            return 50.0

        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0.0 for d in deltas]
        losses = [-d if d < 0 else 0.0 for d in deltas]

        if len(gains) < period:
            return 50.0

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return round(100.0 - (100.0 / (1.0 + rs)), 2)

    def _ema_series_sma_seed(self, data: List[float], period: int) -> List[Optional[float]]:
        """
        Standard EMA: first value = first period root simple average (SMA), then EMA_t = (P_t - EMA_{t-1}) * k + EMA_{t-1}, k=2/(period+1).
        The first period-1 root is undefined and None is returned.
        """
        n = len(data)
        out: List[Optional[float]] = [None] * n
        if n < period:
            return out
        k = 2.0 / (period + 1)
        out[period - 1] = sum(data[:period]) / period
        for i in range(period, n):
            prev = out[i - 1]
            if prev is None:
                break
            out[i] = (data[i] - prev) * k + prev
        return out

    def _calc_macd(self, closes: List[float]) -> Dict[str, float]:
        """
        MACD(12,26,9)：DIF = EMA12(close) − EMA26(close)，DEA = EMA9(DIF)，柱 = DIF − DEA。
        Each EMA uses SMA seeds; DIF is defined from the 26th K onwards, and EMA9 is calculated for the DIF subsequence of the signal line pair.
        """
        n = len(closes)
        ema12 = self._ema_series_sma_seed(closes, 12)
        ema26 = self._ema_series_sma_seed(closes, 26)
        if n < 26 or ema12[-1] is None or ema26[-1] is None:
            return {'MACD': 0.0, 'MACD_signal': 0.0, 'MACD_histogram': 0.0}

        macd_sub: List[float] = []
        for i in range(25, n):
            v12 = ema12[i]
            v26 = ema26[i]
            if v12 is not None and v26 is not None:
                macd_sub.append(v12 - v26)

        if not macd_sub:
            return {'MACD': 0.0, 'MACD_signal': 0.0, 'MACD_histogram': 0.0}

        sig_series = self._ema_series_sma_seed(macd_sub, 9)
        last_macd = macd_sub[-1]
        last_sig = sig_series[-1]
        if last_sig is None:
            last_sig = last_macd

        return {
            'MACD': round(last_macd, 6),
            'MACD_signal': round(last_sig, 6),
            'MACD_histogram': round(last_macd - last_sig, 6),
        }

    def _true_ranges(self, klines: List[Dict[str, Any]]) -> List[float]:
        """True Range for each root of K (the first root is only H−L)."""
        trs: List[float] = []
        for i, k in enumerate(klines):
            h = float(k.get('high', 0))
            l = float(k.get('low', 0))
            if h <= 0 or l <= 0:
                trs.append(0.0)
                continue
            if i == 0:
                trs.append(h - l)
            else:
                pc = float(klines[i - 1].get('close', 0))
                trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return trs

    def _calc_atr_wilder(self, klines: List[Dict[str, Any]], period: int = 14) -> float:
        """Wilder ATR: First ATR = simple average of TR in the previous period, then ATR_t = (ATR_{t-1}*(period-1)+TR_t)/period."""
        trs = self._true_ranges(klines)
        if len(trs) < period:
            return 0.0
        atr = sum(trs[:period]) / period
        for i in range(period, len(trs)):
            atr = (atr * (period - 1) + trs[i]) / period
        return atr
    
    def _calc_bollinger(self, closes: List[float], period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """Bollinger Bands: The middle rail is the period closing SMA, σ is the overall standard deviation (variance/period), the upper and lower rails = middle rail ±std_dev×σ."""
        if len(closes) < period:
            return {}
        
        recent = closes[-period:]
        middle = sum(recent) / period
        
        variance = sum((x - middle) ** 2 for x in recent) / period
        std = variance ** 0.5
        
        return {
            'BB_upper': round(middle + std_dev * std, 4),
            'BB_middle': round(middle, 4),
            'BB_lower': round(middle - std_dev * std, 4),
            'BB_width': round((std_dev * std * 2) / middle * 100, 2) if middle > 0 else 0
        }
    
    # ==================== Fundamental data ====================
    
    def _get_fundamental(self, market: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get fundamental data"""
        try:
            if market == 'USStock':
                return self._get_us_fundamental(symbol)
        except Exception as e:
            logger.warning(f"Fundamental data fetch failed for {market}:{symbol}: {e}")
        return None
    
    def _get_us_fundamental(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        US stock fundamentals - Finnhub + yfinance
        Includes: basic financial indicators + financial report data (balance sheet, income statement, cash flow statement)
        """
        result = {}
        
        # === 1. Basic financial indicators (Finnhub) ===
        if self._finnhub_client:
            try:
                metrics = self._finnhub_client.company_basic_financials(symbol, 'all')
                if metrics and metrics.get('metric'):
                    m = metrics['metric']
                    result.update({
                        'pe_ratio': m.get('peBasicExclExtraTTM'),
                        'pb_ratio': m.get('pbQuarterly'),
                        'ps_ratio': m.get('psTTM'),
                        'market_cap': m.get('marketCapitalization'),
                        'dividend_yield': m.get('dividendYieldIndicatedAnnual'),
                        'beta': m.get('beta'),
                        '52w_high': m.get('52WeekHigh'),
                        '52w_low': m.get('52WeekLow'),
                        'roe': m.get('roeTTM'),
                        'eps': m.get('epsBasicExclExtraItemsTTM'),
                        'revenue_growth': m.get('revenueGrowthTTMYoy'),
                        'profit_margin': m.get('netProfitMarginTTM'),
                        'debt_to_equity': m.get('totalDebtToEquityQuarterly'),
                        'current_ratio': m.get('currentRatioQuarterly'),
                        'quick_ratio': m.get('quickRatioQuarterly'),
                    })
            except Exception as e:
                logger.debug(f"Finnhub fundamental failed for {symbol}: {e}")
        
        # === 2. yfinance supplements basic indicators ===
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
            
            # Supplement missing basic indicators
            if not result.get('pe_ratio'):
                result['pe_ratio'] = info.get('trailingPE') or info.get('forwardPE')
            if not result.get('pb_ratio'):
                result['pb_ratio'] = info.get('priceToBook')
            if not result.get('market_cap'):
                result['market_cap'] = info.get('marketCap')
            if not result.get('dividend_yield'):
                result['dividend_yield'] = info.get('dividendYield')
            if not result.get('beta'):
                result['beta'] = info.get('beta')
            if not result.get('52w_high'):
                result['52w_high'] = info.get('fiftyTwoWeekHigh')
            if not result.get('52w_low'):
                result['52w_low'] = info.get('fiftyTwoWeekLow')
            if not result.get('roe'):
                result['roe'] = info.get('returnOnEquity')
            if not result.get('eps'):
                result['eps'] = info.get('trailingEps')
            
            # Add more financial indicators
            result.update({
                'revenue': info.get('totalRevenue'),
                'gross_profit': info.get('grossProfits'),
                'operating_margin': info.get('operatingMargins'),
                'profit_margin': result.get('profit_margin') or info.get('profitMargins'),
                'ebitda': info.get('ebitda'),
                'debt': info.get('totalDebt'),
                'cash': info.get('totalCash'),
                'free_cash_flow': info.get('freeCashflow'),
                'operating_cash_flow': info.get('operatingCashflow'),
                'book_value': info.get('bookValue'),
                'enterprise_value': info.get('enterpriseValue'),
            })
        except Exception as e:
            logger.debug(f"yfinance fundamental failed for {symbol}: {e}")
        
        # === 3. Obtain financial report data (balance sheet, income statement, cash flow statement) ===
        financial_statements = self._get_financial_statements(symbol)
        if financial_statements:
            result['financial_statements'] = financial_statements
        
        # === 4. Get Earnings ===
        earnings_data = self._get_earnings_data(symbol)
        if earnings_data:
            result['earnings'] = earnings_data
        
        return result if result else None
    
    def _get_financial_statements(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Obtain financial statement data (balance sheet, income statement, cash flow statement)
        
        Use yfinance to obtain, including data for recent quarters
        """
        try:
            ticker = yf.Ticker(symbol)
            statements = {}
            
            # Balance Sheet
            try:
                balance_sheet = ticker.balance_sheet
                if balance_sheet is not None and not balance_sheet.empty:
                    # Get the last 4 quarters
                    latest_quarters = balance_sheet.columns[:4] if len(balance_sheet.columns) >= 4 else balance_sheet.columns
                    statements['balance_sheet'] = {
                        'latest_date': str(latest_quarters[0]) if len(latest_quarters) > 0 else None,
                        'total_assets': float(balance_sheet.loc['Total Assets', latest_quarters[0]]) if 'Total Assets' in balance_sheet.index and len(latest_quarters) > 0 else None,
                        'total_liabilities': float(balance_sheet.loc['Total Liab', latest_quarters[0]]) if 'Total Liab' in balance_sheet.index and len(latest_quarters) > 0 else None,
                        'total_equity': float(balance_sheet.loc['Stockholders Equity', latest_quarters[0]]) if 'Stockholders Equity' in balance_sheet.index and len(latest_quarters) > 0 else None,
                        'cash': float(balance_sheet.loc['Cash', latest_quarters[0]]) if 'Cash' in balance_sheet.index and len(latest_quarters) > 0 else None,
                        'debt': float(balance_sheet.loc['Total Debt', latest_quarters[0]]) if 'Total Debt' in balance_sheet.index and len(latest_quarters) > 0 else None,
                        'current_assets': float(balance_sheet.loc['Current Assets', latest_quarters[0]]) if 'Current Assets' in balance_sheet.index and len(latest_quarters) > 0 else None,
                        'current_liabilities': float(balance_sheet.loc['Current Liabilities', latest_quarters[0]]) if 'Current Liabilities' in balance_sheet.index and len(latest_quarters) > 0 else None,
                    }
            except Exception as e:
                logger.debug(f"Balance sheet fetch failed for {symbol}: {e}")
            
            # Income Statement
            try:
                income_stmt = ticker.financials
                if income_stmt is not None and not income_stmt.empty:
                    latest_quarters = income_stmt.columns[:4] if len(income_stmt.columns) >= 4 else income_stmt.columns
                    statements['income_statement'] = {
                        'latest_date': str(latest_quarters[0]) if len(latest_quarters) > 0 else None,
                        'total_revenue': float(income_stmt.loc['Total Revenue', latest_quarters[0]]) if 'Total Revenue' in income_stmt.index and len(latest_quarters) > 0 else None,
                        'gross_profit': float(income_stmt.loc['Gross Profit', latest_quarters[0]]) if 'Gross Profit' in income_stmt.index and len(latest_quarters) > 0 else None,
                        'operating_income': float(income_stmt.loc['Operating Income', latest_quarters[0]]) if 'Operating Income' in income_stmt.index and len(latest_quarters) > 0 else None,
                        'net_income': float(income_stmt.loc['Net Income', latest_quarters[0]]) if 'Net Income' in income_stmt.index and len(latest_quarters) > 0 else None,
                        'eps': float(income_stmt.loc['Basic EPS', latest_quarters[0]]) if 'Basic EPS' in income_stmt.index and len(latest_quarters) > 0 else None,
                    }
            except Exception as e:
                logger.debug(f"Income statement fetch failed for {symbol}: {e}")
            
            # Cash Flow Statement
            try:
                cashflow = ticker.cashflow
                if cashflow is not None and not cashflow.empty:
                    latest_quarters = cashflow.columns[:4] if len(cashflow.columns) >= 4 else cashflow.columns
                    statements['cash_flow'] = {
                        'latest_date': str(latest_quarters[0]) if len(latest_quarters) > 0 else None,
                        'operating_cash_flow': float(cashflow.loc['Operating Cash Flow', latest_quarters[0]]) if 'Operating Cash Flow' in cashflow.index and len(latest_quarters) > 0 else None,
                        'investing_cash_flow': float(cashflow.loc['Capital Expenditure', latest_quarters[0]]) if 'Capital Expenditure' in cashflow.index and len(latest_quarters) > 0 else None,
                        'financing_cash_flow': float(cashflow.loc['Financing Cash Flow', latest_quarters[0]]) if 'Financing Cash Flow' in cashflow.index and len(latest_quarters) > 0 else None,
                        'free_cash_flow': float(cashflow.loc['Free Cash Flow', latest_quarters[0]]) if 'Free Cash Flow' in cashflow.index and len(latest_quarters) > 0 else None,
                    }
            except Exception as e:
                logger.debug(f"Cash flow statement fetch failed for {symbol}: {e}")
            
            return statements if statements else None
            
        except Exception as e:
            logger.debug(f"Financial statements fetch failed for {symbol}: {e}")
            return None
    
    def _get_earnings_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get earnings report data (Earnings)

        Use quarterly_income_stmt instead of deprecated Ticker.earnings / quarterly_earnings,
        Historical quarterly summaries are derived from the income statement; the earnings calendar still uses ticker.calendar (if available).
        """
        def _pick_float(stmt: pd.DataFrame, row_names: tuple, col) -> Optional[float]:
            for name in row_names:
                if name in stmt.index:
                    raw = stmt.loc[name, col]
                    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                        continue
                    try:
                        return float(raw)
                    except (TypeError, ValueError):
                        continue
            return None

        try:
            ticker = yf.Ticker(symbol)
            earnings_data: Dict[str, Any] = {}

            # Quarterly income statement (yfinance recommended path to avoid fundamentals.Ticker.earnings deprecation warning)
            try:
                q_inc = ticker.quarterly_income_stmt
                if q_inc is not None and not q_inc.empty and len(q_inc.columns) > 0:
                    cols = list(q_inc.columns)[:4]
                    latest_q = cols[0]

                    rev = _pick_float(
                        q_inc,
                        ("Total Revenue", "Revenue", "Total Revenues", "Net Sales"),
                        latest_q,
                    )
                    ni = _pick_float(
                        q_inc,
                        (
                            "Net Income",
                            "Net Income Common Stockholders",
                            "Net Income Continuous Operations",
                            "Net Income Including Noncontrolling Interests",
                        ),
                        latest_q,
                    )
                    earnings_data["quarterly"] = {
                        "latest_quarter": str(latest_q),
                        "revenue": rev,
                        "earnings": ni,
                    }

                    # EPS for recent quarters (from income statement lines, not consensus estimates)
                    earnings_data["history"] = []
                    for col in cols:
                        eps = _pick_float(q_inc, ("Diluted EPS", "Basic EPS"), col)
                        earnings_data["history"].append({
                            "date": str(col),
                            "eps_actual": eps,
                            "eps_estimate": None,
                            "surprise": None,
                        })
            except Exception as e:
                logger.debug(f"Quarterly income statement (earnings) fetch failed for {symbol}: {e}")

            # Earnings Calendar (Future Earnings Dates and Consensus Expectations)
            try:
                earnings_calendar = ticker.calendar
                if earnings_calendar is not None and not earnings_calendar.empty:
                    idx0 = earnings_calendar.index[0]
                    earnings_data["upcoming"] = {
                        "next_earnings_date": str(idx0),
                        "eps_estimate": float(earnings_calendar.loc[idx0, "Earnings Estimate"])
                        if "Earnings Estimate" in earnings_calendar.columns
                        else None,
                        "revenue_estimate": float(earnings_calendar.loc[idx0, "Revenue Estimate"])
                        if "Revenue Estimate" in earnings_calendar.columns
                        else None,
                    }
            except Exception as e:
                logger.debug(f"Earnings calendar fetch failed for {symbol}: {e}")

            return earnings_data if earnings_data else None

        except Exception as e:
            logger.debug(f"Earnings data fetch failed for {symbol}: {e}")
            return None
    
    def _get_crypto_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Cryptocurrency information (mainly fixed description)"""
        # Descriptions of common cryptocurrencies
        crypto_info = {
            'BTC': {
                'name': 'Bitcoin',
                'description': '比特币，数字黄金，市值第一的加密货币，作为价值存储和避险资产',
                'category': 'Store of Value',
            },
            'ETH': {
                'name': 'Ethereum',
                'description': '以太坊，智能合约平台，DeFi和NFT生态的基础设施',
                'category': 'Smart Contract Platform',
            },
            'BNB': {
                'name': 'Binance Coin',
                'description': '币安币，全球最大交易所的平台代币',
                'category': 'Exchange Token',
            },
            'SOL': {
                'name': 'Solana',
                'description': '高性能公链，主打高TPS和低Gas费',
                'category': 'Smart Contract Platform',
            },
            'XRP': {
                'name': 'Ripple',
                'description': '瑞波币，专注跨境支付解决方案',
                'category': 'Payment',
            },
            'DOGE': {
                'name': 'Dogecoin',
                'description': '狗狗币，Meme币代表，社区驱动',
                'category': 'Meme',
            },
        }
        
        # Extract base token name
        base = symbol.split('/')[0] if '/' in symbol else symbol
        base = base.upper()
        
        if base in crypto_info:
            return crypto_info[base]
        
        return {
            'name': base,
            'description': f'{base} 是一种加密货币',
            'category': 'Unknown',
        }
    
    def _get_company(self, market: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get company information"""
        try:
            if market == 'USStock' and self._finnhub_client:
                profile = self._finnhub_client.company_profile2(symbol=symbol)
                if profile:
                    return {
                        'name': profile.get('name'),
                        'industry': profile.get('finnhubIndustry'),
                        'country': profile.get('country'),
                        'exchange': profile.get('exchange'),
                        'ipo_date': profile.get('ipo'),
                        'market_cap': profile.get('marketCapitalization'),
                        'website': profile.get('weburl'),
                    }
            
        except Exception as e:
            logger.debug(f"Company info fetch failed for {market}:{symbol}: {e}")
        
        return None
    
    # ==================== Macro data (reusing the global financial sector) ====================
    
    def _get_macro_data(self, market: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Get macroeconomic data - reuse global_market.py functions and cache
        
        Advantages:
        1. The data is consistent with the global financial page
        2. Reuse 30 seconds/5 minutes cache to reduce API calls
        3. Have complete data interpretation and level judgment
        """
        try:
            # Reuse market sentiment data from global_market.py (with 5-minute cache)
            from app.routes.global_market import (
                _fetch_vix, _fetch_dollar_index, _fetch_yield_curve,
                _fetch_fear_greed_index,
                _get_cached, _set_cached
            )
            
            result = {}
            
            # 1) Try to get it from cache (global_market cache, valid for 6 hours)
            MACRO_CACHE_TTL = 21600  # 6 hours
            cached_sentiment = _get_cached("market_sentiment", MACRO_CACHE_TTL)
            if cached_sentiment:
                logger.info("Using cached sentiment data from global_market (6h cache)")
                # Convert format
                if cached_sentiment.get('vix'):
                    vix = cached_sentiment['vix']
                    result['VIX'] = {
                        'name': 'VIX恐慌指数',
                        'description': vix.get('interpretation', ''),
                        'price': vix.get('value', 0),
                        'change': vix.get('change', 0),
                        'changePercent': vix.get('change', 0),
                        'level': vix.get('level', 'unknown'),
                    }
                
                if cached_sentiment.get('dxy'):
                    dxy = cached_sentiment['dxy']
                    result['DXY'] = {
                        'name': '美元指数',
                        'description': dxy.get('interpretation', ''),
                        'price': dxy.get('value', 0),
                        'change': dxy.get('change', 0),
                        'changePercent': dxy.get('change', 0),
                        'level': dxy.get('level', 'unknown'),
                    }
                
                if cached_sentiment.get('yield_curve'):
                    yc = cached_sentiment['yield_curve']
                    result['TNX'] = {
                        'name': '美债10年收益率',
                        'description': yc.get('interpretation', ''),
                        'price': yc.get('yield_10y', 0),
                        'change': yc.get('change', 0),
                        'changePercent': 0,
                        'spread': yc.get('spread', 0),
                        'level': yc.get('level', 'unknown'),
                    }
                
                if cached_sentiment.get('fear_greed'):
                    fg = cached_sentiment['fear_greed']
                    result['FEAR_GREED'] = {
                        'name': '恐惧贪婪指数',
                        'description': fg.get('classification', 'Neutral'),
                        'price': fg.get('value', 50),
                        'change': 0,
                        'changePercent': 0,
                    }
                
                if result:
                    return result
            
            # 2) If there is no cache, quickly obtain key indicators in parallel
            logger.info("Fetching macro data from global_market functions")
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(_fetch_vix): "VIX",
                    executor.submit(_fetch_dollar_index): "DXY",
                    executor.submit(_fetch_yield_curve): "TNX",
                    executor.submit(_fetch_fear_greed_index): "FEAR_GREED",
                }
                
                try:
                    for future in as_completed(futures, timeout=timeout):
                        key = futures[future]
                        try:
                            data = future.result(timeout=5)
                            if data:
                                # Convert to unified format
                                if key == 'VIX':
                                    result[key] = {
                                        'name': 'VIX恐慌指数',
                                        'description': data.get('interpretation', ''),
                                        'price': data.get('value', 0),
                                        'change': data.get('change', 0),
                                        'changePercent': data.get('change', 0),
                                        'level': data.get('level', 'unknown'),
                                    }
                                elif key == 'DXY':
                                    result[key] = {
                                        'name': '美元指数',
                                        'description': data.get('interpretation', ''),
                                        'price': data.get('value', 0),
                                        'change': data.get('change', 0),
                                        'changePercent': data.get('change', 0),
                                        'level': data.get('level', 'unknown'),
                                    }
                                elif key == 'TNX':
                                    result[key] = {
                                        'name': '美债10年收益率',
                                        'description': data.get('interpretation', ''),
                                        'price': data.get('yield_10y', 0),
                                        'change': data.get('change', 0),
                                        'changePercent': 0,
                                        'spread': data.get('spread', 0),
                                        'level': data.get('level', 'unknown'),
                                    }
                                elif key == 'FEAR_GREED':
                                    result[key] = {
                                        'name': '恐惧贪婪指数',
                                        'description': data.get('classification', 'Neutral'),
                                        'price': data.get('value', 50),
                                        'change': 0,
                                        'changePercent': 0,
                                    }
                        except Exception as e:
                            logger.debug(f"Macro indicator {key} fetch failed: {e}")
                except TimeoutError:
                    logger.warning("Macro data fetch timed out")
            
            # Note: Gold and other commodity data are no longer available as macro indicators
            # Reasons: 1) If the analysis is gold, the price has been obtained in _get_price
            #       2) Reduce API calls and improve stability
            pass
            
            return result
            
        except ImportError as e:
            logger.warning(f"Could not import from global_market: {e}")
            return {}
        except Exception as e:
            logger.error(f"_get_macro_data failed: {e}")
            return {}
    
    # ==================== News/Sentiment Data ====================
    
    def _get_news(
        self, market: str, symbol: str, company_name: str = None, timeout: int = 8
    ) -> Dict[str, Any]:
        """
        Get news and sentiment data
        
        Strategies (by priority):
        1. Structured API (Finnhub) - the first choice for US stocks
        2. Search Engine (Tavily/Google/Bing/SerpAPI) - Supplementary Search
        3. Sentiment Analysis - Finnhub Social Media Sentiment
        """
        news_list = []
        sentiment = {}
        
        # === 1) Finnhub News (Preferred for US stocks) ===
        if self._finnhub_client:
            try:
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                
                raw_news = []
                
                if market == 'USStock':
                    raw_news = self._finnhub_client.company_news(symbol, _from=start_date, to=end_date)
                elif market == 'Crypto':
                    # General Cryptocurrency News
                    raw_news = self._finnhub_client.general_news('crypto', min_id=0)
                else:
                    # Other general market news
                    raw_news = self._finnhub_client.general_news('general', min_id=0)
                
                if raw_news:
                    for item in raw_news[:10]:
                        if not item.get('headline'):
                            continue
                        news_list.append({
                            "datetime": datetime.fromtimestamp(item.get('datetime', 0)).strftime('%Y-%m-%d %H:%M'),
                            "headline": item.get('headline', ''),
                            "summary": item.get('summary', '')[:300] if item.get('summary') else '',
                            "source": item.get('source', 'Finnhub'),
                            "url": item.get('url', ''),
                            "sentiment": item.get('sentiment', 'neutral'),
                        })
                    logger.info(f"Finnhub 新闻获取成功: {len(news_list)} 条")
            except Exception as e:
                logger.debug(f"Finnhub news fetch failed: {e}")
        
        # === 2) Finnhub Sentiment Score (U.S. stock social media sentiment) ===
        if self._finnhub_client and market == 'USStock':
            try:
                social = self._finnhub_client.stock_social_sentiment(symbol)
                if social:
                    sentiment['reddit'] = social.get('reddit', {})
                    sentiment['twitter'] = social.get('twitter', {})
            except Exception as e:
                logger.debug(f"Finnhub sentiment fetch failed: {e}")
        
        # === 3) Search engine supplement (if there is too little news) ===
        if len(news_list) < 5:
            search_news = self._get_news_from_search(market, symbol, company_name)
            news_list.extend(search_news)
        
        # === 4) Get news on major global events (geopolitics, wars, etc.) ===
        # These events affect all markets, especially cryptocurrencies
        global_events = self._get_global_major_events()
        if global_events:
            news_list.extend(global_events)
            logger.info(f"Added {len(global_events)} global major events to news list")
        
        # Remove duplicates (by title)
        seen_titles = set()
        unique_news = []
        for item in news_list:
            title = item.get('headline', '')
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(item)
        
        # Sort by time
        unique_news.sort(key=lambda x: x.get('datetime', ''), reverse=True)
        
        return {
            "news": unique_news[:15],  # Maximum 15 articles
            "sentiment": sentiment,
        }
    
    def _get_news_from_search(
        self, market: str, symbol: str, company_name: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get news from search engines
        
        Use enhanced search services (Tavily/Google/Bing/SerpAPI)
        """
        news_list = []
        
        try:
            from app.services.search import get_search_service
            search_service = get_search_service()
            
            if not search_service.is_available:
                return news_list
            
            # Build search name
            search_name = company_name or symbol
            
            # Search stock news
            response = search_service.search_stock_news(
                stock_code=symbol,
                stock_name=search_name,
                market=market,
                max_results=5
            )
            
            if response.success and response.results:
                for result in response.results:
                    news_list.append({
                        "datetime": result.published_date or datetime.now().strftime('%Y-%m-%d'),
                        "headline": result.title,
                        "summary": result.snippet[:200] if result.snippet else '',
                        "source": f"搜索:{result.source}",
                        "url": result.url,
                        "sentiment": result.sentiment,
                    })
                logger.info(f"搜索引擎新闻补充: {len(news_list)} 条 (来源: {response.provider})")
        except Exception as e:
            logger.debug(f"搜索引擎新闻获取失败: {e}")
        
        return news_list
    
    def _get_global_major_events(self) -> List[Dict]:
        """
        Get news on major global events (geopolitics, wars, major policies, etc.)
        These events affect all markets, especially cryptocurrencies
        
        Returns:
            News list of major global events
        """
        news_list = []
        
        try:
            from app.services.search import get_search_service
            search_service = get_search_service()
            
            if not search_service.is_available:
                return news_list
            
            # Search for major global events (last 24 hours)
            # Optimize: Reduce the number of searches and search only the most important queries
            global_event_queries = [
                "war conflict breaking news today"  # Search only the most important queries and reduce API calls
            ]
            
            for query in global_event_queries:
                try:
                    response = search_service.search_with_fallback(
                        query=query,
                        max_results=2,
                        days=1  # Search only the news of the last 1 day
                    )
                    
                    if response.success and response.results:
                        for result in response.results:
                            # Check if it is a major event (including keywords)
                            title_lower = result.title.lower()
                            snippet_lower = (result.snippet or "").lower()
                            text = f"{title_lower} {snippet_lower}"
                            
                            # Major event keywords
                            major_event_keywords = [
                                "war", "conflict", "military", "attack", "strike", "sanctions",
                                "geopolitical", "crisis", "tension", "iran", "israel", "russia",
                                "ukraine", "middle east", "nato", "united states",
                                "战争", "冲突", "军事", "袭击", "制裁", "地缘政治", "危机"
                            ]
                            
                            if any(keyword in text for keyword in major_event_keywords):
                                news_list.append({
                                    "datetime": result.published_date or datetime.now().strftime('%Y-%m-%d %H:%M'),
                                    "headline": result.title,
                                    "summary": result.snippet[:300] if result.snippet else '',
                                    "source": f"全球事件:{result.source}",
                                    "url": result.url,
                                    "sentiment": "negative" if any(kw in text for kw in ["war", "conflict", "attack", "战争", "冲突", "袭击"]) else "neutral",
                                    "is_global_event": True  # Flag as global event
                                })
                                logger.info(f"Found global major event: {result.title[:60]}")
                except Exception as e:
                    logger.debug(f"Failed to search global events with query '{query}': {e}")
                    continue
            
            # Remove duplicates
            seen_titles = set()
            unique_events = []
            for item in news_list:
                title = item.get('headline', '')
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    unique_events.append(item)
            
            return unique_events[:5]  # Returns up to 5 major global events
            
        except Exception as e:
            logger.debug(f"Failed to get global major events: {e}")
            return []
    
    def _get_polymarket_events(self, symbol: str, market: str) -> List[Dict]:
        """
        Get prediction market events related to an asset
        Directly call Polymarket API to obtain real-time data without relying on local database
        
        Args:
            symbol: asset symbol
            market: market type
            
        Returns:
            List of related prediction market events
        """
        try:
            from app.data_sources.polymarket import PolymarketDataSource
            
            polymarket_source = PolymarketDataSource()
            
            # Extract keywords
            keywords = self._extract_polymarket_keywords(symbol, market)
            logger.info(f"Extracted Polymarket keywords for {symbol}: {keywords}")
            
            # Optimization: Use cache acceleration to reduce API call time
            # For AI analysis, use short-term cache (5 minutes) to ensure timeliness and improve performance.
            # Further optimization: limit the number of keywords and search only the most important keywords (up to 2)
            related_markets = []
            max_keywords = 2  # Only search for 2 keywords at most, reducing API calls
            for keyword in keywords[:max_keywords]:
                try:
                    # Use use_cache=True to enable caching and reduce API call time
                    markets = polymarket_source.search_markets(keyword, limit=5, use_cache=True)
                    logger.info(f"Found {len(markets)} markets for keyword '{keyword}' (cached)")
                    related_markets.extend(markets)
                except Exception as e:
                    logger.warning(f"Failed to search Polymarket for keyword '{keyword}': {e}")
                    continue
            
            # Remove duplicates
            seen = set()
            result = []
            for market_data in related_markets:
                market_id = market_data.get('market_id')
                if market_id and market_id not in seen:
                    seen.add(market_id)
                    # Build the correct Polymarket URL
                    # Prioritize using the existing polymarket_url, if not, build it based on slug or market_id
                    polymarket_url = market_data.get('polymarket_url')
                    if not polymarket_url:
                        slug = market_data.get('slug')
                        if slug and not str(slug).isdigit() and ('-' in str(slug) or any(c.isalpha() for c in str(slug))):
                            # Use a valid slug
                            polymarket_url = f"https://polymarket.com/event/{slug}"
                        else:
                            # Use markets endpoint (more reliable)
                            polymarket_url = f"https://polymarket.com/markets/{market_id}"
                    
                    result.append({
                        "market_id": market_id,
                        "question": market_data.get('question', ''),
                        "current_probability": market_data.get('current_probability', 50.0),
                        "volume_24h": market_data.get('volume_24h', 0),
                        "liquidity": market_data.get('liquidity', 0),
                        "category": market_data.get('category', 'other'),
                        "polymarket_url": polymarket_url
                    })
            
            logger.info(f"Total {len(result)} unique Polymarket events found for {symbol}")
            return result
        except Exception as e:
            logger.debug(f"Failed to get polymarket events for {symbol}: {e}")
            return []
    
    def _extract_polymarket_keywords(self, symbol: str, market: str) -> List[str]:
        """
        Extract keywords used to search prediction markets
        Optimization: Only retain the most important keywords and reduce the number of API calls
        """
        keywords = []
        
        # Basic symbols (most important)
        if '/' in symbol:
            base = symbol.split('/')[0]
            keywords.append(base)
        else:
            keywords.append(symbol)
        
        # Cryptocurrency full name mapping (retain only the most important full name to avoid duplication)
        crypto_names = {
            'BTC': 'Bitcoin',
            'ETH': 'Ethereum',
            'SOL': 'Solana',
            'BNB': 'Binance',
            'XRP': 'Ripple',
            'ADA': 'Cardano',
            'DOGE': 'Dogecoin',
            'AVAX': 'Avalanche',
            'DOT': 'Polkadot',
            'MATIC': 'Polygon'
        }
        
        base_symbol = symbol.split('/')[0] if '/' in symbol else symbol
        if base_symbol in crypto_names:
            # Add only one full name to avoid duplication of upper and lower case
            keywords.append(crypto_names[base_symbol])
        
        # Optimization: Remove generic keywords (such as '$100k', 'ETF', 'approval'), which will match many irrelevant markets
        # Only keep keywords directly related to assets, up to 2-3
        
        # Remove duplicates and limit the number (maximum 3 keywords)
        unique_keywords = []
        seen = set()
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique_keywords.append(kw)
                if len(unique_keywords) >= 3:  # Up to 3 keywords
                    break
        
        logger.info(f"Extracted {len(unique_keywords)} Polymarket keywords (optimized from {len(keywords)}): {unique_keywords}")
        return unique_keywords


# global instance
_collector: Optional[MarketDataCollector] = None

def get_market_data_collector() -> MarketDataCollector:
    """Get market data collector singleton"""
    global _collector
    if _collector is None:
        _collector = MarketDataCollector()
    return _collector
