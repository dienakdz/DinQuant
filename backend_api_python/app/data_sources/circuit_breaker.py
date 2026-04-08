# -*- coding: utf-8 -*-
"""
===================================
Circuit Breaker
===================================

Refer to daily_stock_analysis project implementation
Used to manage the fuse/cooling status of data sources to avoid repeated requests when continuous failures occur.

State machine:
CLOSED (normal) --failed N times --> OPEN (melted) --cooling time expired --> HALF_OPEN (half open)
HALF_OPEN --Success--> CLOSED
HALF_OPEN --Failure--> OPEN
"""

import time
import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """fuse status"""
    CLOSED = "closed"      # normal state
    OPEN = "open"          # Fuse status (not available)
    HALF_OPEN = "half_open"  # Half-open state (exploratory request)


class CircuitBreaker:
    """
    Circuit Breakers - Manage the blown/cooling status of data sources
    
    Strategy:
    - Enter the fuse state after N consecutive failures
    - Skip this data source during the circuit breaker period
    - Automatically returns to half-open state after cooling time
    - In the half-open state, if a single success is successful, it will be fully restored, if it fails, the fuse will continue to be broken.
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,       # Continuous failure threshold
        cooldown_seconds: float = 300.0,  # Cooling time (seconds), default 5 minutes
        half_open_max_calls: int = 1      # Maximum number of attempts in half-open state
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max_calls = half_open_max_calls
        
        # Status of each data source {source_name: {state, failures, last_failure_time, half_open_calls}}
        self._states: Dict[str, Dict[str, Any]] = {}
    
    def _get_state(self, source: str) -> Dict[str, Any]:
        """Get or initialize data source status"""
        if source not in self._states:
            self._states[source] = {
                'state': CircuitState.CLOSED,
                'failures': 0,
                'last_failure_time': 0.0,
                'half_open_calls': 0,
                'last_error': None
            }
        return self._states[source]
    
    def is_available(self, source: str) -> bool:
        """
        Check if the data source is available
        
        Return True to indicate that the request can be attempted
        Return False to indicate that the data source should be skipped
        """
        state = self._get_state(source)
        current_time = time.time()
        
        if state['state'] == CircuitState.CLOSED:
            return True
        
        if state['state'] == CircuitState.OPEN:
            # Check cool down time
            time_since_failure = current_time - state['last_failure_time']
            if time_since_failure >= self.cooldown_seconds:
                # Cooling is completed and enters the half-open state
                state['state'] = CircuitState.HALF_OPEN
                state['half_open_calls'] = 0
                logger.info(f"[circuit breaker] {source} cooldown finished, entering half-open state")
                return True
            else:
                remaining = self.cooldown_seconds - time_since_failure
                logger.debug(f"[circuit breaker] {source} is open, remaining cooldown: {remaining:.0f}s")
                return False
        
        if state['state'] == CircuitState.HALF_OPEN:
            # Limit the number of requests in the half-open state
            if state['half_open_calls'] < self.half_open_max_calls:
                return True
            return False
        
        return True
    
    def record_success(self, source: str) -> None:
        """Log successful request"""
        state = self._get_state(source)
        
        if state['state'] == CircuitState.HALF_OPEN:
            # Successful in half-open state, full recovery
            logger.info(f"[circuit breaker] {source} request succeeded in half-open state, fully recovered")
        
        # reset state
        state['state'] = CircuitState.CLOSED
        state['failures'] = 0
        state['half_open_calls'] = 0
        state['last_error'] = None
    
    def record_failure(self, source: str, error: Optional[str] = None) -> None:
        """Logging failed requests"""
        state = self._get_state(source)
        current_time = time.time()
        
        state['failures'] += 1
        state['last_failure_time'] = current_time
        state['last_error'] = error
        
        if state['state'] == CircuitState.HALF_OPEN:
            # Fails in half-open state and continues to fuse
            state['state'] = CircuitState.OPEN
            state['half_open_calls'] = 0
            logger.warning(f"[circuit breaker] {source} request failed in half-open state, staying open for {self.cooldown_seconds}s")
        elif state['failures'] >= self.failure_threshold:
            # reaches the threshold and enters the circuit breaker
            state['state'] = CircuitState.OPEN
            logger.warning(f"[circuit breaker] {source} failed {state['failures']} times consecutively and is now open "
                          f"(cooldown {self.cooldown_seconds}s)")
            if error:
                logger.warning(f"[circuit breaker] last error: {error}")
    
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get all data source status"""
        return {
            source: {
                'state': info['state'].value,
                'failures': info['failures'],
                'last_error': info['last_error']
            }
            for source, info in self._states.items()
        }
    
    def reset(self, source: Optional[str] = None) -> None:
        """Reset fuse status"""
        if source:
            if source in self._states:
                del self._states[source]
                logger.info(f"[circuit breaker] reset breaker state for {source}")
        else:
            self._states.clear()
            logger.info("[circuit breaker] reset breaker state for all data sources")


# ============================================
# Global circuit breaker example
# ============================================

# Real-time market circuit breaker (more stringent strategy)
_realtime_circuit_breaker = CircuitBreaker(
    failure_threshold=2,      # Failed 2 times in a row
    cooldown_seconds=180.0,   # Cool for 3 minutes
    half_open_max_calls=1
)


def get_realtime_circuit_breaker() -> CircuitBreaker:
    """Get realtime market breaker"""
    return _realtime_circuit_breaker
