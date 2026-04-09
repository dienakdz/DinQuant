"""
Database and cache configuration
"""

import os


class MetaRedisConfig(type):
    """Redis configuration"""

    @property
    def HOST(cls):
        return os.getenv("REDIS_HOST", "localhost")

    @property
    def PORT(cls):
        return int(os.getenv("REDIS_PORT", 6379))

    @property
    def PASSWORD(cls):
        return os.getenv("REDIS_PASSWORD", None)

    @property
    def DB(cls):
        return int(os.getenv("REDIS_DB", 0))

    @property
    def CONNECT_TIMEOUT(cls):
        return int(os.getenv("REDIS_CONNECT_TIMEOUT", 5))

    @property
    def SOCKET_TIMEOUT(cls):
        return int(os.getenv("REDIS_SOCKET_TIMEOUT", 5))

    @property
    def MAX_CONNECTIONS(cls):
        return int(os.getenv("REDIS_MAX_CONNECTIONS", 10))


class RedisConfig(metaclass=MetaRedisConfig):
    """Redis cache configuration."""

    @classmethod
    def get_url(cls) -> str:
        """Get the Redis connection URL."""
        if cls.PASSWORD:
            return f"redis://:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.DB}"
        return f"redis://{cls.HOST}:{cls.PORT}/{cls.DB}"


class MetaCacheConfig(type):
    """Cache business configuration."""

    def ENABLED(cls):
        # Forced to be off by default unless explicitly enabled by an environment variable
        return os.getenv("CACHE_ENABLED", "False").lower() == "true"

    @property
    def DEFAULT_EXPIRE(cls):
        return int(os.getenv("CACHE_EXPIRE", 300))

    @property
    def KLINE_CACHE_TTL(cls):
        return {
            "1m": 5,  # K-line cache for 1 minute and 5 seconds
            "3m": 30,  # 3 minutes K-line cache 30 seconds
            "5m": 60,  # 5 minutes K-line cache 1 minute
            "15m": 300,  # 15 minutes K-line cache 5 minutes
            "30m": 300,  # 30 minutes K-line cache 5 minutes
            "1H": 300,  # 1 hour K-line cache for 5 minutes
            "4H": 300,  # 4 hours K-line cache for 5 minutes
            "1D": 300,  # Daily K-line cache for 5 minutes
            # Compatible with lowercase
            "1h": 300,
            "4h": 300,
            "1d": 300,
        }

    @property
    def ANALYSIS_CACHE_TTL(cls):
        return 3600

    @property
    def PRICE_CACHE_TTL(cls):
        return 10


class CacheConfig(metaclass=MetaCacheConfig):
    """Cache configuration."""

    pass
