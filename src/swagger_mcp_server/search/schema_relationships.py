"""Schema relationship discovery system for the Swagger MCP Server.

This module provides comprehensive schema relationship analysis including
inheritance, composition, dependencies, and usage pattern discovery
as specified in Story 3.5.
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Set, Tuple
from enum import Enum

from ..storage.repositories.schema_repository import SchemaRepository
from ..config.settings import SearchConfig


class RelationshipType(Enum):
    """Types of schema relationships."""
    INHERITANCE = "inheritance"        # allOf with single $ref + properties
    COMPOSITION = "composition"        # allOf, oneOf, anyOf patterns
    REFERENCE = "reference"           # Direct $ref usage
    ARRAY_ITEMS = "array_items"       # Array items reference
    NESTED_PROPERTY = "nested_property" # Property with $ref
    CIRCULAR = "circular"             # Circular dependency


@dataclass
class SchemaRelationship:
    """Represents a relationship between two schemas."""
    source_schema_id: str
    target_schema_id: str
    relationship_type: RelationshipType
    context: str  # Where the relationship occurs
    details: Dict[str, Any]
    strength: float  # Relationship strength (0.0 to 1.0)
    is_bidirectional: bool = False


@dataclass
class SchemaGraph:
    """Complete schema relationship graph."""
    nodes: Dict[str, Dict[str, Any]]  # Schema nodes with metadata
    edges: List[SchemaRelationship]   # Relationships between schemas
    dependency_chains: List[List[str]]  # Dependency chains
    circular_dependencies: List[List[str]]  # Circular dependency cycles
    inheritance_trees: Dict[str, List[str]]  # Inheritance hierarchies


class SchemaRelationshipDiscovery:
    """Discovers and analyzes relationships between API schemas."""

    def __init__(
        self,
        schema_repo: SchemaRepository,
        config: SearchConfig,
    ):
        """Initialize the schema relationship discovery system.

        Args:
            schema_repo: Schema repository instance
            config: Search configuration settings
        """
        self.schema_repo = schema_repo
        self.config = config

    async def discover_all_relationships(self) -> SchemaGraph:
        """Discover all relationships between schemas in the API.

        Returns:
            SchemaGraph: Complete schema relationship graph

        Raises:
            RuntimeError: If relationship discovery fails
        """
        try:
            # Get all schemas
            schemas = await self.schema_repo.get_all_schemas()

            # Create schema nodes
            nodes = {}
            for schema in schemas:
                nodes[schema["id"]] = {
                    "name": schema.get("name", schema["id"]),
                    "type": schema.get("type", "object"),
                    "properties_count": len(schema.get("properties", {})),
                    "required_count": len(schema.get("required", [])),
                    "description": schema.get("description", ""),
                    "complexity": self._assess_schema_complexity(schema)
                }

            # Discover all types of relationships
            edges = []

            # Find inheritance relationships
            inheritance_edges = await self._discover_inheritance_relationships(schemas)
            edges.extend(inheritance_edges)

            # Find composition relationships
            composition_edges = await self._discover_composition_relationships(schemas)
            edges.extend(composition_edges)

            # Find reference relationships
            reference_edges = await self._discover_reference_relationships(schemas)
            edges.extend(reference_edges)

            # Analyze dependency chains
            dependency_chains = self._analyze_dependency_chains(edges)

            # Detect circular dependencies
            circular_dependencies = self._detect_circular_dependencies(edges)

            # Build inheritance trees
            inheritance_trees = self._build_inheritance_trees(inheritance_edges)

            return SchemaGraph(
                nodes=nodes,
                edges=edges,
                dependency_chains=dependency_chains,
                circular_dependencies=circular_dependencies,
                inheritance_trees=inheritance_trees
            )

        except Exception as e:
            raise RuntimeError(f"Failed to discover schema relationships: {e}") from e

    async def _discover_inheritance_relationships(
        self,
        schemas: List[Dict[str, Any]]
    ) -> List[SchemaRelationship]:
        """Discover inheritance relationships between schemas.

        Args:
            schemas: List of all schemas

        Returns:
            List[SchemaRelationship]: Inheritance relationships
        """
        relationships = []

        for schema in schemas:
            schema_id = schema["id"]

            # Check for allOf inheritance pattern
            all_of = schema.get("allOf", [])
            if len(all_of) == 1 and "$ref" in all_of[0] and "properties" in schema:
                # Single allOf with additional properties = inheritance
                parent_ref = all_of[0]["$ref"]
                parent_id = parent_ref.split("/")[-1]

                relationship = SchemaRelationship(
                    source_schema_id=schema_id,
                    target_schema_id=parent_id,
                    relationship_type=RelationshipType.INHERITANCE,
                    context="allOf_inheritance",
                    details={
                        "parent_ref": parent_ref,
                        "additional_properties": list(schema.get("properties", {}).keys()),
                        "inheritance_pattern": "single_allOf_with_properties"
                    },
                    strength=0.9,  # High strength for clear inheritance
                    is_bidirectional=False
                )
                relationships.append(relationship)

            # Check for discriminator-based inheritance
            discriminator = schema.get("discriminator")
            if discriminator:
                mapping = discriminator.get("mapping", {})
                for discriminator_value, schema_ref in mapping.items():
                    child_id = schema_ref.split("/")[-1]

                    relationship = SchemaRelationship(
                        source_schema_id=child_id,
                        target_schema_id=schema_id,
                        relationship_type=RelationshipType.INHERITANCE,
                        context="discriminator_inheritance",
                        details={
                            "discriminator_property": discriminator.get("propertyName"),
                            "discriminator_value": discriminator_value,
                            "inheritance_pattern": "discriminator_mapping"
                        },
                        strength=0.85,
                        is_bidirectional=False
                    )
                    relationships.append(relationship)

        return relationships

    async def _discover_composition_relationships(
        self,
        schemas: List[Dict[str, Any]]
    ) -> List[SchemaRelationship]:
        """Discover composition relationships between schemas.

        Args:
            schemas: List of all schemas

        Returns:
            List[SchemaRelationship]: Composition relationships
        """
        relationships = []

        for schema in schemas:
            schema_id = schema["id"]

            # Check allOf composition (multiple schemas combined)
            all_of = schema.get("allOf", [])
            if len(all_of) > 1:
                for i, component in enumerate(all_of):
                    if "$ref" in component:
                        target_id = component["$ref"].split("/")[-1]

                        relationship = SchemaRelationship(
                            source_schema_id=schema_id,
                            target_schema_id=target_id,
                            relationship_type=RelationshipType.COMPOSITION,
                            context="allOf_composition",
                            details={
                                "composition_type": "allOf",
                                "component_index": i,
                                "total_components": len(all_of),
                                "ref": component["$ref"]
                            },
                            strength=0.8,
                            is_bidirectional=False
                        )
                        relationships.append(relationship)

            # Check oneOf composition (alternative schemas)
            one_of = schema.get("oneOf", [])
            for i, component in enumerate(one_of):
                if "$ref" in component:
                    target_id = component["$ref"].split("/")[-1]

                    relationship = SchemaRelationship(
                        source_schema_id=schema_id,
                        target_schema_id=target_id,
                        relationship_type=RelationshipType.COMPOSITION,
                        context="oneOf_composition",
                        details={
                            "composition_type": "oneOf",
                            "alternative_index": i,
                            "total_alternatives": len(one_of),
                            "ref": component["$ref"]
                        },
                        strength=0.7,
                        is_bidirectional=False
                    )
                    relationships.append(relationship)

            # Check anyOf composition (flexible schemas)
            any_of = schema.get("anyOf", [])
            for i, component in enumerate(any_of):
                if "$ref" in component:
                    target_id = component["$ref"].split("/")[-1]

                    relationship = SchemaRelationship(
                        source_schema_id=schema_id,
                        target_schema_id=target_id,
                        relationship_type=RelationshipType.COMPOSITION,
                        context="anyOf_composition",
                        details={
                            "composition_type": "anyOf",
                            "option_index": i,
                            "total_options": len(any_of),
                            "ref": component["$ref"]
                        },
                        strength=0.6,
                        is_bidirectional=False
                    )
                    relationships.append(relationship)

        return relationships

    async def _discover_reference_relationships(
        self,
        schemas: List[Dict[str, Any]]
    ) -> List[SchemaRelationship]:
        """Discover direct reference relationships between schemas.

        Args:
            schemas: List of all schemas

        Returns:
            List[SchemaRelationship]: Reference relationships
        """
        relationships = []

        for schema in schemas:
            schema_id = schema["id"]

            # Check property references
            properties = schema.get("properties", {})
            for prop_name, prop_def in properties.items():
                # Direct property reference
                if "$ref" in prop_def:
                    target_id = prop_def["$ref"].split("/")[-1]

                    relationship = SchemaRelationship(
                        source_schema_id=schema_id,
                        target_schema_id=target_id,
                        relationship_type=RelationshipType.NESTED_PROPERTY,
                        context=f"property_{prop_name}",
                        details={
                            "property_name": prop_name,
                            "property_description": prop_def.get("description", ""),
                            "ref": prop_def["$ref"],
                            "is_required": prop_name in schema.get("required", [])
                        },
                        strength=0.8 if prop_name in schema.get("required", []) else 0.6,
                        is_bidirectional=False
                    )
                    relationships.append(relationship)

                # Array items reference
                elif prop_def.get("type") == "array" and "$ref" in prop_def.get("items", {}):
                    target_id = prop_def["items"]["$ref"].split("/")[-1]

                    relationship = SchemaRelationship(
                        source_schema_id=schema_id,
                        target_schema_id=target_id,
                        relationship_type=RelationshipType.ARRAY_ITEMS,
                        context=f"array_property_{prop_name}",
                        details={
                            "property_name": prop_name,
                            "array_description": prop_def.get("description", ""),
                            "items_ref": prop_def["items"]["$ref"],
                            "is_required": prop_name in schema.get("required", [])
                        },
                        strength=0.7,
                        is_bidirectional=False
                    )
                    relationships.append(relationship)

                # Nested object with properties containing references
                elif prop_def.get("type") == "object" and "properties" in prop_def:
                    nested_props = prop_def["properties"]
                    for nested_prop_name, nested_prop_def in nested_props.items():
                        if "$ref" in nested_prop_def:
                            target_id = nested_prop_def["$ref"].split("/")[-1]

                            relationship = SchemaRelationship(
                                source_schema_id=schema_id,
                                target_schema_id=target_id,
                                relationship_type=RelationshipType.NESTED_PROPERTY,
                                context=f"nested_property_{prop_name}.{nested_prop_name}",
                                details={
                                    "parent_property": prop_name,
                                    "nested_property": nested_prop_name,
                                    "ref": nested_prop_def["$ref"],
                                    "nesting_level": 2
                                },
                                strength=0.5,  # Lower strength for nested references
                                is_bidirectional=False
                            )
                            relationships.append(relationship)

            # Check additional properties
            additional_props = schema.get("additionalProperties")
            if isinstance(additional_props, dict) and "$ref" in additional_props:
                target_id = additional_props["$ref"].split("/")[-1]

                relationship = SchemaRelationship(
                    source_schema_id=schema_id,
                    target_schema_id=target_id,
                    relationship_type=RelationshipType.REFERENCE,
                    context="additional_properties",
                    details={
                        "ref": additional_props["$ref"],
                        "allows_additional": True
                    },
                    strength=0.4,  # Lower strength for additional properties
                    is_bidirectional=False
                )
                relationships.append(relationship)

        return relationships

    def _analyze_dependency_chains(
        self,
        relationships: List[SchemaRelationship]
    ) -> List[List[str]]:
        """Analyze dependency chains between schemas.

        Args:
            relationships: List of all relationships

        Returns:
            List[List[str]]: Dependency chains (ordered lists of schema IDs)
        """
        # Build adjacency list
        graph = {}
        for rel in relationships:
            if rel.source_schema_id not in graph:
                graph[rel.source_schema_id] = []
            graph[rel.source_schema_id].append(rel.target_schema_id)

        # Find dependency chains using DFS
        chains = []
        visited_global = set()

        def dfs_chains(node: str, current_chain: List[str], visited_local: Set[str]):
            if node in visited_local:  # Cycle detected
                return

            visited_local.add(node)
            current_chain.append(node)

            # If node has dependencies, continue the chain
            if node in graph and graph[node]:
                for neighbor in graph[node]:
                    dfs_chains(neighbor, current_chain.copy(), visited_local.copy())
            else:
                # End of chain, add if meaningful length
                if len(current_chain) > 1:
                    chains.append(current_chain)

        # Start DFS from all unvisited nodes
        for rel in relationships:
            if rel.source_schema_id not in visited_global:
                dfs_chains(rel.source_schema_id, [], set())
                visited_global.add(rel.source_schema_id)

        # Sort chains by length (longest first)
        chains.sort(key=len, reverse=True)

        return chains[:20]  # Return top 20 longest chains

    def _detect_circular_dependencies(
        self,
        relationships: List[SchemaRelationship]
    ) -> List[List[str]]:
        """Detect circular dependencies between schemas.

        Args:
            relationships: List of all relationships

        Returns:
            List[List[str]]: Circular dependency cycles
        """
        # Build adjacency list
        graph = {}
        for rel in relationships:
            if rel.source_schema_id not in graph:
                graph[rel.source_schema_id] = []
            graph[rel.source_schema_id].append(rel.target_schema_id)

        # Find cycles using DFS
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs_cycles(node: str, path: List[str]):
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            if node in graph:
                for neighbor in graph[node]:
                    dfs_cycles(neighbor, path.copy())

            rec_stack.remove(node)

        # Check all nodes for cycles
        for rel in relationships:
            if rel.source_schema_id not in visited:
                dfs_cycles(rel.source_schema_id, [])

        return cycles

    def _build_inheritance_trees(
        self,
        inheritance_relationships: List[SchemaRelationship]
    ) -> Dict[str, List[str]]:
        """Build inheritance trees from inheritance relationships.

        Args:
            inheritance_relationships: List of inheritance relationships

        Returns:
            Dict[str, List[str]]: Inheritance trees (parent -> children)
        """
        trees = {}

        # Build parent -> children mapping
        for rel in inheritance_relationships:
            if rel.relationship_type == RelationshipType.INHERITANCE:
                parent = rel.target_schema_id
                child = rel.source_schema_id

                if parent not in trees:
                    trees[parent] = []
                trees[parent].append(child)

        # Sort children for consistent ordering
        for parent in trees:
            trees[parent].sort()

        return trees

    def _assess_schema_complexity(self, schema: Dict[str, Any]) -> str:
        """Assess the complexity of a schema.

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
        composition_count = 0
        for key in ["allOf", "oneOf", "anyOf"]:
            if key in schema:
                composition_count += len(schema[key])
        complexity_score += min(composition_count, 2)

        # Required properties ratio
        required = schema.get("required", [])
        if len(required) > prop_count * 0.7:  # More than 70% required
            complexity_score += 1

        # Validation complexity
        validation_rules = 0
        for prop in properties.values():
            validation_rules += len([k for k in prop.keys() if k in ["minimum", "maximum", "minLength", "maxLength", "pattern", "enum"]])
        complexity_score += min(validation_rules // 5, 2)

        # Classify complexity
        if complexity_score >= 8:
            return "complex"
        elif complexity_score >= 4:
            return "moderate"
        else:
            return "simple"