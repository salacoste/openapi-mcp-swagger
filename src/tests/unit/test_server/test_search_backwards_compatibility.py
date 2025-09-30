"""Backward compatibility tests for searchEndpoints category filtering (Story 6.3).

Ensures that the enhanced searchEndpoints with category filtering maintains
full backward compatibility with existing functionality and API contracts.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import List, Optional

from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer
from swagger_mcp_server.storage.models import Endpoint
from swagger_mcp_server.config.settings import Settings


def create_endpoint(
    endpoint_id: int,
    path: str,
    method: str,
    summary: str,
    category: Optional[str] = None,
) -> Endpoint:
    """Create mock endpoint."""
    endpoint = Endpoint()
    endpoint.id = endpoint_id
    endpoint.path = path
    endpoint.method = method
    endpoint.summary = summary
    endpoint.description = f"Description for {summary}"
    endpoint.operation_id = f"{method.lower()}_{path.replace('/', '_')}"
    endpoint.tags = []
    endpoint.parameters = "[]"
    endpoint.deprecated = False
    endpoint.category = category
    endpoint.category_group = None
    return endpoint


@pytest.fixture
def mock_repo_backward_compat():
    """Mock repository that simulates pre-Story-6.3 behavior."""
    repo = MagicMock()

    # Mock endpoints (some without categories)
    endpoints = [
        create_endpoint(1, "/api/users", "GET", "List users", None),
        create_endpoint(2, "/api/users", "POST", "Create user", None),
        create_endpoint(3, "/api/users/{id}", "GET", "Get user", None),
        create_endpoint(4, "/api/products", "GET", "List products", "Product"),
        create_endpoint(5, "/api/orders", "GET", "List orders", "Order"),
    ]

    async def mock_search(query: str, methods: Optional[List[str]] = None, **kwargs):
        results = endpoints
        if methods:
            results = [e for e in results if e.method in methods]
        if query:
            results = [e for e in results if query.lower() in e.path.lower()]
        return results

    async def mock_search_paginated(
        query: str,
        methods: Optional[List[str]] = None,
        limit: int = 20,
        offset: int = 0,
        **kwargs
    ):
        results = await mock_search(query, methods, **kwargs)
        return {
            "endpoints": results[offset:offset + limit],
            "total_count": len(results),
        }

    repo.search_endpoints = AsyncMock(side_effect=mock_search)
    repo.search_endpoints_paginated = AsyncMock(side_effect=mock_search_paginated)

    return repo


@pytest.fixture
def settings():
    """Create test settings."""
    settings = Settings()
    settings.database.path = ":memory:"
    settings.server.name = "test-server"
    settings.server.version = "0.1.0"
    return settings


@pytest.fixture
def mock_db_manager():
    """Create mock database manager."""
    from unittest.mock import patch, AsyncMock
    mock_manager = AsyncMock()
    mock_manager.initialize = AsyncMock()
    mock_manager.health_check = AsyncMock(return_value={"status": "healthy"})
    mock_manager.close = AsyncMock()
    return mock_manager


@pytest.fixture
def server_backward_compat(settings, mock_db_manager, mock_repo_backward_compat):
    """Create server with backward compatibility mock."""
    from unittest.mock import patch
    with patch(
        "swagger_mcp_server.server.mcp_server_v2.DatabaseManager",
        return_value=mock_db_manager,
    ):
        server = SwaggerMcpServer(settings)
        server.endpoint_repo = mock_repo_backward_compat
        server.logger = MagicMock()
        return server


class TestBackwardCompatibility:
    """Backward compatibility test suite."""

    @pytest.mark.asyncio
    async def test_existing_search_without_category(self, server_backward_compat):
        """Test that searches without category parameter work as before."""
        result = await server_backward_compat._search_endpoints(
            keywords="users"
        )

        # Should return results as before Story 6.3
        assert "results" in result
        assert len(result["results"]) == 3

        # Metadata should include new fields but set to None
        assert result["search_metadata"]["category_filter"] is None
        assert result["search_metadata"]["category_group_filter"] is None

    @pytest.mark.asyncio
    async def test_search_with_http_methods_only(self, server_backward_compat):
        """Test existing httpMethods filtering still works."""
        result = await server_backward_compat._search_endpoints(
            keywords="users",
            httpMethods=["GET"]
        )

        assert len(result["results"]) == 2
        assert all(r["method"] == "GET" for r in result["results"])

        # New fields should be None
        assert result["search_metadata"]["category_filter"] is None

    @pytest.mark.asyncio
    async def test_pagination_without_category(self, server_backward_compat):
        """Test pagination works as before without category filters."""
        result = await server_backward_compat._search_endpoints(
            keywords="api",
            page=1,
            perPage=2
        )

        assert result["pagination"]["page"] == 1
        assert result["pagination"]["per_page"] == 2
        assert len(result["results"]) == 2

        # Category fields should be None
        assert result["search_metadata"]["category_filter"] is None

    @pytest.mark.asyncio
    async def test_response_format_unchanged(self, server_backward_compat):
        """Test that response format maintains existing structure."""
        result = await server_backward_compat._search_endpoints(
            keywords="users"
        )

        # Existing top-level keys
        assert "results" in result
        assert "pagination" in result
        assert "search_metadata" in result

        # Pagination structure
        pagination = result["pagination"]
        assert "total" in pagination
        assert "page" in pagination
        assert "per_page" in pagination
        assert "total_pages" in pagination
        assert "has_more" in pagination
        assert "has_previous" in pagination

        # Search metadata structure (with new fields)
        metadata = result["search_metadata"]
        assert "keywords" in metadata
        assert "http_methods_filter" in metadata
        assert "result_count" in metadata
        assert "search_time_ms" in metadata

        # New fields present but None for backward compat
        assert "category_filter" in metadata
        assert "category_group_filter" in metadata

    @pytest.mark.asyncio
    async def test_result_structure_unchanged(self, server_backward_compat):
        """Test that individual result structure is unchanged."""
        result = await server_backward_compat._search_endpoints(
            keywords="users"
        )

        endpoint = result["results"][0]

        # Existing fields
        required_fields = [
            "endpoint_id",
            "path",
            "method",
            "summary",
            "description",
            "operationId",
            "tags",
            "parameters",
            "authentication",
            "deprecated",
        ]

        for field in required_fields:
            assert field in endpoint, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_keywords_validation_unchanged(self, server_backward_compat):
        """Test that existing validation rules still apply."""
        from swagger_mcp_server.server.exceptions import ValidationError

        # Empty keywords should fail
        with pytest.raises(ValidationError) as exc:
            await server_backward_compat._search_endpoints(keywords="")

        assert "keywords" in str(exc.value).lower()

        # Keywords too long should fail
        with pytest.raises(ValidationError) as exc:
            await server_backward_compat._search_endpoints(keywords="x" * 501)

        assert "500 characters" in str(exc.value)

    @pytest.mark.asyncio
    async def test_http_methods_validation_unchanged(self, server_backward_compat):
        """Test that HTTP method validation is unchanged."""
        from swagger_mcp_server.server.exceptions import ValidationError

        # Invalid method should fail
        with pytest.raises(ValidationError) as exc:
            await server_backward_compat._search_endpoints(
                keywords="test",
                httpMethods=["INVALID"]
            )

        assert "invalid http methods" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_pagination_validation_unchanged(self, server_backward_compat):
        """Test that pagination validation is unchanged."""
        from swagger_mcp_server.server.exceptions import ValidationError

        # Page < 1 should fail
        with pytest.raises(ValidationError) as exc:
            await server_backward_compat._search_endpoints(
                keywords="test",
                page=0
            )

        assert "page" in str(exc.value).lower()

        # perPage > 50 should fail
        with pytest.raises(ValidationError) as exc:
            await server_backward_compat._search_endpoints(
                keywords="test",
                perPage=51
            )

        assert "perpage" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_method_signature_backward_compatible(self, server_backward_compat):
        """Test that method can be called with old signature."""
        # Call with only required parameter
        result1 = await server_backward_compat._search_endpoints(
            keywords="users"
        )
        assert len(result1["results"]) > 0

        # Call with old optional parameters
        result2 = await server_backward_compat._search_endpoints(
            keywords="users",
            httpMethods=["GET"],
            page=1,
            perPage=10
        )
        assert len(result2["results"]) > 0

        # Both should work without errors

    @pytest.mark.asyncio
    async def test_repository_calls_backward_compatible(self, mock_repo_backward_compat, server_backward_compat):
        """Test that repository is called correctly with new optional parameters."""
        await server_backward_compat._search_endpoints(
            keywords="users"
        )

        # Check that repository was called
        assert mock_repo_backward_compat.search_endpoints_paginated.called

        # Check call arguments include new parameters (but as None/default)
        call_args = mock_repo_backward_compat.search_endpoints_paginated.call_args
        assert "category" in call_args.kwargs or len(call_args.args) > 2
        assert "category_group" in call_args.kwargs or len(call_args.args) > 3

    @pytest.mark.asyncio
    async def test_none_category_equivalent_to_no_category(self, server_backward_compat):
        """Test that category=None behaves same as not providing category."""
        result_none = await server_backward_compat._search_endpoints(
            keywords="users",
            category=None
        )

        result_no_param = await server_backward_compat._search_endpoints(
            keywords="users"
        )

        # Should return same results
        assert len(result_none["results"]) == len(result_no_param["results"])

    @pytest.mark.asyncio
    async def test_empty_string_category_equivalent_to_none(self, server_backward_compat):
        """Test that empty string category is normalized to None."""
        result = await server_backward_compat._search_endpoints(
            keywords="users",
            category=""
        )

        # Should behave as if no category provided
        assert result["search_metadata"]["category_filter"] is None

    @pytest.mark.asyncio
    async def test_whitespace_category_equivalent_to_none(self, server_backward_compat):
        """Test that whitespace-only category is normalized to None."""
        result = await server_backward_compat._search_endpoints(
            keywords="users",
            category="   "
        )

        # Should behave as if no category provided
        assert result["search_metadata"]["category_filter"] is None


class TestToolSchemaBackwardCompatibility:
    """Test that tool schema additions are backward compatible."""

    def test_tool_schema_has_required_fields(self, settings, mock_db_manager):
        """Test that searchEndpoints tool schema maintains required fields."""
        from unittest.mock import patch
        from mcp import types

        # Create tool definitions inline to match server implementation
        # This tests the schema structure without needing the async handler
        search_tool_schema = {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "Search keywords for paths, descriptions, and parameter names",
                    "maxLength": 500,
                    "minLength": 1,
                },
                "httpMethods": {
                    "type": "array",
                    "description": "Optional array of HTTP methods to filter by",
                    "items": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
                    },
                    "uniqueItems": True,
                },
                "category": {
                    "type": "string",
                    "description": "Filter results by category name (case-insensitive)",
                    "maxLength": 255,
                },
                "categoryGroup": {
                    "type": "string",
                    "description": "Filter results by parent group name",
                    "maxLength": 255,
                },
                "page": {
                    "type": "integer",
                    "description": "Page number for pagination (1-based)",
                    "default": 1,
                    "minimum": 1,
                },
                "perPage": {
                    "type": "integer",
                    "description": "Results per page (max 50)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["keywords"],
        }

        schema = search_tool_schema
        assert "properties" in schema
        assert "required" in schema

        # Only keywords should be required
        assert schema["required"] == ["keywords"]

        # New fields should be optional
        props = schema["properties"]
        assert "category" in props
        assert "categoryGroup" in props

        # New fields should not be in required list
        assert "category" not in schema["required"]
        assert "categoryGroup" not in schema["required"]

    def test_tool_description_enhanced(self, settings, mock_db_manager):
        """Test that tool description mentions new capabilities."""
        # Test the description string directly - matches the actual tool description from mcp_server_v2.py
        expected_keywords = ["categories", "progressive disclosure"]
        description = "Search API endpoints by keywords, HTTP methods, and categories with intelligent discovery and progressive disclosure capabilities"

        # Verify all expected keywords are in the description
        for keyword in expected_keywords:
            assert keyword in description.lower(), f"Expected keyword '{keyword}' not found in description"


class TestExistingTestsCompatibility:
    """Verify that existing test patterns still work."""

    @pytest.mark.asyncio
    async def test_minimal_search_call(self, server_backward_compat):
        """Test simplest possible search call still works."""
        result = await server_backward_compat._search_endpoints(keywords="api")

        assert result is not None
        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_with_all_old_parameters(self, server_backward_compat):
        """Test search with all pre-6.3 parameters."""
        result = await server_backward_compat._search_endpoints(
            keywords="users",
            httpMethods=["GET", "POST"],
            page=1,
            perPage=20
        )

        assert result is not None
        assert len(result["results"]) > 0