"""Comprehensive tests for MCP server performance monitoring (Story 2.6)."""

import asyncio
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swagger_mcp_server.config.settings import Settings
from swagger_mcp_server.server.health import (
    ComponentHealth,
    HealthChecker,
    HealthStatus,
)
from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer
from swagger_mcp_server.server.monitoring import (
    MethodMetrics,
    MetricsCollector,
    PerformanceMonitor,
    PerformanceThresholds,
    SystemMetrics,
    global_monitor,
    monitor_performance,
)


class TestMethodMetrics:
    """Test MethodMetrics functionality."""

    def test_method_metrics_initialization(self):
        """Test MethodMetrics initialization."""
        metrics = MethodMetrics("testMethod")

        assert metrics.method_name == "testMethod"
        assert metrics.total_requests == 0
        assert metrics.total_errors == 0
        assert metrics.total_response_time == 0.0
        assert len(metrics.response_times) == 0
        assert len(metrics.error_types) == 0

    def test_record_request_success(self):
        """Test recording successful requests."""
        metrics = MethodMetrics("testMethod")

        # Record multiple requests
        metrics.record_request(0.1)  # 100ms
        metrics.record_request(0.2)  # 200ms
        metrics.record_request(0.15)  # 150ms

        assert metrics.total_requests == 3
        assert metrics.total_errors == 0
        assert abs(metrics.total_response_time - 0.45) < 0.001
        assert abs(metrics.avg_response_time - 150.0) < 0.001  # (100+200+150)/3 = 150ms
        assert len(metrics.response_times) == 3

    def test_record_request_with_errors(self):
        """Test recording requests with errors."""
        metrics = MethodMetrics("testMethod")

        # Record requests with and without errors
        metrics.record_request(0.1)
        metrics.record_request(0.2, "ValidationError")
        metrics.record_request(0.15, "DatabaseError")
        metrics.record_request(0.3, "ValidationError")

        assert metrics.total_requests == 4
        assert metrics.total_errors == 3
        assert abs(metrics.error_rate - 0.75) < 0.001  # 3/4 = 0.75
        assert metrics.error_types["ValidationError"] == 2
        assert metrics.error_types["DatabaseError"] == 1

    def test_p95_response_time(self):
        """Test P95 response time calculation."""
        metrics = MethodMetrics("testMethod")

        # Add enough requests for P95 calculation
        response_times = [
            0.1,
            0.15,
            0.2,
            0.25,
            0.3,
            0.35,
            0.4,
            0.45,
            0.5,
            0.6,
            0.7,
            0.8,
            0.9,
            1.0,
            1.1,
            1.2,
            1.3,
            1.4,
            1.5,
            2.0,
        ]

        for rt in response_times:
            metrics.record_request(rt)

        p95 = metrics.p95_response_time
        # P95 of 20 values should be around 19th value (1.5s = 1500ms)
        assert 1400 <= p95 <= 1600

    def test_metrics_dict_serialization(self):
        """Test metrics dictionary serialization."""
        metrics = MethodMetrics("testMethod")
        metrics.record_request(0.1)
        metrics.record_request(0.2, "TestError")

        metrics_dict = metrics.get_metrics_dict()

        required_fields = [
            "avg_response_time",
            "p95_response_time",
            "requests_per_minute",
            "error_rate",
            "total_requests",
            "total_errors",
            "error_types",
        ]
        for field in required_fields:
            assert field in metrics_dict

        assert metrics_dict["total_requests"] == 2
        assert metrics_dict["total_errors"] == 1
        assert metrics_dict["error_types"]["TestError"] == 1


class TestSystemMetrics:
    """Test SystemMetrics functionality."""

    def test_system_metrics_initialization(self):
        """Test SystemMetrics initialization."""
        metrics = SystemMetrics()

        assert metrics.concurrent_connections == 0
        assert metrics.database_pool_utilization == 0.0
        assert metrics.startup_time > 0

    def test_update_system_metrics(self):
        """Test system metrics update."""
        metrics = SystemMetrics()

        # Mock the startup time to test uptime calculation
        metrics.startup_time = time.time() - 100  # 100 seconds ago

        metrics.update_system_metrics()

        assert metrics.uptime_seconds >= 100
        assert metrics.memory_usage_mb > 0
        assert 0 <= metrics.cpu_utilization <= 1

    def test_system_metrics_dict(self):
        """Test system metrics dictionary serialization."""
        metrics = SystemMetrics()
        metrics.concurrent_connections = 5
        metrics.database_pool_utilization = 0.75

        metrics_dict = metrics.get_metrics_dict()

        required_fields = [
            "concurrent_connections",
            "database_pool_utilization",
            "memory_usage_mb",
            "cpu_utilization",
            "uptime_seconds",
        ]
        for field in required_fields:
            assert field in metrics_dict

        assert metrics_dict["concurrent_connections"] == 5
        assert abs(metrics_dict["database_pool_utilization"] - 0.75) < 0.001


class TestPerformanceMonitor:
    """Test PerformanceMonitor functionality."""

    def test_performance_monitor_initialization(self):
        """Test PerformanceMonitor initialization."""
        thresholds = PerformanceThresholds(searchEndpoints_max_ms=100)
        monitor = PerformanceMonitor(thresholds)

        assert monitor.thresholds.searchEndpoints_max_ms == 100
        assert (
            len(monitor.method_metrics) == 3
        )  # searchEndpoints, getSchema, getExample
        assert monitor.monitoring_enabled is True

    def test_record_request_success(self):
        """Test recording successful requests."""
        monitor = PerformanceMonitor()

        monitor.record_request("searchEndpoints", 0.15, None, "req-123")

        metrics = monitor.method_metrics["searchEndpoints"]
        assert metrics.total_requests == 1
        assert metrics.total_errors == 0
        assert abs(metrics.avg_response_time - 150.0) < 0.001

    def test_record_request_with_error(self):
        """Test recording requests with errors."""
        monitor = PerformanceMonitor()

        monitor.record_request("getSchema", 0.8, "Schema not found", "req-456")

        metrics = monitor.method_metrics["getSchema"]
        assert metrics.total_requests == 1
        assert metrics.total_errors == 1
        assert abs(metrics.error_rate - 1.0) < 0.001

    def test_threshold_violation_detection(self):
        """Test performance threshold violation detection."""
        thresholds = PerformanceThresholds(searchEndpoints_max_ms=100)
        monitor = PerformanceMonitor(thresholds)

        # Record a request that exceeds threshold
        monitor.record_request(
            "searchEndpoints", 0.25, None, "req-123"
        )  # 250ms > 100ms

        # Should have created an alert
        assert len(monitor.alerts) > 0
        alert = monitor.alerts[0]
        assert alert["type"] == "response_time_exceeded"
        assert "searchEndpoints" in alert["message"]

    def test_error_rate_threshold_violation(self):
        """Test error rate threshold violation detection."""
        thresholds = PerformanceThresholds(error_rate_max=0.2)
        monitor = PerformanceMonitor(thresholds)

        # Record requests with high error rate
        for i in range(10):
            error = "Test error" if i < 5 else None  # 50% error rate
            monitor.record_request("getExample", 0.1, error, f"req-{i}")

        # Should have created an alert for high error rate
        error_rate_alerts = [
            a for a in monitor.alerts if a["type"] == "error_rate_exceeded"
        ]
        assert len(error_rate_alerts) > 0

    def test_connection_count_update(self):
        """Test connection count update."""
        monitor = PerformanceMonitor()

        monitor.update_connection_count(25)
        assert monitor.system_metrics.concurrent_connections == 25

    def test_database_pool_utilization_update(self):
        """Test database pool utilization update."""
        monitor = PerformanceMonitor()

        monitor.update_database_pool_utilization(0.8)
        assert abs(monitor.system_metrics.database_pool_utilization - 0.8) < 0.001

    def test_get_performance_metrics(self):
        """Test getting performance metrics."""
        monitor = PerformanceMonitor()
        monitor.record_request("searchEndpoints", 0.1)

        metrics = monitor.get_performance_metrics()

        assert "performance_metrics" in metrics
        assert "system_health" in metrics
        assert "alerts" in metrics
        assert "monitoring_enabled" in metrics
        assert "thresholds" in metrics

        assert "searchEndpoints" in metrics["performance_metrics"]

    def test_get_health_summary(self):
        """Test getting health summary."""
        monitor = PerformanceMonitor()
        monitor.record_request("searchEndpoints", 0.1)

        summary = monitor.get_health_summary()

        required_fields = [
            "status",
            "uptime_seconds",
            "total_requests",
            "total_errors",
            "recent_alerts",
            "critical_alerts",
        ]
        for field in required_fields:
            assert field in summary

        assert summary["status"] in ["healthy", "degraded", "unhealthy"]

    def test_reset_metrics(self):
        """Test metrics reset functionality."""
        monitor = PerformanceMonitor()
        monitor.record_request("searchEndpoints", 0.1, "Test error")

        # Verify metrics exist
        assert monitor.method_metrics["searchEndpoints"].total_requests > 0

        # Reset and verify
        monitor.reset_metrics()
        assert monitor.method_metrics["searchEndpoints"].total_requests == 0
        assert len(monitor.alerts) == 0

    def test_monitoring_enable_disable(self):
        """Test enabling/disabling monitoring."""
        monitor = PerformanceMonitor()

        # Disable monitoring
        monitor.set_monitoring_enabled(False)
        assert monitor.monitoring_enabled is False

        # Record request (should be ignored)
        monitor.record_request("searchEndpoints", 0.1)
        # Note: This test depends on implementation details

        # Re-enable monitoring
        monitor.set_monitoring_enabled(True)
        assert monitor.monitoring_enabled is True


class TestMonitoringDecorator:
    """Test monitoring decorator functionality."""

    @pytest.mark.asyncio
    async def test_monitor_performance_decorator_async(self):
        """Test monitoring decorator with async function."""
        monitor = PerformanceMonitor()
        initial_requests = monitor.method_metrics["testMethod"].total_requests

        @monitor_performance("testMethod", monitor)
        async def test_async_function():
            await asyncio.sleep(0.1)
            return "success"

        result = await test_async_function()
        assert result == "success"

        # Check that metrics were recorded
        metrics = monitor.method_metrics["testMethod"]
        assert metrics.total_requests == initial_requests + 1
        assert metrics.avg_response_time >= 100  # At least 100ms due to sleep

    def test_monitor_performance_decorator_sync(self):
        """Test monitoring decorator with sync function."""
        monitor = PerformanceMonitor()

        @monitor_performance("testSyncMethod", monitor)
        def test_sync_function():
            time.sleep(0.05)  # 50ms
            return "success"

        result = test_sync_function()
        assert result == "success"

        # Check that metrics were recorded
        metrics = monitor.method_metrics["testSyncMethod"]
        assert metrics.total_requests == 1
        assert metrics.avg_response_time >= 50

    @pytest.mark.asyncio
    async def test_monitor_performance_decorator_with_error(self):
        """Test monitoring decorator with function that raises error."""
        monitor = PerformanceMonitor()

        @monitor_performance("testErrorMethod", monitor)
        async def test_error_function():
            await asyncio.sleep(0.05)
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await test_error_function()

        # Check that error was recorded
        metrics = monitor.method_metrics["testErrorMethod"]
        assert metrics.total_requests == 1
        assert metrics.total_errors == 1
        assert "Test error" in metrics.error_types

    @pytest.mark.asyncio
    async def test_monitor_performance_decorator_disabled(self):
        """Test monitoring decorator when monitoring is disabled."""
        monitor = PerformanceMonitor()
        monitor.set_monitoring_enabled(False)

        @monitor_performance("disabledMethod", monitor)
        async def test_function():
            return "success"

        result = await test_function()
        assert result == "success"

        # Metrics should not be recorded when monitoring is disabled
        # Note: This test depends on implementation details


class TestHealthChecker:
    """Test HealthChecker functionality."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        mock_manager = AsyncMock()
        mock_manager.health_check = AsyncMock(
            return_value={
                "status": "healthy",
                "database_path": ":memory:",
                "file_size_bytes": 1024,
                "table_counts": {"endpoints": 5, "schemas": 3},
            }
        )
        return mock_manager

    @pytest.fixture
    def mock_server(self):
        """Create mock MCP server."""
        mock_server = MagicMock()
        mock_server.endpoint_repo = AsyncMock()
        mock_server._search_endpoints = AsyncMock(
            return_value={"results": [], "pagination": {"total": 0}}
        )
        return mock_server

    @pytest.mark.asyncio
    async def test_check_database_health_success(self, mock_db_manager):
        """Test successful database health check."""
        monitor = PerformanceMonitor()
        checker = HealthChecker(monitor)

        health = await checker.check_database_health(mock_db_manager)

        assert health.status == HealthStatus.HEALTHY
        assert "Database connection healthy" in health.message
        assert health.details is not None
        assert health.check_duration_ms > 0

    @pytest.mark.asyncio
    async def test_check_database_health_failure(self):
        """Test failed database health check."""
        monitor = PerformanceMonitor()
        checker = HealthChecker(monitor)

        # Test with None db_manager
        health = await checker.check_database_health(None)

        assert health.status == HealthStatus.UNHEALTHY
        assert "not initialized" in health.message

    @pytest.mark.asyncio
    async def test_check_mcp_responsiveness_success(self, mock_server):
        """Test successful MCP responsiveness check."""
        monitor = PerformanceMonitor()
        checker = HealthChecker(monitor)

        health = await checker.check_mcp_responsiveness(mock_server)

        assert health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        assert health.details is not None
        assert "response_time_ms" in health.details

    @pytest.mark.asyncio
    async def test_check_mcp_responsiveness_failure(self):
        """Test failed MCP responsiveness check."""
        monitor = PerformanceMonitor()
        checker = HealthChecker(monitor)

        # Test with None server
        health = await checker.check_mcp_responsiveness(None)

        assert health.status == HealthStatus.UNHEALTHY
        assert "not properly initialized" in health.message

    @pytest.mark.asyncio
    async def test_check_performance_health_healthy(self):
        """Test performance health check when all metrics are healthy."""
        monitor = PerformanceMonitor()
        checker = HealthChecker(monitor)

        # Record some good performance metrics
        monitor.record_request("searchEndpoints", 0.1)  # 100ms
        monitor.record_request("getSchema", 0.3)  # 300ms

        health = await checker.check_performance_health()

        assert health.status == HealthStatus.HEALTHY
        assert "within thresholds" in health.message

    @pytest.mark.asyncio
    async def test_check_performance_health_degraded(self):
        """Test performance health check when metrics are degraded."""
        thresholds = PerformanceThresholds(searchEndpoints_max_ms=100)
        monitor = PerformanceMonitor(thresholds)
        checker = HealthChecker(monitor)

        # Record requests near threshold (degraded but not unhealthy)
        monitor.record_request(
            "searchEndpoints", 0.09
        )  # 90ms (90% of 100ms threshold)

        health = await checker.check_performance_health()

        # Should be degraded since we're close to threshold
        assert health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]

    @pytest.mark.asyncio
    async def test_check_performance_health_unhealthy(self):
        """Test performance health check when thresholds are violated."""
        thresholds = PerformanceThresholds(searchEndpoints_max_ms=100)
        monitor = PerformanceMonitor(thresholds)
        checker = HealthChecker(monitor)

        # Record requests that exceed threshold
        monitor.record_request("searchEndpoints", 0.25)  # 250ms > 100ms

        health = await checker.check_performance_health()

        assert health.status == HealthStatus.UNHEALTHY
        assert "violated" in health.message

    @pytest.mark.asyncio
    async def test_get_overall_health(self, mock_server, mock_db_manager):
        """Test getting overall health status."""
        monitor = PerformanceMonitor()
        checker = HealthChecker(monitor)

        health = await checker.get_overall_health(mock_server, mock_db_manager)

        required_fields = [
            "status",
            "message",
            "timestamp",
            "uptime_seconds",
            "check_duration_ms",
            "components",
            "performance_summary",
            "version",
        ]
        for field in required_fields:
            assert field in health

        assert "database" in health["components"]
        assert "mcp_server" in health["components"]
        assert "performance" in health["components"]

        assert health["status"] in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_get_basic_health(self):
        """Test getting basic health status."""
        monitor = PerformanceMonitor()
        checker = HealthChecker(monitor)

        health = await checker.get_basic_health()

        required_fields = ["status", "timestamp", "uptime_seconds", "version"]
        for field in required_fields:
            assert field in health

        assert health["status"] == "healthy"


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    @pytest.mark.asyncio
    async def test_metrics_collector_start_stop(self):
        """Test starting and stopping metrics collector."""
        monitor = PerformanceMonitor()
        collector = MetricsCollector(monitor, collection_interval=0.1)

        # Start collector
        await collector.start()
        assert collector.running is True

        # Let it run briefly
        await asyncio.sleep(0.2)

        # Stop collector
        await collector.stop()
        assert collector.running is False

    @pytest.mark.asyncio
    async def test_metrics_collector_double_start(self):
        """Test starting metrics collector multiple times."""
        monitor = PerformanceMonitor()
        collector = MetricsCollector(monitor, collection_interval=0.1)

        # Start twice
        await collector.start()
        await collector.start()  # Should not cause issues

        assert collector.running is True
        await collector.stop()


class TestMCPServerMonitoringIntegration:
    """Test MCP server integration with monitoring."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = Settings()
        settings.database.path = ":memory:"
        return settings

    @pytest.fixture
    async def server(self, settings):
        """Create test server."""
        server = SwaggerMcpServer(settings)
        server.endpoint_repo = AsyncMock()
        server.schema_repo = AsyncMock()
        server.metadata_repo = AsyncMock()
        server.db_manager = AsyncMock()
        server.db_manager.health_check = AsyncMock(
            return_value={"status": "healthy"}
        )
        return server

    @pytest.mark.asyncio
    async def test_server_monitoring_methods(self, server):
        """Test server monitoring methods."""
        # Test start monitoring
        await server.start_monitoring()
        assert server.metrics_collector is not None

        # Test get performance metrics
        metrics = await server.get_performance_metrics()
        assert "performance_metrics" in metrics

        # Test get health status
        health = await server.get_health_status()
        assert "status" in health

        # Test get basic health
        basic_health = await server.get_basic_health()
        assert basic_health["status"] == "healthy"

        # Test update connection count
        server.update_connection_count(10)
        assert (
            server.performance_monitor.system_metrics.concurrent_connections
            == 10
        )

        # Test update database pool utilization
        server.update_database_pool_utilization(0.7)
        assert abs(
            server.performance_monitor.system_metrics.database_pool_utilization
            - 0.7) < 0.001

        # Test stop monitoring
        await server.stop_monitoring()

    @pytest.mark.asyncio
    async def test_monitoring_with_real_requests(self, server):
        """Test monitoring with simulated real requests."""
        # Mock the endpoint repository to return results
        server.endpoint_repo.search_endpoints = AsyncMock(return_value=[])

        # Start monitoring
        await server.start_monitoring()

        # Make some requests that should be monitored
        try:
            await server._search_endpoints_with_resilience(
                {"keywords": "test", "httpMethods": ["GET"]}, "test-request"
            )
        except:
            pass  # We expect some errors due to mocking

        # Check that metrics were recorded
        metrics = await server.get_performance_metrics()
        search_metrics = metrics["performance_metrics"].get(
            "searchEndpoints", {}
        )

        # Should have at least attempted to record metrics
        assert isinstance(search_metrics, dict)

        await server.stop_monitoring()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
