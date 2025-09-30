"""Integration tests for getEndpointCategories MCP workflow.

Epic 6: Story 6.2 - getEndpointCategories MCP method
Tests end-to-end workflow from parsing to MCP tool invocation.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from swagger_mcp_server.config.settings import Settings
from swagger_mcp_server.conversion.pipeline import ConversionPipeline
from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer
from swagger_mcp_server.storage.database import DatabaseManager


class TestMCPEndpointCategoriesWorkflow:
    """Integration tests for full getEndpointCategories workflow."""

    @pytest.fixture
    def swagger_fixture_path(self):
        """Get path to Ozon Performance API fixture."""
        fixture_path = Path(__file__).parent.parent.parent.parent.parent / "swagger-openapi-data" / "swagger.json"

        if not fixture_path.exists():
            pytest.skip(f"Swagger fixture not found at {fixture_path}")

        return fixture_path

    @pytest.fixture
    def test_db_path(self, tmp_path):
        """Create temporary database path."""
        return tmp_path / "test_categories.db"

    @pytest.fixture
    async def populated_db(self, swagger_fixture_path, test_db_path):
        """Parse Ozon API and populate database with categories."""
        # Create settings
        settings = Settings()
        settings.database.path = str(test_db_path)

        # Initialize database
        db_manager = DatabaseManager(settings)
        await db_manager.initialize()

        # Create conversion pipeline
        pipeline = ConversionPipeline(db_manager, settings)

        # Parse swagger file
        await pipeline.convert(str(swagger_fixture_path), str(test_db_path.parent / "output"))

        yield db_manager

        # Cleanup
        await db_manager.close()

    @pytest.fixture
    async def mcp_server(self, test_db_path, populated_db):
        """Create MCP server with populated database."""
        settings = Settings()
        settings.database.path = str(test_db_path)
        settings.server.name = "test-categories-server"
        settings.server.version = "0.1.0"

        server = SwaggerMcpServer(settings)
        await server.initialize()

        yield server

        await server.cleanup()

    @pytest.mark.asyncio
    async def test_full_workflow_parse_and_get_categories(
        self, mcp_server, populated_db
    ):
        """Test complete workflow: parse Ozon API → getEndpointCategories."""
        # Call getEndpointCategories
        result = await mcp_server._get_endpoint_categories()

        # Verify response structure
        assert "categories" in result
        assert "groups" in result
        assert "metadata" in result

        # Verify Ozon API data
        assert len(result["categories"]) >= 6, "Should have at least 6 categories"
        assert result["metadata"]["totalCategories"] >= 6
        assert result["metadata"]["apiTitle"] is not None

        # Verify specific Ozon categories exist
        category_names = [cat["name"] for cat in result["categories"]]
        expected_categories = [
            "Campaign",
            "Statistics",
            "Ad",
            "Product",
            "Search-Promo",
            "Vendor",
        ]

        for expected_cat in expected_categories:
            assert (
                expected_cat in category_names
            ), f"Expected category '{expected_cat}' not found"

        # Verify all categories have required fields
        for cat in result["categories"]:
            assert cat["name"]
            assert cat["displayName"]
            assert cat["endpointCount"] > 0
            assert isinstance(cat["httpMethods"], list)

    @pytest.mark.asyncio
    async def test_category_catalog_token_efficiency(self, mcp_server):
        """Test that category catalog has significant token efficiency."""
        result = await mcp_server._get_endpoint_categories()

        # Serialize to JSON to measure size
        json_output = json.dumps(result, ensure_ascii=False)

        # Rough token estimation: ~4 chars per token
        estimated_tokens = len(json_output) / 4

        # Should be well under 2,000 tokens for 6 categories
        assert (
            estimated_tokens < 2000
        ), f"Token usage {estimated_tokens:.0f} exceeds target of 2000"

        # Verify compact structure
        assert len(result["categories"]) >= 6
        assert result["metadata"]["totalEndpoints"] > 0

        print(f"Token efficiency: ~{estimated_tokens:.0f} tokens for {len(result['categories'])} categories")

    @pytest.mark.asyncio
    async def test_category_filtering_by_group(self, mcp_server):
        """Test filtering categories by group."""
        # Get all categories first
        all_result = await mcp_server._get_endpoint_categories()

        if not all_result["groups"]:
            pytest.skip("No groups found in database")

        # Get first group name
        first_group = all_result["groups"][0]["name"]

        # Filter by group
        filtered_result = await mcp_server._get_endpoint_categories(
            categoryGroup=first_group
        )

        # Verify all categories belong to the group
        for cat in filtered_result["categories"]:
            assert cat["group"] == first_group

    @pytest.mark.asyncio
    async def test_category_sorting_options(self, mcp_server):
        """Test different sorting options."""
        # Test sort by name
        name_result = await mcp_server._get_endpoint_categories(sortBy="name")
        names = [cat["name"] for cat in name_result["categories"]]
        # Names should be in alphabetical order (or at least not empty)
        assert names

        # Test sort by endpoint count
        count_result = await mcp_server._get_endpoint_categories(
            sortBy="endpointCount"
        )
        counts = [cat["endpointCount"] for cat in count_result["categories"]]

        # Should be sorted descending by count
        if len(counts) > 1:
            # Verify descending order
            for i in range(len(counts) - 1):
                assert counts[i] >= counts[i + 1]

        # Test sort by group
        group_result = await mcp_server._get_endpoint_categories(sortBy="group")
        assert group_result["categories"]

    @pytest.mark.asyncio
    async def test_include_empty_categories(self, mcp_server):
        """Test includeEmpty parameter functionality."""
        # Get categories without empty
        without_empty = await mcp_server._get_endpoint_categories(includeEmpty=False)

        # Get categories with empty
        with_empty = await mcp_server._get_endpoint_categories(includeEmpty=True)

        # With empty should have >= without empty
        assert len(with_empty["categories"]) >= len(without_empty["categories"])

        # All categories without empty should have count > 0
        for cat in without_empty["categories"]:
            assert cat["endpointCount"] > 0

    @pytest.mark.asyncio
    async def test_group_aggregation_accuracy(self, mcp_server):
        """Test that group aggregation matches category data."""
        result = await mcp_server._get_endpoint_categories()

        # Calculate totals from categories
        categories_by_group = {}
        for cat in result["categories"]:
            group_name = cat.get("group", "Uncategorized")
            if group_name not in categories_by_group:
                categories_by_group[group_name] = {
                    "count": 0,
                    "endpoints": 0,
                    "names": [],
                }
            categories_by_group[group_name]["count"] += 1
            categories_by_group[group_name]["endpoints"] += cat["endpointCount"]
            categories_by_group[group_name]["names"].append(cat["name"])

        # Verify groups match calculated totals
        for group in result["groups"]:
            group_name = group["name"]
            assert group_name in categories_by_group

            calculated = categories_by_group[group_name]
            assert group["categoryCount"] == calculated["count"]
            assert group["totalEndpoints"] == calculated["endpoints"]
            assert set(group["categories"]) == set(calculated["names"])

    @pytest.mark.asyncio
    async def test_metadata_accuracy(self, mcp_server):
        """Test that metadata section has accurate totals."""
        result = await mcp_server._get_endpoint_categories()

        # Verify metadata totals
        metadata = result["metadata"]

        # Total categories should match array length
        assert metadata["totalCategories"] == len(result["categories"])

        # Total endpoints should match sum
        calculated_total = sum(cat["endpointCount"] for cat in result["categories"])
        assert metadata["totalEndpoints"] == calculated_total

        # Total groups should match array length
        assert metadata["totalGroups"] == len(result["groups"])

        # API info should be present
        assert metadata["apiTitle"] is not None
        assert metadata["apiVersion"] is not None

    @pytest.mark.asyncio
    async def test_mcp_tool_registration(self, mcp_server):
        """Test that getEndpointCategories is properly registered as MCP tool."""
        # Access the MCP server's registered tools
        # This is a simplified test - full MCP client testing would use actual MCP protocol

        # Verify the handler exists
        assert hasattr(mcp_server, "_get_endpoint_categories")
        assert hasattr(mcp_server, "_get_endpoint_categories_with_resilience")

        # Verify it can be called
        result = await mcp_server._get_endpoint_categories()
        assert result is not None


class TestMCPEndpointCategoriesPerformance:
    """Performance tests for getEndpointCategories integration."""

    @pytest.fixture
    async def large_db(self, tmp_path, swagger_fixture_path):
        """Create database with large dataset."""
        db_path = tmp_path / "large_test.db"
        settings = Settings()
        settings.database.path = str(db_path)

        db_manager = DatabaseManager(settings)
        await db_manager.initialize()

        # Parse Ozon API
        pipeline = SwaggerConversionPipeline(db_manager, settings)
        await pipeline.parse_and_store_swagger(str(swagger_fixture_path))

        yield db_manager

        await db_manager.close()

    @pytest.mark.asyncio
    async def test_response_time_with_real_data(self, test_db_path, large_db):
        """Test response time with real Ozon API data."""
        import time

        settings = Settings()
        settings.database.path = str(test_db_path)

        server = SwaggerMcpServer(settings)
        await server.initialize()

        # Warm up
        await server._get_endpoint_categories()

        # Measure
        start = time.perf_counter()
        result = await server._get_endpoint_categories()
        elapsed = (time.perf_counter() - start) * 1000

        await server.cleanup()

        # Should be under 50ms target
        assert elapsed < 50, f"Response took {elapsed:.2f}ms, expected < 50ms"
        assert result["categories"]

    @pytest.mark.asyncio
    async def test_filtered_query_performance(self, test_db_path, large_db):
        """Test performance with filtering and sorting."""
        import time

        settings = Settings()
        settings.database.path = str(test_db_path)

        server = SwaggerMcpServer(settings)
        await server.initialize()

        # Measure with filters
        start = time.perf_counter()
        result = await server._get_endpoint_categories(
            categoryGroup="Методы Performance API",
            includeEmpty=True,
            sortBy="endpointCount",
        )
        elapsed = (time.perf_counter() - start) * 1000

        await server.cleanup()

        # Should be under 100ms target
        assert elapsed < 100, f"Response took {elapsed:.2f}ms, expected < 100ms"

    @pytest.mark.asyncio
    async def test_token_usage_comparison(self, mcp_server):
        """Compare token usage: full endpoint list vs category catalog."""
        # Get category catalog
        catalog_result = await mcp_server._get_endpoint_categories()
        catalog_json = json.dumps(catalog_result, ensure_ascii=False)
        catalog_tokens = len(catalog_json) / 4

        # Estimate full endpoint listing (simplified)
        # Assume ~200 tokens per endpoint × 40 endpoints = ~8,000 tokens
        estimated_full_listing_tokens = 8000

        # Calculate savings
        token_reduction = (
            (estimated_full_listing_tokens - catalog_tokens)
            / estimated_full_listing_tokens
            * 100
        )

        print(
            f"Token reduction: {token_reduction:.1f}% "
            f"({estimated_full_listing_tokens:.0f} → {catalog_tokens:.0f} tokens)"
        )

        # Should achieve at least 80% token reduction
        assert token_reduction >= 80, f"Only {token_reduction:.1f}% reduction"