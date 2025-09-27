"""Integration with existing monitoring framework for search analytics.

This module provides seamless integration between search performance analytics
and the existing MCP server monitoring infrastructure as specified in Story 3.6.
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

from ..config.settings import SearchConfig
from ..server.monitoring import PerformanceMonitor as MCPPerformanceMonitor
from .analytics_dashboard import SearchAnalyticsDashboard
from .performance_monitor import (
    PerformanceAlert,
    SearchAnalytics,
    SearchPerformanceMonitor,
)


@dataclass
class MonitoringIntegrationConfig:
    """Configuration for monitoring integration."""

    enable_mcp_integration: bool = True
    enable_structured_logging: bool = True
    alert_notification_enabled: bool = True
    metrics_export_interval_seconds: int = 60
    correlation_id_tracking: bool = True
    performance_threshold_sync: bool = True


@dataclass
class SearchMetricExport:
    """Standardized search metric export format."""

    metric_name: str
    metric_value: Union[float, int, str]
    metric_type: str  # "counter", "gauge", "histogram", "timer"
    timestamp: datetime
    tags: Dict[str, str]
    correlation_id: Optional[str] = None


class SearchMonitoringIntegration:
    """Integrates search analytics with existing MCP monitoring framework."""

    def __init__(
        self,
        search_monitor: SearchPerformanceMonitor,
        dashboard: SearchAnalyticsDashboard,
        mcp_monitor: Optional[MCPPerformanceMonitor] = None,
        config: Optional[MonitoringIntegrationConfig] = None,
    ):
        """Initialize monitoring integration.

        Args:
            search_monitor: Search performance monitor instance
            dashboard: Search analytics dashboard instance
            mcp_monitor: Existing MCP performance monitor (optional)
            config: Integration configuration
        """
        self.search_monitor = search_monitor
        self.dashboard = dashboard
        self.mcp_monitor = mcp_monitor
        self.config = config or MonitoringIntegrationConfig()

        # Set up logging
        self.logger = logging.getLogger(__name__)
        if self.config.enable_structured_logging:
            self._setup_structured_logging()

        # Metric export state
        self.last_export = datetime.now()
        self.export_task: Optional[asyncio.Task] = None

        # Alert notification callbacks
        self.alert_callbacks: List[Callable] = []

        # Integration status
        self.integration_active = False

    async def initialize_integration(self) -> None:
        """Initialize the monitoring integration."""
        try:
            self.logger.info("Initializing search monitoring integration")

            # Register alert callbacks
            if self.config.alert_notification_enabled:
                self.search_monitor.add_alert_callback(
                    self._handle_search_alert
                )

            # Start metric export task
            if self.config.metrics_export_interval_seconds > 0:
                self.export_task = asyncio.create_task(
                    self._metric_export_loop()
                )

            # Sync performance thresholds
            if self.config.performance_threshold_sync and self.mcp_monitor:
                await self._sync_performance_thresholds()

            self.integration_active = True
            self.logger.info(
                "Search monitoring integration initialized successfully"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to initialize monitoring integration: {e}"
            )
            raise

    async def shutdown_integration(self) -> None:
        """Shutdown the monitoring integration."""
        try:
            self.logger.info("Shutting down search monitoring integration")

            # Cancel metric export task
            if self.export_task and not self.export_task.done():
                self.export_task.cancel()
                try:
                    await self.export_task
                except asyncio.CancelledError:
                    pass

            # Remove alert callbacks
            self.search_monitor.remove_alert_callback(
                self._handle_search_alert
            )

            self.integration_active = False
            self.logger.info("Search monitoring integration shutdown complete")

        except Exception as e:
            self.logger.error(
                f"Error during monitoring integration shutdown: {e}"
            )

    async def export_search_metrics(self) -> List[SearchMetricExport]:
        """Export search metrics in standardized format.

        Returns:
            List[SearchMetricExport]: Exported metrics
        """
        try:
            metrics = []
            current_time = datetime.now()

            # Get performance summary
            performance_summary = (
                await self.search_monitor.get_performance_summary("1h")
            )

            # Export response time metrics
            response_times = performance_summary.get(
                "response_time_metrics", {}
            )
            for percentile, value in response_times.items():
                if isinstance(value, (int, float)):
                    metrics.append(
                        SearchMetricExport(
                            metric_name=f"search_response_time_{percentile}",
                            metric_value=value,
                            metric_type="gauge",
                            timestamp=current_time,
                            tags={
                                "component": "search",
                                "metric_type": "response_time",
                            },
                        )
                    )

            # Export volume metrics
            volume_metrics = performance_summary.get(
                "query_volume_metrics", {}
            )
            for metric_name, value in volume_metrics.items():
                if isinstance(value, (int, float)):
                    metrics.append(
                        SearchMetricExport(
                            metric_name=f"search_{metric_name}",
                            metric_value=value,
                            metric_type="gauge"
                            if "rate" in metric_name
                            else "counter",
                            timestamp=current_time,
                            tags={
                                "component": "search",
                                "metric_type": "volume",
                            },
                        )
                    )

            # Export effectiveness metrics
            effectiveness = performance_summary.get("search_effectiveness", {})
            for metric_name, value in effectiveness.items():
                if isinstance(value, (int, float)):
                    metrics.append(
                        SearchMetricExport(
                            metric_name=f"search_{metric_name}",
                            metric_value=value,
                            metric_type="gauge",
                            timestamp=current_time,
                            tags={
                                "component": "search",
                                "metric_type": "effectiveness",
                            },
                        )
                    )

            # Export cache performance
            cache_performance = performance_summary.get(
                "cache_performance", {}
            )
            for metric_name, value in cache_performance.items():
                if isinstance(value, (int, float)):
                    metrics.append(
                        SearchMetricExport(
                            metric_name=f"search_cache_{metric_name}",
                            metric_value=value,
                            metric_type="gauge",
                            timestamp=current_time,
                            tags={
                                "component": "search",
                                "metric_type": "cache",
                            },
                        )
                    )

            # Export current operational metrics
            current_metrics = performance_summary.get("current_metrics", {})
            for metric_name, value in current_metrics.items():
                if isinstance(value, (int, float)):
                    metrics.append(
                        SearchMetricExport(
                            metric_name=f"search_current_{metric_name}",
                            metric_value=value,
                            metric_type="gauge",
                            timestamp=current_time,
                            tags={
                                "component": "search",
                                "metric_type": "operational",
                            },
                        )
                    )

            return metrics

        except Exception as e:
            self.logger.error(f"Failed to export search metrics: {e}")
            return []

    async def log_search_analytics(self, analytics: SearchAnalytics) -> None:
        """Log search analytics with structured logging.

        Args:
            analytics: Search analytics to log
        """
        if not self.config.enable_structured_logging:
            return

        try:
            # Create structured log entry
            log_data = {
                "event_type": "search_analytics",
                "timestamp": analytics.timestamp.isoformat(),
                "correlation_id": analytics.correlation_id,
                "query_text": analytics.query_text[
                    :100
                ],  # Truncate for logging
                "search_type": analytics.search_type,
                "total_response_time_ms": analytics.total_response_time,
                "result_count": analytics.result_count,
                "performance_grade": analytics.performance_grade,
                "nfr1_compliant": analytics.nfr1_compliant,
                "cache_hit": analytics.cache_hit,
                "concurrent_queries": analytics.concurrent_queries,
                "filters_applied": len(analytics.filters_applied),
                "user_session": analytics.user_session,
            }

            # Log with appropriate level based on performance
            if analytics.exceeded_threshold:
                self.logger.warning(
                    "Search performance threshold exceeded", extra=log_data
                )
            elif analytics.performance_grade == "poor":
                self.logger.warning(
                    "Poor search performance detected", extra=log_data
                )
            else:
                self.logger.info("Search analytics", extra=log_data)

        except Exception as e:
            self.logger.error(f"Failed to log search analytics: {e}")

    async def _handle_search_alert(self, alert: PerformanceAlert) -> None:
        """Handle search performance alerts.

        Args:
            alert: Performance alert to handle
        """
        try:
            # Log alert
            alert_data = {
                "event_type": "search_alert",
                "alert_id": alert.alert_id,
                "alert_level": alert.level.value,
                "alert_title": alert.title,
                "alert_description": alert.description,
                "metric_value": alert.metric_value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp.isoformat(),
            }

            if alert.level.value == "critical":
                self.logger.critical("Critical search alert", extra=alert_data)
            elif alert.level.value == "warning":
                self.logger.warning(
                    "Search performance warning", extra=alert_data
                )
            else:
                self.logger.info("Search alert", extra=alert_data)

            # Integrate with MCP monitoring if available
            if self.mcp_monitor and hasattr(self.mcp_monitor, "record_alert"):
                await self.mcp_monitor.record_alert(
                    alert_type="search_performance",
                    severity=alert.level.value,
                    message=alert.description,
                    metadata=alert_data,
                )

            # Notify registered callbacks
            for callback in self.alert_callbacks:
                try:
                    await callback(alert)
                except Exception as e:
                    self.logger.error(f"Alert callback failed: {e}")

        except Exception as e:
            self.logger.error(f"Failed to handle search alert: {e}")

    async def _metric_export_loop(self) -> None:
        """Background task for periodic metric export."""
        while self.integration_active:
            try:
                # Export metrics
                exported_metrics = await self.export_search_metrics()

                # Send to MCP monitoring if available
                if self.mcp_monitor and exported_metrics:
                    await self._send_metrics_to_mcp(exported_metrics)

                # Log export activity
                self.logger.debug(
                    f"Exported {len(exported_metrics)} search metrics"
                )

                # Update last export time
                self.last_export = datetime.now()

                # Wait for next export cycle
                await asyncio.sleep(
                    self.config.metrics_export_interval_seconds
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in metric export loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _send_metrics_to_mcp(
        self, metrics: List[SearchMetricExport]
    ) -> None:
        """Send metrics to MCP monitoring system.

        Args:
            metrics: Metrics to send
        """
        try:
            if not self.mcp_monitor:
                return

            for metric in metrics:
                # Convert to MCP monitoring format
                mcp_metric = {
                    "name": metric.metric_name,
                    "value": metric.metric_value,
                    "type": metric.metric_type,
                    "timestamp": metric.timestamp.isoformat(),
                    "tags": metric.tags,
                }

                if metric.correlation_id:
                    mcp_metric["correlation_id"] = metric.correlation_id

                # Send to MCP monitoring
                if hasattr(self.mcp_monitor, "record_metric"):
                    await self.mcp_monitor.record_metric(mcp_metric)

        except Exception as e:
            self.logger.error(f"Failed to send metrics to MCP monitoring: {e}")

    async def _sync_performance_thresholds(self) -> None:
        """Sync performance thresholds with MCP monitoring."""
        try:
            if not self.mcp_monitor:
                return

            # Get MCP performance thresholds
            if hasattr(self.mcp_monitor, "get_performance_thresholds"):
                mcp_thresholds = (
                    await self.mcp_monitor.get_performance_thresholds()
                )

                # Update search monitor thresholds
                if "response_time_warning" in mcp_thresholds:
                    self.search_monitor.performance_thresholds[
                        "response_time_warning"
                    ] = mcp_thresholds["response_time_warning"]

                if "response_time_critical" in mcp_thresholds:
                    self.search_monitor.performance_thresholds[
                        "response_time_critical"
                    ] = mcp_thresholds["response_time_critical"]

                self.logger.info(
                    "Performance thresholds synchronized with MCP monitoring"
                )

        except Exception as e:
            self.logger.error(f"Failed to sync performance thresholds: {e}")

    def _setup_structured_logging(self) -> None:
        """Set up structured logging for search analytics."""
        try:
            # Configure logging format for structured data
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

            # Add handler if not already present
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)

        except Exception as e:
            print(f"Failed to setup structured logging: {e}")

    def add_alert_callback(self, callback: Callable) -> None:
        """Add callback function for alert notifications.

        Args:
            callback: Async callback function that accepts PerformanceAlert
        """
        self.alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: Callable) -> None:
        """Remove alert callback function.

        Args:
            callback: Callback function to remove
        """
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)

    async def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status and health information.

        Returns:
            Dict containing integration status
        """
        return {
            "integration_active": self.integration_active,
            "mcp_integration_enabled": self.config.enable_mcp_integration
            and self.mcp_monitor is not None,
            "structured_logging_enabled": self.config.enable_structured_logging,
            "alert_notification_enabled": self.config.alert_notification_enabled,
            "last_metric_export": self.last_export.isoformat(),
            "export_interval_seconds": self.config.metrics_export_interval_seconds,
            "registered_alert_callbacks": len(self.alert_callbacks),
            "export_task_running": self.export_task is not None
            and not self.export_task.done(),
        }

    async def generate_monitoring_report(
        self, time_period: str = "24h"
    ) -> Dict[str, Any]:
        """Generate comprehensive monitoring report.

        Args:
            time_period: Time period for the report

        Returns:
            Dict containing monitoring report
        """
        try:
            # Get dashboard data
            dashboard_data = await self.dashboard.get_dashboard_data(
                time_period
            )

            # Get integration status
            integration_status = await self.get_integration_status()

            # Export current metrics
            current_metrics = await self.export_search_metrics()

            # Generate report
            report = {
                "report_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "time_period": time_period,
                    "report_type": "comprehensive_monitoring",
                },
                "integration_status": integration_status,
                "performance_summary": {
                    "overview": dashboard_data.get("performance", {}).get(
                        "overview", {}
                    ),
                    "nfr1_compliance": dashboard_data.get(
                        "performance", {}
                    ).get("nfr1_compliance", {}),
                    "trends": dashboard_data.get("performance", {}).get(
                        "trends", {}
                    ),
                },
                "analytics_summary": {
                    "effectiveness": dashboard_data.get("analytics", {}).get(
                        "effectiveness", {}
                    ),
                    "top_patterns": dashboard_data.get("analytics", {}).get(
                        "query_patterns", []
                    )[:5],
                    "user_behavior": dashboard_data.get("analytics", {}).get(
                        "user_behavior", {}
                    ),
                },
                "system_health": {
                    "overall_health": dashboard_data.get("status", {}).get(
                        "overall_health", "unknown"
                    ),
                    "system_status": dashboard_data.get("status", {}).get(
                        "system_status", "unknown"
                    ),
                    "index_health": dashboard_data.get("index", {}).get(
                        "health", {}
                    ),
                    "active_alerts": len(
                        dashboard_data.get("alerts", {}).get(
                            "active_alerts", []
                        )
                    ),
                },
                "recommendations": {
                    "priority_actions": dashboard_data.get(
                        "recommendations", {}
                    ).get("priority_actions", []),
                    "performance_recommendations": dashboard_data.get(
                        "recommendations", {}
                    ).get("performance", [])[:3],
                    "analytics_recommendations": dashboard_data.get(
                        "recommendations", {}
                    ).get("analytics", [])[:3],
                },
                "exported_metrics": {
                    "total_metrics": len(current_metrics),
                    "metric_categories": list(
                        set(
                            m.tags.get("metric_type", "unknown")
                            for m in current_metrics
                        )
                    ),
                    "last_export": self.last_export.isoformat(),
                },
            }

            return report

        except Exception as e:
            return {
                "error": f"Failed to generate monitoring report: {e}",
                "timestamp": datetime.now().isoformat(),
            }

    async def validate_integration_health(self) -> Dict[str, Any]:
        """Validate the health of the monitoring integration.

        Returns:
            Dict containing validation results
        """
        health_checks = []

        try:
            # Check integration status
            if self.integration_active:
                health_checks.append(
                    {
                        "check": "integration_active",
                        "status": "pass",
                        "message": "Integration is active",
                    }
                )
            else:
                health_checks.append(
                    {
                        "check": "integration_active",
                        "status": "fail",
                        "message": "Integration is not active",
                    }
                )

            # Check metric export
            time_since_export = (
                datetime.now() - self.last_export
            ).total_seconds()
            if (
                time_since_export
                < self.config.metrics_export_interval_seconds * 2
            ):
                health_checks.append(
                    {
                        "check": "metric_export",
                        "status": "pass",
                        "message": f"Metrics exported {time_since_export:.0f}s ago",
                    }
                )
            else:
                health_checks.append(
                    {
                        "check": "metric_export",
                        "status": "warning",
                        "message": f"Last metric export was {time_since_export:.0f}s ago",
                    }
                )

            # Check MCP integration
            if self.config.enable_mcp_integration:
                if self.mcp_monitor:
                    health_checks.append(
                        {
                            "check": "mcp_integration",
                            "status": "pass",
                            "message": "MCP monitoring integration available",
                        }
                    )
                else:
                    health_checks.append(
                        {
                            "check": "mcp_integration",
                            "status": "warning",
                            "message": "MCP integration enabled but monitor not available",
                        }
                    )

            # Check export task
            if self.export_task:
                if self.export_task.done():
                    health_checks.append(
                        {
                            "check": "export_task",
                            "status": "warning",
                            "message": "Export task has stopped",
                        }
                    )
                else:
                    health_checks.append(
                        {
                            "check": "export_task",
                            "status": "pass",
                            "message": "Export task is running",
                        }
                    )

            # Overall health assessment
            failed_checks = [c for c in health_checks if c["status"] == "fail"]
            warning_checks = [
                c for c in health_checks if c["status"] == "warning"
            ]

            if failed_checks:
                overall_status = "unhealthy"
            elif warning_checks:
                overall_status = "degraded"
            else:
                overall_status = "healthy"

            return {
                "overall_status": overall_status,
                "health_checks": health_checks,
                "total_checks": len(health_checks),
                "failed_checks": len(failed_checks),
                "warning_checks": len(warning_checks),
                "validation_time": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "overall_status": "error",
                "error": f"Health validation failed: {e}",
                "validation_time": datetime.now().isoformat(),
            }
