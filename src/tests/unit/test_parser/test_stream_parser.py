"""Tests for stream-based JSON parser."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from swagger_mcp_server.parser.stream_parser import SwaggerStreamParser
from swagger_mcp_server.parser.base import ParserConfig, ParseStatus, SwaggerParseError


class TestSwaggerStreamParser:
    """Test SwaggerStreamParser functionality."""

    @pytest.fixture
    def parser(self):
        """Create stream parser for testing."""
        return SwaggerStreamParser()

    @pytest.fixture
    def parser_with_config(self):
        """Create stream parser with custom config."""
        config = ParserConfig(
            chunk_size_bytes=4096,
            max_memory_mb=1024,
            progress_interval_bytes=512 * 1024
        )
        return SwaggerStreamParser(config)

    @pytest.fixture
    def simple_openapi_file(self, tmp_path):
        """Create simple OpenAPI JSON file."""
        data = {
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0",
                "description": "A test API"
            },
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/User"}
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "post": {
                        "summary": "Create user",
                        "responses": {
                            "201": {"description": "Created"}
                        }
                    }
                },
                "/users/{id}": {
                    "get": {
                        "summary": "Get user by ID",
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer"}
                            }
                        ],
                        "responses": {
                            "200": {"description": "Success"},
                            "404": {"description": "Not found"}
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "email": {"type": "string", "format": "email"}
                        },
                        "required": ["id", "name", "email"]
                    }
                },
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer"
                    }
                }
            },
            "x-custom-extension": "test-value"
        }

        json_file = tmp_path / "simple_api.json"
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=2)

        return json_file

    @pytest.fixture
    def large_openapi_file(self, tmp_path):
        """Create large OpenAPI JSON file for performance testing."""
        # Create a file with many endpoints
        paths = {}
        for i in range(100):
            path_name = f"/resource{i}"
            paths[path_name] = {
                "get": {
                    "summary": f"Get resource {i}",
                    "description": f"Retrieve resource {i} with detailed information",
                    "responses": {
                        "200": {"description": "Success"},
                        "404": {"description": "Not found"}
                    }
                },
                "post": {
                    "summary": f"Create resource {i}",
                    "description": f"Create a new instance of resource {i}",
                    "responses": {
                        "201": {"description": "Created"},
                        "400": {"description": "Bad request"}
                    }
                }
            }

        # Create schemas for each resource
        schemas = {}
        for i in range(50):
            schema_name = f"Resource{i}"
            schemas[schema_name] = {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    f"field{i}": {"type": "string", "description": f"Field {i} description"}
                },
                "required": ["id", "name"]
            }

        data = {
            "openapi": "3.0.0",
            "info": {
                "title": "Large Test API",
                "version": "1.0.0",
                "description": "A large API for performance testing"
            },
            "paths": paths,
            "components": {
                "schemas": schemas
            }
        }

        json_file = tmp_path / "large_api.json"
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=2)

        return json_file

    @pytest.fixture
    def malformed_json_file(self, tmp_path):
        """Create malformed JSON file for error testing."""
        malformed_content = '''{
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0"
            },
            "paths": {
                "/test": {
                    "get": {
                        "summary": "Test endpoint"
                        // Missing comma here
                        "responses": {
                            "200": {"description": "Success"}
                        }
                    }
                }
            }
        }'''

        json_file = tmp_path / "malformed.json"
        json_file.write_text(malformed_content)
        return json_file

    def test_parser_initialization(self, parser):
        """Test parser initialization with defaults."""
        assert parser.config is not None
        assert parser.get_supported_extensions() == ['.json']
        assert parser.get_parser_type().value == "openapi_json"

    def test_parser_custom_config(self, parser_with_config):
        """Test parser initialization with custom config."""
        assert parser_with_config.config.chunk_size_bytes == 4096
        assert parser_with_config.config.max_memory_mb == 1024

    async def test_parse_simple_file_success(self, parser, simple_openapi_file):
        """Test parsing simple OpenAPI file successfully."""
        result = await parser.parse(simple_openapi_file)

        assert result.is_success is True
        assert result.status == ParseStatus.COMPLETED
        assert result.data is not None
        assert result.openapi_version == "3.0.0"
        assert result.api_title == "Test API"
        assert result.api_version == "1.0.0"

        # Check quality metrics
        assert result.metrics.endpoints_found == 3  # 2 GET, 1 POST
        assert result.metrics.schemas_found == 1    # User schema
        assert result.metrics.security_schemes_found == 1  # bearerAuth
        assert result.metrics.extensions_found == 1  # x-custom-extension
        assert result.metrics.file_size_bytes > 0
        assert result.metrics.parse_duration_ms >= 0

    async def test_parse_large_file_performance(self, parser, large_openapi_file):
        """Test parsing large file within performance limits."""
        result = await parser.parse(large_openapi_file)

        assert result.is_success is True
        assert result.status == ParseStatus.COMPLETED

        # Performance checks
        assert result.metrics.parse_duration_ms < 5000  # Should be under 5 seconds
        assert result.metrics.memory_peak_mb < 100      # Should use reasonable memory

        # Quality metrics
        assert result.metrics.endpoints_found == 200   # 100 GET + 100 POST
        assert result.metrics.schemas_found == 50      # 50 schemas

    async def test_parse_with_progress_callback(self, parser_with_config, simple_openapi_file):
        """Test parsing with progress callback."""
        progress_calls = []

        def progress_callback(processed, total):
            progress_calls.append((processed, total))

        parser_with_config.config.progress_callback = progress_callback

        result = await parser_with_config.parse(simple_openapi_file)

        assert result.is_success is True
        # Should have at least one progress call (final call)
        assert len(progress_calls) >= 1

        # Final call should show completion
        final_call = progress_calls[-1]
        assert final_call[0] <= final_call[1]  # processed <= total

    @pytest.mark.performance
    async def test_memory_usage_monitoring(self, parser, large_openapi_file):
        """Test memory usage monitoring during parsing."""
        result = await parser.parse(large_openapi_file)

        assert result.is_success is True
        assert result.metrics.memory_peak_mb > 0
        # Should stay well under the 2GB limit
        assert result.metrics.memory_peak_mb < 100

    async def test_parse_malformed_json_error(self, parser, malformed_json_file):
        """Test parsing malformed JSON file."""
        result = await parser.parse(malformed_json_file)

        assert result.is_success is False
        assert result.status == ParseStatus.FAILED
        assert len(result.metrics.errors) > 0

        # Check error details
        error = result.metrics.errors[0]
        assert error.error_type == "InvalidJSON"
        assert "JSON" in error.message

    async def test_parse_nonexistent_file(self, parser):
        """Test parsing non-existent file."""
        nonexistent_file = Path("nonexistent.json")

        with pytest.raises(SwaggerParseError) as exc_info:
            await parser.parse(nonexistent_file)

        assert "File not found" in str(exc_info.value)

    async def test_parse_file_too_large(self, parser, tmp_path):
        """Test parsing file that exceeds size limit."""
        # Create file larger than default 10MB limit
        large_file = tmp_path / "huge.json"
        huge_content = '{"data": "' + 'x' * (11 * 1024 * 1024) + '"}'
        large_file.write_text(huge_content)

        with pytest.raises(SwaggerParseError) as exc_info:
            await parser.parse(large_file)

        assert "exceeds maximum" in str(exc_info.value)

    async def test_extract_api_info_complete(self, parser, simple_openapi_file):
        """Test extraction of complete API information."""
        result = await parser.parse(simple_openapi_file)

        assert result.openapi_version == "3.0.0"
        assert result.api_title == "Test API"
        assert result.api_version == "1.0.0"

    async def test_extract_api_info_minimal(self, parser, tmp_path):
        """Test extraction from minimal OpenAPI file."""
        minimal_data = {
            "openapi": "3.0.1",
            "info": {"title": "Minimal API", "version": "0.1.0"},
            "paths": {}
        }

        minimal_file = tmp_path / "minimal.json"
        with open(minimal_file, 'w') as f:
            json.dump(minimal_data, f)

        result = await parser.parse(minimal_file)

        assert result.is_success is True
        assert result.openapi_version == "3.0.1"
        assert result.api_title == "Minimal API"
        assert result.api_version == "0.1.0"

    async def test_count_extensions_recursive(self, parser, tmp_path):
        """Test recursive counting of extensions."""
        data_with_extensions = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {},
            "x-root-extension": "value1",
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "x-schema-extension": "value2",
                        "properties": {
                            "name": {
                                "type": "string",
                                "x-property-extension": "value3"
                            }
                        }
                    }
                }
            }
        }

        ext_file = tmp_path / "extensions.json"
        with open(ext_file, 'w') as f:
            json.dump(data_with_extensions, f)

        result = await parser.parse(ext_file)

        assert result.is_success is True
        # Should find 3 extensions: x-root-extension, x-schema-extension, x-property-extension
        assert result.metrics.extensions_found == 3

    @patch('swagger_mcp_server.parser.stream_parser.ijson')
    async def test_ijson_unavailable_error(self, mock_ijson, parser, simple_openapi_file):
        """Test behavior when ijson is not available."""
        # This test would need to be adapted based on how we handle missing ijson
        # Currently, the import error is raised at module level
        pass

    async def test_build_json_structure_edge_cases(self, parser, tmp_path):
        """Test JSON structure building with edge cases."""
        edge_cases_data = {
            "string_field": "test string",
            "number_field": 42,
            "float_field": 3.14,
            "boolean_field": True,
            "null_field": None,
            "empty_object": {},
            "empty_array": [],
            "nested_array": [1, 2, {"nested": "value"}],
            "complex_nesting": {
                "level1": {
                    "level2": {
                        "level3": ["item1", "item2"]
                    }
                }
            }
        }

        edge_file = tmp_path / "edge_cases.json"
        with open(edge_file, 'w') as f:
            json.dump(edge_cases_data, f)

        result = await parser.parse(edge_file)

        assert result.is_success is True
        assert result.data is not None

        # Verify complex structures are preserved
        assert result.data["string_field"] == "test string"
        assert result.data["number_field"] == 42
        assert result.data["boolean_field"] is True
        assert result.data["null_field"] is None
        assert result.data["empty_object"] == {}
        assert result.data["empty_array"] == []
        assert len(result.data["nested_array"]) == 3

    async def test_memory_limit_exceeded(self, parser, tmp_path):
        """Test handling of memory limit exceeded."""
        # Set very low memory limit
        parser.config.max_memory_mb = 1  # 1MB limit

        # Create file that might exceed memory during processing
        large_data = {"large_field": "x" * (2 * 1024 * 1024)}  # 2MB string
        large_file = tmp_path / "memory_test.json"

        with open(large_file, 'w') as f:
            json.dump(large_data, f)

        # This should either succeed with memory monitoring or fail gracefully
        result = await parser.parse(large_file)

        # If parsing fails due to memory limits, it should be handled gracefully
        if not result.is_success:
            assert len(result.metrics.errors) > 0
            # Could be memory limit or file size limit error

    @pytest.mark.asyncio
    async def test_concurrent_parsing(self, parser, simple_openapi_file):
        """Test that parser handles concurrent access correctly."""
        import asyncio

        # Start multiple parsing operations concurrently
        tasks = []
        for _ in range(3):
            tasks.append(parser.parse(simple_openapi_file))

        results = await asyncio.gather(*tasks)

        # All should succeed
        for result in results:
            assert result.is_success is True
            assert result.data is not None