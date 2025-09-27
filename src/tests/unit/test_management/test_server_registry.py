"""Tests for server registry functionality."""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from swagger_mcp_server.management.server_registry import (
    ServerInstance,
    ServerRegistry,
)


class TestServerRegistry:
    """Test the ServerRegistry class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.registry = ServerRegistry(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_register_server(self):
        """Test server registration."""
        server_info = {
            "name": "test-server",
            "host": "localhost",
            "port": 8080,
            "pid": 12345,
            "config_file": "/path/to/config.yaml",
            "working_directory": "/path/to/work",
            "api_title": "Test API",
        }

        instance = await self.registry.register_server(server_info)

        assert instance.name == "test-server"
        assert instance.host == "localhost"
        assert instance.port == 8080
        assert instance.pid == 12345
        assert instance.config_file == "/path/to/config.yaml"
        assert instance.working_directory == "/path/to/work"
        assert instance.api_title == "Test API"
        assert instance.status == "starting"
        assert instance.id.startswith("test-server-8080-")

    @pytest.mark.asyncio
    async def test_get_server(self):
        """Test retrieving server by ID."""
        server_info = {
            "name": "test-server",
            "host": "localhost",
            "port": 8080,
            "pid": 12345,
        }

        instance = await self.registry.register_server(server_info)
        retrieved = await self.registry.get_server(instance.id)

        assert retrieved is not None
        assert retrieved.id == instance.id
        assert retrieved.name == instance.name
        assert retrieved.port == instance.port

    @pytest.mark.asyncio
    async def test_get_server_not_found(self):
        """Test retrieving non-existent server."""
        result = await self.registry.get_server("non-existent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_servers(self):
        """Test retrieving all registered servers."""
        # Register multiple servers
        servers = []
        for i in range(3):
            server_info = {
                "name": f"test-server-{i}",
                "host": "localhost",
                "port": 8080 + i,
                "pid": 12345 + i,
            }
            instance = await self.registry.register_server(server_info)
            servers.append(instance)

        all_servers = await self.registry.get_all_servers()

        assert len(all_servers) == 3
        server_ids = [s.id for s in all_servers]
        for server in servers:
            assert server.id in server_ids

    @pytest.mark.asyncio
    async def test_get_servers_by_name(self):
        """Test retrieving servers by name."""
        # Register servers with same name
        for i in range(2):
            server_info = {
                "name": "test-server",
                "host": "localhost",
                "port": 8080 + i,
                "pid": 12345 + i,
            }
            await self.registry.register_server(server_info)

        # Register server with different name
        different_server = {
            "name": "other-server",
            "host": "localhost",
            "port": 9000,
            "pid": 54321,
        }
        await self.registry.register_server(different_server)

        servers = await self.registry.get_servers_by_name("test-server")
        assert len(servers) == 2

        for server in servers:
            assert server.name == "test-server"

    @pytest.mark.asyncio
    async def test_get_server_by_port(self):
        """Test retrieving server by port."""
        server_info = {
            "name": "test-server",
            "host": "localhost",
            "port": 8080,
            "pid": 12345,
        }

        await self.registry.register_server(server_info)
        server = await self.registry.get_server_by_port(8080)

        assert server is not None
        assert server.port == 8080
        assert server.name == "test-server"

        # Test non-existent port
        server = await self.registry.get_server_by_port(9999)
        assert server is None

    @pytest.mark.asyncio
    async def test_unregister_server(self):
        """Test server unregistration."""
        server_info = {
            "name": "test-server",
            "host": "localhost",
            "port": 8080,
            "pid": 12345,
        }

        instance = await self.registry.register_server(server_info)

        # Verify server exists
        retrieved = await self.registry.get_server(instance.id)
        assert retrieved is not None

        # Unregister server
        result = await self.registry.unregister_server(instance.id)
        assert result is True

        # Verify server is gone
        retrieved = await self.registry.get_server(instance.id)
        assert retrieved is None

        # Test unregistering non-existent server
        result = await self.registry.unregister_server("non-existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_server_status(self):
        """Test updating server status."""
        server_info = {
            "name": "test-server",
            "host": "localhost",
            "port": 8080,
            "pid": 12345,
        }

        instance = await self.registry.register_server(server_info)

        # Update status
        result = await self.registry.update_server_status(
            instance.id, "running"
        )
        assert result is True

        # Verify status was updated
        retrieved = await self.registry.get_server(instance.id)
        assert retrieved.status == "running"

        # Test updating non-existent server
        result = await self.registry.update_server_status(
            "non-existent", "running"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_is_port_available(self):
        """Test port availability checking."""
        # Port should be available initially
        available = await self.registry.is_port_available(8080)
        assert available is True

        # Register server on port
        server_info = {
            "name": "test-server",
            "host": "localhost",
            "port": 8080,
            "pid": 12345,
        }

        with patch(
            "swagger_mcp_server.management.server_registry.ServerRegistry._is_process_alive",
            return_value=True,
        ):
            await self.registry.register_server(server_info)

            # Port should not be available
            available = await self.registry.is_port_available(8080)
            assert available is False

    @pytest.mark.asyncio
    async def test_cleanup_dead_servers(self):
        """Test cleanup of dead server processes."""
        # Register multiple servers
        servers = []
        for i in range(3):
            server_info = {
                "name": f"test-server-{i}",
                "host": "localhost",
                "port": 8080 + i,
                "pid": 12345 + i,
            }
            instance = await self.registry.register_server(server_info)
            servers.append(instance)

        # Mock process checks - first server is dead, others alive
        def mock_is_process_alive(pid):
            return pid != 12345  # First server is dead

        with patch.object(
            self.registry,
            "_is_process_alive",
            side_effect=mock_is_process_alive,
        ):
            removed_ids = await self.registry.cleanup_dead_servers()

        assert len(removed_ids) == 1
        assert servers[0].id in removed_ids

        # Verify dead server was removed
        remaining_servers = await self.registry.get_all_servers()
        assert len(remaining_servers) == 2


class TestServerInstance:
    """Test the ServerInstance class."""

    def test_server_instance_creation(self):
        """Test creating server instance."""
        instance = ServerInstance(
            id="test-id",
            name="test-server",
            host="localhost",
            port=8080,
            pid=12345,
            start_time=time.time(),
            config_file="/path/to/config.yaml",
            api_title="Test API",
        )

        assert instance.id == "test-id"
        assert instance.name == "test-server"
        assert instance.host == "localhost"
        assert instance.port == 8080
        assert instance.pid == 12345
        assert instance.config_file == "/path/to/config.yaml"
        assert instance.api_title == "Test API"

    def test_server_instance_uptime(self):
        """Test uptime calculation."""
        start_time = time.time() - 100  # 100 seconds ago
        instance = ServerInstance(
            id="test-id",
            name="test-server",
            host="localhost",
            port=8080,
            pid=12345,
            start_time=start_time,
        )

        uptime = instance.uptime
        assert 99 <= uptime <= 101  # Should be around 100 seconds

    def test_server_instance_url(self):
        """Test URL generation."""
        instance = ServerInstance(
            id="test-id",
            name="test-server",
            host="localhost",
            port=8080,
            pid=12345,
            start_time=time.time(),
        )

        assert instance.url == "http://localhost:8080"

    def test_server_instance_to_dict(self):
        """Test dictionary conversion."""
        start_time = time.time()
        instance = ServerInstance(
            id="test-id",
            name="test-server",
            host="localhost",
            port=8080,
            pid=12345,
            start_time=start_time,
            config_file="/path/to/config.yaml",
        )

        data = instance.to_dict()

        assert data["id"] == "test-id"
        assert data["name"] == "test-server"
        assert data["host"] == "localhost"
        assert data["port"] == 8080
        assert data["pid"] == 12345
        assert data["start_time"] == start_time
        assert data["config_file"] == "/path/to/config.yaml"

    def test_server_instance_from_dict(self):
        """Test creating instance from dictionary."""
        data = {
            "id": "test-id",
            "name": "test-server",
            "host": "localhost",
            "port": 8080,
            "pid": 12345,
            "start_time": time.time(),
            "config_file": "/path/to/config.yaml",
            "status": "running",
        }

        instance = ServerInstance.from_dict(data)

        assert instance.id == "test-id"
        assert instance.name == "test-server"
        assert instance.host == "localhost"
        assert instance.port == 8080
        assert instance.pid == 12345
        assert instance.config_file == "/path/to/config.yaml"
        assert instance.status == "running"
