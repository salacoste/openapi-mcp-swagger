"""Unified search interface for endpoints and schemas in the Swagger MCP Server.

This module provides a comprehensive search interface that seamlessly integrates
endpoint and schema search results with cross-referencing capabilities
as specified in Story 3.5.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from ..config.settings import SearchConfig
from .schema_indexing import SchemaIndexManager, SchemaSearchDocument
from .schema_mapper import CrossReferenceMap, SchemaEndpointMapper
from .schema_relationships import SchemaGraph, SchemaRelationshipDiscovery
from .search_engine import SearchEngine


class SearchType(Enum):
    """Types of unified search."""

    ENDPOINTS_ONLY = "endpoints"
    SCHEMAS_ONLY = "schemas"
    MIXED = "mixed"
    ALL = "all"


class ResultType(Enum):
    """Types of search results."""

    ENDPOINT = "endpoint"
    SCHEMA = "schema"
    CROSS_REFERENCE = "cross_reference"


@dataclass
class UnifiedSearchResult:
    """Unified search result that can represent endpoints or schemas."""

    result_id: str
    result_type: ResultType
    title: str
    description: str
    score: float
    highlights: Dict[str, str]
    metadata: Dict[str, Any]
    relationships: Optional[List[Dict[str, Any]]] = None


@dataclass
class UnifiedSearchResponse:
    """Complete unified search response with all result types."""

    query: str
    search_types: List[str]
    total_results: int
    query_time: float
    results: List[UnifiedSearchResult]
    organization: Dict[str, Any]
    cross_references: Dict[str, Any]
    suggestions: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class UnifiedSearchInterface:
    """Unified search interface supporting endpoints, schemas, and cross-references."""

    def __init__(
        self,
        search_engine: SearchEngine,
        schema_index_manager: SchemaIndexManager,
        schema_mapper: SchemaEndpointMapper,
        relationship_discovery: SchemaRelationshipDiscovery,
        config: SearchConfig,
    ):
        """Initialize the unified search interface.

        Args:
            search_engine: Endpoint search engine
            schema_index_manager: Schema indexing manager
            schema_mapper: Schema-endpoint mapper
            relationship_discovery: Schema relationship discovery
            config: Search configuration settings
        """
        self.search_engine = search_engine
        self.schema_index_manager = schema_index_manager
        self.schema_mapper = schema_mapper
        self.relationship_discovery = relationship_discovery
        self.config = config

        # Cache for performance optimization
        self._cross_reference_cache: Optional[CrossReferenceMap] = None
        self._schema_graph_cache: Optional[SchemaGraph] = None

    async def unified_search(
        self,
        query: str,
        search_types: List[str] = ["all"],
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        per_page: int = 20,
        include_cross_references: bool = True,
        include_organization: bool = True,
        include_suggestions: bool = True,
    ) -> UnifiedSearchResponse:
        """Perform unified search across endpoints and schemas.

        Args:
            query: Search query string
            search_types: Types of search to perform
            filters: Search filters
            page: Page number (1-based)
            per_page: Results per page
            include_cross_references: Whether to include cross-references
            include_organization: Whether to organize results
            include_suggestions: Whether to include query suggestions

        Returns:
            UnifiedSearchResponse: Complete unified search response

        Raises:
            ValueError: If query is empty or invalid parameters
            RuntimeError: If unified search operation fails
        """
        if not query.strip():
            raise ValueError("Search query cannot be empty")

        if page < 1:
            raise ValueError("Page number must be >= 1")

        if per_page < 1 or per_page > self.config.performance.max_search_results:
            raise ValueError(
                f"per_page must be between 1 and {self.config.performance.max_search_results}"
            )

        start_time = asyncio.get_event_loop().time()

        try:
            # Determine which search types to execute
            execute_endpoints = any(
                t in search_types for t in ["endpoints", "mixed", "all"]
            )
            execute_schemas = any(
                t in search_types for t in ["schemas", "mixed", "all"]
            )

            # Initialize result containers
            all_results = []
            endpoint_results = []
            schema_results = []

            # Execute endpoint search
            if execute_endpoints:
                endpoint_search_response = await self.search_engine.search_advanced(
                    query=query,
                    filters=filters,
                    page=1,  # Get all for unified processing
                    per_page=self.config.performance.max_search_results,
                    include_organization=False,
                    include_metadata=True,
                )

                endpoint_results = endpoint_search_response.get("results", [])

                # Convert endpoint results to unified format
                for result in endpoint_results:
                    unified_result = UnifiedSearchResult(
                        result_id=result["endpoint_id"],
                        result_type=ResultType.ENDPOINT,
                        title=f"{result['http_method']} {result['endpoint_path']}",
                        description=result.get(
                            "summary", result.get("description", "")
                        ),
                        score=result["score"],
                        highlights=result.get("highlights", {}),
                        metadata={
                            "endpoint_path": result["endpoint_path"],
                            "http_method": result["http_method"],
                            "tags": result.get("tags", ""),
                            "deprecated": result.get("deprecated", False),
                            "operation_type": result.get("operation_type", ""),
                            "complexity_level": result.get("complexity_level", ""),
                            "authentication_info": result.get(
                                "authentication_info", {}
                            ),
                        },
                    )
                    all_results.append(unified_result)

            # Execute schema search
            if execute_schemas:
                schema_documents = (
                    await self.schema_index_manager.create_schema_documents()
                )
                schema_results = await self._search_schemas(
                    query, schema_documents, filters
                )

                # Convert schema results to unified format
                for result in schema_results:
                    unified_result = UnifiedSearchResult(
                        result_id=result["schema_id"],
                        result_type=ResultType.SCHEMA,
                        title=result["schema_name"],
                        description=result.get("description", ""),
                        score=result["score"],
                        highlights=result.get("highlights", {}),
                        metadata={
                            "schema_type": result["schema_type"],
                            "property_count": len(result.get("property_names", [])),
                            "complexity_level": result.get("complexity_level", ""),
                            "usage_frequency": result.get("usage_frequency", 0),
                            "composition_type": result.get("composition_type"),
                            "validation_rules": result.get("validation_rules", {}),
                        },
                    )
                    all_results.append(unified_result)

            # Generate cross-references if requested
            cross_references = {}
            if include_cross_references and endpoint_results and schema_results:
                cross_references = await self._generate_cross_references(
                    endpoint_results, schema_results
                )

                # Add relationships to results
                await self._enrich_results_with_relationships(
                    all_results, cross_references
                )

            # Organize results if requested
            organization = {}
            if include_organization:
                organization = await self._organize_unified_results(all_results, query)

            # Apply intelligent ranking to mixed results
            ranked_results = self._rank_unified_results(
                all_results, query, search_types
            )

            # Apply pagination
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_results = ranked_results[start_idx:end_idx]

            # Generate suggestions if requested
            suggestions = []
            if include_suggestions and len(ranked_results) < 10:
                suggestions = await self._generate_unified_suggestions(
                    query, len(ranked_results), search_types
                )

            query_time = asyncio.get_event_loop().time() - start_time

            return UnifiedSearchResponse(
                query=query,
                search_types=search_types,
                total_results=len(ranked_results),
                query_time=query_time,
                results=paginated_results,
                organization=organization,
                cross_references=cross_references,
                suggestions=suggestions,
                metadata={
                    "endpoint_results_count": len(endpoint_results),
                    "schema_results_count": len(schema_results),
                    "cross_references_found": len(cross_references),
                    "page": page,
                    "per_page": per_page,
                    "has_more": len(ranked_results) > (page * per_page),
                },
            )

        except Exception as e:
            raise RuntimeError(f"Unified search operation failed: {e}") from e

    async def _search_schemas(
        self,
        query: str,
        schema_documents: List[SchemaSearchDocument],
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search schemas using the provided query.

        Args:
            query: Search query
            schema_documents: Schema search documents
            filters: Optional filters

        Returns:
            List[Dict[str, Any]]: Schema search results
        """
        results = []
        query_lower = query.lower()

        for doc in schema_documents:
            score = 0.0

            # Score based on schema name match
            if query_lower in doc.schema_name.lower():
                score += 2.0

            # Score based on description match
            if query_lower in doc.description.lower():
                score += 1.5

            # Score based on property names
            for prop_name in doc.property_names:
                if query_lower in prop_name.lower():
                    score += 1.0

            # Score based on property descriptions
            if query_lower in doc.property_descriptions.lower():
                score += 0.8

            # Score based on keywords
            for keyword in doc.keywords:
                if query_lower in keyword.lower():
                    score += 0.5

            # Score based on searchable text
            if query_lower in doc.searchable_text.lower():
                score += 0.3

            # Apply usage frequency bonus
            if doc.usage_frequency > 0:
                score *= 1.0 + (doc.usage_frequency * 0.1)

            # Apply complexity penalty for very complex schemas
            if doc.complexity_level == "complex":
                score *= 0.9

            # Only include results with meaningful scores
            if score > 0.1:
                result = {
                    "schema_id": doc.schema_id,
                    "schema_name": doc.schema_name,
                    "schema_type": doc.schema_type,
                    "description": doc.description,
                    "score": score,
                    "property_names": doc.property_names,
                    "complexity_level": doc.complexity_level,
                    "usage_frequency": doc.usage_frequency,
                    "composition_type": doc.composition_type,
                    "validation_rules": doc.validation_rules,
                    "highlights": self._generate_schema_highlights(doc, query),
                    "used_in_endpoints": doc.used_in_endpoints,
                }

                # Apply filters if provided
                if self._passes_schema_filters(result, filters):
                    results.append(result)

        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)

        return results

    def _generate_schema_highlights(
        self, doc: SchemaSearchDocument, query: str
    ) -> Dict[str, str]:
        """Generate highlights for schema search results.

        Args:
            doc: Schema search document
            query: Search query

        Returns:
            Dict[str, str]: Highlights for different fields
        """
        highlights = {}
        query_lower = query.lower()

        # Highlight schema name
        if query_lower in doc.schema_name.lower():
            highlights["schema_name"] = self._highlight_text(doc.schema_name, query)

        # Highlight description
        if query_lower in doc.description.lower():
            highlights["description"] = self._highlight_text(doc.description, query)

        # Highlight matching property names
        matching_props = [
            prop for prop in doc.property_names if query_lower in prop.lower()
        ]
        if matching_props:
            highlights["properties"] = ", ".join(matching_props)

        return highlights

    def _highlight_text(self, text: str, query: str) -> str:
        """Add highlighting to text for matching query terms.

        Args:
            text: Text to highlight
            query: Query terms

        Returns:
            str: Highlighted text
        """
        # Simple highlighting implementation
        # In a production system, this would use proper highlighting
        highlighted = text
        for term in query.split():
            highlighted = highlighted.replace(
                term,
                f"<mark>{term}</mark>",
                1,  # Only highlight first occurrence
            )
        return highlighted

    def _passes_schema_filters(
        self, schema_result: Dict[str, Any], filters: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if schema result passes the provided filters.

        Args:
            schema_result: Schema search result
            filters: Filter criteria

        Returns:
            bool: True if result passes filters
        """
        if not filters:
            return True

        schema_filters = filters.get("schema_filters", {})
        if not schema_filters:
            return True

        # Filter by schema type
        if "schema_types" in schema_filters:
            allowed_types = schema_filters["schema_types"]
            if schema_result["schema_type"] not in allowed_types:
                return False

        # Filter by complexity
        if "complexity_levels" in schema_filters:
            allowed_complexity = schema_filters["complexity_levels"]
            if schema_result["complexity_level"] not in allowed_complexity:
                return False

        # Filter by usage frequency
        if "min_usage_frequency" in schema_filters:
            min_usage = schema_filters["min_usage_frequency"]
            if schema_result["usage_frequency"] < min_usage:
                return False

        return True

    async def _generate_cross_references(
        self,
        endpoint_results: List[Dict[str, Any]],
        schema_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate cross-references between endpoint and schema results.

        Args:
            endpoint_results: Endpoint search results
            schema_results: Schema search results

        Returns:
            Dict[str, Any]: Cross-reference information
        """
        if not self._cross_reference_cache:
            self._cross_reference_cache = (
                await self.schema_mapper.create_complete_cross_reference_map()
            )

        cross_refs = self._cross_reference_cache
        result_cross_refs = {
            "endpoint_to_schema": {},
            "schema_to_endpoint": {},
            "related_pairs": [],
        }

        # Map endpoints to their schemas
        for endpoint in endpoint_results:
            endpoint_id = endpoint["endpoint_id"]
            if endpoint_id in cross_refs.endpoint_to_schemas:
                result_cross_refs["endpoint_to_schema"][
                    endpoint_id
                ] = cross_refs.endpoint_to_schemas[endpoint_id]

        # Map schemas to their endpoints
        for schema in schema_results:
            schema_id = schema["schema_id"]
            if schema_id in cross_refs.schema_to_endpoints:
                result_cross_refs["schema_to_endpoint"][
                    schema_id
                ] = cross_refs.schema_to_endpoints[schema_id]

        # Find related pairs
        for endpoint in endpoint_results:
            for schema in schema_results:
                if self._are_related(
                    endpoint["endpoint_id"], schema["schema_id"], cross_refs
                ):
                    result_cross_refs["related_pairs"].append(
                        {
                            "endpoint_id": endpoint["endpoint_id"],
                            "schema_id": schema["schema_id"],
                            "relationship_type": self._get_relationship_type(
                                endpoint["endpoint_id"],
                                schema["schema_id"],
                                cross_refs,
                            ),
                        }
                    )

        return result_cross_refs

    def _are_related(
        self, endpoint_id: str, schema_id: str, cross_refs: CrossReferenceMap
    ) -> bool:
        """Check if endpoint and schema are related."""
        # Check if endpoint uses schema
        if endpoint_id in cross_refs.endpoint_to_schemas:
            for schema_dep in cross_refs.endpoint_to_schemas[endpoint_id]:
                if schema_dep["schema_id"] == schema_id:
                    return True

        # Check if schema is used by endpoint
        if schema_id in cross_refs.schema_to_endpoints:
            for endpoint_usage in cross_refs.schema_to_endpoints[schema_id]:
                if endpoint_usage["endpoint_id"] == endpoint_id:
                    return True

        return False

    def _get_relationship_type(
        self, endpoint_id: str, schema_id: str, cross_refs: CrossReferenceMap
    ) -> Optional[str]:
        """Get the type of relationship between endpoint and schema."""
        if endpoint_id in cross_refs.endpoint_to_schemas:
            for schema_dep in cross_refs.endpoint_to_schemas[endpoint_id]:
                if schema_dep["schema_id"] == schema_id:
                    return schema_dep["context"]
        return None

    async def _enrich_results_with_relationships(
        self,
        results: List[UnifiedSearchResult],
        cross_references: Dict[str, Any],
    ) -> None:
        """Enrich search results with relationship information."""
        for result in results:
            relationships = []

            if result.result_type == ResultType.ENDPOINT:
                # Add schema relationships for endpoints
                endpoint_id = result.result_id
                if endpoint_id in cross_references.get("endpoint_to_schema", {}):
                    schema_deps = cross_references["endpoint_to_schema"][endpoint_id]
                    for schema_dep in schema_deps:
                        relationships.append(
                            {
                                "type": "uses_schema",
                                "target_id": schema_dep["schema_id"],
                                "target_type": "schema",
                                "context": schema_dep["context"],
                                "details": schema_dep.get("details", {}),
                            }
                        )

            elif result.result_type == ResultType.SCHEMA:
                # Add endpoint relationships for schemas
                schema_id = result.result_id
                if schema_id in cross_references.get("schema_to_endpoint", {}):
                    endpoint_usages = cross_references["schema_to_endpoint"][schema_id]
                    for endpoint_usage in endpoint_usages:
                        relationships.append(
                            {
                                "type": "used_by_endpoint",
                                "target_id": endpoint_usage["endpoint_id"],
                                "target_type": "endpoint",
                                "context": endpoint_usage["context"],
                                "details": endpoint_usage.get("details", {}),
                            }
                        )

            result.relationships = relationships

    async def _organize_unified_results(
        self, results: List[UnifiedSearchResult], query: str
    ) -> Dict[str, Any]:
        """Organize unified search results into meaningful categories."""
        organization = {
            "by_type": {"endpoints": 0, "schemas": 0},
            "by_complexity": {"simple": 0, "moderate": 0, "complex": 0},
            "by_relevance": {"high": [], "medium": [], "low": []},
            "top_matches": [],
            "related_groups": [],
        }

        # Count by type
        for result in results:
            if result.result_type == ResultType.ENDPOINT:
                organization["by_type"]["endpoints"] += 1
            elif result.result_type == ResultType.SCHEMA:
                organization["by_type"]["schemas"] += 1

        # Organize by complexity
        for result in results:
            complexity = result.metadata.get("complexity_level", "simple")
            if complexity in organization["by_complexity"]:
                organization["by_complexity"][complexity] += 1

        # Organize by relevance
        for result in results:
            if result.score >= 0.8:
                organization["by_relevance"]["high"].append(result.result_id)
            elif result.score >= 0.5:
                organization["by_relevance"]["medium"].append(result.result_id)
            else:
                organization["by_relevance"]["low"].append(result.result_id)

        # Identify top matches
        organization["top_matches"] = [
            {"id": r.result_id, "type": r.result_type.value, "score": r.score}
            for r in sorted(results, key=lambda x: x.score, reverse=True)[:5]
        ]

        return organization

    def _rank_unified_results(
        self,
        results: List[UnifiedSearchResult],
        query: str,
        search_types: List[str],
    ) -> List[UnifiedSearchResult]:
        """Apply intelligent ranking to unified search results."""
        # Apply type-specific boosts based on search type preferences
        type_boosts = {
            "endpoints": {"endpoint": 1.0, "schema": 0.8},
            "schemas": {"endpoint": 0.8, "schema": 1.0},
            "mixed": {"endpoint": 1.0, "schema": 1.0},
            "all": {"endpoint": 1.0, "schema": 1.0},
        }

        primary_search_type = search_types[0] if search_types else "all"
        boosts = type_boosts.get(primary_search_type, type_boosts["all"])

        # Adjust scores based on type preferences
        for result in results:
            type_key = result.result_type.value
            if type_key in boosts:
                result.score *= boosts[type_key]

        # Sort by adjusted score
        return sorted(results, key=lambda x: x.score, reverse=True)

    async def _generate_unified_suggestions(
        self, query: str, result_count: int, search_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate suggestions for improving unified search results."""
        suggestions = []

        # Low result count suggestions
        if result_count < 5:
            suggestions.append(
                {
                    "type": "broaden_search",
                    "suggestion": f"Try broader terms instead of '{query}'",
                    "description": "Use more general terms to find related content",
                }
            )

            # Suggest alternative search types
            if "endpoints" in search_types and "schemas" not in search_types:
                suggestions.append(
                    {
                        "type": "expand_search_type",
                        "suggestion": "Include schema search",
                        "description": "Search schemas to find data models related to your query",
                    }
                )

            if "schemas" in search_types and "endpoints" not in search_types:
                suggestions.append(
                    {
                        "type": "expand_search_type",
                        "suggestion": "Include endpoint search",
                        "description": "Search endpoints to find APIs that use related schemas",
                    }
                )

        return suggestions
