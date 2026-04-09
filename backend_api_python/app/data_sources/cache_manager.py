# -*- coding: utf-8 -*-
"""
===================================
Data cache management module
===================================

Refer to daily_stock_analysis project implementation
Used to cache realtime market and K-line data to reduce repeated requests

characteristic:
1. TTL (Time To Live) expiration mechanism
2. LRU (Least Recently Used) elimination strategy
3. Partition management by data type
"""

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """cache entry"""

    data: Any
    timestamp: float
    ttl: float
    hit_count: int = 0

    def is_expired(self) -> bool:
        """Check if expired"""
        return time.time() - self.timestamp > self.ttl

    def age(self) -> float:
        """Return cache age (seconds)"""
        return time.time() - self.timestamp


class DataCache:
    """
    Data Cache Manager

    characteristic:
    - TTL expiration mechanism
    - Maximum capacity limit
    - LRU elimination strategy
    - Thread safety
    """

    def __init__(
        self,
        name: str = "default",
        default_ttl: float = 600.0,  # Default 10 minutes
        max_size: int = 1000,  # Maximum number of cache entries
    ):
        self.name = name
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Statistics
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached data

        Returns:
            Cached data, returns None if it does not exist or has expired.
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check if expired
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                logger.debug(f"[cache] {self.name}:{key} expired and was removed")
                return None

            # Update access order (LRU)
            self._cache.move_to_end(key)
            entry.hit_count += 1
            self._hits += 1

            logger.debug(f"[cache hit] {self.name}:{key} (age: {entry.age():.0f}s/{entry.ttl:.0f}s)")
            return entry.data

    def set(self, key: str, data: Any, ttl: Optional[float] = None) -> None:
        """
        Set cache data

        Args:
            key: cache key
            data: cache data
            ttl: expiration time (seconds), None uses the default value
        """
        with self._lock:
            # Check capacity, perform LRU elimination
            while len(self._cache) >= self.max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                logger.debug(f"[cache] {self.name} reached capacity, evicted: {oldest_key}")

            actual_ttl = ttl if ttl is not None else self.default_ttl
            self._cache[key] = CacheEntry(data=data, timestamp=time.time(), ttl=actual_ttl)

            logger.debug(f"[cache update] {self.name}:{key} TTL={actual_ttl}s")

    def delete(self, key: str) -> bool:
        """Delete cache entry"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"[cache] {self.name}:{key} deleted")
                return True
            return False

    def clear(self) -> int:
        """Clear cache"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"[cache] {self.name} cleared {count} records")
            return count

    def cleanup_expired(self) -> int:
        """Clean up expired entries"""
        with self._lock:
            expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]
            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.debug(f"[cache] {self.name} cleaned {len(expired_keys)} expired records")
            return len(expired_keys)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            return {
                "name": self.name,
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.1%}",
                "default_ttl": self.default_ttl,
            }


# ============================================
# Global cache instance
# ============================================

# Real-time quotation caching (20 minutes TTL)
_realtime_cache = DataCache(
    name="realtime",
    default_ttl=1200.0,  # 20 minutes
    max_size=6000,
)

# K-line data caching (5 minutes TTL, caching on demand)
_kline_cache = DataCache(
    name="kline",
    default_ttl=300.0,  # 5 minutes
    max_size=500,  # Up to 500 trading pairs
)

# Stock basic information cache (1 day TTL)
_stock_info_cache = DataCache(
    name="stock_info",
    default_ttl=86400.0,  # 24 hours
    max_size=6000,
)


def get_realtime_cache() -> DataCache:
    """Get real-time quotation cache"""
    return _realtime_cache


def get_kline_cache() -> DataCache:
    """Get K-line data cache"""
    return _kline_cache


def get_stock_info_cache() -> DataCache:
    """Get stock information cache"""
    return _stock_info_cache


def generate_kline_cache_key(symbol: str, timeframe: str, limit: int, before_time: Optional[int] = None) -> str:
    """
    Generate K-line cache key

    Format: symbol:timeframe:limit[:before_time]
    """
    key = f"{symbol}:{timeframe}:{limit}"
    if before_time:
        key += f":{before_time}"
    return key
