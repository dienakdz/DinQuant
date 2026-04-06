"""
data source module
Support K-line data acquisition for multiple markets

Improved version (refer to daily_stock_analysis project):
- Fuse protection (circuit_breaker)
- Data cache (cache_manager)
- Anti-ban strategy (rate_limiter)
"""
from app.data_sources.factory import DataSourceFactory
from app.data_sources.circuit_breaker import (
    CircuitBreaker,
    get_realtime_circuit_breaker
)
from app.data_sources.cache_manager import (
    DataCache,
    get_realtime_cache,
    get_kline_cache,
    get_stock_info_cache
)
from app.data_sources.rate_limiter import (
    RateLimiter,
    get_random_user_agent,
    random_sleep,
    retry_with_backoff
)

__all__ = [
    # factory
    'DataSourceFactory',
    # fuse
    'CircuitBreaker',
    'get_realtime_circuit_breaker',
    # cache
    'DataCache',
    'get_realtime_cache',
    'get_kline_cache',
    'get_stock_info_cache',
    # current limiter
    'RateLimiter',
    'get_random_user_agent',
    'random_sleep',
    'retry_with_backoff',
]
