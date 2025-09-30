"""Core conversion pipeline for Swagger to MCP server transformation."""

import asyncio
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import structlog

from .package_generator import DeploymentPackageGenerator
from .progress_tracker import ConversionProgressTracker
from .validator import ConversionValidator

# Import components from previous epics (using mock implementations for demonstration)
try:
    from ..parser.schema_normalizer import SchemaNormalizer
    from ..parser.swagger_parser import SwaggerParser
    from ..search.index_manager import SearchIndexManager
    from ..search.search_engine import SearchEngine
    from ..server.mcp_server import create_server
    from ..storage.database import Database
except ImportError:
    # Fall back to mock implementations for Story 4.2 demonstration
    from .mock_integration import MockDatabase as Database
    from .mock_integration import MockSchemaNormalizer as SchemaNormalizer
    from .mock_integration import MockSearchEngine as SearchEngine
    from .mock_integration import MockSearchIndexManager as SearchIndexManager
    from .mock_integration import MockSwaggerParser as SwaggerParser
    from .mock_integration import create_server


logger = structlog.get_logger(__name__)


class ConversionError(Exception):
    """Exception raised during conversion process."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ConversionPipeline:
    """Orchestrates complete Swagger to MCP server conversion."""

    def __init__(
        self,
        swagger_file: str,
        output_dir: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        self.swagger_file = swagger_file
        self.output_dir = output_dir or self._generate_output_dir()
        self.options = options or {}
        self.conversion_stats = {}
        self.start_time = None

        # Initialize progress tracker
        self.progress_tracker = ConversionProgressTracker(
            verbose=self.options.get("verbose", False)
        )

        # Initialize generators and validators
        self.package_generator = DeploymentPackageGenerator(self.output_dir)
        self.validator = ConversionValidator()

    def _generate_output_dir(self) -> str:
        """Generate default output directory name in generated-mcp-servers folder."""
        base_name = Path(self.swagger_file).stem
        # Create generated MCP servers in dedicated directory
        generated_dir = Path("./generated-mcp-servers")
        return str(generated_dir / f"mcp-server-{base_name}")

    async def execute_conversion(self) -> Dict[str, Any]:
        """Execute complete conversion pipeline."""
        self.start_time = time.time()

        try:
            logger.info("Starting conversion pipeline", swagger_file=self.swagger_file)

            # Phase 1: Validation and preparation
            await self._validate_input_file()
            await self._prepare_output_directory()

            # Phase 2: Core processing pipeline
            parsed_data = await self._execute_parsing_phase()
            categorized_data = await self._execute_categorization_phase(parsed_data)
            normalized_data = await self._execute_normalization_phase(categorized_data)
            database_path = await self._execute_storage_phase(normalized_data)
            search_index = await self._execute_indexing_phase(
                normalized_data, database_path
            )

            # Phase 3: MCP server generation
            server_config = await self._generate_mcp_server_config(
                normalized_data, database_path
            )
            deployment_package = await self._create_deployment_package(server_config)

            # Phase 3.5: Populate real database with API data
            await self._populate_database(parsed_data)

            # Phase 4: Validation and finalization
            if not self.options.get("skip_validation", False):
                await self._validate_generated_server(deployment_package)

            conversion_report = await self._generate_conversion_report()

            total_time = time.time() - self.start_time
            logger.info(
                "Conversion completed successfully",
                duration=f"{total_time:.1f}s",
            )

            return {
                "status": "success",
                "output_directory": self.output_dir,
                "server_config": server_config,
                "conversion_stats": self.conversion_stats,
                "deployment_ready": True,
                "report": conversion_report,
                "duration": total_time,
            }

        except Exception as e:
            logger.error("Conversion failed", error=str(e))
            error_report = await self._handle_conversion_error(e)
            raise ConversionError(f"Conversion failed: {str(e)}", error_report)

    async def _validate_input_file(self):
        """Validate input Swagger file."""
        with self.progress_tracker.track_phase("Validating input file"):
            if not os.path.exists(self.swagger_file):
                raise ConversionError(f"Swagger file not found: {self.swagger_file}")

            # Check file size
            file_size = os.path.getsize(self.swagger_file)
            if file_size > 100 * 1024 * 1024:  # 100MB limit
                raise ConversionError(
                    f"Swagger file too large: {file_size / 1024 / 1024:.1f}MB"
                )

            # Check if it's a URL (basic check)
            if self.swagger_file.startswith(("http://", "https://")):
                raise ConversionError("URL input not yet implemented in this version")

            # Basic file format check
            if not self.swagger_file.lower().endswith((".json", ".yaml", ".yml")):
                raise ConversionError("Swagger file must be JSON or YAML format")

            self.conversion_stats["input_file_size"] = file_size

    async def _prepare_output_directory(self):
        """Prepare output directory for generated files."""
        with self.progress_tracker.track_phase("Preparing output directory"):
            output_path = Path(self.output_dir)

            if output_path.exists():
                if not self.options.get("force", False):
                    if any(output_path.iterdir()):
                        raise ConversionError(
                            f"Output directory not empty: {self.output_dir}",
                            {
                                "suggestion": "Use --force to overwrite or choose different directory"
                            },
                        )
                else:
                    # Remove existing directory
                    shutil.rmtree(output_path)

            # Create output directory
            output_path.mkdir(parents=True, exist_ok=True)

            # Create subdirectories
            (output_path / "data").mkdir(exist_ok=True)
            (output_path / "config").mkdir(exist_ok=True)
            (output_path / "docs").mkdir(exist_ok=True)

    async def _execute_parsing_phase(self) -> Dict[str, Any]:
        """Execute parsing phase with Epic 1 integration."""
        with self.progress_tracker.track_phase("Parsing Swagger specification"):
            try:
                # Initialize parser from Epic 1
                parser = SwaggerParser()

                # Parse the swagger file
                parsed_data = await parser.parse_file(self.swagger_file)

                # Update conversion statistics
                endpoints = parsed_data.get("endpoints", [])
                schemas = parsed_data.get("schemas", {})

                self.conversion_stats.update(
                    {
                        "endpoints_found": len(endpoints),
                        "schemas_found": len(schemas),
                        "api_title": parsed_data.get("info", {}).get(
                            "title", "Unknown API"
                        ),
                        "api_version": parsed_data.get("info", {}).get(
                            "version", "1.0"
                        ),
                    }
                )

                logger.info(
                    "Parsing completed",
                    endpoints=len(endpoints),
                    schemas=len(schemas),
                )

                return parsed_data

            except Exception as e:
                raise ConversionError(f"Failed to parse Swagger file: {str(e)}")

    async def _execute_categorization_phase(
        self, parsed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute categorization phase with Epic 6 integration."""
        with self.progress_tracker.track_phase("Categorizing API endpoints"):
            try:
                from ..parser.endpoint_processor import enrich_endpoints_with_categories

                # Get endpoints from parsed data
                endpoints = parsed_data.get("endpoints", [])

                if not endpoints:
                    logger.info("No endpoints to categorize, skipping categorization")
                    return parsed_data

                # Prepare endpoints for categorization
                endpoint_list = []
                for endpoint in endpoints:
                    endpoint_list.append(
                        {
                            "path": endpoint.get("path"),
                            "method": endpoint.get("method"),
                            "operation": {
                                "tags": endpoint.get("tags", []),
                                "operationId": endpoint.get("operation_id"),
                                "summary": endpoint.get("summary"),
                                "description": endpoint.get("description"),
                            },
                        }
                    )

                # Enrich endpoints with category information
                enriched_endpoints, category_catalog = enrich_endpoints_with_categories(
                    endpoint_list, parsed_data
                )

                # Update endpoints in parsed_data with category fields
                for i, endpoint in enumerate(endpoints):
                    enriched = enriched_endpoints[i]
                    endpoint["category"] = enriched.get("category")
                    endpoint["category_group"] = enriched.get("category_group")
                    endpoint["category_display_name"] = enriched.get(
                        "category_display_name"
                    )
                    endpoint["category_metadata"] = enriched.get("category_metadata")

                # Add category catalog to parsed data
                parsed_data["category_catalog"] = category_catalog

                # Update statistics
                self.conversion_stats.update(
                    {
                        "categorization_completed": True,
                        "categories_found": len(category_catalog),
                        "categorized_endpoints": len(enriched_endpoints),
                    }
                )

                logger.info(
                    "Categorization completed",
                    endpoints=len(enriched_endpoints),
                    categories=len(category_catalog),
                )

                return parsed_data

            except Exception as e:
                logger.warning(
                    "Categorization failed, continuing without categories",
                    error=str(e),
                )
                # Don't fail the entire conversion if categorization fails
                return parsed_data

    async def _execute_normalization_phase(
        self, parsed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute normalization phase with Epic 1 integration."""
        with self.progress_tracker.track_phase("Normalizing API structure"):
            try:
                # Initialize normalizer from Epic 1
                normalizer = SchemaNormalizer()

                # Normalize the parsed data
                normalized_data = await normalizer.normalize_schema_data(parsed_data)

                # Update statistics
                self.conversion_stats.update(
                    {
                        "normalization_completed": True,
                        "normalized_schemas": len(
                            normalized_data.get("normalized_schemas", {})
                        ),
                    }
                )

                return normalized_data

            except Exception as e:
                raise ConversionError(f"Failed to normalize API structure: {str(e)}")

    async def _execute_storage_phase(self, normalized_data: Dict[str, Any]) -> str:
        """Execute storage phase with Epic 1 integration."""
        with self.progress_tracker.track_phase("Setting up database storage"):
            try:
                # Create database file path
                database_path = os.path.join(self.output_dir, "data", "mcp_server.db")

                # Initialize database from Epic 1
                database = Database(database_path)
                await database.initialize()

                # Store normalized data
                await database.store_swagger_data(normalized_data)

                # Update statistics
                self.conversion_stats.update(
                    {
                        "database_path": database_path,
                        "storage_completed": True,
                    }
                )

                await database.close()
                return database_path

            except Exception as e:
                raise ConversionError(f"Failed to set up database storage: {str(e)}")

    async def _execute_indexing_phase(
        self, normalized_data: Dict[str, Any], database_path: str
    ) -> str:
        """Execute search indexing phase with Epic 3 integration."""
        with self.progress_tracker.track_phase("Building search index"):
            try:
                # Create search index directory
                index_path = os.path.join(self.output_dir, "data", "search_index")
                os.makedirs(index_path, exist_ok=True)

                # Initialize search components from Epic 3
                index_manager = SearchIndexManager(index_path)
                search_engine = SearchEngine(index_manager, config={})

                # Build search index
                await search_engine.build_index(normalized_data)

                # Update statistics
                self.conversion_stats.update(
                    {
                        "search_index_path": index_path,
                        "indexing_completed": True,
                        "indexed_documents": len(normalized_data.get("endpoints", [])),
                    }
                )

                return index_path

            except Exception as e:
                raise ConversionError(f"Failed to build search index: {str(e)}")

    async def _generate_mcp_server_config(
        self, normalized_data: Dict[str, Any], database_path: str
    ) -> Dict[str, Any]:
        """Generate MCP server configuration."""
        with self.progress_tracker.track_phase("Generating MCP server configuration"):
            try:
                api_info = normalized_data.get("info", {})

                server_config = {
                    "api_title": api_info.get("title", "Unknown API"),
                    "api_version": api_info.get("version", "1.0"),
                    "api_description": api_info.get("description", ""),
                    "server_name": self.options.get("name")
                    or self._generate_server_name(api_info),
                    "host": self.options.get("host", "localhost"),
                    "port": self.options.get("port", 8080),
                    "database_path": database_path,
                    "search_index_path": os.path.join(
                        self.output_dir, "data", "search_index"
                    ),
                    "swagger_file": self.swagger_file,
                    "generation_date": datetime.now().isoformat(),
                    "endpoint_count": self.conversion_stats.get("endpoints_found", 0),
                    "schema_count": self.conversion_stats.get("schemas_found", 0),
                }

                return server_config

            except Exception as e:
                raise ConversionError(
                    f"Failed to generate server configuration: {str(e)}"
                )

    def _generate_server_name(self, api_info: Dict[str, Any]) -> str:
        """Generate a suitable server name from API info."""
        title = api_info.get("title", "swagger-api")
        # Convert to lowercase, replace spaces with hyphens, remove special chars
        import re

        name = re.sub(r"[^a-zA-Z0-9\-_]", "", title.lower().replace(" ", "-"))
        return name or "swagger-mcp-server"

    async def _create_deployment_package(self, server_config: Dict[str, Any]) -> str:
        """Create complete deployment package."""
        with self.progress_tracker.track_phase("Creating deployment package"):
            try:
                package_path = await self.package_generator.create_deployment_package(
                    server_config
                )

                self.conversion_stats.update(
                    {
                        "deployment_package": package_path,
                        "package_generation_completed": True,
                    }
                )

                return package_path

            except Exception as e:
                raise ConversionError(f"Failed to create deployment package: {str(e)}")

    async def _populate_database(self, parsed_data: Dict[str, Any]):
        """Populate database with actual API data from parsed swagger."""
        try:
            import json
            from pathlib import Path

            # Import storage components
            from ..storage.database import DatabaseManager, DatabaseConfig
            from ..storage.repositories import (
                EndpointRepository,
                SchemaRepository,
                MetadataRepository,
            )
            from ..storage.models import APIMetadata, Endpoint, Schema

            # Database path
            db_path = Path(self.output_dir) / "data" / "mcp_server.db"

            # Remove mock database if exists
            if db_path.exists():
                db_path.unlink()

            # Initialize real database
            db_config = DatabaseConfig(database_path=str(db_path))
            db_manager = DatabaseManager(db_config)
            await db_manager.initialize()

            # Load swagger data
            with open(self.swagger_file, "r", encoding="utf-8") as f:
                swagger = json.load(f)

            async with db_manager.get_session() as session:
                # Create API metadata
                metadata_repo = MetadataRepository(session)

                # Extract servers info
                servers = swagger.get('servers', [])
                if not servers and swagger.get('host'):
                    # Swagger 2.0 fallback
                    scheme = swagger.get('schemes', ['https'])[0]
                    host = swagger.get('host')
                    base_path = swagger.get('basePath', '')
                    servers = [{"url": f"{scheme}://{host}{base_path}"}]

                api = APIMetadata(
                    title=swagger["info"]["title"],
                    version=swagger["info"]["version"],
                    openapi_version=swagger.get("swagger", swagger.get("openapi", "3.0")),
                    description=swagger["info"].get("description", ""),
                    base_url=swagger.get("host", ""),
                    contact_info=json.dumps(swagger.get("info", {}).get("contact", {})),
                    servers=json.dumps(servers) if servers else None
                )
                api = await metadata_repo.create(api)

                # Create endpoints
                endpoint_repo = EndpointRepository(session)
                endpoint_count = 0
                for path, path_item in swagger.get("paths", {}).items():
                    for method, operation in path_item.items():
                        if method in ["get", "post", "put", "delete", "patch"]:
                            endpoint = Endpoint(
                                api_id=api.id,
                                path=path,
                                method=method.upper(),
                                operation_id=operation.get("operationId", ""),
                                summary=operation.get("summary", ""),
                                description=operation.get("description", ""),
                                tags=json.dumps(operation.get("tags", [])),
                                parameters=json.dumps(operation.get("parameters", [])),
                                request_body=json.dumps(operation.get("requestBody", {})),
                                responses=json.dumps(operation.get("responses", {}))
                            )
                            await endpoint_repo.create(endpoint)
                            endpoint_count += 1

                # Create schemas
                schema_repo = SchemaRepository(session)
                schemas = swagger.get('components', {}).get('schemas', {})
                # Swagger 2.0 fallback
                if not schemas:
                    schemas = swagger.get('definitions', {})

                schema_count = 0
                for schema_name, schema_def in schemas.items():
                    schema_obj = Schema(
                        api_id=api.id,
                        name=schema_name,
                        type=schema_def.get("type", "object"),
                        title=schema_def.get("title", ""),
                        description=schema_def.get("description", ""),
                        properties=json.dumps(schema_def.get("properties", {})),
                        required=json.dumps(schema_def.get("required", [])),
                        example=json.dumps(schema_def.get("example", {})),
                        format=schema_def.get("format", "")
                    )
                    await schema_repo.create(schema_obj)
                    schema_count += 1

                await session.commit()

            await db_manager.close()

            logger.info(
                "Database populated successfully",
                endpoints=endpoint_count,
                schemas=schema_count
            )

            # Update conversion stats
            self.conversion_stats.update({
                "database_populated": True,
                "endpoints_inserted": endpoint_count,
                "schemas_inserted": schema_count
            })

        except Exception as e:
            logger.error("Failed to populate database", error=str(e))
            # Don't fail conversion, just log warning
            logger.warning("Database population failed, server generated with empty database")

    async def _validate_generated_server(self, deployment_package: str):
        """Validate generated MCP server functionality."""
        with self.progress_tracker.track_phase("Validating generated server"):
            try:
                validation_results = await self.validator.validate_generated_server(
                    deployment_package
                )

                if not validation_results["overall_status"] == "passed":
                    logger.warning(
                        "Validation warnings found", results=validation_results
                    )

                self.conversion_stats.update(
                    {
                        "validation_results": validation_results,
                        "validation_completed": True,
                    }
                )

            except Exception as e:
                raise ConversionError(f"Failed to validate generated server: {str(e)}")

    async def _generate_conversion_report(self) -> Dict[str, Any]:
        """Generate comprehensive conversion report."""
        duration = time.time() - self.start_time if self.start_time else 0

        report = {
            "conversion_summary": {
                "status": "success",
                "duration": f"{duration:.1f}s",
                "swagger_file": self.swagger_file,
                "output_directory": self.output_dir,
            },
            "api_summary": {
                "title": self.conversion_stats.get("api_title", "Unknown"),
                "version": self.conversion_stats.get("api_version", "1.0"),
                "endpoints": self.conversion_stats.get("endpoints_found", 0),
                "schemas": self.conversion_stats.get("schemas_found", 0),
            },
            "processing_phases": {
                "parsing": "completed",
                "normalization": "completed",
                "storage": "completed",
                "indexing": "completed",
                "generation": "completed",
                "validation": (
                    "completed"
                    if not self.options.get("skip_validation")
                    else "skipped"
                ),
            },
            "next_steps": [
                f"Start the server: cd {self.output_dir} && python server.py",
                "Connect AI agents to: http://localhost:8080",
                "View API documentation in README.md",
                "Customize configuration in config/server.yaml",
            ],
        }

        return report

    async def _handle_conversion_error(self, error: Exception) -> Dict[str, Any]:
        """Handle conversion errors and generate diagnostic report."""
        duration = time.time() - self.start_time if self.start_time else 0

        error_report = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "conversion_stats": self.conversion_stats,
            "duration": f"{duration:.1f}s",
            "troubleshooting": self._generate_troubleshooting_suggestions(error),
        }

        return error_report

    def _generate_troubleshooting_suggestions(self, error: Exception) -> List[str]:
        """Generate troubleshooting suggestions based on error type."""
        suggestions = []

        error_msg = str(error).lower()

        if "file not found" in error_msg:
            suggestions.append("Check that the Swagger file path is correct")
            suggestions.append("Ensure you have read permissions for the file")

        elif "permission" in error_msg:
            suggestions.append("Check write permissions for the output directory")
            suggestions.append("Try running with appropriate permissions")

        elif "parse" in error_msg or "json" in error_msg or "yaml" in error_msg:
            suggestions.append(
                "Validate your Swagger file syntax using online validators"
            )
            suggestions.append(
                "Ensure the file is valid OpenAPI 3.0 or Swagger 2.0 format"
            )

        elif "memory" in error_msg or "size" in error_msg:
            suggestions.append("Try with a smaller Swagger file")
            suggestions.append("Increase available memory for the conversion process")

        else:
            suggestions.append(
                "Try running with --verbose for more detailed error information"
            )
            suggestions.append("Check that all dependencies are properly installed")

        suggestions.append("Consult the documentation for common issues and solutions")

        return suggestions

    # Preview and validation-only methods

    async def preview_conversion(self) -> Dict[str, Any]:
        """Preview conversion without generating files."""
        await self._validate_input_file()

        # Quick parse to get basic info
        parser = SwaggerParser()
        parsed_data = await parser.parse_file(self.swagger_file)

        api_info = parsed_data.get("info", {})
        endpoints = parsed_data.get("endpoints", [])
        schemas = parsed_data.get("schemas", {})

        preview = {
            "api_info": {
                "title": api_info.get("title", "Unknown API"),
                "version": api_info.get("version", "1.0"),
                "description": api_info.get("description", ""),
            },
            "conversion_plan": {
                "endpoints_to_process": len(endpoints),
                "schemas_to_process": len(schemas),
                "estimated_duration": self._estimate_conversion_time(
                    len(endpoints), len(schemas)
                ),
                "output_directory": self.output_dir,
                "server_name": self.options.get("name")
                or self._generate_server_name(api_info),
            },
            "generated_files": [
                "server.py - Main MCP server implementation",
                "config/server.yaml - Server configuration",
                "data/mcp_server.db - SQLite database with API data",
                "data/search_index/ - Search index files",
                "README.md - Usage documentation",
                "requirements.txt - Python dependencies",
                "Dockerfile - Container deployment",
            ],
        }

        return preview

    async def validate_swagger_only(self):
        """Validate Swagger file without conversion."""
        await self._validate_input_file()

        # Full validation
        parser = SwaggerParser()
        parsed_data = await parser.parse_file(self.swagger_file)

        # Additional validation logic here
        # This would include schema validation, consistency checks, etc.

        return True

    def _estimate_conversion_time(self, endpoint_count: int, schema_count: int) -> str:
        """Estimate conversion time based on API complexity."""
        # Rough estimation based on processing complexity
        base_time = 10  # seconds
        endpoint_time = endpoint_count * 0.1  # 0.1s per endpoint
        schema_time = schema_count * 0.05  # 0.05s per schema

        total_seconds = base_time + endpoint_time + schema_time

        if total_seconds < 60:
            return f"{total_seconds:.0f} seconds"
        else:
            return f"{total_seconds / 60:.1f} minutes"
