"""
US stock data source
Get data using yfinance and finnhub
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import yfinance as yf

from app.config import APIKeys
from app.data_sources.base import BaseDataSource
from app.utils.logger import get_logger

logger = get_logger(__name__)


class USStockDataSource(BaseDataSource):
    """US stock data source"""

    name = "USStock/yfinance"

    # yfinance time period mapping
    INTERVAL_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1H": "1h", "4H": "4h", "1D": "1d", "1W": "1wk"}

    # The range of days to obtain data in different periods
    DAYS_MAP = {
        "1m": lambda limit: min(7, max(1, (limit // 390) + 2)),
        "5m": lambda limit: min(60, max(1, (limit // 78) + 2)),
        "15m": lambda limit: min(60, max(1, (limit // 26) + 2)),
        "30m": lambda limit: min(60, max(1, (limit // 13) + 2)),
        "1H": lambda limit: min(730, max(1, (limit // 24) + 2)),
        "4H": lambda limit: min(730, max(1, (limit // 6) + 2)),
        "1D": lambda limit: min(3650, limit + 1),
        "1W": lambda limit: min(3650, (limit * 7) + 7),
    }

    def __init__(self):
        # Initialize finnhub as an alternative
        self.finnhub_client = None
        try:
            import finnhub

            if APIKeys.is_configured("FINNHUB_API_KEY"):
                self.finnhub_client = finnhub.Client(api_key=APIKeys.FINNHUB_API_KEY)
                logger.info("Finnhub client initialized")
        except Exception as e:
            logger.warning(f"Finnhub init failed: {e}")

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get realtime quotes for U.S. stocks

        Use Finnhub first (more real-time), downgrade to yfinance fast_info

        Returns:
            dict: {
                'last': current price,
                'change': change amount,
                'changePercent': increase or decrease,
                'high': highest price,
                'low': lowest price,
                'open': opening price,
                'previousClose': yesterday's closing price
            }
        """
        symbol = (symbol or "").strip().upper()

        # Prefer using Finnhub (live data)
        if self.finnhub_client:
            try:
                quote = self.finnhub_client.quote(symbol)
                if quote and quote.get("c"):
                    return {
                        "last": quote.get("c", 0),  # current price
                        "change": quote.get("d", 0),  # Changes
                        "changePercent": quote.get("dp", 0),  # Increase or decrease
                        "high": quote.get("h", 0),  # Best in Japan
                        "low": quote.get("l", 0),  # Lowest within the day
                        "open": quote.get("o", 0),  # opening price
                        "previousClose": quote.get("pc", 0),  # Yesterday's closing price
                    }
            except Exception as e:
                msg = str(e).lower()
                if "403" in str(e) or "don't have access" in msg or "no access" in msg:
                    logger.debug(f"Finnhub quote skipped (no access): {symbol}: {e}")
                else:
                    logger.warning(f"Finnhub quote failed for {symbol}: {e}")

        # Downgrade to use yfinance
        try:
            ticker = yf.Ticker(symbol)

            # Try fast_info (faster)
            try:
                fast_info = ticker.fast_info
                last_price = fast_info.get("lastPrice") or fast_info.get("last_price")
                prev_close = (
                    fast_info.get("previousClose")
                    or fast_info.get("previous_close")
                    or fast_info.get("regularMarketPreviousClose")
                )

                if last_price:
                    change = (last_price - prev_close) if prev_close else 0
                    change_pct = (change / prev_close * 100) if prev_close else 0
                    return {
                        "last": float(last_price),
                        "change": round(change, 4),
                        "changePercent": round(change_pct, 2),
                        "high": float(fast_info.get("dayHigh") or fast_info.get("day_high") or last_price),
                        "low": float(fast_info.get("dayLow") or fast_info.get("day_low") or last_price),
                        "open": float(fast_info.get("open") or fast_info.get("regularMarketOpen") or last_price),
                        "previousClose": float(prev_close) if prev_close else 0,
                    }
            except Exception as e:
                logger.debug(f"yfinance fast_info failed for {symbol}: {e}")

            # Downgrade to use info (slower but more complete data)
            try:
                info = ticker.info
                last_price = info.get("regularMarketPrice") or info.get("currentPrice")
                prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")

                if last_price:
                    change = (last_price - prev_close) if prev_close else 0
                    change_pct = (change / prev_close * 100) if prev_close else 0
                    return {
                        "last": float(last_price),
                        "change": round(change, 4),
                        "changePercent": round(change_pct, 2),
                        "high": float(info.get("regularMarketDayHigh") or info.get("dayHigh") or last_price),
                        "low": float(info.get("regularMarketDayLow") or info.get("dayLow") or last_price),
                        "open": float(info.get("regularMarketOpen") or info.get("open") or last_price),
                        "previousClose": float(prev_close) if prev_close else 0,
                    }
            except Exception as e:
                logger.debug(f"yfinance info failed for {symbol}: {e}")

            # Last downgrade: use the most recent 1-minute K-line
            try:
                hist = ticker.history(period="1d", interval="1m")
                if hist is not None and not hist.empty:
                    last_row = hist.iloc[-1]
                    first_row = hist.iloc[0]
                    last_price = float(last_row["Close"])
                    open_price = float(first_row["Open"])

                    return {
                        "last": last_price,
                        "change": round(last_price - open_price, 4),
                        "changePercent": round((last_price - open_price) / open_price * 100, 2) if open_price else 0,
                        "high": float(hist["High"].max()),
                        "low": float(hist["Low"].min()),
                        "open": open_price,
                        "previousClose": open_price,  # approximate
                    }
            except Exception as e:
                logger.debug(f"yfinance history fallback failed for {symbol}: {e}")

        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol}: {e}")

        return {"last": 0, "symbol": symbol}

    def get_kline(
        self, symbol: str, timeframe: str, limit: int, before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get U.S. stock K-line data"""
        klines = []

        try:
            interval = self.INTERVAL_MAP.get(timeframe, "1d")
            days_func = self.DAYS_MAP.get(timeframe, lambda x: x + 1)
            days = days_func(limit)

            # Calculate date range
            if before_time:
                end_date = datetime.fromtimestamp(before_time)
                start_date = end_date - timedelta(days=days)
            else:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)

            # logger.info(f"Use yfinance to get {symbol}, period: {interval}, date: {start_date.date()} ~ {end_date.date()}")

            # Try yfinance
            df = self._fetch_yfinance(symbol, interval, start_date, end_date)

            if df is None or df.empty:
                # try finnhub
                if self.finnhub_client and timeframe == "1D":
                    klines = self._fetch_finnhub(symbol, start_date, end_date, limit)
                    if klines:
                        return klines
            else:
                klines = self._convert_dataframe(df, limit)

            # Filter and restrict
            klines = self.filter_and_limit(klines, limit, before_time)

            # Record results
            self.log_result(symbol, klines, timeframe)

        except Exception as e:
            logger.error(f"Failed to fetch US stock K-lines {symbol}: {str(e)}")
            import traceback

            logger.error(traceback.format_exc())

        return klines

    def _fetch_yfinance(self, symbol: str, interval: str, start_date: datetime, end_date: datetime):
        """Use yfinance to get data"""
        try:
            ticker = yf.Ticker(symbol)

            # The end parameter of yfinance is not included (exclusive), so you need to add one day to include the end_date data of the current day.
            # For example: end="2026-01-12" actually only returns the data of 2026-01-11
            end_date_inclusive = end_date + timedelta(days=1)

            df = ticker.history(
                start=start_date.strftime("%Y-%m-%d"), end=end_date_inclusive.strftime("%Y-%m-%d"), interval=interval
            )
            # logger.info(f"yfinance returns {len(df) if df is not None and not df.empty else 0} pieces of data")
            return df
        except Exception as e:
            logger.warning(f"yfinance fetch failed: {e}")
            return None

    def _fetch_finnhub(self, symbol: str, start_date: datetime, end_date: datetime, limit: int) -> List[Dict[str, Any]]:
        """Use finnhub to get daily data"""
        klines = []
        try:
            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())

            # logger.info(f"Use Finnhub to obtain {symbol} daily data")
            candles = self.finnhub_client.stock_candles(symbol, "D", start_ts, end_ts)

            if candles and candles.get("s") == "ok":
                for i in range(len(candles["t"])):
                    klines.append(
                        self.format_kline(
                            timestamp=candles["t"][i],
                            open_price=candles["o"][i],
                            high=candles["h"][i],
                            low=candles["l"][i],
                            close=candles["c"][i],
                            volume=candles["v"][i],
                        )
                    )
                # logger.info(f"Finnhub returns {len(klines)} pieces of data")
        except Exception as e:
            msg = str(e).lower()
            # Free tier / plan: 403 "You don't have access to this resource" is common; avoid ERROR spam.
            if "403" in str(e) or "don't have access" in msg or "no access" in msg:
                logger.debug(f"Finnhub candles skipped (no access): {symbol}: {e}")
            else:
                logger.warning(f"Finnhub fetch failed: {e}")

        return klines

    def _convert_dataframe(self, df, limit: int) -> List[Dict[str, Any]]:
        """Convert DataFrame to K-line list"""
        klines = []
        df = df.tail(limit).reset_index()

        # Determine the time column name (the daily line is Date, the minute level is Datetime)
        time_col = None
        if "Datetime" in df.columns:
            time_col = "Datetime"
        elif "Date" in df.columns:
            time_col = "Date"
        elif "index" in df.columns:
            time_col = "index"

        if time_col is None:
            logger.warning(f"Unable to determine time column; available columns: {df.columns.tolist()}")
            return klines

        for _, row in df.iterrows():
            try:
                # Processing timestamps
                time_value = row[time_col]
                if hasattr(time_value, "timestamp"):
                    ts = int(time_value.timestamp())
                else:
                    continue

                klines.append(
                    self.format_kline(
                        timestamp=ts,
                        open_price=row["Open"],
                        high=row["High"],
                        low=row["Low"],
                        close=row["Close"],
                        volume=row["Volume"],
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to parse row data: {e}")
                continue

        return klines
