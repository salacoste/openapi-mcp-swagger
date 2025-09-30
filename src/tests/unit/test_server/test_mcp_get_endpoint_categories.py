"""Unit tests for getEndpointCategories MCP method.

Epic 6: Story 6.2 - getEndpointCategories MCP method
Tests the category catalog retrieval functionality.
"""

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swagger_mcp_server.config.settings import Settings
from swagger_mcp_server.server.exceptions import DatabaseConnectionError, ValidationError
from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer
from swagger_mcp_server.storage.models import APIMetadata


class TestGetEndpointCategories:
    """Test cases for getEndpointCategories method."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = Settings()
        settings.database.path = ":memory:"
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
                "table_counts": {"endpoint_categories": 6},
            }
        )
        mock_manager.close = AsyncMock()
        return mock_manager

    @pytest.fixture
    def mock_categories_data(self):
        """Create mock category data."""
        return [
            {
                "name": "Campaign",
                "displayName": "Кампании и рекламируемые объекты",
                "description": "Campaign management operations",
                "endpointCount": 4,
                "group": "Методы Performance API",
                "httpMethods": ["GET", "POST", "PATCH"],
            },
            {
                "name": "Statistics",
                "displayName": "Статистика",
                "description": "Statistics and analytics operations",
                "endpointCount": 8,
                "group": "Методы Performance API",
                "httpMethods": ["GET", "POST"],
            },
            {
                "name": "Ad",
                "displayName": "Объявления",
                "description": "Advertisement management",
                "endpointCount": 6,
                "group": "Методы Performance API",
                "httpMethods": ["GET", "POST", "DELETE"],
            },
            {
                "name": "Product",
                "displayName": "Товары",
                "description": "Product operations",
                "endpointCount": 5,
                "group": "Методы Performance API",
                "httpMethods": ["GET", "POST"],
            },
            {
                "name": "Search-Promo",
                "displayName": "Поисковое продвижение",
                "description": "Search promotion operations",
                "endpointCount": 3,
                "group": "Методы Performance API",
                "httpMethods": ["GET", "POST"],
            },
            {
                "name": "Vendor",
                "displayName": "Управление вендорами",
                "description": "Vendor management",
                "endpointCount": 2,
                "group": "Методы Performance API",
                "httpMethods": ["GET"],
            },
        ]

    @pytest.fixture
    def mock_groups_data(self):
        """Create mock groups data."""
        return [
            {
                "name": "Методы Performance API",
                "categoryCount": 6,
                "totalEndpoints": 28,
                "categories": [
                    "Campaign",
                    "Statistics",
                    "Ad",
                    "Product",
                    "Search-Promo",
                    "Vendor",
                ],
            }
        ]

    @pytest.fixture
    def mock_api_metadata(self):
        """Create mock API metadata."""
        return APIMetadata(
            id=1,
            title="Ozon Performance API",
            version="2.0",
            openapi_version="3.0.0",
            description="Ozon Performance API",
        )

    @pytest.fixture
    def mock_repositories(
        self, mock_categories_data, mock_groups_data, mock_api_metadata
    ):
        """Create mock repositories."""
        endpoint_repo = AsyncMock()
        schema_repo = AsyncMock()
        metadata_repo = AsyncMock()

        # Mock get_categories
        endpoint_repo.get_categories = AsyncMock(return_value=mock_categories_data)

        # Mock get_category_groups
        endpoint_repo.get_category_groups = AsyncMock(return_value=mock_groups_data)

        # Mock list_all
        metadata_repo.list_all = AsyncMock(return_value=[mock_api_metadata])

        return endpoint_repo, schema_repo, metadata_repo

    @pytest.fixture
    async def server(self, settings, mock_db_manager, mock_repositories):
        """Create test server with mocked dependencies."""
        with patch(
            "swagger_mcp_server.server.mcp_server_v2.DatabaseManager",
            return_value=mock_db_manager,
        ):
            server = SwaggerMcpServer(settings)
            await server.initialize()

            # Inject mocked repositories
            endpoint_repo, schema_repo, metadata_repo = mock_repositories
            server.endpoint_repo = endpoint_repo
            server.schema_repo = schema_repo
            server.metadata_repo = metadata_repo

            yield server

            await server.cleanup()

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_default_params(self, server):
        """Test getEndpointCategories with default parameters."""
        result = await server._get_endpoint_categories()

        # Verify structure
        assert "categories" in result
        assert "groups" in result
        assert "metadata" in result

        # Verify categories
        assert len(result["categories"]) == 6
        assert result["categories"][0]["name"] == "Campaign"
        assert result["categories"][0]["endpointCount"] == 4

        # Verify groups
        assert len(result["groups"]) == 1
        assert result["groups"][0]["name"] == "Методы Performance API"
        assert result["groups"][0]["categoryCount"] == 6
        assert result["groups"][0]["totalEndpoints"] == 28

        # Verify metadata
        assert result["metadata"]["totalCategories"] == 6
        assert result["metadata"]["totalEndpoints"] == 28
        assert result["metadata"]["totalGroups"] == 1
        assert result["metadata"]["apiTitle"] == "Ozon Performance API"
        assert result["metadata"]["apiVersion"] == "2.0"

        # Verify repository was called correctly
        server.endpoint_repo.get_categories.assert_called_once_with(
            api_id=None, category_group=None, include_empty=False, sort_by="name"
        )

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_with_group_filter(self, server):
        """Test getEndpointCategories with categoryGroup filter."""
        # Mock filtered results
        filtered_categories = [
            cat
            for cat in server.endpoint_repo.get_categories.return_value
            if cat["group"] == "Методы Performance API"
        ]
        server.endpoint_repo.get_categories = AsyncMock(return_value=filtered_categories)

        result = await server._get_endpoint_categories(
            categoryGroup="Методы Performance API"
        )

        assert len(result["categories"]) == 6
        for cat in result["categories"]:
            assert cat["group"] == "Методы Performance API"

        # Verify filter was passed
        server.endpoint_repo.get_categories.assert_called_once_with(
            api_id=None,
            category_group="Методы Performance API",
            include_empty=False,
            sort_by="name",
        )

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_include_empty(self, server):
        """Test getEndpointCategories with includeEmpty=True."""
        # Add empty category
        categories_with_empty = server.endpoint_repo.get_categories.return_value + [
            {
                "name": "EmptyCategory",
                "displayName": "Empty Category",
                "description": "Category with no endpoints",
                "endpointCount": 0,
                "group": "Test Group",
                "httpMethods": [],
            }
        ]
        server.endpoint_repo.get_categories = AsyncMock(
            return_value=categories_with_empty
        )

        result = await server._get_endpoint_categories(includeEmpty=True)

        assert len(result["categories"]) == 7
        assert any(cat["endpointCount"] == 0 for cat in result["categories"])

        server.endpoint_repo.get_categories.assert_called_once_with(
            api_id=None, category_group=None, include_empty=True, sort_by="name"
        )

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_sort_by_endpoint_count(self, server):
        """Test getEndpointCategories with sortBy=endpointCount."""
        # Mock sorted by endpoint count
        sorted_categories = sorted(
            server.endpoint_repo.get_categories.return_value,
            key=lambda x: x["endpointCount"],
            reverse=True,
        )
        server.endpoint_repo.get_categories = AsyncMock(return_value=sorted_categories)

        result = await server._get_endpoint_categories(sortBy="endpointCount")

        # Verify sorting
        assert result["categories"][0]["name"] == "Statistics"  # 8 endpoints
        assert result["categories"][0]["endpointCount"] == 8
        assert result["categories"][-1]["name"] == "Vendor"  # 2 endpoints
        assert result["categories"][-1]["endpointCount"] == 2

        server.endpoint_repo.get_categories.assert_called_once_with(
            api_id=None, category_group=None, include_empty=False, sort_by="endpointCount"
        )

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_sort_by_group(self, server):
        """Test getEndpointCategories with sortBy=group."""
        result = await server._get_endpoint_categories(sortBy="group")

        server.endpoint_repo.get_categories.assert_called_once_with(
            api_id=None, category_group=None, include_empty=False, sort_by="group"
        )

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_invalid_sort_field(self, server):
        """Test getEndpointCategories with invalid sortBy value."""
        with pytest.raises(ValidationError) as exc_info:
            await server._get_endpoint_categories(sortBy="invalid")

        error = exc_info.value
        assert error.data["parameter"] == "sortBy"
        assert "invalid" in error.message.lower()
        assert "name" in error.data["suggestions"]
        assert "endpointCount" in error.data["suggestions"]
        assert "group" in error.data["suggestions"]

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_empty_database(self, server):
        """Test getEndpointCategories with empty database."""
        server.endpoint_repo.get_categories = AsyncMock(return_value=[])

        result = await server._get_endpoint_categories()

        assert result["categories"] == []
        assert result["groups"] == []
        assert result["metadata"]["totalCategories"] == 0
        assert result["metadata"]["totalEndpoints"] == 0
        assert result["metadata"]["totalGroups"] == 0
        assert result["metadata"]["apiTitle"] is None
        assert result["metadata"]["apiVersion"] is None

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_response_structure(self, server):
        """Test getEndpointCategories response structure correctness."""
        result = await server._get_endpoint_categories()

        # Verify all required fields in categories
        for cat in result["categories"]:
            assert "name" in cat
            assert "displayName" in cat
            assert "description" in cat
            assert "endpointCount" in cat
            assert "group" in cat
            assert "httpMethods" in cat
            assert isinstance(cat["httpMethods"], list)

        # Verify all required fields in groups
        for group in result["groups"]:
            assert "name" in group
            assert "categoryCount" in group
            assert "totalEndpoints" in group
            assert "categories" in group
            assert isinstance(group["categories"], list)

        # Verify all required fields in metadata
        metadata = result["metadata"]
        assert "totalCategories" in metadata
        assert "totalEndpoints" in metadata
        assert "totalGroups" in metadata
        assert "apiTitle" in metadata
        assert "apiVersion" in metadata

    @pytest.mark.asyncio
    async def test_group_aggregation_correctness(self, server):
        """Test that group aggregation is calculated correctly."""
        result = await server._get_endpoint_categories()

        # Verify group totals match sum of categories
        total_from_categories = sum(cat["endpointCount"] for cat in result["categories"])
        total_from_groups = sum(group["totalEndpoints"] for group in result["groups"])

        assert total_from_categories == total_from_groups == 28
        assert result["metadata"]["totalEndpoints"] == 28

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_with_whitespace_filter(self, server):
        """Test getEndpointCategories normalizes whitespace in categoryGroup."""
        result = await server._get_endpoint_categories(
            categoryGroup="  Методы Performance API  "
        )

        # Verify whitespace was trimmed
        server.endpoint_repo.get_categories.assert_called_once_with(
            api_id=None,
            category_group="Методы Performance API",
            include_empty=False,
            sort_by="name",
        )

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_with_empty_string_filter(self, server):
        """Test getEndpointCategories handles empty string categoryGroup."""
        result = await server._get_endpoint_categories(categoryGroup="   ")

        # Empty string should be converted to None
        server.endpoint_repo.get_categories.assert_called_once_with(
            api_id=None, category_group=None, include_empty=False, sort_by="name"
        )

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_metadata_fallback(self, server):
        """Test getEndpointCategories handles missing API metadata gracefully."""
        server.metadata_repo.list_all = AsyncMock(return_value=[])

        result = await server._get_endpoint_categories()

        assert result["metadata"]["apiTitle"] is None
        assert result["metadata"]["apiVersion"] is None
        # Other metadata should still be present
        assert result["metadata"]["totalCategories"] == 6
        assert result["metadata"]["totalEndpoints"] == 28

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_metadata_error_handling(self, server):
        """Test getEndpointCategories handles metadata retrieval errors."""
        server.metadata_repo.list_all = AsyncMock(
            side_effect=Exception("Metadata error")
        )

        # Should not raise, just log warning
        result = await server._get_endpoint_categories()

        assert result["metadata"]["apiTitle"] is None
        assert result["metadata"]["apiVersion"] is None

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_uninitialized_repos(self):
        """Test getEndpointCategories raises error when repos not initialized."""
        settings = Settings()
        settings.database.path = ":memory:"

        with patch("swagger_mcp_server.server.mcp_server_v2.DatabaseManager"):
            server = SwaggerMcpServer(settings)
            # Don't initialize - repos will be None

            with pytest.raises(DatabaseConnectionError) as exc_info:
                await server._get_endpoint_categories()

            assert "not properly initialized" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_resilience_wrapper(self, server):
        """Test _get_endpoint_categories_with_resilience wrapper."""
        arguments = {
            "categoryGroup": "Методы Performance API",
            "includeEmpty": False,
            "sortBy": "endpointCount",
        }
        request_id = "test-request-123"

        result = await server._get_endpoint_categories_with_resilience(
            arguments, request_id
        )

        assert "categories" in result
        assert "groups" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_missing_table_error(self, server):
        """Test getEndpointCategories handles missing table error."""
        server.endpoint_repo.get_categories = AsyncMock(
            side_effect=Exception("no such table: endpoint_categories")
        )

        with pytest.raises(DatabaseConnectionError) as exc_info:
            await server._get_endpoint_categories_with_resilience({}, "test-123")

        error = exc_info.value
        assert "not available" in str(error).lower()
        assert "migration" in str(error).lower()

    @pytest.mark.asyncio
    async def test_get_endpoint_categories_database_error(self, server):
        """Test getEndpointCategories handles database errors."""
        server.endpoint_repo.get_categories = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        with pytest.raises(DatabaseConnectionError) as exc_info:
            await server._get_endpoint_categories_with_resilience({}, "test-123")

        error = exc_info.value
        assert "failed to retrieve categories" in str(error).lower()


class TestGetEndpointCategoriesPerformance(TestGetEndpointCategories):
    """Performance tests for getEndpointCategories.

    Inherits fixtures from TestGetEndpointCategories.
    """

    @pytest.mark.asyncio
    async def test_response_time_target(self, server):
        """Test that response time is under 50ms target."""
        import time

        start = time.perf_counter()
        await server._get_endpoint_categories()
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms

        # Should be well under 50ms with mocked data
        assert elapsed < 50, f"Response took {elapsed:.2f}ms, expected < 50ms"

    @pytest.mark.asyncio
    async def test_response_time_with_filters(self, server):
        """Test that response time with filters is under 100ms target."""
        import time

        start = time.perf_counter()
        await server._get_endpoint_categories(
            categoryGroup="Методы Performance API",
            includeEmpty=True,
            sortBy="endpointCount",
        )
        elapsed = (time.perf_counter() - start) * 1000

        # Should be well under 100ms with mocked data
        assert elapsed < 100, f"Response took {elapsed:.2f}ms, expected < 100ms"