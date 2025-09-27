"""Mock integration with Epic components for Story 4.2 demonstration.

This module provides simplified mock implementations of the Epic 1, 2, and 3 components
to demonstrate the conversion pipeline functionality without requiring full integration.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List


class MockSwaggerParser:
    """Mock implementation of Swagger parser from Epic 1."""

    async def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Parse a Swagger file and return normalized data."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                swagger_data = json.load(f)

            # Extract basic information
            info = swagger_data.get("info", {})
            paths = swagger_data.get("paths", {})
            components = swagger_data.get("components", {})
            schemas = components.get("schemas", {})

            # Convert paths to endpoint list
            endpoints = []
            for path, methods in paths.items():
                for method, details in methods.items():
                    if isinstance(details, dict):
                        endpoints.append(
                            {
                                "path": path,
                                "method": method.upper(),
                                "summary": details.get("summary", ""),
                                "description": details.get("description", ""),
                                "tags": details.get("tags", []),
                                "operationId": details.get(
                                    "operationId", f"{method}_{path}"
                                ),
                                "parameters": details.get("parameters", []),
                                "responses": details.get("responses", {}),
                            }
                        )

            parsed_data = {
                "info": info,
                "endpoints": endpoints,
                "schemas": schemas,
                "swagger_version": swagger_data.get("swagger")
                or swagger_data.get("openapi"),
            }

            return parsed_data

        except Exception as e:
            raise Exception(f"Failed to parse Swagger file: {str(e)}")


class MockSchemaNormalizer:
    """Mock implementation of schema normalizer from Epic 1."""

    async def normalize_schema_data(
        self, parsed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize parsed schema data."""
        # For mock implementation, just pass through with some enhancements
        normalized_data = parsed_data.copy()

        # Add normalized schemas section
        normalized_data["normalized_schemas"] = {}
        for schema_name, schema_def in parsed_data.get("schemas", {}).items():
            normalized_data["normalized_schemas"][schema_name] = {
                "name": schema_name,
                "definition": schema_def,
                "properties": schema_def.get("properties", {}),
                "required": schema_def.get("required", []),
                "type": schema_def.get("type", "object"),
            }

        return normalized_data


class MockDatabase:
    """Mock implementation of database from Epic 1."""

    def __init__(self, database_path: str):
        self.database_path = database_path

    async def initialize(self):
        """Initialize database."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)

        # Create empty database file
        with open(self.database_path, "w") as f:
            f.write("# Mock SQLite database placeholder\n")

    async def store_swagger_data(self, normalized_data: Dict[str, Any]):
        """Store normalized data in database."""
        # For mock implementation, just ensure the file exists
        if not os.path.exists(self.database_path):
            await self.initialize()

    async def close(self):
        """Close database connection."""
        pass


class MockSearchIndexManager:
    """Mock implementation of search index manager from Epic 3."""

    def __init__(self, index_path: str):
        self.index_path = index_path

    async def initialize(self):
        """Initialize search index."""
        os.makedirs(self.index_path, exist_ok=True)


class MockSearchEngine:
    """Mock implementation of search engine from Epic 3."""

    def __init__(self, index_manager, config):
        self.index_manager = index_manager
        self.config = config

    async def build_index(self, normalized_data: Dict[str, Any]):
        """Build search index from normalized data."""
        await self.index_manager.initialize()

        # Create some mock index files
        index_files = ["endpoints.idx", "schemas.idx", "metadata.idx"]

        for file_name in index_files:
            file_path = os.path.join(self.index_manager.index_path, file_name)
            with open(file_path, "w") as f:
                f.write(f"# Mock search index file for {file_name}\n")
                f.write(
                    f"# Indexed {len(normalized_data.get('endpoints', []))} endpoints\n"
                )
                f.write(
                    f"# Indexed {len(normalized_data.get('schemas', {}))} schemas\n"
                )


class MockMCPServer:
    """Mock implementation of MCP server from Epic 2."""

    def __init__(self, database=None, search_engine=None, settings=None):
        self.database = database
        self.search_engine = search_engine
        self.settings = settings

    async def start(self, host: str = "localhost", port: int = 8080):
        """Start MCP server."""
        # Mock implementation - just return success
        pass

    async def stop(self):
        """Stop MCP server."""
        pass


def create_server(**kwargs):
    """Mock function to create MCP server."""
    return MockMCPServer(**kwargs)
