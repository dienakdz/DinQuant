"""
Data source base class
Define a unified data source interface
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


# K-line cycle mapping (seconds)
TIMEFRAME_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1H": 3600, "4H": 14400, "1D": 86400, "1W": 604800}


class BaseDataSource(ABC):
    """Data source base class."""

    name: str = "base"

    @abstractmethod
    def get_kline(
        self, symbol: str, timeframe: str, limit: int, before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get K-line data

        Args:
            symbol: trading pair/stock code
            timeframe: time period (1m, 5m, 15m, 30m, 1H, 4H, 1D, 1W)
            limit: number of data items
            before_time: Get data before this time (Unix timestamp, seconds)

        Returns:
            K-line data list, format:
            [{"time": int, "open": float, "high": float, "low": float, "close": float, "volume": float}, ...]
        """
        pass

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Get latest ticker for a symbol (best-effort).

        This is an optional interface used by the strategy executor for fetching current price.
        Implementations may return a dict compatible with CCXT `fetch_ticker` shape (e.g. {'last': ...}).
        """
        raise NotImplementedError("get_ticker is not implemented for this data source")

    def format_kline(
        self, timestamp: int, open_price: float, high: float, low: float, close: float, volume: float
    ) -> Dict[str, Any]:
        """Format a single K-line record."""
        return {
            "time": timestamp,
            "open": round(float(open_price), 4),
            "high": round(float(high), 4),
            "low": round(float(low), 4),
            "close": round(float(close), 4),
            "volume": round(float(volume), 2),
        }

    def calculate_time_range(self, timeframe: str, limit: int, buffer_ratio: float = 1.2) -> int:
        """
        Calculate the time range (seconds) required to obtain the specified number of K-lines

        Args:
            timeframe: time period
            limit: number of K-lines
            buffer_ratio: buffer coefficient

        Returns:
            Time range (seconds)
        """
        seconds_per_candle = TIMEFRAME_SECONDS.get(timeframe, 86400)
        return int(seconds_per_candle * limit * buffer_ratio)

    def filter_and_limit(
        self, klines: List[Dict[str, Any]], limit: int, before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter and limit K-line data

        Args:
            klines: K-line data list
            limit: maximum quantity
            before_time: Filter data after this time

        Returns:
            Processed K-line data
        """
        # Sort by time
        klines.sort(key=lambda x: x["time"])

        # filter time
        if before_time:
            klines = [k for k in klines if k["time"] < before_time]

        # Limit quantity (take the latest)
        if len(klines) > limit:
            klines = klines[-limit:]

        return klines

    def log_result(self, symbol: str, klines: List[Dict[str, Any]], timeframe: str):
        """Record the result log.

        Delayed judgment:
        - K-line time is Unix seconds (UTC), compared with datetime.now(UTC) to avoid local time zone errors.
        - Daily/weekly line: The last line is usually the "close of the previous trading day", and it can last 3 to 4 days on weekends/holidays.
          Originally, using 2×86400s (48h) would cause false alarms in Monday morning trading; instead, the daily line tolerates up to about 5 natural days, and the weekly line is wider.
        """
        if klines:
            latest_ts = int(klines[-1]["time"])
            latest_utc = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            time_diff = (now_utc - latest_utc).total_seconds()

            tf_sec = TIMEFRAME_SECONDS.get(timeframe, 3600)
            if tf_sec < 86400:
                # Minute/hour level: If it exceeds about 2 K, an alarm will be issued if it is not updated.
                max_diff = tf_sec * 2
            elif tf_sec == 86400:
                # Daily line: covering weekends + short holidays (about 5 calendar days)
                max_diff = 5 * 86400
            else:
                # Weekly: Allows data lags across multiple weeks
                max_diff = max(tf_sec * 2, 21 * 86400)

            if time_diff > max_diff:
                logger.warning(
                    f"Warning: {symbol} data is delayed ({time_diff:.0f}s, "
                    f"latest_bar_utc={latest_utc.isoformat()}, threshold={max_diff:.0f}s, tf={timeframe})"
                )
        else:
            logger.warning(f"{self.name}: no data for {symbol}")
