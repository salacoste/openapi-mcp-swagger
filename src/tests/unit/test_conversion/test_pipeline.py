"""Tests for the conversion pipeline."""

import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock

from swagger_mcp_server.conversion.pipeline import ConversionPipeline, ConversionError
from swagger_mcp_server.conversion.progress_tracker import ConversionProgressTracker


class TestConversionPipeline:
    """Test the ConversionPipeline class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Create a sample Swagger file
        self.swagger_data = {
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0",
                "description": "A test API"
            },
            "paths": {
                "/users": {
                    "get": {
                        "summary": "Get users",
                        "description": "Retrieve a list of users",
                        "responses": {
                            "200": {
                                "description": "Success"
                            }
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
                            "name": {"type": "string"}
                        }
                    }
                }
            }
        }

        self.swagger_file = os.path.join(self.temp_dir, "test_api.json")
        with open(self.swagger_file, 'w') as f:
            json.dump(self.swagger_data, f)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        output_dir = os.path.join(self.temp_dir, "output")
        pipeline = ConversionPipeline(
            self.swagger_file,
            output_dir,
            {"verbose": True}
        )

        assert pipeline.swagger_file == self.swagger_file
        assert pipeline.output_dir == output_dir
        assert pipeline.options["verbose"] is True
        assert isinstance(pipeline.progress_tracker, ConversionProgressTracker)

    def test_generate_output_dir(self):
        """Test default output directory generation."""
        pipeline = ConversionPipeline(self.swagger_file)

        expected_dir = "./mcp-server-test_api"
        assert pipeline.output_dir == expected_dir

    @pytest.mark.asyncio
    async def test_validate_input_file_success(self):
        """Test successful input file validation."""
        pipeline = ConversionPipeline(self.swagger_file)

        # Should not raise an exception
        await pipeline._validate_input_file()

        # Check conversion stats
        assert "input_file_size" in pipeline.conversion_stats
        assert pipeline.conversion_stats["input_file_size"] > 0

    @pytest.mark.asyncio
    async def test_validate_input_file_not_found(self):
        """Test input file validation with non-existent file."""
        pipeline = ConversionPipeline("/nonexistent/file.json")

        with pytest.raises(ConversionError) as exc_info:
            await pipeline._validate_input_file()

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_input_file_too_large(self):
        """Test input file validation with oversized file."""
        # Create a large file (mock)
        with patch('os.path.getsize', return_value=200 * 1024 * 1024):  # 200MB
            pipeline = ConversionPipeline(self.swagger_file)

            with pytest.raises(ConversionError) as exc_info:
                await pipeline._validate_input_file()

            assert "too large" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_prepare_output_directory(self):
        """Test output directory preparation."""
        output_dir = os.path.join(self.temp_dir, "output")
        pipeline = ConversionPipeline(self.swagger_file, output_dir)

        await pipeline._prepare_output_directory()

        # Check that directory was created
        assert os.path.exists(output_dir)
        assert os.path.exists(os.path.join(output_dir, "data"))
        assert os.path.exists(os.path.join(output_dir, "config"))
        assert os.path.exists(os.path.join(output_dir, "docs"))

    @pytest.mark.asyncio
    async def test_prepare_output_directory_force_overwrite(self):
        """Test output directory preparation with force overwrite."""
        output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(output_dir)

        # Create a file in the directory
        test_file = os.path.join(output_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")

        pipeline = ConversionPipeline(
            self.swagger_file,
            output_dir,
            {"force": True}
        )

        await pipeline._prepare_output_directory()

        # Directory should exist but old file should be gone
        assert os.path.exists(output_dir)
        assert not os.path.exists(test_file)

    @pytest.mark.asyncio
    async def test_preview_conversion(self):
        """Test conversion preview functionality."""
        pipeline = ConversionPipeline(self.swagger_file)

        preview = await pipeline.preview_conversion()

        assert "api_info" in preview
        assert "conversion_plan" in preview
        assert "generated_files" in preview

        api_info = preview["api_info"]
        assert api_info["title"] == "Test API"
        assert api_info["version"] == "1.0.0"

        plan = preview["conversion_plan"]
        assert plan["endpoints_to_process"] == 1
        assert plan["schemas_to_process"] == 1

    @pytest.mark.asyncio
    async def test_validate_swagger_only(self):
        """Test Swagger-only validation."""
        pipeline = ConversionPipeline(self.swagger_file)

        # Should complete without raising exception
        result = await pipeline.validate_swagger_only()
        assert result is True

    @pytest.mark.asyncio
    async def test_estimate_conversion_time(self):
        """Test conversion time estimation."""
        pipeline = ConversionPipeline(self.swagger_file)

        # Test with small numbers
        time_str = pipeline._estimate_conversion_time(5, 3)
        assert "seconds" in time_str

        # Test with large numbers that would take over a minute
        time_str = pipeline._estimate_conversion_time(1000, 500)
        assert "minutes" in time_str

    def test_generate_server_name(self):
        """Test server name generation."""
        pipeline = ConversionPipeline(self.swagger_file)

        # Test with API info
        api_info = {"title": "My Test API"}
        name = pipeline._generate_server_name(api_info)
        assert name == "my-test-api"

        # Test with special characters
        api_info = {"title": "API v2.0 (Beta)!"}
        name = pipeline._generate_server_name(api_info)
        assert name == "api-v20-beta"

        # Test with empty title
        api_info = {"title": ""}
        name = pipeline._generate_server_name(api_info)
        assert name == "swagger-mcp-server"

    @pytest.mark.asyncio
    async def test_generate_troubleshooting_suggestions(self):
        """Test troubleshooting suggestion generation."""
        pipeline = ConversionPipeline(self.swagger_file)

        # Test file not found error
        error = Exception("File not found: /path/to/file")
        suggestions = pipeline._generate_troubleshooting_suggestions(error)
        assert any("path is correct" in s for s in suggestions)

        # Test parse error
        error = Exception("JSON parse error: invalid syntax")
        suggestions = pipeline._generate_troubleshooting_suggestions(error)
        assert any("validate" in s.lower() for s in suggestions)

        # Test memory error
        error = Exception("Memory error: out of memory")
        suggestions = pipeline._generate_troubleshooting_suggestions(error)
        assert any("memory" in s.lower() for s in suggestions)

    def test_conversion_error(self):
        """Test ConversionError exception."""
        error = ConversionError("Test error", {"detail": "test detail"})

        assert error.message == "Test error"
        assert error.details["detail"] == "test detail"
        assert str(error) == "Test error"


class TestConversionPipelineIntegration:
    """Integration tests for the conversion pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Create a more complex Swagger file
        self.swagger_data = {
            "openapi": "3.0.0",
            "info": {
                "title": "Integration Test API",
                "version": "2.0.0",
                "description": "An API for integration testing"
            },
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "operationId": "listUsers",
                        "tags": ["users"],
                        "responses": {"200": {"description": "Success"}}
                    },
                    "post": {
                        "summary": "Create user",
                        "operationId": "createUser",
                        "tags": ["users"],
                        "responses": {"201": {"description": "Created"}}
                    }
                },
                "/users/{id}": {
                    "get": {
                        "summary": "Get user",
                        "operationId": "getUser",
                        "tags": ["users"],
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer"}
                            }
                        ],
                        "responses": {"200": {"description": "Success"}}
                    }
                }
            },
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "required": ["id", "name"],
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "email": {"type": "string", "format": "email"}
                        }
                    },
                    "UserProfile": {
                        "type": "object",
                        "properties": {
                            "user": {"$ref": "#/components/schemas/User"},
                            "bio": {"type": "string"}
                        }
                    }
                }
            }
        }

        self.swagger_file = os.path.join(self.temp_dir, "integration_api.json")
        with open(self.swagger_file, 'w') as f:
            json.dump(self.swagger_data, f)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_full_conversion_mock(self):
        """Test full conversion with mock components."""
        output_dir = os.path.join(self.temp_dir, "output")
        pipeline = ConversionPipeline(
            self.swagger_file,
            output_dir,
            {"skip_validation": True}  # Skip validation for speed
        )

        result = await pipeline.execute_conversion()

        # Check result structure
        assert result["status"] == "success"
        assert result["output_directory"] == output_dir
        assert "server_config" in result
        assert "conversion_stats" in result
        assert "report" in result

        # Check conversion stats
        stats = result["conversion_stats"]
        assert stats["endpoints_found"] == 3  # 3 endpoints total
        assert stats["schemas_found"] == 2    # 2 schemas
        assert stats["api_title"] == "Integration Test API"

        # Check that output directory was created
        assert os.path.exists(output_dir)

        # Check some key files were created
        assert os.path.exists(os.path.join(output_dir, "server.py"))
        assert os.path.exists(os.path.join(output_dir, "README.md"))
        assert os.path.exists(os.path.join(output_dir, "requirements.txt"))

    @pytest.mark.asyncio
    async def test_conversion_with_custom_options(self):
        """Test conversion with custom options."""
        output_dir = os.path.join(self.temp_dir, "custom_output")
        options = {
            "name": "custom-server",
            "port": 9000,
            "verbose": True,
            "skip_validation": True
        }

        pipeline = ConversionPipeline(self.swagger_file, output_dir, options)
        result = await pipeline.execute_conversion()

        # Check that custom options were applied
        server_config = result["server_config"]
        assert server_config["server_name"] == "custom-server"
        assert server_config["port"] == 9000

        # Check output directory
        assert result["output_directory"] == output_dir

    @pytest.mark.asyncio
    async def test_conversion_error_handling(self):
        """Test conversion error handling."""
        # Use non-existent file to trigger error
        pipeline = ConversionPipeline("/nonexistent/file.json")

        with pytest.raises(ConversionError) as exc_info:
            await pipeline.execute_conversion()

        error = exc_info.value
        assert "Conversion failed" in error.message
        assert error.details is not None
        assert "troubleshooting" in error.details


@pytest.mark.performance
class TestConversionPerformance:
    """Performance tests for conversion pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_conversion_speed(self):
        """Test conversion speed meets requirements."""
        import time

        # Create a medium-sized Swagger file
        swagger_data = {
            "openapi": "3.0.0",
            "info": {"title": "Performance Test API", "version": "1.0.0"},
            "paths": {},
            "components": {"schemas": {}}
        }

        # Add multiple endpoints and schemas
        for i in range(20):
            swagger_data["paths"][f"/resource{i}"] = {
                "get": {
                    "summary": f"Get resource {i}",
                    "responses": {"200": {"description": "Success"}}
                }
            }
            swagger_data["components"]["schemas"][f"Resource{i}"] = {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"}
                }
            }

        swagger_file = os.path.join(self.temp_dir, "performance_test.json")
        with open(swagger_file, 'w') as f:
            json.dump(swagger_data, f)

        # Run conversion and measure time
        output_dir = os.path.join(self.temp_dir, "output")
        pipeline = ConversionPipeline(
            swagger_file,
            output_dir,
            {"skip_validation": True}
        )

        start_time = time.time()
        result = await pipeline.execute_conversion()
        end_time = time.time()

        conversion_time = end_time - start_time

        # Should complete in reasonable time (generous limit for test environment)
        assert conversion_time < 10.0, f"Conversion took {conversion_time:.2f}s"

        # Check result
        assert result["status"] == "success"
        assert result["conversion_stats"]["endpoints_found"] == 20
        assert result["conversion_stats"]["schemas_found"] == 20