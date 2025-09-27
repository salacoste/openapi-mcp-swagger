"""Analytics dashboard and reporting for search performance monitoring.

This module provides comprehensive dashboard capabilities for search analytics,
performance monitoring, and operational insights as specified in Story 3.6.
"""

import asyncio
import json
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..config.settings import SearchConfig
from .analytics_engine import SearchAnalyticsEngine
from .index_monitor import IndexPerformanceMonitor
from .performance_monitor import (
    PerformanceAlert,
    SearchAnalytics,
    SearchPerformanceMonitor,
)
from .performance_tester import SearchPerformanceTester


@dataclass
class DashboardConfiguration:
    """Configuration for analytics dashboard."""

    refresh_interval_seconds: int = 60
    alert_retention_hours: int = 24
    metrics_retention_days: int = 7
    auto_refresh: bool = True
    real_time_updates: bool = True


@dataclass
class DashboardWidget:
    """Individual dashboard widget configuration."""

    widget_id: str
    widget_type: str  # "metric", "chart", "table", "alert", "recommendation"
    title: str
    data_source: str
    refresh_interval: int = 60
    size: str = "medium"  # "small", "medium", "large"
    position: Tuple[int, int] = (0, 0)
    configuration: Dict[str, Any] = None


class SearchAnalyticsDashboard:
    """Comprehensive analytics dashboard for search performance monitoring."""

    def __init__(
        self,
        performance_monitor: SearchPerformanceMonitor,
        analytics_engine: SearchAnalyticsEngine,
        index_monitor: IndexPerformanceMonitor,
        performance_tester: Optional[SearchPerformanceTester] = None,
        config: Optional[DashboardConfiguration] = None,
    ):
        """Initialize the analytics dashboard.

        Args:
            performance_monitor: Search performance monitor instance
            analytics_engine: Search analytics engine instance
            index_monitor: Index performance monitor instance
            performance_tester: Optional performance tester instance
            config: Dashboard configuration
        """
        self.performance_monitor = performance_monitor
        self.analytics_engine = analytics_engine
        self.index_monitor = index_monitor
        self.performance_tester = performance_tester
        self.config = config or DashboardConfiguration()

        # Dashboard state
        self.last_refresh = datetime.now()
        self.dashboard_data = {}
        self.widget_configurations = self._create_default_widgets()

    def _create_default_widgets(self) -> List[DashboardWidget]:
        """Create default dashboard widget configuration."""
        widgets = [
            # Performance overview widgets
            DashboardWidget(
                widget_id="performance_overview",
                widget_type="metric",
                title="Performance Overview",
                data_source="performance_summary",
                size="large",
                position=(0, 0),
            ),
            DashboardWidget(
                widget_id="nfr1_compliance",
                widget_type="metric",
                title="NFR1 Compliance",
                data_source="nfr1_metrics",
                size="medium",
                position=(1, 0),
            ),
            DashboardWidget(
                widget_id="active_alerts",
                widget_type="alert",
                title="Active Alerts",
                data_source="current_alerts",
                size="medium",
                position=(2, 0),
            ),
            # Analytics widgets
            DashboardWidget(
                widget_id="query_patterns",
                widget_type="table",
                title="Top Query Patterns",
                data_source="query_patterns",
                size="large",
                position=(0, 1),
            ),
            DashboardWidget(
                widget_id="user_behavior",
                widget_type="chart",
                title="User Behavior Distribution",
                data_source="user_behavior",
                size="medium",
                position=(1, 1),
            ),
            DashboardWidget(
                widget_id="search_effectiveness",
                widget_type="metric",
                title="Search Effectiveness",
                data_source="effectiveness_metrics",
                size="medium",
                position=(2, 1),
            ),
            # Index performance widgets
            DashboardWidget(
                widget_id="index_health",
                widget_type="metric",
                title="Index Health",
                data_source="index_health",
                size="medium",
                position=(0, 2),
            ),
            DashboardWidget(
                widget_id="index_growth",
                widget_type="chart",
                title="Index Growth Trend",
                data_source="index_growth",
                size="large",
                position=(1, 2),
            ),
            # Recommendations widget
            DashboardWidget(
                widget_id="recommendations",
                widget_type="recommendation",
                title="Optimization Recommendations",
                data_source="optimization_recommendations",
                size="large",
                position=(0, 3),
            ),
        ]

        return widgets

    async def get_dashboard_data(
        self, time_period: str = "24h"
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard data.

        Args:
            time_period: Time period for analytics (1h, 6h, 24h, 7d)

        Returns:
            Dict containing all dashboard data
        """
        dashboard_start = datetime.now()

        try:
            # Gather data from all monitoring components
            performance_data = (
                await self.performance_monitor.get_performance_summary(
                    time_period
                )
            )
            analytics_data = await self._get_analytics_data(time_period)
            index_data = await self.index_monitor.get_performance_summary(
                time_period
            )

            # Optional performance testing data
            testing_data = {}
            if self.performance_tester:
                testing_data = await self._get_testing_summary()

            # Generate unified dashboard data
            dashboard_data = {
                "metadata": {
                    "generated_at": dashboard_start.isoformat(),
                    "time_period": time_period,
                    "data_freshness": self._calculate_data_freshness(),
                    "dashboard_version": "1.0",
                },
                # Core performance metrics
                "performance": {
                    "overview": self._format_performance_overview(
                        performance_data
                    ),
                    "nfr1_compliance": self._format_nfr1_metrics(
                        performance_data
                    ),
                    "response_times": self._format_response_time_data(
                        performance_data
                    ),
                    "trends": self._format_performance_trends(
                        performance_data
                    ),
                },
                # Search analytics
                "analytics": {
                    "query_patterns": self._format_query_patterns(
                        analytics_data
                    ),
                    "user_behavior": self._format_user_behavior(
                        analytics_data
                    ),
                    "effectiveness": self._format_effectiveness_metrics(
                        analytics_data
                    ),
                    "insights": analytics_data.get("insights", {}),
                },
                # Index performance
                "index": {
                    "health": self._format_index_health(index_data),
                    "performance": self._format_index_performance(index_data),
                    "growth": self._format_index_growth(index_data),
                    "optimization": self._format_optimization_status(
                        index_data
                    ),
                },
                # Alerts and notifications
                "alerts": {
                    "active_alerts": self._format_active_alerts(),
                    "alert_summary": self._format_alert_summary(),
                    "resolved_alerts": self._format_resolved_alerts(),
                },
                # Recommendations
                "recommendations": {
                    "performance": self._extract_performance_recommendations(
                        performance_data
                    ),
                    "analytics": analytics_data.get("recommendations", []),
                    "index": index_data.get("recommendations", []),
                    "priority_actions": self._generate_priority_actions(
                        performance_data, analytics_data, index_data
                    ),
                },
                # Testing results (if available)
                "testing": testing_data,
                # Operational status
                "status": {
                    "overall_health": self._calculate_overall_health(
                        performance_data, index_data
                    ),
                    "system_status": self._determine_system_status(
                        performance_data, analytics_data, index_data
                    ),
                    "capacity_status": self._assess_capacity_status(
                        index_data
                    ),
                    "uptime": self._calculate_uptime(),
                },
            }

            # Cache dashboard data
            self.dashboard_data = dashboard_data
            self.last_refresh = datetime.now()

            return dashboard_data

        except Exception as e:
            return {
                "error": f"Failed to generate dashboard data: {str(e)}",
                "timestamp": dashboard_start.isoformat(),
            }

    async def _get_analytics_data(self, time_period: str) -> Dict[str, Any]:
        """Get analytics data for dashboard."""
        try:
            # Get recent analytics from performance monitor
            cutoff_time = self._get_cutoff_time(time_period)
            recent_analytics = [
                a
                for a in self.performance_monitor.analytics_data
                if a.timestamp >= cutoff_time
            ]

            if recent_analytics:
                return await self.analytics_engine.analyze_search_patterns(
                    recent_analytics
                )
            else:
                return {"patterns": [], "insights": {}, "recommendations": []}

        except Exception:
            return {"patterns": [], "insights": {}, "recommendations": []}

    async def _get_testing_summary(self) -> Dict[str, Any]:
        """Get performance testing summary if available."""
        try:
            # This would integrate with stored test results
            # For now, return basic test status
            return {
                "last_test_run": None,
                "nfr1_compliance": None,
                "load_test_status": "not_run",
                "test_schedule": "weekly",
            }
        except Exception:
            return {}

    def _format_performance_overview(
        self, performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format performance overview for dashboard."""
        try:
            response_times = performance_data.get("response_time_metrics", {})
            volume = performance_data.get("query_volume_metrics", {})
            current_metrics = performance_data.get("current_metrics", {})

            return {
                "avg_response_time_ms": response_times.get("avg", 0),
                "p95_response_time_ms": response_times.get("p95", 0),
                "total_queries": volume.get("total_queries", 0),
                "queries_per_hour": volume.get("avg_queries_per_hour", 0),
                "active_queries": current_metrics.get("active_queries", 0),
                "cache_hit_rate": current_metrics.get(
                    "cache_hit_rate_hour", 0
                ),
                "error_rate": current_metrics.get("error_rate_hour", 0),
            }
        except Exception:
            return {}

    def _format_nfr1_metrics(
        self, performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format NFR1 compliance metrics for dashboard."""
        try:
            response_times = performance_data.get("response_time_metrics", {})
            nfr1_compliance = response_times.get("nfr1_compliance", 0)

            # Determine compliance status
            if nfr1_compliance >= 95:
                status = "excellent"
                color = "green"
            elif nfr1_compliance >= 85:
                status = "good"
                color = "yellow"
            elif nfr1_compliance >= 70:
                status = "warning"
                color = "orange"
            else:
                status = "critical"
                color = "red"

            return {
                "compliance_percentage": nfr1_compliance,
                "status": status,
                "status_color": color,
                "threshold_ms": 200,
                "violations": max(0, 100 - nfr1_compliance),
            }
        except Exception:
            return {"compliance_percentage": 0, "status": "unknown"}

    def _format_response_time_data(
        self, performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format response time data for dashboard charts."""
        try:
            response_times = performance_data.get("response_time_metrics", {})

            return {
                "percentiles": {
                    "p50": response_times.get("p50", 0),
                    "p95": response_times.get("p95", 0),
                    "p99": response_times.get("p99", 0),
                },
                "distribution": {
                    "min": response_times.get("min", 0),
                    "avg": response_times.get("avg", 0),
                    "max": response_times.get("max", 0),
                    "std_dev": response_times.get("std_dev", 0),
                },
                "trend": self._extract_response_time_trend(performance_data),
            }
        except Exception:
            return {}

    def _format_performance_trends(
        self, performance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format performance trends for dashboard."""
        try:
            trends = performance_data.get("performance_trends", {})
            cache_perf = performance_data.get("cache_performance", {})

            return {
                "response_time_trend": trends.get("trend_direction", "stable"),
                "trend_magnitude": trends.get("trend_magnitude_percent", 0),
                "performance_stability": trends.get(
                    "performance_stability", "stable"
                ),
                "cache_effectiveness": cache_perf.get(
                    "cache_effectiveness", "medium"
                ),
                "improvement_opportunities": len(
                    performance_data.get("optimization_recommendations", [])
                ),
            }
        except Exception:
            return {}

    def _format_query_patterns(
        self, analytics_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Format query patterns for dashboard table."""
        try:
            patterns = analytics_data.get("query_patterns", [])

            formatted_patterns = []
            for pattern in patterns[:10]:  # Top 10 patterns
                formatted_patterns.append(
                    {
                        "pattern": pattern.get("pattern_text", ""),
                        "frequency": pattern.get("frequency", 0),
                        "success_rate": pattern.get("success_rate", 0),
                        "avg_response_time": pattern.get(
                            "avg_response_time", 0
                        ),
                        "optimization_potential": pattern.get(
                            "optimization_potential", "low"
                        ),
                        "pattern_type": pattern.get("pattern_type", "unknown"),
                    }
                )

            return formatted_patterns
        except Exception:
            return []

    def _format_user_behavior(
        self, analytics_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format user behavior data for dashboard."""
        try:
            user_behavior = analytics_data.get("user_behavior", {})
            effectiveness = analytics_data.get("effectiveness_metrics", {})

            return {
                "behavior_distribution": user_behavior.get(
                    "behavior_distribution", {}
                ),
                "avg_satisfaction": user_behavior.get(
                    "avg_satisfaction_score", 0
                ),
                "conversion_rate": user_behavior.get("conversion_rate", 0),
                "session_metrics": {
                    "avg_queries_per_session": user_behavior.get(
                        "avg_queries_per_session", 0
                    ),
                    "avg_session_duration": user_behavior.get(
                        "session_duration_avg", 0
                    ),
                },
                "engagement_metrics": {
                    "user_engagement": effectiveness.get("user_engagement", 0),
                    "abandonment_rate": effectiveness.get(
                        "abandonment_rate", 0
                    ),
                    "refinement_rate": effectiveness.get("refinement_rate", 0),
                },
            }
        except Exception:
            return {}

    def _format_effectiveness_metrics(
        self, analytics_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format search effectiveness metrics for dashboard."""
        try:
            effectiveness = analytics_data.get("effectiveness_metrics", {})

            # Calculate overall effectiveness score
            relevance = effectiveness.get("relevance_score", 0)
            success_rate = effectiveness.get("query_success_rate", 0)
            engagement = effectiveness.get("user_engagement", 0)

            overall_score = (
                relevance * 0.4 + success_rate * 0.4 + engagement * 0.2
            ) * 100

            return {
                "overall_effectiveness": overall_score,
                "relevance_score": relevance * 100,
                "success_rate": success_rate * 100,
                "user_engagement": engagement,
                "abandonment_rate": effectiveness.get("abandonment_rate", 0)
                * 100,
                "time_to_success": effectiveness.get("time_to_success"),
                "effectiveness_grade": self._calculate_effectiveness_grade(
                    overall_score
                ),
            }
        except Exception:
            return {}

    def _format_index_health(
        self, index_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format index health data for dashboard."""
        try:
            health = index_data.get("health", {})
            performance = index_data.get("performance", {})

            return {
                "health_score": health.get("health_score", 0),
                "health_status": health.get("health_status", "unknown"),
                "fragmentation": health.get("current_fragmentation", 0),
                "cache_hit_rate": health.get("current_cache_hit_rate", 0),
                "query_performance": {
                    "avg_query_time": performance.get("avg_query_time_ms", 0),
                    "p95_query_time": performance.get("p95_query_time_ms", 0),
                    "nfr_compliance": performance.get(
                        "nfr_compliance_percent", 0
                    ),
                },
            }
        except Exception:
            return {}

    def _format_index_performance(
        self, index_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format index performance data for dashboard."""
        try:
            performance = index_data.get("performance", {})
            resource = index_data.get("resource_usage", {})

            return {
                "query_performance": {
                    "avg_time_ms": performance.get("avg_query_time_ms", 0),
                    "max_time_ms": performance.get("max_query_time_ms", 0),
                    "trend": performance.get("query_time_trend", "stable"),
                },
                "resource_usage": {
                    "memory_mb": resource.get("avg_memory_mb", 0),
                    "cpu_percent": resource.get("avg_cpu_percent", 0),
                    "storage_utilization": resource.get(
                        "current_storage_utilization", 0
                    ),
                },
                "optimization_status": index_data.get("optimization", {}),
            }
        except Exception:
            return {}

    def _format_index_growth(
        self, index_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format index growth data for dashboard."""
        try:
            size_stats = index_data.get("index_size", {})

            return {
                "current_size_mb": size_stats.get("current_size_mb", 0),
                "growth_mb": size_stats.get("size_growth_mb", 0),
                "document_count": size_stats.get("current_documents", 0),
                "document_growth": size_stats.get("document_growth", 0),
                "avg_size_per_doc": size_stats.get(
                    "avg_size_per_document_kb", 0
                ),
                "growth_trend": "increasing"
                if size_stats.get("size_growth_mb", 0) > 0
                else "stable",
            }
        except Exception:
            return {}

    def _format_optimization_status(
        self, index_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format index optimization status for dashboard."""
        try:
            optimization = index_data.get("optimization", {})

            return {
                "last_optimization": optimization.get("last_optimization"),
                "optimization_frequency": f"{optimization.get('total_optimizations', 0)} in last 30 days",
                "avg_improvement": optimization.get(
                    "avg_performance_improvement_percent", 0
                ),
                "size_reduction": optimization.get(
                    "avg_size_reduction_percent", 0
                ),
                "status": "up_to_date"
                if optimization.get("optimization_in_progress")
                else "available",
            }
        except Exception:
            return {}

    def _format_active_alerts(self) -> List[Dict[str, Any]]:
        """Format active alerts for dashboard."""
        try:
            active_alerts = self.performance_monitor.get_active_alerts()

            formatted_alerts = []
            for alert in active_alerts:
                formatted_alerts.append(
                    {
                        "id": alert.alert_id,
                        "level": alert.level.value,
                        "title": alert.title,
                        "description": alert.description,
                        "timestamp": alert.timestamp.isoformat(),
                        "metric_value": alert.metric_value,
                        "threshold": alert.threshold,
                        "age_hours": (
                            datetime.now() - alert.timestamp
                        ).total_seconds()
                        / 3600,
                    }
                )

            return formatted_alerts
        except Exception:
            return []

    def _format_alert_summary(self) -> Dict[str, Any]:
        """Format alert summary for dashboard."""
        try:
            recent_alerts = self.performance_monitor.get_recent_alerts(24)

            critical_count = len(
                [a for a in recent_alerts if a.level.value == "critical"]
            )
            warning_count = len(
                [a for a in recent_alerts if a.level.value == "warning"]
            )
            resolved_count = len([a for a in recent_alerts if a.resolved])

            return {
                "total_alerts_24h": len(recent_alerts),
                "critical_alerts": critical_count,
                "warning_alerts": warning_count,
                "resolved_alerts": resolved_count,
                "resolution_rate": resolved_count
                / max(len(recent_alerts), 1)
                * 100,
            }
        except Exception:
            return {}

    def _format_resolved_alerts(self) -> List[Dict[str, Any]]:
        """Format recently resolved alerts for dashboard."""
        try:
            recent_alerts = self.performance_monitor.get_recent_alerts(24)
            resolved_alerts = [a for a in recent_alerts if a.resolved]

            formatted_alerts = []
            for alert in resolved_alerts[-5:]:  # Last 5 resolved
                resolution_time = None
                if alert.resolution_time and alert.timestamp:
                    resolution_time = (
                        alert.resolution_time - alert.timestamp
                    ).total_seconds() / 60

                formatted_alerts.append(
                    {
                        "title": alert.title,
                        "level": alert.level.value,
                        "resolved_at": alert.resolution_time.isoformat()
                        if alert.resolution_time
                        else None,
                        "resolution_time_minutes": resolution_time,
                    }
                )

            return formatted_alerts
        except Exception:
            return []

    def _extract_performance_recommendations(
        self, performance_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract performance recommendations from performance data."""
        try:
            return performance_data.get("optimization_recommendations", [])
        except Exception:
            return []

    def _generate_priority_actions(
        self,
        performance_data: Dict[str, Any],
        analytics_data: Dict[str, Any],
        index_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate priority actions based on all monitoring data."""
        priority_actions = []

        try:
            # Check for critical performance issues
            response_times = performance_data.get("response_time_metrics", {})
            if response_times.get("nfr1_compliance", 100) < 70:
                priority_actions.append(
                    {
                        "priority": "critical",
                        "category": "performance",
                        "action": "Address NFR1 compliance violations",
                        "impact": "system_performance",
                        "urgency": "immediate",
                    }
                )

            # Check for index health issues
            health = index_data.get("health", {})
            if health.get("health_score", 100) < 60:
                priority_actions.append(
                    {
                        "priority": "high",
                        "category": "index",
                        "action": "Optimize index health and fragmentation",
                        "impact": "search_performance",
                        "urgency": "within_24h",
                    }
                )

            # Check for user experience issues
            effectiveness = analytics_data.get("effectiveness_metrics", {})
            if effectiveness.get("abandonment_rate", 0) > 0.3:
                priority_actions.append(
                    {
                        "priority": "high",
                        "category": "user_experience",
                        "action": "Reduce search abandonment rate",
                        "impact": "user_satisfaction",
                        "urgency": "within_week",
                    }
                )

            # Check for capacity issues
            resource_usage = index_data.get("resource_usage", {})
            if resource_usage.get("current_storage_utilization", 0) > 0.85:
                priority_actions.append(
                    {
                        "priority": "medium",
                        "category": "capacity",
                        "action": "Plan storage capacity expansion",
                        "impact": "system_availability",
                        "urgency": "within_month",
                    }
                )

        except Exception:
            pass

        return priority_actions

    def _calculate_overall_health(
        self, performance_data: Dict[str, Any], index_data: Dict[str, Any]
    ) -> str:
        """Calculate overall system health status."""
        try:
            # Performance health
            nfr1_compliance = performance_data.get(
                "response_time_metrics", {}
            ).get("nfr1_compliance", 0)
            performance_score = min(nfr1_compliance, 100)

            # Index health
            index_health = index_data.get("health", {}).get("health_score", 0)

            # Combined health score
            overall_score = (performance_score + index_health) / 2

            if overall_score >= 90:
                return "excellent"
            elif overall_score >= 75:
                return "good"
            elif overall_score >= 60:
                return "fair"
            else:
                return "poor"

        except Exception:
            return "unknown"

    def _determine_system_status(
        self,
        performance_data: Dict[str, Any],
        analytics_data: Dict[str, Any],
        index_data: Dict[str, Any],
    ) -> str:
        """Determine overall system status."""
        try:
            # Check for critical issues
            active_alerts = self.performance_monitor.get_active_alerts()
            critical_alerts = [
                a for a in active_alerts if a.level.value == "critical"
            ]

            if critical_alerts:
                return "critical"

            # Check performance metrics
            nfr1_compliance = performance_data.get(
                "response_time_metrics", {}
            ).get("nfr1_compliance", 100)
            if nfr1_compliance < 70:
                return "degraded"

            # Check index health
            index_health = index_data.get("health", {}).get(
                "health_score", 100
            )
            if index_health < 60:
                return "degraded"

            return "operational"

        except Exception:
            return "unknown"

    def _assess_capacity_status(self, index_data: Dict[str, Any]) -> str:
        """Assess system capacity status."""
        try:
            resource_usage = index_data.get("resource_usage", {})
            storage_util = resource_usage.get("current_storage_utilization", 0)
            memory_usage = resource_usage.get("avg_memory_mb", 0)

            if (
                storage_util > 0.9 or memory_usage > 1000
            ):  # >90% storage or >1GB memory
                return "critical"
            elif (
                storage_util > 0.8 or memory_usage > 500
            ):  # >80% storage or >500MB memory
                return "warning"
            else:
                return "normal"

        except Exception:
            return "unknown"

    def _calculate_uptime(self) -> Dict[str, Any]:
        """Calculate system uptime metrics."""
        # This would be calculated based on actual monitoring data
        # For now, return placeholder values
        return {
            "uptime_percentage": 99.9,
            "downtime_minutes_24h": 1.44,
            "last_outage": None,
            "mtbf_hours": 720,  # Mean time between failures
        }

    def _calculate_data_freshness(self) -> Dict[str, Any]:
        """Calculate data freshness indicators."""
        now = datetime.now()

        return {
            "performance_data_age_seconds": (
                now - self.last_refresh
            ).total_seconds(),
            "analytics_data_current": True,
            "index_data_current": True,
            "last_refresh": self.last_refresh.isoformat(),
        }

    def _extract_response_time_trend(
        self, performance_data: Dict[str, Any]
    ) -> str:
        """Extract response time trend from performance data."""
        try:
            trends = performance_data.get("performance_trends", {})
            return trends.get("trend_direction", "stable")
        except Exception:
            return "stable"

    def _calculate_effectiveness_grade(
        self, effectiveness_score: float
    ) -> str:
        """Calculate effectiveness grade from score."""
        if effectiveness_score >= 90:
            return "A"
        elif effectiveness_score >= 80:
            return "B"
        elif effectiveness_score >= 70:
            return "C"
        elif effectiveness_score >= 60:
            return "D"
        else:
            return "F"

    def _get_cutoff_time(self, time_period: str) -> datetime:
        """Get cutoff time for time period."""
        now = datetime.now()
        if time_period == "1h":
            return now - timedelta(hours=1)
        elif time_period == "6h":
            return now - timedelta(hours=6)
        elif time_period == "24h":
            return now - timedelta(hours=24)
        elif time_period == "7d":
            return now - timedelta(days=7)
        else:
            return now - timedelta(hours=24)

    async def export_dashboard_data(self, format: str = "json") -> str:
        """Export dashboard data in specified format.

        Args:
            format: Export format ("json", "csv")

        Returns:
            str: Exported data
        """
        dashboard_data = await self.get_dashboard_data()

        if format.lower() == "json":
            return json.dumps(dashboard_data, indent=2, default=str)
        elif format.lower() == "csv":
            # Convert to CSV format (simplified)
            csv_data = "metric,value,timestamp\n"
            perf_overview = dashboard_data.get("performance", {}).get(
                "overview", {}
            )
            for metric, value in perf_overview.items():
                csv_data += f"{metric},{value},{dashboard_data['metadata']['generated_at']}\n"
            return csv_data
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def get_widget_data(self, widget_id: str) -> Dict[str, Any]:
        """Get data for a specific dashboard widget.

        Args:
            widget_id: Widget identifier

        Returns:
            Dict containing widget-specific data
        """
        # Find widget configuration
        widget_config = next(
            (
                w
                for w in self.widget_configurations
                if w.widget_id == widget_id
            ),
            None,
        )

        if not widget_config:
            return {"error": f"Widget {widget_id} not found"}

        # Get full dashboard data
        dashboard_data = await self.get_dashboard_data()

        # Extract widget-specific data based on data source
        data_source = widget_config.data_source
        widget_data = self._extract_widget_data(dashboard_data, data_source)

        return {
            "widget_id": widget_id,
            "widget_type": widget_config.widget_type,
            "title": widget_config.title,
            "data": widget_data,
            "last_updated": datetime.now().isoformat(),
        }

    def _extract_widget_data(
        self, dashboard_data: Dict[str, Any], data_source: str
    ) -> Any:
        """Extract specific data for widget based on data source."""
        data_map = {
            "performance_summary": dashboard_data.get("performance", {}).get(
                "overview", {}
            ),
            "nfr1_metrics": dashboard_data.get("performance", {}).get(
                "nfr1_compliance", {}
            ),
            "current_alerts": dashboard_data.get("alerts", {}).get(
                "active_alerts", []
            ),
            "query_patterns": dashboard_data.get("analytics", {}).get(
                "query_patterns", []
            ),
            "user_behavior": dashboard_data.get("analytics", {}).get(
                "user_behavior", {}
            ),
            "effectiveness_metrics": dashboard_data.get("analytics", {}).get(
                "effectiveness", {}
            ),
            "index_health": dashboard_data.get("index", {}).get("health", {}),
            "index_growth": dashboard_data.get("index", {}).get("growth", {}),
            "optimization_recommendations": dashboard_data.get(
                "recommendations", {}
            ),
        }

        return data_map.get(data_source, {})
