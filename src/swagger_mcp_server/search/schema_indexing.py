"""Schema indexing and search integration for the Swagger MCP Server.

This module provides comprehensive schema indexing capabilities that enable
intelligent search across API schemas, components, and their relationships
with endpoints as specified in Story 3.5.
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Set, Union
from enum import Enum

from ..storage.repositories.schema_repository import SchemaRepository
from ..storage.repositories.endpoint_repository import EndpointRepository
from ..config.settings import SearchConfig


class SchemaUsageContext(Enum):
    """Enumeration of schema usage contexts in API documentation."""
    REQUEST_BODY = "request_body"
    RESPONSE_BODY = "response_body"
    PARAMETER = "parameter"
    HEADER = "header"
    COMPONENT = "component"


@dataclass
class SchemaSearchDocument:
    """Comprehensive search document for API schemas with full metadata."""

    # Core identification
    schema_id: str
    schema_name: str
    schema_type: str  # object, array, string, number, etc.
    schema_path: str  # JSON path within the swagger document

    # Searchable content
    description: str
    property_names: List[str]
    property_descriptions: str
    property_types: List[str]

    # Schema structure and validation
    required_properties: List[str]
    optional_properties: List[str]
    nested_schemas: List[str]
    example_values: Dict[str, Any]
    validation_rules: Dict[str, Any]  # min/max, pattern, enum, etc.

    # Relationships and usage
    used_in_endpoints: List[str]
    usage_contexts: List[SchemaUsageContext]
    usage_details: List[Dict[str, Any]]  # Detailed usage information

    # Schema composition and inheritance
    inherits_from: Optional[str]
    extended_by: List[str]
    composed_schemas: List[str]  # allOf, oneOf, anyOf
    composition_type: Optional[str]

    # Searchable composite fields
    searchable_text: str
    keywords: List[str]

    # Metadata for search optimization
    complexity_level: str  # simple, moderate, complex
    usage_frequency: int  # Number of endpoint usages
    last_modified: Optional[str]


class SchemaIndexManager:
    """Manages comprehensive schema indexing and cross-referencing."""

    def __init__(
        self,
        schema_repo: SchemaRepository,
        endpoint_repo: EndpointRepository,
        config: SearchConfig,
    ):
        """Initialize the schema index manager.

        Args:
            schema_repo: Schema repository instance
            endpoint_repo: Endpoint repository instance
            config: Search configuration settings
        """
        self.schema_repo = schema_repo
        self.endpoint_repo = endpoint_repo
        self.config = config

    async def create_schema_documents(self) -> List[SchemaSearchDocument]:
        """Create comprehensive search documents for all schemas.

        Returns:
            List[SchemaSearchDocument]: Complete schema search documents

        Raises:
            RuntimeError: If schema document creation fails
        """
        try:
            # Get all normalized schemas from repository
            schemas = await self.schema_repo.get_all_schemas()
            schema_documents = []

            for schema in schemas:
                # Extract schema properties and metadata
                properties = await self._extract_schema_properties(schema)

                # Map endpoint relationships
                endpoint_usage = await self._map_endpoint_relationships(schema["id"])

                # Extract composition relationships
                composition = await self._extract_composition_info(schema)

                # Calculate complexity and usage metrics
                complexity = self._calculate_schema_complexity(schema, properties)
                usage_frequency = len(endpoint_usage["endpoints"])

                # Create comprehensive searchable document
                document = SchemaSearchDocument(
                    schema_id=schema["id"],
                    schema_name=schema.get("name", schema["id"]),
                    schema_type=schema.get("type", "object"),
                    schema_path=schema.get("path", f"#/components/schemas/{schema['id']}"),
                    description=schema.get("description", ""),
                    property_names=properties["names"],
                    property_descriptions=properties["descriptions"],
                    property_types=properties["types"],
                    required_properties=properties["required"],
                    optional_properties=properties["optional"],
                    nested_schemas=properties["nested_schemas"],
                    example_values=schema.get("examples", {}),
                    validation_rules=properties["validation_rules"],
                    used_in_endpoints=endpoint_usage["endpoints"],
                    usage_contexts=endpoint_usage["contexts"],
                    usage_details=endpoint_usage["usage_details"],
                    inherits_from=composition.get("inherits_from"),
                    extended_by=composition.get("extended_by", []),
                    composed_schemas=composition.get("composed_schemas", []),
                    composition_type=composition.get("composition_type"),
                    searchable_text=await self._create_schema_searchable_text(schema, properties),
                    keywords=await self._extract_schema_keywords(schema, properties),
                    complexity_level=complexity,
                    usage_frequency=usage_frequency,
                    last_modified=schema.get("last_modified")
                )

                schema_documents.append(document)

            return schema_documents

        except Exception as e:
            raise RuntimeError(f"Failed to create schema documents: {e}") from e

    async def _extract_schema_properties(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive property information from schema.

        Args:
            schema: Schema definition

        Returns:
            Dict[str, Any]: Extracted property information
        """
        properties_info = {
            "names": [],
            "descriptions": "",
            "types": [],
            "required": [],
            "optional": [],
            "nested_schemas": [],
            "validation_rules": {}
        }

        # Extract properties if schema is an object
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for prop_name, prop_def in properties.items():
            properties_info["names"].append(prop_name)

            # Collect property types
            prop_type = prop_def.get("type", "unknown")
            if prop_type not in properties_info["types"]:
                properties_info["types"].append(prop_type)

            # Build descriptions text
            prop_desc = prop_def.get("description", "")
            if prop_desc:
                properties_info["descriptions"] += f"{prop_name}: {prop_desc}. "

            # Categorize as required or optional
            if prop_name in required:
                properties_info["required"].append(prop_name)
            else:
                properties_info["optional"].append(prop_name)

            # Check for nested schema references
            if "$ref" in prop_def:
                ref_schema = prop_def["$ref"].split("/")[-1]
                properties_info["nested_schemas"].append(ref_schema)

            # Extract validation rules
            validation_rules = {}
            for rule in ["minimum", "maximum", "minLength", "maxLength", "pattern", "enum"]:
                if rule in prop_def:
                    validation_rules[rule] = prop_def[rule]

            if validation_rules:
                properties_info["validation_rules"][prop_name] = validation_rules

        return properties_info

    async def _map_endpoint_relationships(self, schema_id: str) -> Dict[str, Any]:
        """Map all endpoint usage relationships for a schema.

        Args:
            schema_id: Schema identifier

        Returns:
            Dict[str, Any]: Endpoint relationship mapping
        """
        relationships = {
            "endpoints": [],
            "contexts": [],
            "usage_details": []
        }

        try:
            # Find request body usage
            request_usage = await self._find_request_body_usage(schema_id)
            for usage in request_usage:
                relationships["endpoints"].append(usage["endpoint_id"])
                relationships["contexts"].append(SchemaUsageContext.REQUEST_BODY)
                relationships["usage_details"].append({
                    "endpoint_id": usage["endpoint_id"],
                    "context": SchemaUsageContext.REQUEST_BODY.value,
                    "content_type": usage.get("content_type", "application/json"),
                    "required": usage.get("required", True)
                })

            # Find response body usage
            response_usage = await self._find_response_body_usage(schema_id)
            for usage in response_usage:
                relationships["endpoints"].append(usage["endpoint_id"])
                relationships["contexts"].append(SchemaUsageContext.RESPONSE_BODY)
                relationships["usage_details"].append({
                    "endpoint_id": usage["endpoint_id"],
                    "context": SchemaUsageContext.RESPONSE_BODY.value,
                    "status_code": usage.get("status_code", "200"),
                    "content_type": usage.get("content_type", "application/json")
                })

            # Find parameter usage
            parameter_usage = await self._find_parameter_usage(schema_id)
            for usage in parameter_usage:
                relationships["endpoints"].append(usage["endpoint_id"])
                relationships["contexts"].append(SchemaUsageContext.PARAMETER)
                relationships["usage_details"].append({
                    "endpoint_id": usage["endpoint_id"],
                    "context": SchemaUsageContext.PARAMETER.value,
                    "parameter_name": usage.get("parameter_name", ""),
                    "parameter_location": usage.get("location", "query")
                })

            return relationships

        except Exception as e:
            # Return empty relationships on error
            return relationships

    async def _find_request_body_usage(self, schema_id: str) -> List[Dict[str, Any]]:
        """Find endpoints that use this schema in request bodies."""
        # This would query the database for request body usage
        # Implementation depends on how request body schemas are stored
        return []

    async def _find_response_body_usage(self, schema_id: str) -> List[Dict[str, Any]]:
        """Find endpoints that use this schema in response bodies."""
        # This would query the database for response body usage
        # Implementation depends on how response schemas are stored
        return []

    async def _find_parameter_usage(self, schema_id: str) -> List[Dict[str, Any]]:
        """Find endpoints that use this schema in parameters."""
        # This would query the database for parameter usage
        # Implementation depends on how parameter schemas are stored
        return []

    async def _extract_composition_info(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract schema composition and inheritance information.

        Args:
            schema: Schema definition

        Returns:
            Dict[str, Any]: Composition information
        """
        composition = {
            "inherits_from": None,
            "extended_by": [],
            "composed_schemas": [],
            "composition_type": None
        }

        # Check for allOf, oneOf, anyOf composition
        for comp_type in ["allOf", "oneOf", "anyOf"]:
            if comp_type in schema:
                composition["composition_type"] = comp_type
                for item in schema[comp_type]:
                    if "$ref" in item:
                        ref_schema = item["$ref"].split("/")[-1]
                        composition["composed_schemas"].append(ref_schema)

        # Check for inheritance (typically allOf with one $ref and properties)
        if "allOf" in schema and len(schema["allOf"]) == 1:
            first_item = schema["allOf"][0]
            if "$ref" in first_item and "properties" in schema:
                parent_schema = first_item["$ref"].split("/")[-1]
                composition["inherits_from"] = parent_schema

        return composition

    def _calculate_schema_complexity(
        self,
        schema: Dict[str, Any],
        properties: Dict[str, Any]
    ) -> str:
        """Calculate schema complexity level based on structure.

        Args:
            schema: Schema definition
            properties: Extracted properties information

        Returns:
            str: Complexity level (simple, moderate, complex)
        """
        # Calculate complexity score based on multiple factors
        score = 0

        # Number of properties
        prop_count = len(properties["names"])
        if prop_count > 20:
            score += 3
        elif prop_count > 10:
            score += 2
        elif prop_count > 5:
            score += 1

        # Nested schemas
        nested_count = len(properties["nested_schemas"])
        score += min(nested_count, 3)

        # Validation rules complexity
        validation_count = len(properties["validation_rules"])
        score += min(validation_count // 3, 2)

        # Composition complexity
        if "allOf" in schema or "oneOf" in schema or "anyOf" in schema:
            score += 2

        # Classify based on total score
        if score >= 6:
            return "complex"
        elif score >= 3:
            return "moderate"
        else:
            return "simple"

    async def _create_schema_searchable_text(
        self,
        schema: Dict[str, Any],
        properties: Dict[str, Any]
    ) -> str:
        """Create comprehensive searchable text for schema.

        Args:
            schema: Schema definition
            properties: Extracted properties information

        Returns:
            str: Searchable text content
        """
        text_parts = []

        # Add schema name and description
        text_parts.append(schema.get("name", schema.get("id", "")))
        description = schema.get("description", "")
        if description:
            text_parts.append(description)

        # Add property names and descriptions
        text_parts.extend(properties["names"])
        if properties["descriptions"]:
            text_parts.append(properties["descriptions"])

        # Add property types
        text_parts.extend(properties["types"])

        # Add nested schema names
        text_parts.extend(properties["nested_schemas"])

        # Add validation keywords
        for prop_rules in properties["validation_rules"].values():
            for rule_name in prop_rules.keys():
                text_parts.append(rule_name)

        return " ".join(filter(None, text_parts))

    async def _extract_schema_keywords(
        self,
        schema: Dict[str, Any],
        properties: Dict[str, Any]
    ) -> List[str]:
        """Extract keywords for schema search optimization.

        Args:
            schema: Schema definition
            properties: Extracted properties information

        Returns:
            List[str]: Schema keywords
        """
        keywords = set()

        # Add schema type and format
        keywords.add(schema.get("type", "object"))
        if "format" in schema:
            keywords.add(schema["format"])

        # Add property types as keywords
        keywords.update(properties["types"])

        # Add semantic keywords based on property names
        for prop_name in properties["names"]:
            # Common API patterns
            if "id" in prop_name.lower():
                keywords.add("identifier")
            if "name" in prop_name.lower():
                keywords.add("name")
            if "email" in prop_name.lower():
                keywords.add("email")
            if "date" in prop_name.lower() or "time" in prop_name.lower():
                keywords.add("temporal")
            if "status" in prop_name.lower():
                keywords.add("status")

        # Add composition keywords
        if "allOf" in schema:
            keywords.add("inheritance")
        if "oneOf" in schema:
            keywords.add("variant")
        if "anyOf" in schema:
            keywords.add("flexible")

        return list(keywords)