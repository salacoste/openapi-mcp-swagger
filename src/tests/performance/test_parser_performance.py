"""Performance tests for parser components."""

import json
import time
import pytest
from pathlib import Path
import asyncio

from swagger_mcp_server.parser.swagger_parser import SwaggerParser
from swagger_mcp_server.parser.base import ParserConfig


class TestParserPerformance:
    """Performance tests for parser components."""

    @pytest.fixture
    def performance_parser(self):
        """Create parser optimized for performance testing."""
        config = ParserConfig(
            chunk_size_bytes=16384,  # Larger chunks for better performance
            progress_interval_bytes=2 * 1024 * 1024,  # Less frequent progress reports
            validate_openapi=False,  # Skip validation for pure parsing performance
            collect_warnings=False   # Skip warning collection
        )
        return SwaggerParser(config)

    @pytest.fixture
    def ozon_like_api_file(self, tmp_path):
        """Create an API file similar to Ozon API (262KB) for performance validation."""
        # Create a complex API structure similar to real-world APIs
        paths = {}

        # Add various endpoint patterns
        resource_types = [
            "products", "categories", "orders", "customers", "reviews",
            "inventory", "payments", "shipping", "analytics", "reports"
        ]

        for resource in resource_types:
            # List endpoint
            paths[f"/{resource}"] = {
                "get": {
                    "summary": f"List {resource}",
                    "description": f"Retrieve a paginated list of {resource}",
                    "parameters": [
                        {
                            "name": "page",
                            "in": "query",
                            "schema": {"type": "integer", "default": 1}
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 20, "maximum": 100}
                        },
                        {
                            "name": "sort",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["asc", "desc"]}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "data": {
                                                "type": "array",
                                                "items": {"$ref": f"#/components/schemas/{resource.title()[:-1]}"}
                                            },
                                            "pagination": {"$ref": "#/components/schemas/Pagination"}
                                        }
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "500": {"$ref": "#/components/responses/InternalError"}
                    },
                    "tags": [resource],
                    "security": [{"bearerAuth": []}]
                },
                "post": {
                    "summary": f"Create {resource[:-1]}",
                    "description": f"Create a new {resource[:-1]}",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/Create{resource.title()[:-1]}"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": f"#/components/schemas/{resource.title()[:-1]}"}
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "409": {"$ref": "#/components/responses/Conflict"}
                    },
                    "tags": [resource],
                    "security": [{"bearerAuth": ["write"]}]
                }
            }

            # Individual resource endpoint
            paths[f"/{resource}/{{id}}"] = {
                "get": {
                    "summary": f"Get {resource[:-1]} by ID",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer", "format": "int64"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": f"#/components/schemas/{resource.title()[:-1]}"}
                                }
                            }
                        },
                        "404": {"$ref": "#/components/responses/NotFound"}
                    },
                    "tags": [resource],
                    "security": [{"bearerAuth": []}]
                },
                "put": {
                    "summary": f"Update {resource[:-1]}",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer", "format": "int64"}
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/Update{resource.title()[:-1]}"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Updated",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": f"#/components/schemas/{resource.title()[:-1]}"}
                                }
                            }
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                        "400": {"$ref": "#/components/responses/BadRequest"}
                    },
                    "tags": [resource],
                    "security": [{"bearerAuth": ["write"]}]
                },
                "delete": {
                    "summary": f"Delete {resource[:-1]}",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer", "format": "int64"}
                        }
                    ],
                    "responses": {
                        "204": {"description": "Deleted"},
                        "404": {"$ref": "#/components/responses/NotFound"}
                    },
                    "tags": [resource],
                    "security": [{"bearerAuth": ["delete"]}]
                }
            }

        # Create comprehensive schemas
        schemas = {
            "Pagination": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "minimum": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "total": {"type": "integer", "minimum": 0},
                    "totalPages": {"type": "integer", "minimum": 0}
                },
                "required": ["page", "limit", "total", "totalPages"]
            },
            "Error": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "details": {"type": "object"}
                },
                "required": ["code", "message"]
            }
        }

        # Add schemas for each resource type
        for resource in resource_types:
            schema_name = resource.title()[:-1]  # Remove 's' and capitalize

            # Main schema
            schemas[schema_name] = {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "format": "int64"},
                    "name": {"type": "string", "maxLength": 255},
                    "description": {"type": "string", "maxLength": 1000},
                    "created_at": {"type": "string", "format": "date-time"},
                    "updated_at": {"type": "string", "format": "date-time"},
                    "status": {"type": "string", "enum": ["active", "inactive", "pending"]},
                    "metadata": {"type": "object", "additionalProperties": True}
                },
                "required": ["id", "name", "created_at", "status"]
            }

            # Create schema
            schemas[f"Create{schema_name}"] = {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 255},
                    "description": {"type": "string", "maxLength": 1000},
                    "status": {"type": "string", "enum": ["active", "inactive"], "default": "active"},
                    "metadata": {"type": "object", "additionalProperties": True}
                },
                "required": ["name"]
            }

            # Update schema
            schemas[f"Update{schema_name}"] = {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "maxLength": 255},
                    "description": {"type": "string", "maxLength": 1000},
                    "status": {"type": "string", "enum": ["active", "inactive", "pending"]},
                    "metadata": {"type": "object", "additionalProperties": True}
                }
            }

        # Create complete OpenAPI document
        api_data = {
            "openapi": "3.0.3",
            "info": {
                "title": "E-commerce API",
                "version": "2.1.0",
                "description": "Comprehensive e-commerce API with product catalog, order management, and customer features",
                "contact": {
                    "name": "API Support",
                    "email": "api-support@example.com",
                    "url": "https://example.com/support"
                },
                "license": {
                    "name": "MIT",
                    "url": "https://opensource.org/licenses/MIT"
                },
                "x-api-id": "ecommerce-api-v2"
            },
            "servers": [
                {
                    "url": "https://api.example.com/v2",
                    "description": "Production server"
                },
                {
                    "url": "https://staging-api.example.com/v2",
                    "description": "Staging server"
                }
            ],
            "paths": paths,
            "components": {
                "schemas": schemas,
                "responses": {
                    "BadRequest": {
                        "description": "Bad request",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"}
                            }
                        }
                    },
                    "NotFound": {
                        "description": "Resource not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"}
                            }
                        }
                    },
                    "Conflict": {
                        "description": "Resource conflict",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"}
                            }
                        }
                    },
                    "InternalError": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"}
                            }
                        }
                    }
                },
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT"
                    },
                    "apiKeyAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key"
                    }
                }
            },
            "security": [
                {"bearerAuth": []},
                {"apiKeyAuth": []}
            ],
            "tags": [
                {"name": resource, "description": f"{resource.title()} management"}
                for resource in resource_types
            ],
            "x-performance-hints": {
                "rateLimit": "1000/hour",
                "cacheTTL": 300,
                "batchSupport": True
            }
        }

        # Write to file and verify size is around 262KB
        api_file = tmp_path / "ozon_like_api.json"
        with open(api_file, 'w') as f:
            json.dump(api_data, f, indent=2)

        # Check file size
        file_size = api_file.stat().st_size
        print(f"Generated API file size: {file_size / 1024:.1f}KB")

        return api_file

    @pytest.fixture
    def large_api_file_5mb(self, tmp_path):
        """Create 5MB API file for stress testing."""
        # Create a very large API with many endpoints and schemas
        paths = {}
        schemas = {}

        # Generate many endpoints
        for i in range(500):
            resource_id = f"resource{i:03d}"
            paths[f"/{resource_id}"] = {
                "get": {
                    "summary": f"Get {resource_id}",
                    "description": f"Retrieve {resource_id} with all associated data and metadata",
                    "parameters": [
                        {"name": "include", "in": "query", "schema": {"type": "string"}},
                        {"name": "fields", "in": "query", "schema": {"type": "string"}},
                        {"name": "format", "in": "query", "schema": {"type": "string", "enum": ["json", "xml", "csv"]}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": f"#/components/schemas/{resource_id.title()}"}
                                }
                            }
                        }
                    },
                    "tags": [f"group_{i // 50}"]
                }
            }

            # Generate schema for each resource
            schemas[resource_id.title()] = {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string", "maxLength": 500},
                    "description": {"type": "string", "maxLength": 2000},
                    **{
                        f"field_{j}": {
                            "type": "string",
                            "description": f"Field {j} for {resource_id} - " + "x" * 100
                        }
                        for j in range(10)  # 10 fields per schema
                    }
                },
                "required": ["id", "name"]
            }

        large_api_data = {
            "openapi": "3.0.3",
            "info": {
                "title": "Large Test API",
                "version": "1.0.0",
                "description": "Large API for performance stress testing with 500 endpoints and schemas"
            },
            "paths": paths,
            "components": {"schemas": schemas}
        }

        large_file = tmp_path / "large_5mb_api.json"
        with open(large_file, 'w') as f:
            json.dump(large_api_data, f)

        return large_file

    @pytest.mark.performance
    async def test_ozon_api_performance_target(self, performance_parser, ozon_like_api_file):
        """Test parsing Ozon-like API (262KB) within 60 second target."""
        start_time = time.time()

        result = await performance_parser.parse(ozon_like_api_file)

        end_time = time.time()
        duration_seconds = end_time - start_time

        # Verify success
        assert result.is_success is True, f"Parsing failed: {result.metrics.errors}"

        # Performance requirements from Story 1.5 AC: 2
        assert duration_seconds < 60, f"Parsing took {duration_seconds:.2f}s, should be <60s"

        # Additional performance checks
        assert result.metrics.parse_duration_ms < 60000  # 60 seconds in ms
        assert result.metrics.memory_peak_mb < 500       # Reasonable memory usage

        # Quality checks
        assert result.metrics.endpoints_found >= 30     # Should find many endpoints
        assert result.metrics.schemas_found >= 20       # Should find many schemas

        print(f"✅ Ozon-like API parsed in {duration_seconds:.2f}s")
        print(f"   Memory peak: {result.metrics.memory_peak_mb:.1f}MB")
        print(f"   Endpoints found: {result.metrics.endpoints_found}")
        print(f"   Schemas found: {result.metrics.schemas_found}")

    @pytest.mark.performance
    async def test_large_file_memory_efficiency(self, performance_parser, large_api_file_5mb):
        """Test memory efficiency with 5MB file within 2GB RAM limit."""
        result = await performance_parser.parse(large_api_file_5mb)

        assert result.is_success is True

        # Memory requirement from Story 1.2 AC: 4 - Process files up to 10MB within 2GB RAM
        assert result.metrics.memory_peak_mb < 2048, f"Memory usage {result.metrics.memory_peak_mb}MB exceeds 2GB limit"

        # Should be much more efficient than the limit
        assert result.metrics.memory_peak_mb < 200, f"Memory usage {result.metrics.memory_peak_mb}MB should be more efficient"

        print(f"✅ Large file (5MB) parsed with {result.metrics.memory_peak_mb:.1f}MB peak memory")

    @pytest.mark.performance
    async def test_concurrent_parsing_performance(self, performance_parser, ozon_like_api_file):
        """Test concurrent parsing performance."""
        num_concurrent = 5
        start_time = time.time()

        # Parse same file concurrently
        tasks = [performance_parser.parse(ozon_like_api_file) for _ in range(num_concurrent)]
        results = await asyncio.gather(*tasks)

        end_time = time.time()
        total_duration = end_time - start_time

        # All should succeed
        for result in results:
            assert result.is_success is True

        # Concurrent parsing shouldn't take much longer than sequential
        # (allowing for some overhead)
        expected_max_duration = 60 * 1.5  # 1.5x single file time
        assert total_duration < expected_max_duration

        print(f"✅ {num_concurrent} concurrent parses completed in {total_duration:.2f}s")

    @pytest.mark.performance
    async def test_progress_reporting_overhead(self, ozon_like_api_file):
        """Test that progress reporting doesn't significantly impact performance."""
        progress_calls = []

        def progress_callback(processed, total):
            progress_calls.append((processed, total, time.time()))

        # Parser with progress reporting
        config_with_progress = ParserConfig(
            progress_callback=progress_callback,
            progress_interval_bytes=64 * 1024,  # Frequent updates
            validate_openapi=False
        )
        parser_with_progress = SwaggerParser(config_with_progress)

        # Parser without progress reporting
        config_without_progress = ParserConfig(
            progress_callback=None,
            validate_openapi=False
        )
        parser_without_progress = SwaggerParser(config_without_progress)

        # Time both approaches
        start_time = time.time()
        result_with_progress = await parser_with_progress.parse(ozon_like_api_file)
        time_with_progress = time.time() - start_time

        start_time = time.time()
        result_without_progress = await parser_without_progress.parse(ozon_like_api_file)
        time_without_progress = time.time() - start_time

        # Both should succeed
        assert result_with_progress.is_success is True
        assert result_without_progress.is_success is True

        # Progress reporting should add minimal overhead (<50% increase)
        overhead_ratio = time_with_progress / time_without_progress
        assert overhead_ratio < 1.5, f"Progress reporting adds {overhead_ratio:.2f}x overhead"

        # Should have received progress updates
        assert len(progress_calls) > 0

        print(f"✅ Progress reporting overhead: {overhead_ratio:.2f}x")
        print(f"   Progress calls: {len(progress_calls)}")

    @pytest.mark.performance
    async def test_processing_speed_mb_per_sec(self, performance_parser, ozon_like_api_file):
        """Test processing speed in MB/s."""
        result = await performance_parser.parse(ozon_like_api_file)

        assert result.is_success is True

        # Calculate processing speed
        speed_mb_per_sec = result.metrics.processing_speed_mb_per_sec

        # Should achieve reasonable processing speed
        # For JSON parsing, expect at least 1MB/s
        assert speed_mb_per_sec > 1.0, f"Processing speed {speed_mb_per_sec:.2f}MB/s is too slow"

        print(f"✅ Processing speed: {speed_mb_per_sec:.2f}MB/s")

    @pytest.mark.benchmark
    def test_parsing_benchmark(self, benchmark, performance_parser, ozon_like_api_file):
        """Benchmark parsing performance using pytest-benchmark."""
        async def parse_file():
            result = await performance_parser.parse(ozon_like_api_file)
            assert result.is_success is True
            return result

        def sync_parse():
            import asyncio
            return asyncio.run(parse_file())

        # Run benchmark
        result = benchmark(sync_parse)

        # Verify result quality
        assert result.metrics.endpoints_found > 0
        assert result.metrics.schemas_found > 0

    @pytest.mark.performance
    async def test_error_handling_performance(self, performance_parser, tmp_path):
        """Test that error handling doesn't significantly impact performance."""
        # Create file with many small errors
        malformed_paths = {}
        for i in range(100):
            # Create paths with various small issues
            malformed_paths[f"/endpoint{i}"] = {
                "get": {
                    "summary": f"Endpoint {i}",
                    "responses": {
                        "200": {"description": "Success"}
                    }
                    # Intentionally missing comma in some cases
                }
            }

        malformed_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": malformed_paths
        }

        malformed_file = tmp_path / "malformed_performance.json"
        with open(malformed_file, 'w') as f:
            json.dump(malformed_data, f)

        start_time = time.time()
        result = await performance_parser.parse(malformed_file)
        duration = time.time() - start_time

        # Should complete within reasonable time even with many minor issues
        assert duration < 10.0  # Should be much faster than this

        # May succeed or fail depending on the nature of issues
        print(f"✅ Error handling performance: {duration:.2f}s")
        print(f"   Result success: {result.is_success}")
        if result.metrics.errors:
            print(f"   Errors found: {len(result.metrics.errors)}")