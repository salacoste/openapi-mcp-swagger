"""MCP server implementation for Swagger API documentation access.

This module implements the Model Context Protocol (MCP) server that provides
searchEndpoints, getSchema, and getExample methods for AI agents to access
and query Swagger/OpenAPI documentation efficiently.
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Sequence

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, Resource

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.config.settings import Settings
from swagger_mcp_server.storage.database import DatabaseConfig, DatabaseManager
from swagger_mcp_server.storage.repositories import (
    EndpointRepository,
    MetadataRepository,
    SchemaRepository,
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

            self.logger.info("MCP server initialization completed successfully")

        except Exception as e:
            self.logger.error("Failed to initialize MCP server", error=str(e))
            raise

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        # Register tools (methods that AI agents can call)
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools/methods."""
            return [
                Tool(
                    name="searchEndpoints",
                    description="Search API endpoints by keyword, HTTP method, or path pattern",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (keywords, endpoint path, description)",
                            },
                            "method": {
                                "type": "string",
                                "description": "HTTP method filter (GET, POST, PUT, DELETE, etc.)",
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
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 100,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="getSchema",
                    description="Get detailed schema definition for API components",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "schema_name": {
                                "type": "string",
                                "description": "Name of the schema/component to retrieve",
                            },
                            "include_examples": {
                                "type": "boolean",
                                "description": "Include example values in the schema",
                                "default": True,
                            },
                            "resolve_refs": {
                                "type": "boolean",
                                "description": "Resolve $ref references to full schemas",
                                "default": True,
                            },
                        },
                        "required": ["schema_name"],
                    },
                ),
                Tool(
                    name="getExample",
                    description="Generate code examples for API endpoints",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "endpoint_id": {
                                "type": "string",
                                "description": "Unique identifier of the endpoint",
                            },
                            "language": {
                                "type": "string",
                                "description": "Programming language for the example",
                                "enum": [
                                    "curl",
                                    "javascript",
                                    "python",
                                    "typescript",
                                ],
                                "default": "curl",
                            },
                            "include_auth": {
                                "type": "boolean",
                                "description": "Include authentication in the example",
                                "default": True,
                            },
                        },
                        "required": ["endpoint_id"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[Any]:
            """Handle tool calls from AI agents."""
            try:
                if name == "searchEndpoints":
                    return await self._search_endpoints(**arguments)
                elif name == "getSchema":
                    return await self._get_schema(**arguments)
                elif name == "getExample":
                    return await self._get_example(**arguments)
                else:
                    raise NotFoundError(f"Unknown tool: {name}")

            except Exception as e:
                self.logger.error(
                    "Tool call failed",
                    tool_name=name,
                    arguments=arguments,
                    error=str(e),
                )
                raise ServerError(f"Tool execution failed: {str(e)}")

        # Register resources (data that can be read)
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available resources."""
            return [
                Resource(
                    uri="swagger://api-info",
                    name="API Information",
                    description="General information about the loaded API",
                ),
                Resource(
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
                    raise NotFoundError(f"Unknown resource: {uri}")

            except Exception as e:
                self.logger.error("Resource read failed", uri=uri, error=str(e))
                raise ServerError(f"Resource read failed: {str(e)}")

    async def _search_endpoints(
        self, query: str, method: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for API endpoints based on query and filters."""
        if not self.endpoint_repo:
            raise ServerError("Server not properly initialized")

        try:
            self.logger.info(
                "Searching endpoints", query=query, method=method, limit=limit
            )

            # Use repository to search endpoints
            endpoints = await self.endpoint_repo.search_endpoints(
                query=query, http_method=method, limit=limit
            )

            # Format results for MCP response
            results = []
            for endpoint in endpoints:
                result = {
                    "id": endpoint.id,
                    "path": endpoint.path,
                    "method": endpoint.http_method,
                    "summary": endpoint.summary,
                    "description": endpoint.description,
                    "operationId": endpoint.operation_id,
                    "tags": endpoint.tags,
                    "parameters": (
                        len(endpoint.parameters) if endpoint.parameters else 0
                    ),
                    "responses": len(endpoint.responses) if endpoint.responses else 0,
                }
                results.append(result)

            self.logger.info(
                "Endpoint search completed",
                query=query,
                results_count=len(results),
            )

            return results

        except Exception as e:
            self.logger.error("Endpoint search failed", query=query, error=str(e))
            raise

    async def _get_schema(
        self,
        schema_name: str,
        include_examples: bool = True,
        resolve_refs: bool = True,
    ) -> Dict[str, Any]:
        """Get detailed schema definition."""
        if not self.schema_repo:
            raise ServerError("Server not properly initialized")

        try:
            self.logger.info(
                "Retrieving schema",
                schema_name=schema_name,
                include_examples=include_examples,
                resolve_refs=resolve_refs,
            )

            # Get schema from repository
            schema = await self.schema_repo.get_schema_by_name(schema_name)

            if not schema:
                raise NotFoundError(f"Schema not found: {schema_name}")

            # Build response
            result = {
                "name": schema.name,
                "type": schema.schema_type,
                "definition": schema.definition,
                "description": schema.description,
                "required_fields": schema.required_fields,
                "properties_count": (
                    len(schema.definition.get("properties", {}))
                    if isinstance(schema.definition, dict)
                    else 0
                ),
            }

            if include_examples and schema.examples:
                result["examples"] = schema.examples

            self.logger.info("Schema retrieval completed", schema_name=schema_name)

            return result

        except NotFoundError:
            raise
        except Exception as e:
            self.logger.error(
                "Schema retrieval failed",
                schema_name=schema_name,
                error=str(e),
            )
            raise

    async def _get_example(
        self,
        endpoint_id: str,
        language: str = "curl",
        include_auth: bool = True,
    ) -> Dict[str, Any]:
        """Generate code example for an endpoint."""
        if not self.endpoint_repo:
            raise ServerError("Server not properly initialized")

        try:
            self.logger.info(
                "Generating code example",
                endpoint_id=endpoint_id,
                language=language,
                include_auth=include_auth,
            )

            # Get endpoint details
            endpoint = await self.endpoint_repo.get_endpoint_by_id(endpoint_id)

            if not endpoint:
                raise NotFoundError(f"Endpoint not found: {endpoint_id}")

            # For now, return a basic structure
            # TODO: Implement proper code generation in Epic 4
            result = {
                "endpoint_id": endpoint_id,
                "language": language,
                "method": endpoint.http_method,
                "path": endpoint.path,
                "example": f"# {language.upper()} example for {endpoint.http_method} {endpoint.path}\n# TODO: Implement code generation",
                "description": f"Code example for {endpoint.summary or endpoint.path}",
            }

            self.logger.info(
                "Code example generation completed",
                endpoint_id=endpoint_id,
                language=language,
            )

            return result

        except NotFoundError:
            raise
        except Exception as e:
            self.logger.error(
                "Code example generation failed",
                endpoint_id=endpoint_id,
                error=str(e),
            )
            raise

    async def _get_api_info(self) -> str:
        """Get general API information."""
        if not self.metadata_repo:
            raise ServerError("Server not properly initialized")

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
                info_parts.append(f"Endpoints: {metadata.endpoint_count}")
                info_parts.append(f"Schemas: {metadata.schema_count}")
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

            # Run server with stdio transport
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream, write_stream, self.server.create_initialization_options()
                )

        except Exception as e:
            self.logger.error("Failed to run MCP server", error=str(e))
            raise
        finally:
            await self.cleanup()

    async def run_sse(self, host: str = "localhost", port: int = 8080) -> None:
        """Run the server with SSE transport."""
        # TODO: Implement SSE transport when available in MCP library
        self.logger.warning("SSE transport not yet implemented, using stdio instead")
        await self.run_stdio()

    async def cleanup(self) -> None:
        """Cleanup server resources."""
        try:
            self.logger.info("Cleaning up MCP server resources")

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
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host for SSE transport (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for SSE transport (default: 8080)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Configure settings
    settings = Settings()
    if args.debug:
        settings.debug = True
        settings.logging.level = "DEBUG"

    # Create and run server
    server = create_server(settings)

    try:
        if args.transport == "stdio":
            await server.run_stdio()
        else:
            await server.run_sse(host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
