"""Health check endpoint implementation for MCP server monitoring.

Implements Story 2.6 health check requirements.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .monitoring import PerformanceMonitor, global_monitor
from .resilience import health_checker

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status for a system component."""

    status: HealthStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    check_duration_ms: Optional[float] = None


class HealthChecker:
    """Health check system for MCP server components."""

    def __init__(self, monitor: PerformanceMonitor = None):
        """Initialize health checker.

        Args:
            monitor: Performance monitor for metrics
        """
        self.monitor = monitor or global_monitor
        self.startup_time = time.time()

    async def check_database_health(self, db_manager) -> ComponentHealth:
        """Check database connectivity and performance."""
        start_time = time.time()

        try:
            if not db_manager:
                return ComponentHealth(
                    status=HealthStatus.UNHEALTHY,
                    message="Database manager not initialized",
                    check_duration_ms=(time.time() - start_time) * 1000,
                )

            # Perform database health check
            health_result = await db_manager.health_check()

            check_duration = (time.time() - start_time) * 1000

            if health_result.get("status") == "healthy":
                return ComponentHealth(
                    status=HealthStatus.HEALTHY,
                    message="Database connection healthy",
                    details={
                        "database_path": health_result.get("database_path"),
                        "file_size_bytes": health_result.get("file_size_bytes"),
                        "table_counts": health_result.get("table_counts", {}),
                    },
                    check_duration_ms=check_duration,
                )
            else:
                return ComponentHealth(
                    status=HealthStatus.DEGRADED,
                    message="Database connection degraded",
                    details=health_result,
                    check_duration_ms=check_duration,
                )

        except asyncio.TimeoutError:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message="Database health check timed out",
                check_duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message=f"Database health check failed: {str(e)}",
                check_duration_ms=(time.time() - start_time) * 1000,
            )

    async def check_mcp_responsiveness(self, server) -> ComponentHealth:
        """Check MCP server responsiveness with synthetic request."""
        start_time = time.time()

        try:
            if not server or not server.endpoint_repo:
                return ComponentHealth(
                    status=HealthStatus.UNHEALTHY,
                    message="MCP server not properly initialized",
                    check_duration_ms=(time.time() - start_time) * 1000,
                )

            # Perform a lightweight synthetic request
            test_result = await self._synthetic_mcp_test(server)
            check_duration = (time.time() - start_time) * 1000

            if test_result["success"]:
                # Check if response time is within reasonable bounds
                if test_result["response_time_ms"] < 1000:  # 1 second threshold
                    status = HealthStatus.HEALTHY
                    message = "MCP server responsive"
                else:
                    status = HealthStatus.DEGRADED
                    message = (
                        f"MCP server slow ({test_result['response_time_ms']:.0f}ms)"
                    )

                return ComponentHealth(
                    status=status,
                    message=message,
                    details={
                        "response_time_ms": test_result["response_time_ms"],
                        "test_type": test_result["test_type"],
                    },
                    check_duration_ms=check_duration,
                )
            else:
                return ComponentHealth(
                    status=HealthStatus.UNHEALTHY,
                    message=f"MCP server test failed: {test_result['error']}",
                    details=test_result,
                    check_duration_ms=check_duration,
                )

        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message=f"MCP responsiveness check failed: {str(e)}",
                check_duration_ms=(time.time() - start_time) * 1000,
            )

    async def _synthetic_mcp_test(self, server) -> Dict[str, Any]:
        """Perform synthetic MCP test for responsiveness check."""
        test_start = time.time()

        try:
            # Try a simple health-check-like operation
            # We'll use a minimal search that should be fast
            result = await server._search_endpoints(
                keywords="health-check-test",
                httpMethods=["GET"],
                page=1,
                perPage=1,
            )

            response_time_ms = (time.time() - test_start) * 1000

            # Check if we got a valid response (even if empty)
            if isinstance(result, dict) and "results" in result:
                return {
                    "success": True,
                    "response_time_ms": response_time_ms,
                    "test_type": "searchEndpoints_synthetic",
                    "result_count": len(result.get("results", [])),
                }
            else:
                return {
                    "success": False,
                    "response_time_ms": response_time_ms,
                    "test_type": "searchEndpoints_synthetic",
                    "error": "Invalid response format",
                }

        except Exception as e:
            return {
                "success": False,
                "response_time_ms": (time.time() - test_start) * 1000,
                "test_type": "searchEndpoints_synthetic",
                "error": str(e),
            }

    async def check_performance_health(self) -> ComponentHealth:
        """Check performance metrics for health assessment."""
        start_time = time.time()

        try:
            metrics = self.monitor.get_performance_metrics()
            performance_metrics = metrics["performance_metrics"]

            # Check if any methods are violating thresholds
            threshold_violations = []
            degraded_methods = []

            for method_name, method_metrics in performance_metrics.items():
                avg_time = method_metrics["avg_response_time"]
                error_rate = method_metrics["error_rate"]

                # Check response time thresholds
                thresholds = {
                    "searchEndpoints": 200,
                    "getSchema": 500,
                    "getExample": 2000,
                }

                if method_name in thresholds:
                    if avg_time > thresholds[method_name]:
                        threshold_violations.append(
                            f"{method_name}: {avg_time:.0f}ms > {thresholds[method_name]}ms"
                        )

                    if avg_time > thresholds[method_name] * 0.8:  # 80% of threshold
                        degraded_methods.append(method_name)

                # Check error rate
                if error_rate > 0.05:  # 5% error rate threshold
                    threshold_violations.append(
                        f"{method_name}: {error_rate:.1%} error rate"
                    )

            check_duration = (time.time() - start_time) * 1000

            if threshold_violations:
                return ComponentHealth(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Performance thresholds violated: {', '.join(threshold_violations)}",
                    details={
                        "violations": threshold_violations,
                        "degraded_methods": degraded_methods,
                        "performance_metrics": performance_metrics,
                    },
                    check_duration_ms=check_duration,
                )
            elif degraded_methods:
                return ComponentHealth(
                    status=HealthStatus.DEGRADED,
                    message=f"Performance degraded for: {', '.join(degraded_methods)}",
                    details={
                        "degraded_methods": degraded_methods,
                        "performance_metrics": performance_metrics,
                    },
                    check_duration_ms=check_duration,
                )
            else:
                return ComponentHealth(
                    status=HealthStatus.HEALTHY,
                    message="Performance metrics within thresholds",
                    details={"performance_metrics": performance_metrics},
                    check_duration_ms=check_duration,
                )

        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                message=f"Performance health check failed: {str(e)}",
                check_duration_ms=(time.time() - start_time) * 1000,
            )

    async def get_overall_health(self, server, db_manager) -> Dict[str, Any]:
        """Get comprehensive health status for all components."""
        check_start = time.time()

        # Run health checks in parallel for better performance
        db_health_task = asyncio.create_task(self.check_database_health(db_manager))
        mcp_health_task = asyncio.create_task(self.check_mcp_responsiveness(server))
        perf_health_task = asyncio.create_task(self.check_performance_health())

        try:
            # Wait for all health checks with timeout
            db_health, mcp_health, perf_health = await asyncio.wait_for(
                asyncio.gather(db_health_task, mcp_health_task, perf_health_task),
                timeout=10.0,  # 10 second timeout for all checks
            )
        except asyncio.TimeoutError:
            # Cancel remaining tasks
            for task in [db_health_task, mcp_health_task, perf_health_task]:
                if not task.done():
                    task.cancel()

            return {
                "status": "unhealthy",
                "message": "Health check timed out",
                "timestamp": time.time(),
                "uptime_seconds": time.time() - self.startup_time,
                "check_duration_ms": (time.time() - check_start) * 1000,
                "components": {
                    "database": {
                        "status": "timeout",
                        "message": "Health check timed out",
                    },
                    "mcp_server": {
                        "status": "timeout",
                        "message": "Health check timed out",
                    },
                    "performance": {
                        "status": "timeout",
                        "message": "Health check timed out",
                    },
                },
            }

        # Determine overall status
        component_statuses = [
            db_health.status,
            mcp_health.status,
            perf_health.status,
        ]

        if all(status == HealthStatus.HEALTHY for status in component_statuses):
            overall_status = "healthy"
        elif any(status == HealthStatus.UNHEALTHY for status in component_statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"

        # Create detailed response
        return {
            "status": overall_status,
            "message": f"System is {overall_status}",
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.startup_time,
            "check_duration_ms": (time.time() - check_start) * 1000,
            "components": {
                "database": {
                    "status": db_health.status.value,
                    "message": db_health.message,
                    "details": db_health.details,
                    "check_duration_ms": db_health.check_duration_ms,
                },
                "mcp_server": {
                    "status": mcp_health.status.value,
                    "message": mcp_health.message,
                    "details": mcp_health.details,
                    "check_duration_ms": mcp_health.check_duration_ms,
                },
                "performance": {
                    "status": perf_health.status.value,
                    "message": perf_health.message,
                    "details": perf_health.details,
                    "check_duration_ms": perf_health.check_duration_ms,
                },
            },
            "performance_summary": self.monitor.get_health_summary(),
            "version": "0.1.0",  # TODO: Get from actual version
        }

    async def get_basic_health(self) -> Dict[str, Any]:
        """Get basic health status for quick checks."""
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.startup_time,
            "version": "0.1.0",
        }


# Global health checker instance
health_checker = HealthChecker()
