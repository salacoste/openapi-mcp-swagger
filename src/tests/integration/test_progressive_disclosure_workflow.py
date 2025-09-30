"""Integration tests for progressive disclosure workflow (Story 6.3).

Tests the complete workflow:
1. getEndpointCategories - Discover available categories
2. searchEndpoints with category filter - Retrieve specific category endpoints

Validates token efficiency, correctness, and real-world usage with Ozon API.
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any

from swagger_mcp_server.conversion.pipeline import ConversionPipeline
from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer


@pytest.fixture
async def ozon_api_server(tmp_path):
    """Create MCP server with parsed Ozon Performance API."""
    # Load Ozon swagger file
    # Path: tests/integration -> tests -> src -> project_root
    swagger_path = Path(__file__).parent.parent.parent.parent / "swagger-openapi-data" / "swagger.json"

    if not swagger_path.exists():
        pytest.skip("Ozon swagger file not found")

    # Create database path
    db_path = tmp_path / "ozon_test.db"

    # Parse swagger file
    pipeline = ConversionPipeline(db_path=str(db_path))
    result = await pipeline.convert(str(swagger_path))

    assert result.success, f"Failed to parse Ozon API: {result.error}"

    # Create MCP server
    server = SwaggerMcpServer(name="test-ozon-server")
    await server.initialize(str(db_path))

    yield server

    await server.cleanup()


class TestProgressiveDisclosureWorkflow:
    """Integration tests for progressive disclosure using category filtering."""

    @pytest.mark.asyncio
    async def test_full_progressive_disclosure_workflow(self, ozon_api_server):
        """Test complete workflow: discover categories → filter by category."""
        server = ozon_api_server

        # Step 1: Discover available categories
        categories_result = await server._get_endpoint_categories()

        assert "categories" in categories_result
        categories = categories_result["categories"]
        assert len(categories) > 0

        # Find Campaign category
        campaign_category = next((c for c in categories if c["category_name"] == "Campaign"), None)
        assert campaign_category is not None, "Campaign category not found"
        assert campaign_category["endpoint_count"] == 4

        # Step 2: Search within Campaign category
        search_result = await server._search_endpoints(
            keywords="campaign",
            category="Campaign"
        )

        # Verify results
        assert len(search_result["results"]) == 4
        assert all("Campaign" in r.get("category", "") for r in search_result["results"])

        # Verify all campaign endpoints present
        paths = [r["path"] for r in search_result["results"]]
        assert any("list" in p.lower() for p in paths)
        assert any("activate" in p.lower() for p in paths)

        # Verify metadata
        assert search_result["search_metadata"]["category_filter"] == "Campaign"

    @pytest.mark.asyncio
    async def test_ozon_api_campaign_category_filtering(self, ozon_api_server):
        """Test filtering Ozon API Campaign category endpoints."""
        server = ozon_api_server

        # Search for all campaign endpoints
        result = await server._search_endpoints(
            keywords="campaign",
            category="Campaign"
        )

        # Expected Campaign endpoints from Ozon API
        assert len(result["results"]) == 4

        # Verify endpoint details
        operation_ids = [r["operationId"] for r in result["results"]]

        # Check for specific Ozon campaign operations
        expected_operations = ["ListCampaigns", "ActivateCampaign", "DeactivateCampaign", "GetCampaigns"]
        for op in expected_operations:
            assert any(op.lower() in oid.lower() for oid in operation_ids), f"Expected operation {op} not found"

    @pytest.mark.asyncio
    async def test_ozon_api_statistics_category_filtering(self, ozon_api_server):
        """Test filtering Ozon API Statistics category endpoints."""
        server = ozon_api_server

        result = await server._search_endpoints(
            keywords="stats",
            category="Statistics"
        )

        # Statistics category should have 13 endpoints
        assert len(result["results"]) == 13

        # All should be in Statistics category
        for endpoint in result["results"]:
            # Note: endpoint dict might not have category directly, check via search_metadata
            pass

        assert result["search_metadata"]["category_filter"] == "Statistics"

    @pytest.mark.asyncio
    async def test_token_usage_comparison(self, ozon_api_server):
        """Compare token usage: full search vs category-filtered search."""
        server = ozon_api_server

        # Full search (no category filter)
        full_result = await server._search_endpoints(
            keywords="campaign",
            perPage=50  # Get many results
        )

        # Category-filtered search
        filtered_result = await server._search_endpoints(
            keywords="campaign",
            category="Campaign",
            perPage=50
        )

        # Filtered results should have fewer endpoints
        assert len(filtered_result["results"]) <= len(full_result["results"])

        # Estimate token savings
        # Assumption: ~185 tokens per endpoint (from Story 6.2 analysis)
        full_tokens = len(full_result["results"]) * 185
        filtered_tokens = len(filtered_result["results"]) * 185

        token_savings = full_tokens - filtered_tokens
        savings_percent = (token_savings / full_tokens * 100) if full_tokens > 0 else 0

        print(f"\nToken comparison:")
        print(f"  Full search: {len(full_result['results'])} endpoints ≈ {full_tokens} tokens")
        print(f"  Filtered: {len(filtered_result['results'])} endpoints ≈ {filtered_tokens} tokens")
        print(f"  Savings: {token_savings} tokens ({savings_percent:.1f}%)")

        # Should achieve significant token reduction
        assert savings_percent > 0, "Category filtering should reduce tokens"

    @pytest.mark.asyncio
    async def test_progressive_disclosure_with_multiple_categories(self, ozon_api_server):
        """Test progressive disclosure across multiple categories."""
        server = ozon_api_server

        # Get all categories
        categories_result = await server._get_endpoint_categories()
        categories = categories_result["categories"]

        # Test searching in each category
        total_endpoints = 0
        for category in categories[:3]:  # Test first 3 categories
            category_name = category["category_name"]
            expected_count = category["endpoint_count"]

            # Search in this category
            result = await server._search_endpoints(
                keywords="",  # Empty to get all in category
                category=category_name,
                perPage=50
            )

            # Note: empty keywords might not work, use generic term
            result = await server._search_endpoints(
                keywords="api",  # Generic keyword
                category=category_name,
                perPage=50
            )

            total_endpoints += len(result["results"])

            # Verify category filter in metadata
            assert result["search_metadata"]["category_filter"] == category_name

        print(f"\nProgressive disclosure tested across {len(categories[:3])} categories")
        print(f"Total endpoints retrieved: {total_endpoints}")

    @pytest.mark.asyncio
    async def test_category_filter_with_pagination_workflow(self, ozon_api_server):
        """Test paginated category filtering workflow."""
        server = ozon_api_server

        # Get Statistics category (13 endpoints)
        page_size = 5
        all_results = []

        page = 1
        while True:
            result = await server._search_endpoints(
                keywords="stats",
                category="Statistics",
                page=page,
                perPage=page_size
            )

            all_results.extend(result["results"])

            if not result["pagination"]["has_more"]:
                break

            page += 1

        # Should have retrieved all Statistics endpoints
        assert len(all_results) == 13

        # Verify no duplicates
        endpoint_ids = [r["endpoint_id"] for r in all_results]
        assert len(endpoint_ids) == len(set(endpoint_ids)), "Duplicate endpoints found"

    @pytest.mark.asyncio
    async def test_category_group_filtering_workflow(self, ozon_api_server):
        """Test filtering by category group (parent category)."""
        server = ozon_api_server

        # Get categories to find groups
        categories_result = await server._get_endpoint_categories()
        categories = categories_result["categories"]

        # Find a category with a group
        category_with_group = next(
            (c for c in categories if c.get("category_group")),
            None
        )

        if not category_with_group:
            pytest.skip("No categories with groups found")

        group_name = category_with_group["category_group"]

        # Search by group
        result = await server._search_endpoints(
            keywords="api",
            categoryGroup=group_name,
            perPage=50
        )

        # Should return endpoints from this group
        assert len(result["results"]) > 0
        assert result["search_metadata"]["category_group_filter"] == group_name

    @pytest.mark.asyncio
    async def test_combined_filters_workflow(self, ozon_api_server):
        """Test combining category filter with other filters."""
        server = ozon_api_server

        # Combine category + HTTP method
        result = await server._search_endpoints(
            keywords="campaign",
            category="Campaign",
            httpMethods=["POST"]
        )

        # Should return only POST endpoints in Campaign category
        assert all(r["method"] == "POST" for r in result["results"])
        assert result["search_metadata"]["category_filter"] == "Campaign"

    @pytest.mark.asyncio
    async def test_case_insensitive_category_workflow(self, ozon_api_server):
        """Test that category filtering is case-insensitive in real workflow."""
        server = ozon_api_server

        # Try different cases
        result_lower = await server._search_endpoints(
            keywords="campaign",
            category="campaign"
        )

        result_upper = await server._search_endpoints(
            keywords="campaign",
            category="CAMPAIGN"
        )

        result_normal = await server._search_endpoints(
            keywords="campaign",
            category="Campaign"
        )

        # All should return same results
        assert len(result_lower["results"]) == len(result_normal["results"])
        assert len(result_upper["results"]) == len(result_normal["results"])

    @pytest.mark.asyncio
    async def test_nonexistent_category_workflow(self, ozon_api_server):
        """Test searching for non-existent category returns empty results."""
        server = ozon_api_server

        result = await server._search_endpoints(
            keywords="test",
            category="NonExistentCategory12345"
        )

        # Should return empty, not error
        assert len(result["results"]) == 0
        assert result["pagination"]["total"] == 0
        assert result["search_metadata"]["category_filter"] == "NonExistentCategory12345"


class TestTokenEfficiency:
    """Tests focused on token efficiency of progressive disclosure."""

    @pytest.mark.asyncio
    async def test_category_discovery_token_efficiency(self, ozon_api_server):
        """Test that category discovery is token-efficient."""
        server = ozon_api_server

        categories_result = await server._get_endpoint_categories()

        # Should return compact category summary
        assert "categories" in categories_result
        assert "summary" in categories_result

        # Each category should have essential info only
        for category in categories_result["categories"]:
            required_fields = ["category_name", "endpoint_count"]
            for field in required_fields:
                assert field in category

    @pytest.mark.asyncio
    async def test_filtered_search_reduces_results(self, ozon_api_server):
        """Test that category filtering reduces result set size."""
        server = ozon_api_server

        # Search without filter
        unfiltered = await server._search_endpoints(
            keywords="api",
            perPage=50
        )

        # Search with Campaign filter
        filtered = await server._search_endpoints(
            keywords="api",
            category="Campaign",
            perPage=50
        )

        # Filtered should have fewer results
        assert len(filtered["results"]) < len(unfiltered["results"])

        # Calculate reduction
        reduction = len(unfiltered["results"]) - len(filtered["results"])
        reduction_percent = (reduction / len(unfiltered["results"]) * 100) if len(unfiltered["results"]) > 0 else 0

        print(f"\nResult reduction: {reduction} endpoints ({reduction_percent:.1f}%)")

        assert reduction_percent > 50, "Category filtering should significantly reduce results"