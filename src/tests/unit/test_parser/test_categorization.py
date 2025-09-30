"""Unit tests for categorization engine.

Epic 6: Hierarchical Endpoint Catalog System - Story 6.1
Tests for automatic endpoint categorization with hybrid extraction strategy.
"""

import pytest

from swagger_mcp_server.parser.categorization import (
    CategorizationEngine,
    CategoryCatalog,
    CategoryInfo,
)


class TestCategoryInfo:
    """Test CategoryInfo dataclass."""

    def test_category_info_creation(self):
        """Test creating CategoryInfo with all fields."""
        info = CategoryInfo(
            category="campaign",
            display_name="Campaign Management",
            description="Campaign operations",
            category_group="API Methods",
            metadata={"original_tag": "Campaign"},
        )

        assert info.category == "campaign"
        assert info.display_name == "Campaign Management"
        assert info.description == "Campaign operations"
        assert info.category_group == "API Methods"
        assert info.metadata == {"original_tag": "Campaign"}

    def test_category_info_minimal(self):
        """Test creating CategoryInfo with minimal fields."""
        info = CategoryInfo(category="test")

        assert info.category == "test"
        assert info.display_name is None
        assert info.description is None
        assert info.category_group is None
        assert info.metadata is None

    def test_category_info_to_dict(self):
        """Test converting CategoryInfo to dictionary."""
        info = CategoryInfo(
            category="campaign",
            display_name="Campaign Management",
            description="Campaign operations",
        )

        result = info.to_dict()

        assert result["category"] == "campaign"
        assert result["display_name"] == "Campaign Management"
        assert result["description"] == "Campaign operations"
        assert result["metadata"] == {}


class TestCategorizationEngine:
    """Test CategorizationEngine functionality."""

    @pytest.fixture
    def engine(self):
        """Create categorization engine for testing."""
        return CategorizationEngine()

    @pytest.fixture
    def engine_with_ozon_tags(self):
        """Create engine with Ozon API tag definitions."""
        engine = CategorizationEngine()
        engine.set_tag_definitions(
            [
                {
                    "name": "Campaign",
                    "x-displayName": "Кампании и рекламируемые объекты",
                    "description": "Campaign management operations",
                },
                {
                    "name": "Statistics",
                    "x-displayName": "Статистика",
                    "description": "Statistics and reporting",
                },
                {
                    "name": "Ad",
                    "x-displayName": "Объявления",
                    "description": "Ad management",
                },
                {
                    "name": "Product",
                    "description": "Product operations",
                },
            ]
        )
        engine.set_tag_groups(
            [
                {
                    "name": "Методы Performance API",
                    "tags": ["Campaign", "Statistics", "Ad", "Product"],
                }
            ]
        )
        return engine

    # Test tag extraction
    def test_extract_category_from_tags_with_ozon_api(self, engine_with_ozon_tags):
        """Test tag extraction with Ozon API fixture."""
        tags = ["Campaign", "Performance"]
        result = engine_with_ozon_tags.extract_category_from_tags(tags)

        assert result is not None
        assert result.category == "campaign"
        assert result.display_name == "Кампании и рекламируемые объекты"
        assert result.description == "Campaign management operations"
        assert result.category_group == "Методы Performance API"
        assert result.metadata["original_tag"] == "Campaign"
        assert result.metadata["all_tags"] == ["Campaign", "Performance"]

    def test_extract_category_from_tags_no_definition(self, engine):
        """Test tag extraction without tag definitions."""
        tags = ["CustomTag"]
        result = engine.extract_category_from_tags(tags)

        assert result is not None
        assert result.category == "customtag"
        assert result.display_name == "CustomTag"
        assert result.metadata["original_tag"] == "CustomTag"

    def test_extract_category_from_tags_empty(self, engine):
        """Test tag extraction with empty tags list."""
        result = engine.extract_category_from_tags([])

        assert result is None

    def test_extract_category_from_tags_none(self, engine):
        """Test tag extraction with None tags."""
        result = engine.extract_category_from_tags(None)

        assert result is None

    # Test path extraction
    def test_extract_category_from_path_api_v1_prefix(self, engine):
        """Test path extraction with /api/v1/ prefix."""
        path = "/api/v1/campaign/list"
        result = engine.extract_category_from_path(path)

        assert result == "campaign"

    def test_extract_category_from_path_api_prefix(self, engine):
        """Test path extraction with /api/ prefix."""
        path = "/api/statistics/report"
        result = engine.extract_category_from_path(path)

        assert result == "statistics"

    def test_extract_category_from_path_no_prefix(self, engine):
        """Test path extraction without prefix."""
        path = "/campaign"
        result = engine.extract_category_from_path(path)

        assert result == "campaign"

    def test_extract_category_from_path_ignore_version(self, engine):
        """Test path extraction ignores version segments."""
        path = "/v2/products/search"
        result = engine.extract_category_from_path(path)

        assert result == "products"

    def test_extract_category_from_path_filter_common_segments(self, engine):
        """Test path extraction filters common non-category segments."""
        path = "/api/v1/users"
        result = engine.extract_category_from_path(path)

        assert result == "users"

    def test_extract_category_from_path_empty(self, engine):
        """Test path extraction with empty path."""
        result = engine.extract_category_from_path("")

        assert result is None

    def test_extract_category_from_path_root(self, engine):
        """Test path extraction with root path."""
        result = engine.extract_category_from_path("/")

        assert result is None

    # Test category normalization
    def test_normalize_category_name_kebab_case(self, engine):
        """Test normalization of kebab-case names."""
        result = engine.normalize_category_name("Search-Promo")

        assert result == "search_promo"

    def test_normalize_category_name_spaces(self, engine):
        """Test normalization with spaces."""
        result = engine.normalize_category_name("Campaign Management")

        assert result == "campaign_management"

    def test_normalize_category_name_unicode(self, engine):
        """Test normalization preserves unicode characters."""
        result = engine.normalize_category_name("Статистика")

        assert result == "статистика"

    def test_normalize_category_name_special_chars(self, engine):
        """Test normalization removes special characters."""
        result = engine.normalize_category_name("API@Settings#Config")

        assert result == "apisettingsconfig"

    def test_normalize_category_name_empty(self, engine):
        """Test normalization of empty string."""
        result = engine.normalize_category_name("")

        assert result == "uncategorized"

    def test_normalize_category_name_none(self, engine):
        """Test normalization of None."""
        result = engine.normalize_category_name(None)

        assert result == "uncategorized"

    # Test category hierarchy resolution
    def test_resolve_category_hierarchy_with_groups(self, engine_with_ozon_tags):
        """Test hierarchy resolution with tag groups."""
        tags = ["Campaign", "Statistics"]
        category, group = engine_with_ozon_tags.resolve_category_hierarchy(tags)

        assert category == "campaign"
        assert group == "Методы Performance API"

    def test_resolve_category_hierarchy_no_groups(self, engine):
        """Test hierarchy resolution without tag groups."""
        tags = ["CustomTag"]
        category, group = engine.resolve_category_hierarchy(tags)

        assert category == "customtag"
        assert group is None

    def test_resolve_category_hierarchy_empty(self, engine):
        """Test hierarchy resolution with empty tags."""
        category, group = engine.resolve_category_hierarchy([])

        assert category is None
        assert group is None

    # Test endpoint categorization
    def test_categorize_endpoint_with_tags(self, engine_with_ozon_tags):
        """Test categorization with operation tags."""
        operation = {
            "tags": ["Campaign"],
            "operationId": "ListCampaigns",
            "summary": "List campaigns",
        }
        path = "/api/client/campaign"

        result = engine_with_ozon_tags.categorize_endpoint(operation, path)

        assert result.category == "campaign"
        assert result.display_name == "Кампании и рекламируемые объекты"
        assert result.category_group == "Методы Performance API"

    def test_categorize_endpoint_fallback_to_path(self, engine):
        """Test categorization falls back to path when no tags."""
        operation = {"operationId": "ListUsers", "summary": "List users"}
        path = "/api/v1/users"

        result = engine.categorize_endpoint(operation, path)

        assert result.category == "users"
        assert result.display_name == "Users"

    def test_categorize_endpoint_default_uncategorized(self, engine):
        """Test categorization defaults to Uncategorized."""
        operation = {"operationId": "RootEndpoint"}
        path = "/"

        result = engine.categorize_endpoint(operation, path)

        assert result.category == "Uncategorized"
        assert result.display_name == "Uncategorized"
        assert result.description == "Endpoints without explicit categorization"

    # Test error handling
    def test_categorize_endpoint_invalid_operation(self, engine):
        """Test categorization handles invalid operation gracefully."""
        operation = "not a dict"
        path = "/api/test"

        result = engine.categorize_endpoint(operation, path)

        assert result.category == "Uncategorized"

    def test_categorize_endpoint_invalid_path(self, engine):
        """Test categorization handles invalid path gracefully."""
        operation = {"operationId": "test"}
        path = None

        result = engine.categorize_endpoint(operation, path)

        assert result.category == "Uncategorized"

    def test_categorize_endpoint_malformed_tags(self, engine):
        """Test categorization handles malformed tags gracefully."""
        operation = {"tags": "not a list"}  # tags should be a list
        path = "/api/test"

        result = engine.categorize_endpoint(operation, path)

        # Should fallback to path extraction
        assert result.category == "test"


class TestCategoryCatalog:
    """Test CategoryCatalog functionality."""

    @pytest.fixture
    def catalog(self):
        """Create category catalog for testing."""
        return CategoryCatalog()

    @pytest.fixture
    def populated_catalog(self):
        """Create catalog with sample data."""
        catalog = CategoryCatalog()

        # Add Campaign category endpoints
        campaign_info = CategoryInfo(
            category="campaign",
            display_name="Campaign Management",
            description="Campaign operations",
            category_group="Performance API",
        )
        catalog.add_endpoint_sync(campaign_info, "GET")
        catalog.add_endpoint_sync(campaign_info, "POST")
        catalog.add_endpoint_sync(campaign_info, "PUT")

        # Add Statistics category endpoints
        stats_info = CategoryInfo(
            category="statistics",
            display_name="Statistics",
            category_group="Performance API",
        )
        catalog.add_endpoint_sync(stats_info, "GET")
        catalog.add_endpoint_sync(stats_info, "GET")

        return catalog

    def test_catalog_initialization(self, catalog):
        """Test catalog initializes with empty state."""
        categories = catalog.get_categories()

        assert len(categories) == 0

    def test_add_endpoint_new_category(self, catalog):
        """Test adding endpoint creates new category."""
        category_info = CategoryInfo(
            category="campaign",
            display_name="Campaign Management",
        )
        catalog.add_endpoint_sync(category_info, "GET")

        categories = catalog.get_categories()

        assert len(categories) == 1
        assert categories[0]["category_name"] == "campaign"
        assert categories[0]["endpoint_count"] == 1
        assert "GET" in categories[0]["http_methods"]

    def test_add_endpoint_existing_category(self, catalog):
        """Test adding endpoint to existing category."""
        category_info = CategoryInfo(category="campaign")

        catalog.add_endpoint_sync(category_info, "GET")
        catalog.add_endpoint_sync(category_info, "POST")

        categories = catalog.get_categories()

        assert len(categories) == 1
        assert categories[0]["endpoint_count"] == 2
        assert set(categories[0]["http_methods"]) == {"GET", "POST"}

    def test_add_endpoint_multiple_categories(self, catalog):
        """Test adding endpoints to multiple categories."""
        campaign_info = CategoryInfo(category="campaign")
        stats_info = CategoryInfo(category="statistics")

        catalog.add_endpoint_sync(campaign_info, "GET")
        catalog.add_endpoint_sync(stats_info, "GET")

        categories = catalog.get_categories()

        assert len(categories) == 2
        category_names = {cat["category_name"] for cat in categories}
        assert category_names == {"campaign", "statistics"}

    def test_get_categories_sorted(self, populated_catalog):
        """Test categories are sorted by endpoint count."""
        categories = populated_catalog.get_categories()

        # Campaign has 3 endpoints, Statistics has 2
        assert categories[0]["category_name"] == "campaign"
        assert categories[0]["endpoint_count"] == 3
        assert categories[1]["category_name"] == "statistics"
        assert categories[1]["endpoint_count"] == 2

    def test_get_categories_http_methods_sorted(self, catalog):
        """Test HTTP methods are sorted in output."""
        category_info = CategoryInfo(category="test")

        catalog.add_endpoint_sync(category_info, "DELETE")
        catalog.add_endpoint_sync(category_info, "POST")
        catalog.add_endpoint_sync(category_info, "GET")

        categories = catalog.get_categories()

        # Methods should be sorted alphabetically
        assert categories[0]["http_methods"] == ["DELETE", "GET", "POST"]

    def test_get_statistics(self, populated_catalog):
        """Test catalog statistics generation."""
        stats = populated_catalog.get_statistics()

        assert stats["total_categories"] == 2
        assert stats["categories_with_groups"] == 2
        assert stats["total_endpoints"] == 5

    def test_get_statistics_empty(self, catalog):
        """Test statistics for empty catalog."""
        stats = catalog.get_statistics()

        assert stats["total_categories"] == 0
        assert stats["categories_with_groups"] == 0
        assert stats["total_endpoints"] == 0

    @pytest.mark.asyncio
    async def test_add_endpoint_async(self, catalog):
        """Test async add_endpoint method."""
        category_info = CategoryInfo(category="campaign")

        await catalog.add_endpoint(category_info, "GET")

        categories = catalog.get_categories()

        assert len(categories) == 1
        assert categories[0]["endpoint_count"] == 1

    @pytest.mark.asyncio
    async def test_add_endpoint_async_concurrent(self, catalog):
        """Test concurrent async add_endpoint calls."""
        import asyncio

        category_info = CategoryInfo(category="test")

        # Add 10 endpoints concurrently
        tasks = [catalog.add_endpoint(category_info, "GET") for _ in range(10)]
        await asyncio.gather(*tasks)

        categories = catalog.get_categories()

        # Thread-safe implementation should handle all 10 additions
        assert len(categories) == 1
        assert categories[0]["endpoint_count"] == 10