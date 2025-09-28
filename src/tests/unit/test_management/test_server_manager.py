"""Tests for server manager functionality."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from swagger_mcp_server.management.server_manager import (
    MCPServerManager,
    ServerError,
)
from swagger_mcp_server.management.server_registry import ServerInstance


class TestMCPServerManager:
    """Test the MCPServerManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = MCPServerManager(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_start_server_daemon_mode_success(self):
        """Test successful daemon server startup."""
        server_config = {
            "name": "test-server",
            "host": "localhost",
            "port": 8080,
            "working_directory": str(self.temp_dir),
        }

        # Mock daemon manager
        mock_daemon_result = {
            "server_id": "test-server-id",
            "pid": 12345,
            "host": "localhost",
            "port": 8080,
            "daemon": True,
        }

        with (
            patch.object(self.manager, "_validate_server_config"),
            patch.object(self.manager.registry, "is_port_available", return_value=True),
            patch.object(self.manager.registry, "cleanup_dead_servers"),
            patch.object(
                self.manager.daemon_manager,
                "start_daemon_server",
                return_value=mock_daemon_result,
            ),
            patch.object(self.manager.registry, "register_server") as mock_register,
            patch.object(self.manager, "_wait_for_server_ready"),
            patch.object(self.manager.registry, "update_server_status"),
        ):
            mock_register.return_value = ServerInstance(
                id="test-server-id",
                name="test-server",
                host="localhost",
                port=8080,
                pid=12345,
                start_time=1234567890.0,
            )

            result = await self.manager.start_server(server_config, daemon=True)

        assert result["status"] == "started"
        assert result["server_id"] == "test-server-id"
        assert result["process_id"] == 12345
        assert result["daemon"] is True

    @pytest.mark.asyncio
    async def test_start_server_port_in_use(self):
        """Test server startup when port is in use."""
        server_config = {
            "name": "test-server",
            "host": "localhost",
            "port": 8080,
        }

        with (
            patch.object(self.manager, "_validate_server_config"),
            patch.object(
                self.manager.registry, "is_port_available", return_value=False
            ),
        ):
            with pytest.raises(ServerError) as exc_info:
                await self.manager.start_server(server_config)

            assert "Port 8080 is already in use" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_server_config_missing_fields(self):
        """Test server configuration validation with missing fields."""
        incomplete_config = {
            "name": "test-server",
            "host": "localhost",
            # Missing port
        }

        with pytest.raises(ServerError) as exc_info:
            await self.manager._validate_server_config(incomplete_config)

        assert "Missing required configuration: port" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_server_config_invalid_port(self):
        """Test server configuration validation with invalid port."""
        invalid_config = {
            "name": "test-server",
            "host": "localhost",
            "port": 99999,  # Invalid port
        }

        with pytest.raises(ServerError) as exc_info:
            await self.manager._validate_server_config(invalid_config)

        assert "Invalid port number: 99999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stop_server_success(self):
        """Test successful server stop."""
        # Mock server instance
        server_instance = ServerInstance(
            id="test-server-id",
            name="test-server",
            host="localhost",
            port=8080,
            pid=12345,
            start_time=1234567890.0,
        )

        with (
            patch.object(
                self.manager.registry, "get_server", return_value=server_instance
            ),
            patch.object(self.manager.registry, "update_server_status"),
            patch.object(self.manager, "_stop_daemon_server", return_value=True),
            patch.object(self.manager.registry, "unregister_server"),
        ):
            result = await self.manager.stop_server("test-server-id")

        assert result["status"] == "stopped"
        assert result["server_id"] == "test-server-id"
        assert "shutdown_time" in result

    @pytest.mark.asyncio
    async def test_stop_server_not_found(self):
        """Test stopping non-existent server."""
        with patch.object(self.manager.registry, "get_server", return_value=None):
            with pytest.raises(ServerError) as exc_info:
                await self.manager.stop_server("non-existent-id")

            assert "Server 'non-existent-id' not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_server_status_success(self):
        """Test successful server status retrieval."""
        # Mock server instance
        server_instance = ServerInstance(
            id="test-server-id",
            name="test-server",
            host="localhost",
            port=8080,
            pid=12345,
            start_time=1234567890.0,
        )

        # Mock process metrics
        from swagger_mcp_server.management.process_monitor import (
            HealthLevel,
            HealthStatus,
            ProcessMetrics,
        )

        process_metrics = ProcessMetrics(
            cpu_percent=25.0,
            memory_mb=100.0,
            memory_percent=15.0,
            threads=8,
            connections=2,
            uptime_seconds=3600.0,
            status="running",
        )

        health_status = HealthStatus(
            overall_level=HealthLevel.HEALTHY,
            checks=[],
            timestamp=1234567890.0,
            issues=[],
        )

        with (
            patch.object(
                self.manager.registry, "get_server", return_value=server_instance
            ),
            patch.object(
                self.manager.process_monitor,
                "get_process_metrics",
                return_value=process_metrics,
            ),
            patch.object(
                self.manager.process_monitor,
                "check_server_health",
                return_value=health_status,
            ),
            patch.object(
                self.manager.process_monitor,
                "get_server_metrics",
                return_value=None,
            ),
            patch.object(self.manager.registry, "update_server_status"),
        ):
            status = await self.manager.get_server_status("test-server-id")

        assert status["server"]["id"] == "test-server-id"
        assert status["health"]["overall_level"] == "healthy"
        assert status["metrics"]["process"]["cpu_percent"] == 25.0

    @pytest.mark.asyncio
    async def test_get_server_status_process_not_found(self):
        """Test server status when process is dead."""
        # Mock server instance
        server_instance = ServerInstance(
            id="test-server-id",
            name="test-server",
            host="localhost",
            port=8080,
            pid=12345,
            start_time=1234567890.0,
        )

        with (
            patch.object(
                self.manager.registry, "get_server", return_value=server_instance
            ),
            patch.object(
                self.manager.process_monitor,
                "get_process_metrics",
                return_value=None,
            ),
            patch.object(self.manager.registry, "update_server_status"),
        ):
            status = await self.manager.get_server_status("test-server-id")

        assert status["status"] == "stopped"
        assert "Process not found" in status["message"]

    @pytest.mark.asyncio
    async def test_get_all_servers_status(self):
        """Test getting status for all servers."""
        # Mock server instances
        servers = [
            ServerInstance(
                id="server-1",
                name="test-server-1",
                host="localhost",
                port=8080,
                pid=12345,
                start_time=1234567890.0,
            ),
            ServerInstance(
                id="server-2",
                name="test-server-2",
                host="localhost",
                port=8081,
                pid=12346,
                start_time=1234567890.0,
            ),
        ]

        with (
            patch.object(self.manager.registry, "cleanup_dead_servers"),
            patch.object(
                self.manager.registry, "get_all_servers", return_value=servers
            ),
            patch.object(self.manager, "get_server_status") as mock_get_status,
        ):
            # Mock individual status calls
            mock_get_status.side_effect = [
                {"server": {"id": "server-1"}, "status": "running"},
                {"server": {"id": "server-2"}, "status": "running"},
            ]

            status_list = await self.manager.get_all_servers_status()

        assert len(status_list) == 2
        assert status_list[0]["server"]["id"] == "server-1"
        assert status_list[1]["server"]["id"] == "server-2"

    @pytest.mark.asyncio
    async def test_restart_server_success(self):
        """Test successful server restart."""
        # Mock server instance
        server_instance = ServerInstance(
            id="test-server-id",
            name="test-server",
            host="localhost",
            port=8080,
            pid=12345,
            start_time=1234567890.0,
            config_file="/path/to/config.yaml",
        )

        mock_stop_result = {
            "status": "stopped",
            "server_id": "test-server-id",
            "shutdown_time": 2.5,
        }

        mock_start_result = {
            "status": "started",
            "server_id": "new-server-id",
            "startup_time": 1.2,
        }

        with (
            patch.object(
                self.manager.registry, "get_server", return_value=server_instance
            ),
            patch.object(self.manager, "stop_server", return_value=mock_stop_result),
            patch.object(self.manager, "start_server", return_value=mock_start_result),
        ):
            result = await self.manager.restart_server("test-server-id")

        assert result["status"] == "restarted"
        assert result["old_server_id"] == "test-server-id"
        assert result["new_server_id"] == "new-server-id"
        assert result["stop_time"] == 2.5
        assert result["start_time"] == 1.2

    @pytest.mark.asyncio
    async def test_wait_for_server_ready_success(self):
        """Test waiting for server to be ready."""
        # Mock successful socket connection
        with patch(
            "swagger_mcp_server.management.server_manager.socket.socket"
        ) as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 0  # Success
            mock_socket.return_value = mock_sock

            # Should not raise exception
            await self.manager._wait_for_server_ready("localhost", 8080, timeout=1)

    @pytest.mark.asyncio
    async def test_wait_for_server_ready_timeout(self):
        """Test timeout when waiting for server."""
        # Mock failed socket connection
        with patch(
            "swagger_mcp_server.management.server_manager.socket.socket"
        ) as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 1  # Failed
            mock_socket.return_value = mock_sock

            with pytest.raises(ServerError) as exc_info:
                await self.manager._wait_for_server_ready("localhost", 8080, timeout=1)

            assert "did not become ready" in str(exc_info.value)


class TestServerError:
    """Test the ServerError class."""

    def test_server_error_basic(self):
        """Test basic ServerError creation."""
        error = ServerError("Test error message")

        assert error.message == "Test error message"
        assert error.suggestion is None
        assert error.details == {}
        assert str(error) == "Test error message"

    def test_server_error_with_suggestion(self):
        """Test ServerError with suggestion."""
        error = ServerError("Test error", "Try this solution")

        assert error.message == "Test error"
        assert error.suggestion == "Try this solution"

    def test_server_error_with_details(self):
        """Test ServerError with details."""
        details = {"code": 500, "context": "startup"}
        error = ServerError("Test error", "Try solution", details)

        assert error.message == "Test error"
        assert error.suggestion == "Try solution"
        assert error.details == details
