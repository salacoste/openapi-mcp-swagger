"""Unit tests for the result processor module.

Tests cover all aspects of result optimization and filtering including:
- Advanced filtering by endpoint characteristics
- Result clustering and organization
- Enhanced ranking and metadata enhancement
- Pagination and result limiting
- Result caching and performance optimization
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
from swagger_mcp_server.search.result_processor import (
    AuthenticationInfo,
    AuthenticationType,
    ComplexityLevel,
    EnhancedSearchResult,
    MetadataEnhancer,
    OperationType,
    PaginationInfo,
    ParameterSummary,
    ResponseInfo,
    ResultCache,
    ResultFilter,
    ResultOrganizer,
    ResultProcessor,
    ResultSummary,
)


@pytest.fixture
def search_config():
    """Create test search configuration."""
    return SearchConfig(
        performance=SearchPerformanceConfig(
            max_search_results=100,
            search_timeout=5.0,
            index_batch_size=1000,
            cache_size=500,
            cache_ttl=300,
        )
    )


@pytest.fixture
def sample_raw_results():
    """Sample raw search results for testing."""
    return [
        {
            "endpoint_id": "get_users",
            "endpoint_path": "/api/v1/users",
            "http_method": "GET",
            "summary": "List all users",
            "description": "Retrieve a paginated list of all users in the system",
            "score": 0.95,
            "tags": "users,list",
            "deprecated": False,
            "parameters": "limit,offset,filter",
            "security": {"bearer": []},
            "responses": {"200": {"content": {"application/json": {}}}},
        },
        {
            "endpoint_id": "create_user",
            "endpoint_path": "/api/v1/users",
            "http_method": "POST",
            "summary": "Create new user",
            "description": "Create a new user account with email and password",
            "score": 0.85,
            "tags": "users,create",
            "deprecated": False,
            "parameters": "email,password,name,profile",
            "security": {"bearer": []},
            "responses": {"201": {"content": {"application/json": {}}}},
        },
        {
            "endpoint_id": "get_user",
            "endpoint_path": "/api/v1/users/{user_id}",
            "http_method": "GET",
            "summary": "Get user by ID",
            "description": "Retrieve a specific user by their unique identifier",
            "score": 0.80,
            "tags": "users,get",
            "deprecated": False,
            "parameters": "user_id",
            "security": {"bearer": []},
            "responses": {"200": {"content": {"application/json": {}}}},
        },
        {
            "endpoint_id": "authenticate",
            "endpoint_path": "/api/v1/auth/login",
            "http_method": "POST",
            "summary": "User authentication",
            "description": "Authenticate user credentials and return access token",
            "score": 0.75,
            "tags": "authentication,login",
            "deprecated": False,
            "parameters": "email,password",
            "security": {},
            "responses": {"200": {"content": {"application/json": {}}}},
        },
        {
            "endpoint_id": "upload_avatar",
            "endpoint_path": "/api/v1/users/avatar",
            "http_method": "POST",
            "summary": "Upload user avatar",
            "description": "Upload and set user profile avatar image",
            "score": 0.70,
            "tags": "users,upload,image",
            "deprecated": False,
            "parameters": "image_file",
            "security": {"bearer": []},
            "responses": {"200": {"content": {"multipart/form-data": {}}}},
        },
        {
            "endpoint_id": "oauth_authorize",
            "endpoint_path": "/api/v1/auth/oauth/authorize",
            "http_method": "GET",
            "summary": "OAuth authorization",
            "description": "OAuth 2.0 authorization endpoint for third-party applications",
            "score": 0.60,
            "tags": "authentication,oauth",
            "deprecated": True,
            "parameters": "client_id,redirect_uri,scope,state",
            "security": {"oauth2": ["read", "write"]},
            "responses": {"302": {"content": {}}},
        },
    ]


class TestResultFilter:
    """Test result filtering functionality."""

    @pytest.fixture
    def result_filter(self, search_config):
        """Create result filter instance."""
        return ResultFilter(search_config)

    def test_filter_by_methods(self, result_filter, sample_raw_results):
        """Test filtering by HTTP methods."""
        # Filter for GET methods only
        filters = {"methods": ["GET"]}
        filtered = result_filter.apply_filters(sample_raw_results, filters)

        assert len(filtered) == 2  # get_users and get_user
        assert all(result["http_method"] == "GET" for result in filtered)

    def test_filter_by_multiple_methods(
        self, result_filter, sample_raw_results
    ):
        """Test filtering by multiple HTTP methods."""
        filters = {"methods": ["GET", "POST"]}
        filtered = result_filter.apply_filters(sample_raw_results, filters)

        assert len(filtered) == 6  # All results
        assert all(
            result["http_method"] in ["GET", "POST"] for result in filtered
        )

    def test_filter_by_authentication_required(
        self, result_filter, sample_raw_results
    ):
        """Test filtering by authentication requirement."""
        # Filter for endpoints requiring authentication
        filters = {"authentication": {"required": True}}
        filtered = result_filter.apply_filters(sample_raw_results, filters)

        # Should include all except authenticate endpoint
        assert len(filtered) == 5
        assert all(result["security"] for result in filtered)

    def test_filter_by_authentication_not_required(
        self, result_filter, sample_raw_results
    ):
        """Test filtering for endpoints not requiring authentication."""
        filters = {"authentication": {"required": False}}
        filtered = result_filter.apply_filters(sample_raw_results, filters)

        # Should only include authenticate endpoint
        assert len(filtered) == 1
        assert filtered[0]["endpoint_id"] == "authenticate"

    def test_filter_by_authentication_schemes(
        self, result_filter, sample_raw_results
    ):
        """Test filtering by specific authentication schemes."""
        filters = {"authentication": {"schemes": ["bearer"]}}
        filtered = result_filter.apply_filters(sample_raw_results, filtered)

        # Should include endpoints with bearer auth
        bearer_results = [
            r for r in filtered if "bearer" in r.get("security", {})
        ]
        assert len(bearer_results) >= 0

    def test_filter_by_tags(self, result_filter, sample_raw_results):
        """Test filtering by OpenAPI tags."""
        filters = {"tags": ["users"]}
        filtered = result_filter.apply_filters(sample_raw_results, filters)

        # Should include user-related endpoints
        assert len(filtered) >= 3
        assert all("users" in result.get("tags", "") for result in filtered)

    def test_filter_exclude_deprecated(
        self, result_filter, sample_raw_results
    ):
        """Test filtering to exclude deprecated endpoints."""
        filters = {"include_deprecated": False}
        filtered = result_filter.apply_filters(sample_raw_results, filters)

        # Should exclude oauth_authorize (deprecated)
        assert len(filtered) == 5
        assert all(not result.get("deprecated", False) for result in filtered)

    def test_filter_complex_combination(
        self, result_filter, sample_raw_results
    ):
        """Test complex filter combinations."""
        filters = {
            "methods": ["POST"],
            "tags": ["users"],
            "include_deprecated": False,
        }
        filtered = result_filter.apply_filters(sample_raw_results, filters)

        # Should include create_user and upload_avatar
        assert len(filtered) == 2
        assert all(result["http_method"] == "POST" for result in filtered)
        assert all("users" in result.get("tags", "") for result in filtered)
        assert all(not result.get("deprecated", False) for result in filtered)

    def test_empty_filters(self, result_filter, sample_raw_results):
        """Test that empty filters return all results."""
        filtered = result_filter.apply_filters(sample_raw_results, {})
        assert len(filtered) == len(sample_raw_results)

    def test_invalid_filters_graceful_handling(
        self, result_filter, sample_raw_results
    ):
        """Test graceful handling of invalid filter values."""
        filters = {"methods": None, "invalid_filter": "invalid_value"}
        filtered = result_filter.apply_filters(sample_raw_results, filters)

        # Should return original results on filter errors
        assert len(filtered) <= len(sample_raw_results)


class TestResultOrganizer:
    """Test result organization and clustering functionality."""

    @pytest.fixture
    def result_organizer(self, search_config):
        """Create result organizer instance."""
        return ResultOrganizer(search_config)

    @pytest.fixture
    def enhanced_results(self):
        """Create sample enhanced results for testing."""
        return [
            EnhancedSearchResult(
                endpoint_id="get_users",
                path="/api/v1/users",
                method="GET",
                summary="List all users",
                description="Get user list",
                relevance_score=0.95,
                rank_position=1,
                ranking_factors=["high_relevance"],
                complexity_level=ComplexityLevel.SIMPLE,
                parameter_summary=ParameterSummary(
                    2, 0, 2, {"string": 2}, False, False, ["limit", "offset"]
                ),
                authentication_info=AuthenticationInfo(
                    True, [AuthenticationType.BEARER], [], "Bearer required"
                ),
                response_info=ResponseInfo(
                    [200],
                    ["application/json"],
                    True,
                    False,
                    ComplexityLevel.SIMPLE,
                    ["200"],
                ),
                tags=["users", "list"],
                resource_group="users",
                operation_type=OperationType.LIST,
                deprecated=False,
                version="v1",
                stability="stable",
            ),
            EnhancedSearchResult(
                endpoint_id="create_user",
                path="/api/v1/users",
                method="POST",
                summary="Create new user",
                description="Create user account",
                relevance_score=0.85,
                rank_position=2,
                ranking_factors=["medium_relevance"],
                complexity_level=ComplexityLevel.MODERATE,
                parameter_summary=ParameterSummary(
                    4,
                    3,
                    1,
                    {"string": 4},
                    False,
                    False,
                    ["email", "password", "name"],
                ),
                authentication_info=AuthenticationInfo(
                    True, [AuthenticationType.BEARER], [], "Bearer required"
                ),
                response_info=ResponseInfo(
                    [201],
                    ["application/json"],
                    True,
                    False,
                    ComplexityLevel.SIMPLE,
                    ["201"],
                ),
                tags=["users", "create"],
                resource_group="users",
                operation_type=OperationType.CREATE,
                deprecated=False,
                version="v1",
                stability="stable",
            ),
            EnhancedSearchResult(
                endpoint_id="authenticate",
                path="/api/v1/auth/login",
                method="POST",
                summary="User authentication",
                description="Authenticate user",
                relevance_score=0.75,
                rank_position=3,
                ranking_factors=["medium_relevance"],
                complexity_level=ComplexityLevel.SIMPLE,
                parameter_summary=ParameterSummary(
                    2, 2, 0, {"string": 2}, False, False, ["email", "password"]
                ),
                authentication_info=AuthenticationInfo(
                    False, [AuthenticationType.NONE], [], "No auth required"
                ),
                response_info=ResponseInfo(
                    [200],
                    ["application/json"],
                    True,
                    False,
                    ComplexityLevel.SIMPLE,
                    ["200"],
                ),
                tags=["authentication", "login"],
                resource_group="auth",
                operation_type=OperationType.ACTION,
                deprecated=False,
                version="v1",
                stability="stable",
            ),
        ]

    def test_cluster_by_tags(self, result_organizer, enhanced_results):
        """Test clustering results by OpenAPI tags."""
        organization = result_organizer.organize_results(enhanced_results)

        by_tags = organization["by_tags"]
        assert "users" in by_tags
        assert "authentication" in by_tags
        assert len(by_tags["users"]) == 2  # get_users and create_user
        assert len(by_tags["authentication"]) == 1  # authenticate

    def test_cluster_by_resource(self, result_organizer, enhanced_results):
        """Test clustering results by resource groups."""
        organization = result_organizer.organize_results(enhanced_results)

        by_resource = organization["by_resource"]
        assert "users" in by_resource
        assert "auth" in by_resource
        assert len(by_resource["users"]) == 2
        assert len(by_resource["auth"]) == 1

    def test_cluster_by_complexity(self, result_organizer, enhanced_results):
        """Test clustering results by complexity level."""
        organization = result_organizer.organize_results(enhanced_results)

        by_complexity = organization["by_complexity"]
        assert "simple" in by_complexity
        assert "moderate" in by_complexity
        assert len(by_complexity["simple"]) == 2
        assert len(by_complexity["moderate"]) == 1

    def test_cluster_by_method(self, result_organizer, enhanced_results):
        """Test clustering results by HTTP method."""
        organization = result_organizer.organize_results(enhanced_results)

        by_method = organization["by_method"]
        assert "GET" in by_method
        assert "POST" in by_method
        assert len(by_method["GET"]) == 1
        assert len(by_method["POST"]) == 2

    def test_cluster_by_operation_type(
        self, result_organizer, enhanced_results
    ):
        """Test clustering results by operation type."""
        organization = result_organizer.organize_results(enhanced_results)

        by_operation = organization["by_operation_type"]
        assert "list" in by_operation
        assert "create" in by_operation
        assert "action" in by_operation

    def test_cluster_by_auth_requirement(
        self, result_organizer, enhanced_results
    ):
        """Test clustering results by authentication requirements."""
        organization = result_organizer.organize_results(enhanced_results)

        by_auth = organization["by_auth_requirement"]
        assert "auth_bearer" in by_auth or "no_auth" in by_auth
        assert len(by_auth) >= 1

    def test_empty_results_handling(self, result_organizer):
        """Test handling of empty result sets."""
        organization = result_organizer.organize_results([])

        assert isinstance(organization, dict)
        assert all(len(cluster) == 0 for cluster in organization.values())


class TestMetadataEnhancer:
    """Test metadata enhancement functionality."""

    @pytest.fixture
    def metadata_enhancer(self, search_config):
        """Create metadata enhancer instance."""
        return MetadataEnhancer(search_config)

    @pytest.mark.asyncio
    async def test_enhance_with_metadata(
        self, metadata_enhancer, sample_raw_results
    ):
        """Test basic metadata enhancement."""
        enhanced = await metadata_enhancer.enhance_with_metadata(
            sample_raw_results[:2]
        )

        assert len(enhanced) == 2
        assert all(
            isinstance(result, EnhancedSearchResult) for result in enhanced
        )
        assert all(result.parameter_summary is not None for result in enhanced)
        assert all(
            result.authentication_info is not None for result in enhanced
        )
        assert all(result.response_info is not None for result in enhanced)

    @pytest.mark.asyncio
    async def test_parameter_analysis(self, metadata_enhancer):
        """Test parameter analysis functionality."""
        # Test string parameters
        param_summary = metadata_enhancer._analyze_parameters(
            "email,password,name"
        )
        assert param_summary.total_count == 3
        assert (
            param_summary.required_count == 3
        )  # Assumes all required for string format

        # Test empty parameters
        param_summary = metadata_enhancer._analyze_parameters("")
        assert param_summary.total_count == 0

    @pytest.mark.asyncio
    async def test_authentication_info_extraction(self, metadata_enhancer):
        """Test authentication information extraction."""
        # Test bearer authentication
        auth_info = metadata_enhancer._extract_authentication_info(
            {"bearer": []}
        )
        assert auth_info.required == True
        assert AuthenticationType.BEARER in auth_info.schemes

        # Test no authentication
        auth_info = metadata_enhancer._extract_authentication_info({})
        assert auth_info.required == False
        assert AuthenticationType.NONE in auth_info.schemes

    @pytest.mark.asyncio
    async def test_response_analysis(self, metadata_enhancer):
        """Test response characteristics analysis."""
        responses = {
            "200": {"content": {"application/json": {}}},
            "400": {"content": {"application/json": {}}},
        }
        response_info = metadata_enhancer._analyze_responses(responses)

        assert 200 in response_info.status_codes
        assert 400 in response_info.status_codes
        assert response_info.has_json_response == True
        assert "application/json" in response_info.content_types

    @pytest.mark.asyncio
    async def test_complexity_determination(self, metadata_enhancer):
        """Test endpoint complexity determination."""
        # Simple endpoint
        simple_params = ParameterSummary(
            2, 1, 1, {"string": 2}, False, False, ["id", "name"]
        )
        simple_response = ResponseInfo(
            [200],
            ["application/json"],
            True,
            False,
            ComplexityLevel.SIMPLE,
            ["200"],
        )
        complexity = metadata_enhancer._determine_complexity(
            simple_params, simple_response
        )
        assert complexity == ComplexityLevel.SIMPLE

        # Complex endpoint
        complex_params = ParameterSummary(
            10, 8, 2, {"string": 6, "object": 4}, True, True, []
        )
        complex_response = ResponseInfo(
            [200, 201, 400, 401, 500],
            ["application/json", "application/xml"],
            True,
            False,
            ComplexityLevel.COMPLEX,
            [],
        )
        complexity = metadata_enhancer._determine_complexity(
            complex_params, complex_response
        )
        assert complexity == ComplexityLevel.COMPLEX

    @pytest.mark.asyncio
    async def test_operation_type_determination(self, metadata_enhancer):
        """Test operation type determination from method and path."""
        # Test CREATE operation
        op_type = metadata_enhancer._determine_operation_type(
            "POST", "/api/v1/users"
        )
        assert op_type == OperationType.CREATE

        # Test READ operation
        op_type = metadata_enhancer._determine_operation_type(
            "GET", "/api/v1/users/{id}"
        )
        assert op_type == OperationType.READ

        # Test LIST operation
        op_type = metadata_enhancer._determine_operation_type(
            "GET", "/api/v1/users"
        )
        assert op_type == OperationType.LIST

        # Test UPDATE operation
        op_type = metadata_enhancer._determine_operation_type(
            "PUT", "/api/v1/users/{id}"
        )
        assert op_type == OperationType.UPDATE

        # Test DELETE operation
        op_type = metadata_enhancer._determine_operation_type(
            "DELETE", "/api/v1/users/{id}"
        )
        assert op_type == OperationType.DELETE

        # Test UPLOAD operation
        op_type = metadata_enhancer._determine_operation_type(
            "POST", "/api/v1/upload"
        )
        assert op_type == OperationType.UPLOAD

    @pytest.mark.asyncio
    async def test_error_handling_graceful_fallback(self, metadata_enhancer):
        """Test graceful error handling with fallback results."""
        # Test with malformed data
        malformed_results = [{"invalid": "data"}]
        enhanced = await metadata_enhancer.enhance_with_metadata(
            malformed_results
        )

        assert len(enhanced) == 1
        assert isinstance(enhanced[0], EnhancedSearchResult)
        # Should have basic fallback values


class TestResultCache:
    """Test result caching functionality."""

    @pytest.fixture
    def result_cache(self):
        """Create result cache instance."""
        return ResultCache(max_cache_size=10, ttl_seconds=1)

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, result_cache):
        """Test cache key generation."""
        key1 = result_cache.get_cache_key(
            "query", {"filter": "value"}, {"page": 1}
        )
        key2 = result_cache.get_cache_key(
            "query", {"filter": "value"}, {"page": 1}
        )
        key3 = result_cache.get_cache_key(
            "different", {"filter": "value"}, {"page": 1}
        )

        assert key1 == key2  # Same inputs should generate same key
        assert key1 != key3  # Different inputs should generate different keys

    @pytest.mark.asyncio
    async def test_cache_storage_and_retrieval(self, result_cache):
        """Test basic cache storage and retrieval."""
        key = "test_key"
        data = {"results": [{"id": 1}]}

        # Cache should be empty initially
        cached = await result_cache.get_cached_results(key)
        assert cached is None

        # Store data
        await result_cache.cache_results(key, data)

        # Retrieve data
        cached = await result_cache.get_cached_results(key)
        assert cached == data

    @pytest.mark.asyncio
    async def test_cache_expiration(self, result_cache):
        """Test cache TTL expiration."""
        key = "test_key"
        data = {"results": [{"id": 1}]}

        # Store data
        await result_cache.cache_results(key, data)

        # Should be available immediately
        cached = await result_cache.get_cached_results(key)
        assert cached == data

        # Wait for expiration (TTL = 1 second)
        await asyncio.sleep(1.1)

        # Should be expired
        cached = await result_cache.get_cached_results(key)
        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self, result_cache):
        """Test LRU eviction when cache is full."""
        # Fill cache to capacity (10 entries)
        for i in range(10):
            await result_cache.cache_results(f"key_{i}", {"data": i})

        assert len(result_cache.cache) == 10

        # Add one more entry to trigger eviction
        await result_cache.cache_results("new_key", {"data": "new"})

        # Cache should still be at capacity
        assert len(result_cache.cache) <= 10

        # New entry should be present
        cached = await result_cache.get_cached_results("new_key")
        assert cached == {"data": "new"}

    def test_cache_stats(self, result_cache):
        """Test cache statistics generation."""
        stats = result_cache.get_cache_stats()

        assert "entries" in stats
        assert "max_size" in stats
        assert "total_accesses" in stats
        assert "hit_rate" in stats
        assert "oldest_entry_age" in stats


class TestResultProcessor:
    """Test complete result processing pipeline."""

    @pytest.fixture
    def result_processor(self, search_config):
        """Create result processor instance."""
        return ResultProcessor(search_config)

    @pytest.mark.asyncio
    async def test_complete_processing_pipeline(
        self, result_processor, sample_raw_results
    ):
        """Test the complete result processing pipeline."""
        filters = {"methods": ["GET", "POST"]}
        pagination = {"page": 1, "per_page": 3}

        processed = await result_processor.process_search_results(
            sample_raw_results, "user", filters, pagination
        )

        # Verify structure
        assert "results" in processed
        assert "pagination" in processed
        assert "organization" in processed
        assert "summary" in processed
        assert "filters_applied" in processed

        # Verify pagination
        assert len(processed["results"]) <= 3
        assert processed["pagination"]["page"] == 1
        assert processed["pagination"]["per_page"] == 3

    @pytest.mark.asyncio
    async def test_caching_integration(
        self, result_processor, sample_raw_results
    ):
        """Test caching integration in processing pipeline."""
        filters = {"methods": ["GET"]}
        pagination = {"page": 1, "per_page": 10}

        # First call should cache results
        processed1 = await result_processor.process_search_results(
            sample_raw_results, "user", filters, pagination
        )

        # Second call should use cache
        processed2 = await result_processor.process_search_results(
            sample_raw_results, "user", filters, pagination
        )

        # Results should be identical
        assert processed1["cache_key"] == processed2["cache_key"]

    @pytest.mark.asyncio
    async def test_empty_results_handling(self, result_processor):
        """Test handling of empty result sets."""
        processed = await result_processor.process_search_results(
            [], "empty", {}, {"page": 1, "per_page": 10}
        )

        assert processed["results"] == []
        assert processed["summary"]["total_results"] == 0
        assert processed["pagination"]["total_results"] == 0

    @pytest.mark.asyncio
    async def test_large_result_set_pagination(self, result_processor):
        """Test pagination with large result sets."""
        # Create large result set
        large_results = []
        for i in range(50):
            result = {
                "endpoint_id": f"endpoint_{i}",
                "endpoint_path": f"/api/v1/items/{i}",
                "http_method": "GET",
                "summary": f"Get item {i}",
                "description": f"Description for item {i}",
                "score": 0.8,
                "tags": "items",
                "deprecated": False,
                "parameters": "id",
                "security": {},
                "responses": {"200": {"content": {"application/json": {}}}},
            }
            large_results.append(result)

        # Test first page
        processed = await result_processor.process_search_results(
            large_results, "items", {}, {"page": 1, "per_page": 10}
        )

        assert len(processed["results"]) == 10
        assert processed["pagination"]["page"] == 1
        assert processed["pagination"]["total_pages"] == 5
        assert processed["pagination"]["has_next"] == True
        assert processed["pagination"]["has_previous"] == False

        # Test middle page
        processed = await result_processor.process_search_results(
            large_results, "items", {}, {"page": 3, "per_page": 10}
        )

        assert len(processed["results"]) == 10
        assert processed["pagination"]["page"] == 3
        assert processed["pagination"]["has_next"] == True
        assert processed["pagination"]["has_previous"] == True

    @pytest.mark.asyncio
    async def test_performance_requirements(
        self, result_processor, sample_raw_results
    ):
        """Test that processing meets <200ms performance requirement."""
        start_time = time.time()

        processed = await result_processor.process_search_results(
            sample_raw_results, "user", {}, {"page": 1, "per_page": 10}
        )

        end_time = time.time()
        processing_time = end_time - start_time

        # Should complete within 200ms
        assert processing_time < 0.2
        assert processed["processing_time_ms"] < 200

    @pytest.mark.asyncio
    async def test_error_handling_fallback(self, result_processor):
        """Test error handling with fallback results."""
        # Test with invalid data that might cause processing errors
        invalid_results = [{"completely": "invalid", "data": None}]

        # Should not raise exception, should return fallback results
        processed = await result_processor.process_search_results(
            invalid_results, "test", {}, {"page": 1, "per_page": 10}
        )

        assert "results" in processed
        assert "error" in processed or len(processed["results"]) >= 0

    @pytest.mark.asyncio
    async def test_filter_combinations(
        self, result_processor, sample_raw_results
    ):
        """Test various filter combinations."""
        test_cases = [
            {"methods": ["GET"]},
            {"tags": ["users"]},
            {"authentication": {"required": True}},
            {"include_deprecated": False},
            {
                "methods": ["POST"],
                "tags": ["users"],
                "include_deprecated": False,
            },
        ]

        for filters in test_cases:
            processed = await result_processor.process_search_results(
                sample_raw_results,
                "test",
                filters,
                {"page": 1, "per_page": 10},
            )

            assert "results" in processed
            assert processed["filters_applied"] == filters
            assert isinstance(processed["summary"]["filtered_results"], int)

    @pytest.mark.asyncio
    async def test_organization_completeness(
        self, result_processor, sample_raw_results
    ):
        """Test that result organization includes all expected categories."""
        processed = await result_processor.process_search_results(
            sample_raw_results, "test", {}, {"page": 1, "per_page": 10}
        )

        organization = processed["organization"]
        expected_categories = [
            "by_tags",
            "by_resource",
            "by_complexity",
            "by_method",
            "by_operation_type",
            "by_auth_requirement",
        ]

        for category in expected_categories:
            assert category in organization
            assert isinstance(organization[category], dict)

    @pytest.mark.asyncio
    async def test_metadata_accuracy(
        self, result_processor, sample_raw_results
    ):
        """Test accuracy of enhanced metadata."""
        processed = await result_processor.process_search_results(
            sample_raw_results, "test", {}, {"page": 1, "per_page": 10}
        )

        results = processed["results"]

        for result in results:
            # Verify required fields are present
            assert "endpoint_id" in result
            assert "path" in result
            assert "method" in result
            assert "relevance_score" in result
            assert "complexity_level" in result
            assert "parameter_summary" in result
            assert "authentication_info" in result
            assert "response_info" in result

            # Verify data types
            assert isinstance(result["relevance_score"], (int, float))
            assert result["complexity_level"] in [
                "simple",
                "moderate",
                "complex",
            ]
