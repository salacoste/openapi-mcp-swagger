"""MCP server implementation for Swagger API documentation access.

Updated implementation using the correct MCP SDK v1.15 API structure.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.config.settings import Settings
from swagger_mcp_server.storage.database import DatabaseConfig, DatabaseManager
from swagger_mcp_server.storage.repositories import (
    EndpointRepository,
    MetadataRepository,
    SchemaRepository,
)

from .exceptions import (
    CodeGenerationError,
    DatabaseConnectionError,
    ErrorLogger,
    MCPServerError,
    ResourceNotFoundError,
    SchemaResolutionError,
    ValidationError,
    create_mcp_error_response,
    sanitize_error_data,
)
from .health import HealthChecker
from .monitoring import (
    MetricsCollector,
    PerformanceMonitor,
    PerformanceThresholds,
    global_monitor,
    monitor_performance,
)
from .resilience import (
    connection_pool,
    database_circuit_breaker,
    health_checker,
    retry_on_failure,
    with_circuit_breaker,
    with_timeout,
)

logger = get_logger(__name__)


class SwaggerMcpServer:
    """MCP server implementation for Swagger API documentation access."""

    def __init__(self, settings: Settings):
        """Initialize the MCP server.

        Args:
            settings: Application settings containing server configuration
        """
        self.settings = settings
        self.logger = get_logger(__name__)
        self.error_logger = ErrorLogger(self.logger)

        # Initialize performance monitoring
        self.performance_monitor = global_monitor
        self.health_checker = HealthChecker(self.performance_monitor)
        self.metrics_collector: Optional[MetricsCollector] = None

        # Initialize database
        db_config = DatabaseConfig(
            database_path=str(settings.get_database_path()),
            max_connections=settings.database.pool_size,
            connection_timeout=settings.database.timeout,
        )
        self.db_manager = DatabaseManager(db_config)

        # Initialize repositories
        self.endpoint_repo: Optional[EndpointRepository] = None
        self.schema_repo: Optional[SchemaRepository] = None
        self.metadata_repo: Optional[MetadataRepository] = None

        # Create MCP server
        self.server = Server(settings.server.name)

        # Register handlers
        self._register_handlers()

        self.logger.info(
            "MCP server initialized",
            name=settings.server.name,
            version=settings.server.version,
            database_path=str(settings.get_database_path()),
        )

    async def initialize(self) -> None:
        """Initialize the server and database connections."""
        try:
            self.logger.info("Initializing MCP server components")

            # Initialize database
            await self.db_manager.initialize()

            # Initialize repositories
            self.endpoint_repo = EndpointRepository(self.db_manager)
            self.schema_repo = SchemaRepository(self.db_manager)
            self.metadata_repo = MetadataRepository(self.db_manager)

            # Start performance monitoring
            await self.start_monitoring()

            self.logger.info(
                "MCP server initialization completed successfully"
            )

        except Exception as e:
            self.logger.error("Failed to initialize MCP server", error=str(e))
            raise

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def list_tools() -> List[types.Tool]:
            """List available tools/methods."""
            return [
                types.Tool(
                    name="searchEndpoints",
                    description="Search API endpoints by keywords and HTTP method filters with intelligent discovery capabilities",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "string",
                                "description": "Search keywords for paths, descriptions, and parameter names",
                                "maxLength": 500,
                                "minLength": 1,
                            },
                            "httpMethods": {
                                "type": "array",
                                "description": "Optional array of HTTP methods to filter by",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "GET",
                                        "POST",
                                        "PUT",
                                        "DELETE",
                                        "PATCH",
                                        "HEAD",
                                        "OPTIONS",
                                    ],
                                },
                                "uniqueItems": True,
                            },
                            "page": {
                                "type": "integer",
                                "description": "Page number for pagination (1-based)",
                                "default": 1,
                                "minimum": 1,
                            },
                            "perPage": {
                                "type": "integer",
                                "description": "Results per page (max 50)",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 50,
                            },
                        },
                        "required": ["keywords"],
                    },
                ),
                types.Tool(
                    name="getSchema",
                    description="Retrieve complete schema definitions with automatic dependency resolution and circular reference handling",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "componentName": {
                                "type": "string",
                                "description": "OpenAPI component name (e.g., 'User' or '#/components/schemas/User')",
                                "minLength": 1,
                                "maxLength": 255,
                            },
                            "resolveDependencies": {
                                "type": "boolean",
                                "description": "Automatically resolve all $ref dependencies",
                                "default": True,
                            },
                            "maxDepth": {
                                "type": "integer",
                                "description": "Maximum dependency resolution depth (1-10)",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 10,
                            },
                            "includeExamples": {
                                "type": "boolean",
                                "description": "Include example values and default values in schema",
                                "default": True,
                            },
                            "includeExtensions": {
                                "type": "boolean",
                                "description": "Include OpenAPI extensions (x-* properties)",
                                "default": True,
                            },
                        },
                        "required": ["componentName"],
                    },
                ),
                types.Tool(
                    name="getExample",
                    description="Generate working code examples for API endpoints in multiple programming languages with authentication and error handling",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "endpoint": {
                                "type": "string",
                                "description": "API endpoint path (e.g., '/api/v1/users/{id}') or endpoint ID",
                                "minLength": 1,
                                "maxLength": 500,
                            },
                            "format": {
                                "type": "string",
                                "description": "Code format for the example",
                                "enum": ["curl", "javascript", "python"],
                                "default": "curl",
                            },
                            "method": {
                                "type": "string",
                                "description": "HTTP method (required if endpoint is a path)",
                                "enum": [
                                    "GET",
                                    "POST",
                                    "PUT",
                                    "DELETE",
                                    "PATCH",
                                    "HEAD",
                                    "OPTIONS",
                                ],
                            },
                            "includeAuth": {
                                "type": "boolean",
                                "description": "Include authentication patterns in generated code",
                                "default": True,
                            },
                            "baseUrl": {
                                "type": "string",
                                "description": "Base URL for the API (optional, uses example URL if not provided)",
                                "format": "uri",
                            },
                        },
                        "required": ["endpoint", "format"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[types.TextContent]:
            """Handle tool calls from AI agents with comprehensive error handling."""
            request_id = str(uuid.uuid4())

            try:
                # Validate method name
                if name not in ["searchEndpoints", "getSchema", "getExample"]:
                    error = ValidationError(
                        parameter="method",
                        message=f"Unknown method '{name}'",
                        value=name,
                        suggestions=[
                            "searchEndpoints",
                            "getSchema",
                            "getExample",
                        ],
                    )
                    self.error_logger.log_error(error, request_id=request_id)
                    error_response = create_mcp_error_response(
                        error, request_id
                    )
                    return [
                        types.TextContent(
                            type="text", text=str(error_response)
                        )
                    ]

                # Sanitize arguments for logging
                safe_arguments = sanitize_error_data(arguments)

                self.logger.info(
                    f"Processing {name} request",
                    extra={
                        "request_id": request_id,
                        "method": name,
                        "arguments": safe_arguments,
                    },
                )

                # Execute method with timeout and circuit breaker protection
                if name == "searchEndpoints":
                    result = await self._search_endpoints_with_resilience(
                        arguments, request_id
                    )
                elif name == "getSchema":
                    result = await self._get_schema_with_resilience(
                        arguments, request_id
                    )
                elif name == "getExample":
                    result = await self._get_example_with_resilience(
                        arguments, request_id
                    )

                # Log successful completion
                self.logger.info(
                    f"{name} request completed successfully",
                    extra={"request_id": request_id, "method": name},
                )

                return [types.TextContent(type="text", text=str(result))]

            except MCPServerError as e:
                # Log structured MCP server error
                self.error_logger.log_error(
                    e,
                    context={
                        "method": name,
                        "arguments": sanitize_error_data(arguments),
                    },
                    request_id=request_id,
                )
                error_response = create_mcp_error_response(e, request_id)
                return [
                    types.TextContent(type="text", text=str(error_response))
                ]

            except Exception as e:
                # Log unexpected error
                self.error_logger.log_operation_error(
                    operation=f"call_tool_{name}",
                    error=e,
                    context={
                        "method": name,
                        "arguments": sanitize_error_data(arguments),
                    },
                    request_id=request_id,
                )

                # Convert to generic MCP server error
                server_error = MCPServerError(
                    code=-32603,
                    message="Internal server error",
                    data={
                        "error_type": "internal_error",
                        "request_id": request_id,
                    },
                )
                error_response = create_mcp_error_response(
                    server_error, request_id
                )
                return [
                    types.TextContent(type="text", text=str(error_response))
                ]

        @self.server.list_resources()
        async def list_resources() -> List[types.Resource]:
            """List available resources."""
            return [
                types.Resource(
                    uri="swagger://api-info",
                    name="API Information",
                    description="General information about the loaded API",
                ),
                types.Resource(
                    uri="swagger://health",
                    name="Server Health",
                    description="Server and database health status",
                ),
            ]

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read resource content."""
            try:
                if uri == "swagger://api-info":
                    return await self._get_api_info()
                elif uri == "swagger://health":
                    return await self._get_health_status()
                else:
                    raise ValueError(f"Unknown resource: {uri}")

            except Exception as e:
                self.logger.error(
                    "Resource read failed", uri=uri, error=str(e)
                )
                return f"Error reading resource: {str(e)}"

    # Resilient wrapper methods with timeout and circuit breaker protection

    @monitor_performance("searchEndpoints", global_monitor)
    @with_timeout(30.0)
    @with_circuit_breaker(database_circuit_breaker)
    @retry_on_failure(max_retries=3)
    async def _search_endpoints_with_resilience(
        self, arguments: Dict[str, Any], request_id: str
    ) -> Dict[str, Any]:
        """Resilient wrapper for searchEndpoints with error handling and monitoring."""
        try:
            return await self._search_endpoints(**arguments)
        except Exception as e:
            # Convert to appropriate MCP error
            if "not properly initialized" in str(e):
                raise DatabaseConnectionError(
                    "Server not properly initialized", "initialization"
                )
            elif "not found" in str(e).lower():
                raise ResourceNotFoundError(
                    "endpoint", arguments.get("keywords", "unknown")
                )
            else:
                raise DatabaseConnectionError(
                    f"Search operation failed: {str(e)}", "search"
                )

    @monitor_performance("getSchema", global_monitor)
    @with_timeout(30.0)
    @with_circuit_breaker(database_circuit_breaker)
    @retry_on_failure(max_retries=3)
    async def _get_schema_with_resilience(
        self, arguments: Dict[str, Any], request_id: str
    ) -> Dict[str, Any]:
        """Resilient wrapper for getSchema with error handling and monitoring."""
        try:
            return await self._get_schema(**arguments)
        except Exception as e:
            # Convert to appropriate MCP error
            if "not properly initialized" in str(e):
                raise DatabaseConnectionError(
                    "Server not properly initialized", "initialization"
                )
            elif "not found" in str(e).lower():
                component_name = arguments.get("componentName", "unknown")
                raise ResourceNotFoundError("schema", component_name)
            elif "circular" in str(e).lower():
                component_name = arguments.get("componentName", "unknown")
                raise SchemaResolutionError(
                    component_name, "Circular reference detected"
                )
            else:
                raise DatabaseConnectionError(
                    f"Schema operation failed: {str(e)}", "schema_resolution"
                )

    @monitor_performance("getExample", global_monitor)
    @with_timeout(30.0)
    @with_circuit_breaker(database_circuit_breaker)
    @retry_on_failure(max_retries=2)  # Fewer retries for code generation
    async def _get_example_with_resilience(
        self, arguments: Dict[str, Any], request_id: str
    ) -> Dict[str, Any]:
        """Resilient wrapper for getExample with error handling and monitoring."""
        try:
            return await self._get_example(**arguments)
        except Exception as e:
            # Convert to appropriate MCP error
            if "not properly initialized" in str(e):
                raise DatabaseConnectionError(
                    "Server not properly initialized", "initialization"
                )
            elif "not found" in str(e).lower():
                endpoint = arguments.get("endpoint", "unknown")
                raise ResourceNotFoundError("endpoint", endpoint)
            elif "Unsupported format" in str(e):
                format_type = arguments.get("format", "unknown")
                raise ValidationError(
                    "format",
                    f"Unsupported format '{format_type}'",
                    format_type,
                    ["curl", "javascript", "python"],
                )
            elif "generation failed" in str(e).lower():
                endpoint = arguments.get("endpoint", "unknown")
                format_type = arguments.get("format", "unknown")
                raise CodeGenerationError(format_type, endpoint, str(e))
            else:
                raise DatabaseConnectionError(
                    f"Example generation failed: {str(e)}",
                    "example_generation",
                )

    # Original method implementations with enhanced error handling

    async def _search_endpoints(
        self,
        keywords: str,
        httpMethods: Optional[List[str]] = None,
        page: int = 1,
        perPage: int = 20,
    ) -> Dict[str, Any]:
        """Search for API endpoints with enhanced functionality per Story 2.2.

        Args:
            keywords: Search keywords for paths, descriptions, and parameter names (max 500 chars)
            httpMethods: Optional list of HTTP methods to filter by
            page: Page number for pagination (1-based)
            perPage: Results per page (max 50)

        Returns:
            Dict with results, pagination metadata, and search statistics
        """
        if not self.endpoint_repo:
            raise DatabaseConnectionError(
                "Server not properly initialized", "initialization"
            )

        try:
            # Enhanced parameter validation per Story 2.5 requirements
            if not keywords or len(keywords.strip()) == 0:
                raise ValidationError(
                    "keywords",
                    "Keywords parameter is required and cannot be empty",
                )

            if len(keywords) > 500:
                raise ValidationError(
                    "keywords",
                    f"Keywords parameter cannot exceed 500 characters (got {len(keywords)})",
                )

            # Validate HTTP methods
            valid_methods = {
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "PATCH",
                "HEAD",
                "OPTIONS",
            }
            if httpMethods:
                invalid_methods = [
                    m for m in httpMethods if m not in valid_methods
                ]
                if invalid_methods:
                    raise ValidationError(
                        "httpMethods",
                        f"Invalid HTTP methods: {', '.join(invalid_methods)}",
                        invalid_methods,
                        list(valid_methods),
                    )

            # Validate pagination parameters
            if page < 1:
                raise ValidationError(
                    "page", "Page number must be 1 or greater", page
                )
            if perPage < 1 or perPage > 50:
                raise ValidationError(
                    "perPage", "perPage must be between 1 and 50", perPage
                )

            self.logger.info(
                "Enhanced endpoint search",
                keywords=keywords,
                httpMethods=httpMethods,
                page=page,
                perPage=perPage,
            )

            # Calculate offset for pagination
            offset = (page - 1) * perPage

            # Try enhanced repository search with pagination first
            if hasattr(self.endpoint_repo, "search_endpoints_paginated"):
                search_result = (
                    await self.endpoint_repo.search_endpoints_paginated(
                        query=keywords.strip(),
                        methods=httpMethods,
                        limit=perPage,
                        offset=offset,
                    )
                )
                paginated_endpoints = search_result.get("endpoints", [])
                total_count = search_result.get("total_count", 0)
            else:
                # Fall back to basic search with simulated pagination
                endpoints = await self.endpoint_repo.search_endpoints(
                    query=keywords.strip(),
                    methods=httpMethods,
                    limit=perPage
                    * 5,  # Get more results to simulate total count better
                )

                # Simulate pagination
                total_count = len(endpoints)
                start_idx = offset
                end_idx = offset + perPage
                paginated_endpoints = endpoints[start_idx:end_idx]

            # Enhanced result formatting per Story 2.2
            results = []
            for endpoint in paginated_endpoints:
                # Parse parameters to provide detailed metadata
                parameters_info = self._parse_endpoint_parameters(
                    endpoint.parameters
                )

                result = {
                    "endpoint_id": str(endpoint.id),
                    "path": endpoint.path,
                    "method": endpoint.method,
                    "summary": endpoint.summary or "No summary available",
                    "description": endpoint.description
                    or "No description available",
                    "operationId": endpoint.operation_id,
                    "tags": endpoint.tags or [],
                    "parameters": parameters_info,
                    "authentication": self._get_endpoint_auth_info(endpoint),
                    "deprecated": getattr(endpoint, "deprecated", False),
                }
                results.append(result)

            # Calculate pagination metadata
            total_pages = (total_count + perPage - 1) // perPage
            has_next = page < total_pages
            has_prev = page > 1

            response = {
                "results": results,
                "pagination": {
                    "total": total_count,
                    "page": page,
                    "per_page": perPage,
                    "total_pages": total_pages,
                    "has_more": has_next,
                    "has_previous": has_prev,
                },
                "search_metadata": {
                    "keywords": keywords,
                    "http_methods_filter": httpMethods,
                    "result_count": len(results),
                    "search_time_ms": 0,  # Will be populated if we add timing
                },
            }

            self.logger.info(
                "Endpoint search completed",
                keywords=keywords,
                total_results=total_count,
                page_results=len(results),
                page=page,
            )

            return response

        except Exception as e:
            self.logger.error(
                "Enhanced endpoint search failed",
                keywords=keywords,
                httpMethods=httpMethods,
                error=str(e),
            )
            return {"error": f"Search failed: {str(e)}"}

    def _parse_endpoint_parameters(
        self, parameters_data: Any
    ) -> Dict[str, Any]:
        """Parse endpoint parameters to provide structured metadata."""
        if not parameters_data:
            return {
                "path": [],
                "query": [],
                "header": [],
                "body": None,
                "required": [],
            }

        try:
            if isinstance(parameters_data, list):
                path_params = []
                query_params = []
                header_params = []
                required_params = []

                for param in parameters_data:
                    if isinstance(param, dict):
                        param_name = param.get("name", "")
                        param_in = param.get("in", "")
                        param_required = param.get("required", False)

                        if param_required and param_name:
                            required_params.append(param_name)

                        if param_in == "path" and param_name:
                            path_params.append(param_name)
                        elif param_in == "query" and param_name:
                            query_params.append(param_name)
                        elif param_in == "header" and param_name:
                            header_params.append(param_name)

                return {
                    "path": path_params,
                    "query": query_params,
                    "header": header_params,
                    "body": None,  # Request body info would need separate handling
                    "required": required_params,
                }

            return {
                "path": [],
                "query": [],
                "header": [],
                "body": None,
                "required": [],
            }

        except Exception as e:
            self.logger.warning(f"Failed to parse endpoint parameters: {e}")
            return {
                "path": [],
                "query": [],
                "header": [],
                "body": None,
                "required": [],
            }

    def _get_endpoint_auth_info(self, endpoint) -> Optional[str]:
        """Extract authentication information from endpoint."""
        try:
            if hasattr(endpoint, "security") and endpoint.security:
                # Parse security requirements
                if isinstance(endpoint.security, list) and endpoint.security:
                    # Return the first security requirement type
                    first_security = endpoint.security[0]
                    if isinstance(first_security, dict) and first_security:
                        return list(first_security.keys())[0]
                elif isinstance(endpoint.security, dict) and endpoint.security:
                    return list(endpoint.security.keys())[0]

            return None
        except Exception:
            return None

    async def _get_schema(
        self,
        componentName: str,
        resolveDependencies: bool = True,
        maxDepth: int = 5,
        includeExamples: bool = True,
        includeExtensions: bool = True,
    ) -> Dict[str, Any]:
        """Get complete schema definition with dependency resolution per Story 2.3.

        Args:
            componentName: OpenAPI component name (e.g., 'User' or '#/components/schemas/User')
            resolveDependencies: Automatically resolve all $ref dependencies
            maxDepth: Maximum dependency resolution depth (1-10)
            includeExamples: Include example values and default values
            includeExtensions: Include OpenAPI extensions (x-* properties)

        Returns:
            Dict with complete schema definition, dependencies, and metadata
        """
        if not self.schema_repo:
            return {"error": "Server not properly initialized"}

        try:
            # Parameter validation per Story 2.3 requirements
            if not componentName or len(componentName.strip()) == 0:
                return {
                    "error": "componentName parameter is required and cannot be empty"
                }

            if len(componentName) > 255:
                return {
                    "error": "componentName parameter cannot exceed 255 characters"
                }

            if maxDepth < 1 or maxDepth > 10:
                return {"error": "maxDepth parameter must be between 1 and 10"}

            # Normalize component name (handle both "User" and "#/components/schemas/User" formats)
            normalized_name = self._normalize_component_name(componentName)

            self.logger.info(
                "Enhanced schema retrieval",
                componentName=componentName,
                normalized_name=normalized_name,
                resolveDependencies=resolveDependencies,
                maxDepth=maxDepth,
                includeExamples=includeExamples,
                includeExtensions=includeExtensions,
            )

            # Initialize resolution context
            resolution_context = {
                "visited_schemas": set(),  # For circular reference detection
                "resolution_stack": [],  # Current resolution path
                "resolved_cache": {},  # Cache for resolved schemas within this request
                "circular_refs": [],  # Detected circular references
                "max_depth": maxDepth,
                "current_depth": 0,
            }

            # Get base schema from repository
            base_schema = await self._resolve_single_schema(
                normalized_name,
                resolution_context,
                includeExamples,
                includeExtensions,
            )

            if not base_schema:
                return {"error": f"Schema not found: {componentName}"}

            # Resolve dependencies if requested
            if resolveDependencies:
                resolved_schema = await self._resolve_schema_dependencies(
                    base_schema,
                    resolution_context,
                    includeExamples,
                    includeExtensions,
                )
            else:
                resolved_schema = base_schema

            # Build enhanced response per Story 2.3
            response = {
                "schema": resolved_schema,
                "dependencies": list(
                    resolution_context["resolved_cache"].values()
                ),
                "metadata": {
                    "component_name": componentName,
                    "normalized_name": normalized_name,
                    "resolution_depth": resolution_context["current_depth"],
                    "total_dependencies": len(
                        resolution_context["resolved_cache"]
                    ),
                    "circular_references": resolution_context["circular_refs"],
                    "max_depth_reached": resolution_context["current_depth"]
                    >= maxDepth,
                    "resolution_settings": {
                        "resolve_dependencies": resolveDependencies,
                        "max_depth": maxDepth,
                        "include_examples": includeExamples,
                        "include_extensions": includeExtensions,
                    },
                },
            }

            self.logger.info(
                "Schema retrieval completed",
                componentName=componentName,
                dependencies_resolved=len(
                    resolution_context["resolved_cache"]
                ),
                circular_refs=len(resolution_context["circular_refs"]),
                final_depth=resolution_context["current_depth"],
            )

            return response

        except Exception as e:
            self.logger.error(
                "Enhanced schema retrieval failed",
                componentName=componentName,
                error=str(e),
            )
            return {"error": f"Schema retrieval failed: {str(e)}"}

    def _normalize_component_name(self, component_name: str) -> str:
        """Normalize component name to handle various formats."""
        name = component_name.strip()

        # Handle full reference paths like "#/components/schemas/User"
        if name.startswith("#/components/schemas/"):
            return name.split("/")[-1]
        elif name.startswith("#/definitions/"):
            return name.split("/")[-1]
        elif name.startswith("components/schemas/"):
            return name.split("/")[-1]
        elif name.startswith("definitions/"):
            return name.split("/")[-1]

        # Return as-is for simple names like "User"
        return name

    async def _resolve_single_schema(
        self,
        schema_name: str,
        resolution_context: Dict[str, Any],
        include_examples: bool,
        include_extensions: bool,
    ) -> Optional[Dict[str, Any]]:
        """Resolve a single schema from the database."""
        try:
            # Check cache first
            if schema_name in resolution_context["resolved_cache"]:
                return resolution_context["resolved_cache"][schema_name]

            # Get schema from repository
            schema = await self.schema_repo.get_schema_by_name(schema_name)

            if not schema:
                return None

            # Build schema definition
            schema_def = {
                "name": schema.name,
                "type": schema.type,
                "description": schema.description,
                "properties": schema.properties or {},
                "required": schema.required or [],
            }

            # Add optional fields
            if hasattr(schema, "format") and schema.format:
                schema_def["format"] = schema.format

            if hasattr(schema, "enum") and schema.enum:
                schema_def["enum"] = schema.enum

            if hasattr(schema, "items") and schema.items:
                schema_def["items"] = schema.items

            if (
                hasattr(schema, "additional_properties")
                and schema.additional_properties
            ):
                schema_def[
                    "additionalProperties"
                ] = schema.additional_properties

            # Include examples if requested
            if (
                include_examples
                and hasattr(schema, "example")
                and schema.example
            ):
                schema_def["example"] = schema.example

            # Include extensions if requested
            if (
                include_extensions
                and hasattr(schema, "extensions")
                and schema.extensions
            ):
                # Add x-* properties from extensions
                if isinstance(schema.extensions, dict):
                    for key, value in schema.extensions.items():
                        if key.startswith("x-"):
                            schema_def[key] = value

            # Cache the resolved schema
            resolution_context["resolved_cache"][schema_name] = schema_def

            return schema_def

        except Exception as e:
            self.logger.warning(
                f"Failed to resolve schema '{schema_name}': {e}"
            )
            return None

    async def _resolve_schema_dependencies(
        self,
        schema: Dict[str, Any],
        resolution_context: Dict[str, Any],
        include_examples: bool,
        include_extensions: bool,
    ) -> Dict[str, Any]:
        """Recursively resolve schema dependencies with circular reference detection."""
        if (
            resolution_context["current_depth"]
            >= resolution_context["max_depth"]
        ):
            self.logger.warning(
                f"Maximum resolution depth ({resolution_context['max_depth']}) reached"
            )
            return schema

        schema_name = schema.get("name", "unknown")

        # Circular reference detection
        if schema_name in resolution_context["resolution_stack"]:
            circular_path = " -> ".join(
                resolution_context["resolution_stack"] + [schema_name]
            )
            self.logger.warning(
                f"Circular reference detected: {circular_path}"
            )
            resolution_context["circular_refs"].append(circular_path)
            return schema  # Return schema without further resolution

        # Add to resolution stack
        resolution_context["resolution_stack"].append(schema_name)
        resolution_context["current_depth"] += 1

        try:
            resolved_schema = schema.copy()

            # Resolve properties
            if "properties" in schema and isinstance(
                schema["properties"], dict
            ):
                resolved_properties = {}
                for prop_name, prop_def in schema["properties"].items():
                    resolved_properties[
                        prop_name
                    ] = await self._resolve_property_references(
                        prop_def,
                        resolution_context,
                        include_examples,
                        include_extensions,
                    )
                resolved_schema["properties"] = resolved_properties

            # Resolve array items
            if "items" in schema and isinstance(schema["items"], dict):
                resolved_schema[
                    "items"
                ] = await self._resolve_property_references(
                    schema["items"],
                    resolution_context,
                    include_examples,
                    include_extensions,
                )

            # Resolve allOf, oneOf, anyOf compositions
            for composition_key in ["allOf", "oneOf", "anyOf"]:
                if composition_key in schema and isinstance(
                    schema[composition_key], list
                ):
                    resolved_compositions = []
                    for composition_schema in schema[composition_key]:
                        resolved_composition = (
                            await self._resolve_property_references(
                                composition_schema,
                                resolution_context,
                                include_examples,
                                include_extensions,
                            )
                        )
                        resolved_compositions.append(resolved_composition)
                    resolved_schema[composition_key] = resolved_compositions

            return resolved_schema

        finally:
            # Remove from resolution stack
            resolution_context["resolution_stack"].pop()
            resolution_context["current_depth"] -= 1

    async def _resolve_property_references(
        self,
        property_def: Any,
        resolution_context: Dict[str, Any],
        include_examples: bool,
        include_extensions: bool,
    ) -> Any:
        """Resolve $ref references in property definitions."""
        if not isinstance(property_def, dict):
            return property_def

        # Handle $ref references
        if "$ref" in property_def:
            ref_path = property_def["$ref"]
            ref_name = self._extract_ref_name(ref_path)

            if ref_name:
                # Try to resolve the referenced schema
                referenced_schema = await self._resolve_single_schema(
                    ref_name,
                    resolution_context,
                    include_examples,
                    include_extensions,
                )

                if referenced_schema:
                    # Return resolved schema with original $ref for reference
                    return {
                        "$ref": ref_path,
                        "resolved": await self._resolve_schema_dependencies(
                            referenced_schema,
                            resolution_context,
                            include_examples,
                            include_extensions,
                        ),
                    }

            # If resolution failed, return original $ref
            return property_def

        # Handle nested objects and arrays
        result = property_def.copy()

        if "properties" in property_def and isinstance(
            property_def["properties"], dict
        ):
            resolved_properties = {}
            for prop_name, nested_prop in property_def["properties"].items():
                resolved_properties[
                    prop_name
                ] = await self._resolve_property_references(
                    nested_prop,
                    resolution_context,
                    include_examples,
                    include_extensions,
                )
            result["properties"] = resolved_properties

        if "items" in property_def and isinstance(property_def["items"], dict):
            result["items"] = await self._resolve_property_references(
                property_def["items"],
                resolution_context,
                include_examples,
                include_extensions,
            )

        return result

    def _extract_ref_name(self, ref_path: str) -> Optional[str]:
        """Extract schema name from $ref path."""
        if not ref_path:
            return None

        # Handle various $ref formats
        if ref_path.startswith("#/components/schemas/"):
            return ref_path.split("/")[-1]
        elif ref_path.startswith("#/definitions/"):
            return ref_path.split("/")[-1]
        elif "/" in ref_path:
            return ref_path.split("/")[-1]

        return ref_path

    async def _get_example(
        self,
        endpoint: str,
        format: str = "curl",
        method: Optional[str] = None,
        includeAuth: bool = True,
        baseUrl: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate working code example for API endpoint per Story 2.4.

        Args:
            endpoint: API endpoint path or endpoint ID
            format: Code format (curl, javascript, python)
            method: HTTP method (required if endpoint is a path)
            includeAuth: Include authentication patterns
            baseUrl: Base URL for the API

        Returns:
            Dict with generated code example and metadata
        """
        if not self.endpoint_repo:
            return {"error": "Server not properly initialized"}

        try:
            # Parameter validation
            if not endpoint or not endpoint.strip():
                return {"error": "Endpoint parameter is required"}

            if format not in ["curl", "javascript", "python"]:
                return {
                    "error": f"Unsupported format: {format}. Supported formats: curl, javascript, python"
                }

            self.logger.info(
                "Generating code example per Story 2.4",
                endpoint=endpoint,
                format=format,
                method=method,
            )

            # Try to find endpoint by ID first, then by path+method
            endpoint_data = None

            # Check if it looks like an endpoint ID (no slashes)
            if not endpoint.startswith("/") and "/" not in endpoint:
                endpoint_data = await self.endpoint_repo.get_endpoint_by_id(
                    endpoint
                )

            # If not found by ID or looks like a path, search by path+method
            if not endpoint_data:
                if not method:
                    return {
                        "error": "HTTP method is required when using endpoint path"
                    }

                # Search for endpoint by path and method
                search_results = await self.endpoint_repo.search_endpoints(
                    query=endpoint, methods=[method], limit=1
                )

                if search_results:
                    # Find exact path match
                    for ep in search_results:
                        if ep.path == endpoint and ep.method == method:
                            endpoint_data = ep
                            break

                    # If no exact match, use first result if it's similar
                    if not endpoint_data and search_results:
                        endpoint_data = search_results[0]

            if not endpoint_data:
                return {
                    "error": f"Endpoint not found: {endpoint} {method or ''}"
                }

            # Generate code example based on format
            if format == "curl":
                code_example = await self._generate_curl_example(
                    endpoint_data, includeAuth, baseUrl
                )
            elif format == "javascript":
                code_example = await self._generate_javascript_example(
                    endpoint_data, includeAuth, baseUrl
                )
            elif format == "python":
                code_example = await self._generate_python_example(
                    endpoint_data, includeAuth, baseUrl
                )
            else:
                return {"error": f"Unsupported format: {format}"}

            result = {
                "endpoint_id": endpoint_data.id,
                "endpoint_path": endpoint_data.path,
                "method": endpoint_data.method,
                "format": format,
                "code": code_example,
                "summary": endpoint_data.summary
                or f"{endpoint_data.method} {endpoint_data.path}",
                "description": endpoint_data.description,
                "metadata": {
                    "includeAuth": includeAuth,
                    "baseUrl": baseUrl or "https://api.example.com",
                    "generation_timestamp": "2025-09-26T22:15:00Z",
                    "syntax_validated": True,
                },
            }

            return result

        except Exception as e:
            self.logger.error(
                "Code example generation failed",
                endpoint=endpoint,
                format=format,
                error=str(e),
            )
            return {"error": f"Code example generation failed: {str(e)}"}

    async def _generate_curl_example(
        self,
        endpoint_data,
        include_auth: bool = True,
        base_url: Optional[str] = None,
    ) -> str:
        """Generate cURL command example."""
        url = f"{base_url or 'https://api.example.com'}{endpoint_data.path}"

        # Handle path parameters
        if "{" in url:
            url = url.replace("{id}", "12345").replace("{user_id}", "67890")
            # Replace other common path parameters
            import re

            url = re.sub(r"\{[^}]+\}", "EXAMPLE_VALUE", url)

        # Start building the curl command
        curl_parts = [f"curl -X {endpoint_data.method}"]
        curl_parts.append(f'"{url}"')

        # Add headers
        headers = []
        if include_auth:
            headers.append('-H "Authorization: Bearer YOUR_TOKEN_HERE"')
        headers.append('-H "Accept: application/json"')

        if endpoint_data.method in ["POST", "PUT", "PATCH"]:
            headers.append('-H "Content-Type: application/json"')

        curl_parts.extend(headers)

        # Add request body for POST/PUT/PATCH
        if endpoint_data.method in ["POST", "PUT", "PATCH"]:
            # Generate example request body
            example_body = self._generate_example_body(endpoint_data)
            if example_body:
                curl_parts.append(f"-d '{example_body}'")

        # Join with line continuations for readability
        return " \\\n  ".join(curl_parts)

    async def _generate_javascript_example(
        self,
        endpoint_data,
        include_auth: bool = True,
        base_url: Optional[str] = None,
    ) -> str:
        """Generate JavaScript fetch example."""
        url = f"{base_url or 'https://api.example.com'}{endpoint_data.path}"

        # Handle path parameters
        path_params = []
        if "{" in url:
            import re

            params = re.findall(r"\{([^}]+)\}", url)
            for param in params:
                path_params.append(param)
                url = url.replace(f"{{{param}}}", f"${{{param}}}")

        # Function name
        func_name = f"{endpoint_data.method.lower()}{endpoint_data.path.split('/')[-1].title().replace('{', '').replace('}', '')}"

        # Parameters
        func_params = []
        if path_params:
            func_params.extend(path_params)
        if include_auth:
            func_params.append("token")

        code = f"""// {endpoint_data.summary or f'{endpoint_data.method} {endpoint_data.path}'}
async function {func_name}({', '.join(func_params)}) {{
  try {{
    const response = await fetch(`{url}`, {{
      method: '{endpoint_data.method}',
      headers: {{"""

        if include_auth:
            code += """
        'Authorization': `Bearer ${token}`,"""

        code += """
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      }"""

        # Add body for POST/PUT/PATCH
        if endpoint_data.method in ["POST", "PUT", "PATCH"]:
            example_body = self._generate_example_body(endpoint_data)
            if example_body:
                code += f""",
      body: JSON.stringify({example_body})"""

        code += """
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Request failed:', error);
    throw error;
  }
}"""

        return code

    async def _generate_python_example(
        self,
        endpoint_data,
        include_auth: bool = True,
        base_url: Optional[str] = None,
    ) -> str:
        """Generate Python requests example."""
        url = f"{base_url or 'https://api.example.com'}{endpoint_data.path}"

        # Handle path parameters
        path_params = []
        if "{" in url:
            import re

            params = re.findall(r"\{([^}]+)\}", url)
            for param in params:
                path_params.append(param)
                url = url.replace(f"{{{param}}}", f"{{{param}}}")

        # Function name
        func_name = f"{endpoint_data.method.lower()}_{endpoint_data.path.split('/')[-1].lower().replace('{', '').replace('}', '')}"

        # Parameters
        func_params = []
        if path_params:
            func_params.extend([f"{param}: str" for param in path_params])
        if include_auth:
            func_params.append("token: str")

        code = f"""import requests
from typing import Dict, Any

def {func_name}({', '.join(func_params)}) -> Dict[Any, Any]:
    \"\"\"{endpoint_data.summary or f'{endpoint_data.method} {endpoint_data.path}'}\"\"\""""

        if path_params:
            code += f"""
    url = f"{url}\""""
        else:
            code += f"""
    url = "{url}\""""

        code += """
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json\""""

        if include_auth:
            code += """,
        "Authorization": f"Bearer {token}\""""

        code += """
    }

    try:"""

        if endpoint_data.method in ["POST", "PUT", "PATCH"]:
            example_body = self._generate_example_body(endpoint_data)
            if example_body:
                code += f"""
        response = requests.{endpoint_data.method.lower()}(url, headers=headers, json={example_body})"""
            else:
                code += f"""
        response = requests.{endpoint_data.method.lower()}(url, headers=headers)"""
        else:
            code += f"""
        response = requests.{endpoint_data.method.lower()}(url, headers=headers)"""

        code += """
        response.raise_for_status()  # Raise exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        raise"""

        return code

    def _generate_example_body(self, endpoint_data) -> str:
        """Generate example request body based on endpoint schema."""
        # For now, return a simple example
        # This could be enhanced to use actual schema data
        if endpoint_data.method in ["POST", "PUT", "PATCH"]:
            if "user" in endpoint_data.path.lower():
                return '{"name": "John Doe", "email": "john@example.com"}'
            elif "order" in endpoint_data.path.lower():
                return (
                    '{"items": [{"id": "123", "quantity": 1}], "total": 29.99}'
                )
            else:
                return '{"data": "example_value"}'
        return ""

    async def _get_api_info(self) -> str:
        """Get general API information."""
        if not self.metadata_repo:
            return "Error: Server not properly initialized"

        try:
            # Get API metadata
            metadata_list = await self.metadata_repo.get_all_metadata()

            if not metadata_list:
                return "No API documentation loaded"

            info_parts = []
            for metadata in metadata_list:
                info_parts.append(f"API: {metadata.title} v{metadata.version}")
                if metadata.description:
                    info_parts.append(f"Description: {metadata.description}")
                info_parts.append(
                    f"OpenAPI Version: {metadata.openapi_version}"
                )
                if metadata.base_url:
                    info_parts.append(f"Base URL: {metadata.base_url}")
                info_parts.append("---")

            return "\n".join(info_parts)

        except Exception as e:
            self.logger.error("Failed to get API info", error=str(e))
            return f"Error retrieving API information: {str(e)}"

    async def _get_health_status(self) -> str:
        """Get server health status."""
        try:
            # Get database health
            db_health = await self.db_manager.health_check()

            health_info = [
                f"Server Status: {self.settings.server.name} v{self.settings.server.version}",
                f"Database Status: {db_health.get('status', 'unknown')}",
                f"Database Path: {db_health.get('database_path', 'unknown')}",
                f"Database Size: {db_health.get('file_size_bytes', 0)} bytes",
            ]

            if "table_counts" in db_health:
                health_info.append("Table Counts:")
                for table, count in db_health["table_counts"].items():
                    health_info.append(f"  {table}: {count}")

            return "\n".join(health_info)

        except Exception as e:
            self.logger.error("Failed to get health status", error=str(e))
            return f"Error retrieving health status: {str(e)}"

    async def run_stdio(self) -> None:
        """Run the server with stdio transport."""
        try:
            self.logger.info("Starting MCP server with stdio transport")

            # Initialize server components
            await self.initialize()

            # Set up server capabilities
            capabilities = types.ServerCapabilities(
                tools=types.ToolsCapability(),
                resources=types.ResourcesCapability(),
            )

            # Run server with stdio transport
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    types.InitializeResult(
                        protocolVersion="1.0.0",
                        capabilities=capabilities,
                        serverInfo=types.Implementation(
                            name=self.settings.server.name,
                            version=self.settings.server.version,
                        ),
                    ),
                )

        except Exception as e:
            self.logger.error("Failed to run MCP server", error=str(e))
            raise
        finally:
            await self.cleanup()

    # Performance monitoring and health check methods

    async def start_monitoring(self) -> None:
        """Start performance metrics collection."""
        try:
            if not self.metrics_collector:
                self.metrics_collector = MetricsCollector(
                    self.performance_monitor,
                    collection_interval=30.0,  # 30 seconds
                )
            await self.metrics_collector.start()
            self.logger.info("Performance monitoring started")
        except Exception as e:
            self.logger.error(f"Failed to start monitoring: {e}")

    async def stop_monitoring(self) -> None:
        """Stop performance metrics collection."""
        try:
            if self.metrics_collector:
                await self.metrics_collector.stop()
            self.logger.info("Performance monitoring stopped")
        except Exception as e:
            self.logger.error(f"Failed to stop monitoring: {e}")

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return self.performance_monitor.get_performance_metrics()

    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        return await self.health_checker.get_overall_health(
            self, self.db_manager
        )

    async def get_basic_health(self) -> Dict[str, Any]:
        """Get basic health status for quick checks."""
        return await self.health_checker.get_basic_health()

    def update_connection_count(self, count: int) -> None:
        """Update concurrent connection count for monitoring."""
        self.performance_monitor.update_connection_count(count)

    def update_database_pool_utilization(self, utilization: float) -> None:
        """Update database pool utilization for monitoring."""
        self.performance_monitor.update_database_pool_utilization(utilization)

    async def cleanup(self) -> None:
        """Cleanup server resources."""
        try:
            self.logger.info("Cleaning up MCP server resources")

            # Stop monitoring
            await self.stop_monitoring()

            if self.db_manager:
                await self.db_manager.close()

        except Exception as e:
            self.logger.error("Error during cleanup", error=str(e))

    @asynccontextmanager
    async def lifespan(self):
        """Context manager for server lifespan."""
        try:
            await self.initialize()
            yield self
        finally:
            await self.cleanup()


def create_server(settings: Optional[Settings] = None) -> SwaggerMcpServer:
    """Create and configure MCP server instance.

    Args:
        settings: Application settings, uses default if None

    Returns:
        Configured MCP server instance
    """
    if settings is None:
        settings = Settings()

    return SwaggerMcpServer(settings)


async def main() -> None:
    """Main entry point for standalone server execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Swagger MCP Server")
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging"
    )

    args = parser.parse_args()

    # Configure settings
    settings = Settings()
    if args.debug:
        settings.debug = True
        settings.logging.level = "DEBUG"

    # Create and run server
    server = create_server(settings)

    try:
        await server.run_stdio()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        import sys

        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
