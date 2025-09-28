"""Schema definition processing and reference resolution for OpenAPI documents."""

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import jsonref

    JSONREF_AVAILABLE = True
except ImportError:
    JSONREF_AVAILABLE = False

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.parser.models import NormalizedSchema

logger = get_logger(__name__)


@dataclass
class ReferenceResolution:
    """Result of reference resolution."""

    resolved: bool
    target: Optional[str] = None
    error: Optional[str] = None
    circular: bool = False


class SchemaProcessor:
    """Processes OpenAPI schema definitions with reference resolution and dependency tracking."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.processed_schemas: Dict[str, NormalizedSchema] = {}
        self.reference_cache: Dict[str, ReferenceResolution] = {}
        self.circular_references: Set[str] = set()
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)

    def process_schemas(
        self,
        components_data: Dict[str, Any],
        full_document: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, NormalizedSchema], List[str], List[str]]:
        """Process all schema components with reference resolution.

        Args:
            components_data: OpenAPI components object
            full_document: Complete OpenAPI document for reference resolution

        Returns:
            Tuple of (normalized_schemas, errors, warnings)
        """
        errors = []
        warnings = []
        schemas_data = components_data.get("schemas", {})

        if not isinstance(schemas_data, dict):
            errors.append("Components.schemas must be a dictionary")
            return {}, errors, warnings

        self.logger.info(
            "Starting schema processing",
            schemas_count=len(schemas_data),
            jsonref_available=JSONREF_AVAILABLE,
        )

        # Clear previous state
        self.processed_schemas.clear()
        self.reference_cache.clear()
        self.circular_references.clear()
        self.dependency_graph.clear()

        # First pass: Create basic schema objects
        for schema_name, schema_def in schemas_data.items():
            if not isinstance(schema_def, dict):
                errors.append(
                    f"Schema definition must be object: {schema_name}"
                )
                continue

            try:
                normalized_schema = self._create_basic_schema(
                    schema_name, schema_def
                )
                self.processed_schemas[schema_name] = normalized_schema
            except Exception as e:
                errors.append(
                    f"Failed to create basic schema {schema_name}: {str(e)}"
                )

        # Second pass: Resolve references and build dependency graph
        if full_document:
            for schema_name in list(self.processed_schemas.keys()):
                try:
                    self._resolve_schema_references(
                        schema_name, schemas_data[schema_name], full_document
                    )
                except Exception as e:
                    error_msg = f"Failed to resolve references for schema {schema_name}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(
                        "Schema reference resolution failed",
                        schema=schema_name,
                        error=str(e),
                    )

        # Third pass: Update usage relationships
        self._update_usage_relationships()

        # Detect and report circular references
        circular_refs = self._detect_circular_references()
        if circular_refs:
            warnings.extend(
                [
                    f"Circular reference detected: {' -> '.join(cycle)}"
                    for cycle in circular_refs
                ]
            )

        # Validate schema consistency
        validation_errors = self._validate_schema_consistency()
        errors.extend(validation_errors)

        self.logger.info(
            "Schema processing completed",
            schemas_processed=len(self.processed_schemas),
            circular_references=len(circular_refs),
            errors=len(errors),
            warnings=len(warnings),
        )

        return self.processed_schemas.copy(), errors, warnings

    def _create_basic_schema(
        self, name: str, schema_def: Dict[str, Any]
    ) -> NormalizedSchema:
        """Create basic normalized schema from definition.

        Args:
            name: Schema name
            schema_def: Schema definition

        Returns:
            Basic normalized schema
        """
        # Extract basic properties
        schema_type = schema_def.get("type")
        format_type = schema_def.get("format")
        title = schema_def.get("title")
        description = schema_def.get("description")
        default = schema_def.get("default")
        example = schema_def.get("example")
        examples = schema_def.get("examples")

        # Object properties
        properties = schema_def.get("properties", {})
        required = schema_def.get("required", [])
        additional_properties = schema_def.get("additionalProperties")

        # Array properties
        items = schema_def.get("items")
        min_items = schema_def.get("minItems")
        max_items = schema_def.get("maxItems")
        unique_items = schema_def.get("uniqueItems")

        # String properties
        min_length = schema_def.get("minLength")
        max_length = schema_def.get("maxLength")
        pattern = schema_def.get("pattern")

        # Numeric properties
        minimum = schema_def.get("minimum")
        maximum = schema_def.get("maximum")
        exclusive_minimum = schema_def.get("exclusiveMinimum")
        exclusive_maximum = schema_def.get("exclusiveMaximum")
        multiple_of = schema_def.get("multipleOf")

        # Enumeration
        enum = schema_def.get("enum")
        const = schema_def.get("const")

        # Composition
        all_of = schema_def.get("allOf")
        one_of = schema_def.get("oneOf")
        any_of = schema_def.get("anyOf")
        not_schema = schema_def.get("not")

        # Conditional
        if_schema = schema_def.get("if")
        then_schema = schema_def.get("then")
        else_schema = schema_def.get("else")

        # Metadata
        read_only = schema_def.get("readOnly")
        write_only = schema_def.get("writeOnly")
        deprecated = schema_def.get("deprecated", False)

        # OpenAPI specific
        discriminator = schema_def.get("discriminator")
        xml = schema_def.get("xml")
        external_docs = schema_def.get("externalDocs")

        # Extract extensions
        extensions = self._extract_extensions(schema_def)

        return NormalizedSchema(
            name=name,
            type=schema_type,
            format=format_type,
            title=title,
            description=description,
            default=default,
            example=example,
            examples=examples,
            properties=properties,
            required=required,
            additional_properties=additional_properties,
            items=items,
            min_items=min_items,
            max_items=max_items,
            unique_items=unique_items,
            min_length=min_length,
            max_length=max_length,
            pattern=pattern,
            minimum=minimum,
            maximum=maximum,
            exclusive_minimum=exclusive_minimum,
            exclusive_maximum=exclusive_maximum,
            multiple_of=multiple_of,
            enum=enum,
            const=const,
            all_of=all_of,
            one_of=one_of,
            any_of=any_of,
            not_schema=not_schema,
            if_schema=if_schema,
            then_schema=then_schema,
            else_schema=else_schema,
            read_only=read_only,
            write_only=write_only,
            deprecated=deprecated,
            discriminator=discriminator,
            xml=xml,
            external_docs=external_docs,
            extensions=extensions,
            dependencies=set(),
        )

    def _resolve_schema_references(
        self,
        schema_name: str,
        schema_def: Dict[str, Any],
        full_document: Dict[str, Any],
    ) -> None:
        """Resolve references and build dependency graph for a schema.

        Args:
            schema_name: Schema name
            schema_def: Schema definition
            full_document: Complete OpenAPI document
        """
        if schema_name not in self.processed_schemas:
            return

        schema = self.processed_schemas[schema_name]

        # Find all references in this schema
        references = self._find_all_references(schema_def)

        # Resolve each reference and build dependency graph
        for ref_path in references:
            resolution = self._resolve_reference(ref_path, full_document)

            if resolution.resolved and resolution.target:
                # Add to dependency graph
                self.dependency_graph[schema_name].add(resolution.target)

                # Add to schema dependencies
                if resolution.target.startswith("schemas/"):
                    target_schema = resolution.target.replace("schemas/", "")
                    schema.dependencies.add(target_schema)

            elif resolution.circular:
                self.circular_references.add(
                    f"{schema_name} -> {resolution.target}"
                )

            if resolution.error:
                self.logger.warning(
                    "Reference resolution warning",
                    schema=schema_name,
                    reference=ref_path,
                    error=resolution.error,
                )

    def _find_all_references(self, obj: Any, path: str = "") -> Set[str]:
        """Recursively find all $ref references in an object.

        Args:
            obj: Object to scan
            path: Current path for tracking

        Returns:
            Set of reference paths found
        """
        references = set()

        if isinstance(obj, dict):
            # Direct reference
            if "$ref" in obj:
                references.add(obj["$ref"])

            # Recurse into all values
            for key, value in obj.items():
                if key != "$ref":  # Avoid infinite recursion
                    sub_path = f"{path}.{key}" if path else key
                    references.update(
                        self._find_all_references(value, sub_path)
                    )

        elif isinstance(obj, list):
            # Recurse into all items
            for i, item in enumerate(obj):
                sub_path = f"{path}[{i}]" if path else f"[{i}]"
                references.update(self._find_all_references(item, sub_path))

        return references

    def _resolve_reference(
        self, ref_path: str, document: Dict[str, Any]
    ) -> ReferenceResolution:
        """Resolve a single JSON reference.

        Args:
            ref_path: Reference path (e.g., "#/components/schemas/User")
            document: Complete document for resolution

        Returns:
            Reference resolution result
        """
        # Check cache first
        if ref_path in self.reference_cache:
            return self.reference_cache[ref_path]

        try:
            # Handle local references only (starting with #/)
            if not ref_path.startswith("#/"):
                result = ReferenceResolution(
                    resolved=False,
                    error=f"External references not supported: {ref_path}",
                )
                self.reference_cache[ref_path] = result
                return result

            # Parse the reference path
            path_parts = ref_path[2:].split("/")  # Remove '#/' prefix

            # Navigate to the referenced object
            current = document
            target_path = []

            for part in path_parts:
                if not isinstance(current, dict) or part not in current:
                    result = ReferenceResolution(
                        resolved=False,
                        error=f"Reference not found: {ref_path}",
                    )
                    self.reference_cache[ref_path] = result
                    return result

                current = current[part]
                target_path.append(part)

            # Determine target type
            target = "/".join(target_path)

            # Check for circular references if this is a schema reference
            if "schemas" in path_parts:
                schema_name = path_parts[-1]
                if self._would_create_circular_reference(
                    schema_name, target_path
                ):
                    result = ReferenceResolution(
                        resolved=True, target=target, circular=True
                    )
                    self.reference_cache[ref_path] = result
                    return result

            result = ReferenceResolution(resolved=True, target=target)
            self.reference_cache[ref_path] = result
            return result

        except Exception as e:
            result = ReferenceResolution(
                resolved=False, error=f"Reference resolution failed: {str(e)}"
            )
            self.reference_cache[ref_path] = result
            return result

    def _would_create_circular_reference(
        self, schema_name: str, target_path: List[str]
    ) -> bool:
        """Check if adding a dependency would create a circular reference.

        Args:
            schema_name: Source schema name
            target_path: Target path components

        Returns:
            True if circular reference would be created
        """
        if (
            len(target_path) < 2
            or target_path[0] != "components"
            or target_path[1] != "schemas"
        ):
            return False

        target_schema = target_path[2]

        # Simple check: direct circular reference
        if target_schema == schema_name:
            return True

        # Use breadth-first search to detect cycles in dependency graph
        visited = set()
        queue = deque([target_schema])

        while queue:
            current = queue.popleft()

            if current in visited:
                continue

            visited.add(current)

            # If we reach back to the original schema, it's circular
            if current == schema_name:
                return True

            # Add dependencies to queue
            if current in self.dependency_graph:
                for dep in self.dependency_graph[current]:
                    if dep.startswith("schemas/"):
                        dep_schema = dep.replace("schemas/", "")
                        if dep_schema not in visited:
                            queue.append(dep_schema)

        return False

    def _update_usage_relationships(self) -> None:
        """Update used_by relationships in schemas based on dependency graph."""
        # Clear existing usage relationships
        for schema in self.processed_schemas.values():
            schema.used_by.clear()

        # Build reverse relationships
        for schema_name, dependencies in self.dependency_graph.items():
            for dep in dependencies:
                if dep.startswith("schemas/"):
                    dep_schema = dep.replace("schemas/", "")
                    if dep_schema in self.processed_schemas:
                        self.processed_schemas[dep_schema].used_by.add(
                            schema_name
                        )

    def _detect_circular_references(self) -> List[List[str]]:
        """Detect circular reference cycles in the dependency graph.

        Returns:
            List of circular reference cycles
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
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

            # Follow schema dependencies only
            for dep in self.dependency_graph.get(node, []):
                if dep.startswith("schemas/"):
                    dep_schema = dep.replace("schemas/", "")
                    if dep_schema in self.processed_schemas:
                        dfs(dep_schema, path + [node])

            rec_stack.remove(node)

        # Check all schemas
        for schema_name in self.processed_schemas.keys():
            if schema_name not in visited:
                dfs(schema_name, [])

        return cycles

    def _validate_schema_consistency(self) -> List[str]:
        """Validate schema consistency and report issues.

        Returns:
            List of validation error messages
        """
        errors = []

        for schema_name, schema in self.processed_schemas.items():
            # Check required properties exist in properties
            if schema.type == "object" and schema.required:
                missing_properties = []
                for required_prop in schema.required:
                    if required_prop not in schema.properties:
                        missing_properties.append(required_prop)

                if missing_properties:
                    errors.append(
                        f"Schema {schema_name}: Required properties not defined: {missing_properties}"
                    )

            # Check array items are defined
            if schema.type == "array" and not schema.items:
                errors.append(
                    f"Schema {schema_name}: Array type missing items definition"
                )

            # Check discriminator properties
            if schema.discriminator:
                discriminator_prop = schema.discriminator.get("propertyName")
                if (
                    discriminator_prop
                    and discriminator_prop not in schema.properties
                ):
                    errors.append(
                        f"Schema {schema_name}: Discriminator property '{discriminator_prop}' not defined"
                    )

            # Validate dependencies exist
            for dep in schema.dependencies:
                if dep not in self.processed_schemas:
                    errors.append(
                        f"Schema {schema_name}: Dependency '{dep}' not found"
                    )

        return errors

    def _extract_extensions(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """Extract extension properties (x-*) from an object.

        Args:
            obj: Object to extract extensions from

        Returns:
            Dictionary of extension properties
        """
        extensions = {}

        for key, value in obj.items():
            if isinstance(key, str) and key.startswith("x-"):
                extensions[key] = value

        return extensions

    def resolve_schema_reference(
        self, ref_path: str
    ) -> Optional[NormalizedSchema]:
        """Resolve a schema reference to its normalized schema.

        Args:
            ref_path: Reference path (e.g., "#/components/schemas/User")

        Returns:
            Resolved schema or None if not found
        """
        if not ref_path.startswith("#/components/schemas/"):
            return None

        schema_name = ref_path.split("/")[-1]
        return self.processed_schemas.get(schema_name)

    def get_schema_statistics(self) -> Dict[str, Any]:
        """Generate statistics about processed schemas.

        Returns:
            Dictionary with schema statistics
        """
        if not self.processed_schemas:
            return {}

        stats = {
            "total_schemas": len(self.processed_schemas),
            "types": defaultdict(int),
            "with_properties": 0,
            "with_required": 0,
            "with_examples": 0,
            "deprecated_count": 0,
            "circular_references": len(self.circular_references),
            "total_dependencies": 0,
            "orphaned_schemas": 0,
            "most_referenced": None,
            "largest_schema": None,
        }

        dependency_counts = defaultdict(int)
        usage_counts = defaultdict(int)
        property_counts = {}

        for schema_name, schema in self.processed_schemas.items():
            # Type distribution
            if schema.type:
                stats["types"][schema.type] += 1
            else:
                stats["types"]["untyped"] += 1

            # Feature usage
            if schema.properties:
                stats["with_properties"] += 1
                property_counts[schema_name] = len(schema.properties)

            if schema.required:
                stats["with_required"] += 1

            if schema.example or schema.examples:
                stats["with_examples"] += 1

            if schema.deprecated:
                stats["deprecated_count"] += 1

            # Dependencies
            dep_count = len(schema.dependencies)
            stats["total_dependencies"] += dep_count
            dependency_counts[schema_name] = dep_count

            # Usage tracking
            usage_count = len(schema.used_by)
            usage_counts[schema_name] = usage_count

            if usage_count == 0:
                stats["orphaned_schemas"] += 1

        # Convert defaultdict to regular dict
        stats["types"] = dict(stats["types"])

        # Find most referenced schema
        if usage_counts:
            most_referenced = max(usage_counts.items(), key=lambda x: x[1])
            stats["most_referenced"] = {
                "name": most_referenced[0],
                "usage_count": most_referenced[1],
            }

        # Find largest schema by property count
        if property_counts:
            largest = max(property_counts.items(), key=lambda x: x[1])
            stats["largest_schema"] = {
                "name": largest[0],
                "property_count": largest[1],
            }

        # Average dependencies per schema
        if self.processed_schemas:
            stats["avg_dependencies"] = stats["total_dependencies"] / len(
                self.processed_schemas
            )

        return stats

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get the complete dependency graph.

        Returns:
            Dictionary mapping schema names to their dependencies
        """
        graph = {}

        for schema_name in self.processed_schemas.keys():
            dependencies = []
            for dep in self.dependency_graph.get(schema_name, []):
                if dep.startswith("schemas/"):
                    dependencies.append(dep.replace("schemas/", ""))
            graph[schema_name] = dependencies

        return graph
