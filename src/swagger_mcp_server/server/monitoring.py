"""MCP server performance monitoring and metrics collection.

Implements Story 2.6 performance monitoring requirements.
"""

import asyncio
import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class PerformanceThresholds:
    """Performance thresholds for monitoring and alerting."""

    searchEndpoints_max_ms: float = 200.0
    getSchema_max_ms: float = 500.0
    getExample_max_ms: float = 2000.0
    error_rate_max: float = 0.05
    response_time_degradation: float = 1.5  # 50% slower than baseline
    error_rate_spike: float = 0.10  # 10% error rate
    connection_limit: int = 95  # 95% of max connections


@dataclass
class MethodMetrics:
    """Performance metrics for a single MCP method."""

    method_name: str
    total_requests: int = 0
    total_errors: int = 0
    total_response_time: float = 0.0
    response_times: deque = None
    error_types: Dict[str, int] = None
    last_request_time: Optional[float] = None

    def __post_init__(self):
        if self.response_times is None:
            self.response_times = deque(maxlen=1000)  # Keep last 1000 requests
        if self.error_types is None:
            self.error_types = defaultdict(int)

    @property
    def avg_response_time(self) -> float:
        """Get average response time in milliseconds."""
        return (
            (self.total_response_time / self.total_requests * 1000)
            if self.total_requests > 0
            else 0.0
        )

    @property
    def p95_response_time(self) -> float:
        """Get 95th percentile response time in milliseconds."""
        if len(self.response_times) >= 20:  # Need reasonable sample size
            sorted_times = sorted(self.response_times)
            p95_index = int(len(sorted_times) * 0.95)
            return sorted_times[p95_index] * 1000
        return self.avg_response_time

    @property
    def error_rate(self) -> float:
        """Get error rate as percentage."""
        return (
            (self.total_errors / self.total_requests)
            if self.total_requests > 0
            else 0.0
        )

    @property
    def requests_per_minute(self) -> float:
        """Get requests per minute based on recent activity."""
        if not self.last_request_time:
            return 0.0

        # Calculate based on last minute of activity
        current_time = time.time()
        minute_ago = current_time - 60
        recent_requests = sum(
            1
            for rt in self.response_times
            if hasattr(rt, "timestamp") and rt.timestamp > minute_ago
        )
        return recent_requests

    def record_request(
        self, response_time: float, error: Optional[str] = None
    ):
        """Record a request with its performance metrics."""
        self.total_requests += 1
        self.total_response_time += response_time
        self.response_times.append(response_time)
        self.last_request_time = time.time()

        if error:
            self.total_errors += 1
            self.error_types[error] += 1

    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get metrics as dictionary for JSON serialization."""
        return {
            "avg_response_time": round(self.avg_response_time, 2),
            "p95_response_time": round(self.p95_response_time, 2),
            "requests_per_minute": round(self.requests_per_minute, 2),
            "error_rate": round(self.error_rate, 4),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_types": dict(self.error_types),
        }


@dataclass
class SystemMetrics:
    """System-level performance metrics."""

    concurrent_connections: int = 0
    database_pool_utilization: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_utilization: float = 0.0
    uptime_seconds: float = 0.0
    startup_time: float = 0.0

    def __post_init__(self):
        if self.startup_time == 0.0:
            self.startup_time = time.time()

    def update_system_metrics(self):
        """Update system metrics with current values."""
        try:
            # Get CPU and memory usage
            process = psutil.Process()
            self.cpu_utilization = process.cpu_percent() / 100.0
            self.memory_usage_mb = process.memory_info().rss / 1024 / 1024
            self.uptime_seconds = time.time() - self.startup_time
        except Exception as e:
            logger.warning(f"Failed to update system metrics: {e}")

    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get metrics as dictionary for JSON serialization."""
        self.update_system_metrics()
        return {
            "concurrent_connections": self.concurrent_connections,
            "database_pool_utilization": round(
                self.database_pool_utilization, 3
            ),
            "memory_usage_mb": round(self.memory_usage_mb, 2),
            "cpu_utilization": round(self.cpu_utilization, 3),
            "uptime_seconds": round(self.uptime_seconds, 1),
        }


class PerformanceMonitor:
    """Central performance monitoring system for MCP server."""

    def __init__(self, thresholds: Optional[PerformanceThresholds] = None):
        """Initialize performance monitor.

        Args:
            thresholds: Performance thresholds for alerting
        """
        self.thresholds = thresholds or PerformanceThresholds()
        self.method_metrics: Dict[str, MethodMetrics] = {}
        self.system_metrics = SystemMetrics()
        self.alerts: List[Dict[str, Any]] = []
        self.monitoring_enabled = True
        self._lock = threading.Lock()

        # Initialize method metrics for known methods
        for method in ["searchEndpoints", "getSchema", "getExample"]:
            self.method_metrics[method] = MethodMetrics(method)

    def record_request(
        self,
        method_name: str,
        response_time: float,
        error: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """Record a request and its performance metrics.

        Args:
            method_name: Name of the MCP method
            response_time: Response time in seconds
            error: Error message if request failed
            request_id: Request ID for correlation
        """
        if not self.monitoring_enabled:
            return

        with self._lock:
            if method_name not in self.method_metrics:
                self.method_metrics[method_name] = MethodMetrics(method_name)

            metrics = self.method_metrics[method_name]
            metrics.record_request(response_time, error)

            # Check for threshold violations
            self._check_performance_thresholds(
                method_name, response_time, error, request_id
            )

    def _check_performance_thresholds(
        self,
        method_name: str,
        response_time: float,
        error: Optional[str],
        request_id: Optional[str],
    ):
        """Check if performance thresholds are violated."""
        response_time_ms = response_time * 1000
        metrics = self.method_metrics[method_name]

        # Check response time thresholds
        threshold_map = {
            "searchEndpoints": self.thresholds.searchEndpoints_max_ms,
            "getSchema": self.thresholds.getSchema_max_ms,
            "getExample": self.thresholds.getExample_max_ms,
        }

        if method_name in threshold_map:
            max_time = threshold_map[method_name]
            if response_time_ms > max_time:
                self._create_alert(
                    "response_time_exceeded",
                    f"{method_name} response time {response_time_ms:.1f}ms exceeded threshold {max_time}ms",
                    {
                        "method": method_name,
                        "response_time_ms": response_time_ms,
                        "threshold_ms": max_time,
                        "request_id": request_id,
                    },
                )

        # Check error rate thresholds
        if metrics.total_requests >= 10:  # Need reasonable sample size
            if metrics.error_rate > self.thresholds.error_rate_max:
                self._create_alert(
                    "error_rate_exceeded",
                    f"{method_name} error rate {metrics.error_rate:.3f} exceeded threshold {self.thresholds.error_rate_max}",
                    {
                        "method": method_name,
                        "error_rate": metrics.error_rate,
                        "threshold": self.thresholds.error_rate_max,
                        "total_requests": metrics.total_requests,
                        "total_errors": metrics.total_errors,
                    },
                )

    def _create_alert(
        self, alert_type: str, message: str, context: Dict[str, Any]
    ):
        """Create a performance alert."""
        alert = {
            "timestamp": time.time(),
            "type": alert_type,
            "message": message,
            "context": context,
        }
        self.alerts.append(alert)

        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]

        logger.warning(f"Performance alert: {message}", extra=context)

    def update_connection_count(self, count: int):
        """Update concurrent connection count."""
        with self._lock:
            self.system_metrics.concurrent_connections = count

    def update_database_pool_utilization(self, utilization: float):
        """Update database pool utilization."""
        with self._lock:
            self.system_metrics.database_pool_utilization = utilization

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get complete performance metrics."""
        with self._lock:
            return {
                "performance_metrics": {
                    method: metrics.get_metrics_dict()
                    for method, metrics in self.method_metrics.items()
                },
                "system_health": self.system_metrics.get_metrics_dict(),
                "alerts": self.alerts[-10:],  # Last 10 alerts
                "monitoring_enabled": self.monitoring_enabled,
                "thresholds": asdict(self.thresholds),
            }

    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary for health check endpoint."""
        with self._lock:
            # Determine overall health based on recent alerts and metrics
            recent_alerts = [
                a for a in self.alerts if time.time() - a["timestamp"] < 300
            ]  # Last 5 minutes
            critical_alerts = [
                a
                for a in recent_alerts
                if a["type"]
                in ["error_rate_exceeded", "response_time_exceeded"]
            ]

            if critical_alerts:
                status = (
                    "degraded" if len(critical_alerts) < 3 else "unhealthy"
                )
            else:
                status = "healthy"

            return {
                "status": status,
                "uptime_seconds": self.system_metrics.uptime_seconds,
                "total_requests": sum(
                    m.total_requests for m in self.method_metrics.values()
                ),
                "total_errors": sum(
                    m.total_errors for m in self.method_metrics.values()
                ),
                "recent_alerts": len(recent_alerts),
                "critical_alerts": len(critical_alerts),
            }

    def reset_metrics(self):
        """Reset all metrics (useful for testing)."""
        with self._lock:
            for metrics in self.method_metrics.values():
                metrics.total_requests = 0
                metrics.total_errors = 0
                metrics.total_response_time = 0.0
                metrics.response_times.clear()
                metrics.error_types.clear()
            self.alerts.clear()
            self.system_metrics = SystemMetrics()

    def set_monitoring_enabled(self, enabled: bool):
        """Enable or disable monitoring."""
        self.monitoring_enabled = enabled
        logger.info(
            f"Performance monitoring {'enabled' if enabled else 'disabled'}"
        )


def monitor_performance(method_name: str, monitor: PerformanceMonitor):
    """Decorator to monitor MCP method performance.

    Args:
        method_name: Name of the method being monitored
        monitor: PerformanceMonitor instance
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not monitor.monitoring_enabled:
                return await func(*args, **kwargs)

            start_time = time.time()
            error_msg = None
            request_id = kwargs.get("request_id", "unknown")

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error_msg = str(e)
                raise
            finally:
                response_time = time.time() - start_time
                monitor.record_request(
                    method_name, response_time, error_msg, request_id
                )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not monitor.monitoring_enabled:
                return func(*args, **kwargs)

            start_time = time.time()
            error_msg = None
            request_id = kwargs.get("request_id", "unknown")

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_msg = str(e)
                raise
            finally:
                response_time = time.time() - start_time
                monitor.record_request(
                    method_name, response_time, error_msg, request_id
                )

        # Return appropriate wrapper based on function type
        return (
            async_wrapper
            if asyncio.iscoroutinefunction(func)
            else sync_wrapper
        )

    return decorator


class MetricsCollector:
    """Periodic metrics collection for system monitoring."""

    def __init__(
        self, monitor: PerformanceMonitor, collection_interval: float = 30.0
    ):
        """Initialize metrics collector.

        Args:
            monitor: Performance monitor instance
            collection_interval: Collection interval in seconds
        """
        self.monitor = monitor
        self.collection_interval = collection_interval
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start periodic metrics collection."""
        if self.running:
            return

        self.running = True
        self._task = asyncio.create_task(self._collection_loop())
        logger.info(
            f"Started metrics collection with {self.collection_interval}s interval"
        )

    async def stop(self):
        """Stop periodic metrics collection."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped metrics collection")

    async def _collection_loop(self):
        """Periodic metrics collection loop."""
        while self.running:
            try:
                # Update system metrics
                self.monitor.system_metrics.update_system_metrics()

                # Log performance summary
                metrics = self.monitor.get_performance_metrics()
                logger.info(
                    "Performance summary",
                    extra={
                        "performance_metrics": metrics["performance_metrics"],
                        "system_health": metrics["system_health"],
                    },
                )

                await asyncio.sleep(self.collection_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
                await asyncio.sleep(self.collection_interval)


# Global performance monitor instance
global_monitor = PerformanceMonitor()
