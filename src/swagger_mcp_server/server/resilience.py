"""MCP server resilience utilities and retry logic.

Implements Story 2.5 retry patterns, circuit breaker, and graceful degradation.
"""

import asyncio
import time
import logging
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from functools import wraps
from enum import Enum

from .exceptions import (
    DatabaseConnectionError,
    DatabaseTimeoutError,
    ServiceUnavailableError,
    ResourceExhaustedError
)

T = TypeVar('T')
logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests rejected immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 10,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            success_threshold: Consecutive successes needed to close circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None

    def can_execute(self) -> bool:
        """Check if request can be executed through circuit breaker."""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (
                self.last_failure_time and
                time.time() - self.last_failure_time >= self.recovery_timeout
            ):
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN state")
                return True
            return False

        # HALF_OPEN state - allow limited requests
        return True

    def record_success(self) -> None:
        """Record successful operation."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker CLOSED - service recovered")
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning(
                    f"Circuit breaker OPEN - {self.failure_count} failures exceeded threshold"
                )
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Failed during recovery, go back to OPEN
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0
            logger.warning("Circuit breaker back to OPEN - recovery failed")

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "can_execute": self.can_execute()
        }


def retry_on_failure(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    max_backoff: float = 60.0,
    retry_exceptions: tuple = (DatabaseConnectionError, DatabaseTimeoutError)
):
    """Decorator for automatic retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier
        max_backoff: Maximum backoff delay in seconds
        retry_exceptions: Tuple of exceptions that should trigger retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"Operation succeeded after {attempt} retries")
                    return result

                except retry_exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(
                            f"Operation failed after {max_retries} retries",
                            extra={"error": str(e), "attempts": attempt + 1}
                        )
                        break

                    # Calculate backoff delay
                    delay = min(backoff_factor ** attempt, max_backoff)
                    logger.warning(
                        f"Operation failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay:.1f}s",
                        extra={"error": str(e), "retry_delay": delay}
                    )
                    await asyncio.sleep(delay)

                except Exception as e:
                    # Non-retryable exception, fail immediately
                    logger.error(f"Non-retryable error: {str(e)}")
                    raise

            # All retries exhausted
            raise last_exception

        return wrapper
    return decorator


def with_timeout(timeout_seconds: float = 30.0):
    """Decorator to add timeout to async operations.

    Args:
        timeout_seconds: Timeout in seconds
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                operation_name = func.__name__
                logger.error(
                    f"Operation '{operation_name}' timed out after {timeout_seconds}s"
                )
                raise DatabaseTimeoutError(operation_name, timeout_seconds)

        return wrapper
    return decorator


def with_circuit_breaker(circuit_breaker: CircuitBreaker):
    """Decorator to protect operations with circuit breaker.

    Args:
        circuit_breaker: Circuit breaker instance
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if not circuit_breaker.can_execute():
                raise ServiceUnavailableError(
                    service=func.__name__,
                    reason="Circuit breaker is OPEN",
                    retry_after_seconds=int(circuit_breaker.recovery_timeout)
                )

            try:
                result = await func(*args, **kwargs)
                circuit_breaker.record_success()
                return result
            except Exception as e:
                circuit_breaker.record_failure()
                raise

        return wrapper
    return decorator


class ResourcePool:
    """Simple resource pool with limits and monitoring."""

    def __init__(self, max_size: int, name: str = "resource_pool"):
        """Initialize resource pool.

        Args:
            max_size: Maximum number of resources in pool
            name: Name for logging and monitoring
        """
        self.max_size = max_size
        self.name = name
        self.current_size = 0
        self.peak_usage = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire a resource from the pool.

        Returns:
            True if resource acquired, False if pool exhausted

        Raises:
            ResourceExhaustedError: If pool is at capacity
        """
        async with self._lock:
            if self.current_size >= self.max_size:
                raise ResourceExhaustedError(
                    resource_type=self.name,
                    current_usage=self.current_size,
                    limit=self.max_size
                )

            self.current_size += 1
            self.peak_usage = max(self.peak_usage, self.current_size)
            return True

    async def release(self) -> None:
        """Release a resource back to the pool."""
        async with self._lock:
            if self.current_size > 0:
                self.current_size -= 1

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "name": self.name,
            "current_size": self.current_size,
            "max_size": self.max_size,
            "peak_usage": self.peak_usage,
            "utilization": self.current_size / self.max_size if self.max_size > 0 else 0
        }


class HealthChecker:
    """Health checker for system components."""

    def __init__(self):
        """Initialize health checker."""
        self.component_status: Dict[str, Dict[str, Any]] = {}
        self.last_check_time: Dict[str, float] = {}

    async def check_component_health(
        self,
        component_name: str,
        health_check_func: Callable[[], Any],
        cache_duration: float = 30.0
    ) -> Dict[str, Any]:
        """Check health of a system component.

        Args:
            component_name: Name of component to check
            health_check_func: Function that performs health check
            cache_duration: How long to cache health check results

        Returns:
            Health status dictionary
        """
        current_time = time.time()
        last_check = self.last_check_time.get(component_name, 0)

        # Use cached result if recent
        if current_time - last_check < cache_duration:
            return self.component_status.get(component_name, {"status": "unknown"})

        try:
            health_result = await health_check_func()
            status = {
                "status": "healthy",
                "timestamp": current_time,
                "details": health_result
            }
        except Exception as e:
            status = {
                "status": "unhealthy",
                "timestamp": current_time,
                "error": str(e)
            }

        self.component_status[component_name] = status
        self.last_check_time[component_name] = current_time
        return status

    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        if not self.component_status:
            return {"status": "unknown", "components": {}}

        healthy_count = sum(
            1 for status in self.component_status.values()
            if status.get("status") == "healthy"
        )
        total_count = len(self.component_status)

        overall_status = "healthy" if healthy_count == total_count else "degraded"
        if healthy_count == 0:
            overall_status = "unhealthy"

        return {
            "status": overall_status,
            "healthy_components": healthy_count,
            "total_components": total_count,
            "components": self.component_status
        }


# Global instances for server-wide use
database_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
connection_pool = ResourcePool(max_size=20, name="database_connections")
health_checker = HealthChecker()