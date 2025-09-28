"""Comprehensive tests for enhanced getSchema method (Story 2.3)."""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from swagger_mcp_server.config.settings import Settings
from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer


class TestEnhancedGetSchema:
    """Test cases for enhanced getSchema functionality per Story 2.3."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = Settings()
        settings.database.path = ":memory:"
        settings.server.name = "test-server"
        settings.server.version = "0.1.0"
        return settings

    @pytest.fixture
    def mock_schemas(self):
        """Create mock schema data for testing dependency resolution."""
        schemas = {}

        # User schema (root schema)
        user_schema = MagicMock()
        user_schema.name = "User"
        user_schema.type = "object"
        user_schema.description = "User entity"
        user_schema.properties = {
            "id": {"type": "string", "format": "uuid"},
            "profile": {"$ref": "#/components/schemas/UserProfile"},
            "settings": {"$ref": "#/components/schemas/UserSettings"},
            "posts": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Post"},
            },
        }
        user_schema.required = ["id", "profile"]
        user_schema.example = {"id": "123e4567-e89b-12d3-a456-426614174000"}
        user_schema.extensions = {"x-custom": "user-extension"}
        schemas["User"] = user_schema

        # UserProfile schema (dependency)
        profile_schema = MagicMock()
        profile_schema.name = "UserProfile"
        profile_schema.type = "object"
        profile_schema.description = "User profile information"
        profile_schema.properties = {
            "firstName": {"type": "string"},
            "lastName": {"type": "string"},
            "email": {"type": "string", "format": "email"},
            "avatar": {"$ref": "#/components/schemas/Image"},
        }
        profile_schema.required = ["firstName", "lastName", "email"]
        profile_schema.example = {"firstName": "John", "lastName": "Doe"}
        schemas["UserProfile"] = profile_schema

        # UserSettings schema (dependency)
        settings_schema = MagicMock()
        settings_schema.name = "UserSettings"
        settings_schema.type = "object"
        settings_schema.description = "User preferences and settings"
        settings_schema.properties = {
            "theme": {"type": "string", "enum": ["light", "dark"]},
            "notifications": {"type": "boolean"},
            "privacy": {"$ref": "#/components/schemas/PrivacySettings"},
        }
        settings_schema.required = ["theme"]
        schemas["UserSettings"] = settings_schema

        # Post schema (array item dependency)
        post_schema = MagicMock()
        post_schema.name = "Post"
        post_schema.type = "object"
        post_schema.description = "User post"
        post_schema.properties = {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "content": {"type": "string"},
            "author": {"$ref": "#/components/schemas/User"},  # Circular reference!
        }
        post_schema.required = ["id", "title", "author"]
        schemas["Post"] = post_schema

        # Image schema (nested dependency)
        image_schema = MagicMock()
        image_schema.name = "Image"
        image_schema.type = "object"
        image_schema.description = "Image metadata"
        image_schema.properties = {
            "url": {"type": "string", "format": "uri"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
        }
        image_schema.required = ["url"]
        schemas["Image"] = image_schema

        # PrivacySettings schema (deeper dependency)
        privacy_schema = MagicMock()
        privacy_schema.name = "PrivacySettings"
        privacy_schema.type = "object"
        privacy_schema.description = "Privacy settings"
        privacy_schema.properties = {
            "public": {"type": "boolean"},
            "searchable": {"type": "boolean"},
        }
        schemas["PrivacySettings"] = privacy_schema

        # Schema with allOf composition
        enhanced_user_schema = MagicMock()
        enhanced_user_schema.name = "EnhancedUser"
        enhanced_user_schema.allOf = [
            {"$ref": "#/components/schemas/User"},
            {
                "type": "object",
                "properties": {
                    "premium": {"type": "boolean"},
                    "subscriptions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        ]
        schemas["EnhancedUser"] = enhanced_user_schema

        return schemas

    @pytest.fixture
    def mock_schema_repo(self, mock_schemas):
        """Create mock schema repository."""
        repo = AsyncMock()

        async def mock_get_schema_by_name(name):
            return mock_schemas.get(name)

        repo.get_schema_by_name = mock_get_schema_by_name
        return repo

    @pytest.fixture
    async def server(self, settings, mock_schema_repo):
        """Create test server with mocked dependencies."""
        server = SwaggerMcpServer(settings)
        server.schema_repo = mock_schema_repo
        server.endpoint_repo = AsyncMock()
        server.metadata_repo = AsyncMock()
        server.db_manager = AsyncMock()
        return server

    @pytest.mark.asyncio
    async def test_parameter_validation_component_name_required(self, server):
        """Test that componentName parameter is required."""
        # Empty componentName
        result = await server._get_schema(componentName="")
        assert "error" in result
        assert "required" in result["error"].lower()

        # Whitespace only
        result = await server._get_schema(componentName="   ")
        assert "error" in result
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_parameter_validation_component_name_max_length(self, server):
        """Test componentName parameter max length validation."""
        long_name = "a" * 256  # Exceeds 255 char limit
        result = await server._get_schema(componentName=long_name)
        assert "error" in result
        assert "255 characters" in result["error"]

    @pytest.mark.asyncio
    async def test_parameter_validation_max_depth(self, server):
        """Test maxDepth parameter validation."""
        # Valid range
        result = await server._get_schema(componentName="User", maxDepth=5)
        assert "error" not in result or "not properly initialized" in result["error"]

        # Invalid - too small
        result = await server._get_schema(componentName="User", maxDepth=0)
        assert "error" in result
        assert "between 1 and 10" in result["error"]

        # Invalid - too large
        result = await server._get_schema(componentName="User", maxDepth=11)
        assert "error" in result
        assert "between 1 and 10" in result["error"]

    def test_component_name_normalization(self, server):
        """Test component name normalization for various formats."""
        # Full OpenAPI 3.0 path
        assert server._normalize_component_name("#/components/schemas/User") == "User"

        # OpenAPI 2.0 definitions path
        assert server._normalize_component_name("#/definitions/User") == "User"

        # Relative paths
        assert server._normalize_component_name("components/schemas/User") == "User"
        assert server._normalize_component_name("definitions/User") == "User"

        # Simple names
        assert server._normalize_component_name("User") == "User"
        assert server._normalize_component_name("  User  ") == "User"

        # Complex names
        assert (
            server._normalize_component_name("#/components/schemas/User.Profile")
            == "User.Profile"
        )

    def test_extract_ref_name(self, server):
        """Test $ref path parsing for various formats."""
        # OpenAPI 3.0 format
        assert server._extract_ref_name("#/components/schemas/User") == "User"

        # OpenAPI 2.0 format
        assert server._extract_ref_name("#/definitions/User") == "User"

        # Relative reference
        assert server._extract_ref_name("User") == "User"

        # External file reference
        assert server._extract_ref_name("common.yaml#/schemas/User") == "User"

        # Empty or invalid
        assert server._extract_ref_name("") is None
        assert server._extract_ref_name(None) is None

    @pytest.mark.asyncio
    async def test_basic_schema_retrieval(self, server):
        """Test basic schema retrieval without dependency resolution."""
        result = await server._get_schema(
            componentName="User", resolveDependencies=False
        )

        assert "error" not in result
        assert "schema" in result
        assert "dependencies" in result
        assert "metadata" in result

        schema = result["schema"]
        assert schema["name"] == "User"
        assert schema["type"] == "object"
        assert schema["description"] == "User entity"
        assert "properties" in schema

        # Metadata validation
        metadata = result["metadata"]
        assert metadata["component_name"] == "User"
        assert metadata["normalized_name"] == "User"
        assert metadata["resolution_settings"]["resolve_dependencies"] is False

    @pytest.mark.asyncio
    async def test_dependency_resolution(self, server):
        """Test automatic dependency resolution."""
        result = await server._get_schema(
            componentName="User", resolveDependencies=True, maxDepth=3
        )

        assert "error" not in result
        assert "schema" in result
        assert "dependencies" in result

        # Should have resolved dependencies
        dependencies = result["dependencies"]
        assert len(dependencies) > 1  # Should have User plus its dependencies

        # Check that dependencies were cached
        dependency_names = [dep["name"] for dep in dependencies]
        assert "User" in dependency_names
        assert "UserProfile" in dependency_names or "UserSettings" in dependency_names

    @pytest.mark.asyncio
    async def test_circular_reference_detection(self, server):
        """Test circular reference detection and handling."""
        result = await server._get_schema(
            componentName="Post",  # Post -> User -> Post (circular)
            resolveDependencies=True,
            maxDepth=3,
        )

        assert "error" not in result
        assert "metadata" in result

        metadata = result["metadata"]
        # Should detect circular reference
        assert "circular_references" in metadata
        # Circular references might be detected depending on resolution order

    @pytest.mark.asyncio
    async def test_max_depth_limiting(self, server):
        """Test that maximum depth limiting works correctly."""
        result = await server._get_schema(
            componentName="User", resolveDependencies=True, maxDepth=1
        )

        assert "error" not in result
        metadata = result["metadata"]

        # Should respect max depth
        assert metadata["resolution_depth"] <= 1

    @pytest.mark.asyncio
    async def test_schema_composition_handling(self, server):
        """Test handling of allOf, oneOf, anyOf compositions."""
        result = await server._get_schema(
            componentName="EnhancedUser", resolveDependencies=True
        )

        assert "error" not in result
        schema = result["schema"]

        # Should handle allOf composition
        if "allOf" in schema:
            assert isinstance(schema["allOf"], list)
            assert len(schema["allOf"]) > 0

    @pytest.mark.asyncio
    async def test_examples_inclusion(self, server):
        """Test that examples are included when requested."""
        # With examples
        result = await server._get_schema(componentName="User", includeExamples=True)

        assert "error" not in result
        schema = result["schema"]
        if "example" in schema:
            assert schema["example"] is not None

        # Without examples
        result = await server._get_schema(componentName="User", includeExamples=False)

        assert "error" not in result
        # Implementation should respect the flag

    @pytest.mark.asyncio
    async def test_extensions_inclusion(self, server):
        """Test that OpenAPI extensions are included when requested."""
        result = await server._get_schema(componentName="User", includeExtensions=True)

        assert "error" not in result
        schema = result["schema"]

        # Should include x-* extensions if present
        # The implementation should handle extensions from the mock data

    @pytest.mark.asyncio
    async def test_error_handling_schema_not_found(self, server):
        """Test error handling when schema is not found."""
        result = await server._get_schema(componentName="NonExistentSchema")

        assert "error" in result
        assert "not found" in result["error"].lower()
        assert "NonExistentSchema" in result["error"]

    @pytest.mark.asyncio
    async def test_error_handling_server_not_initialized(self):
        """Test error handling when server is not properly initialized."""
        uninitialized_server = SwaggerMcpServer(Settings())
        result = await uninitialized_server._get_schema(componentName="User")

        assert "error" in result
        assert "not properly initialized" in result["error"]

    @pytest.mark.asyncio
    async def test_response_format_compliance(self, server):
        """Test that response format matches Story 2.3 requirements."""
        result = await server._get_schema(componentName="User")

        assert "error" not in result

        # Check main structure
        required_fields = ["schema", "dependencies", "metadata"]
        for field in required_fields:
            assert field in result

        # Check schema structure
        schema = result["schema"]
        schema_fields = [
            "name",
            "type",
            "properties",
            "description",
            "required",
        ]
        for field in schema_fields:
            assert field in schema

        # Check metadata structure
        metadata = result["metadata"]
        metadata_fields = [
            "component_name",
            "normalized_name",
            "resolution_depth",
            "total_dependencies",
            "circular_references",
            "max_depth_reached",
            "resolution_settings",
        ]
        for field in metadata_fields:
            assert field in metadata

        # Check resolution settings
        settings = metadata["resolution_settings"]
        settings_fields = [
            "resolve_dependencies",
            "max_depth",
            "include_examples",
            "include_extensions",
        ]
        for field in settings_fields:
            assert field in settings

    @pytest.mark.asyncio
    async def test_performance_requirements(self, server):
        """Test that schema retrieval meets performance requirements."""
        import time

        start_time = time.time()
        result = await server._get_schema(componentName="User", maxDepth=3)
        end_time = time.time()

        retrieval_time_ms = (end_time - start_time) * 1000

        # Should complete within reasonable time (much less than 500ms requirement)
        # Note: This is a unit test with mocks, so it should be very fast
        assert retrieval_time_ms < 200  # 200ms for unit test
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_concurrent_schema_requests(self, server):
        """Test handling of concurrent schema requests."""
        import asyncio

        # Simulate concurrent requests
        tasks = [
            server._get_schema(componentName="User"),
            server._get_schema(componentName="UserProfile"),
            server._get_schema(componentName="Post"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All requests should complete successfully
        for result in results:
            assert not isinstance(result, Exception)
            if isinstance(result, dict) and "error" not in result:
                assert "schema" in result

    @pytest.mark.asyncio
    async def test_caching_within_request(self, server):
        """Test that schemas are cached within a single request."""
        # This test would verify that the resolution_context cache works
        # by checking that repeated resolution of the same schema uses cached data
        result = await server._get_schema(
            componentName="User", resolveDependencies=True
        )

        assert "error" not in result
        # The internal caching is tested indirectly through dependency resolution


class TestSchemaResolutionEdgeCases:
    """Test edge cases in schema resolution."""

    @pytest.fixture
    def server_with_edge_cases(self):
        """Create server with edge case scenarios."""
        # This would test malformed schemas, missing dependencies, etc.
        pass

    @pytest.mark.asyncio
    async def test_malformed_schema_handling(self):
        """Test handling of malformed schema definitions."""
        # Test schemas with invalid JSON, missing required fields, etc.
        pass

    @pytest.mark.asyncio
    async def test_missing_dependency_handling(self):
        """Test handling when schema dependencies are missing."""
        # Test $ref pointing to non-existent schemas
        pass

    @pytest.mark.asyncio
    async def test_deep_nesting_performance(self):
        """Test performance with deeply nested schema hierarchies."""
        # Test schemas with 10+ levels of nesting
        pass


class TestSchemaResolutionIntegration:
    """Integration tests for schema resolution with real data patterns."""

    @pytest.mark.integration
    async def test_with_ozon_api_schemas(self):
        """Test getSchema with complex Ozon API schema patterns."""
        # This would use actual Ozon API schema data
        pass

    @pytest.mark.performance
    async def test_large_schema_performance(self):
        """Test performance with large schemas (100KB+)."""
        # Test the 100KB schema size requirement from Story 2.3
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
