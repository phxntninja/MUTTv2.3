#!/usr/bin/env python3
"""
=====================================================================
MUTT Shared Rate Limiter Module (Phase 3A)
=====================================================================
Provides reusable rate limiting functionality using Redis as a
distributed state store. Implements sliding window algorithm.

This module is shared between:
- Ingestor Service (protect MUTT from ingestion floods)
- Moog Forwarder Service (respect Moogsoft API rate limits)

Author: MUTT Team
Version: 2.5
=====================================================================
"""

import time
import logging
from typing import Optional
import redis

logger = logging.getLogger(__name__)

# Lua script for atomic sliding window rate limiting
# This ensures accurate rate limiting across multiple pods/processes
RATE_LIMIT_LUA_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Remove expired entries (outside the window)
local cutoff = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)

-- Count current entries in window
local current = redis.call('ZCARD', key)

-- Check if limit exceeded
if current >= limit then
    return 0
end

-- Add current request
redis.call('ZADD', key, now, now .. ':' .. math.random())

-- Set expiry on the key (cleanup)
redis.call('EXPIRE', key, window + 1)

return 1
"""


class RedisSlidingWindowRateLimiter:
    """
    Redis-based distributed rate limiter using sliding window algorithm.

    Features:
    - Distributed: Works across multiple pods/processes
    - Atomic: Uses Lua script for thread-safe operations
    - Sliding window: More accurate than fixed window
    - Auto-cleanup: Expired entries automatically removed

    Usage:
        limiter = RedisSlidingWindowRateLimiter(
            redis_client=redis_client,
            key="mutt:rate_limit:ingestor",
            max_requests=100,
            window_seconds=60
        )

        if limiter.is_allowed():
            # Process request
            pass
        else:
            # Reject request (rate limit exceeded)
            pass
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        key: str,
        max_requests: int,
        window_seconds: int
    ):
        """
        Initialize rate limiter.

        Args:
            redis_client: Redis client instance
            key: Redis key for this rate limiter (e.g., "mutt:rate_limit:ingestor")
            max_requests: Maximum number of requests allowed in the window
            window_seconds: Time window in seconds
        """
        self.redis_client = redis_client
        self.key = key
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        # Register Lua script
        try:
            self.lua_script = self.redis_client.register_script(RATE_LIMIT_LUA_SCRIPT)
            logger.debug(f"Rate limiter initialized: {key} ({max_requests}/{window_seconds}s)")
        except Exception as e:
            logger.error(f"Failed to register rate limit Lua script: {e}")
            self.lua_script = None

    def is_allowed(self) -> bool:
        """
        Check if a request is allowed under the current rate limit.

        Returns:
            True if request is allowed (within rate limit)
            False if request should be rejected (rate limit exceeded)
        """
        if self.lua_script is None:
            logger.warning("Rate limiter not initialized properly; allowing request")
            return True

        try:
            now = time.time()
            result = self.lua_script(
                keys=[self.key],
                args=[self.max_requests, self.window_seconds, now]
            )

            # result = 1 if allowed, 0 if rate limit exceeded
            return bool(result)

        except Exception as e:
            logger.error(f"Rate limiter check failed: {e}; allowing request")
            # Fail open: allow request if rate limiter has errors
            return True

    def get_current_count(self) -> int:
        """
        Get the current number of requests in the window.

        Returns:
            Number of requests in the current sliding window
        """
        try:
            now = time.time()
            cutoff = now - self.window_seconds

            # Remove expired entries
            self.redis_client.zremrangebyscore(self.key, '-inf', cutoff)

            # Count remaining entries
            count = self.redis_client.zcard(self.key)
            return count

        except Exception as e:
            logger.error(f"Failed to get rate limit count: {e}")
            return 0

    def reset(self) -> None:
        """
        Reset the rate limiter (clear all entries).

        Useful for testing or manual intervention.
        """
        try:
            self.redis_client.delete(self.key)
            logger.info(f"Rate limiter reset: {self.key}")
        except Exception as e:
            logger.error(f"Failed to reset rate limiter: {e}")

    def update_config(self, max_requests: Optional[int] = None, window_seconds: Optional[int] = None) -> None:
        """
        Update rate limiter configuration dynamically.

        Args:
            max_requests: New maximum requests limit (optional)
            window_seconds: New window size in seconds (optional)
        """
        if max_requests is not None and max_requests > 0:
            old_max = self.max_requests
            self.max_requests = max_requests
            logger.info(f"Rate limiter max_requests updated: {old_max} -> {max_requests}")

        if window_seconds is not None and window_seconds > 0:
            old_window = self.window_seconds
            self.window_seconds = window_seconds
            logger.info(f"Rate limiter window_seconds updated: {old_window} -> {window_seconds}")


class CircuitBreakerState:
    """Enum-like class for circuit breaker states."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external service calls.

    State Machine:
    - CLOSED: Normal operation, requests allowed
    - OPEN: Failure threshold exceeded, requests blocked
    - HALF_OPEN: Timeout expired, one test request allowed

    Features:
    - Protects against cascading failures
    - Automatic recovery testing
    - Configurable thresholds
    - Thread-safe (uses Redis for state)

    Usage:
        breaker = CircuitBreaker(
            redis_client=redis_client,
            name="moogsoft",
            failure_threshold=10,
            timeout_seconds=300
        )

        if breaker.is_open():
            # Skip request, circuit is open
            return

        try:
            result = make_external_call()
            breaker.record_success()
        except Exception as e:
            breaker.record_failure()
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        name: str,
        failure_threshold: int = 10,
        timeout_seconds: int = 300
    ):
        """
        Initialize circuit breaker.

        Args:
            redis_client: Redis client instance
            name: Circuit breaker name (e.g., "moogsoft")
            failure_threshold: Number of consecutive failures before opening
            timeout_seconds: Seconds to wait before attempting recovery (OPEN -> HALF_OPEN)
        """
        self.redis_client = redis_client
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds

        # Redis keys
        self.state_key = f"mutt:circuit_breaker:{name}:state"
        self.failure_count_key = f"mutt:circuit_breaker:{name}:failures"
        self.open_time_key = f"mutt:circuit_breaker:{name}:open_time"

        logger.debug(
            f"Circuit breaker initialized: {name} "
            f"(threshold={failure_threshold}, timeout={timeout_seconds}s)"
        )

    def get_state(self) -> str:
        """
        Get current circuit breaker state.

        Returns:
            One of: CLOSED, OPEN, HALF_OPEN
        """
        try:
            state = self.redis_client.get(self.state_key)
            if state is None:
                # Default to CLOSED if not set
                self._set_state(CircuitBreakerState.CLOSED)
                return CircuitBreakerState.CLOSED

            state_str = state.decode('utf-8') if isinstance(state, bytes) else state

            # Check if OPEN circuit should transition to HALF_OPEN
            if state_str == CircuitBreakerState.OPEN:
                open_time_raw = self.redis_client.get(self.open_time_key)
                if open_time_raw:
                    open_time = float(open_time_raw)
                    if time.time() - open_time >= self.timeout_seconds:
                        logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN (timeout expired)")
                        self._set_state(CircuitBreakerState.HALF_OPEN)
                        return CircuitBreakerState.HALF_OPEN

            return state_str

        except Exception as e:
            logger.error(f"Failed to get circuit breaker state: {e}")
            # Fail closed: allow requests if we can't determine state
            return CircuitBreakerState.CLOSED

    def is_open(self) -> bool:
        """
        Check if circuit is open (requests should be blocked).

        Returns:
            True if circuit is OPEN, False otherwise
        """
        return self.get_state() == CircuitBreakerState.OPEN

    def is_half_open(self) -> bool:
        """
        Check if circuit is half-open (testing recovery).

        Returns:
            True if circuit is HALF_OPEN, False otherwise
        """
        return self.get_state() == CircuitBreakerState.HALF_OPEN

    def is_closed(self) -> bool:
        """
        Check if circuit is closed (normal operation).

        Returns:
            True if circuit is CLOSED, False otherwise
        """
        return self.get_state() == CircuitBreakerState.CLOSED

    def record_success(self) -> None:
        """
        Record a successful request.

        Effects:
        - Resets failure counter
        - HALF_OPEN -> CLOSED transition
        """
        try:
            state = self.get_state()

            # Reset failure count
            self.redis_client.set(self.failure_count_key, 0)

            # If HALF_OPEN, transition to CLOSED
            if state == CircuitBreakerState.HALF_OPEN:
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED (success)")
                self._set_state(CircuitBreakerState.CLOSED)
                self.redis_client.delete(self.open_time_key)

        except Exception as e:
            logger.error(f"Failed to record circuit breaker success: {e}")

    def record_failure(self) -> None:
        """
        Record a failed request.

        Effects:
        - Increments failure counter
        - CLOSED -> OPEN transition if threshold exceeded
        - HALF_OPEN -> OPEN transition (test request failed)
        """
        try:
            state = self.get_state()

            # If HALF_OPEN, one failure immediately re-opens
            if state == CircuitBreakerState.HALF_OPEN:
                logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN (test request failed)")
                self._set_state(CircuitBreakerState.OPEN)
                self.redis_client.set(self.open_time_key, time.time())
                return

            # Increment failure count
            failure_count = self.redis_client.incr(self.failure_count_key)

            # Check threshold
            if failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit breaker {self.name}: CLOSED -> OPEN "
                    f"(failures={failure_count}, threshold={self.failure_threshold})"
                )
                self._set_state(CircuitBreakerState.OPEN)
                self.redis_client.set(self.open_time_key, time.time())

        except Exception as e:
            logger.error(f"Failed to record circuit breaker failure: {e}")

    def get_failure_count(self) -> int:
        """
        Get current consecutive failure count.

        Returns:
            Number of consecutive failures
        """
        try:
            count_raw = self.redis_client.get(self.failure_count_key)
            if count_raw is None:
                return 0
            return int(count_raw)
        except Exception as e:
            logger.error(f"Failed to get failure count: {e}")
            return 0

    def reset(self) -> None:
        """
        Manually reset circuit breaker to CLOSED state.

        Useful for manual intervention or testing.
        """
        try:
            self._set_state(CircuitBreakerState.CLOSED)
            self.redis_client.set(self.failure_count_key, 0)
            self.redis_client.delete(self.open_time_key)
            logger.info(f"Circuit breaker {self.name} manually reset to CLOSED")
        except Exception as e:
            logger.error(f"Failed to reset circuit breaker: {e}")

    def _set_state(self, state: str) -> None:
        """Internal: Set circuit breaker state in Redis."""
        try:
            self.redis_client.set(self.state_key, state)
        except Exception as e:
            logger.error(f"Failed to set circuit breaker state: {e}")

    def update_config(
        self,
        failure_threshold: Optional[int] = None,
        timeout_seconds: Optional[int] = None
    ) -> None:
        """
        Update circuit breaker configuration dynamically.

        Args:
            failure_threshold: New failure threshold (optional)
            timeout_seconds: New timeout in seconds (optional)
        """
        if failure_threshold is not None and failure_threshold > 0:
            old_threshold = self.failure_threshold
            self.failure_threshold = failure_threshold
            logger.info(f"Circuit breaker {self.name} threshold updated: {old_threshold} -> {failure_threshold}")

        if timeout_seconds is not None and timeout_seconds > 0:
            old_timeout = self.timeout_seconds
            self.timeout_seconds = timeout_seconds
            logger.info(f"Circuit breaker {self.name} timeout updated: {old_timeout} -> {timeout_seconds}")
