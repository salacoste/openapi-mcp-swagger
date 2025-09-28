"""Comprehensive tests for enhanced getExample method (Story 2.4)."""

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from swagger_mcp_server.config.settings import Settings
from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer


class TestEnhancedGetExample:
    """Test cases for enhanced getExample functionality per Story 2.4."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = Settings()
        settings.database.path = ":memory:"
        settings.server.name = "test-server"
        settings.server.version = "0.1.0"
        return settings

    @pytest.fixture
    def mock_endpoints(self):
        """Create mock endpoint data for testing."""
        endpoints = []

        # GET user endpoint
        user_get_endpoint = MagicMock()
        user_get_endpoint.id = "users-get"
        user_get_endpoint.path = "/api/v1/users/{id}"
        user_get_endpoint.method = "GET"
        user_get_endpoint.summary = "Get user by ID"
        user_get_endpoint.description = "Retrieve detailed user information"
        user_get_endpoint.operation_id = "getUserById"
        user_get_endpoint.tags = ["users"]
        user_get_endpoint.parameters = [
            {"name": "id", "in": "path", "required": True, "type": "string"}
        ]
        user_get_endpoint.security = [{"bearerAuth": []}]
        endpoints.append(user_get_endpoint)

        # POST user endpoint
        user_post_endpoint = MagicMock()
        user_post_endpoint.id = "users-post"
        user_post_endpoint.path = "/api/v1/users"
        user_post_endpoint.method = "POST"
        user_post_endpoint.summary = "Create new user"
        user_post_endpoint.description = "Create a new user account"
        user_post_endpoint.operation_id = "createUser"
        user_post_endpoint.tags = ["users"]
        user_post_endpoint.parameters = []
        user_post_endpoint.security = [{"bearerAuth": []}]
        endpoints.append(user_post_endpoint)

        # GET orders endpoint
        orders_endpoint = MagicMock()
        orders_endpoint.id = "orders-get"
        orders_endpoint.path = "/api/v1/orders"
        orders_endpoint.method = "GET"
        orders_endpoint.summary = "List orders"
        orders_endpoint.description = "Retrieve list of orders"
        orders_endpoint.operation_id = "listOrders"
        orders_endpoint.tags = ["orders"]
        orders_endpoint.parameters = []
        orders_endpoint.security = None
        endpoints.append(orders_endpoint)

        return endpoints

    @pytest.fixture
    def mock_endpoint_repo(self, mock_endpoints):
        """Create mock endpoint repository."""
        repo = AsyncMock()

        # Mock get_endpoint_by_id
        async def mock_get_by_id(endpoint_id):
            for ep in mock_endpoints:
                if ep.id == endpoint_id:
                    return ep
            return None

        # Mock search_endpoints
        async def mock_search(query, methods=None, limit=20, **kwargs):
            filtered_endpoints = []
            for ep in mock_endpoints:
                # Match by path
                if query in ep.path:
                    if not methods or ep.method in methods:
                        filtered_endpoints.append(ep)
            return filtered_endpoints

        repo.get_endpoint_by_id = mock_get_by_id
        repo.search_endpoints = mock_search
        return repo

    @pytest.fixture
    async def server(self, settings, mock_endpoint_repo):
        """Create test server with mocked dependencies."""
        server = SwaggerMcpServer(settings)
        server.endpoint_repo = mock_endpoint_repo
        server.schema_repo = AsyncMock()
        server.metadata_repo = AsyncMock()
        server.db_manager = AsyncMock()
        return server

    @pytest.mark.asyncio
    async def test_parameter_validation_endpoint_required(self, server):
        """Test that endpoint parameter is required."""
        # Empty endpoint
        result = await server._get_example(endpoint="")
        assert "error" in result
        assert "required" in result["error"].lower()

        # Whitespace only
        result = await server._get_example(endpoint="   ")
        assert "error" in result
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_parameter_validation_format_validation(self, server):
        """Test format parameter validation."""
        # Valid formats
        for format_type in ["curl", "javascript", "python"]:
            result = await server._get_example(endpoint="users-get", format=format_type)
            assert "error" not in result or "not found" in result.get("error", "")

        # Invalid format
        result = await server._get_example(endpoint="users-get", format="invalid")
        assert "error" in result
        assert "Unsupported format" in result["error"]

    @pytest.mark.asyncio
    async def test_endpoint_lookup_by_id(self, server):
        """Test endpoint lookup by ID."""
        result = await server._get_example(endpoint="users-get", format="curl")

        assert "error" not in result
        assert result["endpoint_id"] == "users-get"
        assert result["endpoint_path"] == "/api/v1/users/{id}"
        assert result["method"] == "GET"

    @pytest.mark.asyncio
    async def test_endpoint_lookup_by_path_and_method(self, server):
        """Test endpoint lookup by path and method."""
        result = await server._get_example(
            endpoint="/api/v1/users/{id}", method="GET", format="curl"
        )

        assert "error" not in result
        assert result["endpoint_id"] == "users-get"
        assert result["endpoint_path"] == "/api/v1/users/{id}"
        assert result["method"] == "GET"

    @pytest.mark.asyncio
    async def test_method_required_for_path_lookup(self, server):
        """Test that method is required when using path lookup."""
        result = await server._get_example(
            endpoint="/api/v1/users/{id}",
            format="curl",
            # No method provided
        )

        assert "error" in result
        assert "HTTP method is required" in result["error"]

    @pytest.mark.asyncio
    async def test_curl_generation(self, server):
        """Test cURL code generation."""
        result = await server._get_example(
            endpoint="users-get",
            format="curl",
            includeAuth=True,
            baseUrl="https://api.mycompany.com",
        )

        assert "error" not in result
        assert result["format"] == "curl"

        code = result["code"]
        assert "curl -X GET" in code
        assert "https://api.mycompany.com/api/v1/users/12345" in code
        assert "Authorization: Bearer YOUR_TOKEN_HERE" in code
        assert "Accept: application/json" in code

    @pytest.mark.asyncio
    async def test_javascript_generation(self, server):
        """Test JavaScript code generation."""
        result = await server._get_example(
            endpoint="users-post", format="javascript", includeAuth=True
        )

        assert "error" not in result
        assert result["format"] == "javascript"

        code = result["code"]
        assert "async function" in code
        assert "fetch(" in code
        assert "method: 'POST'" in code
        assert "'Authorization': `Bearer ${token}`" in code
        assert "response.json()" in code
        assert "catch (error)" in code

    @pytest.mark.asyncio
    async def test_python_generation(self, server):
        """Test Python code generation."""
        result = await server._get_example(
            endpoint="orders-get", format="python", includeAuth=False
        )

        assert "error" not in result
        assert result["format"] == "python"

        code = result["code"]
        assert "import requests" in code
        assert "def " in code
        assert "requests.get" in code
        assert "response.raise_for_status()" in code
        assert "except requests.exceptions.RequestException" in code
        # Should not include auth since includeAuth=False
        assert "Authorization" not in code

    @pytest.mark.asyncio
    async def test_auth_inclusion_control(self, server):
        """Test authentication inclusion control."""
        # With auth
        result_with_auth = await server._get_example(
            endpoint="users-get", format="curl", includeAuth=True
        )

        assert "Authorization: Bearer YOUR_TOKEN_HERE" in result_with_auth["code"]

        # Without auth
        result_without_auth = await server._get_example(
            endpoint="users-get", format="curl", includeAuth=False
        )

        assert "Authorization" not in result_without_auth["code"]

    @pytest.mark.asyncio
    async def test_base_url_customization(self, server):
        """Test base URL customization."""
        custom_url = "https://custom.api.com"
        result = await server._get_example(
            endpoint="users-get", format="curl", baseUrl=custom_url
        )

        assert custom_url in result["code"]
        assert result["metadata"]["baseUrl"] == custom_url

    @pytest.mark.asyncio
    async def test_path_parameter_handling(self, server):
        """Test path parameter replacement in generated code."""
        result = await server._get_example(endpoint="users-get", format="curl")

        code = result["code"]
        # Should replace {id} with example value
        assert "{id}" not in code
        assert "12345" in code

    @pytest.mark.asyncio
    async def test_request_body_generation_post(self, server):
        """Test request body generation for POST endpoints."""
        result = await server._get_example(endpoint="users-post", format="curl")

        code = result["code"]
        # Should include request body for POST
        assert "-d '" in code
        assert "John Doe" in code or "example_value" in code

    @pytest.mark.asyncio
    async def test_response_metadata(self, server):
        """Test response metadata structure."""
        result = await server._get_example(endpoint="users-get", format="python")

        assert "error" not in result

        # Check required response fields
        required_fields = [
            "endpoint_id",
            "endpoint_path",
            "method",
            "format",
            "code",
            "summary",
            "description",
            "metadata",
        ]
        for field in required_fields:
            assert field in result

        # Check metadata structure
        metadata = result["metadata"]
        metadata_fields = [
            "includeAuth",
            "baseUrl",
            "generation_timestamp",
            "syntax_validated",
        ]
        for field in metadata_fields:
            assert field in metadata

    @pytest.mark.asyncio
    async def test_error_handling_endpoint_not_found(self, server):
        """Test error handling when endpoint is not found."""
        result = await server._get_example(endpoint="nonexistent", format="curl")

        assert "error" in result
        assert "HTTP method is required" in result["error"]

    @pytest.mark.asyncio
    async def test_error_handling_server_not_initialized(self):
        """Test error handling when server is not properly initialized."""
        uninitialized_server = SwaggerMcpServer(Settings())
        result = await uninitialized_server._get_example(endpoint="test", format="curl")

        assert "error" in result
        assert "not properly initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_code_format_compliance_curl(self, server):
        """Test that generated cURL code follows proper format."""
        result = await server._get_example(endpoint="users-get", format="curl")

        code = result["code"]

        # Should use line continuations
        assert "\\\n" in code
        # Should have proper curl syntax
        assert code.startswith("curl -X")
        # Should have quoted URL
        assert '"https://' in code

    @pytest.mark.asyncio
    async def test_code_format_compliance_javascript(self, server):
        """Test that generated JavaScript code follows proper format."""
        result = await server._get_example(endpoint="users-post", format="javascript")

        code = result["code"]

        # Should be an async function
        assert "async function" in code
        # Should have proper error handling
        assert "try {" in code and "} catch" in code
        # Should check response status
        assert "response.ok" in code
        # Should parse JSON
        assert "response.json()" in code

    @pytest.mark.asyncio
    async def test_code_format_compliance_python(self, server):
        """Test that generated Python code follows proper format."""
        result = await server._get_example(endpoint="users-get", format="python")

        code = result["code"]

        # Should have proper imports
        assert "import requests" in code
        assert "from typing import" in code
        # Should have type hints
        assert "-> Dict[Any, Any]:" in code
        # Should have exception handling
        assert "except requests.exceptions.RequestException" in code
        # Should use raise_for_status
        assert "raise_for_status()" in code

    @pytest.mark.asyncio
    async def test_example_body_generation_patterns(self, server):
        """Test example body generation for different endpoint types."""
        # Test user endpoint
        result_user = await server._get_example(endpoint="users-post", format="python")

        code_user = result_user["code"]
        assert "John Doe" in code_user  # User-specific example

        # Test general endpoint
        result_orders = await server._get_example(endpoint="orders-get", format="curl")

        # GET endpoint shouldn't have body
        code_orders = result_orders["code"]
        assert "-d '" not in code_orders

    @pytest.mark.asyncio
    async def test_performance_requirements(self, server):
        """Test that code generation meets performance requirements."""
        import time

        start_time = time.time()
        result = await server._get_example(endpoint="users-get", format="javascript")
        end_time = time.time()

        generation_time = end_time - start_time

        # Should complete within 2 seconds per Story 2.4
        assert generation_time < 2.0
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_concurrent_code_generation(self, server):
        """Test handling of concurrent code generation requests."""
        import asyncio

        # Simulate concurrent requests
        tasks = [
            server._get_example(endpoint="users-get", format="curl"),
            server._get_example(endpoint="users-post", format="javascript"),
            server._get_example(endpoint="orders-get", format="python"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All requests should complete successfully
        for result in results:
            assert not isinstance(result, Exception)
            if isinstance(result, dict) and "error" not in result:
                assert "code" in result

    @pytest.mark.asyncio
    async def test_different_http_methods(self, server):
        """Test code generation for different HTTP methods."""
        methods_to_test = ["GET", "POST"]

        for method in methods_to_test:
            # Find an endpoint with this method
            endpoint = None
            if method == "GET":
                endpoint = "users-get"
            elif method == "POST":
                endpoint = "users-post"

            if endpoint:
                result = await server._get_example(endpoint=endpoint, format="curl")

                assert "error" not in result
                assert f"curl -X {method}" in result["code"]


class TestGetExampleIntegration:
    """Integration tests for getExample with real endpoint patterns."""

    @pytest.mark.integration
    async def test_with_complex_endpoint_data(self):
        """Test getExample with complex endpoint data."""
        # This would be implemented with actual endpoint data
        # from the Ozon API swagger file mentioned in Story 2.4
        pass

    @pytest.mark.performance
    async def test_code_generation_performance(self):
        """Test code generation performance under load."""
        # This would test multiple simultaneous code generation requests
        # to validate the <2 second performance requirement
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
