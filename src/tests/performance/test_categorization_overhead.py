"""Performance tests for categorization overhead.

Epic 6: Hierarchical Endpoint Catalog System - Story 6.1
Tests that categorization meets performance requirements (AC 12):
- < 0.3ms overhead per endpoint
- < 100ms total overhead for 100 endpoints
- No regression in parse performance
"""

import time

import pytest

from swagger_mcp_server.parser.categorization import (
    CategorizationEngine,
    CategoryCatalog,
)
from swagger_mcp_server.parser.endpoint_processor import enrich_endpoints_with_categories


@pytest.mark.performance
class TestCategorizationPerformance:
    """Test categorization performance requirements."""

    @pytest.fixture
    def engine_with_tags(self):
        """Create engine with representative tag definitions."""
        engine = CategorizationEngine()
        engine.set_tag_definitions(
            [
                {
                    "name": f"Category{i}",
                    "x-displayName": f"Category {i} Display",
                    "description": f"Category {i} description",
                }
                for i in range(20)
            ]
        )
        engine.set_tag_groups(
            [
                {
                    "name": "API Group",
                    "tags": [f"Category{i}" for i in range(20)],
                }
            ]
        )
        return engine

    @pytest.fixture
    def sample_operations(self):
        """Generate sample operations for performance testing."""
        operations = []
        for i in range(100):
            operations.append(
                {
                    "tags": [f"Category{i % 20}"],
                    "operationId": f"operation{i}",
                    "summary": f"Test operation {i}",
                }
            )
        return operations

    def test_categorization_overhead_per_endpoint(
        self, engine_with_tags, benchmark
    ):
        """Test categorization overhead is < 0.3ms per endpoint."""
        operation = {
            "tags": ["Category1"],
            "operationId": "testOp",
            "summary": "Test operation",
        }
        path = "/api/v1/test"

        def categorize():
            return engine_with_tags.categorize_endpoint(operation, path)

        # Run benchmark
        result = benchmark(categorize)

        # Verify result is correct
        assert result.category == "category1"

        # Check performance: < 0.3ms = 300 microseconds
        stats = benchmark.stats
        mean_time_ms = stats["mean"] * 1000  # Convert to milliseconds

        assert (
            mean_time_ms < 0.3
        ), f"Categorization took {mean_time_ms:.4f}ms (target: <0.3ms)"

    def test_parsing_100_endpoints_with_categorization(
        self, sample_operations, benchmark
    ):
        """Test categorization of 100 endpoints completes in < 100ms."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "tags": [
                {
                    "name": f"Category{i}",
                    "x-displayName": f"Category {i} Display",
                }
                for i in range(20)
            ],
            "x-tagGroups": [
                {"name": "API Group", "tags": [f"Category{i}" for i in range(20)]}
            ],
        }

        # Create endpoints with operations
        endpoints = []
        for i in range(100):
            endpoints.append(
                {
                    "path": f"/api/endpoint{i}",
                    "method": "get",
                    "operation": sample_operations[i],
                }
            )

        def batch_categorize():
            return enrich_endpoints_with_categories(endpoints, spec)

        # Run benchmark
        result = benchmark(batch_categorize)

        # Verify results
        enriched, catalog = result
        assert len(enriched) == 100
        assert len(catalog) > 0

        # Check performance: < 100ms total
        stats = benchmark.stats
        mean_time_ms = stats["mean"] * 1000

        assert (
            mean_time_ms < 100
        ), f"100 endpoints took {mean_time_ms:.2f}ms (target: <100ms)"

    def test_no_regression_in_parse_performance(self, sample_operations):
        """Test categorization doesn't significantly slow down overall parsing."""
        # Simulate parsing without categorization (baseline)
        start = time.perf_counter()
        parsed_operations = []
        for i in range(100):
            # Simulate basic operation parsing
            parsed_operations.append(
                {
                    "path": f"/api/endpoint{i}",
                    "method": "get",
                    "operation_id": sample_operations[i]["operationId"],
                    "summary": sample_operations[i]["summary"],
                }
            )
        baseline_time = time.perf_counter() - start

        # Now with categorization
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "tags": [
                {
                    "name": f"Category{i}",
                    "x-displayName": f"Category {i} Display",
                }
                for i in range(20)
            ],
        }

        endpoints = [
            {
                "path": f"/api/endpoint{i}",
                "method": "get",
                "operation": sample_operations[i],
            }
            for i in range(100)
        ]

        start = time.perf_counter()
        enriched, catalog = enrich_endpoints_with_categories(endpoints, spec)
        categorization_time = time.perf_counter() - start

        # Calculate overhead
        overhead_time = categorization_time - baseline_time
        overhead_ms = overhead_time * 1000

        # Verify no significant regression (should be < 100ms overhead)
        assert overhead_ms < 100, f"Overhead: {overhead_ms:.2f}ms (target: <100ms)"

        # Calculate overhead percentage
        if baseline_time > 0:
            overhead_percent = (overhead_time / baseline_time) * 100
            # Overhead should be < 50% of baseline
            assert (
                overhead_percent < 50
            ), f"Overhead: {overhead_percent:.1f}% (target: <50%)"

    def test_path_extraction_caching_performance(self, engine_with_tags, benchmark):
        """Test LRU cache improves path extraction performance."""
        paths = [f"/api/v1/category{i % 10}/action" for i in range(100)]

        def extract_paths():
            return [engine_with_tags.extract_category_from_path(p) for p in paths]

        # First run (cold cache)
        start = time.perf_counter()
        results_cold = extract_paths()
        cold_time = time.perf_counter() - start

        # Second run (warm cache) - should be faster due to LRU cache
        start = time.perf_counter()
        results_warm = extract_paths()
        warm_time = time.perf_counter() - start

        # Verify cache hit improves performance
        assert warm_time < cold_time, "Cache should improve performance"

        # Warm cache should be significantly faster (at least 30% improvement)
        improvement = ((cold_time - warm_time) / cold_time) * 100
        assert improvement > 30, f"Cache improvement: {improvement:.1f}% (target: >30%)"

    def test_normalize_category_caching_performance(self, benchmark):
        """Test LRU cache improves normalization performance."""
        engine = CategorizationEngine()

        # Repeated normalization should benefit from cache
        category_names = ["Campaign-Management", "Search Promo", "Ad-System"] * 50

        def normalize_batch():
            return [engine.normalize_category_name(name) for name in category_names]

        # Run benchmark
        result = benchmark(normalize_batch)

        # Verify results
        assert len(result) == 150

        # Check performance (should be fast due to caching)
        stats = benchmark.stats
        mean_time_ms = stats["mean"] * 1000

        # 150 normalizations should complete in < 10ms
        assert mean_time_ms < 10, f"Normalization took {mean_time_ms:.2f}ms (target: <10ms)"

    def test_category_catalog_performance(self, benchmark):
        """Test CategoryCatalog.add_endpoint_sync performance."""
        from swagger_mcp_server.parser.categorization import CategoryInfo

        catalog = CategoryCatalog()
        category_info = CategoryInfo(
            category="test",
            display_name="Test Category",
            category_group="Test Group",
        )

        def add_100_endpoints():
            for i in range(100):
                catalog.add_endpoint_sync(category_info, "GET")

        # Run benchmark
        benchmark(add_100_endpoints)

        # Check performance
        stats = benchmark.stats
        mean_time_ms = stats["mean"] * 1000

        # Adding 100 endpoints should be < 5ms
        assert mean_time_ms < 5, f"Catalog update took {mean_time_ms:.2f}ms (target: <5ms)"

    def test_large_api_categorization_scalability(self):
        """Test categorization scales well with large APIs (500+ endpoints)."""
        # Generate large API spec
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Large API", "version": "1.0.0"},
            "tags": [{"name": f"Category{i}"} for i in range(50)],
        }

        # Generate 500 endpoints
        endpoints = []
        for i in range(500):
            endpoints.append(
                {
                    "path": f"/api/v1/resource{i}",
                    "method": "get",
                    "operation": {
                        "tags": [f"Category{i % 50}"],
                        "operationId": f"operation{i}",
                        "summary": f"Operation {i}",
                    },
                }
            )

        # Time categorization
        start = time.perf_counter()
        enriched, catalog = enrich_endpoints_with_categories(endpoints, spec)
        duration = time.perf_counter() - start

        duration_ms = duration * 1000

        # 500 endpoints should complete in < 500ms (1ms per endpoint average)
        assert (
            duration_ms < 500
        ), f"500 endpoints took {duration_ms:.2f}ms (target: <500ms)"

        # Verify results
        assert len(enriched) == 500
        assert len(catalog) == 50  # 50 unique categories

    @pytest.mark.benchmark(
        group="categorization",
        min_rounds=100,
        warmup=True,
    )
    def test_tag_extraction_benchmark(self, engine_with_tags, benchmark):
        """Benchmark tag extraction performance."""
        tags = ["Category5", "Category10"]

        result = benchmark(engine_with_tags.extract_category_from_tags, tags)

        assert result is not None
        assert result.category == "category5"

    @pytest.mark.benchmark(
        group="categorization",
        min_rounds=100,
        warmup=True,
    )
    def test_path_extraction_benchmark(self, engine_with_tags, benchmark):
        """Benchmark path-based extraction performance."""
        path = "/api/v1/campaigns/list"

        result = benchmark(engine_with_tags.extract_category_from_path, path)

        assert result == "campaigns"

    def test_memory_usage_reasonable(self, sample_operations):
        """Test categorization doesn't cause excessive memory usage."""
        import sys

        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "tags": [{"name": f"Category{i}"} for i in range(20)],
        }

        endpoints = [
            {
                "path": f"/api/endpoint{i}",
                "method": "get",
                "operation": sample_operations[i],
            }
            for i in range(100)
        ]

        # Measure memory before
        import gc

        gc.collect()

        # Run categorization
        enriched, catalog = enrich_endpoints_with_categories(endpoints, spec)

        # Memory usage should be reasonable (enriched data ~100KB max)
        enriched_size = sys.getsizeof(enriched)
        catalog_size = sys.getsizeof(catalog)

        # Combined size should be < 500KB for 100 endpoints
        total_size_kb = (enriched_size + catalog_size) / 1024
        assert total_size_kb < 500, f"Memory usage: {total_size_kb:.2f}KB (target: <500KB)"