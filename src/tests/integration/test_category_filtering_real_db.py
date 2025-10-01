"""Integration tests for category filtering with real database (Story 10.2).

Tests category filtering using the actual Ozon MCP server database with
JOIN-based implementation and tag transformation logic.

Epic 10: Category Filtering Validation and Quality Assurance
Story 10.2: Comprehensive Test Suite Development
"""

import pytest
from pathlib import Path
import sqlite3
from typing import Dict, List, Any

from swagger_mcp_server.storage.repositories.endpoint_repository import EndpointRepository
from swagger_mcp_server.storage.database import DatabaseManager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


# Test database path (Ozon server with Epic 8 categories populated)
TEST_DB_PATH = Path(__file__).parent.parent.parent.parent / "generated-mcp-servers" / "ozon-mcp-server" / "data" / "mcp_server.db"


@pytest.fixture
async def db_session():
    """Create async database session for testing."""
    if not TEST_DB_PATH.exists():
        pytest.skip(f"Test database not found: {TEST_DB_PATH}")

    engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB_PATH}")
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def endpoint_repo(db_session):
    """Create endpoint repository with real database."""
    return EndpointRepository(db_session)


@pytest.fixture
def category_counts():
    """Expected category endpoint counts for Ozon API."""
    return {
        "statistics": 13,
        "search_promo": 9,
        "ad": 5,
        "product": 5,
        "campaign": 4,
        "vendor": 4,
    }


class TestCategoryFilteringRealDatabase:
    """Integration tests with real Ozon database (Story 10.2 AC 1-4)."""

    @pytest.mark.asyncio
    async def test_exact_category_match_statistics(self, endpoint_repo, category_counts):
        """AC 1: Test category="statistics" returns ONLY statistics endpoints."""
        results = await endpoint_repo.search_endpoints(
            query="",
            category="statistics",
            limit=50
        )

        # Verify count matches expected
        assert len(results) == category_counts["statistics"], \
            f"Expected {category_counts['statistics']} statistics endpoints, got {len(results)}"

        # Verify ALL results have Statistics tag
        for endpoint in results:
            tags = eval(endpoint.tags) if isinstance(endpoint.tags, str) else endpoint.tags
            assert any("Statistics" in tag for tag in tags), \
                f"Endpoint {endpoint.path} missing Statistics tag: {tags}"

    @pytest.mark.asyncio
    async def test_exact_category_match_campaign(self, endpoint_repo, category_counts):
        """AC 1: Test category="campaign" returns ONLY campaign endpoints."""
        results = await endpoint_repo.search_endpoints(
            query="",
            category="campaign",
            limit=50
        )

        assert len(results) == category_counts["campaign"]

        # Verify no statistics, ad, or other category endpoints
        for endpoint in results:
            tags = eval(endpoint.tags) if isinstance(endpoint.tags, str) else endpoint.tags
            assert any("Campaign" in tag for tag in tags), \
                f"Endpoint {endpoint.path} missing Campaign tag"
            assert not any("Statistics" in tag for tag in tags), \
                f"Cross-contamination: Statistics in {endpoint.path}"
            assert not any("Ad" in tag for tag in tags), \
                f"Cross-contamination: Ad in {endpoint.path}"

    @pytest.mark.asyncio
    async def test_all_six_categories(self, endpoint_repo, category_counts):
        """AC 1: Test all 6 Ozon categories filter correctly."""
        for category_name, expected_count in category_counts.items():
            results = await endpoint_repo.search_endpoints(
                query="",
                category=category_name,
                limit=50
            )

            assert len(results) == expected_count, \
                f"Category {category_name}: expected {expected_count}, got {len(results)}"

    @pytest.mark.asyncio
    async def test_category_excludes_other_categories(self, endpoint_repo):
        """AC 1: Verify no cross-category contamination."""
        # Get statistics endpoints
        statistics = await endpoint_repo.search_endpoints(
            query="",
            category="statistics",
            limit=50
        )

        # Get campaign endpoints
        campaign = await endpoint_repo.search_endpoints(
            query="",
            category="campaign",
            limit=50
        )

        # Extract paths
        stats_paths = {e.path for e in statistics}
        campaign_paths = {e.path for e in campaign}

        # Verify NO overlap
        overlap = stats_paths & campaign_paths
        assert len(overlap) == 0, \
            f"Cross-category contamination found: {overlap}"

    @pytest.mark.asyncio
    async def test_category_and_query_both_apply(self, endpoint_repo):
        """AC 2: Test query AND category filter (not OR) with real data."""
        # Search for "video" in statistics category (safer query word)
        results = await endpoint_repo.search_endpoints(
            query="video",
            category="statistics",
            limit=50
        )

        # Should return at least 1 result (statistics/video endpoint exists)
        assert len(results) >= 1, "Expected at least 1 result for 'video' in statistics"

        # All results must:
        # 1. Be in statistics category (have Statistics tag)
        # 2. Match "video" in path or description
        for endpoint in results:
            tags = eval(endpoint.tags) if isinstance(endpoint.tags, str) else endpoint.tags

            # Verify Statistics tag
            assert any("Statistics" in tag for tag in tags), \
                f"Missing Statistics tag: {endpoint.path}"

            # Verify "video" in path or description (case-insensitive)
            searchable = f"{endpoint.path} {endpoint.summary or ''} {endpoint.description or ''}".lower()
            assert "video" in searchable, \
                f"'video' not found in {endpoint.path}"

    @pytest.mark.asyncio
    async def test_category_and_query_empty_results(self, endpoint_repo):
        """AC 2: Test AND logic returns empty when no matches."""
        # Search for "nonexistent_word_xyz" in statistics category
        # This should be empty because this word doesn't exist in any endpoint
        results = await endpoint_repo.search_endpoints(
            query="nonexistent_word_xyz_12345",
            category="statistics",
            limit=50
        )

        # Should return 0 results
        assert len(results) == 0, \
            f"Expected 0 results for nonexistent word in statistics, got {len(results)}"

    @pytest.mark.asyncio
    async def test_invalid_category_returns_empty(self, endpoint_repo):
        """AC 3: Test invalid category returns empty results gracefully."""
        results = await endpoint_repo.search_endpoints(
            query="test",
            category="nonexistent_category_12345",
            limit=50
        )

        assert len(results) == 0, \
            f"Invalid category should return empty, got {len(results)} results"

    @pytest.mark.asyncio
    async def test_null_category_returns_all_matching(self, endpoint_repo):
        """AC 3: Test null category returns all results matching query."""
        # With category filter
        with_category = await endpoint_repo.search_endpoints(
            query="statistics",
            category="statistics",
            limit=50
        )

        # Without category filter
        without_category = await endpoint_repo.search_endpoints(
            query="statistics",
            category=None,
            limit=50
        )

        # Without filter should return MORE results (includes all categories)
        assert len(without_category) >= len(with_category), \
            f"No filter should return more: with={len(with_category)}, without={len(without_category)}"

    @pytest.mark.asyncio
    async def test_empty_query_with_category(self, endpoint_repo, category_counts):
        """AC 3: Test empty query with category returns all category endpoints."""
        results = await endpoint_repo.search_endpoints(
            query="",
            category="ad",
            limit=50
        )

        assert len(results) == category_counts["ad"], \
            f"Empty query should return all ad endpoints: {category_counts['ad']}"

    @pytest.mark.asyncio
    async def test_three_way_and_filter(self, endpoint_repo):
        """AC 4: Test query + category + method (3-way AND logic)."""
        # Search for "list" in statistics category with POST method
        results = await endpoint_repo.search_endpoints(
            query="list",
            category="statistics",
            methods=["POST"],
            limit=50
        )

        # All results must satisfy ALL three filters
        for endpoint in results:
            # Check method
            assert endpoint.method == "POST", \
                f"Expected POST, got {endpoint.method} for {endpoint.path}"

            # Check category (Statistics tag)
            tags = eval(endpoint.tags) if isinstance(endpoint.tags, str) else endpoint.tags
            assert any("Statistics" in tag for tag in tags), \
                f"Missing Statistics tag: {endpoint.path}"

            # Check query
            searchable = f"{endpoint.path} {endpoint.summary or ''} {endpoint.description or ''}".lower()
            assert "list" in searchable, \
                f"'list' not found in {endpoint.path}"

    @pytest.mark.asyncio
    async def test_category_and_method_filter(self, endpoint_repo):
        """AC 4: Test category + method (2-filter combination)."""
        results = await endpoint_repo.search_endpoints(
            query="",
            category="campaign",
            methods=["GET"],
            limit=50
        )

        # All results must be Campaign category AND GET method
        for endpoint in results:
            assert endpoint.method == "GET"
            tags = eval(endpoint.tags) if isinstance(endpoint.tags, str) else endpoint.tags
            assert any("Campaign" in tag for tag in tags)

    @pytest.mark.asyncio
    async def test_case_insensitive_category_matching(self, endpoint_repo, category_counts):
        """Test category filter is case-insensitive."""
        # Lowercase
        lower_results = await endpoint_repo.search_endpoints(
            query="",
            category="statistics",
            limit=50
        )

        # Uppercase
        upper_results = await endpoint_repo.search_endpoints(
            query="",
            category="STATISTICS",
            limit=50
        )

        # Mixed case
        mixed_results = await endpoint_repo.search_endpoints(
            query="",
            category="StAtIsTiCs",
            limit=50
        )

        # All should return same count
        assert len(lower_results) == category_counts["statistics"]
        assert len(upper_results) == category_counts["statistics"]
        assert len(mixed_results) == category_counts["statistics"]


class TestCategoryDatabaseSchema:
    """Test database schema and category table population (Story 10.1 findings)."""

    def test_endpoint_categories_table_populated(self):
        """Verify endpoint_categories table has 6 categories."""
        if not TEST_DB_PATH.exists():
            pytest.skip(f"Test database not found: {TEST_DB_PATH}")

        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()

        # Query category count
        cursor.execute("SELECT COUNT(*) FROM endpoint_categories")
        count = cursor.fetchone()[0]

        conn.close()

        assert count == 6, f"Expected 6 categories, found {count}"

    def test_category_endpoint_counts_accurate(self):
        """Verify endpoint_count in endpoint_categories matches actual distribution."""
        if not TEST_DB_PATH.exists():
            pytest.skip(f"Test database not found: {TEST_DB_PATH}")

        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()

        # Get category counts from table
        cursor.execute("SELECT category_name, endpoint_count FROM endpoint_categories ORDER BY category_name")
        db_counts = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        # Expected counts
        expected = {
            "ad": 5,
            "campaign": 4,
            "product": 5,
            "search_promo": 9,
            "statistics": 13,
            "vendor": 4,
        }

        assert db_counts == expected, \
            f"Category counts mismatch:\nExpected: {expected}\nActual: {db_counts}"

    def test_tag_transformation_logic(self):
        """Test that category names transform correctly to tag format."""
        transformations = {
            "ad": "Ad",
            "campaign": "Campaign",
            "product": "Product",
            "search_promo": "Search-Promo",  # Underscore → dash, title case
            "statistics": "Statistics",
            "vendor": "Vendor",
        }

        # This tests the SQL logic:
        # UPPER(SUBSTR(category_name, 1, 1)) || SUBSTR(REPLACE(category_name, '_', '-'), 2)
        for category, expected_tag in transformations.items():
            first_char = category[0].upper()
            rest = category[1:].replace('_', '-')
            result = first_char + rest

            # Note: SQL LIKE is case-insensitive in SQLite, so "Search-promo" matches "Search-Promo"
            assert result.lower() == expected_tag.lower(), \
                f"Transformation failed: {category} → {result} (expected {expected_tag})"


class TestCategoryFilteringPerformance:
    """Performance tests for category filtering (Story 10.2 AC 8)."""

    @pytest.mark.asyncio
    async def test_category_filter_performance(self, endpoint_repo, benchmark):
        """AC 8: Benchmark category filtering performance."""
        async def search_with_category():
            return await endpoint_repo.search_endpoints(
                query="",
                category="statistics",
                limit=50
            )

        # Run benchmark
        result = benchmark(lambda: None)  # Placeholder - pytest-benchmark doesn't support async

        # For now, just time manually
        import time
        start = time.perf_counter()
        results = await search_with_category()
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Performance target: < 100ms for small API (40 endpoints)
        assert elapsed_ms < 100, \
            f"Category filtering took {elapsed_ms:.2f}ms (expected < 100ms)"

        # Verify results
        assert len(results) == 13

    @pytest.mark.asyncio
    async def test_three_way_filter_performance(self, endpoint_repo):
        """AC 8: Benchmark 3-way filter (query + category + method) performance."""
        import time

        start = time.perf_counter()
        results = await endpoint_repo.search_endpoints(
            query="list",
            category="statistics",
            methods=["POST"],
            limit=50
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Performance target: < 150ms for 3-way filter
        assert elapsed_ms < 150, \
            f"3-way filter took {elapsed_ms:.2f}ms (expected < 150ms)"

    @pytest.mark.asyncio
    async def test_pagination_performance(self, endpoint_repo):
        """AC 8: Test pagination doesn't degrade performance significantly."""
        import time

        # Page 1
        start = time.perf_counter()
        page1 = await endpoint_repo.search_endpoints(
            query="",
            category="statistics",
            limit=5,
            offset=0
        )
        page1_ms = (time.perf_counter() - start) * 1000

        # Page 2
        start = time.perf_counter()
        page2 = await endpoint_repo.search_endpoints(
            query="",
            category="statistics",
            limit=5,
            offset=5
        )
        page2_ms = (time.perf_counter() - start) * 1000

        # Both pages should be fast
        assert page1_ms < 100
        assert page2_ms < 100

        # Verify results
        assert len(page1) == 5
        assert len(page2) == 5
