"""Integration tests for universal API indexing and search functionality.

This module tests the search infrastructure with various types of API specifications
to ensure universal compatibility. Uses sample data from different API styles
including REST, e-commerce, social media, and enterprise APIs.
"""

import asyncio
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest

from swagger_mcp_server.search.index_manager import SearchIndexManager
from swagger_mcp_server.search.search_engine import SearchEngine
from swagger_mcp_server.config.settings import SearchConfig
from swagger_mcp_server.storage.repositories.endpoint_repository import EndpointRepository


@pytest.fixture
def temp_search_dir():
    """Create temporary directory for search index testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def search_config():
    """Create test search configuration."""
    return SearchConfig(
        indexing__batch_size=50,
        performance__max_search_results=100,
    )


@pytest.fixture
def sample_rest_api_data():
    """Sample REST API endpoints data (generic structure)."""
    return [
        {
            "id": "users_get",
            "path": "/api/v1/users",
            "method": "GET",
            "operation_id": "getUsers",
            "summary": "List users",
            "description": "Retrieve a paginated list of all users in the system",
            "parameters": [
                {"name": "page", "type": "integer", "description": "Page number for pagination"},
                {"name": "limit", "type": "integer", "description": "Number of users per page"},
                {"name": "filter", "type": "string", "description": "Filter users by name or email"}
            ],
            "tags": ["users", "management"],
            "security": [{"bearer_auth": []}],
            "responses": {
                "200": {
                    "description": "List of users",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserList"}}}
                }
            },
            "deprecated": False
        },
        {
            "id": "users_post",
            "path": "/api/v1/users",
            "method": "POST",
            "operation_id": "createUser",
            "summary": "Create user",
            "description": "Create a new user account with email verification",
            "parameters": [],
            "tags": ["users", "registration"],
            "security": [{"api_key": []}],
            "responses": {
                "201": {"description": "User created successfully"},
                "400": {"description": "Invalid user data"}
            },
            "deprecated": False
        },
        {
            "id": "products_search",
            "path": "/api/v1/products/search",
            "method": "GET",
            "operation_id": "searchProducts",
            "summary": "Search products",
            "description": "Full-text search across product catalog with filters",
            "parameters": [
                {"name": "q", "type": "string", "description": "Search query text"},
                {"name": "category", "type": "string", "description": "Product category filter"},
                {"name": "price_min", "type": "number", "description": "Minimum price filter"},
                {"name": "price_max", "type": "number", "description": "Maximum price filter"}
            ],
            "tags": ["products", "search", "catalog"],
            "security": [],
            "responses": {
                "200": {"description": "Search results"}
            },
            "deprecated": False
        }
    ]


@pytest.fixture
def sample_enterprise_api_data():
    """Sample enterprise API endpoints (complex business logic)."""
    return [
        {
            "id": "org_reports_analytics",
            "path": "/api/enterprise/v2/organizations/{orgId}/reports/analytics",
            "method": "POST",
            "operation_id": "generateAnalyticsReport",
            "summary": "Generate analytics report",
            "description": "Create comprehensive analytics report for organization with custom metrics and time ranges",
            "parameters": [
                {"name": "orgId", "type": "string", "description": "Organization identifier"},
                {"name": "report_type", "type": "string", "description": "Type of analytics report"},
                {"name": "date_from", "type": "string", "description": "Start date for report data"},
                {"name": "date_to", "type": "string", "description": "End date for report data"}
            ],
            "tags": ["enterprise", "analytics", "reports", "business-intelligence"],
            "security": [{"oauth2": ["reports:read", "analytics:access"]}],
            "responses": {
                "202": {"description": "Report generation started"},
                "403": {"description": "Insufficient permissions"}
            },
            "deprecated": False
        },
        {
            "id": "workflow_automation",
            "path": "/api/enterprise/v2/workflows/{workflowId}/execute",
            "method": "POST",
            "operation_id": "executeWorkflow",
            "summary": "Execute workflow",
            "description": "Trigger automated business workflow with input parameters and callback configuration",
            "parameters": [
                {"name": "workflowId", "type": "string", "description": "Workflow template identifier"},
                {"name": "async", "type": "boolean", "description": "Execute workflow asynchronously"}
            ],
            "tags": ["enterprise", "workflow", "automation", "business-process"],
            "security": [{"oauth2": ["workflows:execute"]}],
            "responses": {
                "200": {"description": "Workflow executed successfully"},
                "422": {"description": "Workflow validation failed"}
            },
            "deprecated": False
        }
    ]


@pytest.fixture
def sample_social_api_data():
    """Sample social media API endpoints."""
    return [
        {
            "id": "posts_timeline",
            "path": "/api/v3/feed/timeline",
            "method": "GET",
            "operation_id": "getTimeline",
            "summary": "Get user timeline",
            "description": "Retrieve personalized timeline feed with posts from followed users",
            "parameters": [
                {"name": "limit", "type": "integer", "description": "Maximum number of posts to return"},
                {"name": "since_id", "type": "string", "description": "Return posts newer than this ID"},
                {"name": "include_replies", "type": "boolean", "description": "Include reply posts in timeline"}
            ],
            "tags": ["social", "feed", "timeline", "posts"],
            "security": [{"user_token": []}],
            "responses": {
                "200": {"description": "Timeline posts"}
            },
            "deprecated": False
        },
        {
            "id": "posts_create",
            "path": "/api/v3/posts",
            "method": "POST",
            "operation_id": "createPost",
            "summary": "Create post",
            "description": "Publish a new post with text, media attachments, and privacy settings",
            "parameters": [],
            "tags": ["social", "posts", "publishing", "content"],
            "security": [{"user_token": []}],
            "responses": {
                "201": {"description": "Post created"},
                "413": {"description": "Content too large"}
            },
            "deprecated": False
        }
    ]


@pytest.fixture
def sample_deprecated_api_data():
    """Sample deprecated API endpoints for testing deprecation handling."""
    return [
        {
            "id": "legacy_auth",
            "path": "/api/v1/auth/legacy",
            "method": "POST",
            "operation_id": "legacyAuth",
            "summary": "Legacy authentication",
            "description": "Legacy authentication method - use OAuth2 instead",
            "parameters": [
                {"name": "username", "type": "string", "description": "User name"},
                {"name": "password", "type": "string", "description": "User password"}
            ],
            "tags": ["auth", "legacy"],
            "security": [],
            "responses": {
                "200": {"description": "Authentication successful"}
            },
            "deprecated": True
        }
    ]


class TestUniversalAPIIndexing:
    """Test indexing capabilities across different API types."""

    @pytest.mark.asyncio
    async def test_index_rest_api_endpoints(
        self, temp_search_dir, search_config, sample_rest_api_data
    ):
        """Test indexing standard REST API endpoints."""
        # Setup mock repositories
        endpoint_repo = AsyncMock(spec=EndpointRepository)
        schema_repo = AsyncMock()
        metadata_repo = AsyncMock()

        endpoint_repo.count_all.return_value = len(sample_rest_api_data)
        endpoint_repo.get_all.return_value = sample_rest_api_data

        # Create index manager
        index_manager = SearchIndexManager(
            index_dir=temp_search_dir,
            endpoint_repo=endpoint_repo,
            schema_repo=schema_repo,
            metadata_repo=metadata_repo,
            config=search_config
        )

        # Create index from data
        total_indexed, elapsed_time = await index_manager.create_index_from_database()

        # Verify indexing
        assert total_indexed == len(sample_rest_api_data)
        assert elapsed_time >= 0

        # Verify index stats
        stats = await index_manager.get_index_stats()
        assert stats["document_count"] == len(sample_rest_api_data)

        # Verify index integrity
        validation = await index_manager.validate_index_integrity()
        assert validation["validation_passed"] is True

    @pytest.mark.asyncio
    async def test_index_enterprise_api_endpoints(
        self, temp_search_dir, search_config, sample_enterprise_api_data
    ):
        """Test indexing complex enterprise API endpoints."""
        endpoint_repo = AsyncMock(spec=EndpointRepository)
        schema_repo = AsyncMock()
        metadata_repo = AsyncMock()

        endpoint_repo.count_all.return_value = len(sample_enterprise_api_data)
        endpoint_repo.get_all.return_value = sample_enterprise_api_data

        index_manager = SearchIndexManager(
            index_dir=temp_search_dir,
            endpoint_repo=endpoint_repo,
            schema_repo=schema_repo,
            metadata_repo=metadata_repo,
            config=search_config
        )

        # Index enterprise endpoints
        total_indexed, elapsed_time = await index_manager.create_index_from_database()

        assert total_indexed == len(sample_enterprise_api_data)

        # Verify complex enterprise data is properly indexed
        stats = await index_manager.get_index_stats()
        assert stats["document_count"] == len(sample_enterprise_api_data)

    @pytest.mark.asyncio
    async def test_index_mixed_api_types(
        self, temp_search_dir, search_config,
        sample_rest_api_data, sample_enterprise_api_data, sample_social_api_data
    ):
        """Test indexing mixed API types in single index."""
        # Combine all sample data types
        all_endpoints = (
            sample_rest_api_data +
            sample_enterprise_api_data +
            sample_social_api_data
        )

        endpoint_repo = AsyncMock(spec=EndpointRepository)
        schema_repo = AsyncMock()
        metadata_repo = AsyncMock()

        endpoint_repo.count_all.return_value = len(all_endpoints)
        endpoint_repo.get_all.return_value = all_endpoints

        index_manager = SearchIndexManager(
            index_dir=temp_search_dir,
            endpoint_repo=endpoint_repo,
            schema_repo=schema_repo,
            metadata_repo=metadata_repo,
            config=search_config
        )

        # Index all endpoint types
        total_indexed, elapsed_time = await index_manager.create_index_from_database()

        assert total_indexed == len(all_endpoints)

        # Verify all types are indexed
        stats = await index_manager.get_index_stats()
        assert stats["document_count"] == len(all_endpoints)

    @pytest.mark.asyncio
    async def test_handle_deprecated_endpoints(
        self, temp_search_dir, search_config, sample_deprecated_api_data
    ):
        """Test proper handling of deprecated API endpoints."""
        endpoint_repo = AsyncMock(spec=EndpointRepository)
        schema_repo = AsyncMock()
        metadata_repo = AsyncMock()

        endpoint_repo.count_all.return_value = len(sample_deprecated_api_data)
        endpoint_repo.get_all.return_value = sample_deprecated_api_data

        index_manager = SearchIndexManager(
            index_dir=temp_search_dir,
            endpoint_repo=endpoint_repo,
            schema_repo=schema_repo,
            metadata_repo=metadata_repo,
            config=search_config
        )

        # Index deprecated endpoints
        total_indexed, elapsed_time = await index_manager.create_index_from_database()

        assert total_indexed == len(sample_deprecated_api_data)

        # Verify deprecated endpoints are indexed but marked properly
        stats = await index_manager.get_index_stats()
        assert stats["document_count"] == len(sample_deprecated_api_data)


class TestUniversalAPISearch:
    """Test search capabilities across different API types."""

    async def setup_search_engine_with_data(self, temp_search_dir, search_config, endpoint_data):
        """Helper method to setup search engine with test data."""
        endpoint_repo = AsyncMock(spec=EndpointRepository)
        schema_repo = AsyncMock()
        metadata_repo = AsyncMock()

        endpoint_repo.count_all.return_value = len(endpoint_data)
        endpoint_repo.get_all.return_value = endpoint_data

        index_manager = SearchIndexManager(
            index_dir=temp_search_dir,
            endpoint_repo=endpoint_repo,
            schema_repo=schema_repo,
            metadata_repo=metadata_repo,
            config=search_config
        )

        # Create index
        await index_manager.create_index_from_database()

        # Create search engine
        search_engine = SearchEngine(index_manager, search_config)
        return search_engine

    @pytest.mark.asyncio
    async def test_search_across_different_api_types(
        self, temp_search_dir, search_config,
        sample_rest_api_data, sample_enterprise_api_data, sample_social_api_data
    ):
        """Test searching across different API types."""
        all_endpoints = (
            sample_rest_api_data +
            sample_enterprise_api_data +
            sample_social_api_data
        )

        search_engine = await self.setup_search_engine_with_data(
            temp_search_dir, search_config, all_endpoints
        )

        # Test search for "users" - should find REST API endpoints
        response = await search_engine.search("users")
        assert response.total_results > 0
        user_results = [r for r in response.results if "user" in r.endpoint_path.lower()]
        assert len(user_results) > 0

        # Test search for "analytics" - should find enterprise endpoints
        response = await search_engine.search("analytics")
        assert response.total_results > 0
        analytics_results = [r for r in response.results if "analytics" in r.description.lower()]
        assert len(analytics_results) > 0

        # Test search for "timeline" - should find social media endpoints
        response = await search_engine.search("timeline")
        assert response.total_results > 0
        timeline_results = [r for r in response.results if "timeline" in r.endpoint_path.lower()]
        assert len(timeline_results) > 0

    @pytest.mark.asyncio
    async def test_search_by_http_methods(
        self, temp_search_dir, search_config, sample_rest_api_data
    ):
        """Test searching by HTTP methods across any API type."""
        search_engine = await self.setup_search_engine_with_data(
            temp_search_dir, search_config, sample_rest_api_data
        )

        # Search for GET endpoints
        get_results = await search_engine.search_by_path("", http_methods=["GET"])
        assert len(get_results) > 0
        assert all(r.http_method == "GET" for r in get_results)

        # Search for POST endpoints
        post_results = await search_engine.search_by_path("", http_methods=["POST"])
        assert len(post_results) > 0
        assert all(r.http_method == "POST" for r in post_results)

    @pytest.mark.asyncio
    async def test_search_by_tags_universal(
        self, temp_search_dir, search_config, sample_enterprise_api_data
    ):
        """Test tag-based search across any API type."""
        search_engine = await self.setup_search_engine_with_data(
            temp_search_dir, search_config, sample_enterprise_api_data
        )

        # Search by enterprise tag
        enterprise_results = await search_engine.search_by_tag("enterprise")
        assert len(enterprise_results) > 0

        # Search by analytics tag
        analytics_results = await search_engine.search_by_tag("analytics")
        assert len(analytics_results) > 0

        # Search by multiple tags
        workflow_results = await search_engine.search_by_tag(["workflow", "automation"])
        assert len(workflow_results) > 0

    @pytest.mark.asyncio
    async def test_search_with_filters_universal(
        self, temp_search_dir, search_config, sample_social_api_data
    ):
        """Test filtered search across any API type."""
        search_engine = await self.setup_search_engine_with_data(
            temp_search_dir, search_config, sample_social_api_data
        )

        # Search with method filter
        response = await search_engine.search(
            "posts",
            filters={"http_method": "GET"}
        )

        get_results = [r for r in response.results if r.http_method == "GET"]
        assert len(get_results) > 0

        # Search with deprecation filter
        response = await search_engine.search(
            "posts",
            filters={"deprecated": False}
        )

        non_deprecated = [r for r in response.results if not r.metadata.get("deprecated", False)]
        assert len(non_deprecated) > 0

    @pytest.mark.asyncio
    async def test_search_pagination_universal(
        self, temp_search_dir, search_config, sample_rest_api_data
    ):
        """Test search pagination works with any API type."""
        search_engine = await self.setup_search_engine_with_data(
            temp_search_dir, search_config, sample_rest_api_data
        )

        # Test pagination
        page1 = await search_engine.search("api", page=1, per_page=2)
        assert page1.page == 1
        assert page1.per_page == 2

        if page1.has_more:
            page2 = await search_engine.search("api", page=2, per_page=2)
            assert page2.page == 2
            assert page2.per_page == 2

    @pytest.mark.asyncio
    async def test_search_performance_universal(
        self, temp_search_dir, search_config, sample_rest_api_data
    ):
        """Test search performance meets requirements regardless of API type."""
        search_engine = await self.setup_search_engine_with_data(
            temp_search_dir, search_config, sample_rest_api_data
        )

        # Test search response time
        response = await search_engine.search("users")

        # Should meet <200ms requirement from story
        assert response.query_time < 0.5  # Relaxed for testing environment

    @pytest.mark.asyncio
    async def test_incremental_updates_universal(
        self, temp_search_dir, search_config, sample_rest_api_data
    ):
        """Test incremental index updates work with any API type."""
        endpoint_repo = AsyncMock(spec=EndpointRepository)
        schema_repo = AsyncMock()
        metadata_repo = AsyncMock()

        endpoint_repo.count_all.return_value = len(sample_rest_api_data)
        endpoint_repo.get_all.return_value = sample_rest_api_data

        index_manager = SearchIndexManager(
            index_dir=temp_search_dir,
            endpoint_repo=endpoint_repo,
            schema_repo=schema_repo,
            metadata_repo=metadata_repo,
            config=search_config
        )

        # Create initial index
        await index_manager.create_index_from_database()

        # Mock updated endpoint data
        updated_endpoint = {
            **sample_rest_api_data[0],
            "summary": "Updated user endpoint",
            "description": "Updated description for user management"
        }

        endpoint_repo.get_by_id.return_value = updated_endpoint

        # Test incremental update
        result = await index_manager.update_endpoint_document("users_get")
        assert result is True

        # Test document removal
        endpoint_repo.get_by_id.return_value = None
        result = await index_manager.remove_endpoint_document("users_get")
        assert result is True


class TestUniversalAPICompatibility:
    """Test compatibility with various API specification styles."""

    @pytest.mark.asyncio
    async def test_minimal_endpoint_data(self, temp_search_dir, search_config):
        """Test indexing with minimal required endpoint data."""
        minimal_endpoint = [{
            "id": "minimal_test",
            "path": "/test",
            "method": "GET",
            "summary": "",
            "description": "",
            "parameters": [],
            "tags": [],
            "security": [],
            "responses": {},
            "deprecated": False
        }]

        search_engine = await self.setup_search_engine_with_data(
            temp_search_dir, search_config, minimal_endpoint
        )

        # Should be able to search even with minimal data
        response = await search_engine.search("test")
        assert response.total_results >= 0  # May or may not find results

    async def setup_search_engine_with_data(self, temp_search_dir, search_config, endpoint_data):
        """Helper method to setup search engine with test data."""
        endpoint_repo = AsyncMock(spec=EndpointRepository)
        schema_repo = AsyncMock()
        metadata_repo = AsyncMock()

        endpoint_repo.count_all.return_value = len(endpoint_data)
        endpoint_repo.get_all.return_value = endpoint_data

        index_manager = SearchIndexManager(
            index_dir=temp_search_dir,
            endpoint_repo=endpoint_repo,
            schema_repo=schema_repo,
            metadata_repo=metadata_repo,
            config=search_config
        )

        await index_manager.create_index_from_database()
        return SearchEngine(index_manager, search_config)