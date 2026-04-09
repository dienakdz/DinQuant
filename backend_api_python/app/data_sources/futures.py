"""
Futures data source
support:
1. Cryptocurrency Futures (Binance Futures via CCXT)
2. Traditional futures (Yahoo Finance)
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import ccxt
import yfinance as yf

from app.config import CCXTConfig
from app.data_sources.base import TIMEFRAME_SECONDS, BaseDataSource
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FuturesDataSource(BaseDataSource):
    """Futures data source"""

    name = "Futures"

    # Yahoo Finance time period mapping
    YF_TIMEFRAME_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1H": "1h",
        "4H": "4h",
        "1D": "1d",
        "1W": "1wk",
    }

    # CCXT time period mapping
    CCXT_TIMEFRAME_MAP = CCXTConfig.TIMEFRAME_MAP

    # Traditional futures contract code (Yahoo Finance)
    YF_SYMBOLS = {
        "GC": "GC=F",  # gold futures
        "SI": "SI=F",  # Silver futures
        "CL": "CL=F",  # Crude oil futures
        "NG": "NG=F",  # Natural gas futures
        "ZC": "ZC=F",  # Corn futures
        "ZW": "ZW=F",  # Wheat futures
    }

    def __init__(self):
        # Initialize CCXT (for cryptocurrency futures)
        config = {
            "timeout": CCXTConfig.TIMEOUT,
            "enableRateLimit": CCXTConfig.ENABLE_RATE_LIMIT,
            "options": {"defaultType": "future"},
        }

        if CCXTConfig.PROXY:
            config["proxies"] = {"http": CCXTConfig.PROXY, "https": CCXTConfig.PROXY}

        self.exchange = ccxt.binance(config)

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get latest ticker for futures symbol.

        - For crypto futures, uses CCXT Binance futures client.
        - For traditional futures (Yahoo Finance symbols), returns a minimal ticker shape with `last`.
        """
        sym = (symbol or "").strip()
        if sym in self.YF_SYMBOLS or sym.endswith("=F"):
            try:
                yf_symbol = self.YF_SYMBOLS.get(sym, sym)
                if not yf_symbol.endswith("=F"):
                    yf_symbol = yf_symbol + "=F"
                t = yf.Ticker(yf_symbol)
                # Prefer fast_info if available, fall back to last close
                last = None
                try:
                    last = getattr(t, "fast_info", {}).get("last_price")
                except Exception:
                    last = None
                if last is None:
                    hist = t.history(period="2d", interval="1d")
                    if hist is not None and not hist.empty:
                        last = float(hist["Close"].iloc[-1])
                return {"symbol": yf_symbol, "last": float(last or 0.0)}
            except Exception:
                return {"symbol": sym, "last": 0.0}

        if ":" in sym:
            sym = sym.split(":", 1)[0]
        sym = sym.upper()
        if "/" not in sym:
            if sym.endswith("USDT") and len(sym) > 4:
                sym = f"{sym[:-4]}/USDT"
            elif sym.endswith("USD") and len(sym) > 3:
                sym = f"{sym[:-3]}/USD"
        return self.exchange.fetch_ticker(sym)

    def _get_timeframe_seconds(self, timeframe: str) -> int:
        """Get the number of seconds corresponding to the time period"""
        return TIMEFRAME_SECONDS.get(timeframe, 86400)

    def get_kline(
        self, symbol: str, timeframe: str, limit: int, before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get futures K-line data

        Args:
            symbol: futures contract code
            timeframe: time period
            limit: number of data items
            before_time: end timestamp
        """
        # Determine whether it is traditional futures or cryptocurrency futures
        if symbol in self.YF_SYMBOLS or symbol.endswith("=F"):
            return self._get_traditional_futures(symbol, timeframe, limit, before_time)
        else:
            return self._get_crypto_futures(symbol, timeframe, limit, before_time)

    def _get_traditional_futures(
        self, symbol: str, timeframe: str, limit: int, before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Use yfinance to obtain traditional futures data"""
        try:
            # Convert symbol format
            yf_symbol = self.YF_SYMBOLS.get(symbol, symbol)
            if not yf_symbol.endswith("=F"):
                yf_symbol = symbol + "=F"

            # conversion time period
            yf_interval = self.YF_TIMEFRAME_MAP.get(timeframe, "1d")

            # logger.info(f"Get traditional futures K-line: {yf_symbol}, period: {yf_interval}, number of bars: {limit}")

            # Calculation time range
            if before_time:
                end_time = datetime.fromtimestamp(before_time)
            else:
                end_time = datetime.now()

            tf_seconds = self._get_timeframe_seconds(timeframe)
            start_time = end_time - timedelta(seconds=tf_seconds * limit * 1.5)

            # The end parameter of yfinance is not included (exclusive), and one day needs to be added.
            end_time_inclusive = end_time + timedelta(days=1)

            # Get data
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(start=start_time, end=end_time_inclusive, interval=yf_interval)

            if df.empty:
                logger.warning(f"No data: {yf_symbol}")
                return []

            # Convert format
            klines = []
            for index, row in df.iterrows():
                klines.append(
                    {
                        "time": int(index.timestamp()),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row["Volume"]),
                    }
                )

            klines.sort(key=lambda x: x["time"])
            if len(klines) > limit:
                klines = klines[-limit:]

            # logger.info(f"obtained {len(klines)} pieces of traditional futures data")
            return klines

        except Exception as e:
            logger.error(f"Failed to fetch traditional futures data: {e}")
            return []

    def _get_crypto_futures(
        self, symbol: str, timeframe: str, limit: int, before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Obtain cryptocurrency futures data using CCXT"""
        try:
            # Make sure the symbol format is correct
            ccxt_symbol = symbol if "/" in symbol else f"{symbol}/USDT"
            ccxt_timeframe = self.CCXT_TIMEFRAME_MAP.get(timeframe, "1d")

            # logger.info(f"Get cryptocurrency futures K-line: {ccxt_symbol}, period: {ccxt_timeframe}, number of bars: {limit}")

            # Get data
            if before_time:
                since_time = before_time - limit * self._get_timeframe_seconds(timeframe)
                ohlcv = self.exchange.fetch_ohlcv(ccxt_symbol, ccxt_timeframe, since=since_time * 1000, limit=limit)
            else:
                ohlcv = self.exchange.fetch_ohlcv(ccxt_symbol, ccxt_timeframe, limit=limit)

            # Convert format
            klines = []
            for candle in ohlcv:
                klines.append(
                    {
                        "time": int(candle[0] / 1000),
                        "open": float(candle[1]),
                        "high": float(candle[2]),
                        "low": float(candle[3]),
                        "close": float(candle[4]),
                        "volume": float(candle[5]),
                    }
                )

            # logger.info(f"obtained {len(klines)} pieces of cryptocurrency futures data")
            return klines

        except Exception as e:
            logger.error(f"Failed to fetch crypto futures data: {e}")
            return []
