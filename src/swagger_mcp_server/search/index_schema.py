"""Search index schema definitions for the Swagger MCP Server.

This module defines the Whoosh index schema structure for searching
API endpoints, parameters, schemas, and related documentation.
Enhanced to support comprehensive endpoint indexing from Story 3.2.
"""

from typing import Any, Dict

from whoosh.analysis import StandardAnalyzer, StemmingAnalyzer
from whoosh.fields import BOOLEAN, ID, KEYWORD, NUMERIC, TEXT, Schema

# Custom analyzer for technical content
TECHNICAL_ANALYZER = StemmingAnalyzer(stoplist=None, minsize=2)
STANDARD_ANALYZER = StandardAnalyzer(stoplist=None, minsize=1)


class IndexSchema:
    """Index schema configuration and field definitions."""

    # Field boost weights optimized for comprehensive endpoint search
    FIELD_WEIGHTS = {
        "endpoint_path": 1.8,
        "operation_summary": 1.5,
        "operation_description": 1.2,
        "searchable_text": 1.0,
        "parameter_names": 0.9,
        "parameter_descriptions": 0.8,
        "tags": 0.7,
        "operation_id": 0.6,
        "resource_name": 1.4,
        "keywords": 0.8,
    }

    @classmethod
    def get_schema(cls) -> Schema:
        """Create and return the comprehensive search index schema.

        Returns:
            Schema: Whoosh schema configured for comprehensive endpoint search
        """
        return Schema(
            # Primary identifier
            endpoint_id=ID(stored=True, unique=True),
            # Core endpoint information
            endpoint_path=TEXT(
                stored=True,
                analyzer=TECHNICAL_ANALYZER,
                field_boost=cls.FIELD_WEIGHTS["endpoint_path"],
            ),
            http_method=KEYWORD(stored=True),
            operation_id=TEXT(
                stored=True,
                analyzer=STANDARD_ANALYZER,
                field_boost=cls.FIELD_WEIGHTS["operation_id"],
            ),
            # Enhanced operation documentation
            operation_summary=TEXT(
                stored=True,
                analyzer=TECHNICAL_ANALYZER,
                field_boost=cls.FIELD_WEIGHTS["operation_summary"],
            ),
            operation_description=TEXT(
                stored=True,
                analyzer=TECHNICAL_ANALYZER,
                field_boost=cls.FIELD_WEIGHTS["operation_description"],
            ),
            # Path processing fields
            path_segments=KEYWORD(stored=True),
            resource_name=TEXT(
                stored=True,
                analyzer=STANDARD_ANALYZER,
                field_boost=cls.FIELD_WEIGHTS["resource_name"],
            ),
            operation_type=KEYWORD(stored=True),
            # Comprehensive parameter information
            parameter_names=TEXT(
                stored=True,
                analyzer=STANDARD_ANALYZER,
                field_boost=cls.FIELD_WEIGHTS["parameter_names"],
            ),
            parameter_descriptions=TEXT(
                stored=True,
                analyzer=TECHNICAL_ANALYZER,
                field_boost=cls.FIELD_WEIGHTS["parameter_descriptions"],
            ),
            parameter_types=KEYWORD(stored=True),
            required_parameters=KEYWORD(stored=True),
            optional_parameters=KEYWORD(stored=True),
            path_parameters=KEYWORD(stored=True),
            query_parameters=KEYWORD(stored=True),
            header_parameters=KEYWORD(stored=True),
            # Response information
            response_types=KEYWORD(stored=True),
            response_schemas=TEXT(stored=True, analyzer=STANDARD_ANALYZER),
            status_codes=KEYWORD(stored=True),
            response_descriptions=TEXT(
                stored=True, analyzer=TECHNICAL_ANALYZER
            ),
            # Security and authentication
            security_requirements=KEYWORD(stored=True),
            security_scopes=KEYWORD(stored=True),
            security_schemes=KEYWORD(stored=True),
            # Classification and organization
            tags=KEYWORD(stored=True, field_boost=cls.FIELD_WEIGHTS["tags"]),
            # Composite search fields
            searchable_text=TEXT(
                stored=True,
                analyzer=TECHNICAL_ANALYZER,
                field_boost=cls.FIELD_WEIGHTS["searchable_text"],
            ),
            keywords=TEXT(
                stored=True,
                analyzer=STANDARD_ANALYZER,
                field_boost=cls.FIELD_WEIGHTS["keywords"],
            ),
            # Additional metadata
            deprecated=BOOLEAN(stored=True),
            content_types=KEYWORD(stored=True),
            has_request_body=BOOLEAN(stored=True),
            has_examples=BOOLEAN(stored=True),
            external_docs=TEXT(stored=True, analyzer=STANDARD_ANALYZER),
            # Index management
            last_updated=NUMERIC(stored=True, numtype=float),
            doc_version=NUMERIC(stored=True, numtype=int, default=1),
        )


def create_search_schema() -> Schema:
    """Factory function to create the search index schema.

    Returns:
        Schema: Configured Whoosh schema for API documentation search
    """
    return IndexSchema.get_schema()


def get_field_weights() -> Dict[str, float]:
    """Get the field boost weights for search ranking.

    Returns:
        Dict[str, float]: Mapping of field names to boost weights
    """
    return IndexSchema.FIELD_WEIGHTS.copy()


def validate_schema_fields(document: Dict[str, Any]) -> bool:
    """Validate that a document contains required schema fields.

    Args:
        document: Document to validate

    Returns:
        bool: True if document is valid for indexing
    """
    required_fields = {"endpoint_id", "endpoint_path", "http_method"}

    return all(field in document for field in required_fields)


def convert_endpoint_document_to_index_fields(endpoint_doc) -> Dict[str, Any]:
    """Convert EndpointSearchDocument to index document format.

    Args:
        endpoint_doc: EndpointSearchDocument instance

    Returns:
        Dict[str, Any]: Document ready for Whoosh indexing
    """
    import time

    from .endpoint_indexing import EndpointSearchDocument

    if not isinstance(endpoint_doc, EndpointSearchDocument):
        raise ValueError("Expected EndpointSearchDocument instance")

    return {
        # Primary identifier
        "endpoint_id": endpoint_doc.endpoint_id,
        # Core endpoint information
        "endpoint_path": endpoint_doc.endpoint_path,
        "http_method": endpoint_doc.http_method,
        "operation_id": endpoint_doc.operation_id,
        # Enhanced operation documentation
        "operation_summary": endpoint_doc.operation_summary,
        "operation_description": endpoint_doc.operation_description,
        # Path processing fields
        "path_segments": " ".join(endpoint_doc.path_segments),
        "resource_name": endpoint_doc.resource_name,
        "operation_type": endpoint_doc.operation_type,
        # Comprehensive parameter information
        "parameter_names": " ".join(endpoint_doc.parameter_names),
        "parameter_descriptions": endpoint_doc.parameter_descriptions,
        "parameter_types": " ".join(endpoint_doc.parameter_types),
        "required_parameters": " ".join(endpoint_doc.required_parameters),
        "optional_parameters": " ".join(endpoint_doc.optional_parameters),
        "path_parameters": " ".join(endpoint_doc.path_parameters),
        "query_parameters": " ".join(endpoint_doc.query_parameters),
        "header_parameters": " ".join(endpoint_doc.header_parameters),
        # Response information
        "response_types": " ".join(endpoint_doc.response_types),
        "response_schemas": " ".join(endpoint_doc.response_schemas),
        "status_codes": " ".join(
            str(code) for code in endpoint_doc.status_codes
        ),
        "response_descriptions": endpoint_doc.response_descriptions,
        # Security and authentication
        "security_requirements": " ".join(endpoint_doc.security_requirements),
        "security_scopes": " ".join(endpoint_doc.security_scopes),
        "security_schemes": " ".join(endpoint_doc.security_schemes),
        # Classification and organization
        "tags": " ".join(endpoint_doc.tags),
        # Composite search fields
        "searchable_text": endpoint_doc.searchable_text,
        "keywords": " ".join(endpoint_doc.keywords),
        # Additional metadata
        "deprecated": endpoint_doc.deprecated,
        "content_types": " ".join(endpoint_doc.content_types),
        "has_request_body": endpoint_doc.has_request_body,
        "has_examples": endpoint_doc.has_examples,
        "external_docs": endpoint_doc.external_docs,
        # Index management
        "last_updated": time.time(),
        "doc_version": 1,
    }
