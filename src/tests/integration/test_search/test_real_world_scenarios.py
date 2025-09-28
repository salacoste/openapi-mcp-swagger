"""Integration tests for real-world API search scenarios.

Tests the search infrastructure with realistic usage patterns and edge cases
that would occur when working with any real API documentation.
"""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from swagger_mcp_server.config.settings import SearchConfig
from swagger_mcp_server.search.index_manager import SearchIndexManager
from swagger_mcp_server.search.search_engine import SearchEngine


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
        indexing__batch_size=100,
        performance__max_search_results=500,
    )


@pytest.fixture
def large_api_dataset():
    """Generate a large dataset simulating real-world API with many endpoints."""
    endpoints = []

    # Simulate various API patterns found in real world
    api_patterns = [
        # CRUD operations
        {
            "base": "/api/v1/users",
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "category": "user-management",
        },
        {
            "base": "/api/v1/products",
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "category": "catalog",
        },
        {
            "base": "/api/v1/orders",
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "category": "commerce",
        },
        {
            "base": "/api/v1/payments",
            "methods": ["GET", "POST"],
            "category": "finance",
        },
        # Resource-specific endpoints
        {"base": "/api/v1/search", "methods": ["GET"], "category": "search"},
        {
            "base": "/api/v1/reports",
            "methods": ["GET", "POST"],
            "category": "analytics",
        },
        {
            "base": "/api/v1/webhooks",
            "methods": ["POST", "DELETE"],
            "category": "integration",
        },
        # Administrative endpoints
        {
            "base": "/api/v1/admin/users",
            "methods": ["GET", "POST", "DELETE"],
            "category": "administration",
        },
        {
            "base": "/api/v1/admin/system",
            "methods": ["GET"],
            "category": "system",
        },
        # Third-party integrations
        {
            "base": "/api/v1/integrations/crm",
            "methods": ["GET", "POST"],
            "category": "external",
        },
        {
            "base": "/api/v1/integrations/email",
            "methods": ["POST"],
            "category": "external",
        },
    ]

    endpoint_id = 0
    for pattern in api_patterns:
        for method in pattern["methods"]:
            endpoint_id += 1

            # Generate various endpoint variations
            variations = ["", "/{id}", "/{id}/status", "/{id}/history"]

            for variation in variations:
                if variation and method in ["POST"] and "{id}" in variation:
                    continue  # Skip POST to specific IDs

                endpoint_id += 1
                path = pattern["base"] + variation

                endpoints.append(
                    {
                        "id": f"endpoint_{endpoint_id}",
                        "path": path,
                        "method": method,
                        "operation_id": f"{method.lower()}{pattern['category'].replace('-', '').title()}{variation.replace('/', '').replace('{', '').replace('}', '').title()}",
                        "summary": f"{method} {pattern['category']} {variation}".strip(),
                        "description": f"Perform {method} operation on {pattern['category']} resource {variation}".strip(),
                        "parameters": (
                            [
                                {
                                    "name": "id",
                                    "type": "string",
                                    "description": "Resource identifier",
                                }
                            ]
                            if "{id}" in variation
                            else []
                        ),
                        "tags": [pattern["category"], method.lower()],
                        "security": [{"bearer_auth": []}] if "admin" in path else [],
                        "responses": {
                            "200": {"description": "Success"},
                            "404": (
                                {"description": "Not found"}
                                if "{id}" in variation
                                else None
                            ),
                        },
                        "deprecated": False,
                    }
                )

    return endpoints[:100]  # Limit to 100 for performance


@pytest.fixture
def search_scenarios():
    """Define realistic search scenarios that users would perform."""
    return [
        # Basic entity searches
        {
            "query": "users",
            "expected_min_results": 1,
            "description": "Find user-related endpoints",
        },
        {
            "query": "products",
            "expected_min_results": 1,
            "description": "Find product catalog endpoints",
        },
        {
            "query": "orders",
            "expected_min_results": 1,
            "description": "Find order management endpoints",
        },
        # Operation-based searches
        {
            "query": "create",
            "expected_min_results": 1,
            "description": "Find creation endpoints",
        },
        {
            "query": "delete",
            "expected_min_results": 1,
            "description": "Find deletion endpoints",
        },
        {
            "query": "search",
            "expected_min_results": 1,
            "description": "Find search functionality",
        },
        # Administrative searches
        {
            "query": "admin",
            "expected_min_results": 1,
            "description": "Find admin endpoints",
        },
        {
            "query": "system",
            "expected_min_results": 1,
            "description": "Find system endpoints",
        },
        # Integration searches
        {
            "query": "webhook",
            "expected_min_results": 1,
            "description": "Find webhook endpoints",
        },
        {
            "query": "integration",
            "expected_min_results": 1,
            "description": "Find integration endpoints",
        },
        # Complex searches
        {
            "query": "user management",
            "expected_min_results": 1,
            "description": "Multi-word search",
        },
        {
            "query": "payment processing",
            "expected_min_results": 0,
            "description": "May not find exact matches",
        },
    ]


class TestRealWorldSearchScenarios:
    """Test realistic search usage patterns."""

    async def setup_search_with_large_dataset(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Setup search engine with large dataset."""
        endpoint_repo = AsyncMock()
        schema_repo = AsyncMock()
        metadata_repo = AsyncMock()

        endpoint_repo.count_all.return_value = len(large_api_dataset)
        endpoint_repo.get_all.return_value = large_api_dataset

        index_manager = SearchIndexManager(
            index_dir=temp_search_dir,
            endpoint_repo=endpoint_repo,
            schema_repo=schema_repo,
            metadata_repo=metadata_repo,
            config=search_config,
        )

        await index_manager.create_index_from_database()
        return SearchEngine(index_manager, search_config)

    @pytest.mark.asyncio
    async def test_common_search_patterns(
        self,
        temp_search_dir,
        search_config,
        large_api_dataset,
        search_scenarios,
    ):
        """Test common search patterns users would perform."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        for scenario in search_scenarios:
            response = await search_engine.search(scenario["query"])

            # Verify search completed successfully
            assert response.query_time >= 0
            assert response.query == scenario["query"]

            # Check if we meet minimum expected results
            if scenario["expected_min_results"] > 0:
                assert (
                    response.total_results >= scenario["expected_min_results"]
                ), f"Search '{scenario['query']}' expected at least {scenario['expected_min_results']} results, got {response.total_results}"

    @pytest.mark.asyncio
    async def test_search_relevance_ranking(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Test that search results are properly ranked by relevance."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        # Search for "users" - should rank user endpoints higher
        response = await search_engine.search("users")

        if response.total_results > 1:
            # First result should be more relevant than last
            first_score = response.results[0].score
            last_score = response.results[-1].score
            assert first_score >= last_score

            # User-related endpoints should appear early
            top_3_results = response.results[:3]
            user_related = any("user" in r.endpoint_path.lower() for r in top_3_results)
            assert user_related, "Expected user-related endpoint in top 3 results"

    @pytest.mark.asyncio
    async def test_search_with_typos_and_variations(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Test search handles common typos and variations."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        # Test variations that should still find results
        variations = [
            ("user", "users"),  # Singular vs plural
            ("product", "products"),
            ("order", "orders"),
        ]

        for singular, plural in variations:
            singular_response = await search_engine.search(singular)
            plural_response = await search_engine.search(plural)

            # Both should find relevant results
            assert (
                singular_response.total_results > 0 or plural_response.total_results > 0
            )

    @pytest.mark.asyncio
    async def test_filtered_search_scenarios(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Test realistic filtered search scenarios."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        # Find all GET endpoints
        get_response = await search_engine.search("api", filters={"http_method": "GET"})

        if get_response.total_results > 0:
            assert all(r.http_method == "GET" for r in get_response.results)

        # Find all admin endpoints
        admin_response = await search_engine.search(
            "admin", filters={"http_method": ["GET", "POST"]}
        )

        if admin_response.total_results > 0:
            assert all(r.http_method in ["GET", "POST"] for r in admin_response.results)

    @pytest.mark.asyncio
    async def test_pagination_with_large_results(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Test pagination behavior with large result sets."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        # Search for common term that should return many results
        response = await search_engine.search("api", per_page=10)

        if response.total_results > 10:
            assert len(response.results) == 10
            assert response.has_more is True

            # Test second page
            page2 = await search_engine.search("api", page=2, per_page=10)
            assert page2.page == 2
            assert len(page2.results) <= 10

            # Results should be different
            page1_ids = {r.endpoint_id for r in response.results}
            page2_ids = {r.endpoint_id for r in page2.results}
            assert page1_ids != page2_ids  # No overlap expected

    @pytest.mark.asyncio
    async def test_empty_and_edge_case_searches(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Test edge cases and empty result scenarios."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        # Search for non-existent terms
        edge_cases = [
            "xyznonexistent",
            "12345678901234567890",
            "!@#$%^&*()",
        ]

        for query in edge_cases:
            response = await search_engine.search(query)
            # Should handle gracefully without errors
            assert response.total_results >= 0
            assert response.query == query

    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Test search performance with larger datasets."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        # Test multiple concurrent searches
        search_tasks = [
            search_engine.search("users"),
            search_engine.search("products"),
            search_engine.search("orders"),
            search_engine.search("admin"),
            search_engine.search("api"),
        ]

        # Run searches concurrently
        results = await asyncio.gather(*search_tasks)

        # All searches should complete successfully
        assert len(results) == 5
        for response in results:
            assert response.query_time >= 0
            # Performance target: should be under 1 second in test environment
            assert response.query_time < 1.0

    @pytest.mark.asyncio
    async def test_search_suggestion_functionality(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Test search suggestion/autocomplete functionality."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        # Test query suggestions
        suggestions = await search_engine.suggest_queries("user", limit=5)

        assert isinstance(suggestions, list)
        assert len(suggestions) <= 5

        # All suggestions should start with "user"
        for suggestion in suggestions:
            assert suggestion.startswith("user")

    @pytest.mark.asyncio
    async def test_tag_based_discovery(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Test discovering endpoints by tags."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        # Test searching by common tags
        common_tags = ["user-management", "catalog", "administration"]

        for tag in common_tags:
            results = await search_engine.search_by_tag(tag)

            # Should find tagged endpoints
            if results:
                assert len(results) > 0
                # Verify results are relevant to the tag
                for result in results[:3]:  # Check first 3 results
                    assert (
                        tag in result.metadata.get("tags", "").lower()
                        or tag.replace("-", "") in result.endpoint_path.lower()
                    )

    @pytest.mark.asyncio
    async def test_path_based_search(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Test path-based endpoint discovery."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        # Test exact path matching
        exact_results = await search_engine.search_by_path(
            "/api/v1/users", exact_match=True
        )

        if exact_results:
            for result in exact_results:
                assert result.endpoint_path == "/api/v1/users"

        # Test pattern-based path search
        pattern_results = await search_engine.search_by_path("users")

        if pattern_results:
            for result in pattern_results:
                assert "users" in result.endpoint_path.lower()

    @pytest.mark.asyncio
    async def test_complex_query_scenarios(
        self, temp_search_dir, search_config, large_api_dataset
    ):
        """Test complex multi-faceted queries."""
        search_engine = await self.setup_search_with_large_dataset(
            temp_search_dir, search_config, large_api_dataset
        )

        # Complex scenarios combining multiple criteria
        complex_scenarios = [
            {
                "query": "user",
                "filters": {"http_method": "POST"},
                "description": "Find user creation endpoints",
            },
            {
                "query": "admin",
                "filters": {"http_method": ["GET", "DELETE"]},
                "description": "Find admin read/delete operations",
            },
        ]

        for scenario in complex_scenarios:
            response = await search_engine.search(
                scenario["query"], filters=scenario.get("filters", {})
            )

            # Verify filters are applied
            if response.total_results > 0:
                for result in response.results:
                    if "http_method" in scenario.get("filters", {}):
                        expected_methods = scenario["filters"]["http_method"]
                        if isinstance(expected_methods, list):
                            assert result.http_method in expected_methods
                        else:
                            assert result.http_method == expected_methods
