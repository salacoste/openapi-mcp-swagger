"""Unit tests for intelligent endpoint indexing functionality.

Tests the comprehensive endpoint indexing system from Story 3.2,
ensuring accurate content extraction and document creation.
"""

from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

import pytest

from swagger_mcp_server.search.endpoint_indexing import (
    EndpointDocumentProcessor,
    EndpointSearchDocument,
)
from swagger_mcp_server.search.index_schema import (
    convert_endpoint_document_to_index_fields,
)


class TestEndpointSearchDocument:
    """Test cases for EndpointSearchDocument dataclass."""

    def test_endpoint_document_creation(self):
        """Test basic endpoint document creation."""
        doc = EndpointSearchDocument(
            endpoint_id="test-123",
            endpoint_path="/api/v1/users/{id}",
            http_method="GET",
        )

        assert doc.endpoint_id == "test-123"
        assert doc.endpoint_path == "/api/v1/users/{id}"
        assert doc.http_method == "GET"
        assert doc.operation_summary == ""
        assert doc.parameter_names == []
        assert doc.deprecated is False

    def test_endpoint_document_with_full_data(self):
        """Test endpoint document with comprehensive data."""
        doc = EndpointSearchDocument(
            endpoint_id="user-detail",
            endpoint_path="/api/v1/users/{id}",
            http_method="GET",
            operation_summary="Get user details",
            operation_description="Retrieve detailed information about a specific user",
            path_segments=["users"],
            parameter_names=["id", "include"],
            required_parameters=["id"],
            optional_parameters=["include"],
            path_parameters=["id"],
            query_parameters=["include"],
            response_types=["application/json"],
            status_codes=[200, 404],
            security_requirements=["bearerAuth"],
            tags=["users", "profile"],
            deprecated=False,
            keywords=["user", "profile", "get", "detail"],
        )

        assert doc.operation_summary == "Get user details"
        assert doc.parameter_names == ["id", "include"]
        assert doc.required_parameters == ["id"]
        assert doc.status_codes == [200, 404]
        assert doc.tags == ["users", "profile"]
        assert doc.keywords == ["user", "profile", "get", "detail"]


class TestEndpointDocumentProcessor:
    """Test cases for EndpointDocumentProcessor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = EndpointDocumentProcessor()

    def test_extract_path_segments(self):
        """Test path segment extraction."""
        # Test basic path
        segments = self.processor.extract_path_segments("/api/v1/users")
        assert segments == ["users"]

        # Test path with parameters
        segments = self.processor.extract_path_segments(
            "/api/v1/users/{id}/posts"
        )
        assert segments == ["users", "posts"]

        # Test path with colon parameters
        segments = self.processor.extract_path_segments(
            "/api/v1/users/:id/posts"
        )
        assert segments == ["users", "posts"]

        # Test path with multiple parameters
        segments = self.processor.extract_path_segments(
            "/api/v1/users/{userId}/orders/{orderId}"
        )
        assert segments == ["users", "orders"]

    def test_extract_path_parameters(self):
        """Test path parameter extraction."""
        # Test curly brace parameters
        params = self.processor.extract_path_parameters(
            "/users/{id}/posts/{postId}"
        )
        assert params == ["id", "postId"]

        # Test colon parameters
        params = self.processor.extract_path_parameters(
            "/users/:id/posts/:postId"
        )
        assert params == ["id", "postId"]

        # Test mixed parameters
        params = self.processor.extract_path_parameters(
            "/users/{id}/posts/:postId"
        )
        assert params == ["id", "postId"]

        # Test no parameters
        params = self.processor.extract_path_parameters("/users/posts")
        assert params == []

    @pytest.mark.asyncio
    async def test_process_parameters_comprehensive(self):
        """Test comprehensive parameter processing."""
        parameters = [
            {
                "name": "id",
                "in": "path",
                "required": True,
                "description": "User ID",
                "schema": {"type": "integer"},
            },
            {
                "name": "include",
                "in": "query",
                "required": False,
                "description": "Include related data",
                "schema": {"type": "string"},
            },
            {
                "name": "authorization",
                "in": "header",
                "required": True,
                "description": "Bearer token",
                "schema": {"type": "string"},
            },
        ]

        result = await self.processor.process_parameters(parameters)

        assert result["names"] == ["id", "include", "authorization"]
        assert "id: User ID" in result["descriptions"]
        assert "include: Include related data" in result["descriptions"]
        assert set(result["types"]) == {"integer", "string"}
        assert result["required"] == ["id", "authorization"]
        assert result["optional"] == ["include"]
        assert result["path_params"] == ["id"]
        assert result["query_params"] == ["include"]
        assert result["header_params"] == ["authorization"]

    @pytest.mark.asyncio
    async def test_extract_response_info(self):
        """Test response information extraction."""
        responses = {
            "200": {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/User"}
                    }
                },
            },
            "404": {
                "description": "User not found",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                },
            },
        }

        result = await self.processor.extract_response_info(responses)

        assert result["content_types"] == ["application/json"]
        assert "User" in result["schema_names"]
        assert "Error" in result["schema_names"]
        assert result["status_codes"] == [200, 404]
        assert "200: Successful response" in result["descriptions"]
        assert "404: User not found" in result["descriptions"]

    @pytest.mark.asyncio
    async def test_extract_security_info(self):
        """Test security information extraction."""
        security = [
            {"bearerAuth": []},
            {"apiKey": ["read:users"]},
            {"oauth2": ["users:read", "users:write"]},
        ]

        result = await self.processor.extract_security_info(security)

        assert "bearerAuth" in result["schemes"]
        assert "apiKey" in result["schemes"]
        assert "oauth2" in result["schemes"]
        assert "read:users" in result["scopes"]
        assert "users:read" in result["scopes"]
        assert "users:write" in result["scopes"]
        assert "bearer" in result["scheme_types"]
        assert "apiKey" in result["scheme_types"]
        assert "oauth2" in result["scheme_types"]

    def test_extract_resource_name(self):
        """Test resource name extraction."""
        # Test simple resource
        resource = self.processor.extract_resource_name("/api/v1/users")
        assert resource == "users"

        # Test nested resource
        resource = self.processor.extract_resource_name(
            "/api/v1/users/{id}/posts"
        )
        assert resource == "users"

        # Test multiple segments
        resource = self.processor.extract_resource_name(
            "/organizations/{orgId}/projects/{projectId}"
        )
        assert resource == "organizations"

    def test_classify_operation_type(self):
        """Test operation type classification."""
        # Test based on method and path patterns
        assert (
            self.processor.classify_operation_type("GET", "/users/{id}", "")
            == "read"
        )
        assert (
            self.processor.classify_operation_type("GET", "/users", "")
            == "list"
        )
        assert (
            self.processor.classify_operation_type("POST", "/users", "")
            == "create"
        )
        assert (
            self.processor.classify_operation_type("PUT", "/users/{id}", "")
            == "update"
        )
        assert (
            self.processor.classify_operation_type("DELETE", "/users/{id}", "")
            == "delete"
        )

        # Test based on summary content
        assert (
            self.processor.classify_operation_type(
                "POST", "/users", "Create new user"
            )
            == "create"
        )
        assert (
            self.processor.classify_operation_type(
                "GET", "/users/search", "Search users"
            )
            == "search"
        )
        assert (
            self.processor.classify_operation_type(
                "PUT", "/users/{id}", "Update user profile"
            )
            == "update"
        )

    def test_create_composite_text(self):
        """Test composite text generation."""
        endpoint_data = {
            "summary": "Get user details",
            "description": "Retrieve user information",
            "tags": ["users", "profile"],
            "operation_id": "getUserById",
            "path": "/users/{id}",
        }

        parameter_info = {
            "descriptions": "id: User identifier include: Include related data"
        }

        response_info = {"descriptions": "200: User found 404: User not found"}

        operation_info = {
            "summary": "Get user details",
            "description": "Retrieve user information",
            "operation_id": "getUserById",
        }

        text = self.processor.create_composite_text(
            endpoint_data, parameter_info, response_info, operation_info
        )

        assert "Get user details" in text
        assert "Retrieve user information" in text
        assert "User identifier" in text
        assert "users profile" in text
        assert "getUserById" in text

    def test_extract_keywords(self):
        """Test keyword extraction."""
        searchable_text = "Get user details and retrieve profile information"
        endpoint_data = {
            "method": "GET",
            "tags": ["users", "profile"],
            "operationId": "getUserProfile",
            "path": "/users/{id}",
        }

        keywords = self.processor.extract_keywords(
            searchable_text, endpoint_data
        )

        assert "get" in keywords
        assert "user" in keywords
        assert "profile" in keywords
        assert "users" in keywords
        # Stop words should be filtered out
        assert "and" not in keywords
        assert "the" not in keywords

    def test_has_examples(self):
        """Test example detection."""
        # Test with parameter examples
        endpoint_with_param_examples = {
            "parameters": [{"name": "id", "example": "123"}]
        }
        assert (
            self.processor.has_examples(endpoint_with_param_examples) is True
        )

        # Test with request body examples
        endpoint_with_request_examples = {
            "requestBody": {
                "content": {
                    "application/json": {"example": {"name": "John Doe"}}
                }
            }
        }
        assert (
            self.processor.has_examples(endpoint_with_request_examples) is True
        )

        # Test with response examples
        endpoint_with_response_examples = {
            "responses": {
                "200": {
                    "content": {
                        "application/json": {
                            "examples": {
                                "user": {"value": {"id": 1, "name": "John"}}
                            }
                        }
                    }
                }
            }
        }
        assert (
            self.processor.has_examples(endpoint_with_response_examples)
            is True
        )

        # Test without examples
        endpoint_without_examples = {
            "parameters": [{"name": "id"}],
            "responses": {"200": {"description": "OK"}},
        }
        assert self.processor.has_examples(endpoint_without_examples) is False

    @pytest.mark.asyncio
    async def test_create_endpoint_document_complete(self):
        """Test complete endpoint document creation."""
        endpoint_data = {
            "id": "getUserById",
            "path": "/api/v1/users/{id}",
            "method": "GET",
            "summary": "Get user by ID",
            "description": "Retrieve detailed information about a specific user",
            "operationId": "getUserById",
            "tags": ["users", "profile"],
            "deprecated": False,
            "parameters": [
                {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "description": "User identifier",
                    "schema": {"type": "integer"},
                },
                {
                    "name": "include",
                    "in": "query",
                    "required": False,
                    "description": "Include related data",
                    "schema": {"type": "string"},
                },
            ],
            "responses": {
                "200": {
                    "description": "User found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/User"}
                        }
                    },
                },
                "404": {"description": "User not found"},
            },
            "security": [{"bearerAuth": []}],
        }

        document = await self.processor.create_endpoint_document(endpoint_data)

        # Verify basic information
        assert document.endpoint_id == "getUserById"
        assert document.endpoint_path == "/api/v1/users/{id}"
        assert document.http_method == "GET"
        assert document.operation_summary == "Get user by ID"
        assert (
            document.operation_description
            == "Retrieve detailed information about a specific user"
        )

        # Verify path processing
        assert document.path_segments == ["users"]
        assert document.resource_name == "users"
        assert document.operation_type == "read"

        # Verify parameters
        assert "id" in document.parameter_names
        assert "include" in document.parameter_names
        assert "id" in document.required_parameters
        assert "include" in document.optional_parameters
        assert "id" in document.path_parameters
        assert "include" in document.query_parameters

        # Verify responses
        assert 200 in document.status_codes
        assert 404 in document.status_codes
        assert "User" in document.response_schemas

        # Verify security
        assert "bearerAuth" in document.security_requirements

        # Verify tags and keywords
        assert "users" in document.tags
        assert "profile" in document.tags

        # Verify composite fields
        assert len(document.searchable_text) > 0
        assert len(document.keywords) > 0

    @pytest.mark.asyncio
    async def test_create_endpoint_document_missing_required_fields(self):
        """Test error handling for missing required fields."""
        # Missing 'id' field
        invalid_data = {"path": "/users", "method": "GET"}

        with pytest.raises(
            ValueError, match="must include 'id' and 'path' fields"
        ):
            await self.processor.create_endpoint_document(invalid_data)

        # Missing 'path' field
        invalid_data = {"id": "test", "method": "GET"}

        with pytest.raises(
            ValueError, match="must include 'id' and 'path' fields"
        ):
            await self.processor.create_endpoint_document(invalid_data)


class TestIndexSchemaIntegration:
    """Test integration between endpoint documents and index schema."""

    def test_convert_endpoint_document_to_index_fields(self):
        """Test conversion of endpoint document to index fields."""
        doc = EndpointSearchDocument(
            endpoint_id="test-endpoint",
            endpoint_path="/api/v1/users/{id}",
            http_method="GET",
            operation_summary="Get user",
            operation_description="Retrieve user details",
            path_segments=["users"],
            parameter_names=["id", "include"],
            parameter_types=["integer", "string"],
            required_parameters=["id"],
            optional_parameters=["include"],
            path_parameters=["id"],
            query_parameters=["include"],
            response_types=["application/json"],
            response_schemas=["User"],
            status_codes=[200, 404],
            security_requirements=["bearerAuth"],
            tags=["users"],
            deprecated=False,
            searchable_text="Get user details",
            keywords=["user", "get", "detail"],
            resource_name="users",
            operation_type="read",
            content_types=["application/json"],
            has_request_body=False,
            has_examples=True,
        )

        index_fields = convert_endpoint_document_to_index_fields(doc)

        # Verify all required fields are present
        assert index_fields["endpoint_id"] == "test-endpoint"
        assert index_fields["endpoint_path"] == "/api/v1/users/{id}"
        assert index_fields["http_method"] == "GET"
        assert index_fields["operation_summary"] == "Get user"
        assert index_fields["path_segments"] == "users"
        assert index_fields["parameter_names"] == "id include"
        assert index_fields["parameter_types"] == "integer string"
        assert index_fields["required_parameters"] == "id"
        assert index_fields["response_schemas"] == "User"
        assert index_fields["status_codes"] == "200 404"
        assert index_fields["security_requirements"] == "bearerAuth"
        assert index_fields["tags"] == "users"
        assert index_fields["deprecated"] is False
        assert index_fields["has_request_body"] is False
        assert index_fields["has_examples"] is True

    def test_convert_invalid_document_type(self):
        """Test error handling for invalid document type."""
        with pytest.raises(
            ValueError, match="Expected EndpointSearchDocument instance"
        ):
            convert_endpoint_document_to_index_fields("invalid")


class TestEndpointIndexingEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = EndpointDocumentProcessor()

    @pytest.mark.asyncio
    async def test_process_parameters_with_invalid_data(self):
        """Test parameter processing with invalid or missing data."""
        # Test with non-dict parameters
        parameters = ["invalid", None, {"name": "valid"}]
        result = await self.processor.process_parameters(parameters)
        assert result["names"] == ["valid"]

        # Test with missing fields
        parameters = [
            {"name": "test"},  # Missing other fields
            {"description": "test"},  # Missing name
            {},  # Empty parameter
        ]
        result = await self.processor.process_parameters(parameters)
        assert result["names"] == ["test"]

    @pytest.mark.asyncio
    async def test_extract_response_info_with_invalid_data(self):
        """Test response extraction with invalid data."""
        responses = {
            "invalid": "not a dict",
            "200": {
                "content": {"application/json": {"schema": "invalid schema"}}
            },
        }

        result = await self.processor.extract_response_info(responses)
        assert "application/json" in result["content_types"]
        # Invalid status code should be filtered out
        assert "invalid" not in [str(code) for code in result["status_codes"]]

    @pytest.mark.asyncio
    async def test_extract_security_info_with_invalid_data(self):
        """Test security extraction with invalid data."""
        security = [
            "invalid",  # Not a dict
            {"validScheme": ["scope1", "scope2"]},
            {"anotherScheme": "not a list"},  # Scopes not a list
        ]

        result = await self.processor.extract_security_info(security)
        assert "validScheme" in result["schemes"]
        assert "anotherScheme" in result["schemes"]
        assert "scope1" in result["scopes"]
        assert "scope2" in result["scopes"]

    def test_path_processing_edge_cases(self):
        """Test edge cases in path processing."""
        # Empty path
        segments = self.processor.extract_path_segments("")
        assert segments == []

        # Root path
        segments = self.processor.extract_path_segments("/")
        assert segments == []

        # Path with only version
        segments = self.processor.extract_path_segments("/api/v1")
        assert segments == []

        # Path with special characters
        segments = self.processor.extract_path_segments(
            "/api/v1/user-profiles"
        )
        assert segments == ["user-profiles"]

    def test_keyword_extraction_edge_cases(self):
        """Test keyword extraction edge cases."""
        # Empty text
        keywords = self.processor.extract_keywords(
            "", {"method": "GET", "tags": []}
        )
        assert "get" in keywords

        # Text with only stop words
        keywords = self.processor.extract_keywords(
            "the and for", {"method": "POST", "tags": []}
        )
        assert "post" in keywords
        assert "the" not in keywords

        # Text with special characters
        keywords = self.processor.extract_keywords(
            "user-profile & data", {"method": "GET", "tags": []}
        )
        # Should extract meaningful words, special characters filtered out
        assert any(
            word in keywords for word in ["user", "profile", "data", "get"]
        )

    @pytest.mark.asyncio
    async def test_minimal_endpoint_data(self):
        """Test document creation with minimal required data."""
        minimal_data = {"id": "minimal", "path": "/test", "method": "GET"}

        document = await self.processor.create_endpoint_document(minimal_data)

        assert document.endpoint_id == "minimal"
        assert document.endpoint_path == "/test"
        assert document.http_method == "GET"
        assert document.operation_summary == ""
        assert document.parameter_names == []
        assert document.status_codes == []
        assert document.tags == []
        assert document.deprecated is False
