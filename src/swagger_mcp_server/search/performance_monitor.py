"""Search performance monitoring and analytics for the Swagger MCP Server.

This module provides comprehensive search performance monitoring, metrics collection,
and analytics capabilities as specified in Story 3.6.
"""

import asyncio
import statistics
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..config.settings import SearchConfig


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SearchOperationType(Enum):
    """Types of search operations being monitored."""

    ENDPOINT_SEARCH = "endpoint_search"
    SCHEMA_SEARCH = "schema_search"
    UNIFIED_SEARCH = "unified_search"
    INDEX_QUERY = "index_query"
    RESULT_PROCESSING = "result_processing"


@dataclass
class SearchAnalytics:
    """Comprehensive search analytics data structure."""

    # Query information
    query_text: str
    search_type: str  # 'endpoint', 'schema', 'unified'
    filters_applied: Dict[str, Any]
    query_processing_time: float  # milliseconds

    # Performance metrics
    total_response_time: float  # milliseconds
    index_query_time: float  # milliseconds
    result_processing_time: float  # milliseconds
    result_count: int

    # Result interaction
    results_clicked: List[str] = field(default_factory=list)
    user_satisfaction: Optional[int] = None  # 1-5 rating if available
    query_abandoned: bool = False

    # Context information
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: str = ""
    user_session: Optional[str] = None

    # Performance classification
    performance_grade: str = "unknown"  # excellent, good, acceptable, poor
    exceeded_threshold: bool = False

    # Additional metrics
    cache_hit: bool = False
    index_size_at_query: Optional[int] = None
    concurrent_queries: int = 0


@dataclass
class PerformanceAlert:
    """Performance alert information."""

    alert_id: str
    level: AlertLevel
    title: str
    description: str
    metric_value: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution_time: Optional[datetime] = None


class SearchPerformanceMonitor:
    """Monitors and analyzes search performance with comprehensive metrics."""

    def __init__(self, config: SearchConfig):
        """Initialize the search performance monitor.

        Args:
            config: Search configuration with performance settings
        """
        self.config = config
        self.analytics_data: deque = deque(maxlen=10000)  # Keep last 10k queries
        self.performance_thresholds = {
            "response_time_warning": 150,  # ms
            "response_time_critical": 300,  # ms
            "response_time_excellent": 50,  # ms
            "response_time_good": 100,  # ms
            "result_count_minimum": 1,
            "cache_hit_rate_warning": 0.4,
            "index_query_time_warning": 100,  # ms
        }

        # Real-time metrics
        self.current_metrics = {
            "active_queries": 0,
            "total_queries_today": 0,
            "avg_response_time_hour": 0.0,
            "cache_hit_rate_hour": 0.0,
            "error_rate_hour": 0.0,
        }

        # Performance alerts
        self.alerts: List[PerformanceAlert] = []
        self.alert_callbacks: List[Callable] = []

        # Concurrent query tracking
        self.active_queries: Dict[str, datetime] = {}

    async def monitor_search_operation(
        self, search_func: Callable, *args, **kwargs
    ) -> Any:
        """Monitor search operation with comprehensive metrics collection.

        Args:
            search_func: Search function to monitor
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Search results with performance monitoring

        Raises:
            Exception: Re-raises any exceptions from the search function
        """
        correlation_id = self._generate_correlation_id()
        start_time = time.time()

        # Track concurrent queries
        self.active_queries[correlation_id] = datetime.now()
        self.current_metrics["active_queries"] = len(self.active_queries)

        try:
            # Execute search with detailed timing
            timing_info = {}

            # Query processing timing
            query_start = time.time()
            if (
                hasattr(search_func, "__name__")
                and "process_query" in search_func.__name__
            ):
                processed_query = await search_func(*args, **kwargs)
                timing_info["query_processing"] = (time.time() - query_start) * 1000
                result = processed_query
            else:
                # For full search operations
                result = await search_func(*args, **kwargs)
                timing_info["query_processing"] = 0  # Will be calculated separately

            total_time = (time.time() - start_time) * 1000

            # Determine cache hit
            cache_hit = self._determine_cache_hit(result)

            # Create analytics record
            analytics = SearchAnalytics(
                query_text=kwargs.get("query", str(args[0] if args else "")),
                search_type=kwargs.get("search_type", "unknown"),
                filters_applied=kwargs.get("filters", {}),
                query_processing_time=timing_info.get("query_processing", 0),
                total_response_time=total_time,
                index_query_time=timing_info.get(
                    "index_query", total_time * 0.6
                ),  # Estimate
                result_processing_time=timing_info.get(
                    "result_processing", total_time * 0.2
                ),  # Estimate
                result_count=self._extract_result_count(result),
                correlation_id=correlation_id,
                performance_grade=self._classify_performance(total_time),
                exceeded_threshold=total_time
                > self.performance_thresholds["response_time_warning"],
                cache_hit=cache_hit,
                concurrent_queries=len(self.active_queries),
            )

            # Store analytics and check performance
            await self._record_analytics(analytics)
            await self._check_performance_thresholds(analytics)
            await self._update_real_time_metrics(analytics)

            return result

        except Exception as e:
            # Record failed search analytics
            await self._record_search_failure(
                correlation_id, str(e), (time.time() - start_time) * 1000
            )
            raise
        finally:
            # Remove from active queries
            self.active_queries.pop(correlation_id, None)
            self.current_metrics["active_queries"] = len(self.active_queries)

    async def get_performance_summary(self, time_period: str = "1h") -> Dict[str, Any]:
        """Get comprehensive performance summary for specified time period.

        Args:
            time_period: Time period (1h, 6h, 24h, 7d)

        Returns:
            Dict containing performance summary
        """
        cutoff_time = self._get_cutoff_time(time_period)
        relevant_data = [a for a in self.analytics_data if a.timestamp >= cutoff_time]

        if not relevant_data:
            return self._empty_performance_summary()

        summary = {
            "time_period": time_period,
            "total_queries": len(relevant_data),
            "response_time_metrics": self._calculate_response_time_metrics(
                relevant_data
            ),
            "query_volume_metrics": self._calculate_query_volume_metrics(relevant_data),
            "search_effectiveness": self._calculate_search_effectiveness(relevant_data),
            "performance_trends": self._calculate_performance_trends(relevant_data),
            "cache_performance": self._calculate_cache_performance(relevant_data),
            "concurrent_usage": self._calculate_concurrent_usage_metrics(relevant_data),
            "optimization_recommendations": await self._generate_optimization_recommendations(
                relevant_data
            ),
            "current_metrics": self.current_metrics,
            "active_alerts": [a for a in self.alerts if not a.resolved],
        }

        return summary

    def _calculate_response_time_metrics(
        self, analytics_data: List[SearchAnalytics]
    ) -> Dict[str, float]:
        """Calculate detailed response time metrics."""
        if not analytics_data:
            return {"avg": 0, "p50": 0, "p95": 0, "p99": 0, "min": 0, "max": 0}

        response_times = [a.total_response_time for a in analytics_data]
        response_times.sort()
        count = len(response_times)

        return {
            "avg": statistics.mean(response_times),
            "median": statistics.median(response_times),
            "p50": response_times[int(count * 0.5)],
            "p95": response_times[int(count * 0.95)]
            if count > 20
            else response_times[-1],
            "p99": response_times[int(count * 0.99)]
            if count > 100
            else response_times[-1],
            "min": min(response_times),
            "max": max(response_times),
            "std_dev": statistics.stdev(response_times) if count > 1 else 0,
            "nfr1_compliance": len([t for t in response_times if t <= 200])
            / count
            * 100,
        }

    def _calculate_query_volume_metrics(
        self, analytics_data: List[SearchAnalytics]
    ) -> Dict[str, Any]:
        """Calculate query volume and pattern metrics."""
        total_queries = len(analytics_data)

        # Group by hour for volume analysis
        hourly_volume = defaultdict(int)
        query_types = defaultdict(int)
        filter_usage = defaultdict(int)

        for analytics in analytics_data:
            hour_key = analytics.timestamp.strftime("%Y-%m-%d %H:00")
            hourly_volume[hour_key] += 1
            query_types[analytics.search_type] += 1

            for filter_key in analytics.filters_applied.keys():
                filter_usage[filter_key] += 1

        return {
            "total_queries": total_queries,
            "avg_queries_per_hour": total_queries / max(len(hourly_volume), 1),
            "peak_hour_volume": max(hourly_volume.values()) if hourly_volume else 0,
            "query_type_distribution": dict(query_types),
            "popular_filters": dict(
                sorted(filter_usage.items(), key=lambda x: x[1], reverse=True)[:5]
            ),
            "hourly_volume": dict(hourly_volume),
        }

    def _calculate_search_effectiveness(
        self, analytics_data: List[SearchAnalytics]
    ) -> Dict[str, Any]:
        """Calculate search effectiveness and user satisfaction metrics."""
        if not analytics_data:
            return {"success_rate": 0, "avg_results": 0, "zero_result_rate": 0}

        successful_searches = [a for a in analytics_data if a.result_count > 0]
        zero_result_searches = [a for a in analytics_data if a.result_count == 0]
        abandoned_searches = [a for a in analytics_data if a.query_abandoned]

        return {
            "success_rate": len(successful_searches) / len(analytics_data) * 100,
            "zero_result_rate": len(zero_result_searches) / len(analytics_data) * 100,
            "abandonment_rate": len(abandoned_searches) / len(analytics_data) * 100,
            "avg_results_per_query": statistics.mean(
                [a.result_count for a in analytics_data]
            ),
            "median_results_per_query": statistics.median(
                [a.result_count for a in analytics_data]
            ),
            "performance_grade_distribution": self._calculate_performance_grade_distribution(
                analytics_data
            ),
            "user_satisfaction": self._calculate_user_satisfaction(analytics_data),
        }

    def _calculate_performance_trends(
        self, analytics_data: List[SearchAnalytics]
    ) -> Dict[str, Any]:
        """Calculate performance trends over time."""
        if len(analytics_data) < 10:
            return {"trend": "insufficient_data"}

        # Sort by timestamp
        sorted_data = sorted(analytics_data, key=lambda x: x.timestamp)

        # Split into first half and second half
        midpoint = len(sorted_data) // 2
        first_half = sorted_data[:midpoint]
        second_half = sorted_data[midpoint:]

        first_half_avg = statistics.mean([a.total_response_time for a in first_half])
        second_half_avg = statistics.mean([a.total_response_time for a in second_half])

        trend_direction = (
            "improving" if second_half_avg < first_half_avg else "degrading"
        )
        trend_magnitude = abs(second_half_avg - first_half_avg) / first_half_avg * 100

        return {
            "trend_direction": trend_direction,
            "trend_magnitude_percent": trend_magnitude,
            "first_period_avg": first_half_avg,
            "second_period_avg": second_half_avg,
            "performance_stability": "stable" if trend_magnitude < 10 else "volatile",
        }

    def _calculate_cache_performance(
        self, analytics_data: List[SearchAnalytics]
    ) -> Dict[str, Any]:
        """Calculate cache performance metrics."""
        if not analytics_data:
            return {"hit_rate": 0, "effectiveness": "unknown"}

        cache_hits = len([a for a in analytics_data if a.cache_hit])
        total_queries = len(analytics_data)
        hit_rate = cache_hits / total_queries

        # Compare performance of cached vs non-cached queries
        cached_queries = [a for a in analytics_data if a.cache_hit]
        non_cached_queries = [a for a in analytics_data if not a.cache_hit]

        cached_avg_time = (
            statistics.mean([a.total_response_time for a in cached_queries])
            if cached_queries
            else 0
        )
        non_cached_avg_time = (
            statistics.mean([a.total_response_time for a in non_cached_queries])
            if non_cached_queries
            else 0
        )

        return {
            "hit_rate": hit_rate,
            "cache_hits": cache_hits,
            "total_queries": total_queries,
            "cached_avg_response_time": cached_avg_time,
            "non_cached_avg_response_time": non_cached_avg_time,
            "cache_effectiveness": "high"
            if hit_rate > 0.7
            else "medium"
            if hit_rate > 0.4
            else "low",
            "performance_improvement": max(0, non_cached_avg_time - cached_avg_time),
        }

    def _calculate_concurrent_usage_metrics(
        self, analytics_data: List[SearchAnalytics]
    ) -> Dict[str, Any]:
        """Calculate concurrent usage patterns."""
        if not analytics_data:
            return {"max_concurrent": 0, "avg_concurrent": 0}

        concurrent_counts = [a.concurrent_queries for a in analytics_data]

        return {
            "max_concurrent_queries": max(concurrent_counts),
            "avg_concurrent_queries": statistics.mean(concurrent_counts),
            "concurrent_distribution": self._calculate_distribution(
                concurrent_counts, [1, 5, 10, 25, 50]
            ),
        }

    async def _generate_optimization_recommendations(
        self, analytics_data: List[SearchAnalytics]
    ) -> List[Dict[str, Any]]:
        """Generate actionable optimization recommendations."""
        recommendations = []

        if not analytics_data:
            return recommendations

        # Analyze slow queries
        slow_queries = [
            a
            for a in analytics_data
            if a.total_response_time
            > self.performance_thresholds["response_time_warning"]
        ]
        if len(slow_queries) > len(analytics_data) * 0.1:  # >10% slow queries
            recommendations.append(
                {
                    "type": "performance",
                    "priority": "high",
                    "issue": "High percentage of slow queries detected",
                    "recommendation": "Optimize index structure and query processing pipeline",
                    "affected_queries": len(slow_queries),
                    "impact": "response_time_improvement",
                    "estimated_improvement": "20-40%",
                }
            )

        # Analyze cache performance
        cache_hit_rate = statistics.mean(
            [1 if a.cache_hit else 0 for a in analytics_data]
        )
        if cache_hit_rate < self.performance_thresholds["cache_hit_rate_warning"]:
            recommendations.append(
                {
                    "type": "caching",
                    "priority": "medium",
                    "issue": f"Low cache hit rate: {cache_hit_rate:.1%}",
                    "recommendation": "Improve cache strategy and increase cache size",
                    "current_hit_rate": cache_hit_rate,
                    "target_hit_rate": 0.7,
                    "estimated_improvement": "15-30%",
                }
            )

        # Analyze failed searches
        failed_searches = [a for a in analytics_data if a.result_count == 0]
        if len(failed_searches) > len(analytics_data) * 0.15:  # >15% failed searches
            common_failed_terms = self._analyze_common_failed_terms(failed_searches)
            recommendations.append(
                {
                    "type": "relevance",
                    "priority": "medium",
                    "issue": "High percentage of searches with no results",
                    "recommendation": "Improve query processing and index completeness",
                    "failure_rate": len(failed_searches) / len(analytics_data),
                    "common_failed_terms": common_failed_terms[:5],
                }
            )

        # Analyze index performance
        index_times = [
            a.index_query_time for a in analytics_data if a.index_query_time > 0
        ]
        if (
            index_times
            and statistics.mean(index_times)
            > self.performance_thresholds["index_query_time_warning"]
        ):
            recommendations.append(
                {
                    "type": "index",
                    "priority": "medium",
                    "issue": "Index query performance degradation detected",
                    "recommendation": "Consider index optimization or hardware upgrade",
                    "avg_index_time": statistics.mean(index_times),
                    "target_index_time": 50,
                    "estimated_improvement": "25-50%",
                }
            )

        # Analyze concurrent load issues
        concurrent_counts = [a.concurrent_queries for a in analytics_data]
        if max(concurrent_counts) > 20:
            high_concurrency_slow = [
                a
                for a in analytics_data
                if a.concurrent_queries > 10
                and a.total_response_time
                > self.performance_thresholds["response_time_warning"]
            ]
            if (
                len(high_concurrency_slow)
                > len([a for a in analytics_data if a.concurrent_queries > 10]) * 0.3
            ):
                recommendations.append(
                    {
                        "type": "scalability",
                        "priority": "high",
                        "issue": "Performance degradation under high concurrent load",
                        "recommendation": "Implement connection pooling and async processing",
                        "max_concurrent": max(concurrent_counts),
                        "degradation_threshold": 10,
                    }
                )

        return recommendations

    async def _record_analytics(self, analytics: SearchAnalytics) -> None:
        """Record analytics data with cleanup."""
        self.analytics_data.append(analytics)

        # Update daily counter
        self.current_metrics["total_queries_today"] += 1

    async def _check_performance_thresholds(self, analytics: SearchAnalytics) -> None:
        """Check performance against thresholds and generate alerts."""
        # Response time alerts
        if (
            analytics.total_response_time
            > self.performance_thresholds["response_time_critical"]
        ):
            await self._create_alert(
                AlertLevel.CRITICAL,
                "Critical Response Time",
                f"Query '{analytics.query_text}' took {analytics.total_response_time:.1f}ms (>{self.performance_thresholds['response_time_critical']}ms)",
                analytics.total_response_time,
                self.performance_thresholds["response_time_critical"],
            )
        elif (
            analytics.total_response_time
            > self.performance_thresholds["response_time_warning"]
        ):
            await self._create_alert(
                AlertLevel.WARNING,
                "Slow Response Time",
                f"Query '{analytics.query_text}' took {analytics.total_response_time:.1f}ms (>{self.performance_thresholds['response_time_warning']}ms)",
                analytics.total_response_time,
                self.performance_thresholds["response_time_warning"],
            )

    async def _update_real_time_metrics(self, analytics: SearchAnalytics) -> None:
        """Update real-time performance metrics."""
        # Get recent data for hourly averages
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_data = [a for a in self.analytics_data if a.timestamp >= one_hour_ago]

        if recent_data:
            self.current_metrics["avg_response_time_hour"] = statistics.mean(
                [a.total_response_time for a in recent_data]
            )
            self.current_metrics["cache_hit_rate_hour"] = statistics.mean(
                [1 if a.cache_hit else 0 for a in recent_data]
            )
            # Error rate would need error tracking implementation
            self.current_metrics["error_rate_hour"] = 0.0  # Placeholder

    async def _create_alert(
        self,
        level: AlertLevel,
        title: str,
        description: str,
        metric_value: float,
        threshold: float,
    ) -> None:
        """Create and store a performance alert."""
        alert = PerformanceAlert(
            alert_id=str(uuid.uuid4()),
            level=level,
            title=title,
            description=description,
            metric_value=metric_value,
            threshold=threshold,
        )

        self.alerts.append(alert)

        # Trigger alert callbacks
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception:
                pass  # Don't let callback failures affect monitoring

    # Helper methods

    def _generate_correlation_id(self) -> str:
        """Generate unique correlation ID for request tracking."""
        return str(uuid.uuid4())[:8]

    def _determine_cache_hit(self, result: Any) -> bool:
        """Determine if result came from cache."""
        # Implementation would depend on how cache is structured
        # This is a placeholder implementation
        if isinstance(result, dict):
            return result.get("from_cache", False)
        return False

    def _extract_result_count(self, result: Any) -> int:
        """Extract result count from search result."""
        if isinstance(result, dict):
            if "results" in result:
                return len(result["results"])
            elif "total_results" in result:
                return result["total_results"]
        return 0

    def _classify_performance(self, response_time: float) -> str:
        """Classify performance based on response time."""
        if response_time <= self.performance_thresholds["response_time_excellent"]:
            return "excellent"
        elif response_time <= self.performance_thresholds["response_time_good"]:
            return "good"
        elif response_time <= self.performance_thresholds["response_time_warning"]:
            return "acceptable"
        else:
            return "poor"

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
            return now - timedelta(hours=1)  # Default to 1 hour

    def _empty_performance_summary(self) -> Dict[str, Any]:
        """Return empty performance summary."""
        return {
            "time_period": "0",
            "total_queries": 0,
            "response_time_metrics": {"avg": 0, "p50": 0, "p95": 0, "p99": 0},
            "query_volume_metrics": {"total_queries": 0},
            "search_effectiveness": {"success_rate": 0},
            "performance_trends": {"trend": "no_data"},
            "optimization_recommendations": [],
        }

    def _calculate_performance_grade_distribution(
        self, analytics_data: List[SearchAnalytics]
    ) -> Dict[str, int]:
        """Calculate distribution of performance grades."""
        distribution = defaultdict(int)
        for analytics in analytics_data:
            distribution[analytics.performance_grade] += 1
        return dict(distribution)

    def _calculate_user_satisfaction(
        self, analytics_data: List[SearchAnalytics]
    ) -> Dict[str, Any]:
        """Calculate user satisfaction metrics."""
        satisfaction_scores = [
            a.user_satisfaction
            for a in analytics_data
            if a.user_satisfaction is not None
        ]

        if not satisfaction_scores:
            return {"avg_satisfaction": None, "satisfaction_count": 0}

        return {
            "avg_satisfaction": statistics.mean(satisfaction_scores),
            "satisfaction_count": len(satisfaction_scores),
            "satisfaction_distribution": self._calculate_distribution(
                satisfaction_scores, [1, 2, 3, 4, 5]
            ),
        }

    def _calculate_distribution(
        self, values: List[float], buckets: List[float]
    ) -> Dict[str, int]:
        """Calculate distribution of values across buckets."""
        distribution = {}
        for i, bucket in enumerate(buckets):
            if i == 0:
                count = len([v for v in values if v <= bucket])
                distribution[f"<={bucket}"] = count
            else:
                prev_bucket = buckets[i - 1]
                count = len([v for v in values if prev_bucket < v <= bucket])
                distribution[f"{prev_bucket}-{bucket}"] = count

        # Add count for values above highest bucket
        if buckets:
            highest = buckets[-1]
            count = len([v for v in values if v > highest])
            distribution[f">{highest}"] = count

        return distribution

    def _analyze_common_failed_terms(
        self, failed_searches: List[SearchAnalytics]
    ) -> List[str]:
        """Analyze common terms in failed searches."""
        term_counts = defaultdict(int)

        for analytics in failed_searches:
            terms = analytics.query_text.lower().split()
            for term in terms:
                if len(term) > 2:  # Ignore very short terms
                    term_counts[term] += 1

        return [
            term
            for term, count in sorted(
                term_counts.items(), key=lambda x: x[1], reverse=True
            )
        ]

    async def _record_search_failure(
        self, correlation_id: str, error: str, duration: float
    ) -> None:
        """Record search failure for analytics."""
        failure_analytics = SearchAnalytics(
            query_text="[FAILED]",
            search_type="error",
            filters_applied={},
            query_processing_time=0,
            total_response_time=duration,
            index_query_time=0,
            result_processing_time=0,
            result_count=0,
            correlation_id=correlation_id,
            performance_grade="error",
            exceeded_threshold=True,
        )

        await self._record_analytics(failure_analytics)

        # Create error alert
        await self._create_alert(
            AlertLevel.WARNING,
            "Search Operation Failed",
            f"Search failed with error: {error}",
            duration,
            0,
        )

    def add_alert_callback(self, callback: Callable) -> None:
        """Add callback function for alert notifications."""
        self.alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: Callable) -> None:
        """Remove alert callback function."""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)

    async def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        for alert in self.alerts:
            if alert.alert_id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolution_time = datetime.now()
                return True
        return False

    def get_active_alerts(self) -> List[PerformanceAlert]:
        """Get all active (unresolved) alerts."""
        return [alert for alert in self.alerts if not alert.resolved]

    def get_recent_alerts(self, hours: int = 24) -> List[PerformanceAlert]:
        """Get alerts from the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [alert for alert in self.alerts if alert.timestamp >= cutoff]
