"""SQLAlchemy database models for OpenAPI data storage."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

from swagger_mcp_server.config.logging import get_logger

logger = get_logger(__name__)

Base = declarative_base()


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class APIMetadata(Base, TimestampMixin):
    """Stores OpenAPI specification metadata."""

    __tablename__ = "api_metadata"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    openapi_version = Column(String(20), nullable=False)
    description = Column(Text)
    base_url = Column(String(500))
    contact_info = Column(JSON)  # Contact information
    license_info = Column(JSON)  # License information
    servers = Column(JSON)  # Server configurations
    external_docs = Column(JSON)  # External documentation
    extensions = Column(JSON)  # x-* extensions
    specification_hash = Column(String(64))  # SHA-256 hash of original spec
    file_path = Column(String(1000))  # Path to original file
    file_size = Column(Integer)  # File size in bytes
    parse_metadata = Column(JSON)  # Parser metadata and statistics

    # Relationships
    endpoints = relationship(
        "Endpoint", back_populates="api", cascade="all, delete-orphan"
    )
    schemas = relationship(
        "Schema", back_populates="api", cascade="all, delete-orphan"
    )
    security_schemes = relationship(
        "SecurityScheme", back_populates="api", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_api_metadata_title_version", "title", "version"),
        Index("ix_api_metadata_specification_hash", "specification_hash"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "version": self.version,
            "openapi_version": self.openapi_version,
            "description": self.description,
            "base_url": self.base_url,
            "contact_info": self.contact_info,
            "license_info": self.license_info,
            "servers": self.servers,
            "external_docs": self.external_docs,
            "extensions": self.extensions,
            "specification_hash": self.specification_hash,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "parse_metadata": self.parse_metadata,
            "created_at": self.created_at.isoformat()
            if self.created_at
            else None,
            "updated_at": self.updated_at.isoformat()
            if self.updated_at
            else None,
        }


class Endpoint(Base, TimestampMixin):
    """Stores normalized endpoint definitions."""

    __tablename__ = "endpoints"

    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, ForeignKey("api_metadata.id"), nullable=False)
    path = Column(String(1000), nullable=False)
    method = Column(String(10), nullable=False)
    operation_id = Column(String(255))
    summary = Column(String(500))
    description = Column(Text)
    tags = Column(JSON)  # List of tag strings
    parameters = Column(JSON)  # List of parameter objects
    request_body = Column(JSON)  # Request body definition
    responses = Column(JSON)  # Response definitions by status code
    security = Column(JSON)  # Security requirements
    callbacks = Column(JSON)  # Callback definitions
    deprecated = Column(Boolean, default=False)
    extensions = Column(JSON)  # x-* extensions

    # Search optimization fields
    searchable_text = Column(Text)  # Pre-computed searchable content
    parameter_names = Column(JSON)  # List of parameter names for filtering
    response_codes = Column(JSON)  # List of response status codes
    content_types = Column(JSON)  # Request/response content types

    # Dependency tracking
    schema_dependencies = Column(JSON)  # List of referenced schema names
    security_dependencies = Column(
        JSON
    )  # List of referenced security scheme names

    # Relationships
    api = relationship("APIMetadata", back_populates="endpoints")
    dependencies = relationship(
        "EndpointDependency",
        back_populates="endpoint",
        cascade="all, delete-orphan",
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint(
            "api_id", "path", "method", name="uq_endpoint_path_method"
        ),
        Index("ix_endpoints_api_id", "api_id"),
        Index("ix_endpoints_method", "method"),
        Index("ix_endpoints_path", "path"),
        Index("ix_endpoints_operation_id", "operation_id"),
        Index("ix_endpoints_deprecated", "deprecated"),
        Index("ix_endpoints_tags", "tags"),  # JSON index for tag queries
        Index("ix_endpoints_searchable_text", "searchable_text"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "api_id": self.api_id,
            "path": self.path,
            "method": self.method,
            "operation_id": self.operation_id,
            "summary": self.summary,
            "description": self.description,
            "tags": self.tags,
            "parameters": self.parameters,
            "request_body": self.request_body,
            "responses": self.responses,
            "security": self.security,
            "callbacks": self.callbacks,
            "deprecated": self.deprecated,
            "extensions": self.extensions,
            "searchable_text": self.searchable_text,
            "parameter_names": self.parameter_names,
            "response_codes": self.response_codes,
            "content_types": self.content_types,
            "schema_dependencies": self.schema_dependencies,
            "security_dependencies": self.security_dependencies,
            "created_at": self.created_at.isoformat()
            if self.created_at
            else None,
            "updated_at": self.updated_at.isoformat()
            if self.updated_at
            else None,
        }


class Schema(Base, TimestampMixin):
    """Stores normalized schema definitions."""

    __tablename__ = "schemas"

    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, ForeignKey("api_metadata.id"), nullable=False)
    name = Column(String(255), nullable=False)
    title = Column(String(500))
    type = Column(String(50))  # object, array, string, etc.
    format = Column(String(50))  # email, uuid, date-time, etc.
    description = Column(Text)

    # Schema definition components
    properties = Column(JSON)  # Property definitions
    required = Column(JSON)  # List of required property names
    additional_properties = Column(JSON)  # Additional properties definition
    items = Column(JSON)  # Array item schema
    enum = Column(JSON)  # Enumeration values
    example = Column(JSON)  # Example value
    default = Column(JSON)  # Default value

    # Validation constraints
    minimum = Column(JSON)  # Minimum value constraint
    maximum = Column(JSON)  # Maximum value constraint
    min_length = Column(Integer)  # Minimum string length
    max_length = Column(Integer)  # Maximum string length
    pattern = Column(String(500))  # Regex pattern
    min_items = Column(Integer)  # Minimum array items
    max_items = Column(Integer)  # Maximum array items
    unique_items = Column(Boolean)  # Array items must be unique

    # Composition and inheritance
    all_of = Column(JSON)  # allOf composition
    one_of = Column(JSON)  # oneOf composition
    any_of = Column(JSON)  # anyOf composition
    not_schema = Column(JSON)  # not schema

    # Metadata
    deprecated = Column(Boolean, default=False)
    read_only = Column(Boolean, default=False)
    write_only = Column(Boolean, default=False)
    extensions = Column(JSON)  # x-* extensions

    # Search optimization
    searchable_text = Column(Text)  # Pre-computed searchable content
    property_names = Column(JSON)  # List of property names

    # Dependency tracking
    schema_dependencies = Column(JSON)  # List of referenced schema names
    reference_count = Column(
        Integer, default=0
    )  # How many times this schema is referenced

    # Relationships
    api = relationship("APIMetadata", back_populates="schemas")
    dependencies = relationship(
        "EndpointDependency",
        back_populates="schema",
        cascade="all, delete-orphan",
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("api_id", "name", name="uq_schema_name"),
        Index("ix_schemas_api_id", "api_id"),
        Index("ix_schemas_name", "name"),
        Index("ix_schemas_type", "type"),
        Index("ix_schemas_deprecated", "deprecated"),
        Index("ix_schemas_reference_count", "reference_count"),
        Index("ix_schemas_searchable_text", "searchable_text"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "api_id": self.api_id,
            "name": self.name,
            "title": self.title,
            "type": self.type,
            "format": self.format,
            "description": self.description,
            "properties": self.properties,
            "required": self.required,
            "additional_properties": self.additional_properties,
            "items": self.items,
            "enum": self.enum,
            "example": self.example,
            "default": self.default,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "pattern": self.pattern,
            "min_items": self.min_items,
            "max_items": self.max_items,
            "unique_items": self.unique_items,
            "all_of": self.all_of,
            "one_of": self.one_of,
            "any_of": self.any_of,
            "not_schema": self.not_schema,
            "deprecated": self.deprecated,
            "read_only": self.read_only,
            "write_only": self.write_only,
            "extensions": self.extensions,
            "searchable_text": self.searchable_text,
            "property_names": self.property_names,
            "schema_dependencies": self.schema_dependencies,
            "reference_count": self.reference_count,
            "created_at": self.created_at.isoformat()
            if self.created_at
            else None,
            "updated_at": self.updated_at.isoformat()
            if self.updated_at
            else None,
        }


class SecurityScheme(Base, TimestampMixin):
    """Stores normalized security scheme definitions."""

    __tablename__ = "security_schemes"

    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, ForeignKey("api_metadata.id"), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(
        String(50), nullable=False
    )  # apiKey, http, oauth2, openIdConnect, mutualTLS
    description = Column(Text)

    # API Key specific
    api_key_name = Column(String(255))  # Parameter name
    api_key_location = Column(String(20))  # query, header, cookie

    # HTTP specific
    http_scheme = Column(String(50))  # basic, bearer, digest, etc.
    bearer_format = Column(String(100))  # JWT, etc.

    # OAuth2 specific
    oauth2_flows = Column(JSON)  # OAuth2 flow definitions

    # OpenID Connect specific
    openid_connect_url = Column(String(1000))

    # Extensions and metadata
    extensions = Column(JSON)  # x-* extensions

    # Usage tracking
    reference_count = Column(
        Integer, default=0
    )  # How many endpoints use this scheme

    # Relationships
    api = relationship("APIMetadata", back_populates="security_schemes")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("api_id", "name", name="uq_security_scheme_name"),
        Index("ix_security_schemes_api_id", "api_id"),
        Index("ix_security_schemes_name", "name"),
        Index("ix_security_schemes_type", "type"),
        Index("ix_security_schemes_reference_count", "reference_count"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "api_id": self.api_id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "api_key_name": self.api_key_name,
            "api_key_location": self.api_key_location,
            "http_scheme": self.http_scheme,
            "bearer_format": self.bearer_format,
            "oauth2_flows": self.oauth2_flows,
            "openid_connect_url": self.openid_connect_url,
            "extensions": self.extensions,
            "reference_count": self.reference_count,
            "created_at": self.created_at.isoformat()
            if self.created_at
            else None,
            "updated_at": self.updated_at.isoformat()
            if self.updated_at
            else None,
        }


class EndpointDependency(Base, TimestampMixin):
    """Tracks dependencies between endpoints and schemas."""

    __tablename__ = "endpoint_dependencies"

    id = Column(Integer, primary_key=True)
    endpoint_id = Column(Integer, ForeignKey("endpoints.id"), nullable=False)
    schema_id = Column(Integer, ForeignKey("schemas.id"), nullable=False)
    dependency_type = Column(
        String(50), nullable=False
    )  # parameter, request_body, response, etc.
    context = Column(JSON)  # Additional context about the dependency

    # Relationships
    endpoint = relationship("Endpoint", back_populates="dependencies")
    schema = relationship("Schema", back_populates="dependencies")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint(
            "endpoint_id",
            "schema_id",
            "dependency_type",
            name="uq_endpoint_schema_dep",
        ),
        Index("ix_endpoint_dependencies_endpoint_id", "endpoint_id"),
        Index("ix_endpoint_dependencies_schema_id", "schema_id"),
        Index("ix_endpoint_dependencies_type", "dependency_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "endpoint_id": self.endpoint_id,
            "schema_id": self.schema_id,
            "dependency_type": self.dependency_type,
            "context": self.context,
            "created_at": self.created_at.isoformat()
            if self.created_at
            else None,
            "updated_at": self.updated_at.isoformat()
            if self.updated_at
            else None,
        }


class DatabaseMigration(Base, TimestampMixin):
    """Tracks database schema migrations."""

    __tablename__ = "database_migrations"

    id = Column(Integer, primary_key=True)
    version = Column(String(50), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    applied_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    rollback_sql = Column(Text)  # SQL for rolling back this migration
    checksum = Column(String(64))  # SHA-256 hash of migration script

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "version": self.version,
            "name": self.name,
            "applied_at": self.applied_at.isoformat()
            if self.applied_at
            else None,
            "rollback_sql": self.rollback_sql,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat()
            if self.created_at
            else None,
            "updated_at": self.updated_at.isoformat()
            if self.updated_at
            else None,
        }


# FTS5 Virtual Table SQL (to be created separately)
ENDPOINTS_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS endpoints_fts USING fts5(
    path UNINDEXED,
    method UNINDEXED,
    operation_id,
    summary,
    description,
    tags,
    searchable_text,
    content='endpoints',
    content_rowid='id',
    tokenize='porter ascii'
);
"""

SCHEMAS_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS schemas_fts USING fts5(
    name,
    title,
    description,
    searchable_text,
    property_names,
    content='schemas',
    content_rowid='id',
    tokenize='porter ascii'
);
"""

# Triggers to keep FTS5 tables in sync
ENDPOINTS_FTS_TRIGGERS = [
    """
    CREATE TRIGGER IF NOT EXISTS endpoints_fts_insert AFTER INSERT ON endpoints
    BEGIN
        INSERT INTO endpoints_fts(rowid, path, method, operation_id, summary, description, tags, searchable_text)
        VALUES (new.id, new.path, new.method, new.operation_id, new.summary, new.description,
                json_extract(new.tags, '$'), new.searchable_text);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS endpoints_fts_delete AFTER DELETE ON endpoints
    BEGIN
        DELETE FROM endpoints_fts WHERE rowid = old.id;
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS endpoints_fts_update AFTER UPDATE ON endpoints
    BEGIN
        UPDATE endpoints_fts SET
            path = new.path,
            method = new.method,
            operation_id = new.operation_id,
            summary = new.summary,
            description = new.description,
            tags = json_extract(new.tags, '$'),
            searchable_text = new.searchable_text
        WHERE rowid = new.id;
    END;
    """,
]

SCHEMAS_FTS_TRIGGERS = [
    """
    CREATE TRIGGER IF NOT EXISTS schemas_fts_insert AFTER INSERT ON schemas
    BEGIN
        INSERT INTO schemas_fts(rowid, name, title, description, searchable_text, property_names)
        VALUES (new.id, new.name, new.title, new.description, new.searchable_text,
                json_extract(new.property_names, '$'));
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS schemas_fts_delete AFTER DELETE ON schemas
    BEGIN
        DELETE FROM schemas_fts WHERE rowid = old.id;
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS schemas_fts_update AFTER UPDATE ON schemas
    BEGIN
        UPDATE schemas_fts SET
            name = new.name,
            title = new.title,
            description = new.description,
            searchable_text = new.searchable_text,
            property_names = json_extract(new.property_names, '$')
        WHERE rowid = new.id;
    END;
    """,
]
