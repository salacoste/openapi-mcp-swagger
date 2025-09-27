"""Tests for search index schema functionality."""

import pytest
from whoosh.fields import Schema

from swagger_mcp_server.search.index_schema import (
    IndexSchema,
    create_search_schema,
    get_field_weights,
    validate_schema_fields,
)


class TestIndexSchema:
    """Test cases for IndexSchema class."""

    def test_get_schema_returns_valid_schema(self):
        """Test that get_schema returns a valid Whoosh schema."""
        schema = IndexSchema.get_schema()

        assert isinstance(schema, Schema)
        assert "endpoint_id" in schema
        assert "endpoint_path" in schema
        assert "http_method" in schema
        assert "description" in schema

    def test_field_weights_are_correctly_configured(self):
        """Test that field weights match the story requirements."""
        weights = IndexSchema.FIELD_WEIGHTS

        # Verify weights as specified in the story
        assert weights["endpoint_path"] == 1.5
        assert weights["description"] == 1.0
        assert weights["parameters"] == 0.8
        assert weights["tags"] == 0.6
        assert weights["summary"] == 1.2
        assert weights["operation_id"] == 0.9

    def test_schema_contains_all_required_fields(self):
        """Test that schema contains all required fields for API documentation."""
        schema = IndexSchema.get_schema()
        field_names = list(schema.names())

        required_fields = [
            "endpoint_id",
            "endpoint_path",
            "http_method",
            "operation_id",
            "summary",
            "description",
            "parameters",
            "parameter_names",
            "tags",
            "authentication",
            "security_schemes",
            "request_schema",
            "response_schemas",
            "schema_refs",
            "deprecated",
            "response_codes",
            "content_types",
            "last_updated",
            "doc_version",
        ]

        for field in required_fields:
            assert (
                field in field_names
            ), f"Required field '{field}' missing from schema"

    def test_field_properties_are_correctly_configured(self):
        """Test that fields have correct properties (stored, analyzers, etc.)."""
        schema = IndexSchema.get_schema()

        # endpoint_id should be ID type, stored, and unique
        endpoint_id_field = schema["endpoint_id"]
        assert endpoint_id_field.stored is True
        assert endpoint_id_field.unique is True

        # Text fields should have analyzers
        endpoint_path_field = schema["endpoint_path"]
        assert hasattr(endpoint_path_field, "analyzer")
        assert endpoint_path_field.stored is True

        # Boolean fields
        deprecated_field = schema["deprecated"]
        assert deprecated_field.stored is True


class TestSchemaFactoryFunctions:
    """Test schema factory functions."""

    def test_create_search_schema_returns_schema(self):
        """Test that create_search_schema factory function works."""
        schema = create_search_schema()

        assert isinstance(schema, Schema)
        assert "endpoint_id" in schema
        assert "endpoint_path" in schema

    def test_get_field_weights_returns_copy(self):
        """Test that get_field_weights returns a copy of weights."""
        weights1 = get_field_weights()
        weights2 = get_field_weights()

        # Should be equal but not the same object
        assert weights1 == weights2
        assert weights1 is not weights2

        # Modifying one shouldn't affect the other
        weights1["test"] = 999
        assert "test" not in weights2


class TestDocumentValidation:
    """Test document validation functionality."""

    def test_validate_schema_fields_with_valid_document(self):
        """Test validation with a valid document."""
        valid_document = {
            "endpoint_id": "test_id",
            "endpoint_path": "/api/test",
            "http_method": "GET",
            "summary": "Test endpoint",
            "description": "A test endpoint for validation",
        }

        assert validate_schema_fields(valid_document) is True

    def test_validate_schema_fields_with_missing_required_fields(self):
        """Test validation fails with missing required fields."""
        # Missing endpoint_id
        invalid_document1 = {
            "endpoint_path": "/api/test",
            "http_method": "GET",
        }
        assert validate_schema_fields(invalid_document1) is False

        # Missing endpoint_path
        invalid_document2 = {
            "endpoint_id": "test_id",
            "http_method": "GET",
        }
        assert validate_schema_fields(invalid_document2) is False

        # Missing http_method
        invalid_document3 = {
            "endpoint_id": "test_id",
            "endpoint_path": "/api/test",
        }
        assert validate_schema_fields(invalid_document3) is False

    def test_validate_schema_fields_with_extra_fields(self):
        """Test validation passes with extra fields."""
        document_with_extras = {
            "endpoint_id": "test_id",
            "endpoint_path": "/api/test",
            "http_method": "GET",
            "extra_field": "should not affect validation",
            "another_extra": 123,
        }

        assert validate_schema_fields(document_with_extras) is True

    def test_validate_schema_fields_with_empty_document(self):
        """Test validation fails with empty document."""
        assert validate_schema_fields({}) is False

    def test_validate_schema_fields_with_none_values(self):
        """Test validation with None values in required fields."""
        document_with_none = {
            "endpoint_id": None,
            "endpoint_path": "/api/test",
            "http_method": "GET",
        }

        # Should still pass because the field exists (even if None)
        assert validate_schema_fields(document_with_none) is True


class TestFieldBoostConfiguration:
    """Test field boost weights configuration."""

    def test_field_boosts_are_applied_correctly(self):
        """Test that field boost weights are correctly applied to schema fields."""
        schema = IndexSchema.get_schema()
        weights = IndexSchema.FIELD_WEIGHTS

        # Check that boost values are applied to the schema
        # Note: Whoosh field boost is accessed via field_boost attribute
        endpoint_path_field = schema["endpoint_path"]
        if hasattr(endpoint_path_field, "field_boost"):
            assert endpoint_path_field.field_boost == weights["endpoint_path"]

    def test_field_weights_are_numeric(self):
        """Test that all field weights are numeric values."""
        weights = IndexSchema.FIELD_WEIGHTS

        for field_name, weight in weights.items():
            assert isinstance(
                weight, (int, float)
            ), f"Weight for {field_name} is not numeric"
            assert weight > 0, f"Weight for {field_name} must be positive"

    def test_field_weights_priorities_are_logical(self):
        """Test that field weight priorities make sense for API search."""
        weights = IndexSchema.FIELD_WEIGHTS

        # endpoint_path should have high weight for API search
        assert weights["endpoint_path"] > weights["description"]

        # description should have base weight
        assert weights["description"] == 1.0

        # parameters should have reasonable weight
        assert weights["parameters"] > 0.5

        # tags should have lower weight than main content
        assert weights["tags"] < weights["description"]
