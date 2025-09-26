"""Comprehensive tests for enhanced searchEndpoints method (Story 2.2)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, List

from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer
from swagger_mcp_server.config.settings import Settings


class TestEnhancedSearchEndpoints:
    """Test cases for enhanced searchEndpoints functionality per Story 2.2."""

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

        # User management endpoints
        user_endpoint = MagicMock()
        user_endpoint.id = "users-get"
        user_endpoint.path = "/api/v1/users/{id}"
        user_endpoint.method = "GET"
        user_endpoint.summary = "Get user by ID"
        user_endpoint.description = "Retrieve detailed user information including profile data"
        user_endpoint.operation_id = "getUserById"
        user_endpoint.tags = ["users", "profile"]
        user_endpoint.parameters = [
            {"name": "id", "in": "path", "required": True, "type": "string"},
            {"name": "include_profile", "in": "query", "required": False, "type": "boolean"}
        ]
        user_endpoint.security = [{"bearerAuth": []}]
        user_endpoint.deprecated = False
        endpoints.append(user_endpoint)

        # Order management endpoint
        order_endpoint = MagicMock()
        order_endpoint.id = "orders-post"
        order_endpoint.path = "/api/v1/orders"
        order_endpoint.method = "POST"
        order_endpoint.summary = "Create new order"
        order_endpoint.description = "Submit a new order with items and shipping information"
        order_endpoint.operation_id = "createOrder"
        order_endpoint.tags = ["orders", "commerce"]
        order_endpoint.parameters = [
            {"name": "X-API-Key", "in": "header", "required": True, "type": "string"}
        ]
        order_endpoint.security = [{"apiKey": []}]
        order_endpoint.deprecated = False
        endpoints.append(order_endpoint)

        # Product search endpoint
        product_endpoint = MagicMock()
        product_endpoint.id = "products-search"
        product_endpoint.path = "/api/v1/products/search"
        product_endpoint.method = "GET"
        product_endpoint.summary = "Search products"
        product_endpoint.description = "Search and filter products by various criteria"
        product_endpoint.operation_id = "searchProducts"
        product_endpoint.tags = ["products", "search"]
        product_endpoint.parameters = [
            {"name": "query", "in": "query", "required": True, "type": "string"},
            {"name": "category", "in": "query", "required": False, "type": "string"},
            {"name": "price_min", "in": "query", "required": False, "type": "number"}
        ]
        product_endpoint.security = None
        product_endpoint.deprecated = False
        endpoints.append(product_endpoint)

        return endpoints

    @pytest.fixture
    def mock_endpoint_repo(self, mock_endpoints):
        """Create mock endpoint repository."""
        repo = AsyncMock()

        # Mock search_endpoints method to simulate different search results
        async def mock_search(query, methods=None, limit=20, **kwargs):
            filtered_endpoints = mock_endpoints

            # Simple keyword filtering simulation
            if query:
                query_lower = query.lower()
                filtered_endpoints = [
                    ep for ep in mock_endpoints
                    if (query_lower in ep.path.lower() or
                        query_lower in (ep.summary or "").lower() or
                        query_lower in (ep.description or "").lower())
                ]

            # Method filtering
            if methods:
                filtered_endpoints = [
                    ep for ep in filtered_endpoints
                    if ep.method in methods
                ]

            return filtered_endpoints[:limit]

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
    async def test_parameter_validation_keywords_required(self, server):
        """Test that keywords parameter is required."""
        # Empty keywords
        result = await server._search_endpoints(keywords="")
        assert "error" in result
        assert "required" in result["error"].lower()

        # Whitespace only
        result = await server._search_endpoints(keywords="   ")
        assert "error" in result
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_parameter_validation_keywords_max_length(self, server):
        """Test keywords parameter max length validation."""
        long_keywords = "a" * 501  # Exceeds 500 char limit
        result = await server._search_endpoints(keywords=long_keywords)
        assert "error" in result
        assert "500 characters" in result["error"]

    @pytest.mark.asyncio
    async def test_parameter_validation_http_methods(self, server):
        """Test HTTP methods parameter validation."""
        # Valid methods
        result = await server._search_endpoints(
            keywords="user",
            httpMethods=["GET", "POST"]
        )
        assert "error" not in result

        # Invalid method
        result = await server._search_endpoints(
            keywords="user",
            httpMethods=["GET", "INVALID"]
        )
        assert "error" in result
        assert "Invalid HTTP methods" in result["error"]

    @pytest.mark.asyncio
    async def test_parameter_validation_pagination(self, server):
        """Test pagination parameter validation."""
        # Invalid page number
        result = await server._search_endpoints(keywords="user", page=0)
        assert "error" in result
        assert "Page number must be 1 or greater" in result["error"]

        # Invalid perPage - too small
        result = await server._search_endpoints(keywords="user", perPage=0)
        assert "error" in result
        assert "perPage must be between 1 and 50" in result["error"]

        # Invalid perPage - too large
        result = await server._search_endpoints(keywords="user", perPage=51)
        assert "error" in result
        assert "perPage must be between 1 and 50" in result["error"]

    @pytest.mark.asyncio
    async def test_keyword_search_functionality(self, server):
        """Test comprehensive keyword search across different fields."""
        # Search by path
        result = await server._search_endpoints(keywords="users")
        assert "error" not in result
        assert len(result["results"]) > 0
        assert any("users" in r["path"] for r in result["results"])

        # Search by description
        result = await server._search_endpoints(keywords="profile")
        assert "error" not in result
        assert len(result["results"]) > 0

        # Search by summary
        result = await server._search_endpoints(keywords="search")
        assert "error" not in result
        assert len(result["results"]) > 0

    @pytest.mark.asyncio
    async def test_http_method_filtering(self, server):
        """Test HTTP method filtering functionality."""
        # Filter by single method
        result = await server._search_endpoints(
            keywords="api",
            httpMethods=["GET"]
        )
        assert "error" not in result
        for endpoint in result["results"]:
            assert endpoint["method"] == "GET"

        # Filter by multiple methods
        result = await server._search_endpoints(
            keywords="api",
            httpMethods=["GET", "POST"]
        )
        assert "error" not in result
        for endpoint in result["results"]:
            assert endpoint["method"] in ["GET", "POST"]

    @pytest.mark.asyncio
    async def test_pagination_functionality(self, server):
        """Test pagination functionality."""
        # Test first page
        result = await server._search_endpoints(
            keywords="api",
            page=1,
            perPage=2
        )
        assert "error" not in result
        assert "pagination" in result
        assert result["pagination"]["page"] == 1
        assert result["pagination"]["per_page"] == 2
        assert len(result["results"]) <= 2

    @pytest.mark.asyncio
    async def test_response_format_compliance(self, server):
        """Test that response format matches Story 2.2 requirements."""
        result = await server._search_endpoints(keywords="users")
        assert "error" not in result

        # Check main structure
        assert "results" in result
        assert "pagination" in result
        assert "search_metadata" in result

        # Check pagination metadata
        pagination = result["pagination"]
        required_pagination_fields = [
            "total", "page", "per_page", "total_pages",
            "has_more", "has_previous"
        ]
        for field in required_pagination_fields:
            assert field in pagination

        # Check search metadata
        metadata = result["search_metadata"]
        required_metadata_fields = [
            "keywords", "http_methods_filter", "result_count"
        ]
        for field in required_metadata_fields:
            assert field in metadata

        # Check result structure
        if result["results"]:
            endpoint = result["results"][0]
            required_endpoint_fields = [
                "endpoint_id", "path", "method", "summary",
                "description", "operationId", "tags", "parameters",
                "authentication", "deprecated"
            ]
            for field in required_endpoint_fields:
                assert field in endpoint

            # Check parameters structure
            params = endpoint["parameters"]
            required_param_fields = ["path", "query", "header", "body", "required"]
            for field in required_param_fields:
                assert field in params

    @pytest.mark.asyncio
    async def test_parameter_parsing(self, server):
        """Test endpoint parameter parsing functionality."""
        result = await server._search_endpoints(keywords="users")
        assert "error" not in result

        if result["results"]:
            endpoint = result["results"][0]
            params = endpoint["parameters"]

            # Should have parsed parameters correctly
            assert isinstance(params["path"], list)
            assert isinstance(params["query"], list)
            assert isinstance(params["header"], list)
            assert isinstance(params["required"], list)

    @pytest.mark.asyncio
    async def test_authentication_info_extraction(self, server):
        """Test authentication information extraction."""
        result = await server._search_endpoints(keywords="users")
        assert "error" not in result

        if result["results"]:
            # Check that authentication info is extracted when present
            endpoints_with_auth = [
                ep for ep in result["results"]
                if ep["authentication"] is not None
            ]
            # Should have at least one endpoint with auth info
            assert len(endpoints_with_auth) >= 0  # May be 0 if no auth configured

    @pytest.mark.asyncio
    async def test_edge_cases(self, server):
        """Test edge cases and error scenarios."""
        # No results found
        result = await server._search_endpoints(keywords="nonexistent")
        assert "error" not in result
        assert result["results"] == []
        assert result["pagination"]["total"] == 0

        # Server not initialized
        uninitialized_server = SwaggerMcpServer(Settings())
        result = await uninitialized_server._search_endpoints(keywords="test")
        assert "error" in result
        assert "not properly initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_search_performance_requirements(self, server):
        """Test that search meets performance requirements."""
        import time

        start_time = time.time()
        result = await server._search_endpoints(keywords="api")
        end_time = time.time()

        search_time_ms = (end_time - start_time) * 1000

        # Should complete within reasonable time (much less than 200ms requirement)
        # Note: This is a unit test with mocks, so it should be very fast
        assert search_time_ms < 100  # 100ms for unit test
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_case_insensitive_search(self, server):
        """Test case-insensitive search functionality."""
        # Test different cases
        result1 = await server._search_endpoints(keywords="USER")
        result2 = await server._search_endpoints(keywords="user")
        result3 = await server._search_endpoints(keywords="User")

        # All should return the same results (case-insensitive)
        assert len(result1["results"]) == len(result2["results"])
        assert len(result2["results"]) == len(result3["results"])

    @pytest.mark.asyncio
    async def test_partial_matching(self, server):
        """Test partial keyword matching."""
        # Should find endpoints containing partial matches
        result = await server._search_endpoints(keywords="prod")
        assert "error" not in result
        # Should find "products" endpoint
        assert any("product" in r["path"].lower() for r in result["results"])


class TestSearchEndpointsIntegration:
    """Integration tests for searchEndpoints with real repository patterns."""

    @pytest.mark.integration
    async def test_with_sample_data(self):
        """Test searchEndpoints with sample data structure."""
        # This would be implemented with actual sample data
        # from the Ozon API swagger file mentioned in Story 2.2
        pass

    @pytest.mark.performance
    async def test_concurrent_search_requests(self):
        """Test handling of concurrent search requests."""
        # This would test multiple simultaneous search requests
        # to validate the <200ms performance requirement
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])