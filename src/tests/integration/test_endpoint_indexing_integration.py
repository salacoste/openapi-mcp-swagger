"""Integration tests for endpoint indexing with real-world data.

Tests the complete endpoint indexing pipeline with realistic API data
to ensure the comprehensive indexing system works end-to-end.
"""

import pytest
import asyncio
import json
from typing import Dict, Any

from swagger_mcp_server.search.endpoint_indexing import EndpointDocumentProcessor
from swagger_mcp_server.search.index_schema import convert_endpoint_document_to_index_fields


class TestEndpointIndexingIntegration:
    """Integration tests with realistic endpoint data."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = EndpointDocumentProcessor()

    @pytest.mark.asyncio
    async def test_complex_endpoint_processing(self):
        """Test processing of complex endpoint with comprehensive data."""
        # Simulate complex endpoint data like what would come from Ozon API
        complex_endpoint = {
            "id": "get-product-by-id",
            "path": "/api/v2/products/{productId}/details",
            "method": "GET",
            "summary": "Get product details by ID",
            "description": "Retrieve comprehensive product information including pricing, availability, and specifications",
            "operationId": "getProductDetails",
            "tags": ["products", "catalog", "retail"],
            "deprecated": False,
            "parameters": [
                {
                    "name": "productId",
                    "in": "path",
                    "required": True,
                    "description": "Unique identifier for the product",
                    "schema": {"type": "integer", "format": "int64"},
                    "example": 123456
                },
                {
                    "name": "include",
                    "in": "query",
                    "required": False,
                    "description": "Comma-separated list of additional data to include",
                    "schema": {
                        "type": "string",
                        "enum": ["pricing", "inventory", "specifications", "reviews"]
                    },
                    "example": "pricing,inventory"
                },
                {
                    "name": "locale",
                    "in": "query",
                    "required": False,
                    "description": "Locale for localized content",
                    "schema": {"type": "string", "pattern": "^[a-z]{2}-[A-Z]{2}$"},
                    "example": "en-US"
                },
                {
                    "name": "authorization",
                    "in": "header",
                    "required": True,
                    "description": "Bearer token for API access",
                    "schema": {"type": "string"}
                }
            ],
            "responses": {
                "200": {
                    "description": "Product details retrieved successfully",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ProductDetail"
                            },
                            "example": {
                                "id": 123456,
                                "name": "Premium Wireless Headphones",
                                "price": 299.99,
                                "availability": "in_stock"
                            }
                        }
                    }
                },
                "404": {
                    "description": "Product not found",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/Error"
                            }
                        }
                    }
                },
                "401": {
                    "description": "Unauthorized - invalid or missing authentication"
                }
            },
            "security": [
                {"bearerAuth": ["products:read"]},
                {"apiKey": ["products:read"]}
            ],
            "requestBody": None,
            "externalDocs": {
                "url": "https://docs.example.com/products/get-details"
            }
        }

        # Process the endpoint
        document = await self.processor.create_endpoint_document(complex_endpoint)

        # Verify core information
        assert document.endpoint_id == "get-product-by-id"
        assert document.endpoint_path == "/api/v2/products/{productId}/details"
        assert document.http_method == "GET"
        assert document.operation_summary == "Get product details by ID"
        assert "Retrieve comprehensive product information" in document.operation_description

        # Verify path processing
        assert "products" in document.path_segments
        assert "details" in document.path_segments
        assert document.resource_name == "products"
        assert document.operation_type == "read"

        # Verify parameter processing
        assert "productId" in document.parameter_names
        assert "include" in document.parameter_names
        assert "locale" in document.parameter_names
        assert "authorization" in document.parameter_names

        # Verify parameter categorization
        assert "productId" in document.required_parameters
        assert "authorization" in document.required_parameters
        assert "include" in document.optional_parameters
        assert "locale" in document.optional_parameters
        assert "productId" in document.path_parameters
        assert "include" in document.query_parameters
        assert "locale" in document.query_parameters
        assert "authorization" in document.header_parameters

        # Verify response processing
        assert 200 in document.status_codes
        assert 404 in document.status_codes
        assert 401 in document.status_codes
        assert "ProductDetail" in document.response_schemas
        assert "Error" in document.response_schemas
        assert "application/json" in document.response_types

        # Verify security processing
        assert "bearerAuth" in document.security_requirements
        assert "apiKey" in document.security_requirements
        assert "products:read" in document.security_scopes
        assert "bearer" in document.security_schemes
        assert "apiKey" in document.security_schemes

        # Verify tags and metadata
        assert "products" in document.tags
        assert "catalog" in document.tags
        assert "retail" in document.tags
        assert document.deprecated is False
        assert document.has_examples is True
        assert document.has_request_body is False
        assert "https://docs.example.com/products/get-details" in document.external_docs

        # Verify composite fields
        assert len(document.searchable_text) > 100  # Should be substantial
        assert "product" in [kw.lower() for kw in document.keywords]
        assert "get" in [kw.lower() for kw in document.keywords]
        assert len(document.keywords) >= 5

        # Test conversion to index format
        index_fields = convert_endpoint_document_to_index_fields(document)

        # Verify all required fields are present
        required_fields = ["endpoint_id", "endpoint_path", "http_method"]
        for field in required_fields:
            assert field in index_fields
            assert index_fields[field] is not None

        # Verify field types and content
        assert isinstance(index_fields["deprecated"], bool)
        assert isinstance(index_fields["has_request_body"], bool)
        assert isinstance(index_fields["has_examples"], bool)
        assert "productId include locale authorization" == index_fields["parameter_names"]

    @pytest.mark.asyncio
    async def test_minimal_endpoint_processing(self):
        """Test processing of minimal endpoint with limited data."""
        minimal_endpoint = {
            "id": "basic-health-check",
            "path": "/health",
            "method": "GET"
        }

        document = await self.processor.create_endpoint_document(minimal_endpoint)

        # Verify basic information
        assert document.endpoint_id == "basic-health-check"
        assert document.endpoint_path == "/health"
        assert document.http_method == "GET"

        # Verify defaults for missing data
        assert document.operation_summary == ""
        assert document.operation_description == ""
        assert document.parameter_names == []
        assert document.status_codes == []
        assert document.tags == []
        assert document.deprecated is False
        assert document.has_examples is False
        assert document.has_request_body is False

        # Verify path processing still works
        assert document.path_segments == ["health"]
        assert document.resource_name == "health"
        assert document.operation_type in ["read", "list"]  # Could be either for /health endpoint

        # Verify it can be converted to index format
        index_fields = convert_endpoint_document_to_index_fields(document)
        assert index_fields["endpoint_id"] == "basic-health-check"

    @pytest.mark.asyncio
    async def test_post_endpoint_with_request_body(self):
        """Test processing of POST endpoint with request body."""
        post_endpoint = {
            "id": "create-user",
            "path": "/api/v1/users",
            "method": "POST",
            "summary": "Create new user account",
            "description": "Register a new user in the system",
            "operationId": "createUser",
            "tags": ["users", "registration"],
            "parameters": [
                {
                    "name": "content-type",
                    "in": "header",
                    "required": True,
                    "description": "Content type header",
                    "schema": {"type": "string"}
                }
            ],
            "requestBody": {
                "description": "User registration data",
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/UserCreateRequest"
                        },
                        "example": {
                            "username": "john_doe",
                            "email": "john@example.com",
                            "password": "secretpassword"
                        }
                    }
                }
            },
            "responses": {
                "201": {
                    "description": "User created successfully",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/User"
                            }
                        }
                    }
                },
                "400": {
                    "description": "Invalid input data"
                },
                "409": {
                    "description": "User already exists"
                }
            },
            "security": [
                {"apiKey": []}
            ]
        }

        document = await self.processor.create_endpoint_document(post_endpoint)

        # Verify operation classification
        assert document.operation_type == "create"
        assert document.resource_name == "users"

        # Verify request body detection
        assert document.has_request_body is True
        assert document.has_examples is True

        # Verify responses
        assert 201 in document.status_codes
        assert 400 in document.status_codes
        assert 409 in document.status_codes
        assert "User" in document.response_schemas

        # Verify keyword extraction includes operation-specific terms
        keywords_lower = [kw.lower() for kw in document.keywords]
        assert "create" in keywords_lower
        assert "user" in keywords_lower
        assert "post" in keywords_lower

    @pytest.mark.asyncio
    async def test_batch_processing_performance(self):
        """Test performance with multiple endpoints processed in batch."""
        # Create multiple endpoints to test batch processing
        endpoints = []
        for i in range(50):
            endpoint = {
                "id": f"endpoint-{i}",
                "path": f"/api/v1/resource/{i}/{{id}}",
                "method": "GET" if i % 2 == 0 else "POST",
                "summary": f"Operation {i} summary",
                "description": f"Detailed description for operation {i}",
                "tags": [f"tag{i % 5}", "common"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "description": f"Resource ID for operation {i}",
                        "schema": {"type": "integer"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Success response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/Resource{i}"}
                            }
                        }
                    }
                }
            }
            endpoints.append(endpoint)

        # Process all endpoints and measure basic performance
        import time
        start_time = time.time()

        documents = []
        for endpoint in endpoints:
            doc = await self.processor.create_endpoint_document(endpoint)
            documents.append(doc)

        end_time = time.time()
        processing_time = end_time - start_time

        # Basic performance validation
        assert len(documents) == 50
        assert processing_time < 5.0  # Should process 50 endpoints in under 5 seconds

        # Verify all documents are valid
        for i, doc in enumerate(documents):
            assert doc.endpoint_id == f"endpoint-{i}"
            assert len(doc.searchable_text) > 0
            assert len(doc.keywords) > 0
            assert doc.resource_name == "resource"

        # Verify operation type classification
        get_operations = [doc for doc in documents if doc.operation_type == "read"]
        post_operations = [doc for doc in documents if doc.operation_type in ["create", "update"]]
        assert len(get_operations) > 0
        assert len(post_operations) > 0

    @pytest.mark.asyncio
    async def test_edge_case_handling(self):
        """Test handling of edge cases and malformed data."""
        # Test with malformed parameters
        edge_case_endpoint = {
            "id": "edge-case-test",
            "path": "/api/weird/{param1}/test/{param2}",
            "method": "PATCH",
            "summary": "Edge case test endpoint",
            "parameters": [
                {},  # Empty parameter
                {"name": "valid_param", "in": "query"},  # Missing other fields
                {
                    "name": "complex_param",
                    "in": "query",
                    "description": "A parameter with complex requirements",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "nested": {"type": "string"}
                        }
                    }
                }
            ],
            "responses": {
                "default": {
                    "description": "Default response",
                    "content": {
                        "text/plain": {"schema": {"type": "string"}}
                    }
                }
            },
            "security": [
                {},  # Empty security requirement
                {"customAuth": ["read", "write"]}
            ]
        }

        # Should not raise exceptions with malformed data
        document = await self.processor.create_endpoint_document(edge_case_endpoint)

        # Verify basic processing still works
        assert document.endpoint_id == "edge-case-test"
        assert document.http_method == "PATCH"
        assert document.operation_type == "update"

        # Verify path parameters are extracted correctly
        assert "param1" in document.path_parameters
        assert "param2" in document.path_parameters

        # Verify security processing handles malformed data
        assert "customAuth" in document.security_requirements
        assert "read" in document.security_scopes
        assert "write" in document.security_scopes

        # Verify content type processing
        assert "text/plain" in document.content_types

        # Should still produce valid searchable content
        assert len(document.searchable_text) > 0
        assert len(document.keywords) >= 2  # At least method and some words