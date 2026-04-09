# -*- coding: utf-8 -*-
"""
===================================
Anti-ban tool module (Rate Limiter)
===================================

Refer to daily_stock_analysis project implementation
Provide anti-crawler strategies:
1. Random sleep (Jitter)
2. Random User-Agent rotation
3. Exponential backoff retry
4. Request frequency limit
"""

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


# ============================================
# User-Agent Pond
# ============================================

USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Linux Chrome
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    """Get a random User-Agent"""
    return random.choice(USER_AGENTS)


def get_request_headers(referer: Optional[str] = None) -> dict:
    """
    Get request header with random User-Agent

    Args:
        referer: optional Referer header

    Returns:
        Request header dictionary
    """
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    if referer:
        headers["Referer"] = referer

    return headers


# ============================================
# Random sleep
# ============================================


def random_sleep(min_seconds: float = 1.0, max_seconds: float = 3.0, log: bool = False) -> None:
    """
    Random sleep (Jitter)

    Anti-ban strategy: simulate random delays in human behavior
    Incorporate irregular wait times between requests

    Args:
        min_seconds: Minimum sleep time (seconds)
        max_seconds: Maximum sleep time (seconds)
        log: whether to log
    """
    sleep_time = random.uniform(min_seconds, max_seconds)
    if log:
        logger.debug(f"Random hibernation {sleep_time:.2f} seconds...")
    time.sleep(sleep_time)


# ============================================
# Request frequency limiter
# ============================================


class RateLimiter:
    """
    Request frequency limiter

    Ensure there is a minimum amount of time between requests
    """

    def __init__(self, min_interval: float = 1.0, jitter_min: float = 0.5, jitter_max: float = 1.5):
        """
        Initialize frequency limiter

        Args:
            min_interval: Minimum request interval (seconds)
            jitter_min: minimum random jitter (seconds)
            jitter_max: maximum random jitter (seconds)
        """
        self.min_interval = min_interval
        self.jitter_min = jitter_min
        self.jitter_max = jitter_max
        self._last_request_time: Optional[float] = None

    def wait(self) -> float:
        """
        Wait until the next request can be made

        Returns:
            Actual waiting time (seconds)
        """
        wait_time = 0.0

        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.min_interval:
                # Supplement sleep to minimum interval
                wait_time = self.min_interval - elapsed
                time.sleep(wait_time)

        # Add random jitter
        jitter = random.uniform(self.jitter_min, self.jitter_max)
        time.sleep(jitter)
        wait_time += jitter

        # Record the time of this request
        self._last_request_time = time.time()

        return wait_time

    def reset(self) -> None:
        """reset limiter"""
        self._last_request_time = None


# ============================================
# Exponential backoff retry decorator
# ============================================


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
):
    """
    Exponential backoff retry decorator

    Args:
        max_attempts: Maximum number of retries
        base_delay: base delay time (seconds)
        max_delay: maximum delay time (seconds)
        exponential_base: exponential base
        exceptions: Exception types that need to be retried
        on_retry: callback function when retrying

    Usage example:
        @retry_with_backoff(max_attempts=3, exceptions=(ConnectionError, TimeoutError))
        def fetch_data():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"[Retry] {func.__name__} has reached the maximum number of retries ({max_attempts}), giving up"
                        )
                        raise

                    # Calculate the backoff delay: base_delay * (exponential_base ^ (attempt - 1))
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    # Add random jitter (±20%)
                    delay *= random.uniform(0.8, 1.2)

                    logger.warning(
                        f"[Retry] {func.__name__} failed for the {attempt}/{max_attempts} time: {e}, "
                        f"waiting {delay:.1f}s before retrying..."
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    time.sleep(delay)

            # Shouldn't have gotten here
            raise last_exception

        return wrapper

    return decorator


# ============================================
# Global current limiter example
# ============================================

# Oriental Fortune interface current limiter (more stringent)
_eastmoney_limiter = RateLimiter(min_interval=2.0, jitter_min=1.0, jitter_max=3.0)

# Tencent Finance interface current limiter (relatively loose)
_tencent_limiter = RateLimiter(min_interval=1.0, jitter_min=0.5, jitter_max=1.5)

# Akshare interface current limiter
_akshare_limiter = RateLimiter(min_interval=2.0, jitter_min=1.5, jitter_max=3.5)


def get_eastmoney_limiter() -> RateLimiter:
    """Get Oriental Wealth Current Limiter"""
    return _eastmoney_limiter


def get_tencent_limiter() -> RateLimiter:
    """Get Tencent Finance current limiter"""
    return _tencent_limiter


def get_akshare_limiter() -> RateLimiter:
    """Get Akshare Throttler"""
    return _akshare_limiter
