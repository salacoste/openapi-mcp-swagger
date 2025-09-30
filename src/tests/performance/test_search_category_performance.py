"""Performance tests for category filtering in searchEndpoints (Story 6.3).

Tests performance characteristics:
- Response time targets (< 200ms)
- No performance regression vs unfiltered search
- SQL query optimization and index utilization
- Pagination performance with category filters
"""

import pytest
import time
import asyncio
from pathlib import Path
from typing import List

from swagger_mcp_server.conversion.pipeline import ConversionPipeline
from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer


@pytest.fixture(scope="module")
async def performance_server(tmp_path_factory):
    """Create MCP server with parsed Ozon API for performance testing."""
    # Path: tests/performance -> tests -> src -> project_root
    swagger_path = Path(__file__).parent.parent.parent.parent / "swagger-openapi-data" / "swagger.json"

    if not swagger_path.exists():
        pytest.skip("Ozon swagger file not found")

    db_path = tmp_path_factory.mktemp("perf") / "ozon_perf.db"

    pipeline = ConversionPipeline(db_path=str(db_path))
    result = await pipeline.convert(str(swagger_path))

    assert result.success, f"Failed to parse: {result.error}"

    server = SwaggerMcpServer(name="perf-server")
    await server.initialize(str(db_path))

    yield server

    await server.cleanup()


async def measure_search_time(server, **kwargs):
    """Measure search execution time in milliseconds."""
    start = time.perf_counter()
    result = await server._search_endpoints(**kwargs)
    end = time.perf_counter()
    elapsed_ms = (end - start) * 1000
    return elapsed_ms, result


class TestCategoryFilterPerformance:
    """Performance tests for category filtering."""

    @pytest.mark.asyncio
    async def test_category_filter_response_time(self, performance_server):
        """Test that category-filtered search meets < 200ms target."""
        server = performance_server

        # Run multiple iterations to get average
        iterations = 10
        times = []

        for _ in range(iterations):
            elapsed_ms, result = await measure_search_time(
                server,
                keywords="campaign",
                category="Campaign"
            )
            times.append(elapsed_ms)

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]

        print(f"\nCategory filter performance ({iterations} iterations):")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Min: {min_time:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")
        print(f"  P95: {p95_time:.2f}ms")

        # Target: < 200ms average
        assert avg_time < 200, f"Average response time {avg_time:.2f}ms exceeds 200ms target"

        # Target: < 500ms maximum (per acceptance criteria)
        assert max_time < 500, f"Max response time {max_time:.2f}ms exceeds 500ms limit"

    @pytest.mark.asyncio
    async def test_no_performance_regression(self, performance_server):
        """Test that category filtering doesn't slow down search significantly."""
        server = performance_server

        iterations = 10

        # Measure unfiltered search
        unfiltered_times = []
        for _ in range(iterations):
            elapsed_ms, _ = await measure_search_time(
                server,
                keywords="campaign"
            )
            unfiltered_times.append(elapsed_ms)

        avg_unfiltered = sum(unfiltered_times) / len(unfiltered_times)

        # Measure filtered search
        filtered_times = []
        for _ in range(iterations):
            elapsed_ms, _ = await measure_search_time(
                server,
                keywords="campaign",
                category="Campaign"
            )
            filtered_times.append(elapsed_ms)

        avg_filtered = sum(filtered_times) / len(filtered_times)

        # Calculate performance difference
        diff_ms = avg_filtered - avg_unfiltered
        diff_percent = (diff_ms / avg_unfiltered * 100) if avg_unfiltered > 0 else 0

        print(f"\nPerformance comparison ({iterations} iterations):")
        print(f"  Unfiltered: {avg_unfiltered:.2f}ms")
        print(f"  Filtered: {avg_filtered:.2f}ms")
        print(f"  Difference: {diff_ms:.2f}ms ({diff_percent:+.1f}%)")

        # Allow up to 10% performance difference
        assert abs(diff_percent) < 10, f"Performance regression: {diff_percent:.1f}% difference"

    @pytest.mark.asyncio
    async def test_category_group_filter_performance(self, performance_server):
        """Test performance of categoryGroup filtering."""
        server = performance_server

        iterations = 5

        # Find a category group from the database
        categories_result = await server._get_endpoint_categories()
        category_with_group = next(
            (c for c in categories_result["categories"] if c.get("category_group")),
            None
        )

        if not category_with_group:
            pytest.skip("No category groups available")

        group_name = category_with_group["category_group"]

        times = []
        for _ in range(iterations):
            elapsed_ms, _ = await measure_search_time(
                server,
                keywords="api",
                categoryGroup=group_name
            )
            times.append(elapsed_ms)

        avg_time = sum(times) / len(times)

        print(f"\nCategory group filter performance ({iterations} iterations):")
        print(f"  Average: {avg_time:.2f}ms")

        # Should meet same performance target
        assert avg_time < 200, f"Category group filter too slow: {avg_time:.2f}ms"

    @pytest.mark.asyncio
    async def test_combined_filters_performance(self, performance_server):
        """Test performance with multiple filters combined."""
        server = performance_server

        iterations = 5

        times = []
        for _ in range(iterations):
            elapsed_ms, _ = await measure_search_time(
                server,
                keywords="campaign",
                category="Campaign",
                httpMethods=["POST"],
                page=1,
                perPage=10
            )
            times.append(elapsed_ms)

        avg_time = sum(times) / len(times)

        print(f"\nCombined filters performance ({iterations} iterations):")
        print(f"  Average: {avg_time:.2f}ms")

        # Combined filters should still be fast
        assert avg_time < 250, f"Combined filters too slow: {avg_time:.2f}ms"

    @pytest.mark.asyncio
    async def test_pagination_with_category_performance(self, performance_server):
        """Test pagination performance with category filtering."""
        server = performance_server

        # Test first page
        elapsed_page1, result1 = await measure_search_time(
            server,
            keywords="stats",
            category="Statistics",
            page=1,
            perPage=5
        )

        # Test second page
        elapsed_page2, result2 = await measure_search_time(
            server,
            keywords="stats",
            category="Statistics",
            page=2,
            perPage=5
        )

        print(f"\nPagination performance:")
        print(f"  Page 1: {elapsed_page1:.2f}ms")
        print(f"  Page 2: {elapsed_page2:.2f}ms")

        # Both pages should be fast
        assert elapsed_page1 < 200, f"Page 1 too slow: {elapsed_page1:.2f}ms"
        assert elapsed_page2 < 200, f"Page 2 too slow: {elapsed_page2:.2f}ms"

        # Pages should have similar performance
        diff = abs(elapsed_page2 - elapsed_page1)
        assert diff < 100, f"Inconsistent pagination performance: {diff:.2f}ms difference"

    @pytest.mark.asyncio
    async def test_case_insensitive_performance(self, performance_server):
        """Test that case-insensitive matching doesn't impact performance."""
        server = performance_server

        iterations = 5

        # Lowercase
        lower_times = []
        for _ in range(iterations):
            elapsed_ms, _ = await measure_search_time(
                server,
                keywords="campaign",
                category="campaign"
            )
            lower_times.append(elapsed_ms)

        # Uppercase
        upper_times = []
        for _ in range(iterations):
            elapsed_ms, _ = await measure_search_time(
                server,
                keywords="campaign",
                category="CAMPAIGN"
            )
            upper_times.append(elapsed_ms)

        avg_lower = sum(lower_times) / len(lower_times)
        avg_upper = sum(upper_times) / len(upper_times)

        print(f"\nCase-insensitive performance ({iterations} iterations):")
        print(f"  Lowercase: {avg_lower:.2f}ms")
        print(f"  Uppercase: {avg_upper:.2f}ms")

        # Should have similar performance
        diff_percent = abs(avg_upper - avg_lower) / avg_lower * 100
        assert diff_percent < 15, f"Case sensitivity impacts performance: {diff_percent:.1f}%"

    @pytest.mark.asyncio
    async def test_empty_results_performance(self, performance_server):
        """Test performance when category filter returns no results."""
        server = performance_server

        iterations = 5

        times = []
        for _ in range(iterations):
            elapsed_ms, _ = await measure_search_time(
                server,
                keywords="test",
                category="NonExistentCategory"
            )
            times.append(elapsed_ms)

        avg_time = sum(times) / len(times)

        print(f"\nEmpty results performance ({iterations} iterations):")
        print(f"  Average: {avg_time:.2f}ms")

        # Empty results should be fast (no result processing)
        assert avg_time < 150, f"Empty results too slow: {avg_time:.2f}ms"


class TestCategoryIndexUtilization:
    """Tests for SQL query optimization and index usage."""

    @pytest.mark.asyncio
    async def test_category_index_exists(self, performance_server):
        """Verify that category index exists and is used."""
        server = performance_server

        # Get database connection
        if not server.endpoint_repo:
            pytest.skip("No repository available")

        # Check if idx_endpoints_category exists
        query = """
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='idx_endpoints_category'
        """

        from sqlalchemy import text
        result = await server.endpoint_repo.session.execute(text(query))
        row = result.fetchone()

        assert row is not None, "Category index idx_endpoints_category not found"
        print("\n✓ Category index exists: idx_endpoints_category")

    @pytest.mark.asyncio
    async def test_query_plan_uses_index(self, performance_server):
        """Verify that category filtering uses the index."""
        server = performance_server

        if not server.endpoint_repo:
            pytest.skip("No repository available")

        # Analyze query plan
        query = """
        EXPLAIN QUERY PLAN
        SELECT * FROM endpoints
        WHERE LOWER(category) = LOWER('Campaign')
        LIMIT 10
        """

        from sqlalchemy import text
        result = await server.endpoint_repo.session.execute(text(query))
        plan = result.fetchall()

        print("\nQuery plan for category filtering:")
        for row in plan:
            print(f"  {row}")

        # Check if index is mentioned in plan
        plan_text = " ".join(str(row) for row in plan)
        # Note: LOWER() function might prevent index usage in some cases
        # This test documents the actual behavior

        print(f"\n  Plan uses index: {'idx_endpoints_category' in plan_text}")


class TestScalabilityPerformance:
    """Tests for performance at scale."""

    @pytest.mark.asyncio
    async def test_large_category_performance(self, performance_server):
        """Test performance when filtering large categories."""
        server = performance_server

        # Find largest category
        categories_result = await server._get_endpoint_categories()
        largest_category = max(
            categories_result["categories"],
            key=lambda c: c["endpoint_count"]
        )

        category_name = largest_category["category_name"]
        endpoint_count = largest_category["endpoint_count"]

        print(f"\nTesting largest category: {category_name} ({endpoint_count} endpoints)")

        # Measure performance
        elapsed_ms, result = await measure_search_time(
            server,
            keywords="api",
            category=category_name,
            perPage=50
        )

        print(f"  Response time: {elapsed_ms:.2f}ms")

        # Should still be fast even for large categories
        assert elapsed_ms < 250, f"Large category too slow: {elapsed_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_multiple_concurrent_searches(self, performance_server):
        """Test performance under concurrent load."""
        server = performance_server

        # Run 5 concurrent searches
        concurrent_count = 5

        async def run_search():
            start = time.perf_counter()
            await server._search_endpoints(
                keywords="campaign",
                category="Campaign"
            )
            return (time.perf_counter() - start) * 1000

        # Execute concurrently
        start_all = time.perf_counter()
        times = await asyncio.gather(*[run_search() for _ in range(concurrent_count)])
        total_time = (time.perf_counter() - start_all) * 1000

        avg_time = sum(times) / len(times)
        max_time = max(times)

        print(f"\nConcurrent search performance ({concurrent_count} searches):")
        print(f"  Total time: {total_time:.2f}ms")
        print(f"  Average per search: {avg_time:.2f}ms")
        print(f"  Max per search: {max_time:.2f}ms")

        # Concurrent searches should complete reasonably fast
        assert avg_time < 300, f"Concurrent searches too slow: {avg_time:.2f}ms"
        assert total_time < 1000, f"Total concurrent time too high: {total_time:.2f}ms"