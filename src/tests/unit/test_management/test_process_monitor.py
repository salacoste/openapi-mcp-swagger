"""Tests for process monitoring functionality."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from swagger_mcp_server.management.process_monitor import (
    HealthCheck,
    HealthLevel,
    HealthStatus,
    ProcessMetrics,
    ProcessMonitor,
    ServerMetrics,
)


class TestProcessMonitor:
    """Test the ProcessMonitor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = ProcessMonitor()

    @pytest.mark.asyncio
    async def test_process_monitor_context_manager(self):
        """Test process monitor as async context manager."""
        async with ProcessMonitor() as monitor:
            assert monitor.session is not None
            assert isinstance(monitor.session, aiohttp.ClientSession)

    @pytest.mark.asyncio
    async def test_get_process_metrics_success(self):
        """Test successful process metrics retrieval."""
        mock_process = Mock()
        mock_process.cpu_percent.return_value = 25.5
        mock_process.memory_info.return_value = Mock(
            rss=1024 * 1024 * 100
        )  # 100MB
        mock_process.memory_percent.return_value = 15.2
        mock_process.num_threads.return_value = 8
        mock_process.connections.return_value = [
            Mock(),
            Mock(),
        ]  # 2 connections
        mock_process.create_time.return_value = (
            time.time() - 3600
        )  # 1 hour ago
        mock_process.status.return_value = "running"

        with patch(
            "swagger_mcp_server.management.process_monitor.psutil.Process",
            return_value=mock_process,
        ):
            metrics = await self.monitor.get_process_metrics(12345)

        assert metrics is not None
        assert metrics.cpu_percent == 25.5
        assert metrics.memory_mb == 100.0
        assert metrics.memory_percent == 15.2
        assert metrics.threads == 8
        assert metrics.connections == 2
        assert 3590 <= metrics.uptime_seconds <= 3610  # Around 1 hour
        assert metrics.status == "running"

    @pytest.mark.asyncio
    async def test_get_process_metrics_process_not_found(self):
        """Test process metrics when process doesn't exist."""
        with patch(
            "swagger_mcp_server.management.process_monitor.psutil.Process",
            side_effect=Exception("No such process"),
        ):
            metrics = await self.monitor.get_process_metrics(99999)

        assert metrics is None

    @pytest.mark.asyncio
    async def test_check_server_health_healthy(self):
        """Test health check for healthy server."""
        with patch.object(
            self.monitor, "_check_network_connectivity"
        ) as mock_network, patch.object(
            self.monitor, "_check_mcp_health"
        ) as mock_mcp, patch.object(
            self.monitor, "_check_response_time"
        ) as mock_response:
            # Mock all checks as healthy
            mock_network.return_value = HealthCheck(
                name="network",
                passed=True,
                level=HealthLevel.HEALTHY,
                message="Connection successful",
                duration_ms=50.0,
            )

            mock_mcp.return_value = HealthCheck(
                name="mcp",
                passed=True,
                level=HealthLevel.HEALTHY,
                message="MCP server healthy",
                duration_ms=100.0,
            )

            mock_response.return_value = HealthCheck(
                name="response_time",
                passed=True,
                level=HealthLevel.HEALTHY,
                message="Response time: 150ms",
                duration_ms=150.0,
            )

            health = await self.monitor.check_server_health(
                "localhost", 8080, "test-server"
            )

        assert health.overall_level == HealthLevel.HEALTHY
        assert len(health.checks) == 3
        assert len(health.issues) == 0
        assert health.is_healthy is True

    @pytest.mark.asyncio
    async def test_check_server_health_unhealthy(self):
        """Test health check for unhealthy server."""
        with patch.object(
            self.monitor, "_check_network_connectivity"
        ) as mock_network, patch.object(
            self.monitor, "_check_mcp_health"
        ) as mock_mcp, patch.object(
            self.monitor, "_check_response_time"
        ) as mock_response:
            # Mock network check as failed
            mock_network.return_value = HealthCheck(
                name="network",
                passed=False,
                level=HealthLevel.CRITICAL,
                message="Connection refused",
                duration_ms=5000.0,
            )

            mock_mcp.return_value = HealthCheck(
                name="mcp",
                passed=False,
                level=HealthLevel.WARNING,
                message="MCP endpoint timeout",
                duration_ms=10000.0,
            )

            mock_response.return_value = HealthCheck(
                name="response_time",
                passed=True,
                level=HealthLevel.HEALTHY,
                message="Response time: 100ms",
                duration_ms=100.0,
            )

            health = await self.monitor.check_server_health(
                "localhost", 8080, "test-server"
            )

        assert health.overall_level == HealthLevel.CRITICAL
        assert len(health.checks) == 3
        assert len(health.issues) == 2  # Network and MCP issues
        assert health.is_healthy is False

    @pytest.mark.asyncio
    async def test_network_connectivity_check_success(self):
        """Test successful network connectivity check."""
        # Mock successful socket connection
        with patch(
            "swagger_mcp_server.management.process_monitor.socket.socket"
        ) as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 0  # Success
            mock_socket.return_value = mock_sock

            check = await self.monitor._check_network_connectivity(
                "localhost", 8080
            )

        assert check.passed is True
        assert check.level == HealthLevel.HEALTHY
        assert "reachable" in check.message
        assert check.duration_ms is not None

    @pytest.mark.asyncio
    async def test_network_connectivity_check_failed(self):
        """Test failed network connectivity check."""
        # Mock failed socket connection
        with patch(
            "swagger_mcp_server.management.process_monitor.socket.socket"
        ) as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 1  # Failed
            mock_socket.return_value = mock_sock

            check = await self.monitor._check_network_connectivity(
                "localhost", 8080
            )

        assert check.passed is False
        assert check.level == HealthLevel.CRITICAL
        assert "Cannot connect" in check.message

    @pytest.mark.asyncio
    async def test_mcp_health_check_success(self):
        """Test successful MCP health check."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"status": "healthy", "version": "1.0"}
        )

        mock_session = Mock()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        self.monitor.session = mock_session

        check = await self.monitor._check_mcp_health("localhost", 8080)

        assert check.passed is True
        assert check.level == HealthLevel.HEALTHY
        assert "healthy" in check.message

    @pytest.mark.asyncio
    async def test_mcp_health_check_connection_error(self):
        """Test MCP health check with connection error."""
        mock_session = Mock()
        mock_session.get.side_effect = aiohttp.ClientConnectorError(None, None)

        self.monitor.session = mock_session

        check = await self.monitor._check_mcp_health("localhost", 8080)

        assert check.passed is False
        assert check.level == HealthLevel.CRITICAL
        assert "Cannot connect" in check.message

    @pytest.mark.asyncio
    async def test_response_time_check_excellent(self):
        """Test response time check with excellent performance."""
        mock_response = Mock()
        mock_response.status = 200

        mock_session = Mock()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        self.monitor.session = mock_session

        # Mock time to simulate fast response
        with patch(
            "swagger_mcp_server.management.process_monitor.time.time",
            side_effect=[0.0, 0.1],
        ):  # 100ms response
            check = await self.monitor._check_response_time("localhost", 8080)

        assert check.passed is True
        assert check.level == HealthLevel.HEALTHY
        assert "100.0ms" in check.message
        assert "excellent" in check.message

    @pytest.mark.asyncio
    async def test_response_time_check_slow(self):
        """Test response time check with slow performance."""
        mock_response = Mock()
        mock_response.status = 200

        mock_session = Mock()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        self.monitor.session = mock_session

        # Mock time to simulate slow response
        with patch(
            "swagger_mcp_server.management.process_monitor.time.time",
            side_effect=[0.0, 6.0],
        ):  # 6000ms response
            check = await self.monitor._check_response_time("localhost", 8080)

        assert check.passed is False
        assert check.level == HealthLevel.CRITICAL
        assert "6000.0ms" in check.message
        assert "very slow" in check.message

    @pytest.mark.asyncio
    async def test_get_server_metrics_success(self):
        """Test successful server metrics retrieval."""
        # Mock process metrics
        process_metrics = ProcessMetrics(
            cpu_percent=25.0,
            memory_mb=100.0,
            memory_percent=15.0,
            threads=8,
            connections=2,
            uptime_seconds=3600.0,
            status="running",
        )

        # Mock MCP metrics
        mcp_metrics = {
            "requests_total": 1000,
            "requests_per_minute": 50.0,
            "response_time_avg_ms": 150.0,
            "response_time_p95_ms": 300.0,
            "active_connections": 5,
            "error_rate": 0.01,
        }

        with patch.object(
            self.monitor, "get_process_metrics", return_value=process_metrics
        ), patch.object(
            self.monitor, "_get_mcp_metrics", return_value=mcp_metrics
        ):
            server_metrics = await self.monitor.get_server_metrics(
                12345, "localhost", 8080
            )

        assert server_metrics is not None
        assert server_metrics.process == process_metrics
        assert server_metrics.requests_total == 1000
        assert server_metrics.requests_per_minute == 50.0
        assert server_metrics.response_time_avg_ms == 150.0
        assert server_metrics.response_time_p95_ms == 300.0
        assert server_metrics.active_connections == 5
        assert server_metrics.error_rate == 0.01

    @pytest.mark.asyncio
    async def test_get_server_metrics_no_process(self):
        """Test server metrics when process doesn't exist."""
        with patch.object(
            self.monitor, "get_process_metrics", return_value=None
        ):
            server_metrics = await self.monitor.get_server_metrics(
                99999, "localhost", 8080
            )

        assert server_metrics is None


class TestHealthStatus:
    """Test the HealthStatus class."""

    def test_health_status_healthy(self):
        """Test healthy status."""
        checks = [
            HealthCheck("test1", True, HealthLevel.HEALTHY, "Good"),
            HealthCheck("test2", True, HealthLevel.HEALTHY, "Good"),
        ]

        status = HealthStatus(
            overall_level=HealthLevel.HEALTHY,
            checks=checks,
            timestamp=time.time(),
            issues=[],
        )

        assert status.is_healthy is True
        assert status.overall_level == HealthLevel.HEALTHY

    def test_health_status_warning(self):
        """Test warning status."""
        checks = [
            HealthCheck("test1", True, HealthLevel.HEALTHY, "Good"),
            HealthCheck("test2", False, HealthLevel.WARNING, "Slow"),
        ]

        status = HealthStatus(
            overall_level=HealthLevel.WARNING,
            checks=checks,
            timestamp=time.time(),
            issues=["Slow response"],
        )

        assert status.is_healthy is True  # Warning is still considered healthy
        assert status.overall_level == HealthLevel.WARNING

    def test_health_status_critical(self):
        """Test critical status."""
        checks = [
            HealthCheck("test1", False, HealthLevel.CRITICAL, "Failed"),
            HealthCheck("test2", True, HealthLevel.HEALTHY, "Good"),
        ]

        status = HealthStatus(
            overall_level=HealthLevel.CRITICAL,
            checks=checks,
            timestamp=time.time(),
            issues=["Connection failed"],
        )

        assert status.is_healthy is False
        assert status.overall_level == HealthLevel.CRITICAL

    def test_health_status_to_dict(self):
        """Test converting health status to dictionary."""
        checks = [
            HealthCheck(
                "test1",
                True,
                HealthLevel.HEALTHY,
                "Good",
                {"detail": "value"},
                100.0,
            )
        ]

        status = HealthStatus(
            overall_level=HealthLevel.HEALTHY,
            checks=checks,
            timestamp=1234567890.0,
            issues=[],
        )

        data = status.to_dict()

        assert data["overall_level"] == "healthy"
        assert len(data["checks"]) == 1
        assert data["checks"][0]["name"] == "test1"
        assert data["checks"][0]["passed"] is True
        assert data["checks"][0]["level"] == "healthy"
        assert data["checks"][0]["message"] == "Good"
        assert data["checks"][0]["details"] == {"detail": "value"}
        assert data["checks"][0]["duration_ms"] == 100.0
        assert data["timestamp"] == 1234567890.0
        assert data["issues"] == []
