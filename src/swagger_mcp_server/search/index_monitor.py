"""Index performance monitoring for the Swagger MCP Server.

This module provides comprehensive monitoring of search index performance,
optimization tracking, and capacity planning as specified in Story 3.6.
"""

import asyncio
import os
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import psutil

from ..config.settings import SearchConfig


@dataclass
class IndexMetrics:
    """Comprehensive index performance metrics."""

    # Size and storage metrics
    index_size_bytes: int
    index_size_mb: float
    document_count: int
    field_count: int

    # Performance metrics
    query_time_ms: float
    update_time_ms: float
    optimization_time_ms: Optional[float]

    # Health metrics
    fragmentation_ratio: float
    cache_hit_rate: float
    disk_io_rate: float

    # Capacity metrics
    storage_utilization: float
    memory_usage_mb: float
    cpu_usage_percent: float

    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class IndexOptimizationEvent:
    """Records index optimization operations."""

    event_id: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]

    # Before optimization
    size_before_mb: float
    fragmentation_before: float
    query_time_before_ms: float

    # After optimization
    size_after_mb: Optional[float]
    fragmentation_after: Optional[float]
    query_time_after_ms: Optional[float]

    # Optimization results
    size_reduction_percent: Optional[float]
    performance_improvement_percent: Optional[float]
    success: bool = False
    error_message: Optional[str] = None


@dataclass
class IndexGrowthProjection:
    """Index growth projections for capacity planning."""

    current_size_mb: float
    projected_size_mb: float
    projection_period_days: int

    current_document_count: int
    projected_document_count: int

    growth_rate_mb_per_day: float
    growth_rate_documents_per_day: float

    estimated_full_date: Optional[datetime]
    recommended_actions: List[str] = field(default_factory=list)


class IndexPerformanceMonitor:
    """Monitors search index performance and provides optimization insights."""

    def __init__(self, index_path: str, config: SearchConfig):
        """Initialize index performance monitor.

        Args:
            index_path: Path to the search index directory
            config: Search configuration settings
        """
        self.index_path = index_path
        self.config = config

        # Historical metrics storage
        self.metrics_history: deque = deque(
            maxlen=1440
        )  # 24 hours of minute-by-minute data
        self.optimization_events: List[IndexOptimizationEvent] = []

        # Performance thresholds
        self.thresholds = {
            "max_query_time_ms": 100,
            "max_fragmentation_ratio": 0.3,
            "min_cache_hit_rate": 0.7,
            "max_storage_utilization": 0.8,
            "max_memory_usage_mb": 512,
            "optimization_trigger_fragmentation": 0.2,
        }

        # Current state
        self.last_optimization: Optional[datetime] = None
        self.optimization_in_progress = False

    async def collect_index_metrics(self) -> IndexMetrics:
        """Collect comprehensive index performance metrics.

        Returns:
            IndexMetrics: Current index performance metrics
        """
        # Collect basic index statistics
        index_stats = await self._get_index_statistics()

        # Measure query performance
        query_time = await self._measure_query_performance()

        # Measure update performance
        update_time = await self._measure_update_performance()

        # Calculate fragmentation
        fragmentation = await self._calculate_fragmentation()

        # Get cache statistics
        cache_hit_rate = await self._get_cache_hit_rate()

        # Get system resource usage
        resource_usage = await self._get_resource_usage()

        metrics = IndexMetrics(
            index_size_bytes=index_stats["size_bytes"],
            index_size_mb=index_stats["size_bytes"] / (1024 * 1024),
            document_count=index_stats["document_count"],
            field_count=index_stats["field_count"],
            query_time_ms=query_time,
            update_time_ms=update_time,
            optimization_time_ms=None,  # Set during optimization
            fragmentation_ratio=fragmentation,
            cache_hit_rate=cache_hit_rate,
            disk_io_rate=resource_usage["disk_io_rate"],
            storage_utilization=resource_usage["storage_utilization"],
            memory_usage_mb=resource_usage["memory_usage_mb"],
            cpu_usage_percent=resource_usage["cpu_usage_percent"],
        )

        # Store metrics
        self.metrics_history.append(metrics)

        # Check for optimization triggers
        await self._check_optimization_triggers(metrics)

        return metrics

    async def _get_index_statistics(self) -> Dict[str, Any]:
        """Get basic index statistics."""
        try:
            if not os.path.exists(self.index_path):
                return {"size_bytes": 0, "document_count": 0, "field_count": 0}

            # Calculate total size of index directory
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(self.index_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)

            # For a real implementation, these would come from the search engine
            # This is a placeholder implementation
            document_count = self._estimate_document_count(total_size)
            field_count = 10  # Placeholder

            return {
                "size_bytes": total_size,
                "document_count": document_count,
                "field_count": field_count,
            }

        except Exception as e:
            # Return default values on error
            return {"size_bytes": 0, "document_count": 0, "field_count": 0}

    def _estimate_document_count(self, index_size_bytes: int) -> int:
        """Estimate document count based on index size."""
        # Rough estimation: assume ~1KB per document on average
        if index_size_bytes == 0:
            return 0
        return max(1, index_size_bytes // 1024)

    async def _measure_query_performance(self) -> float:
        """Measure average query performance."""
        # This would integrate with the actual search engine
        # For now, simulate with a small delay and return estimated time
        start_time = time.time()

        # Simulate query execution
        await asyncio.sleep(0.001)  # 1ms simulated query

        query_time = (time.time() - start_time) * 1000

        # Add some realistic variation based on index size
        if hasattr(self, "metrics_history") and self.metrics_history:
            last_metrics = self.metrics_history[-1]
            size_factor = min(last_metrics.index_size_mb / 100, 2.0)  # Scale with size
            query_time *= 1 + size_factor * 0.1

        return query_time

    async def _measure_update_performance(self) -> float:
        """Measure index update performance."""
        # This would measure actual index update operations
        # For now, return an estimated value
        base_update_time = 5.0  # 5ms base update time

        # Scale with index size
        if hasattr(self, "metrics_history") and self.metrics_history:
            last_metrics = self.metrics_history[-1]
            size_factor = last_metrics.index_size_mb / 100
            base_update_time *= 1 + size_factor * 0.2

        return base_update_time

    async def _calculate_fragmentation(self) -> float:
        """Calculate index fragmentation ratio."""
        # This would analyze actual index structure
        # For now, simulate fragmentation based on time since last optimization

        if self.last_optimization:
            time_since_optimization = datetime.now() - self.last_optimization
            days_since = time_since_optimization.total_seconds() / (24 * 3600)

            # Fragmentation increases over time
            fragmentation = min(0.05 + (days_since * 0.02), 0.5)
        else:
            # No optimization recorded, assume some fragmentation
            fragmentation = 0.15

        return fragmentation

    async def _get_cache_hit_rate(self) -> float:
        """Get cache hit rate for search operations."""
        # This would integrate with actual caching system
        # For now, simulate a reasonable hit rate
        base_hit_rate = 0.75

        # Hit rate might decrease with high fragmentation
        if hasattr(self, "metrics_history") and self.metrics_history:
            last_metrics = self.metrics_history[-1]
            if hasattr(last_metrics, "fragmentation_ratio"):
                fragmentation_penalty = last_metrics.fragmentation_ratio * 0.3
                base_hit_rate = max(0.3, base_hit_rate - fragmentation_penalty)

        return base_hit_rate

    async def _get_resource_usage(self) -> Dict[str, float]:
        """Get system resource usage metrics."""
        try:
            # Get current process
            process = psutil.Process()

            # Memory usage
            memory_info = process.memory_info()
            memory_usage_mb = memory_info.rss / (1024 * 1024)

            # CPU usage
            cpu_percent = process.cpu_percent()

            # Disk I/O (simplified)
            disk_io = process.io_counters()
            disk_io_rate = (disk_io.read_bytes + disk_io.write_bytes) / (
                1024 * 1024
            )  # MB

            # Storage utilization for index directory
            if os.path.exists(self.index_path):
                disk_usage = psutil.disk_usage(self.index_path)
                storage_utilization = disk_usage.used / disk_usage.total
            else:
                storage_utilization = 0.0

            return {
                "memory_usage_mb": memory_usage_mb,
                "cpu_usage_percent": cpu_percent,
                "disk_io_rate": disk_io_rate,
                "storage_utilization": storage_utilization,
            }

        except Exception:
            # Return default values on error
            return {
                "memory_usage_mb": 0.0,
                "cpu_usage_percent": 0.0,
                "disk_io_rate": 0.0,
                "storage_utilization": 0.0,
            }

    async def _check_optimization_triggers(self, metrics: IndexMetrics) -> None:
        """Check if index optimization should be triggered."""
        if self.optimization_in_progress:
            return

        # Trigger optimization based on fragmentation
        if (
            metrics.fragmentation_ratio
            > self.thresholds["optimization_trigger_fragmentation"]
        ):
            await self._trigger_optimization("high_fragmentation")

        # Trigger optimization based on query performance
        elif metrics.query_time_ms > self.thresholds["max_query_time_ms"] * 2:
            await self._trigger_optimization("poor_performance")

        # Trigger optimization based on time since last optimization
        elif self.last_optimization:
            time_since = datetime.now() - self.last_optimization
            if time_since > timedelta(days=7):  # Weekly optimization
                await self._trigger_optimization("scheduled")

    async def _trigger_optimization(self, reason: str) -> str:
        """Trigger index optimization operation.

        Args:
            reason: Reason for triggering optimization

        Returns:
            str: Optimization event ID
        """
        if self.optimization_in_progress:
            raise RuntimeError("Optimization already in progress")

        event_id = f"opt_{int(time.time())}"
        current_metrics = self.metrics_history[-1] if self.metrics_history else None

        if not current_metrics:
            raise RuntimeError("No current metrics available for optimization")

        # Create optimization event
        optimization_event = IndexOptimizationEvent(
            event_id=event_id,
            start_time=datetime.now(),
            end_time=None,
            duration_ms=None,
            size_before_mb=current_metrics.index_size_mb,
            fragmentation_before=current_metrics.fragmentation_ratio,
            query_time_before_ms=current_metrics.query_time_ms,
            size_after_mb=None,
            fragmentation_after=None,
            query_time_after_ms=None,
            size_reduction_percent=None,
            performance_improvement_percent=None,
        )

        self.optimization_events.append(optimization_event)
        self.optimization_in_progress = True

        try:
            # Perform optimization (this would call actual optimization logic)
            await self._perform_optimization(optimization_event)

            optimization_event.success = True
            self.last_optimization = datetime.now()

        except Exception as e:
            optimization_event.success = False
            optimization_event.error_message = str(e)

        finally:
            self.optimization_in_progress = False
            optimization_event.end_time = datetime.now()

            if optimization_event.start_time and optimization_event.end_time:
                duration = optimization_event.end_time - optimization_event.start_time
                optimization_event.duration_ms = duration.total_seconds() * 1000

        return event_id

    async def _perform_optimization(self, event: IndexOptimizationEvent) -> None:
        """Perform the actual index optimization."""
        # Simulate optimization work
        await asyncio.sleep(2.0)  # 2 second optimization

        # Collect post-optimization metrics
        post_metrics = await self.collect_index_metrics()

        # Update optimization event with results
        event.size_after_mb = post_metrics.index_size_mb
        event.fragmentation_after = post_metrics.fragmentation_ratio
        event.query_time_after_ms = post_metrics.query_time_ms

        # Calculate improvements
        if event.size_before_mb > 0:
            event.size_reduction_percent = (
                (event.size_before_mb - event.size_after_mb)
                / event.size_before_mb
                * 100
            )

        if event.query_time_before_ms > 0:
            event.performance_improvement_percent = (
                (event.query_time_before_ms - event.query_time_after_ms)
                / event.query_time_before_ms
                * 100
            )

    async def get_performance_summary(self, time_period: str = "24h") -> Dict[str, Any]:
        """Get index performance summary for specified period.

        Args:
            time_period: Time period (1h, 6h, 24h, 7d)

        Returns:
            Dict containing performance summary
        """
        cutoff_time = self._get_cutoff_time(time_period)
        relevant_metrics = [
            m for m in self.metrics_history if m.timestamp >= cutoff_time
        ]

        if not relevant_metrics:
            return {"error": "No metrics available for specified period"}

        # Calculate summary statistics
        summary = {
            "time_period": time_period,
            "metrics_count": len(relevant_metrics),
            "index_size": self._calculate_size_stats(relevant_metrics),
            "performance": self._calculate_performance_stats(relevant_metrics),
            "resource_usage": self._calculate_resource_stats(relevant_metrics),
            "health": self._calculate_health_stats(relevant_metrics),
            "optimization": self._get_optimization_summary(),
            "alerts": self._get_performance_alerts(relevant_metrics),
            "recommendations": await self._generate_index_recommendations(
                relevant_metrics
            ),
        }

        return summary

    def _calculate_size_stats(self, metrics: List[IndexMetrics]) -> Dict[str, Any]:
        """Calculate index size statistics."""
        sizes_mb = [m.index_size_mb for m in metrics]
        doc_counts = [m.document_count for m in metrics]

        return {
            "current_size_mb": sizes_mb[-1] if sizes_mb else 0,
            "avg_size_mb": statistics.mean(sizes_mb) if sizes_mb else 0,
            "size_growth_mb": sizes_mb[-1] - sizes_mb[0] if len(sizes_mb) > 1 else 0,
            "current_documents": doc_counts[-1] if doc_counts else 0,
            "document_growth": (
                doc_counts[-1] - doc_counts[0] if len(doc_counts) > 1 else 0
            ),
            "avg_size_per_document_kb": (
                (sizes_mb[-1] * 1024 / max(doc_counts[-1], 1)) if doc_counts else 0
            ),
        }

    def _calculate_performance_stats(
        self, metrics: List[IndexMetrics]
    ) -> Dict[str, Any]:
        """Calculate performance statistics."""
        query_times = [m.query_time_ms for m in metrics]
        update_times = [m.update_time_ms for m in metrics]

        return {
            "avg_query_time_ms": statistics.mean(query_times) if query_times else 0,
            "p95_query_time_ms": (
                statistics.quantiles(query_times, n=20)[18]
                if len(query_times) > 20
                else max(query_times) if query_times else 0
            ),
            "max_query_time_ms": max(query_times) if query_times else 0,
            "avg_update_time_ms": statistics.mean(update_times) if update_times else 0,
            "query_time_trend": self._calculate_trend(query_times),
            "nfr_compliance_percent": (
                len([t for t in query_times if t <= 100]) / len(query_times) * 100
                if query_times
                else 0
            ),
        }

    def _calculate_resource_stats(self, metrics: List[IndexMetrics]) -> Dict[str, Any]:
        """Calculate resource usage statistics."""
        memory_usage = [m.memory_usage_mb for m in metrics]
        cpu_usage = [m.cpu_usage_percent for m in metrics]
        storage_usage = [m.storage_utilization for m in metrics]

        return {
            "avg_memory_mb": statistics.mean(memory_usage) if memory_usage else 0,
            "max_memory_mb": max(memory_usage) if memory_usage else 0,
            "avg_cpu_percent": statistics.mean(cpu_usage) if cpu_usage else 0,
            "max_cpu_percent": max(cpu_usage) if cpu_usage else 0,
            "current_storage_utilization": storage_usage[-1] if storage_usage else 0,
            "storage_trend": self._calculate_trend(storage_usage),
        }

    def _calculate_health_stats(self, metrics: List[IndexMetrics]) -> Dict[str, Any]:
        """Calculate index health statistics."""
        fragmentation = [m.fragmentation_ratio for m in metrics]
        cache_hits = [m.cache_hit_rate for m in metrics]

        current_fragmentation = fragmentation[-1] if fragmentation else 0
        current_cache_rate = cache_hits[-1] if cache_hits else 0

        # Determine health score
        health_score = 100
        if (
            current_fragmentation
            > self.thresholds["optimization_trigger_fragmentation"]
        ):
            health_score -= 30
        if current_cache_rate < self.thresholds["min_cache_hit_rate"]:
            health_score -= 20

        avg_query_time = (
            statistics.mean([m.query_time_ms for m in metrics]) if metrics else 0
        )
        if avg_query_time > self.thresholds["max_query_time_ms"]:
            health_score -= 25

        health_score = max(0, health_score)

        # Determine health status
        if health_score >= 80:
            health_status = "excellent"
        elif health_score >= 60:
            health_status = "good"
        elif health_score >= 40:
            health_status = "fair"
        else:
            health_status = "poor"

        return {
            "health_score": health_score,
            "health_status": health_status,
            "current_fragmentation": current_fragmentation,
            "fragmentation_trend": self._calculate_trend(fragmentation),
            "current_cache_hit_rate": current_cache_rate,
            "cache_performance_trend": self._calculate_trend(cache_hits),
        }

    def _get_optimization_summary(self) -> Dict[str, Any]:
        """Get optimization operation summary."""
        recent_optimizations = [
            opt
            for opt in self.optimization_events
            if opt.start_time >= datetime.now() - timedelta(days=30)
        ]

        successful_opts = [opt for opt in recent_optimizations if opt.success]

        return {
            "total_optimizations": len(recent_optimizations),
            "successful_optimizations": len(successful_opts),
            "last_optimization": (
                self.last_optimization.isoformat() if self.last_optimization else None
            ),
            "optimization_in_progress": self.optimization_in_progress,
            "avg_optimization_time_ms": (
                statistics.mean(
                    [opt.duration_ms for opt in successful_opts if opt.duration_ms]
                )
                if successful_opts
                else 0
            ),
            "avg_size_reduction_percent": (
                statistics.mean(
                    [
                        opt.size_reduction_percent
                        for opt in successful_opts
                        if opt.size_reduction_percent
                    ]
                )
                if successful_opts
                else 0
            ),
            "avg_performance_improvement_percent": (
                statistics.mean(
                    [
                        opt.performance_improvement_percent
                        for opt in successful_opts
                        if opt.performance_improvement_percent
                    ]
                )
                if successful_opts
                else 0
            ),
        }

    def _get_performance_alerts(
        self, metrics: List[IndexMetrics]
    ) -> List[Dict[str, Any]]:
        """Get performance alerts based on current metrics."""
        alerts = []

        if not metrics:
            return alerts

        current = metrics[-1]

        # Query performance alert
        if current.query_time_ms > self.thresholds["max_query_time_ms"]:
            alerts.append(
                {
                    "level": (
                        "warning"
                        if current.query_time_ms
                        < self.thresholds["max_query_time_ms"] * 2
                        else "critical"
                    ),
                    "type": "performance",
                    "message": f"Query time ({current.query_time_ms:.1f}ms) exceeds threshold ({self.thresholds['max_query_time_ms']}ms)",
                    "value": current.query_time_ms,
                    "threshold": self.thresholds["max_query_time_ms"],
                }
            )

        # Fragmentation alert
        if (
            current.fragmentation_ratio
            > self.thresholds["optimization_trigger_fragmentation"]
        ):
            alerts.append(
                {
                    "level": "warning",
                    "type": "fragmentation",
                    "message": f"Index fragmentation ({current.fragmentation_ratio:.1%}) suggests optimization needed",
                    "value": current.fragmentation_ratio,
                    "threshold": self.thresholds["optimization_trigger_fragmentation"],
                }
            )

        # Cache performance alert
        if current.cache_hit_rate < self.thresholds["min_cache_hit_rate"]:
            alerts.append(
                {
                    "level": "warning",
                    "type": "cache",
                    "message": f"Cache hit rate ({current.cache_hit_rate:.1%}) below optimal threshold",
                    "value": current.cache_hit_rate,
                    "threshold": self.thresholds["min_cache_hit_rate"],
                }
            )

        # Storage utilization alert
        if current.storage_utilization > self.thresholds["max_storage_utilization"]:
            alerts.append(
                {
                    "level": (
                        "critical" if current.storage_utilization > 0.9 else "warning"
                    ),
                    "type": "storage",
                    "message": f"Storage utilization ({current.storage_utilization:.1%}) approaching capacity",
                    "value": current.storage_utilization,
                    "threshold": self.thresholds["max_storage_utilization"],
                }
            )

        return alerts

    async def _generate_index_recommendations(
        self, metrics: List[IndexMetrics]
    ) -> List[Dict[str, Any]]:
        """Generate index optimization recommendations."""
        recommendations = []

        if not metrics:
            return recommendations

        current = metrics[-1]

        # Optimization recommendation
        if (
            current.fragmentation_ratio
            > self.thresholds["optimization_trigger_fragmentation"]
        ):
            recommendations.append(
                {
                    "priority": "high",
                    "type": "optimization",
                    "title": "Schedule Index Optimization",
                    "description": f"Current fragmentation ({current.fragmentation_ratio:.1%}) suggests optimization would improve performance",
                    "expected_benefit": "15-30% query performance improvement",
                    "estimated_duration": "2-5 minutes",
                }
            )

        # Cache improvement recommendation
        if current.cache_hit_rate < self.thresholds["min_cache_hit_rate"]:
            recommendations.append(
                {
                    "priority": "medium",
                    "type": "caching",
                    "title": "Improve Cache Configuration",
                    "description": "Low cache hit rate suggests cache size or strategy optimization needed",
                    "expected_benefit": "10-20% query performance improvement",
                    "actions": [
                        "Increase cache size",
                        "Review cache eviction policy",
                    ],
                }
            )

        # Storage capacity recommendation
        if current.storage_utilization > 0.7:
            recommendations.append(
                {
                    "priority": (
                        "medium" if current.storage_utilization < 0.85 else "high"
                    ),
                    "type": "capacity",
                    "title": "Monitor Storage Capacity",
                    "description": f"Storage utilization ({current.storage_utilization:.1%}) requires attention",
                    "actions": [
                        "Monitor growth trends",
                        "Plan storage expansion",
                        "Implement data archiving",
                    ],
                }
            )

        # Performance tuning recommendation
        avg_query_time = (
            statistics.mean([m.query_time_ms for m in metrics]) if metrics else 0
        )
        if avg_query_time > self.thresholds["max_query_time_ms"]:
            recommendations.append(
                {
                    "priority": "medium",
                    "type": "performance",
                    "title": "Query Performance Tuning",
                    "description": f"Average query time ({avg_query_time:.1f}ms) exceeds target",
                    "actions": [
                        "Analyze slow queries",
                        "Optimize index structure",
                        "Review query patterns",
                    ],
                }
            )

        return recommendations

    async def project_index_growth(
        self, projection_days: int = 30
    ) -> IndexGrowthProjection:
        """Project index growth for capacity planning.

        Args:
            projection_days: Number of days to project forward

        Returns:
            IndexGrowthProjection: Growth projection data
        """
        if len(self.metrics_history) < 2:
            # Not enough data for projection
            current = self.metrics_history[-1] if self.metrics_history else None
            if current:
                return IndexGrowthProjection(
                    current_size_mb=current.index_size_mb,
                    projected_size_mb=current.index_size_mb,
                    projection_period_days=projection_days,
                    current_document_count=current.document_count,
                    projected_document_count=current.document_count,
                    growth_rate_mb_per_day=0,
                    growth_rate_documents_per_day=0,
                    estimated_full_date=None,
                    recommended_actions=["Collect more data for accurate projections"],
                )

        # Calculate growth rates from recent data
        recent_metrics = list(self.metrics_history)[
            -min(7, len(self.metrics_history)) :
        ]  # Last week

        if len(recent_metrics) < 2:
            current = recent_metrics[0]
            return IndexGrowthProjection(
                current_size_mb=current.index_size_mb,
                projected_size_mb=current.index_size_mb,
                projection_period_days=projection_days,
                current_document_count=current.document_count,
                projected_document_count=current.document_count,
                growth_rate_mb_per_day=0,
                growth_rate_documents_per_day=0,
                estimated_full_date=None,
            )

        # Calculate linear growth rate
        first_metric = recent_metrics[0]
        last_metric = recent_metrics[-1]

        time_diff_days = (
            last_metric.timestamp - first_metric.timestamp
        ).total_seconds() / (24 * 3600)

        if time_diff_days > 0:
            size_growth_rate = (
                last_metric.index_size_mb - first_metric.index_size_mb
            ) / time_diff_days
            doc_growth_rate = (
                last_metric.document_count - first_metric.document_count
            ) / time_diff_days
        else:
            size_growth_rate = 0
            doc_growth_rate = 0

        # Project future values
        projected_size_mb = last_metric.index_size_mb + (
            size_growth_rate * projection_days
        )
        projected_document_count = last_metric.document_count + int(
            doc_growth_rate * projection_days
        )

        # Estimate when storage might be full (assuming 80% utilization threshold)
        estimated_full_date = None
        if size_growth_rate > 0 and last_metric.storage_utilization > 0:
            # Rough calculation based on current storage usage
            available_storage_mb = (
                last_metric.index_size_mb / last_metric.storage_utilization
            ) * (1 - 0.8)
            if available_storage_mb > 0:
                days_to_full = available_storage_mb / size_growth_rate
                estimated_full_date = datetime.now() + timedelta(days=days_to_full)

        # Generate recommendations
        recommendations = []
        if projected_size_mb > last_metric.index_size_mb * 1.5:
            recommendations.append("Consider storage capacity planning")
        if doc_growth_rate > 1000:  # More than 1000 docs per day
            recommendations.append(
                "Monitor indexing performance under high document volume"
            )
        if size_growth_rate > 50:  # More than 50MB per day
            recommendations.append("Implement data archiving strategy")

        return IndexGrowthProjection(
            current_size_mb=last_metric.index_size_mb,
            projected_size_mb=projected_size_mb,
            projection_period_days=projection_days,
            current_document_count=last_metric.document_count,
            projected_document_count=projected_document_count,
            growth_rate_mb_per_day=size_growth_rate,
            growth_rate_documents_per_day=doc_growth_rate,
            estimated_full_date=estimated_full_date,
            recommended_actions=recommendations,
        )

    # Helper methods

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
            return now - timedelta(hours=24)  # Default to 24 hours

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from values."""
        if len(values) < 2:
            return "stable"

        # Simple trend calculation
        first_half = values[: len(values) // 2]
        second_half = values[len(values) // 2 :]

        if not first_half or not second_half:
            return "stable"

        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)

        change_percent = abs(second_avg - first_avg) / max(first_avg, 0.001) * 100

        if change_percent < 5:
            return "stable"
        elif second_avg > first_avg:
            return "increasing"
        else:
            return "decreasing"
