"""Unit tests for MCP server implementation."""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swagger_mcp_server.config.settings import Settings
from swagger_mcp_server.server.mcp_server_v2 import (
    SwaggerMcpServer,
    create_server,
)
from swagger_mcp_server.storage.models import APIMetadata, Endpoint, Schema


class TestSwaggerMcpServer:
    """Test cases for SwaggerMcpServer class."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = Settings()
        settings.database.path = ":memory:"  # Use in-memory database for tests
        settings.server.name = "test-server"
        settings.server.version = "0.1.0"
        return settings

    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        mock_manager = AsyncMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.health_check = AsyncMock(
            return_value={
                "status": "healthy",
                "database_path": ":memory:",
                "file_size_bytes": 1024,
                "table_counts": {"endpoints": 5, "schemas": 3},
            }
        )
        mock_manager.close = AsyncMock()
        return mock_manager

    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories."""
        endpoint_repo = AsyncMock()
        schema_repo = AsyncMock()
        metadata_repo = AsyncMock()

        # Mock endpoint data
        mock_endpoint = MagicMock()
        mock_endpoint.id = "test-endpoint-1"
        mock_endpoint.path = "/api/test"
        mock_endpoint.method = "GET"
        mock_endpoint.summary = "Test endpoint"
        mock_endpoint.description = "Test endpoint description"
        mock_endpoint.operation_id = "getTest"
        mock_endpoint.tags = ["test"]
        mock_endpoint.parameters = []
        mock_endpoint.responses = {}

        endpoint_repo.search_endpoints = AsyncMock(
            return_value=[mock_endpoint]
        )
        endpoint_repo.get_endpoint_by_id = AsyncMock(
            return_value=mock_endpoint
        )

        # Mock schema data
        mock_schema = MagicMock()
        mock_schema.id = "test-schema-1"
        mock_schema.name = "TestSchema"
        mock_schema.type = "object"
        mock_schema.properties = {"id": {"type": "string"}}
        mock_schema.description = "Test schema"
        mock_schema.required = ["id"]
        mock_schema.example = {"id": "example-123"}

        schema_repo.get_schema_by_name = AsyncMock(return_value=mock_schema)

        # Mock metadata
        mock_metadata = APIMetadata(
            id=1,
            title="Test API",
            version="1.0.0",
            openapi_version="3.0.0",
            description="Test API description",
        )

        metadata_repo.get_all_metadata = AsyncMock(
            return_value=[mock_metadata]
        )

        return endpoint_repo, schema_repo, metadata_repo

    @pytest.fixture
    async def server(self, settings, mock_db_manager, mock_repositories):
        """Create test server with mocked dependencies."""
        with patch(
            "swagger_mcp_server.server.mcp_server_v2.DatabaseManager",
            return_value=mock_db_manager,
        ):
            server = SwaggerMcpServer(settings)

            # Inject mock repositories
            endpoint_repo, schema_repo, metadata_repo = mock_repositories
            server.endpoint_repo = endpoint_repo
            server.schema_repo = schema_repo
            server.metadata_repo = metadata_repo
            server.db_manager = mock_db_manager

            return server

    def test_server_creation(self, settings):
        """Test server can be created with settings."""
        server = SwaggerMcpServer(settings)
        assert server.settings == settings
        assert server.server is not None

    def test_create_server_function(self):
        """Test create_server function works with default and custom settings."""
        # Test with default settings
        server1 = create_server()
        assert server1 is not None
        assert isinstance(server1, SwaggerMcpServer)

        # Test with custom settings
        custom_settings = Settings()
        custom_settings.server.name = "custom-server"
        server2 = create_server(custom_settings)
        assert server2.settings.server.name == "custom-server"

    @pytest.mark.asyncio
    async def test_server_initialization(self, server, mock_db_manager):
        """Test server initialization process."""
        await server.initialize()

        # Verify database manager was initialized
        mock_db_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_endpoints(self, server):
        """Test searchEndpoints functionality."""
        result = await server._search_endpoints(
            query="test", method="GET", limit=10
        )

        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == "test-endpoint-1"
        assert result["results"][0]["path"] == "/api/test"
        assert result["results"][0]["method"] == "GET"

        # Verify repository was called correctly
        server.endpoint_repo.search_endpoints.assert_called_once_with(
            query="test", methods=["GET"], limit=10
        )

    @pytest.mark.asyncio
    async def test_search_endpoints_no_repository(self, settings):
        """Test searchEndpoints when repository is not initialized."""
        server = SwaggerMcpServer(settings)
        # Don't initialize repositories

        result = await server._search_endpoints(query="test")
        assert "error" in result
        assert "not properly initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_get_schema(self, server):
        """Test getSchema functionality."""
        result = await server._get_schema(
            schema_name="TestSchema", include_examples=True
        )

        assert result["name"] == "TestSchema"
        assert result["type"] == "object"
        assert "properties" in result
        assert "examples" in result

        # Verify repository was called correctly
        server.schema_repo.get_schema_by_name.assert_called_once_with(
            "TestSchema"
        )

    @pytest.mark.asyncio
    async def test_get_schema_not_found(self, server):
        """Test getSchema when schema is not found."""
        server.schema_repo.get_schema_by_name = AsyncMock(return_value=None)

        result = await server._get_schema(schema_name="NonExistentSchema")
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_example(self, server):
        """Test getExample functionality."""
        result = await server._get_example(
            endpoint_id="test-endpoint-1", language="curl"
        )

        assert result["endpoint_id"] == "test-endpoint-1"
        assert result["language"] == "curl"
        assert result["method"] == "GET"
        assert result["path"] == "/api/test"
        assert "example" in result

        # Verify repository was called correctly
        server.endpoint_repo.get_endpoint_by_id.assert_called_once_with(
            "test-endpoint-1"
        )

    @pytest.mark.asyncio
    async def test_get_example_not_found(self, server):
        """Test getExample when endpoint is not found."""
        server.endpoint_repo.get_endpoint_by_id = AsyncMock(return_value=None)

        result = await server._get_example(endpoint_id="non-existent")
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_api_info(self, server):
        """Test API info retrieval."""
        result = await server._get_api_info()

        assert "Test API v1.0.0" in result
        assert "Test API description" in result

        # Verify repository was called
        server.metadata_repo.get_all_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_api_info_no_metadata(self, server):
        """Test API info when no metadata is available."""
        server.metadata_repo.get_all_metadata = AsyncMock(return_value=[])

        result = await server._get_api_info()
        assert "No API documentation loaded" in result

    @pytest.mark.asyncio
    async def test_get_health_status(self, server, mock_db_manager):
        """Test health status retrieval."""
        result = await server._get_health_status()

        assert "Server Status: test-server v0.1.0" in result
        assert "Database Status: healthy" in result
        assert "endpoints: 5" in result

        # Verify database health check was called
        mock_db_manager.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup(self, server, mock_db_manager):
        """Test server cleanup process."""
        await server.cleanup()

        # Verify database manager was closed
        mock_db_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_context_manager(self, server, mock_db_manager):
        """Test server lifespan context manager."""
        async with server.lifespan() as ctx_server:
            assert ctx_server == server
            # Verify initialization was called
            mock_db_manager.initialize.assert_called_once()

        # Verify cleanup was called
        mock_db_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_in_search(self, server):
        """Test error handling in search methods."""
        # Make repository raise an exception
        server.endpoint_repo.search_endpoints = AsyncMock(
            side_effect=Exception("Database error")
        )

        result = await server._search_endpoints(query="test")
        assert "error" in result
        assert "Database error" in result["error"]

    @pytest.mark.asyncio
    async def test_error_handling_in_schema_retrieval(self, server):
        """Test error handling in schema retrieval."""
        # Make repository raise an exception
        server.schema_repo.get_schema_by_name = AsyncMock(
            side_effect=Exception("Schema error")
        )

        result = await server._get_schema(schema_name="TestSchema")
        assert "error" in result
        assert "Schema error" in result["error"]


class TestMcpServerIntegration:
    """Integration tests for MCP server functionality."""

    @pytest.mark.asyncio
    async def test_server_tools_registration(self):
        """Test that server tools are properly registered."""
        server = create_server()

        # Access the registered handlers through the server
        assert hasattr(server.server, "_tools_handler")

        # This would be tested more thoroughly in integration tests
        # with actual MCP client connections

    @pytest.mark.asyncio
    async def test_server_resources_registration(self):
        """Test that server resources are properly registered."""
        server = create_server()

        # Access the registered handlers through the server
        assert hasattr(server.server, "_resources_handler")

        # This would be tested more thoroughly in integration tests
        # with actual MCP client connections


@pytest.mark.performance
class TestMcpServerPerformance:
    """Performance tests for MCP server."""

    @pytest.mark.asyncio
    async def test_initialization_time(self, benchmark):
        """Test server initialization performance."""
        settings = Settings()
        settings.database.path = ":memory:"

        def create_and_init():
            server = SwaggerMcpServer(settings)
            return server

        # Benchmark server creation (initialization happens async)
        server = benchmark(create_and_init)
        assert server is not None

    @pytest.mark.asyncio
    async def test_search_performance(self, benchmark):
        """Test search operation performance."""
        # This would be implemented with real data
        # to test search performance under load
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
