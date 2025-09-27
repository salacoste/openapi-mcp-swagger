"""Endpoint extraction and normalization for OpenAPI documents."""

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.parser.models import (
    HttpMethod,
    NormalizedEndpoint,
    NormalizedParameter,
    NormalizedRequestBody,
    NormalizedResponse,
    NormalizedSecurityRequirement,
    ParameterLocation,
)

logger = get_logger(__name__)


class EndpointNormalizer:
    """Normalizes OpenAPI path operations into structured endpoint models."""

    def __init__(self):
        self.logger = get_logger(__name__)

        # HTTP methods supported by OpenAPI
        self.http_methods = {method.value for method in HttpMethod}

        # Parameter location mapping
        self.param_location_map = {
            "query": ParameterLocation.QUERY,
            "path": ParameterLocation.PATH,
            "header": ParameterLocation.HEADER,
            "cookie": ParameterLocation.COOKIE,
        }

    def normalize_endpoints(
        self,
        paths_data: Dict[str, Any],
        global_security: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[NormalizedEndpoint], List[str], List[str]]:
        """Normalize all endpoints from OpenAPI paths object.

        Args:
            paths_data: OpenAPI paths object
            global_security: Global security requirements

        Returns:
            Tuple of (normalized_endpoints, errors, warnings)
        """
        normalized_endpoints = []
        errors = []
        warnings = []

        if not isinstance(paths_data, dict):
            errors.append("Paths object must be a dictionary")
            return normalized_endpoints, errors, warnings

        self.logger.info(
            "Starting endpoint normalization", paths_count=len(paths_data)
        )

        for path_name, path_item in paths_data.items():
            if not isinstance(path_name, str):
                warnings.append(f"Skipping non-string path key: {path_name}")
                continue

            if not path_name.startswith("/"):
                warnings.append(f"Path should start with '/': {path_name}")

            if not isinstance(path_item, dict):
                errors.append(f"Path item must be object: {path_name}")
                continue

            # Extract path-level parameters and extensions
            path_parameters = self._extract_path_parameters(path_item)
            path_extensions = self._extract_extensions(path_item)

            # Process each HTTP method in the path
            for method_name, operation in path_item.items():
                method_lower = method_name.lower()

                # Skip non-method properties
                if method_lower not in self.http_methods:
                    continue

                if not isinstance(operation, dict):
                    errors.append(
                        f"Operation must be object: {path_name} {method_name}"
                    )
                    continue

                try:
                    normalized_endpoint = self._normalize_single_endpoint(
                        path_name=path_name,
                        method=HttpMethod(method_lower),
                        operation=operation,
                        path_parameters=path_parameters,
                        path_extensions=path_extensions,
                        global_security=global_security,
                    )

                    normalized_endpoints.append(normalized_endpoint)

                except Exception as e:
                    error_msg = f"Failed to normalize endpoint {path_name} {method_name}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(
                        "Endpoint normalization failed",
                        path=path_name,
                        method=method_name,
                        error=str(e),
                    )

        self.logger.info(
            "Endpoint normalization completed",
            endpoints_normalized=len(normalized_endpoints),
            errors=len(errors),
            warnings=len(warnings),
        )

        return normalized_endpoints, errors, warnings

    def _normalize_single_endpoint(
        self,
        path_name: str,
        method: HttpMethod,
        operation: Dict[str, Any],
        path_parameters: List[Dict[str, Any]],
        path_extensions: Dict[str, Any],
        global_security: Optional[List[Dict[str, Any]]] = None,
    ) -> NormalizedEndpoint:
        """Normalize a single endpoint operation.

        Args:
            path_name: API path
            method: HTTP method
            operation: Operation object
            path_parameters: Path-level parameters
            path_extensions: Path-level extensions
            global_security: Global security requirements

        Returns:
            Normalized endpoint
        """
        # Extract basic operation metadata
        operation_id = operation.get("operationId")
        summary = operation.get("summary")
        description = operation.get("description")
        tags = operation.get("tags", [])
        external_docs = operation.get("externalDocs")
        deprecated = operation.get("deprecated", False)

        # Normalize parameters
        operation_parameters = operation.get("parameters", [])
        all_parameters = path_parameters + operation_parameters
        normalized_parameters = self._normalize_parameters(all_parameters)

        # Normalize request body
        request_body = None
        if "requestBody" in operation:
            request_body = self._normalize_request_body(
                operation["requestBody"]
            )

        # Normalize responses
        responses = self._normalize_responses(operation.get("responses", {}))

        # Normalize security requirements
        security = self._normalize_security_requirements(
            operation.get("security", global_security or [])
        )

        # Extract callbacks
        callbacks = operation.get("callbacks", {})

        # Extract extensions
        extensions = self._extract_extensions(operation)
        extensions.update(path_extensions)

        # Build dependency sets
        schema_dependencies = self._extract_schema_dependencies(operation)
        security_dependencies = self._extract_security_dependencies(security)

        # Create normalized endpoint
        endpoint = NormalizedEndpoint(
            path=path_name,
            method=method,
            operation_id=operation_id,
            summary=summary,
            description=description,
            tags=tags,
            external_docs=external_docs,
            parameters=normalized_parameters,
            request_body=request_body,
            responses=responses,
            security=security,
            callbacks=callbacks,
            deprecated=deprecated,
            schema_dependencies=schema_dependencies,
            security_dependencies=security_dependencies,
            extensions=extensions,
        )

        return endpoint

    def _extract_path_parameters(
        self, path_item: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract path-level parameters.

        Args:
            path_item: Path item object

        Returns:
            List of path-level parameters
        """
        return path_item.get("parameters", [])

    def _normalize_parameters(
        self, parameters: List[Dict[str, Any]]
    ) -> List[NormalizedParameter]:
        """Normalize operation parameters.

        Args:
            parameters: List of parameter objects

        Returns:
            List of normalized parameters
        """
        normalized = []

        for param in parameters:
            if not isinstance(param, dict):
                continue

            # Handle parameter references
            if "$ref" in param:
                # Store reference for later resolution
                normalized.append(
                    NormalizedParameter(
                        name=f"ref:{param['$ref']}",
                        location=ParameterLocation.QUERY,  # Will be resolved later
                        extensions={"$ref": param["$ref"]},
                    )
                )
                continue

            name = param.get("name")
            location = param.get("in")

            if not name or not location:
                continue

            if location not in self.param_location_map:
                continue

            # Extract schema information
            schema = param.get("schema", {})
            schema_type = schema.get("type")
            format_type = schema.get("format")
            enum_values = schema.get("enum")
            default_value = schema.get("default")

            # Extract validation constraints
            minimum = schema.get("minimum")
            maximum = schema.get("maximum")
            min_length = schema.get("minLength")
            max_length = schema.get("maxLength")
            pattern = schema.get("pattern")

            # Handle complex schema types
            schema_ref = schema.get("$ref")
            items_schema = schema.get("items")
            additional_properties = schema.get("additionalProperties")

            normalized_param = NormalizedParameter(
                name=name,
                location=self.param_location_map[location],
                required=param.get("required", False),
                description=param.get("description"),
                schema_type=schema_type,
                format=format_type,
                enum=enum_values,
                default=default_value,
                example=param.get("example") or schema.get("example"),
                deprecated=param.get("deprecated", False),
                minimum=minimum,
                maximum=maximum,
                min_length=min_length,
                max_length=max_length,
                pattern=pattern,
                schema_ref=schema_ref,
                items_schema=items_schema,
                additional_properties=additional_properties,
                extensions=self._extract_extensions(param),
            )

            normalized.append(normalized_param)

        return normalized

    def _normalize_request_body(
        self, request_body: Dict[str, Any]
    ) -> Optional[NormalizedRequestBody]:
        """Normalize request body object.

        Args:
            request_body: Request body object

        Returns:
            Normalized request body or None
        """
        if not isinstance(request_body, dict):
            return None

        # Handle request body references
        if "$ref" in request_body:
            return NormalizedRequestBody(
                description=f"Reference: {request_body['$ref']}",
                extensions={"$ref": request_body["$ref"]},
            )

        return NormalizedRequestBody(
            description=request_body.get("description"),
            required=request_body.get("required", False),
            content=request_body.get("content", {}),
            extensions=self._extract_extensions(request_body),
        )

    def _normalize_responses(
        self, responses: Dict[str, Any]
    ) -> Dict[str, NormalizedResponse]:
        """Normalize response objects.

        Args:
            responses: Responses object

        Returns:
            Dictionary of normalized responses by status code
        """
        normalized = {}

        for status_code, response in responses.items():
            if not isinstance(response, dict):
                continue

            # Handle response references
            if "$ref" in response:
                normalized[status_code] = NormalizedResponse(
                    status_code=status_code,
                    description=f"Reference: {response['$ref']}",
                    extensions={"$ref": response["$ref"]},
                )
                continue

            normalized[status_code] = NormalizedResponse(
                status_code=status_code,
                description=response.get("description", ""),
                headers=response.get("headers", {}),
                content=response.get("content", {}),
                links=response.get("links", {}),
                extensions=self._extract_extensions(response),
            )

        return normalized

    def _normalize_security_requirements(
        self, security_list: List[Dict[str, Any]]
    ) -> List[List[NormalizedSecurityRequirement]]:
        """Normalize security requirements.

        Args:
            security_list: List of security requirement objects

        Returns:
            List of security requirement alternatives
        """
        normalized = []

        for security_alternatives in security_list:
            if not isinstance(security_alternatives, dict):
                continue

            alternative_requirements = []

            for scheme_name, scopes in security_alternatives.items():
                if not isinstance(scopes, list):
                    scopes = []

                requirement = NormalizedSecurityRequirement(
                    scheme_id=scheme_name, scopes=scopes
                )
                alternative_requirements.append(requirement)

            if alternative_requirements:
                normalized.append(alternative_requirements)

        return normalized

    def _extract_schema_dependencies(
        self, operation: Dict[str, Any]
    ) -> Set[str]:
        """Extract all schema dependencies from an operation.

        Args:
            operation: Operation object

        Returns:
            Set of schema component names referenced
        """
        dependencies = set()

        # Extract from parameters
        for param in operation.get("parameters", []):
            if isinstance(param, dict):
                schema_ref = param.get("schema", {}).get("$ref")
                if schema_ref and schema_ref.startswith(
                    "#/components/schemas/"
                ):
                    schema_name = schema_ref.split("/")[-1]
                    dependencies.add(schema_name)

                # Handle direct $ref in parameter
                param_ref = param.get("$ref")
                if param_ref and "schemas" in param_ref:
                    schema_name = param_ref.split("/")[-1]
                    dependencies.add(schema_name)

        # Extract from request body
        request_body = operation.get("requestBody", {})
        dependencies.update(
            self._extract_schema_refs_from_content(request_body)
        )

        # Extract from responses
        for response in operation.get("responses", {}).values():
            if isinstance(response, dict):
                dependencies.update(
                    self._extract_schema_refs_from_content(response)
                )

        return dependencies

    def _extract_schema_refs_from_content(
        self, content_container: Dict[str, Any]
    ) -> Set[str]:
        """Recursively extract schema references from content objects.

        Args:
            content_container: Object that may contain content with schema refs

        Returns:
            Set of schema names
        """
        dependencies = set()

        # Handle direct reference
        ref = content_container.get("$ref")
        if ref and "#/components/schemas/" in ref:
            schema_name = ref.split("/")[-1]
            dependencies.add(schema_name)

        # Handle content object
        content = content_container.get("content", {})
        if isinstance(content, dict):
            for media_type_obj in content.values():
                if isinstance(media_type_obj, dict):
                    schema = media_type_obj.get("schema", {})
                    if isinstance(schema, dict):
                        dependencies.update(
                            self._extract_refs_recursively(schema)
                        )

        return dependencies

    def _extract_refs_recursively(self, obj: Any) -> Set[str]:
        """Recursively extract all $ref schema references from an object.

        Args:
            obj: Object to scan for references

        Returns:
            Set of schema names
        """
        refs = set()

        if isinstance(obj, dict):
            # Direct reference
            ref = obj.get("$ref")
            if ref and "#/components/schemas/" in ref:
                schema_name = ref.split("/")[-1]
                refs.add(schema_name)

            # Recurse into all values
            for value in obj.values():
                refs.update(self._extract_refs_recursively(value))

        elif isinstance(obj, list):
            # Recurse into all items
            for item in obj:
                refs.update(self._extract_refs_recursively(item))

        return refs

    def _extract_security_dependencies(
        self, security_requirements: List[List[NormalizedSecurityRequirement]]
    ) -> Set[str]:
        """Extract security scheme dependencies.

        Args:
            security_requirements: Normalized security requirements

        Returns:
            Set of security scheme IDs
        """
        dependencies = set()

        for alternatives in security_requirements:
            for requirement in alternatives:
                dependencies.add(requirement.scheme_id)

        return dependencies

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

    def validate_path_parameters(
        self, path: str, parameters: List[NormalizedParameter]
    ) -> List[str]:
        """Validate that path parameters match the path template.

        Args:
            path: API path with parameter templates
            parameters: Normalized parameters

        Returns:
            List of validation error messages
        """
        errors = []

        # Extract path parameter names from template
        path_template_params = set(re.findall(r"\{([^}]+)\}", path))

        # Extract actual path parameters
        actual_path_params = {
            param.name
            for param in parameters
            if param.location == ParameterLocation.PATH
        }

        # Check for missing path parameters
        missing_params = path_template_params - actual_path_params
        if missing_params:
            errors.append(f"Missing path parameters: {missing_params}")

        # Check for extra path parameters
        extra_params = actual_path_params - path_template_params
        if extra_params:
            errors.append(
                f"Extra path parameters not in template: {extra_params}"
            )

        # Validate that all path parameters are required
        for param in parameters:
            if param.location == ParameterLocation.PATH and not param.required:
                errors.append(
                    f"Path parameter '{param.name}' must be required"
                )

        return errors

    def get_endpoint_statistics(
        self, endpoints: List[NormalizedEndpoint]
    ) -> Dict[str, Any]:
        """Generate statistics about normalized endpoints.

        Args:
            endpoints: List of normalized endpoints

        Returns:
            Dictionary with endpoint statistics
        """
        stats = {
            "total_endpoints": len(endpoints),
            "methods": defaultdict(int),
            "tags": defaultdict(int),
            "parameters_per_endpoint": [],
            "deprecated_count": 0,
            "with_request_body": 0,
            "with_security": 0,
            "response_codes": defaultdict(int),
            "schema_dependencies": set(),
            "security_dependencies": set(),
        }

        for endpoint in endpoints:
            # Method distribution
            stats["methods"][endpoint.method.value] += 1

            # Tag distribution
            for tag in endpoint.tags:
                stats["tags"][tag] += 1

            # Parameter count
            stats["parameters_per_endpoint"].append(len(endpoint.parameters))

            # Deprecated count
            if endpoint.deprecated:
                stats["deprecated_count"] += 1

            # Request body presence
            if endpoint.request_body:
                stats["with_request_body"] += 1

            # Security presence
            if endpoint.security:
                stats["with_security"] += 1

            # Response codes
            for status_code in endpoint.responses.keys():
                stats["response_codes"][status_code] += 1

            # Dependencies
            stats["schema_dependencies"].update(endpoint.schema_dependencies)
            stats["security_dependencies"].update(
                endpoint.security_dependencies
            )

        # Convert defaultdicts to regular dicts
        stats["methods"] = dict(stats["methods"])
        stats["tags"] = dict(stats["tags"])
        stats["response_codes"] = dict(stats["response_codes"])

        # Convert sets to counts
        stats["unique_schema_dependencies"] = len(stats["schema_dependencies"])
        stats["unique_security_dependencies"] = len(
            stats["security_dependencies"]
        )

        # Calculate averages
        if stats["parameters_per_endpoint"]:
            stats["avg_parameters_per_endpoint"] = sum(
                stats["parameters_per_endpoint"]
            ) / len(stats["parameters_per_endpoint"])
        else:
            stats["avg_parameters_per_endpoint"] = 0

        return stats
