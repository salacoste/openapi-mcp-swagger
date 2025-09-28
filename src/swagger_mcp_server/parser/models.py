"""Normalized data models for OpenAPI/Swagger documents."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, Field, validator

from swagger_mcp_server.config.logging import get_logger

logger = get_logger(__name__)


class HttpMethod(str, Enum):
    """HTTP methods supported in OpenAPI."""

    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"
    PATCH = "patch"
    HEAD = "head"
    OPTIONS = "options"
    TRACE = "trace"


class ParameterLocation(str, Enum):
    """Parameter locations in OpenAPI."""

    QUERY = "query"
    PATH = "path"
    HEADER = "header"
    COOKIE = "cookie"


class SecurityType(str, Enum):
    """Security scheme types in OpenAPI."""

    API_KEY = "apiKey"
    HTTP = "http"
    OAUTH2 = "oauth2"
    OPEN_ID_CONNECT = "openIdConnect"
    MUTUAL_TLS = "mutualTLS"


# Alias for compatibility
SecuritySchemeType = SecurityType


class SecuritySchemeLocation(str, Enum):
    """Security scheme locations in OpenAPI."""

    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"


class SecurityFlowType(str, Enum):
    """OAuth2 flow types in OpenAPI."""

    AUTHORIZATION_CODE = "authorizationCode"
    IMPLICIT = "implicit"
    PASSWORD = "password"
    CLIENT_CREDENTIALS = "clientCredentials"


class SchemaType(str, Enum):
    """Schema types in OpenAPI."""

    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


# Pydantic Models for Normalized Data


class NormalizedParameter(BaseModel):
    """Normalized parameter model."""

    name: str = Field(..., description="Parameter name")
    location: ParameterLocation = Field(..., description="Parameter location")
    required: bool = Field(default=False, description="Whether parameter is required")
    description: Optional[str] = Field(None, description="Parameter description")
    schema_type: Optional[str] = Field(None, alias="type", description="Parameter type")
    format: Optional[str] = Field(None, description="Parameter format")
    enum: Optional[List[Any]] = Field(None, description="Allowed values")
    default: Optional[Any] = Field(None, description="Default value")
    example: Optional[Any] = Field(None, description="Example value")
    deprecated: bool = Field(
        default=False, description="Whether parameter is deprecated"
    )

    # Validation constraints
    minimum: Optional[Union[int, float]] = Field(None, description="Minimum value")
    maximum: Optional[Union[int, float]] = Field(None, description="Maximum value")
    min_length: Optional[int] = Field(None, description="Minimum string length")
    max_length: Optional[int] = Field(None, description="Maximum string length")
    pattern: Optional[str] = Field(None, description="Regex pattern")

    # Advanced schema properties
    schema_ref: Optional[str] = Field(None, description="Reference to schema component")
    items_schema: Optional[Dict[str, Any]] = Field(
        None, description="Array items schema"
    )
    additional_properties: Optional[Dict[str, Any]] = Field(
        None, description="Additional properties for objects"
    )

    # Extension properties
    extensions: Dict[str, Any] = Field(
        default_factory=dict, description="OpenAPI extensions (x-*)"
    )

    class Config:
        allow_population_by_field_name = True


class NormalizedRequestBody(BaseModel):
    """Normalized request body model."""

    description: Optional[str] = Field(None, description="Request body description")
    required: bool = Field(
        default=False, description="Whether request body is required"
    )
    content: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Content by media type"
    )

    # Extension properties
    extensions: Dict[str, Any] = Field(
        default_factory=dict, description="OpenAPI extensions (x-*)"
    )


class NormalizedResponse(BaseModel):
    """Normalized response model."""

    status_code: str = Field(..., description="HTTP status code")
    description: str = Field(..., description="Response description")
    headers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Response headers"
    )
    content: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Content by media type"
    )
    links: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Response links"
    )

    # Extension properties
    extensions: Dict[str, Any] = Field(
        default_factory=dict, description="OpenAPI extensions (x-*)"
    )


class NormalizedSecurity(BaseModel):
    """Normalized security scheme model."""

    scheme_id: str = Field(..., description="Security scheme identifier")
    type: SecurityType = Field(..., description="Security scheme type")
    description: Optional[str] = Field(None, description="Security scheme description")

    # API Key specific
    name: Optional[str] = Field(None, description="API key name")
    location: Optional[ParameterLocation] = Field(
        None, alias="in", description="API key location"
    )

    # HTTP specific
    scheme: Optional[str] = Field(None, description="HTTP authentication scheme")
    bearer_format: Optional[str] = Field(None, description="Bearer token format")

    # OAuth2 specific
    flows: Optional[Dict[str, Any]] = Field(None, description="OAuth2 flows")

    # OpenID Connect specific
    open_id_connect_url: Optional[str] = Field(None, description="OpenID Connect URL")

    # Extension properties
    extensions: Dict[str, Any] = Field(
        default_factory=dict, description="OpenAPI extensions (x-*)"
    )

    class Config:
        allow_population_by_field_name = True


class NormalizedSecurityRequirement(BaseModel):
    """Normalized security requirement model."""

    scheme_id: str = Field(..., description="Security scheme identifier")
    scopes: List[str] = Field(default_factory=list, description="Required scopes")


class NormalizedEndpoint(BaseModel):
    """Normalized endpoint model with complete operation data."""

    # Basic endpoint identification
    path: str = Field(..., description="API path")
    method: HttpMethod = Field(..., description="HTTP method")
    operation_id: Optional[str] = Field(None, description="Unique operation identifier")

    # Metadata
    summary: Optional[str] = Field(None, description="Brief operation summary")
    description: Optional[str] = Field(
        None, description="Detailed operation description"
    )
    tags: List[str] = Field(default_factory=list, description="Operation tags")
    external_docs: Optional[Dict[str, Any]] = Field(
        None, description="External documentation"
    )

    # Parameters and body
    parameters: List[NormalizedParameter] = Field(
        default_factory=list, description="Operation parameters"
    )
    request_body: Optional[NormalizedRequestBody] = Field(
        None, description="Request body"
    )

    # Responses
    responses: Dict[str, NormalizedResponse] = Field(
        default_factory=dict, description="Responses by status code"
    )

    # Security
    security: List[List[NormalizedSecurityRequirement]] = Field(
        default_factory=list, description="Security requirements"
    )

    # Callbacks and links
    callbacks: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Operation callbacks"
    )

    # Status
    deprecated: bool = Field(
        default=False, description="Whether operation is deprecated"
    )

    # Search optimization fields
    searchable_text: str = Field(default="", description="Combined searchable text")
    parameter_names: List[str] = Field(
        default_factory=list, description="All parameter names for search"
    )
    response_schemas: List[str] = Field(
        default_factory=list, description="Response schema references"
    )

    # Relationships
    schema_dependencies: Set[str] = Field(
        default_factory=set, description="Referenced schema components"
    )
    security_dependencies: Set[str] = Field(
        default_factory=set, description="Referenced security schemes"
    )

    # Extension properties
    extensions: Dict[str, Any] = Field(
        default_factory=dict, description="OpenAPI extensions (x-*)"
    )

    @validator("searchable_text", always=True)
    def generate_searchable_text(cls, v, values):
        """Generate combined searchable text from all relevant fields."""
        parts = []

        if "path" in values:
            parts.append(values["path"])
        if "method" in values:
            parts.append(values["method"])
        if "operation_id" in values and values["operation_id"]:
            parts.append(values["operation_id"])
        if "summary" in values and values["summary"]:
            parts.append(values["summary"])
        if "description" in values and values["description"]:
            parts.append(values["description"])
        if "tags" in values:
            parts.extend(values["tags"])

        return " ".join(parts)

    @validator("parameter_names", always=True)
    def extract_parameter_names(cls, v, values):
        """Extract all parameter names for search indexing."""
        if "parameters" in values:
            return [param.name for param in values["parameters"]]
        return []

    class Config:
        use_enum_values = True


class NormalizedSchema(BaseModel):
    """Normalized schema component model."""

    # Basic identification
    name: str = Field(..., description="Schema component name")
    type: Optional[str] = Field(None, description="Schema type")
    format: Optional[str] = Field(None, description="Schema format")

    # Schema definition
    title: Optional[str] = Field(None, description="Schema title")
    description: Optional[str] = Field(None, description="Schema description")
    default: Optional[Any] = Field(None, description="Default value")
    example: Optional[Any] = Field(None, description="Example value")
    examples: Optional[List[Any]] = Field(None, description="Multiple examples")

    # Object properties
    properties: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Object properties"
    )
    required: List[str] = Field(default_factory=list, description="Required properties")
    additional_properties: Optional[Union[bool, Dict[str, Any]]] = Field(
        None, description="Additional properties"
    )

    # Array properties
    items: Optional[Dict[str, Any]] = Field(None, description="Array items schema")
    min_items: Optional[int] = Field(None, description="Minimum array length")
    max_items: Optional[int] = Field(None, description="Maximum array length")
    unique_items: Optional[bool] = Field(
        None, description="Whether array items must be unique"
    )

    # String properties
    min_length: Optional[int] = Field(None, description="Minimum string length")
    max_length: Optional[int] = Field(None, description="Maximum string length")
    pattern: Optional[str] = Field(None, description="String pattern")

    # Numeric properties
    minimum: Optional[Union[int, float]] = Field(None, description="Minimum value")
    maximum: Optional[Union[int, float]] = Field(None, description="Maximum value")
    exclusive_minimum: Optional[bool] = Field(None, description="Exclusive minimum")
    exclusive_maximum: Optional[bool] = Field(None, description="Exclusive maximum")
    multiple_of: Optional[Union[int, float]] = Field(
        None, description="Multiple of value"
    )

    # Enumeration
    enum: Optional[List[Any]] = Field(None, description="Enumeration values")
    const: Optional[Any] = Field(None, description="Constant value")

    # Composition
    all_of: Optional[List[Dict[str, Any]]] = Field(None, description="All of schemas")
    one_of: Optional[List[Dict[str, Any]]] = Field(None, description="One of schemas")
    any_of: Optional[List[Dict[str, Any]]] = Field(None, description="Any of schemas")
    not_schema: Optional[Dict[str, Any]] = Field(
        None, alias="not", description="Not schema"
    )

    # Conditional
    if_schema: Optional[Dict[str, Any]] = Field(
        None, alias="if", description="If schema"
    )
    then_schema: Optional[Dict[str, Any]] = Field(
        None, alias="then", description="Then schema"
    )
    else_schema: Optional[Dict[str, Any]] = Field(
        None, alias="else", description="Else schema"
    )

    # Metadata
    read_only: Optional[bool] = Field(None, description="Read-only property")
    write_only: Optional[bool] = Field(None, description="Write-only property")
    deprecated: bool = Field(default=False, description="Whether schema is deprecated")

    # OpenAPI specific
    discriminator: Optional[Dict[str, Any]] = Field(
        None, description="Discriminator object"
    )
    xml: Optional[Dict[str, Any]] = Field(None, description="XML metadata")
    external_docs: Optional[Dict[str, Any]] = Field(
        None, description="External documentation"
    )

    # Relationships and dependencies
    dependencies: Set[str] = Field(
        default_factory=set, description="Schema dependencies ($ref)"
    )
    used_by: Set[str] = Field(
        default_factory=set, description="Endpoints using this schema"
    )

    # Search optimization
    searchable_text: str = Field(default="", description="Combined searchable text")
    property_names: List[str] = Field(
        default_factory=list, description="Property names for search"
    )

    # Extension properties
    extensions: Dict[str, Any] = Field(
        default_factory=dict, description="OpenAPI extensions (x-*)"
    )

    @validator("searchable_text", always=True)
    def generate_searchable_text(cls, v, values):
        """Generate combined searchable text from schema fields."""
        parts = []

        if "name" in values:
            parts.append(values["name"])
        if "title" in values and values["title"]:
            parts.append(values["title"])
        if "description" in values and values["description"]:
            parts.append(values["description"])
        if "type" in values and values["type"]:
            parts.append(values["type"])
        if "format" in values and values["format"]:
            parts.append(values["format"])

        return " ".join(parts)

    @validator("property_names", always=True)
    def extract_property_names(cls, v, values):
        """Extract property names for search indexing."""
        if "properties" in values:
            return list(values["properties"].keys())
        return []

    class Config:
        allow_population_by_field_name = True


class NormalizedAPI(BaseModel):
    """Complete normalized OpenAPI document."""

    # Document metadata
    openapi_version: str = Field(..., description="OpenAPI specification version")
    title: str = Field(..., description="API title")
    version: str = Field(..., description="API version")
    description: Optional[str] = Field(None, description="API description")

    # Contact and license
    contact: Optional[Dict[str, Any]] = Field(None, description="Contact information")
    license: Optional[Dict[str, Any]] = Field(None, description="License information")
    terms_of_service: Optional[str] = Field(None, description="Terms of service URL")

    # Servers
    servers: List[Dict[str, Any]] = Field(
        default_factory=list, description="Server information"
    )

    # Core components
    endpoints: List[NormalizedEndpoint] = Field(
        default_factory=list, description="All API endpoints"
    )
    schemas: Dict[str, NormalizedSchema] = Field(
        default_factory=dict, description="Schema components"
    )
    security_schemes: Dict[str, NormalizedSecurity] = Field(
        default_factory=dict, description="Security schemes"
    )

    # Additional components
    responses: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Reusable responses"
    )
    parameters: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Reusable parameters"
    )
    examples: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Reusable examples"
    )
    request_bodies: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Reusable request bodies"
    )
    headers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Reusable headers"
    )
    links: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Reusable links"
    )
    callbacks: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Reusable callbacks"
    )

    # Global security
    security: List[List[NormalizedSecurityRequirement]] = Field(
        default_factory=list, description="Global security requirements"
    )

    # Tags
    tags: List[Dict[str, Any]] = Field(
        default_factory=list, description="Tag definitions"
    )
    external_docs: Optional[Dict[str, Any]] = Field(
        None, description="External documentation"
    )

    # Processing metadata
    normalized_at: datetime = Field(
        default_factory=datetime.now, description="Normalization timestamp"
    )
    source_file: Optional[str] = Field(None, description="Source file path")

    # Statistics
    endpoint_count: int = Field(default=0, description="Total number of endpoints")
    schema_count: int = Field(default=0, description="Total number of schemas")
    security_scheme_count: int = Field(
        default=0, description="Total number of security schemes"
    )
    extension_count: int = Field(default=0, description="Total number of extensions")

    # Relationships
    dependency_graph: Dict[str, Set[str]] = Field(
        default_factory=dict, description="Component dependency graph"
    )
    reverse_dependencies: Dict[str, Set[str]] = Field(
        default_factory=dict, description="Reverse dependency mapping"
    )

    # Search optimization
    all_searchable_text: str = Field(
        default="", description="Combined searchable text for API"
    )
    endpoint_tags: Set[str] = Field(
        default_factory=set, description="All unique endpoint tags"
    )

    # Extension properties
    extensions: Dict[str, Any] = Field(
        default_factory=dict, description="Root-level OpenAPI extensions (x-*)"
    )

    @validator("endpoint_count", always=True)
    def calculate_endpoint_count(cls, v, values):
        """Calculate endpoint count from endpoints list."""
        if "endpoints" in values:
            return len(values["endpoints"])
        return 0

    @validator("schema_count", always=True)
    def calculate_schema_count(cls, v, values):
        """Calculate schema count from schemas dict."""
        if "schemas" in values:
            return len(values["schemas"])
        return 0

    @validator("security_scheme_count", always=True)
    def calculate_security_scheme_count(cls, v, values):
        """Calculate security scheme count."""
        if "security_schemes" in values:
            return len(values["security_schemes"])
        return 0

    @validator("endpoint_tags", always=True)
    def extract_endpoint_tags(cls, v, values):
        """Extract all unique tags from endpoints."""
        tags = set()
        if "endpoints" in values:
            for endpoint in values["endpoints"]:
                tags.update(endpoint.tags)
        return tags

    @validator("all_searchable_text", always=True)
    def generate_all_searchable_text(cls, v, values):
        """Generate combined searchable text for entire API."""
        parts = []

        if "title" in values:
            parts.append(values["title"])
        if "description" in values and values["description"]:
            parts.append(values["description"])
        if "endpoints" in values:
            for endpoint in values["endpoints"]:
                parts.append(endpoint.searchable_text)
        if "schemas" in values:
            for schema in values["schemas"].values():
                parts.append(schema.searchable_text)

        return " ".join(parts)


# Utility dataclasses for processing


class NormalizedSecurityFlow(BaseModel):
    """Normalized OAuth2 flow."""

    type: SecurityFlowType = Field(..., description="Flow type")
    authorization_url: Optional[str] = Field(None, description="Authorization URL")
    token_url: Optional[str] = Field(None, description="Token URL")
    refresh_url: Optional[str] = Field(None, description="Refresh URL")
    scopes: Dict[str, str] = Field(default_factory=dict, description="Available scopes")

    class Config:
        allow_population_by_field_name = True


class NormalizedSecurityScheme(BaseModel):
    """Normalized security scheme."""

    name: str = Field(..., description="Security scheme name")
    type: SecuritySchemeType = Field(..., description="Security scheme type")
    description: Optional[str] = Field(None, description="Security scheme description")

    # API Key specific
    api_key_name: Optional[str] = Field(None, description="API key parameter name")
    api_key_location: Optional[SecuritySchemeLocation] = Field(
        None, description="API key location"
    )

    # HTTP specific
    http_scheme: Optional[str] = Field(None, description="HTTP authentication scheme")
    bearer_format: Optional[str] = Field(None, description="Bearer token format")

    # OAuth2 specific
    oauth2_flows: Dict[SecurityFlowType, NormalizedSecurityFlow] = Field(
        default_factory=dict, description="OAuth2 flows"
    )

    # OpenID Connect specific
    openid_connect_url: Optional[str] = Field(
        None, description="OpenID Connect discovery URL"
    )

    # Extensions
    extensions: Dict[str, Any] = Field(
        default_factory=dict, description="Security scheme extensions"
    )

    class Config:
        allow_population_by_field_name = True


@dataclass
class NormalizationMetrics:
    """Metrics collected during normalization process."""

    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    # Input statistics
    raw_endpoints_processed: int = 0
    raw_schemas_processed: int = 0
    raw_security_schemes_processed: int = 0

    # Output statistics
    normalized_endpoints: int = 0
    normalized_schemas: int = 0
    normalized_security_schemes: int = 0

    # Processing details
    references_resolved: int = 0
    circular_references_detected: int = 0
    extensions_preserved: int = 0
    validation_errors: int = 0
    validation_warnings: int = 0

    # Performance metrics
    processing_duration_ms: float = 0.0
    memory_peak_mb: float = 0.0

    @property
    def duration_ms(self) -> float:
        """Calculate processing duration in milliseconds."""
        if self.end_time is None:
            return (datetime.now() - self.start_time).total_seconds() * 1000
        return (self.end_time - self.start_time).total_seconds() * 1000


@dataclass
class NormalizationResult:
    """Result of normalization operation."""

    success: bool
    normalized_api: Optional[NormalizedAPI]
    metrics: NormalizationMetrics = field(default_factory=NormalizationMetrics)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
