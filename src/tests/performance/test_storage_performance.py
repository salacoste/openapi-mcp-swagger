"""Performance tests for storage layer - validates NFR1 requirements."""

import os
import pytest
import tempfile
import asyncio
import time
import statistics
from typing import List, Dict, Any

from swagger_mcp_server.storage.database import DatabaseManager, DatabaseConfig
from swagger_mcp_server.storage.models import APIMetadata, Endpoint, Schema, SecurityScheme
from swagger_mcp_server.storage.repositories import (
    EndpointRepository, SchemaRepository, SecurityRepository, MetadataRepository
)


@pytest.fixture
async def performance_db():
    """Create a database optimized for performance testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
        temp_path = temp_file.name

    config = DatabaseConfig(
        database_path=temp_path,
        enable_wal=True,  # Enable WAL for better performance
        enable_fts=True,
        vacuum_on_startup=True,
        max_connections=50,
        busy_timeout=10.0
    )

    db_manager = DatabaseManager(config)
    await db_manager.initialize()

    yield db_manager

    await db_manager.close()
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
async def large_dataset(performance_db):
    """Create a large dataset for performance testing."""
    async with performance_db.get_session() as session:
        # Create API metadata
        api = APIMetadata(
            title="Large Test API",
            version="1.0.0",
            openapi_version="3.0.0",
            description="Large API for performance testing",
            base_url="https://large-api.test.com",
            specification_hash="large_test_hash",
            file_path="/test/large_swagger.json",
            file_size=5000000
        )
        session.add(api)
        await session.flush()
        await session.refresh(api)

        # Create schemas (100 schemas)
        schemas = []
        for i in range(100):
            schema = Schema(
                api_id=api.id,
                name=f"Model{i}",
                title=f"Test Model {i}",
                type="object",
                description=f"Test model {i} for performance testing",
                properties={
                    "id": {"type": "integer", "description": f"ID for model {i}"},
                    "name": {"type": "string", "description": f"Name field for model {i}"},
                    "email": {"type": "string", "format": "email"},
                    "created_at": {"type": "string", "format": "date-time"},
                    f"field_{i}": {"type": "string", "description": f"Custom field for model {i}"}
                },
                required=["id", "name"],
                searchable_text=f"Model{i} object test model {i} performance ID name email",
                property_names=["id", "name", "email", "created_at", f"field_{i}"],
                reference_count=i % 20  # Vary reference counts
            )
            schemas.append(schema)

        session.add_all(schemas)
        await session.flush()

        # Create endpoints (500 endpoints)
        endpoints = []
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        for i in range(500):
            method = methods[i % len(methods)]
            endpoint = Endpoint(
                api_id=api.id,
                path=f"/api/v1/resources/{i}" if method == "GET" else f"/api/v1/resources",
                method=method,
                operation_id=f"{method.lower()}Resource{i}",
                summary=f"{method} resource {i}",
                description=f"Perform {method} operation on resource {i}",
                tags=[f"resource-{i % 10}", "api", "v1"],
                parameters=[
                    {
                        "name": "id" if method != "POST" else "resource_id",
                        "in": "path" if method != "POST" else "query",
                        "required": True,
                        "schema": {"type": "integer"}
                    }
                ] if method != "POST" else [],
                request_body={
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/Model{i % 100}"}
                        }
                    }
                } if method in ["POST", "PUT", "PATCH"] else None,
                responses={
                    "200": {
                        "description": f"Resource {i} operation successful",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/Model{i % 100}"}
                            }
                        }
                    },
                    "404": {"description": "Resource not found"},
                    "400": {"description": "Bad request"}
                },
                searchable_text=f"resource {i} {method} api endpoint operation {i % 10} performance test",
                parameter_names=["id", "resource_id"],
                response_codes=["200", "404", "400"],
                content_types=["application/json"],
                schema_dependencies=[f"Model{i % 100}"]
            )
            endpoints.append(endpoint)

        session.add_all(endpoints)

        # Create security schemes (10 schemes)
        security_schemes = []
        scheme_types = ["http", "apiKey", "oauth2"]
        for i in range(10):
            scheme_type = scheme_types[i % len(scheme_types)]
            scheme = SecurityScheme(
                api_id=api.id,
                name=f"Auth{i}",
                type=scheme_type,
                description=f"Authentication scheme {i}",
                http_scheme="bearer" if scheme_type == "http" else None,
                bearer_format="JWT" if scheme_type == "http" else None,
                api_key_name=f"X-API-Key-{i}" if scheme_type == "apiKey" else None,
                api_key_location="header" if scheme_type == "apiKey" else None,
                reference_count=i * 5
            )
            security_schemes.append(scheme)

        session.add_all(security_schemes)
        await session.commit()

        return api


async def measure_time(coro, iterations: int = 1) -> Dict[str, float]:
    """Measure execution time of coroutine with statistics."""
    times = []

    for _ in range(iterations):
        start_time = time.perf_counter()
        await coro
        end_time = time.perf_counter()
        times.append((end_time - start_time) * 1000)  # Convert to milliseconds

    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'min': min(times),
        'max': max(times),
        'p95': statistics.quantiles(times, n=20)[18] if len(times) > 1 else times[0],
        'p99': statistics.quantiles(times, n=100)[98] if len(times) > 1 else times[0]
    }


@pytest.mark.performance
class TestSearchPerformance:
    """Test search performance requirements (NFR1: <200ms)."""

    async def test_endpoint_search_performance(self, performance_db, large_dataset):
        """Test endpoint search meets <200ms requirement."""
        async with performance_db.get_session() as session:
            repo = EndpointRepository(session)

            # Test various search scenarios
            search_scenarios = [
                {"query": "resource", "description": "Common keyword search"},
                {"query": "GET api", "description": "Multi-word search"},
                {"query": "performance", "description": "Single word search"},
                {"query": "resource api endpoint", "description": "Complex multi-word search"},
                {"query": "", "methods": ["GET"], "description": "Method filter only"},
                {"query": "resource", "methods": ["POST", "PUT"], "description": "Keyword + method filter"},
                {"query": "api", "tags": ["resource-1", "resource-2"], "description": "Keyword + tag filter"}
            ]

            for scenario in search_scenarios:
                query = scenario.pop("query")
                description = scenario.pop("description")

                # Measure search time with multiple iterations
                stats = await measure_time(
                    repo.search_endpoints(
                        query=query,
                        api_id=large_dataset.id,
                        limit=50,
                        **scenario
                    ),
                    iterations=10
                )

                print(f"\n{description}:")
                print(f"  Mean: {stats['mean']:.1f}ms")
                print(f"  P95: {stats['p95']:.1f}ms")
                print(f"  P99: {stats['p99']:.1f}ms")

                # Assert NFR1 requirement: <200ms for search
                assert stats['mean'] < 200.0, f"Search too slow: {stats['mean']:.1f}ms > 200ms for '{description}'"
                assert stats['p95'] < 250.0, f"P95 search too slow: {stats['p95']:.1f}ms > 250ms for '{description}'"

    async def test_endpoint_search_large_results(self, performance_db, large_dataset):
        """Test search performance with large result sets."""
        async with performance_db.get_session() as session:
            repo = EndpointRepository(session)

            # Search that returns many results
            stats = await measure_time(
                repo.search_endpoints(
                    query="api",  # Should match most endpoints
                    api_id=large_dataset.id,
                    limit=100
                ),
                iterations=5
            )

            print(f"\nLarge result set search:")
            print(f"  Mean: {stats['mean']:.1f}ms")
            print(f"  P95: {stats['p95']:.1f}ms")

            # Should still be under 200ms even with large result sets
            assert stats['mean'] < 200.0, f"Large result search too slow: {stats['mean']:.1f}ms"

    async def test_schema_search_performance(self, performance_db, large_dataset):
        """Test schema search performance."""
        async with performance_db.get_session() as session:
            repo = SchemaRepository(session)

            search_scenarios = [
                {"query": "Model", "description": "Common schema search"},
                {"query": "performance test", "description": "Multi-word schema search"},
                {"query": "Model object", "description": "Schema type search"}
            ]

            for scenario in search_scenarios:
                query = scenario.pop("query")
                description = scenario.pop("description")

                stats = await measure_time(
                    repo.search_schemas(
                        query=query,
                        api_id=large_dataset.id,
                        limit=50
                    ),
                    iterations=10
                )

                print(f"\n{description}:")
                print(f"  Mean: {stats['mean']:.1f}ms")
                print(f"  P95: {stats['p95']:.1f}ms")

                # Schema search should also be fast
                assert stats['mean'] < 200.0, f"Schema search too slow: {stats['mean']:.1f}ms"


@pytest.mark.performance
class TestSchemaRetrievalPerformance:
    """Test schema retrieval performance requirements (NFR1: <500ms)."""

    async def test_schema_retrieval_by_id(self, performance_db, large_dataset):
        """Test single schema retrieval performance."""
        async with performance_db.get_session() as session:
            repo = SchemaRepository(session)

            # Get all schema IDs
            schemas = await repo.get_schemas_by_api(large_dataset.id)
            schema_ids = [s.id for s in schemas[:10]]  # Test first 10

            # Test retrieving schemas by ID
            for schema_id in schema_ids:
                stats = await measure_time(
                    repo.get_by_id(schema_id),
                    iterations=5
                )

                # Schema retrieval should be <500ms (actually should be much faster)
                assert stats['mean'] < 500.0, f"Schema retrieval too slow: {stats['mean']:.1f}ms"
                assert stats['mean'] < 50.0, f"Schema retrieval unexpectedly slow: {stats['mean']:.1f}ms"

    async def test_schema_with_dependencies(self, performance_db, large_dataset):
        """Test schema retrieval with dependency resolution."""
        async with performance_db.get_session() as session:
            repo = SchemaRepository(session)

            # Find schemas with dependencies
            schemas_with_deps = await repo.list(
                filters={"api_id": large_dataset.id},
                limit=10
            )

            for schema in schemas_with_deps:
                stats = await measure_time(
                    repo.get_schema_with_dependencies(schema.id),
                    iterations=5
                )

                print(f"Schema {schema.name} with deps: {stats['mean']:.1f}ms")

                # Complex schema retrieval should be <500ms
                assert stats['mean'] < 500.0, f"Schema with deps too slow: {stats['mean']:.1f}ms"

    async def test_bulk_schema_retrieval(self, performance_db, large_dataset):
        """Test bulk schema retrieval performance."""
        async with performance_db.get_session() as session:
            repo = SchemaRepository(session)

            # Retrieve all schemas for API
            stats = await measure_time(
                repo.get_schemas_by_api(large_dataset.id),
                iterations=5
            )

            print(f"Bulk schema retrieval (100 schemas): {stats['mean']:.1f}ms")

            # Bulk retrieval should be reasonable
            assert stats['mean'] < 500.0, f"Bulk schema retrieval too slow: {stats['mean']:.1f}ms"


@pytest.mark.performance
class TestDatabasePerformance:
    """Test overall database performance."""

    async def test_concurrent_operations(self, performance_db, large_dataset):
        """Test performance under concurrent load."""

        async def search_task(session, repo, query_suffix):
            """Single search task for concurrent testing."""
            return await repo.search_endpoints(
                query=f"resource {query_suffix}",
                api_id=large_dataset.id,
                limit=20
            )

        # Create multiple concurrent search operations
        concurrent_tasks = []
        for i in range(10):
            async with performance_db.get_session() as session:
                repo = EndpointRepository(session)
                task = search_task(session, repo, i)
                concurrent_tasks.append(task)

        # Measure concurrent execution
        start_time = time.perf_counter()
        results = await asyncio.gather(*concurrent_tasks)
        end_time = time.perf_counter()

        concurrent_time = (end_time - start_time) * 1000
        print(f"10 concurrent searches: {concurrent_time:.1f}ms")

        # Concurrent operations should complete reasonably quickly
        assert concurrent_time < 2000.0, f"Concurrent operations too slow: {concurrent_time:.1f}ms"

        # All searches should return results
        for result in results:
            assert len(result) > 0

    async def test_database_health_check_performance(self, performance_db):
        """Test database health check performance."""
        stats = await measure_time(
            performance_db.health_check(),
            iterations=5
        )

        print(f"Database health check: {stats['mean']:.1f}ms")

        # Health check should be fast
        assert stats['mean'] < 100.0, f"Health check too slow: {stats['mean']:.1f}ms"

    async def test_migration_status_performance(self, performance_db):
        """Test migration status check performance."""
        stats = await measure_time(
            performance_db.get_migration_status(),
            iterations=5
        )

        print(f"Migration status check: {stats['mean']:.1f}ms")

        # Migration status should be reasonably fast
        assert stats['mean'] < 200.0, f"Migration status too slow: {stats['mean']:.1f}ms"


@pytest.mark.performance
class TestMemoryPerformance:
    """Test memory usage and efficiency."""

    async def test_large_result_set_memory(self, performance_db, large_dataset):
        """Test memory usage with large result sets."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        async with performance_db.get_session() as session:
            repo = EndpointRepository(session)

            # Retrieve large result set
            large_results = await repo.search_endpoints(
                query="api",
                api_id=large_dataset.id,
                limit=500  # Get all endpoints
            )

            peak_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = peak_memory - initial_memory

            print(f"Memory used for {len(large_results)} endpoints: {memory_used:.1f}MB")

            # Should not use excessive memory (less than 50MB for this dataset)
            assert memory_used < 50.0, f"Excessive memory usage: {memory_used:.1f}MB"

            # Clean up
            del large_results

    async def test_connection_pooling_efficiency(self, performance_db, large_dataset):
        """Test connection pool efficiency."""

        async def db_operation(i):
            async with performance_db.get_session() as session:
                repo = EndpointRepository(session)
                return await repo.search_endpoints(
                    query=f"resource {i}",
                    api_id=large_dataset.id,
                    limit=10
                )

        # Run many operations to test connection pooling
        start_time = time.perf_counter()
        tasks = [db_operation(i) for i in range(20)]
        results = await asyncio.gather(*tasks)
        end_time = time.perf_counter()

        total_time = (end_time - start_time) * 1000
        avg_time = total_time / len(tasks)

        print(f"20 pooled operations: {total_time:.1f}ms total, {avg_time:.1f}ms avg")

        # Connection pooling should be efficient
        assert avg_time < 50.0, f"Connection pooling inefficient: {avg_time:.1f}ms per operation"
        assert len([r for r in results if r]) == len(tasks), "Some operations failed"


@pytest.mark.performance
class TestIndexPerformance:
    """Test database index performance."""

    async def test_index_usage_verification(self, performance_db, large_dataset):
        """Test that queries are using indexes efficiently."""
        # Test common query patterns that should use indexes

        async with performance_db.get_session() as session:
            repo = EndpointRepository(session)

            # Query by API ID (should use ix_endpoints_api_id)
            stats = await measure_time(
                repo.get_endpoints_by_api(large_dataset.id),
                iterations=5
            )
            print(f"Endpoints by API ID: {stats['mean']:.1f}ms")
            assert stats['mean'] < 100.0, "API ID lookup too slow - index may not be used"

            # Query by method (should use ix_endpoints_method)
            stats = await measure_time(
                repo.list(filters={"method": "GET", "api_id": large_dataset.id}),
                iterations=5
            )
            print(f"Endpoints by method: {stats['mean']:.1f}ms")
            assert stats['mean'] < 100.0, "Method lookup too slow - index may not be used"

    async def test_fts_index_performance(self, performance_db, large_dataset):
        """Test FTS5 full-text search index performance."""
        async with performance_db.get_session() as session:
            repo = EndpointRepository(session)

            # Test FTS5 search
            stats = await measure_time(
                repo.execute_raw_query(
                    "SELECT COUNT(*) FROM endpoints_fts WHERE endpoints_fts MATCH ?",
                    {"match_param": "resource"}
                ),
                iterations=10
            )

            print(f"FTS5 search: {stats['mean']:.1f}ms")

            # FTS5 should be very fast
            assert stats['mean'] < 50.0, f"FTS5 search too slow: {stats['mean']:.1f}ms"


@pytest.mark.performance
@pytest.mark.slow
class TestStressTests:
    """Stress tests for extreme scenarios."""

    async def test_high_concurrency(self, performance_db, large_dataset):
        """Test behavior under high concurrency."""

        async def stress_operation():
            async with performance_db.get_session() as session:
                repo = EndpointRepository(session)
                return await repo.search_endpoints(
                    query="resource",
                    api_id=large_dataset.id,
                    limit=10
                )

        # Run 50 concurrent operations
        start_time = time.perf_counter()
        tasks = [stress_operation() for _ in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.perf_counter()

        total_time = (end_time - start_time) * 1000

        print(f"50 concurrent operations: {total_time:.1f}ms")

        # Check for failures
        failures = [r for r in results if isinstance(r, Exception)]
        success_count = len(results) - len(failures)

        print(f"Success rate: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")

        # Should handle high concurrency well
        assert success_count >= 45, f"Too many failures under stress: {len(failures)} failures"
        assert total_time < 5000.0, f"Stress test too slow: {total_time:.1f}ms"

    async def test_memory_stability(self, performance_db, large_dataset):
        """Test memory stability over many operations."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024

        async with performance_db.get_session() as session:
            repo = EndpointRepository(session)

            # Perform many operations
            for i in range(100):
                await repo.search_endpoints(
                    query=f"resource {i % 10}",
                    api_id=large_dataset.id,
                    limit=20
                )

                # Check memory every 25 operations
                if i % 25 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_growth = current_memory - initial_memory
                    print(f"After {i+1} ops: {memory_growth:.1f}MB growth")

            final_memory = process.memory_info().rss / 1024 / 1024
            total_growth = final_memory - initial_memory

            print(f"Total memory growth after 100 operations: {total_growth:.1f}MB")

            # Memory should not grow excessively
            assert total_growth < 100.0, f"Excessive memory growth: {total_growth:.1f}MB"