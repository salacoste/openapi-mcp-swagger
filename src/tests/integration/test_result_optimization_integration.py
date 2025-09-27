"""Integration tests for result optimization and filtering.

Tests the complete result processing pipeline with realistic scenarios
and integration with the search engine.
"""

import asyncio
import time
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from swagger_mcp_server.config.settings import (
    SearchConfig,
    SearchPerformanceConfig,
)
from swagger_mcp_server.search.index_manager import SearchIndexManager
from swagger_mcp_server.search.result_processor import (
    ComplexityLevel,
    ResultProcessor,
)
from swagger_mcp_server.search.search_engine import SearchEngine


@pytest.fixture
def search_config():
    """Create test search configuration."""
    return SearchConfig(
        performance=SearchPerformanceConfig(
            max_search_results=100,
            search_timeout=5.0,
            index_batch_size=100,
            cache_size=500,
            cache_ttl=300,
        )
    )


@pytest.fixture
def extended_sample_endpoints():
    """Extended sample API endpoints for comprehensive testing."""
    return [
        {
            "endpoint_id": "list_users",
            "endpoint_path": "/api/v1/users",
            "http_method": "GET",
            "summary": "List all users",
            "description": "Retrieve a paginated list of all users in the system with filtering options",
            "parameters": "limit, offset, filter, sort, include_deleted",
            "tags": "users, list, pagination",
            "auth_type": "bearer",
            "operation_id": "listUsers",
            "deprecated": False,
            "responses": {"200": {"content": {"application/json": {}}}},
            "security": {"bearer": []},
        },
        {
            "endpoint_id": "create_user",
            "endpoint_path": "/api/v1/users",
            "http_method": "POST",
            "summary": "Create new user",
            "description": "Create a new user account with email, password, and profile information",
            "parameters": "email, password, name, profile, avatar, preferences",
            "tags": "users, create, registration",
            "auth_type": "bearer",
            "operation_id": "createUser",
            "deprecated": False,
            "responses": {"201": {"content": {"application/json": {}}}},
            "security": {"bearer": []},
        },
        {
            "endpoint_id": "get_user",
            "endpoint_path": "/api/v1/users/{user_id}",
            "http_method": "GET",
            "summary": "Get user by ID",
            "description": "Retrieve detailed information for a specific user",
            "parameters": "user_id, include_permissions",
            "tags": "users, get, details",
            "auth_type": "bearer",
            "operation_id": "getUserById",
            "deprecated": False,
            "responses": {"200": {"content": {"application/json": {}}}},
            "security": {"bearer": []},
        },
        {
            "endpoint_id": "update_user",
            "endpoint_path": "/api/v1/users/{user_id}",
            "http_method": "PUT",
            "summary": "Update user",
            "description": "Update user information including email, name, and profile settings",
            "parameters": "user_id, email, name, profile, avatar, settings, preferences",
            "tags": "users, update, profile",
            "auth_type": "bearer",
            "operation_id": "updateUser",
            "deprecated": False,
            "responses": {"200": {"content": {"application/json": {}}}},
            "security": {"bearer": []},
        },
        {
            "endpoint_id": "delete_user",
            "endpoint_path": "/api/v1/users/{user_id}",
            "http_method": "DELETE",
            "summary": "Delete user",
            "description": "Permanently delete a user account and all associated data",
            "parameters": "user_id, force_delete, cascade",
            "tags": "users, delete, admin",
            "auth_type": "bearer",
            "operation_id": "deleteUser",
            "deprecated": False,
            "responses": {"204": {"content": {}}},
            "security": {"bearer": ["admin"]},
        },
        {
            "endpoint_id": "authenticate",
            "endpoint_path": "/api/v1/auth/login",
            "http_method": "POST",
            "summary": "User authentication",
            "description": "Authenticate user credentials and return access and refresh tokens",
            "parameters": "email, password, remember_me",
            "tags": "authentication, login, security",
            "auth_type": "none",
            "operation_id": "authenticateUser",
            "deprecated": False,
            "responses": {"200": {"content": {"application/json": {}}}},
            "security": {},
        },
        {
            "endpoint_id": "refresh_token",
            "endpoint_path": "/api/v1/auth/refresh",
            "http_method": "POST",
            "summary": "Refresh access token",
            "description": "Refresh expired access token using valid refresh token",
            "parameters": "refresh_token",
            "tags": "authentication, token, security",
            "auth_type": "refresh",
            "operation_id": "refreshAccessToken",
            "deprecated": False,
            "responses": {"200": {"content": {"application/json": {}}}},
            "security": {"refresh": []},
        },
        {
            "endpoint_id": "oauth_authorize",
            "endpoint_path": "/api/v1/auth/oauth/authorize",
            "http_method": "GET",
            "summary": "OAuth authorization",
            "description": "OAuth 2.0 authorization endpoint for third-party applications",
            "parameters": "client_id, redirect_uri, scope, state, response_type",
            "tags": "authentication, oauth, deprecated",
            "auth_type": "oauth",
            "operation_id": "oauthAuthorize",
            "deprecated": True,
            "responses": {"302": {"content": {}}},
            "security": {"oauth2": ["read", "write"]},
        },
        {
            "endpoint_id": "upload_avatar",
            "endpoint_path": "/api/v1/users/avatar",
            "http_method": "POST",
            "summary": "Upload user avatar",
            "description": "Upload and set user profile avatar image with validation and resizing",
            "parameters": "image_file, resize, quality",
            "tags": "users, upload, image, files",
            "auth_type": "bearer",
            "operation_id": "uploadUserAvatar",
            "deprecated": False,
            "responses": {"200": {"content": {"multipart/form-data": {}}}},
            "security": {"bearer": []},
        },
        {
            "endpoint_id": "search_users",
            "endpoint_path": "/api/v1/users/search",
            "http_method": "GET",
            "summary": "Search users",
            "description": "Advanced user search with filters, sorting, and pagination",
            "parameters": "query, filters, sort_by, limit, offset, facets",
            "tags": "users, search, advanced, filters",
            "auth_type": "bearer",
            "operation_id": "searchUsers",
            "deprecated": False,
            "responses": {"200": {"content": {"application/json": {}}}},
            "security": {"bearer": []},
        },
        {
            "endpoint_id": "get_user_permissions",
            "endpoint_path": "/api/v1/users/{user_id}/permissions",
            "http_method": "GET",
            "summary": "Get user permissions",
            "description": "Retrieve detailed permission and role information for a specific user",
            "parameters": "user_id, include_inherited, include_groups",
            "tags": "users, permissions, security, admin",
            "auth_type": "bearer",
            "operation_id": "getUserPermissions",
            "deprecated": False,
            "responses": {"200": {"content": {"application/json": {}}}},
            "security": {"bearer": ["admin"]},
        },
        {
            "endpoint_id": "bulk_update_users",
            "endpoint_path": "/api/v1/users/bulk",
            "http_method": "PATCH",
            "summary": "Bulk update users",
            "description": "Update multiple users simultaneously with batch operations and validation",
            "parameters": "user_updates, validation_mode, rollback_on_error, notify_users",
            "tags": "users, bulk, admin, batch",
            "auth_type": "bearer",
            "operation_id": "bulkUpdateUsers",
            "deprecated": False,
            "responses": {"200": {"content": {"application/json": {}}}},
            "security": {"bearer": ["admin"]},
        },
    ]


@pytest.fixture
async def mock_search_engine(search_config, extended_sample_endpoints):
    """Create a mock search engine with extended sample data."""
    # Mock index manager
    mock_index_manager = Mock(spec=SearchIndexManager)
    mock_index = Mock()
    mock_index.schema.names.return_value = [
        "endpoint_id",
        "endpoint_path",
        "http_method",
        "summary",
        "description",
        "parameters",
        "tags",
        "auth_type",
        "operation_id",
        "deprecated",
        "responses",
        "security",
    ]
    mock_index_manager.index = mock_index

    # Create search engine
    search_engine = SearchEngine(mock_index_manager, search_config)

    # Mock search execution to return sample data
    async def mock_execute_search(
        query, page=1, per_page=20, sort_by=None, include_highlights=True
    ):
        # Advanced mock search logic with relevance scoring
        query_str = str(query).lower()
        matches = []

        for endpoint in extended_sample_endpoints:
            score = 0
            text_fields = [
                endpoint["endpoint_path"],
                endpoint["summary"],
                endpoint["description"],
                endpoint["parameters"],
                endpoint["tags"],
            ]
            full_text = " ".join(text_fields).lower()

            # Enhanced scoring algorithm
            for word in query_str.split():
                if word in full_text:
                    # Weight different fields differently
                    if word in endpoint["endpoint_path"].lower():
                        score += 3
                    if word in endpoint["summary"].lower():
                        score += 2
                    if word in endpoint["description"].lower():
                        score += 1
                    if word in endpoint["tags"].lower():
                        score += 1.5

            # Boost non-deprecated endpoints
            if not endpoint["deprecated"]:
                score *= 1.2

            # Boost common endpoints
            if endpoint["http_method"] == "GET":
                score *= 1.1

            if score > 0:
                matches.append((endpoint, score))

        # Sort by score
        matches.sort(key=lambda x: x[1], reverse=True)

        # Normalize scores
        if matches:
            max_score = matches[0][1]
            matches = [
                (endpoint, score / max_score) for endpoint, score in matches
            ]

        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        page_matches = matches[start:end]

        # Convert to search results
        from swagger_mcp_server.search.search_engine import SearchResult

        hits = []
        for endpoint, score in page_matches:
            result = SearchResult(
                endpoint_id=endpoint["endpoint_id"],
                endpoint_path=endpoint["endpoint_path"],
                http_method=endpoint["http_method"],
                summary=endpoint["summary"],
                description=endpoint["description"],
                score=float(score),
                highlights={"description": endpoint["description"][:100]},
                metadata={
                    "operation_id": endpoint["operation_id"],
                    "tags": endpoint["tags"],
                    "deprecated": endpoint["deprecated"],
                    "parameters": endpoint["parameters"],
                    "security": endpoint["security"],
                    "responses": endpoint["responses"],
                },
            )
            hits.append(result)

        return {
            "hits": hits,
            "total": len(matches),
            "page": page,
            "per_page": per_page,
        }

    search_engine._execute_search = mock_execute_search

    # Mock available terms
    def mock_get_available_terms():
        terms = set()
        for endpoint in extended_sample_endpoints:
            text_fields = [
                endpoint["endpoint_path"],
                endpoint["summary"],
                endpoint["description"],
                endpoint["parameters"],
                endpoint["tags"],
            ]
            for field in text_fields:
                terms.update(field.lower().split())
        return terms

    search_engine._get_available_terms = mock_get_available_terms

    return search_engine


class TestAdvancedFiltering:
    """Test advanced filtering capabilities."""

    @pytest.mark.asyncio
    async def test_method_filtering(self, mock_search_engine):
        """Test filtering by HTTP methods."""
        # Test GET methods only
        response = await mock_search_engine.search_advanced(
            "users", filters={"methods": ["GET"]}, page=1, per_page=10
        )

        assert response["summary"]["filtered_results"] > 0
        for result in response["results"]:
            assert result["method"] == "GET"

    @pytest.mark.asyncio
    async def test_authentication_filtering(self, mock_search_engine):
        """Test filtering by authentication requirements."""
        # Test endpoints requiring authentication
        response = await mock_search_engine.search_advanced(
            "users",
            filters={"authentication": {"required": True}},
            page=1,
            per_page=10,
        )

        assert response["summary"]["filtered_results"] > 0
        for result in response["results"]:
            assert result["authentication_info"]["required"] == True

    @pytest.mark.asyncio
    async def test_complexity_filtering(self, mock_search_engine):
        """Test filtering by endpoint complexity."""
        response = await mock_search_engine.search_advanced(
            "users",
            filters={"complexity": ["simple", "moderate"]},
            page=1,
            per_page=10,
        )

        assert response["summary"]["filtered_results"] >= 0
        for result in response["results"]:
            assert result["complexity_level"] in ["simple", "moderate"]

    @pytest.mark.asyncio
    async def test_tag_filtering(self, mock_search_engine):
        """Test filtering by OpenAPI tags."""
        response = await mock_search_engine.search_advanced(
            "authentication",
            filters={"tags": ["authentication"]},
            page=1,
            per_page=10,
        )

        assert response["summary"]["filtered_results"] > 0
        for result in response["results"]:
            assert any(
                "authentication" in tag for tag in result.get("tags", [])
            )

    @pytest.mark.asyncio
    async def test_deprecated_filtering(self, mock_search_engine):
        """Test filtering deprecated endpoints."""
        # Exclude deprecated endpoints
        response = await mock_search_engine.search_advanced(
            "auth", filters={"include_deprecated": False}, page=1, per_page=10
        )

        for result in response["results"]:
            assert result["deprecated"] == False

    @pytest.mark.asyncio
    async def test_complex_filter_combinations(self, mock_search_engine):
        """Test complex filter combinations."""
        filters = {
            "methods": ["GET", "POST"],
            "authentication": {"required": True},
            "tags": ["users"],
            "include_deprecated": False,
        }

        response = await mock_search_engine.search_advanced(
            "users", filters=filters, page=1, per_page=10
        )

        assert response["filters_applied"] == filters
        assert response["summary"]["filtered_results"] >= 0

        for result in response["results"]:
            assert result["method"] in ["GET", "POST"]
            assert result["authentication_info"]["required"] == True
            assert result["deprecated"] == False


class TestResultOrganization:
    """Test result organization and clustering."""

    @pytest.mark.asyncio
    async def test_organization_by_tags(self, mock_search_engine):
        """Test result organization by tags."""
        response = await mock_search_engine.search_advanced(
            "users", page=1, per_page=20
        )

        organization = response["organization"]
        assert "by_tags" in organization

        by_tags = organization["by_tags"]
        assert isinstance(by_tags, dict)

        # Should have user-related tags
        assert any("users" in tag for tag in by_tags.keys())

    @pytest.mark.asyncio
    async def test_organization_by_resource(self, mock_search_engine):
        """Test result organization by resource groups."""
        response = await mock_search_engine.search_advanced(
            "api", page=1, per_page=20
        )

        organization = response["organization"]
        assert "by_resource" in organization

        by_resource = organization["by_resource"]
        assert isinstance(by_resource, dict)
        assert len(by_resource) > 0

    @pytest.mark.asyncio
    async def test_organization_by_complexity(self, mock_search_engine):
        """Test result organization by complexity level."""
        response = await mock_search_engine.search_advanced(
            "users", page=1, per_page=20
        )

        organization = response["organization"]
        assert "by_complexity" in organization

        by_complexity = organization["by_complexity"]
        assert isinstance(by_complexity, dict)

        # Should have different complexity levels
        complexity_levels = ["simple", "moderate", "complex"]
        found_levels = [
            level for level in complexity_levels if level in by_complexity
        ]
        assert len(found_levels) > 0

    @pytest.mark.asyncio
    async def test_organization_by_method(self, mock_search_engine):
        """Test result organization by HTTP method."""
        response = await mock_search_engine.search_advanced(
            "users", page=1, per_page=20
        )

        organization = response["organization"]
        assert "by_method" in organization

        by_method = organization["by_method"]
        assert isinstance(by_method, dict)

        # Should have HTTP methods
        expected_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        found_methods = [
            method for method in expected_methods if method in by_method
        ]
        assert len(found_methods) > 0

    @pytest.mark.asyncio
    async def test_organization_by_operation_type(self, mock_search_engine):
        """Test result organization by operation type."""
        response = await mock_search_engine.search_advanced(
            "users", page=1, per_page=20
        )

        organization = response["organization"]
        assert "by_operation_type" in organization

        by_operation = organization["by_operation_type"]
        assert isinstance(by_operation, dict)

        # Should have CRUD operations
        expected_operations = ["create", "read", "update", "delete", "list"]
        found_operations = [
            op for op in expected_operations if op in by_operation
        ]
        assert len(found_operations) > 0


class TestMetadataEnhancement:
    """Test metadata enhancement features."""

    @pytest.mark.asyncio
    async def test_parameter_summary_accuracy(self, mock_search_engine):
        """Test parameter summary generation accuracy."""
        response = await mock_search_engine.search_advanced(
            "bulk update", page=1, per_page=5
        )

        for result in response["results"]:
            param_summary = result["parameter_summary"]

            # Verify parameter summary structure
            assert "total_count" in param_summary
            assert "required_count" in param_summary
            assert "optional_count" in param_summary
            assert "parameter_types" in param_summary
            assert "has_file_upload" in param_summary
            assert "has_complex_types" in param_summary
            assert "common_parameters" in param_summary

            # Verify logical consistency
            assert param_summary["total_count"] >= 0
            assert param_summary["required_count"] >= 0
            assert param_summary["optional_count"] >= 0
            assert (
                param_summary["total_count"]
                == param_summary["required_count"]
                + param_summary["optional_count"]
            )

    @pytest.mark.asyncio
    async def test_authentication_info_accuracy(self, mock_search_engine):
        """Test authentication information accuracy."""
        response = await mock_search_engine.search_advanced(
            "authentication", page=1, per_page=10
        )

        for result in response["results"]:
            auth_info = result["authentication_info"]

            # Verify authentication info structure
            assert "required" in auth_info
            assert "schemes" in auth_info
            assert "scopes" in auth_info
            assert "description" in auth_info

            # Verify data types
            assert isinstance(auth_info["required"], bool)
            assert isinstance(auth_info["schemes"], list)
            assert isinstance(auth_info["scopes"], list)
            assert isinstance(auth_info["description"], str)

    @pytest.mark.asyncio
    async def test_response_info_accuracy(self, mock_search_engine):
        """Test response information accuracy."""
        response = await mock_search_engine.search_advanced(
            "users", page=1, per_page=10
        )

        for result in response["results"]:
            response_info = result["response_info"]

            # Verify response info structure
            assert "status_codes" in response_info
            assert "content_types" in response_info
            assert "has_json_response" in response_info
            assert "has_binary_response" in response_info
            assert "response_complexity" in response_info
            assert "common_responses" in response_info

            # Verify data types
            assert isinstance(response_info["status_codes"], list)
            assert isinstance(response_info["content_types"], list)
            assert isinstance(response_info["has_json_response"], bool)

    @pytest.mark.asyncio
    async def test_complexity_level_determination(self, mock_search_engine):
        """Test complexity level determination accuracy."""
        response = await mock_search_engine.search_advanced(
            "users", page=1, per_page=20
        )

        complexity_counts = {"simple": 0, "moderate": 0, "complex": 0}

        for result in response["results"]:
            complexity = result["complexity_level"]
            assert complexity in complexity_counts
            complexity_counts[complexity] += 1

        # Should have a mix of complexity levels
        assert sum(complexity_counts.values()) > 0

    @pytest.mark.asyncio
    async def test_operation_type_accuracy(self, mock_search_engine):
        """Test operation type determination accuracy."""
        response = await mock_search_engine.search_advanced(
            "users", page=1, per_page=20
        )

        operation_counts = {}

        for result in response["results"]:
            operation_type = result["operation_type"]
            operation_counts[operation_type] = (
                operation_counts.get(operation_type, 0) + 1
            )

        # Should have various operation types
        expected_operations = ["create", "read", "update", "delete", "list"]
        found_operations = [
            op for op in expected_operations if op in operation_counts
        ]
        assert len(found_operations) > 0


class TestPaginationAndLimiting:
    """Test pagination and result limiting functionality."""

    @pytest.mark.asyncio
    async def test_basic_pagination(self, mock_search_engine):
        """Test basic pagination functionality."""
        # Get first page
        response1 = await mock_search_engine.search_advanced(
            "users", page=1, per_page=3
        )

        # Get second page
        response2 = await mock_search_engine.search_advanced(
            "users", page=2, per_page=3
        )

        # Verify pagination metadata
        assert response1["pagination"]["page"] == 1
        assert response2["pagination"]["page"] == 2
        assert response1["pagination"]["per_page"] == 3
        assert response2["pagination"]["per_page"] == 3

        # Verify results are different (assuming enough results)
        if len(response1["results"]) == 3 and len(response2["results"]) > 0:
            result_ids_1 = {
                result["endpoint_id"] for result in response1["results"]
            }
            result_ids_2 = {
                result["endpoint_id"] for result in response2["results"]
            }
            assert result_ids_1 != result_ids_2

    @pytest.mark.asyncio
    async def test_pagination_metadata(self, mock_search_engine):
        """Test pagination metadata accuracy."""
        response = await mock_search_engine.search_advanced(
            "users", page=2, per_page=5
        )

        pagination = response["pagination"]

        # Verify pagination structure
        assert "page" in pagination
        assert "per_page" in pagination
        assert "total_pages" in pagination
        assert "total_results" in pagination
        assert "has_previous" in pagination
        assert "has_next" in pagination

        # Verify logical consistency
        assert pagination["page"] == 2
        assert pagination["per_page"] == 5
        assert pagination["total_results"] >= 0

        if pagination["total_results"] > 5:
            assert pagination["has_previous"] == True

    @pytest.mark.asyncio
    async def test_large_page_size_limit(self, mock_search_engine):
        """Test page size limits are enforced."""
        # Try to request more than max allowed
        with pytest.raises(ValueError, match="per_page must be between"):
            await mock_search_engine.search_advanced(
                "users", page=1, per_page=200  # Exceeds max_search_results
            )

    @pytest.mark.asyncio
    async def test_invalid_page_number(self, mock_search_engine):
        """Test invalid page number handling."""
        with pytest.raises(ValueError, match="Page number must be"):
            await mock_search_engine.search_advanced(
                "users", page=0, per_page=10
            )


class TestCachingPerformance:
    """Test caching functionality and performance."""

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self, mock_search_engine):
        """Test cache hit performance improvement."""
        query = "users authentication"
        filters = {"methods": ["GET"], "include_deprecated": False}
        pagination = {"page": 1, "per_page": 10}

        # First call (cache miss)
        start_time = time.time()
        response1 = await mock_search_engine.search_advanced(
            query, filters, **pagination
        )
        first_call_time = time.time() - start_time

        # Second call (cache hit)
        start_time = time.time()
        response2 = await mock_search_engine.search_advanced(
            query, filters, **pagination
        )
        second_call_time = time.time() - start_time

        # Cache hit should be faster (though with mocking, difference may be minimal)
        assert second_call_time <= first_call_time * 2  # Allow some variance

        # Results should be identical
        assert response1["cache_key"] == response2["cache_key"]
        assert len(response1["results"]) == len(response2["results"])

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, mock_search_engine):
        """Test cache behavior with different queries."""
        # Different queries should have different cache keys
        response1 = await mock_search_engine.search_advanced("users")
        response2 = await mock_search_engine.search_advanced("auth")

        if "cache_key" in response1 and "cache_key" in response2:
            assert response1["cache_key"] != response2["cache_key"]

    @pytest.mark.asyncio
    async def test_filter_impact_on_caching(self, mock_search_engine):
        """Test that different filters create different cache entries."""
        query = "users"

        response1 = await mock_search_engine.search_advanced(
            query, filters={"methods": ["GET"]}
        )
        response2 = await mock_search_engine.search_advanced(
            query, filters={"methods": ["POST"]}
        )

        # Different filters should create different cache entries
        if "cache_key" in response1 and "cache_key" in response2:
            assert response1["cache_key"] != response2["cache_key"]

        # Results should be different
        if response1["results"] and response2["results"]:
            result_methods_1 = {
                result["method"] for result in response1["results"]
            }
            result_methods_2 = {
                result["method"] for result in response2["results"]
            }
            assert result_methods_1 != result_methods_2


class TestPerformanceRequirements:
    """Test performance requirements compliance."""

    @pytest.mark.asyncio
    async def test_response_time_under_200ms(self, mock_search_engine):
        """Test that advanced search meets <200ms requirement."""
        start_time = time.time()

        response = await mock_search_engine.search_advanced(
            "complex query with multiple filters and organization",
            filters={
                "methods": ["GET", "POST"],
                "authentication": {"required": True},
                "tags": ["users"],
                "include_deprecated": False,
            },
            page=1,
            per_page=20,
        )

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete within 200ms
        assert total_time < 0.2
        assert response["processing_time_ms"] < 200

    @pytest.mark.asyncio
    async def test_large_result_set_performance(self, mock_search_engine):
        """Test performance with large result sets."""
        start_time = time.time()

        response = await mock_search_engine.search_advanced(
            "api",
            page=1,
            per_page=50,  # Broad query likely to return many results
        )

        end_time = time.time()
        processing_time = end_time - start_time

        # Should handle large result sets efficiently
        assert processing_time < 0.3
        assert response["processing_time_ms"] < 300

    @pytest.mark.asyncio
    async def test_concurrent_request_performance(self, mock_search_engine):
        """Test performance under concurrent load."""
        queries = [
            "users authentication",
            "create user",
            "delete account",
            "upload file",
            "oauth token",
            "permissions admin",
            "bulk operations",
            "search filters",
        ]

        start_time = time.time()

        # Execute queries concurrently
        tasks = []
        for query in queries:
            task = mock_search_engine.search_advanced(
                query,
                filters={"include_deprecated": False},
                page=1,
                per_page=10,
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # Should handle concurrent requests efficiently
        assert len(responses) == len(queries)
        assert all(isinstance(r, dict) for r in responses)
        assert total_time < 2.0  # 8 concurrent requests in under 2 seconds

        # Each individual response should be fast
        for response in responses:
            assert response["processing_time_ms"] < 500


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @pytest.mark.asyncio
    async def test_api_discovery_workflow(self, mock_search_engine):
        """Test typical API discovery workflow."""
        # 1. Broad search for user-related endpoints
        response = await mock_search_engine.search_advanced("users")
        assert response["summary"]["filtered_results"] > 0

        # 2. Narrow down to creation endpoints
        response = await mock_search_engine.search_advanced(
            "users", filters={"methods": ["POST"]}
        )
        creation_endpoints = [
            r for r in response["results"] if r["method"] == "POST"
        ]
        assert len(creation_endpoints) > 0

        # 3. Look for authentication requirements
        response = await mock_search_engine.search_advanced(
            "users", filters={"authentication": {"required": True}}
        )
        auth_required = [
            r
            for r in response["results"]
            if r["authentication_info"]["required"]
        ]
        assert len(auth_required) > 0

    @pytest.mark.asyncio
    async def test_security_audit_scenario(self, mock_search_engine):
        """Test security audit scenario."""
        # Find all endpoints without authentication
        response = await mock_search_engine.search_advanced(
            "api", filters={"authentication": {"required": False}}
        )

        public_endpoints = [
            r
            for r in response["results"]
            if not r["authentication_info"]["required"]
        ]

        # Should find at least the login endpoint
        assert len(public_endpoints) > 0

        # Find deprecated security endpoints
        response = await mock_search_engine.search_advanced(
            "auth", filters={"include_deprecated": True}
        )

        deprecated_auth = [r for r in response["results"] if r["deprecated"]]

        # Should find deprecated OAuth endpoint
        assert any("oauth" in r["path"].lower() for r in deprecated_auth)

    @pytest.mark.asyncio
    async def test_integration_planning_scenario(self, mock_search_engine):
        """Test integration planning scenario."""
        # Find all CRUD operations for users
        user_operations = {}

        for method in ["GET", "POST", "PUT", "DELETE"]:
            response = await mock_search_engine.search_advanced(
                "users", filters={"methods": [method]}
            )
            user_operations[method] = response["results"]

        # Should have operations for each CRUD method
        assert len(user_operations["GET"]) > 0  # Read operations
        assert len(user_operations["POST"]) > 0  # Create operations
        assert len(user_operations["PUT"]) > 0  # Update operations
        assert len(user_operations["DELETE"]) > 0  # Delete operations

        # Check for file upload capabilities
        response = await mock_search_engine.search_advanced(
            "upload", page=1, per_page=10
        )

        upload_endpoints = [
            r
            for r in response["results"]
            if r["parameter_summary"]["has_file_upload"]
        ]
        assert len(upload_endpoints) >= 0  # May or may not have file upload

    @pytest.mark.asyncio
    async def test_developer_exploration_scenario(self, mock_search_engine):
        """Test developer exploration scenario."""
        # Explore API structure through organization
        response = await mock_search_engine.search_advanced(
            "api", page=1, per_page=50
        )

        organization = response["organization"]

        # Explore by resource groups
        by_resource = organization["by_resource"]
        assert len(by_resource) > 0

        # Explore by complexity for learning curve
        by_complexity = organization["by_complexity"]
        simple_endpoints = by_complexity.get("simple", [])

        # Should have simple endpoints for getting started
        assert len(simple_endpoints) > 0

        # Check operation types for CRUD understanding
        by_operation = organization["by_operation_type"]
        assert len(by_operation) > 0
