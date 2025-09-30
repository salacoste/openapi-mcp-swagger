"""Endpoint processor with category integration.

Epic 6: Integrates categorization engine into endpoint processing workflow.
"""

from typing import Any, Dict, List, Optional, Tuple

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.parser.categorization import (
    CategorizationEngine,
    CategoryCatalog,
    CategoryInfo,
)

logger = get_logger(__name__)


class EndpointProcessor:
    """Processes endpoints with automatic categorization.

    Epic 6: Hierarchical Endpoint Catalog System
    """

    def __init__(self):
        """Initialize endpoint processor."""
        self.logger = logger
        self.categorization_engine = CategorizationEngine()
        self.category_catalog = CategoryCatalog()

    def initialize_from_spec(self, spec_data: Dict[str, Any]) -> None:
        """Initialize categorization from OpenAPI specification root.

        Args:
            spec_data: Complete OpenAPI specification dictionary
        """
        # Extract tag definitions from root
        tags = spec_data.get("tags", [])
        if tags:
            self.categorization_engine.set_tag_definitions(tags)
            self.logger.info("Tag definitions loaded", count=len(tags))

        # Extract x-tagGroups vendor extension
        tag_groups = spec_data.get("x-tagGroups", [])
        if tag_groups:
            self.categorization_engine.set_tag_groups(tag_groups)
            self.logger.info("Tag groups loaded", count=len(tag_groups))

    def process_endpoint(
        self, path: str, method: str, operation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process endpoint and add category information.

        Args:
            path: Endpoint path (e.g., "/api/v1/campaign/list")
            method: HTTP method (e.g., "get", "post")
            operation: OpenAPI operation object

        Returns:
            Operation dict enriched with category fields
        """
        # Categorize endpoint
        category_info = self.categorization_engine.categorize_endpoint(operation, path)

        # Add to catalog
        self.category_catalog.add_endpoint(category_info, method.upper())

        # Enrich operation with category fields
        enriched_operation = operation.copy()
        enriched_operation["category"] = category_info.category
        enriched_operation["category_group"] = category_info.category_group
        enriched_operation["category_display_name"] = category_info.display_name
        enriched_operation["category_metadata"] = category_info.to_dict()

        self.logger.debug(
            "Endpoint categorized",
            path=path,
            method=method,
            category=category_info.category,
            group=category_info.category_group,
        )

        return enriched_operation

    def process_paths(self, paths: Dict[str, Any]) -> Dict[str, Any]:
        """Process all paths and categorize endpoints.

        Args:
            paths: OpenAPI paths object

        Returns:
            Paths dict with categorized operations
        """
        processed_paths = {}

        for path, path_item in paths.items():
            processed_path_item = {}

            # Process each HTTP method
            http_methods = ["get", "post", "put", "delete", "patch", "head", "options"]
            for method in http_methods:
                if method in path_item:
                    operation = path_item[method]
                    processed_operation = self.process_endpoint(path, method, operation)
                    processed_path_item[method] = processed_operation

            # Preserve non-operation fields (parameters, servers, etc.)
            for key, value in path_item.items():
                if key not in http_methods:
                    processed_path_item[key] = value

            processed_paths[path] = processed_path_item

        self.logger.info(
            "All paths processed",
            paths=len(processed_paths),
            categories=len(self.category_catalog._categories),
        )

        return processed_paths

    def get_category_catalog_data(self) -> List[Dict[str, Any]]:
        """Get category catalog for database insertion.

        Returns:
            List of category dictionaries ready for endpoint_categories table
        """
        return self.category_catalog.get_categories()

    def get_catalog_statistics(self) -> Dict[str, Any]:
        """Get catalog statistics.

        Returns:
            Statistics dictionary
        """
        return self.category_catalog.get_statistics()


def enrich_endpoints_with_categories(
    endpoints: List[Dict[str, Any]],
    spec_data: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Enrich endpoint list with category information.

    Convenience function for batch processing.

    Args:
        endpoints: List of endpoint dictionaries
        spec_data: Complete OpenAPI specification

    Returns:
        Tuple of (enriched_endpoints, category_catalog)
    """
    processor = EndpointProcessor()
    processor.initialize_from_spec(spec_data)

    enriched_endpoints = []

    for endpoint in endpoints:
        path = endpoint.get("path", "")
        method = endpoint.get("method", "get")
        operation = endpoint.get("operation", {})

        # Process endpoint
        enriched_operation = processor.process_endpoint(path, method, operation)

        # Merge enriched data back to endpoint
        enriched_endpoint = endpoint.copy()
        enriched_endpoint.update(
            {
                "category": enriched_operation.get("category"),
                "category_group": enriched_operation.get("category_group"),
                "category_display_name": enriched_operation.get(
                    "category_display_name"
                ),
                # SQLAlchemy JSON column expects dict, not JSON string
                "category_metadata": enriched_operation.get("category_metadata", {}),
            }
        )

        enriched_endpoints.append(enriched_endpoint)

    # Get category catalog
    category_catalog = processor.get_category_catalog_data()

    logger.info(
        "Endpoint enrichment completed",
        endpoints=len(enriched_endpoints),
        categories=len(category_catalog),
    )

    return enriched_endpoints, category_catalog