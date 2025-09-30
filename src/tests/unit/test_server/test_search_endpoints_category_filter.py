"""Unit tests for searchEndpoints category filtering (Story 6.3).

Tests the enhanced searchEndpoints method with category and categoryGroup filtering.
Validates parameter handling, validation logic, and response metadata.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Optional

from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer
from swagger_mcp_server.storage.models import Endpoint
from swagger_mcp_server.server.exceptions import ValidationError
from swagger_mcp_server.config.settings import Settings


# Mock Endpoint Factory
def create_mock_endpoint(
    endpoint_id: int,
    path: str,
    method: str,
    summary: str,
    category: Optional[str] = None,
    category_group: Optional[str] = None,
) -> Endpoint:
    """Create a mock endpoint with category fields."""
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
    endpoint.category_group = category_group
    return endpoint


# Fixtures
@pytest.fixture
def mock_endpoint_repo():
    """Mock endpoint repository with category support."""
    repo = MagicMock()

    # Mock endpoints with different categories
    campaign_endpoints = [
        create_mock_endpoint(1, "/api/campaigns", "GET", "List campaigns", "Campaign", "Marketing"),
        create_mock_endpoint(2, "/api/campaigns", "POST", "Create campaign", "Campaign", "Marketing"),
        create_mock_endpoint(3, "/api/campaigns/{id}", "GET", "Get campaign", "Campaign", "Marketing"),
        create_mock_endpoint(4, "/api/campaigns/{id}/activate", "POST", "Activate campaign", "Campaign", "Marketing"),
    ]

    statistics_endpoints = [
        create_mock_endpoint(5, "/api/stats/clicks", "GET", "Get click stats", "Statistics", "Analytics"),
        create_mock_endpoint(6, "/api/stats/impressions", "GET", "Get impression stats", "Statistics", "Analytics"),
    ]

    uncategorized_endpoints = [
        create_mock_endpoint(7, "/api/health", "GET", "Health check", None, None),
    ]

    all_endpoints = campaign_endpoints + statistics_endpoints + uncategorized_endpoints

    # Mock search_endpoints method
    async def mock_search_endpoints(
        query: str,
        methods: Optional[List[str]] = None,
        category: Optional[str] = None,
        category_group: Optional[str] = None,
        **kwargs
    ):
        """Mock search with category filtering."""
        results = all_endpoints

        # Filter by category (case-insensitive)
        if category:
            results = [e for e in results if e.category and e.category.lower() == category.lower()]

        # Filter by category_group (case-insensitive)
        if category_group:
            results = [e for e in results if e.category_group and e.category_group.lower() == category_group.lower()]

        # Filter by methods
        if methods:
            results = [e for e in results if e.method in methods]

        # Filter by query (simple contains)
        if query and query.strip():
            query_lower = query.lower()
            results = [
                e for e in results
                if query_lower in e.path.lower() or query_lower in e.summary.lower()
            ]

        return results

    # Mock search_endpoints_paginated method
    async def mock_search_paginated(
        query: str,
        methods: Optional[List[str]] = None,
        category: Optional[str] = None,
        category_group: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        **kwargs
    ):
        """Mock paginated search with category filtering."""
        # Get all results
        all_results = await mock_search_endpoints(
            query=query,
            methods=methods,
            category=category,
            category_group=category_group
        )

        # Apply pagination
        paginated = all_results[offset:offset + limit]

        return {
            "endpoints": paginated,
            "total_count": len(all_results),
        }

    repo.search_endpoints = AsyncMock(side_effect=mock_search_endpoints)
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
    mock_manager = AsyncMock()
    mock_manager.initialize = AsyncMock()
    mock_manager.health_check = AsyncMock(return_value={"status": "healthy"})
    mock_manager.close = AsyncMock()
    return mock_manager


@pytest.fixture
def mcp_server(settings, mock_db_manager, mock_endpoint_repo):
    """Create MCP server instance with mocked repository."""
    with patch(
        "swagger_mcp_server.server.mcp_server_v2.DatabaseManager",
        return_value=mock_db_manager,
    ):
        server = SwaggerMcpServer(settings)
        server.endpoint_repo = mock_endpoint_repo
        server.logger = MagicMock()
        return server


# Unit Tests
class TestSearchEndpointsCategoryFilter:
    """Test suite for category filtering in searchEndpoints."""

    @pytest.mark.asyncio
    async def test_search_with_category_filter_only(self, mcp_server):
        """Test searching with category filter and keywords."""
        result = await mcp_server._search_endpoints(
            keywords="campaign",
            category="Campaign"
        )

        assert "results" in result
        assert len(result["results"]) == 4
        assert all(r["path"].startswith("/api/campaigns") for r in result["results"])

        # Verify metadata
        assert result["search_metadata"]["category_filter"] == "Campaign"
        assert result["search_metadata"]["category_group_filter"] is None

    @pytest.mark.asyncio
    async def test_search_with_category_and_keywords(self, mcp_server):
        """Test category filter combined with keyword search."""
        result = await mcp_server._search_endpoints(
            keywords="activate",
            category="Campaign"
        )

        assert len(result["results"]) == 1
        assert result["results"][0]["path"] == "/api/campaigns/{id}/activate"
        assert result["search_metadata"]["category_filter"] == "Campaign"

    @pytest.mark.asyncio
    async def test_search_with_category_and_http_methods(self, mcp_server):
        """Test category filter combined with HTTP method filter."""
        result = await mcp_server._search_endpoints(
            keywords="campaign",
            category="Campaign",
            httpMethods=["POST"]
        )

        assert len(result["results"]) == 2
        assert all(r["method"] == "POST" for r in result["results"])
        assert result["search_metadata"]["category_filter"] == "Campaign"

    @pytest.mark.asyncio
    async def test_search_with_category_group_filter(self, mcp_server):
        """Test searching with categoryGroup filter."""
        result = await mcp_server._search_endpoints(
            keywords="stats",
            categoryGroup="Analytics"
        )

        assert len(result["results"]) == 2
        assert all("stats" in r["path"] for r in result["results"])
        assert result["search_metadata"]["category_group_filter"] == "Analytics"
        assert result["search_metadata"]["category_filter"] is None

    @pytest.mark.asyncio
    async def test_search_both_category_and_group_error(self, mcp_server):
        """Test that using both category and categoryGroup raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await mcp_server._search_endpoints(
                keywords="test",
                category="Campaign",
                categoryGroup="Marketing"
            )

        assert "Cannot filter by both category and categoryGroup" in str(exc_info.value)
        assert exc_info.value.data["parameter"] == "category"

    @pytest.mark.asyncio
    async def test_category_case_insensitive_matching(self, mcp_server):
        """Test that category filtering is case-insensitive."""
        # Test lowercase
        result_lower = await mcp_server._search_endpoints(
            keywords="campaign",
            category="campaign"
        )

        # Test uppercase
        result_upper = await mcp_server._search_endpoints(
            keywords="campaign",
            category="CAMPAIGN"
        )

        # Test mixed case
        result_mixed = await mcp_server._search_endpoints(
            keywords="campaign",
            category="CaMpAiGn"
        )

        # All should return same results
        assert len(result_lower["results"]) == 4
        assert len(result_upper["results"]) == 4
        assert len(result_mixed["results"]) == 4

    @pytest.mark.asyncio
    async def test_category_empty_string_treated_as_none(self, mcp_server):
        """Test that empty string category is treated as None (no filtering)."""
        # Empty string
        result_empty = await mcp_server._search_endpoints(
            keywords="campaign",
            category=""
        )

        # None
        result_none = await mcp_server._search_endpoints(
            keywords="campaign",
            category=None
        )

        # Should return same results (no category filtering)
        assert len(result_empty["results"]) == len(result_none["results"])
        assert result_empty["search_metadata"]["category_filter"] is None

    @pytest.mark.asyncio
    async def test_category_whitespace_normalization(self, mcp_server):
        """Test that category with whitespace is properly normalized."""
        result = await mcp_server._search_endpoints(
            keywords="campaign",
            category="  Campaign  "
        )

        assert len(result["results"]) == 4
        assert result["search_metadata"]["category_filter"] == "Campaign"

    @pytest.mark.asyncio
    async def test_nonexistent_category_returns_empty(self, mcp_server):
        """Test that non-existent category returns empty results (not an error)."""
        result = await mcp_server._search_endpoints(
            keywords="test",
            category="NonExistentCategory"
        )

        assert len(result["results"]) == 0
        assert result["pagination"]["total"] == 0
        assert result["search_metadata"]["category_filter"] == "NonExistentCategory"

    @pytest.mark.asyncio
    async def test_category_filter_with_pagination(self, mcp_server):
        """Test that pagination works correctly with category filtering."""
        # Page 1
        result_page1 = await mcp_server._search_endpoints(
            keywords="campaign",
            category="Campaign",
            page=1,
            perPage=2
        )

        assert len(result_page1["results"]) == 2
        assert result_page1["pagination"]["page"] == 1
        assert result_page1["pagination"]["per_page"] == 2
        assert result_page1["pagination"]["total"] == 4
        assert result_page1["pagination"]["has_more"] is True

        # Page 2
        result_page2 = await mcp_server._search_endpoints(
            keywords="campaign",
            category="Campaign",
            page=2,
            perPage=2
        )

        assert len(result_page2["results"]) == 2
        assert result_page2["pagination"]["page"] == 2
        assert result_page2["pagination"]["has_previous"] is True

    @pytest.mark.asyncio
    async def test_category_in_response_metadata(self, mcp_server):
        """Test that response metadata includes category filter information."""
        result = await mcp_server._search_endpoints(
            keywords="test",
            category="Campaign",
            httpMethods=["GET"]
        )

        metadata = result["search_metadata"]
        assert "category_filter" in metadata
        assert "category_group_filter" in metadata
        assert metadata["category_filter"] == "Campaign"
        assert metadata["category_group_filter"] is None
        assert metadata["keywords"] == "test"
        assert metadata["http_methods_filter"] == ["GET"]

    @pytest.mark.asyncio
    async def test_backward_compatibility_no_category(self, mcp_server):
        """Test that existing behavior works without category parameters."""
        result = await mcp_server._search_endpoints(
            keywords="campaign"
        )

        # Should return all campaign-related results (not just Campaign category)
        assert len(result["results"]) == 4
        assert result["search_metadata"]["category_filter"] is None
        assert result["search_metadata"]["category_group_filter"] is None

    @pytest.mark.asyncio
    async def test_category_group_empty_string(self, mcp_server):
        """Test that empty categoryGroup is treated as None."""
        result = await mcp_server._search_endpoints(
            keywords="stats",
            categoryGroup="   "
        )

        assert result["search_metadata"]["category_group_filter"] is None

    @pytest.mark.asyncio
    async def test_validation_both_filters_with_values(self, mcp_server):
        """Test validation when both category and categoryGroup have non-empty values."""
        with pytest.raises(ValidationError) as exc_info:
            await mcp_server._search_endpoints(
                keywords="test",
                category="Campaign",
                categoryGroup="Marketing"
            )

        error = exc_info.value
        assert error.data["parameter"] == "category"
        assert "simultaneously" in error.message.lower()
        assert "Campaign" in str(error.data["value"])
        assert "Marketing" in str(error.data["value"])