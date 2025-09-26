"""Schema-endpoint cross-reference mapping for the Swagger MCP Server.

This module provides comprehensive mapping capabilities between schemas and
endpoints, enabling bidirectional discovery and relationship analysis
as specified in Story 3.5.
"""

import asyncio
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass

from ..storage.repositories.schema_repository import SchemaRepository
from ..storage.repositories.endpoint_repository import EndpointRepository
from ..config.settings import SearchConfig
from .schema_indexing import SchemaUsageContext


@dataclass
class SchemaEndpointRelationship:
    """Represents a relationship between a schema and an endpoint."""
    schema_id: str
    endpoint_id: str
    context: SchemaUsageContext
    details: Dict[str, Any]
    bidirectional_score: float  # Relevance score for the relationship


@dataclass
class CrossReferenceMap:
    """Complete cross-reference mapping between schemas and endpoints."""
    schema_to_endpoints: Dict[str, List[Dict[str, Any]]]
    endpoint_to_schemas: Dict[str, List[Dict[str, Any]]]
    relationship_graph: List[SchemaEndpointRelationship]
    dependency_matrix: Dict[str, Set[str]]


class SchemaEndpointMapper:
    """Maps bidirectional relationships between schemas and endpoints."""

    def __init__(
        self,
        schema_repo: SchemaRepository,
        endpoint_repo: EndpointRepository,
        config: SearchConfig,
    ):
        """Initialize the schema-endpoint mapper.

        Args:
            schema_repo: Schema repository instance
            endpoint_repo: Endpoint repository instance
            config: Search configuration settings
        """
        self.schema_repo = schema_repo
        self.endpoint_repo = endpoint_repo
        self.config = config

    async def create_complete_cross_reference_map(self) -> CrossReferenceMap:
        """Create complete bidirectional cross-reference mapping.

        Returns:
            CrossReferenceMap: Complete mapping with all relationships

        Raises:
            RuntimeError: If mapping creation fails
        """
        try:
            # Get all schemas and endpoints
            schemas = await self.schema_repo.get_all_schemas()
            endpoints = await self.endpoint_repo.get_all()

            # Initialize mapping structures
            schema_to_endpoints = {}
            endpoint_to_schemas = {}
            relationship_graph = []
            dependency_matrix = {}

            # Process each schema to find its endpoint usage
            for schema in schemas:
                schema_id = schema["id"]
                schema_to_endpoints[schema_id] = []
                dependency_matrix[schema_id] = set()

                endpoint_relationships = await self._map_schema_endpoint_relationships(
                    schema_id, endpoints
                )

                for relationship in endpoint_relationships:
                    # Add to schema-to-endpoint mapping
                    schema_to_endpoints[schema_id].append({
                        "endpoint_id": relationship.endpoint_id,
                        "context": relationship.context.value,
                        "details": relationship.details,
                        "score": relationship.bidirectional_score
                    })

                    # Add to relationship graph
                    relationship_graph.append(relationship)

                    # Update dependency matrix
                    dependency_matrix[schema_id].add(relationship.endpoint_id)

            # Process each endpoint to find its schema dependencies
            for endpoint in endpoints:
                endpoint_id = endpoint.get("id", endpoint.get("endpoint_id"))
                if endpoint_id not in endpoint_to_schemas:
                    endpoint_to_schemas[endpoint_id] = []

                schema_dependencies = await self._map_endpoint_schema_dependencies(
                    endpoint_id, schemas
                )

                for schema_dep in schema_dependencies:
                    endpoint_to_schemas[endpoint_id].append(schema_dep)

            return CrossReferenceMap(
                schema_to_endpoints=schema_to_endpoints,
                endpoint_to_schemas=endpoint_to_schemas,
                relationship_graph=relationship_graph,
                dependency_matrix=dependency_matrix
            )

        except Exception as e:
            raise RuntimeError(f"Failed to create cross-reference map: {e}") from e

    async def _map_schema_endpoint_relationships(
        self,
        schema_id: str,
        endpoints: List[Dict[str, Any]]
    ) -> List[SchemaEndpointRelationship]:
        """Map all relationships between a schema and endpoints.

        Args:
            schema_id: Schema identifier
            endpoints: List of all endpoints

        Returns:
            List[SchemaEndpointRelationship]: All relationships for the schema
        """
        relationships = []

        for endpoint in endpoints:
            endpoint_id = endpoint.get("id", endpoint.get("endpoint_id"))

            # Check request body usage
            request_relationships = await self._find_request_body_relationships(
                schema_id, endpoint
            )
            relationships.extend(request_relationships)

            # Check response body usage
            response_relationships = await self._find_response_body_relationships(
                schema_id, endpoint
            )
            relationships.extend(response_relationships)

            # Check parameter usage
            parameter_relationships = await self._find_parameter_relationships(
                schema_id, endpoint
            )
            relationships.extend(parameter_relationships)

        return relationships

    async def _find_request_body_relationships(
        self,
        schema_id: str,
        endpoint: Dict[str, Any]
    ) -> List[SchemaEndpointRelationship]:
        """Find request body relationships between schema and endpoint.

        Args:
            schema_id: Schema identifier
            endpoint: Endpoint definition

        Returns:
            List[SchemaEndpointRelationship]: Request body relationships
        """
        relationships = []
        endpoint_id = endpoint.get("id", endpoint.get("endpoint_id"))

        # Check if endpoint has request body that uses this schema
        request_body = endpoint.get("request_body", {})
        if not request_body:
            return relationships

        content = request_body.get("content", {})
        for content_type, content_def in content.items():
            schema_ref = content_def.get("schema", {})

            # Direct schema reference
            if schema_ref.get("$ref", "").endswith(f"/{schema_id}"):
                relationship = SchemaEndpointRelationship(
                    schema_id=schema_id,
                    endpoint_id=endpoint_id,
                    context=SchemaUsageContext.REQUEST_BODY,
                    details={
                        "content_type": content_type,
                        "required": request_body.get("required", True),
                        "description": request_body.get("description", "")
                    },
                    bidirectional_score=self._calculate_relationship_score(
                        "request_body", content_type, request_body.get("required", True)
                    )
                )
                relationships.append(relationship)

            # Array of schemas
            elif schema_ref.get("type") == "array":
                items_ref = schema_ref.get("items", {}).get("$ref", "")
                if items_ref.endswith(f"/{schema_id}"):
                    relationship = SchemaEndpointRelationship(
                        schema_id=schema_id,
                        endpoint_id=endpoint_id,
                        context=SchemaUsageContext.REQUEST_BODY,
                        details={
                            "content_type": content_type,
                            "required": request_body.get("required", True),
                            "array_type": True,
                            "description": request_body.get("description", "")
                        },
                        bidirectional_score=self._calculate_relationship_score(
                            "request_body", content_type, request_body.get("required", True)
                        )
                    )
                    relationships.append(relationship)

        return relationships

    async def _find_response_body_relationships(
        self,
        schema_id: str,
        endpoint: Dict[str, Any]
    ) -> List[SchemaEndpointRelationship]:
        """Find response body relationships between schema and endpoint.

        Args:
            schema_id: Schema identifier
            endpoint: Endpoint definition

        Returns:
            List[SchemaEndpointRelationship]: Response body relationships
        """
        relationships = []
        endpoint_id = endpoint.get("id", endpoint.get("endpoint_id"))

        # Check responses for schema usage
        responses = endpoint.get("responses", {})
        for status_code, response_def in responses.items():
            content = response_def.get("content", {})

            for content_type, content_def in content.items():
                schema_ref = content_def.get("schema", {})

                # Direct schema reference
                if schema_ref.get("$ref", "").endswith(f"/{schema_id}"):
                    relationship = SchemaEndpointRelationship(
                        schema_id=schema_id,
                        endpoint_id=endpoint_id,
                        context=SchemaUsageContext.RESPONSE_BODY,
                        details={
                            "status_code": status_code,
                            "content_type": content_type,
                            "description": response_def.get("description", ""),
                            "success_response": status_code.startswith("2")
                        },
                        bidirectional_score=self._calculate_relationship_score(
                            "response_body", content_type, status_code.startswith("2")
                        )
                    )
                    relationships.append(relationship)

                # Array of schemas
                elif schema_ref.get("type") == "array":
                    items_ref = schema_ref.get("items", {}).get("$ref", "")
                    if items_ref.endswith(f"/{schema_id}"):
                        relationship = SchemaEndpointRelationship(
                            schema_id=schema_id,
                            endpoint_id=endpoint_id,
                            context=SchemaUsageContext.RESPONSE_BODY,
                            details={
                                "status_code": status_code,
                                "content_type": content_type,
                                "array_type": True,
                                "description": response_def.get("description", ""),
                                "success_response": status_code.startswith("2")
                            },
                            bidirectional_score=self._calculate_relationship_score(
                                "response_body", content_type, status_code.startswith("2")
                            )
                        )
                        relationships.append(relationship)

        return relationships

    async def _find_parameter_relationships(
        self,
        schema_id: str,
        endpoint: Dict[str, Any]
    ) -> List[SchemaEndpointRelationship]:
        """Find parameter relationships between schema and endpoint.

        Args:
            schema_id: Schema identifier
            endpoint: Endpoint definition

        Returns:
            List[SchemaEndpointRelationship]: Parameter relationships
        """
        relationships = []
        endpoint_id = endpoint.get("id", endpoint.get("endpoint_id"))

        # Check parameters for schema usage
        parameters = endpoint.get("parameters", [])
        for param in parameters:
            schema_ref = param.get("schema", {})

            # Direct schema reference
            if schema_ref.get("$ref", "").endswith(f"/{schema_id}"):
                relationship = SchemaEndpointRelationship(
                    schema_id=schema_id,
                    endpoint_id=endpoint_id,
                    context=SchemaUsageContext.PARAMETER,
                    details={
                        "parameter_name": param.get("name", ""),
                        "parameter_location": param.get("in", "query"),
                        "required": param.get("required", False),
                        "description": param.get("description", "")
                    },
                    bidirectional_score=self._calculate_relationship_score(
                        "parameter", param.get("in", "query"), param.get("required", False)
                    )
                )
                relationships.append(relationship)

        return relationships

    async def _map_endpoint_schema_dependencies(
        self,
        endpoint_id: str,
        schemas: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Map all schema dependencies for an endpoint.

        Args:
            endpoint_id: Endpoint identifier
            schemas: List of all schemas

        Returns:
            List[Dict[str, Any]]: Schema dependencies with details
        """
        dependencies = []

        # Get endpoint data
        endpoint = await self.endpoint_repo.get_by_id(endpoint_id)
        if not endpoint:
            return dependencies

        # Find all schema references in the endpoint
        schema_refs = self._extract_schema_references(endpoint)

        for schema_ref in schema_refs:
            # Find matching schema
            for schema in schemas:
                if schema_ref["schema_id"] == schema["id"]:
                    dependency = {
                        "schema_id": schema["id"],
                        "schema_name": schema.get("name", schema["id"]),
                        "context": schema_ref["context"],
                        "details": schema_ref["details"],
                        "complexity": self._assess_schema_complexity(schema),
                        "score": schema_ref["score"]
                    }
                    dependencies.append(dependency)
                    break

        return dependencies

    def _extract_schema_references(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all schema references from an endpoint definition.

        Args:
            endpoint: Endpoint definition

        Returns:
            List[Dict[str, Any]]: Schema references with context
        """
        references = []

        # Extract from request body
        request_body = endpoint.get("request_body", {})
        if request_body:
            refs = self._extract_refs_from_content(
                request_body.get("content", {}),
                "request_body",
                {"required": request_body.get("required", True)}
            )
            references.extend(refs)

        # Extract from responses
        responses = endpoint.get("responses", {})
        for status_code, response in responses.items():
            refs = self._extract_refs_from_content(
                response.get("content", {}),
                "response_body",
                {
                    "status_code": status_code,
                    "success_response": status_code.startswith("2")
                }
            )
            references.extend(refs)

        # Extract from parameters
        parameters = endpoint.get("parameters", [])
        for param in parameters:
            schema_ref = param.get("schema", {}).get("$ref", "")
            if schema_ref:
                schema_id = schema_ref.split("/")[-1]
                references.append({
                    "schema_id": schema_id,
                    "context": "parameter",
                    "details": {
                        "parameter_name": param.get("name", ""),
                        "parameter_location": param.get("in", "query"),
                        "required": param.get("required", False)
                    },
                    "score": self._calculate_relationship_score(
                        "parameter", param.get("in", "query"), param.get("required", False)
                    )
                })

        return references

    def _extract_refs_from_content(
        self,
        content: Dict[str, Any],
        context: str,
        base_details: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract schema references from content definitions.

        Args:
            content: Content definition (e.g., from request/response body)
            context: Usage context
            base_details: Base details for the reference

        Returns:
            List[Dict[str, Any]]: Schema references
        """
        references = []

        for content_type, content_def in content.items():
            schema_ref = content_def.get("schema", {})

            # Direct reference
            ref_url = schema_ref.get("$ref", "")
            if ref_url:
                schema_id = ref_url.split("/")[-1]
                details = {**base_details, "content_type": content_type}
                references.append({
                    "schema_id": schema_id,
                    "context": context,
                    "details": details,
                    "score": self._calculate_relationship_score(
                        context, content_type, details.get("required", True)
                    )
                })

            # Array type
            elif schema_ref.get("type") == "array":
                items_ref = schema_ref.get("items", {}).get("$ref", "")
                if items_ref:
                    schema_id = items_ref.split("/")[-1]
                    details = {**base_details, "content_type": content_type, "array_type": True}
                    references.append({
                        "schema_id": schema_id,
                        "context": context,
                        "details": details,
                        "score": self._calculate_relationship_score(
                            context, content_type, details.get("required", True)
                        )
                    })

        return references

    def _calculate_relationship_score(
        self,
        context: str,
        type_or_location: str,
        importance_factor: bool
    ) -> float:
        """Calculate a relevance score for a schema-endpoint relationship.

        Args:
            context: Usage context (request_body, response_body, parameter)
            type_or_location: Content type or parameter location
            importance_factor: Factor indicating importance (required, success, etc.)

        Returns:
            float: Relationship score (0.0 to 1.0)
        """
        base_score = 0.5

        # Context importance
        context_weights = {
            "request_body": 0.9,    # High importance for input validation
            "response_body": 0.8,   # High importance for output understanding
            "parameter": 0.6        # Moderate importance
        }
        base_score *= context_weights.get(context, 0.5)

        # Content type or location importance
        if context in ["request_body", "response_body"]:
            if type_or_location == "application/json":
                base_score *= 1.0  # Standard JSON is most important
            elif type_or_location.startswith("application/"):
                base_score *= 0.8
            else:
                base_score *= 0.6
        elif context == "parameter":
            location_weights = {
                "path": 1.0,      # Path parameters are critical
                "query": 0.8,     # Query parameters are common
                "header": 0.6,    # Headers are less common
                "cookie": 0.4     # Cookies are least common
            }
            base_score *= location_weights.get(type_or_location, 0.5)

        # Importance factor (required, success response, etc.)
        if importance_factor:
            base_score *= 1.2  # Boost for important relationships

        return min(base_score, 1.0)  # Cap at 1.0

    def _assess_schema_complexity(self, schema: Dict[str, Any]) -> str:
        """Assess the complexity of a schema for dependency analysis.

        Args:
            schema: Schema definition

        Returns:
            str: Complexity level (simple, moderate, complex)
        """
        complexity_score = 0

        # Property count
        properties = schema.get("properties", {})
        prop_count = len(properties)
        if prop_count > 15:
            complexity_score += 3
        elif prop_count > 8:
            complexity_score += 2
        elif prop_count > 3:
            complexity_score += 1

        # Nested references
        nested_refs = 0
        for prop in properties.values():
            if "$ref" in prop or (prop.get("type") == "array" and "$ref" in prop.get("items", {})):
                nested_refs += 1
        complexity_score += min(nested_refs, 3)

        # Composition patterns
        if any(key in schema for key in ["allOf", "oneOf", "anyOf"]):
            complexity_score += 2

        # Required properties ratio
        required = schema.get("required", [])
        if len(required) > prop_count * 0.7:  # More than 70% required
            complexity_score += 1

        # Classify complexity
        if complexity_score >= 6:
            return "complex"
        elif complexity_score >= 3:
            return "moderate"
        else:
            return "simple"