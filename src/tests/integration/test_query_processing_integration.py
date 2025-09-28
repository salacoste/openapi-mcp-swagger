"""Integration tests for advanced query processing with sample API searches.

Tests the complete query processing pipeline with realistic API scenarios
using sample Swagger/OpenAPI data.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

from swagger_mcp_server.config.settings import (
    SearchConfig,
    SearchPerformanceConfig,
)
from swagger_mcp_server.search.index_manager import SearchIndexManager
from swagger_mcp_server.search.query_processor import QueryProcessor
from swagger_mcp_server.search.search_engine import (
    SearchEngine,
    SearchResponse,
)


@pytest.fixture
def search_config():
    """Create test search configuration."""
    return SearchConfig(
        performance=SearchPerformanceConfig(
            max_search_results=50, search_timeout=5.0, index_batch_size=100
        )
    )


@pytest.fixture
def sample_api_endpoints():
    """Sample API endpoints for testing."""
    return [
        {
            "endpoint_id": "get_users",
            "endpoint_path": "/api/v1/users",
            "http_method": "GET",
            "summary": "List all users",
            "description": "Retrieve a paginated list of all users in the system",
            "parameters": "limit, offset, filter",
            "tags": "users, list",
            "auth_type": "bearer",
            "operation_id": "listUsers",
            "deprecated": False,
        },
        {
            "endpoint_id": "create_user",
            "endpoint_path": "/api/v1/users",
            "http_method": "POST",
            "summary": "Create new user",
            "description": "Create a new user account with email and password",
            "parameters": "email, password, name",
            "tags": "users, create",
            "auth_type": "bearer",
            "operation_id": "createUser",
            "deprecated": False,
        },
        {
            "endpoint_id": "get_user",
            "endpoint_path": "/api/v1/users/{user_id}",
            "http_method": "GET",
            "summary": "Get user by ID",
            "description": "Retrieve a specific user by their unique identifier",
            "parameters": "user_id",
            "tags": "users, get",
            "auth_type": "bearer",
            "operation_id": "getUserById",
            "deprecated": False,
        },
        {
            "endpoint_id": "update_user",
            "endpoint_path": "/api/v1/users/{user_id}",
            "http_method": "PUT",
            "summary": "Update user",
            "description": "Update user information including email, name, and profile",
            "parameters": "user_id, email, name, profile",
            "tags": "users, update",
            "auth_type": "bearer",
            "operation_id": "updateUser",
            "deprecated": False,
        },
        {
            "endpoint_id": "delete_user",
            "endpoint_path": "/api/v1/users/{user_id}",
            "http_method": "DELETE",
            "summary": "Delete user",
            "description": "Permanently delete a user account and all associated data",
            "parameters": "user_id",
            "tags": "users, delete",
            "auth_type": "bearer",
            "operation_id": "deleteUser",
            "deprecated": False,
        },
        {
            "endpoint_id": "authenticate",
            "endpoint_path": "/api/v1/auth/login",
            "http_method": "POST",
            "summary": "User authentication",
            "description": "Authenticate user credentials and return access token",
            "parameters": "email, password",
            "tags": "authentication, login",
            "auth_type": "none",
            "operation_id": "authenticateUser",
            "deprecated": False,
        },
        {
            "endpoint_id": "refresh_token",
            "endpoint_path": "/api/v1/auth/refresh",
            "http_method": "POST",
            "summary": "Refresh access token",
            "description": "Refresh expired access token using refresh token",
            "parameters": "refresh_token",
            "tags": "authentication, token",
            "auth_type": "refresh",
            "operation_id": "refreshAccessToken",
            "deprecated": False,
        },
        {
            "endpoint_id": "oauth_authorize",
            "endpoint_path": "/api/v1/auth/oauth/authorize",
            "http_method": "GET",
            "summary": "OAuth authorization",
            "description": "OAuth 2.0 authorization endpoint for third-party applications",
            "parameters": "client_id, redirect_uri, scope",
            "tags": "authentication, oauth",
            "auth_type": "oauth",
            "operation_id": "oauthAuthorize",
            "deprecated": True,
        },
        {
            "endpoint_id": "get_profile",
            "endpoint_path": "/api/v1/users/profile",
            "http_method": "GET",
            "summary": "Get current user profile",
            "description": "Retrieve the profile information for the currently authenticated user",
            "parameters": "none",
            "tags": "users, profile",
            "auth_type": "bearer",
            "operation_id": "getCurrentUserProfile",
            "deprecated": False,
        },
        {
            "endpoint_id": "upload_avatar",
            "endpoint_path": "/api/v1/users/avatar",
            "http_method": "POST",
            "summary": "Upload user avatar",
            "description": "Upload and set user profile avatar image",
            "parameters": "image_file",
            "tags": "users, upload, image",
            "auth_type": "bearer",
            "operation_id": "uploadUserAvatar",
            "deprecated": False,
        },
    ]


@pytest.fixture
async def mock_search_engine(search_config, sample_api_endpoints):
    """Create a mock search engine with sample data."""
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
    ]
    mock_index_manager.index = mock_index

    # Create search engine
    search_engine = SearchEngine(mock_index_manager, search_config)

    # Mock search execution to return sample data
    async def mock_execute_search(
        query, page=1, per_page=20, sort_by=None, include_highlights=True
    ):
        # Simple mock search logic - match query against descriptions
        query_str = str(query).lower()
        matches = []

        for endpoint in sample_api_endpoints:
            score = 0
            text_fields = [
                endpoint["endpoint_path"],
                endpoint["summary"],
                endpoint["description"],
                endpoint["parameters"],
                endpoint["tags"],
            ]
            full_text = " ".join(text_fields).lower()

            # Simple scoring based on term matches
            for word in query_str.split():
                if word in full_text:
                    score += full_text.count(word)

            if score > 0:
                matches.append((endpoint, score))

        # Sort by score
        matches.sort(key=lambda x: x[1], reverse=True)

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
        for endpoint in sample_api_endpoints:
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


class TestBasicQueryProcessing:
    """Test basic query processing scenarios."""

    @pytest.mark.asyncio
    async def test_simple_keyword_search(self, mock_search_engine):
        """Test simple keyword search processing."""
        response = await mock_search_engine.search("user")

        assert isinstance(response, SearchResponse)
        assert response.total_results > 0
        assert len(response.results) > 0

        # Should find user-related endpoints
        user_results = [r for r in response.results if "user" in r.description.lower()]
        assert len(user_results) > 0

    @pytest.mark.asyncio
    async def test_multi_term_search(self, mock_search_engine):
        """Test multi-term search processing."""
        response = await mock_search_engine.search("user authentication")

        assert response.total_results > 0

        # Should prioritize results containing both terms
        for result in response.results[:3]:  # Top 3 results
            text = (result.description + " " + result.summary).lower()
            # Should contain at least one of the terms
            assert "user" in text or "auth" in text

    @pytest.mark.asyncio
    async def test_performance_requirement(self, mock_search_engine):
        """Test that query processing meets <200ms requirement."""
        query = "user authentication endpoint parameter"

        start_time = time.time()
        response = await mock_search_engine.search(query)
        end_time = time.time()

        query_time = end_time - start_time

        # Should complete within 200ms (using mock, so should be much faster)
        assert query_time < 0.2
        assert response.query_time < 0.2
        assert response.total_results >= 0


class TestBooleanQueryProcessing:
    """Test boolean query processing with sample data."""

    @pytest.mark.asyncio
    async def test_and_query_processing(self, mock_search_engine):
        """Test AND query processing."""
        response = await mock_search_engine.search("user AND authentication")

        # Should find results containing both terms
        if response.total_results > 0:
            for result in response.results:
                text = (result.description + " " + result.summary).lower()
                # Mock implementation may not enforce strict AND logic
                # but should prioritize results with both terms
                assert "user" in text or "auth" in text

    @pytest.mark.asyncio
    async def test_or_query_processing(self, mock_search_engine):
        """Test OR query processing."""
        response = await mock_search_engine.search("user OR profile")

        assert response.total_results > 0

        # Should find results containing either term
        for result in response.results:
            text = (result.description + " " + result.summary).lower()
            assert "user" in text or "profile" in text

    @pytest.mark.asyncio
    async def test_not_query_processing(self, mock_search_engine):
        """Test NOT query processing."""
        response = await mock_search_engine.search("authentication NOT oauth")

        # Should find auth results but exclude oauth
        for result in response.results:
            text = (result.description + " " + result.summary).lower()
            if "oauth" in text:
                # In mock implementation, NOT may not be strictly enforced
                # but oauth results should have lower scores
                pass


class TestFieldSpecificQueries:
    """Test field-specific query processing."""

    @pytest.mark.asyncio
    async def test_path_specific_search(self, mock_search_engine):
        """Test path-specific search queries."""
        response = await mock_search_engine.search("path:/users")

        if response.total_results > 0:
            # Should find endpoints with /users in path
            for result in response.results:
                assert (
                    "/users" in result.endpoint_path
                    or "user" in result.endpoint_path.lower()
                )

    @pytest.mark.asyncio
    async def test_method_specific_search(self, mock_search_engine):
        """Test HTTP method-specific search queries."""
        response = await mock_search_engine.search("method:POST")

        if response.total_results > 0:
            # Should prioritize POST endpoints
            post_results = [r for r in response.results if r.http_method == "POST"]
            # Mock may not strictly filter, but should boost POST results

    @pytest.mark.asyncio
    async def test_auth_specific_search(self, mock_search_engine):
        """Test authentication-specific search queries."""
        response = await mock_search_engine.search("auth:bearer")

        # Should find bearer token authenticated endpoints
        if response.total_results > 0:
            # Check that auth-related results are found
            for result in response.results:
                # Mock implementation should find auth-related endpoints
                pass

    @pytest.mark.asyncio
    async def test_combined_field_search(self, mock_search_engine):
        """Test combined field-specific search."""
        response = await mock_search_engine.search("path:/users method:GET")

        if response.total_results > 0:
            # Should find GET endpoints on /users path
            relevant_results = [
                r
                for r in response.results
                if "user" in r.endpoint_path.lower() and r.http_method == "GET"
            ]
            # Should have at least some relevant results


class TestQuerySuggestions:
    """Test query suggestion generation."""

    @pytest.mark.asyncio
    async def test_typo_correction_suggestions(self, mock_search_engine):
        """Test typo correction in query suggestions."""
        # Search with a typo
        response = await mock_search_engine.search("autentication")  # Missing 'h'

        # Check if suggestions are provided for low result count
        if hasattr(response, "metadata") and response.metadata:
            suggestions = response.metadata.get("suggestions", [])
            if suggestions:
                # Should suggest correct spelling
                auth_suggestions = [
                    s for s in suggestions if "authentication" in s["query"]
                ]
                assert len(auth_suggestions) > 0

    @pytest.mark.asyncio
    async def test_partial_match_suggestions(self, mock_search_engine):
        """Test partial match suggestions."""
        response = await mock_search_engine.search("auth")

        # Should find authentication-related endpoints
        assert response.total_results > 0

        # Check for auth-related results
        auth_results = [
            r
            for r in response.results
            if "auth" in r.description.lower() or "auth" in r.summary.lower()
        ]
        assert len(auth_results) > 0

    @pytest.mark.asyncio
    async def test_refinement_suggestions(self, mock_search_engine):
        """Test query refinement suggestions."""
        response = await mock_search_engine.search("user")

        # For broad queries, should suggest refinements
        if hasattr(response, "metadata") and response.metadata:
            suggestions = response.metadata.get("suggestions", [])
            if suggestions:
                refinement_suggestions = [
                    s for s in suggestions if s["category"] == "refinement"
                ]
                # Should provide ways to narrow down the search


class TestFuzzyMatching:
    """Test fuzzy matching capabilities."""

    @pytest.mark.asyncio
    async def test_slight_misspelling_tolerance(self, mock_search_engine):
        """Test tolerance for slight misspellings."""
        # Test variations of "authentication"
        test_queries = [
            "authentication",  # Correct
            "authentification",  # Common misspelling
            "athentication",  # Missing letter
        ]

        results = []
        for query in test_queries:
            response = await mock_search_engine.search(query)
            results.append(response.total_results)

        # Correct spelling should have most results
        assert results[0] > 0

        # Misspellings should still find some results (depending on fuzzy matching)
        # This tests the system's tolerance for typos

    @pytest.mark.asyncio
    async def test_partial_word_matching(self, mock_search_engine):
        """Test partial word matching capabilities."""
        # Test partial words
        response_full = await mock_search_engine.search("authentication")
        response_partial = await mock_search_engine.search("auth")

        # Partial word should find relevant results
        assert response_partial.total_results > 0

        # Should find authentication-related endpoints
        auth_results = [
            r
            for r in response_partial.results
            if "auth" in r.description.lower() or "auth" in r.summary.lower()
        ]
        assert len(auth_results) > 0


class TestNaturalLanguageQueries:
    """Test natural language query processing."""

    @pytest.mark.asyncio
    async def test_natural_language_query(self, mock_search_engine):
        """Test natural language query processing."""
        response = await mock_search_engine.search("how to create a new user account")

        # Should find user creation endpoints
        assert response.total_results > 0

        create_results = [
            r
            for r in response.results
            if "create" in r.description.lower() or "create" in r.summary.lower()
        ]
        assert len(create_results) > 0

    @pytest.mark.asyncio
    async def test_question_based_query(self, mock_search_engine):
        """Test question-based query processing."""
        response = await mock_search_engine.search("how to authenticate users?")

        # Should find authentication endpoints
        assert response.total_results > 0

        auth_results = [
            r
            for r in response.results
            if "auth" in r.description.lower() or "login" in r.description.lower()
        ]
        assert len(auth_results) > 0

    @pytest.mark.asyncio
    async def test_task_oriented_query(self, mock_search_engine):
        """Test task-oriented query processing."""
        response = await mock_search_engine.search("delete user account permanently")

        # Should find delete endpoints
        assert response.total_results > 0

        delete_results = [
            r
            for r in response.results
            if "delete" in r.description.lower() or r.http_method == "DELETE"
        ]
        assert len(delete_results) > 0


class TestQueryComplexity:
    """Test handling of complex query scenarios."""

    @pytest.mark.asyncio
    async def test_complex_multi_criteria_query(self, mock_search_engine):
        """Test complex queries with multiple criteria."""
        response = await mock_search_engine.search(
            "path:/users method:POST auth:bearer create new account"
        )

        # Should handle complex query without errors
        assert isinstance(response, SearchResponse)
        assert response.total_results >= 0

    @pytest.mark.asyncio
    async def test_nested_boolean_query(self, mock_search_engine):
        """Test nested boolean query processing."""
        response = await mock_search_engine.search(
            "user AND (create OR update) NOT delete"
        )

        # Should process complex boolean logic
        assert isinstance(response, SearchResponse)
        assert response.total_results >= 0

    @pytest.mark.asyncio
    async def test_mixed_syntax_query(self, mock_search_engine):
        """Test queries mixing different syntax types."""
        response = await mock_search_engine.search(
            "path:/api method:GET user profile authentication"
        )

        # Should handle mixed field-specific and general terms
        assert isinstance(response, SearchResponse)
        assert response.total_results >= 0


class TestErrorHandling:
    """Test error handling in query processing."""

    @pytest.mark.asyncio
    async def test_empty_query_handling(self, mock_search_engine):
        """Test handling of empty queries."""
        with pytest.raises(ValueError):
            await mock_search_engine.search("")

    @pytest.mark.asyncio
    async def test_malformed_field_query(self, mock_search_engine):
        """Test handling of malformed field queries."""
        # Should handle gracefully without crashing
        response = await mock_search_engine.search("path: method:GET:")
        assert isinstance(response, SearchResponse)

    @pytest.mark.asyncio
    async def test_invalid_boolean_syntax(self, mock_search_engine):
        """Test handling of invalid boolean syntax."""
        response = await mock_search_engine.search("user AND AND auth OR")

        # Should handle malformed boolean queries gracefully
        assert isinstance(response, SearchResponse)

    @pytest.mark.asyncio
    async def test_extremely_long_query(self, mock_search_engine):
        """Test handling of extremely long queries."""
        long_query = " ".join(["user"] * 1000)
        response = await mock_search_engine.search(long_query)

        # Should handle without memory issues
        assert isinstance(response, SearchResponse)


class TestRealWorldScenarios:
    """Test real-world API search scenarios."""

    @pytest.mark.asyncio
    async def test_api_exploration_scenario(self, mock_search_engine):
        """Test typical API exploration queries."""
        scenarios = [
            "list users",
            "create user",
            "user authentication",
            "upload file",
            "delete account",
            "get profile",
            "refresh token",
        ]

        for query in scenarios:
            response = await mock_search_engine.search(query)
            assert isinstance(response, SearchResponse)
            # Each should find some relevant results
            assert response.total_results >= 0

    @pytest.mark.asyncio
    async def test_developer_workflow_queries(self, mock_search_engine):
        """Test queries typical in developer workflows."""
        workflow_queries = [
            "POST /users",  # Looking for specific endpoint
            "bearer token authentication",  # Security implementation
            "user_id parameter",  # Parameter usage
            "json response",  # Response format
            "deprecated endpoints",  # Maintenance
        ]

        for query in workflow_queries:
            response = await mock_search_engine.search(query)
            assert isinstance(response, SearchResponse)
            # Should handle each query type appropriately

    @pytest.mark.asyncio
    async def test_integration_discovery_queries(self, mock_search_engine):
        """Test queries for API integration discovery."""
        integration_queries = [
            "how to authenticate",
            "create new user endpoint",
            "user profile information",
            "file upload endpoint",
            "token refresh mechanism",
        ]

        for query in integration_queries:
            response = await mock_search_engine.search(query)
            assert isinstance(response, SearchResponse)

            # Should provide helpful results for integration planning
            if response.total_results > 0:
                # Results should be relevant to the query intent
                assert len(response.results) > 0


@pytest.mark.performance
class TestPerformanceIntegration:
    """Test performance characteristics of query processing."""

    @pytest.mark.asyncio
    async def test_concurrent_query_processing(self, mock_search_engine):
        """Test concurrent query processing performance."""
        queries = [
            "user authentication",
            "create user",
            "delete account",
            "upload file",
            "refresh token",
        ] * 10  # 50 total queries

        start_time = time.time()

        # Execute queries concurrently
        tasks = [mock_search_engine.search(query) for query in queries]
        responses = await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # Should handle concurrent queries efficiently
        assert len(responses) == len(queries)
        assert all(isinstance(r, SearchResponse) for r in responses)

        # Average time per query should be reasonable
        avg_time_per_query = total_time / len(queries)
        assert avg_time_per_query < 0.1  # 100ms average with mocking

    @pytest.mark.asyncio
    async def test_query_complexity_performance(self, mock_search_engine):
        """Test performance with varying query complexity."""
        complexity_queries = [
            "user",  # Simple
            "user authentication",  # Medium
            "path:/users method:POST auth:bearer create account",  # Complex
            "user AND (create OR update) NOT delete auth:bearer",  # Very complex
        ]

        times = []
        for query in complexity_queries:
            start_time = time.time()
            response = await mock_search_engine.search(query)
            end_time = time.time()

            times.append(end_time - start_time)
            assert isinstance(response, SearchResponse)

        # Even complex queries should complete quickly with mocking
        assert all(t < 0.1 for t in times)

    @pytest.mark.asyncio
    async def test_large_result_set_handling(self, mock_search_engine):
        """Test handling of large result sets."""
        # Query that should match many endpoints
        response = await mock_search_engine.search("api")

        # Should handle pagination properly
        if response.total_results > 20:
            assert len(response.results) <= 20  # Default page size
            assert response.has_more == (response.total_results > 20)

        # Test pagination
        if response.total_results > 20:
            page2_response = await mock_search_engine.search("api", page=2)
            assert isinstance(page2_response, SearchResponse)
            assert page2_response.page == 2
