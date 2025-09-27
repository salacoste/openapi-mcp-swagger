"""Comprehensive tests for search analytics and performance monitoring.

Tests cover all components of the search analytics system including performance
monitoring, analytics engine, index monitoring, and dashboard functionality.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from swagger_mcp_server.config.settings import (
    SearchConfig,
    SearchPerformanceConfig,
)
from swagger_mcp_server.search.analytics_dashboard import (
    SearchAnalyticsDashboard,
)
from swagger_mcp_server.search.analytics_engine import (
    QueryPattern,
    QueryPatternType,
    SearchAnalyticsEngine,
    UserBehaviorPattern,
    UserSession,
)
from swagger_mcp_server.search.index_monitor import (
    IndexMetrics,
    IndexOptimizationEvent,
    IndexPerformanceMonitor,
)
from swagger_mcp_server.search.monitoring_integration import (
    SearchMonitoringIntegration,
)
from swagger_mcp_server.search.performance_monitor import (
    AlertLevel,
    PerformanceAlert,
    SearchAnalytics,
    SearchPerformanceMonitor,
)
from swagger_mcp_server.search.performance_tester import (
    LoadTestConfiguration,
    PerformanceTestCase,
    SearchPerformanceTester,
)


@pytest.fixture
def search_config():
    """Create test search configuration."""
    return SearchConfig(
        performance=SearchPerformanceConfig(
            max_search_results=100, query_timeout=30.0, enable_caching=True
        )
    )


@pytest.fixture
def sample_analytics_data():
    """Create sample analytics data for testing."""
    base_time = datetime.now()

    analytics_data = []
    for i in range(20):
        analytics = SearchAnalytics(
            query_text=f"test query {i}",
            search_type="endpoint",
            filters_applied={},
            query_processing_time=10.0 + i,
            total_response_time=50.0 + (i * 10),
            index_query_time=30.0 + i,
            result_processing_time=10.0 + i,
            result_count=max(0, 10 - i // 3),
            correlation_id=f"corr_{i}",
            timestamp=base_time + timedelta(minutes=i),
            performance_grade="good" if i < 10 else "poor",
            exceeded_threshold=i >= 15,
            cache_hit=i % 2 == 0,
            concurrent_queries=min(i, 5),
        )
        analytics_data.append(analytics)

    return analytics_data


class TestSearchPerformanceMonitor:
    """Test search performance monitoring functionality."""

    @pytest.fixture
    def performance_monitor(self, search_config):
        """Create performance monitor instance."""
        return SearchPerformanceMonitor(search_config)

    @pytest.mark.asyncio
    async def test_monitor_search_operation(self, performance_monitor):
        """Test monitoring of search operations."""

        # Mock search function
        async def mock_search_function(query, **kwargs):
            await asyncio.sleep(0.01)  # Simulate search time
            return {"results": [{"id": "1"}, {"id": "2"}], "total_results": 2}

        # Monitor search operation
        result = await performance_monitor.monitor_search_operation(
            mock_search_function, query="test query", search_type="endpoint"
        )

        # Verify result
        assert result["total_results"] == 2
        assert len(result["results"]) == 2

        # Verify analytics recorded
        assert len(performance_monitor.analytics_data) == 1
        analytics = performance_monitor.analytics_data[0]
        assert analytics.query_text == "test query"
        assert analytics.search_type == "endpoint"
        assert analytics.result_count == 2
        assert analytics.total_response_time > 0

    @pytest.mark.asyncio
    async def test_performance_summary_generation(
        self, performance_monitor, sample_analytics_data
    ):
        """Test performance summary generation."""
        # Add sample data
        for analytics in sample_analytics_data:
            performance_monitor.analytics_data.append(analytics)

        # Get performance summary
        summary = await performance_monitor.get_performance_summary("1h")

        # Verify summary structure
        assert "time_period" in summary
        assert "response_time_metrics" in summary
        assert "query_volume_metrics" in summary
        assert "search_effectiveness" in summary
        assert "optimization_recommendations" in summary

        # Verify response time metrics
        response_times = summary["response_time_metrics"]
        assert "avg" in response_times
        assert "p95" in response_times
        assert "nfr1_compliance" in response_times

        # Verify optimization recommendations
        recommendations = summary["optimization_recommendations"]
        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_alert_generation(self, performance_monitor):
        """Test performance alert generation."""
        alert_triggered = False
        captured_alert = None

        async def alert_callback(alert):
            nonlocal alert_triggered, captured_alert
            alert_triggered = True
            captured_alert = alert

        performance_monitor.add_alert_callback(alert_callback)

        # Create analytics that should trigger an alert
        slow_analytics = SearchAnalytics(
            query_text="slow query",
            search_type="endpoint",
            filters_applied={},
            query_processing_time=50.0,
            total_response_time=350.0,  # Exceeds critical threshold
            index_query_time=200.0,
            result_processing_time=100.0,
            result_count=5,
            correlation_id="slow_test",
        )

        # Record analytics (should trigger alert)
        await performance_monitor._record_analytics(slow_analytics)
        await performance_monitor._check_performance_thresholds(slow_analytics)

        # Verify alert was triggered
        assert alert_triggered
        assert captured_alert is not None
        assert captured_alert.level == AlertLevel.CRITICAL
        assert "slow query" in captured_alert.description

    def test_correlation_id_generation(self, performance_monitor):
        """Test correlation ID generation."""
        correlation_id = performance_monitor._generate_correlation_id()
        assert len(correlation_id) == 8
        assert correlation_id.isalnum()

        # Test uniqueness
        correlation_id2 = performance_monitor._generate_correlation_id()
        assert correlation_id != correlation_id2

    def test_performance_classification(self, performance_monitor):
        """Test performance classification logic."""
        # Test excellent performance
        assert performance_monitor._classify_performance(30.0) == "excellent"

        # Test good performance
        assert performance_monitor._classify_performance(80.0) == "good"

        # Test acceptable performance
        assert performance_monitor._classify_performance(180.0) == "acceptable"

        # Test poor performance
        assert performance_monitor._classify_performance(350.0) == "poor"


class TestSearchAnalyticsEngine:
    """Test search analytics engine functionality."""

    @pytest.fixture
    def analytics_engine(self):
        """Create analytics engine instance."""
        return SearchAnalyticsEngine()

    @pytest.mark.asyncio
    async def test_query_pattern_identification(
        self, analytics_engine, sample_analytics_data
    ):
        """Test query pattern identification."""
        # Add some duplicate queries for pattern detection
        duplicate_queries = []
        for i in range(5):
            analytics = SearchAnalytics(
                query_text="user authentication",
                search_type="endpoint",
                filters_applied={},
                query_processing_time=15.0,
                total_response_time=85.0,
                index_query_time=50.0,
                result_processing_time=20.0,
                result_count=8,
                correlation_id=f"dup_{i}",
                timestamp=datetime.now() + timedelta(minutes=i),
            )
            duplicate_queries.append(analytics)

        all_data = sample_analytics_data + duplicate_queries

        # Analyze patterns
        analysis_result = await analytics_engine.analyze_search_patterns(
            all_data
        )

        # Verify pattern analysis
        assert "query_patterns" in analysis_result
        assert "user_behavior" in analysis_result
        assert "effectiveness_metrics" in analysis_result
        assert "recommendations" in analysis_result

        # Find the pattern for "user authentication"
        patterns = analysis_result["query_patterns"]
        auth_pattern = None
        for pattern in patterns:
            if pattern["pattern_text"] == "user authentication":
                auth_pattern = pattern
                break

        assert auth_pattern is not None
        assert auth_pattern["frequency"] == 5
        assert auth_pattern["pattern_type"] in [
            pt.value for pt in QueryPatternType
        ]

    @pytest.mark.asyncio
    async def test_user_session_analysis(self, analytics_engine):
        """Test user session analysis."""
        # Create session-based analytics data
        session_data = []
        base_time = datetime.now()

        # Session 1: Iterative user
        for i in range(3):
            analytics = SearchAnalytics(
                query_text=f"user auth{'' if i == 0 else 'entication'}",  # Similar queries
                search_type="endpoint",
                filters_applied={},
                query_processing_time=10.0,
                total_response_time=100.0,
                index_query_time=60.0,
                result_processing_time=30.0,
                result_count=5 + i,
                correlation_id=f"session1_{i}",
                user_session="session_1",
                timestamp=base_time + timedelta(minutes=i * 2),
                results_clicked=[f"result_{j}" for j in range(min(i + 1, 2))],
            )
            session_data.append(analytics)

        # Session 2: Explorer user
        for i in range(4):
            analytics = SearchAnalytics(
                query_text=f"different query {i}",  # Diverse queries
                search_type="endpoint",
                filters_applied={
                    "http_method": ["GET"],
                    "tag": f"tag_{i}",
                },  # Many filters
                query_processing_time=15.0,
                total_response_time=120.0,
                index_query_time=70.0,
                result_processing_time=35.0,
                result_count=10,
                correlation_id=f"session2_{i}",
                user_session="session_2",
                timestamp=base_time + timedelta(minutes=i * 3),
            )
            session_data.append(analytics)

        # Analyze sessions
        sessions = await analytics_engine._analyze_user_sessions(session_data)

        # Verify session analysis
        assert len(sessions) == 2

        # Find sessions by ID
        session_1 = next(s for s in sessions if s.session_id == "session_1")
        session_2 = next(s for s in sessions if s.session_id == "session_2")

        # Session 1 should be classified as iterative (similar queries)
        assert session_1.behavior_pattern == UserBehaviorPattern.ITERATIVE

        # Session 2 should be classified as explorer (diverse queries, many filters)
        assert session_2.behavior_pattern == UserBehaviorPattern.EXPLORER

    @pytest.mark.asyncio
    async def test_search_effectiveness_calculation(
        self, analytics_engine, sample_analytics_data
    ):
        """Test search effectiveness calculation."""
        # Add some interaction data
        for i, analytics in enumerate(sample_analytics_data):
            if i % 3 == 0:  # Some queries have clicks
                analytics.results_clicked = [
                    f"result_{j}"
                    for j in range(min(analytics.result_count, 2))
                ]
            if i >= 15:  # Some queries are abandoned
                analytics.query_abandoned = True

        effectiveness = await analytics_engine._calculate_search_effectiveness(
            sample_analytics_data
        )

        # Verify effectiveness metrics
        assert 0 <= effectiveness.relevance_score <= 1
        assert 0 <= effectiveness.query_success_rate <= 1
        assert 0 <= effectiveness.abandonment_rate <= 1
        assert 0 <= effectiveness.refinement_rate <= 1
        assert effectiveness.user_engagement >= 0

        # Check that effectiveness calculations make sense
        assert (
            effectiveness.query_success_rate > 0
        )  # Some queries should succeed
        assert (
            effectiveness.abandonment_rate > 0
        )  # Some queries are marked as abandoned

    def test_query_normalization(self, analytics_engine):
        """Test query text normalization."""
        # Test basic normalization
        normalized = analytics_engine._normalize_query_text(
            "User Authentication System"
        )
        assert normalized == "user authentication system"

        # Test special character removal
        normalized = analytics_engine._normalize_query_text(
            "user@auth!system#"
        )
        assert normalized == "user auth system"

        # Test multiple spaces
        normalized = analytics_engine._normalize_query_text(
            "user    auth   system"
        )
        assert normalized == "user auth system"

    def test_query_similarity(self, analytics_engine):
        """Test query similarity detection."""
        # Similar queries
        assert analytics_engine._are_queries_similar(
            "user auth", "user authentication"
        )
        assert analytics_engine._are_queries_similar("get users", "users get")

        # Different queries
        assert not analytics_engine._are_queries_similar(
            "user auth", "product catalog"
        )
        assert not analytics_engine._are_queries_similar(
            "authentication", "completely different"
        )


class TestIndexPerformanceMonitor:
    """Test index performance monitoring functionality."""

    @pytest.fixture
    def index_monitor(self, search_config):
        """Create index monitor instance."""
        return IndexPerformanceMonitor("/tmp/test_index", search_config)

    @pytest.mark.asyncio
    async def test_index_metrics_collection(self, index_monitor):
        """Test index metrics collection."""
        with patch("os.path.exists", return_value=True), patch(
            "os.walk",
            return_value=[
                ("/tmp/test_index", [], ["index.db", "segments.gen"])
            ],
        ), patch(
            "os.path.getsize", side_effect=[1024 * 1024, 512 * 1024]
        ):  # 1MB + 512KB
            metrics = await index_monitor.collect_index_metrics()

            # Verify metrics structure
            assert isinstance(metrics, IndexMetrics)
            assert metrics.index_size_mb > 0
            assert metrics.document_count > 0
            assert metrics.query_time_ms > 0
            assert 0 <= metrics.fragmentation_ratio <= 1
            assert 0 <= metrics.cache_hit_rate <= 1

    @pytest.mark.asyncio
    async def test_optimization_trigger(self, index_monitor):
        """Test optimization triggering logic."""
        # Create metrics with high fragmentation
        with patch.object(
            index_monitor, "_calculate_fragmentation", return_value=0.35
        ), patch.object(
            index_monitor, "_trigger_optimization"
        ) as mock_trigger:
            metrics = await index_monitor.collect_index_metrics()

            # Optimization should be triggered due to high fragmentation
            mock_trigger.assert_called_once_with("high_fragmentation")

    @pytest.mark.asyncio
    async def test_performance_summary(self, index_monitor):
        """Test performance summary generation."""
        # Add some mock metrics to history
        for i in range(10):
            metrics = IndexMetrics(
                index_size_bytes=1024 * 1024 * (i + 1),
                index_size_mb=i + 1,
                document_count=1000 * (i + 1),
                field_count=10,
                query_time_ms=50 + i * 5,
                update_time_ms=10 + i,
                optimization_time_ms=None,
                fragmentation_ratio=0.1 + i * 0.02,
                cache_hit_rate=0.8 - i * 0.01,
                disk_io_rate=100.0,
                storage_utilization=0.5 + i * 0.02,
                memory_usage_mb=100 + i * 10,
                cpu_usage_percent=20 + i * 2,
                timestamp=datetime.now() - timedelta(minutes=10 - i),
            )
            index_monitor.metrics_history.append(metrics)

        summary = await index_monitor.get_performance_summary("24h")

        # Verify summary structure
        assert "index_size" in summary
        assert "performance" in summary
        assert "resource_usage" in summary
        assert "health" in summary
        assert "recommendations" in summary

        # Verify calculations
        size_stats = summary["index_size"]
        assert size_stats["current_size_mb"] == 10  # Last metrics
        assert size_stats["size_growth_mb"] == 9  # 10 - 1

    @pytest.mark.asyncio
    async def test_growth_projection(self, index_monitor):
        """Test index growth projection."""
        # Add metrics with growth pattern
        base_time = datetime.now() - timedelta(days=7)
        for i in range(7):  # One week of data
            metrics = IndexMetrics(
                index_size_bytes=(100 + i * 10)
                * 1024
                * 1024,  # 10MB growth per day
                index_size_mb=100 + i * 10,
                document_count=10000 + i * 1000,  # 1000 docs per day
                field_count=10,
                query_time_ms=50,
                update_time_ms=10,
                optimization_time_ms=None,
                fragmentation_ratio=0.1,
                cache_hit_rate=0.8,
                disk_io_rate=100.0,
                storage_utilization=0.5,
                memory_usage_mb=200,
                cpu_usage_percent=30,
                timestamp=base_time + timedelta(days=i),
            )
            index_monitor.metrics_history.append(metrics)

        projection = await index_monitor.project_index_growth(30)

        # Verify projection
        assert projection.current_size_mb == 160  # Last value
        assert projection.projected_size_mb > 160  # Should project growth
        assert projection.growth_rate_mb_per_day > 0
        assert projection.growth_rate_documents_per_day > 0


class TestPerformanceTester:
    """Test performance testing functionality."""

    @pytest.fixture
    def performance_tester(self, search_config):
        """Create performance tester instance."""

        # Mock search function for testing
        async def mock_search(test_case):
            await asyncio.sleep(0.01)  # Simulate search time
            return {
                "results": [{"id": f"result_{i}"} for i in range(5)],
                "total_results": 5,
            }

        return SearchPerformanceTester(mock_search, search_config)

    @pytest.mark.asyncio
    async def test_nfr1_validation(self, performance_tester):
        """Test NFR1 compliance validation."""
        validation_result = await performance_tester.validate_nfr1_compliance()

        # Verify validation structure
        assert "nfr1_threshold_ms" in validation_result
        assert "overall_compliance_rate" in validation_result
        assert "detailed_results" in validation_result

        # Verify threshold
        assert validation_result["nfr1_threshold_ms"] == 200.0

        # Verify compliance status
        assert validation_result["compliance_status"] in [
            "pass",
            "warning",
            "fail",
        ]

    @pytest.mark.asyncio
    async def test_load_testing(self, performance_tester):
        """Test load testing functionality."""
        # Use shorter duration for testing
        with patch.object(
            performance_tester, "_execute_load_test"
        ) as mock_load_test:
            mock_result = Mock()
            mock_result.configuration.concurrent_users = 5
            mock_result.avg_response_time_ms = 75.0
            mock_result.nfr1_compliance_rate = 0.95
            mock_result.failed_requests = 0
            mock_result.total_requests = 50
            mock_load_test.return_value = mock_result

            load_results = await performance_tester.run_load_tests()

            # Verify load test structure
            assert "results" in load_results
            assert "summary" in load_results

            # Verify mock was called
            assert mock_load_test.call_count > 0

    @pytest.mark.asyncio
    async def test_stress_testing(self, performance_tester):
        """Test stress testing functionality."""
        with patch.object(
            performance_tester, "_execute_load_test"
        ) as mock_load_test:
            # Mock increasing degradation with load
            def side_effect(config):
                result = Mock()
                result.configuration = config
                result.avg_response_time_ms = 50 + (
                    config.concurrent_users * 5
                )
                result.failed_requests = max(0, config.concurrent_users - 10)
                result.total_requests = config.concurrent_users * 10
                return result

            mock_load_test.side_effect = side_effect

            stress_results = await performance_tester.run_stress_tests()

            # Verify stress test results
            assert "max_successful_concurrent_users" in stress_results
            assert "breaking_point_concurrent_users" in stress_results
            assert "response_time_at_breaking_point" in stress_results

    def test_test_case_creation(self, performance_tester):
        """Test standard test case creation."""
        test_cases = performance_tester.standard_test_cases

        # Verify test cases were created
        assert len(test_cases) > 0

        # Verify test case structure
        for test_case in test_cases:
            assert hasattr(test_case, "test_id")
            assert hasattr(test_case, "query")
            assert hasattr(test_case, "expected_response_time_ms")
            assert test_case.expected_response_time_ms > 0

        # Verify specific test cases exist
        test_ids = [tc.test_id for tc in test_cases]
        assert "simple_user_search" in test_ids
        assert "simple_auth_search" in test_ids
        assert "unified_simple_search" in test_ids


class TestAnalyticsDashboard:
    """Test analytics dashboard functionality."""

    @pytest.fixture
    def dashboard_components(self, search_config):
        """Create dashboard components for testing."""
        performance_monitor = Mock(spec=SearchPerformanceMonitor)
        analytics_engine = Mock(spec=SearchAnalyticsEngine)
        index_monitor = Mock(spec=IndexPerformanceMonitor)

        # Mock performance monitor
        performance_monitor.get_performance_summary = AsyncMock(
            return_value={
                "response_time_metrics": {
                    "avg": 85.0,
                    "p95": 150.0,
                    "nfr1_compliance": 92.0,
                },
                "query_volume_metrics": {
                    "total_queries": 1000,
                    "avg_queries_per_hour": 42,
                },
                "current_metrics": {
                    "active_queries": 3,
                    "cache_hit_rate_hour": 0.75,
                },
            }
        )
        performance_monitor.get_active_alerts = Mock(return_value=[])
        performance_monitor.analytics_data = []

        # Mock analytics engine
        analytics_engine.analyze_search_patterns = AsyncMock(
            return_value={
                "query_patterns": [
                    {"pattern_text": "user auth", "frequency": 10}
                ],
                "user_behavior": {
                    "behavior_distribution": {"explorer": 5, "searcher": 3}
                },
                "effectiveness_metrics": {
                    "relevance_score": 0.85,
                    "query_success_rate": 0.9,
                },
                "recommendations": [],
            }
        )

        # Mock index monitor
        index_monitor.get_performance_summary = AsyncMock(
            return_value={
                "health": {"health_score": 85, "health_status": "good"},
                "index_size": {"current_size_mb": 256, "size_growth_mb": 12},
                "optimization": {"last_optimization": None},
            }
        )

        dashboard = SearchAnalyticsDashboard(
            performance_monitor=performance_monitor,
            analytics_engine=analytics_engine,
            index_monitor=index_monitor,
        )

        return dashboard, performance_monitor, analytics_engine, index_monitor

    @pytest.mark.asyncio
    async def test_dashboard_data_generation(self, dashboard_components):
        """Test dashboard data generation."""
        dashboard, _, _, _ = dashboard_components

        dashboard_data = await dashboard.get_dashboard_data("24h")

        # Verify dashboard structure
        assert "metadata" in dashboard_data
        assert "performance" in dashboard_data
        assert "analytics" in dashboard_data
        assert "index" in dashboard_data
        assert "alerts" in dashboard_data
        assert "recommendations" in dashboard_data
        assert "status" in dashboard_data

        # Verify metadata
        metadata = dashboard_data["metadata"]
        assert "generated_at" in metadata
        assert "time_period" in metadata
        assert metadata["time_period"] == "24h"

        # Verify performance data
        performance = dashboard_data["performance"]
        assert "overview" in performance
        assert "nfr1_compliance" in performance

    @pytest.mark.asyncio
    async def test_widget_data_extraction(self, dashboard_components):
        """Test widget data extraction."""
        dashboard, _, _, _ = dashboard_components

        # Test specific widget data
        widget_data = await dashboard.get_widget_data("performance_overview")

        # Verify widget data structure
        assert "widget_id" in widget_data
        assert "widget_type" in widget_data
        assert "title" in widget_data
        assert "data" in widget_data
        assert widget_data["widget_id"] == "performance_overview"

    @pytest.mark.asyncio
    async def test_dashboard_export(self, dashboard_components):
        """Test dashboard data export."""
        dashboard, _, _, _ = dashboard_components

        # Test JSON export
        json_export = await dashboard.export_dashboard_data("json")
        assert isinstance(json_export, str)
        assert "performance" in json_export

        # Test CSV export
        csv_export = await dashboard.export_dashboard_data("csv")
        assert isinstance(csv_export, str)
        assert "metric,value,timestamp" in csv_export

        # Test invalid format
        with pytest.raises(ValueError):
            await dashboard.export_dashboard_data("invalid")


class TestMonitoringIntegration:
    """Test monitoring integration functionality."""

    @pytest.fixture
    def integration_components(self, search_config):
        """Create integration components for testing."""
        search_monitor = Mock(spec=SearchPerformanceMonitor)
        dashboard = Mock(spec=SearchAnalyticsDashboard)
        mcp_monitor = Mock()

        search_monitor.get_performance_summary = AsyncMock(
            return_value={
                "response_time_metrics": {"avg": 85.0, "p95": 150.0},
                "query_volume_metrics": {"total_queries": 1000},
                "current_metrics": {"active_queries": 3},
            }
        )
        search_monitor.add_alert_callback = Mock()
        search_monitor.remove_alert_callback = Mock()

        dashboard.get_dashboard_data = AsyncMock(return_value={"status": "ok"})

        mcp_monitor.record_metric = AsyncMock()
        mcp_monitor.record_alert = AsyncMock()

        integration = SearchMonitoringIntegration(
            search_monitor=search_monitor,
            dashboard=dashboard,
            mcp_monitor=mcp_monitor,
        )

        return integration, search_monitor, dashboard, mcp_monitor

    @pytest.mark.asyncio
    async def test_integration_initialization(self, integration_components):
        """Test monitoring integration initialization."""
        integration, search_monitor, _, _ = integration_components

        await integration.initialize_integration()

        # Verify initialization
        assert integration.integration_active
        search_monitor.add_alert_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_metric_export(self, integration_components):
        """Test metric export functionality."""
        integration, _, _, _ = integration_components

        metrics = await integration.export_search_metrics()

        # Verify exported metrics
        assert isinstance(metrics, list)
        assert len(metrics) > 0

        # Verify metric structure
        for metric in metrics:
            assert hasattr(metric, "metric_name")
            assert hasattr(metric, "metric_value")
            assert hasattr(metric, "metric_type")
            assert hasattr(metric, "timestamp")
            assert hasattr(metric, "tags")

    @pytest.mark.asyncio
    async def test_alert_handling(self, integration_components):
        """Test alert handling in integration."""
        integration, _, _, mcp_monitor = integration_components

        # Create test alert
        test_alert = PerformanceAlert(
            alert_id="test_alert",
            level=AlertLevel.WARNING,
            title="Test Alert",
            description="Test alert description",
            metric_value=150.0,
            threshold=100.0,
        )

        # Handle alert
        await integration._handle_search_alert(test_alert)

        # Verify alert was sent to MCP monitoring
        mcp_monitor.record_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_integration_status(self, integration_components):
        """Test integration status reporting."""
        integration, _, _, _ = integration_components

        await integration.initialize_integration()
        status = await integration.get_integration_status()

        # Verify status structure
        assert "integration_active" in status
        assert "mcp_integration_enabled" in status
        assert "last_metric_export" in status
        assert status["integration_active"] is True

    @pytest.mark.asyncio
    async def test_health_validation(self, integration_components):
        """Test integration health validation."""
        integration, _, _, _ = integration_components

        await integration.initialize_integration()
        health = await integration.validate_integration_health()

        # Verify health check structure
        assert "overall_status" in health
        assert "health_checks" in health
        assert "total_checks" in health
        assert health["overall_status"] in [
            "healthy",
            "degraded",
            "unhealthy",
            "error",
        ]

    @pytest.mark.asyncio
    async def test_monitoring_report_generation(self, integration_components):
        """Test monitoring report generation."""
        integration, _, _, _ = integration_components

        report = await integration.generate_monitoring_report("24h")

        # Verify report structure
        assert "report_metadata" in report
        assert "integration_status" in report
        assert "performance_summary" in report
        assert "system_health" in report
        assert "recommendations" in report

        # Verify metadata
        metadata = report["report_metadata"]
        assert "generated_at" in metadata
        assert "time_period" in metadata
        assert metadata["time_period"] == "24h"


class TestIntegrationScenarios:
    """Test end-to-end integration scenarios."""

    @pytest.mark.asyncio
    async def test_complete_analytics_workflow(
        self, search_config, sample_analytics_data
    ):
        """Test complete analytics workflow from data collection to dashboard."""
        # Create components
        performance_monitor = SearchPerformanceMonitor(search_config)
        analytics_engine = SearchAnalyticsEngine()
        index_monitor = IndexPerformanceMonitor("/tmp/test", search_config)

        # Mock index monitor methods
        index_monitor.get_performance_summary = AsyncMock(
            return_value={
                "health": {"health_score": 85},
                "index_size": {"current_size_mb": 100},
            }
        )

        dashboard = SearchAnalyticsDashboard(
            performance_monitor=performance_monitor,
            analytics_engine=analytics_engine,
            index_monitor=index_monitor,
        )

        # Add sample data
        for analytics in sample_analytics_data:
            performance_monitor.analytics_data.append(analytics)

        # Generate dashboard data
        dashboard_data = await dashboard.get_dashboard_data("1h")

        # Verify complete workflow
        assert dashboard_data is not None
        assert "performance" in dashboard_data
        assert "analytics" in dashboard_data
        assert "recommendations" in dashboard_data

    @pytest.mark.asyncio
    async def test_performance_degradation_detection(self, search_config):
        """Test detection of performance degradation."""
        performance_monitor = SearchPerformanceMonitor(search_config)

        # Create degrading performance data
        base_time = datetime.now()
        for i in range(10):
            # Performance gets worse over time
            response_time = 100 + (i * 20)  # 100ms to 280ms
            analytics = SearchAnalytics(
                query_text=f"query {i}",
                search_type="endpoint",
                filters_applied={},
                query_processing_time=20.0,
                total_response_time=response_time,
                index_query_time=response_time * 0.6,
                result_processing_time=response_time * 0.2,
                result_count=5,
                correlation_id=f"deg_{i}",
                timestamp=base_time + timedelta(minutes=i),
            )
            performance_monitor.analytics_data.append(analytics)

        # Get performance summary
        summary = await performance_monitor.get_performance_summary("1h")

        # Verify degradation detection
        trends = summary.get("performance_trends", {})
        assert trends.get("trend_direction") == "degrading"

        # Check for recommendations
        recommendations = summary.get("optimization_recommendations", [])
        assert len(recommendations) > 0

    @pytest.mark.asyncio
    async def test_alert_escalation_workflow(self, search_config):
        """Test alert escalation workflow."""
        performance_monitor = SearchPerformanceMonitor(search_config)

        alerts_triggered = []

        async def alert_handler(alert):
            alerts_triggered.append(alert)

        performance_monitor.add_alert_callback(alert_handler)

        # Create critical performance issue
        critical_analytics = SearchAnalytics(
            query_text="critical query",
            search_type="endpoint",
            filters_applied={},
            query_processing_time=100.0,
            total_response_time=500.0,  # Well above critical threshold
            index_query_time=300.0,
            result_processing_time=100.0,
            result_count=0,  # No results
            correlation_id="critical_test",
        )

        # Process the analytics
        await performance_monitor._record_analytics(critical_analytics)
        await performance_monitor._check_performance_thresholds(
            critical_analytics
        )

        # Verify alert escalation
        assert len(alerts_triggered) > 0
        critical_alert = alerts_triggered[0]
        assert critical_alert.level == AlertLevel.CRITICAL
        assert critical_alert.metric_value == 500.0


if __name__ == "__main__":
    pytest.main([__file__])
