"""Semantic consistency validation for normalized OpenAPI data."""

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.parser.models import (
    HttpMethod,
    NormalizedEndpoint,
    NormalizedParameter,
    NormalizedSchema,
    NormalizedSecurityScheme,
    ParameterLocation,
)

logger = get_logger(__name__)


class ConsistencyValidator:
    """Validates semantic consistency across normalized OpenAPI components."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def validate_full_consistency(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
        security_schemes: Dict[str, NormalizedSecurityScheme],
    ) -> Tuple[List[str], List[str]]:
        """Perform comprehensive consistency validation.

        Args:
            endpoints: List of normalized endpoints
            schemas: Dictionary of normalized schemas
            security_schemes: Dictionary of security schemes

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        self.logger.info(
            "Starting comprehensive consistency validation",
            endpoints=len(endpoints),
            schemas=len(schemas),
            security_schemes=len(security_schemes),
        )

        # Reference consistency validation
        ref_errors, ref_warnings = self.validate_reference_consistency(
            endpoints, schemas, security_schemes
        )
        errors.extend(ref_errors)
        warnings.extend(ref_warnings)

        # Path parameter consistency
        path_errors, path_warnings = self.validate_path_parameter_consistency(
            endpoints
        )
        errors.extend(path_errors)
        warnings.extend(path_warnings)

        # Schema consistency
        schema_errors, schema_warnings = self.validate_schema_consistency(
            endpoints, schemas
        )
        errors.extend(schema_errors)
        warnings.extend(schema_warnings)

        # Security consistency
        sec_errors, sec_warnings = self.validate_security_consistency(
            endpoints, security_schemes
        )
        errors.extend(sec_errors)
        warnings.extend(sec_warnings)

        # Naming consistency
        naming_warnings = self.validate_naming_consistency(endpoints, schemas)
        warnings.extend(naming_warnings)

        # HTTP method consistency
        method_warnings = self.validate_http_method_consistency(endpoints)
        warnings.extend(method_warnings)

        # Response consistency
        response_warnings = self.validate_response_consistency(endpoints)
        warnings.extend(response_warnings)

        self.logger.info(
            "Consistency validation completed",
            errors=len(errors),
            warnings=len(warnings),
        )

        return errors, warnings

    def validate_reference_consistency(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
        security_schemes: Dict[str, NormalizedSecurityScheme],
    ) -> Tuple[List[str], List[str]]:
        """Validate that all references point to existing definitions."""
        errors = []
        warnings = []

        schema_names = set(schemas.keys())
        security_scheme_names = set(security_schemes.keys())

        for endpoint in endpoints:
            # Check schema dependencies
            for schema_name in endpoint.schema_dependencies:
                if schema_name not in schema_names:
                    errors.append(
                        f"Endpoint {endpoint.method.value.upper()} {endpoint.path} "
                        f"references undefined schema: {schema_name}"
                    )

            # Check security dependencies
            for scheme_name in endpoint.security_dependencies:
                if scheme_name not in security_scheme_names:
                    errors.append(
                        f"Endpoint {endpoint.method.value.upper()} {endpoint.path} "
                        f"references undefined security scheme: {scheme_name}"
                    )

            # Check parameter schema references
            for param in endpoint.parameters:
                if param.schema_ref:
                    ref_name = (
                        param.schema_ref.split("/")[-1]
                        if "/" in param.schema_ref
                        else param.schema_ref
                    )
                    if (
                        ref_name not in schema_names
                        and not param.schema_ref.startswith("#/")
                    ):
                        warnings.append(
                            f"Parameter {param.name} in {endpoint.path} "
                            f"references unresolved schema: {param.schema_ref}"
                        )

        # Check schema cross-references
        for schema_name, schema in schemas.items():
            for ref_name in schema.schema_dependencies:
                if ref_name not in schema_names:
                    errors.append(
                        f"Schema {schema_name} references undefined schema: {ref_name}"
                    )

        return errors, warnings

    def validate_path_parameter_consistency(
        self, endpoints: List[NormalizedEndpoint]
    ) -> Tuple[List[str], List[str]]:
        """Validate path parameter consistency."""
        errors = []
        warnings = []

        # Group endpoints by path template
        path_groups = defaultdict(list)
        for endpoint in endpoints:
            path_groups[endpoint.path].append(endpoint)

        for path, path_endpoints in path_groups.items():
            # Extract path parameter names from template
            path_param_names = set(re.findall(r"\{([^}]+)\}", path))

            for endpoint in path_endpoints:
                # Get actual path parameters
                actual_path_params = {
                    param.name
                    for param in endpoint.parameters
                    if param.location == ParameterLocation.PATH
                }

                # Check for missing path parameters
                missing_params = path_param_names - actual_path_params
                if missing_params:
                    errors.append(
                        f"Endpoint {endpoint.method.value.upper()} {path} "
                        f"missing path parameters: {missing_params}"
                    )

                # Check for extra path parameters
                extra_params = actual_path_params - path_param_names
                if extra_params:
                    warnings.append(
                        f"Endpoint {endpoint.method.value.upper()} {path} "
                        f"has extra path parameters not in template: {extra_params}"
                    )

                # Validate that path parameters are required
                for param in endpoint.parameters:
                    if (
                        param.location == ParameterLocation.PATH
                        and not param.required
                    ):
                        errors.append(
                            f"Path parameter {param.name} in {endpoint.method.value.upper()} {path} "
                            "must be required"
                        )

            # Check consistency across methods for the same path
            if len(path_endpoints) > 1:
                self._validate_path_parameter_consistency_across_methods(
                    path, path_endpoints, errors, warnings
                )

        return errors, warnings

    def _validate_path_parameter_consistency_across_methods(
        self,
        path: str,
        endpoints: List[NormalizedEndpoint],
        errors: List[str],
        warnings: List[str],
    ):
        """Validate path parameter consistency across methods for the same path."""
        # Get path parameters from all methods
        param_definitions = {}

        for endpoint in endpoints:
            for param in endpoint.parameters:
                if param.location == ParameterLocation.PATH:
                    if param.name not in param_definitions:
                        param_definitions[param.name] = []
                    param_definitions[param.name].append(
                        (endpoint.method, param)
                    )

        # Check for inconsistent parameter definitions
        for param_name, param_list in param_definitions.items():
            if len(param_list) > 1:
                # Check type consistency
                types = set()
                formats = set()
                descriptions = set()

                for method, param in param_list:
                    if param.schema_type:
                        types.add(param.schema_type)
                    if param.format:
                        formats.add(param.format)
                    if param.description:
                        descriptions.add(param.description.strip())

                if len(types) > 1:
                    warnings.append(
                        f"Path parameter {param_name} in {path} has inconsistent types: {types}"
                    )

                if len(formats) > 1:
                    warnings.append(
                        f"Path parameter {param_name} in {path} has inconsistent formats: {formats}"
                    )

                if len(descriptions) > 1:
                    warnings.append(
                        f"Path parameter {param_name} in {path} has inconsistent descriptions"
                    )

    def validate_schema_consistency(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
    ) -> Tuple[List[str], List[str]]:
        """Validate schema usage consistency."""
        errors = []
        warnings = []

        # Check for unused schemas
        used_schemas = set()
        for endpoint in endpoints:
            used_schemas.update(endpoint.schema_dependencies)

        # Also check schemas used by other schemas
        for schema in schemas.values():
            used_schemas.update(schema.schema_dependencies)

        unused_schemas = set(schemas.keys()) - used_schemas
        if unused_schemas:
            warnings.extend(
                [
                    f"Schema defined but never used: {schema_name}"
                    for schema_name in unused_schemas
                ]
            )

        # Check for schema naming conflicts with primitives
        primitive_types = {
            "string",
            "number",
            "integer",
            "boolean",
            "array",
            "object",
        }
        for schema_name in schemas.keys():
            if schema_name.lower() in primitive_types:
                warnings.append(
                    f"Schema name conflicts with primitive type: {schema_name}"
                )

        # Check for circular dependencies (already handled in schema processor)
        # Check for overly complex inheritance hierarchies
        for schema_name, schema in schemas.items():
            if len(schema.schema_dependencies) > 5:
                warnings.append(
                    f"Schema {schema_name} has many dependencies ({len(schema.schema_dependencies)}), "
                    "consider simplifying"
                )

        return errors, warnings

    def validate_security_consistency(
        self,
        endpoints: List[NormalizedEndpoint],
        security_schemes: Dict[str, NormalizedSecurityScheme],
    ) -> Tuple[List[str], List[str]]:
        """Validate security configuration consistency."""
        errors = []
        warnings = []

        # Check for unused security schemes
        used_schemes = set()
        for endpoint in endpoints:
            used_schemes.update(endpoint.security_dependencies)

        unused_schemes = set(security_schemes.keys()) - used_schemes
        if unused_schemes:
            warnings.extend(
                [
                    f"Security scheme defined but never used: {scheme_name}"
                    for scheme_name in unused_schemes
                ]
            )

        # Check for endpoints without security
        unsecured_endpoints = []
        for endpoint in endpoints:
            if not endpoint.security:
                unsecured_endpoints.append(
                    f"{endpoint.method.value.upper()} {endpoint.path}"
                )

        if unsecured_endpoints:
            warnings.append(
                f"Endpoints without security requirements: {', '.join(unsecured_endpoints[:5])}"
                + (
                    f" and {len(unsecured_endpoints) - 5} more"
                    if len(unsecured_endpoints) > 5
                    else ""
                )
            )

        return errors, warnings

    def validate_naming_consistency(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
    ) -> List[str]:
        """Validate naming convention consistency."""
        warnings = []

        # Check operation ID naming patterns
        operation_ids = [
            ep.operation_id for ep in endpoints if ep.operation_id
        ]
        if operation_ids:
            patterns = self._analyze_naming_patterns(operation_ids)
            if len(patterns) > 2:
                warnings.append(
                    f"Inconsistent operation ID naming patterns detected: {list(patterns.keys())[:3]}"
                )

        # Check schema naming patterns
        schema_names = list(schemas.keys())
        if schema_names:
            patterns = self._analyze_naming_patterns(schema_names)
            if len(patterns) > 2:
                warnings.append(
                    f"Inconsistent schema naming patterns detected: {list(patterns.keys())[:3]}"
                )

        # Check parameter naming consistency
        all_params = []
        for endpoint in endpoints:
            all_params.extend([param.name for param in endpoint.parameters])

        if all_params:
            patterns = self._analyze_naming_patterns(all_params)
            if len(patterns) > 3:  # Allow more variation for parameters
                warnings.append(
                    "Inconsistent parameter naming patterns detected"
                )

        return warnings

    def _analyze_naming_patterns(self, names: List[str]) -> Dict[str, int]:
        """Analyze naming patterns in a list of names."""
        patterns = defaultdict(int)

        for name in names:
            if "_" in name and name.islower():
                patterns["snake_case"] += 1
            elif re.match(r"^[a-z]+([A-Z][a-z]*)*$", name):
                patterns["camelCase"] += 1
            elif re.match(r"^[A-Z][a-z]*([A-Z][a-z]*)*$", name):
                patterns["PascalCase"] += 1
            elif "-" in name and name.islower():
                patterns["kebab-case"] += 1
            elif name.isupper():
                patterns["UPPER_CASE"] += 1
            else:
                patterns["mixed"] += 1

        return dict(patterns)

    def validate_http_method_consistency(
        self, endpoints: List[NormalizedEndpoint]
    ) -> List[str]:
        """Validate HTTP method usage patterns."""
        warnings = []

        # Group endpoints by path
        path_methods = defaultdict(set)
        for endpoint in endpoints:
            path_methods[endpoint.path].add(endpoint.method)

        # Check for unusual method combinations
        for path, methods in path_methods.items():
            # Check for paths with only GET (might need POST for creation)
            if methods == {HttpMethod.GET}:
                # Skip if it looks like a detail endpoint
                if not re.search(r"\{[^}]+\}", path):
                    warnings.append(
                        f"Path {path} only supports GET, consider adding POST"
                    )

            # Check for missing GET on collection endpoints
            if HttpMethod.POST in methods and HttpMethod.GET not in methods:
                # Check if it looks like a collection endpoint
                if not re.search(r"\{[^}]+\}$", path):
                    warnings.append(
                        f"Collection path {path} has POST but no GET"
                    )

            # Check for DELETE without GET
            if HttpMethod.DELETE in methods and HttpMethod.GET not in methods:
                warnings.append(f"Path {path} supports DELETE but not GET")

        return warnings

    def validate_response_consistency(
        self, endpoints: List[NormalizedEndpoint]
    ) -> List[str]:
        """Validate response code consistency patterns."""
        warnings = []

        for endpoint in endpoints:
            status_codes = set(endpoint.responses.keys())

            # Check for missing common success responses
            if endpoint.method == HttpMethod.GET:
                if "200" not in status_codes:
                    warnings.append(
                        f"GET {endpoint.path} missing 200 response"
                    )
            elif endpoint.method == HttpMethod.POST:
                if "201" not in status_codes and "200" not in status_codes:
                    warnings.append(
                        f"POST {endpoint.path} missing 201 or 200 response"
                    )
            elif endpoint.method == HttpMethod.PUT:
                if "200" not in status_codes and "204" not in status_codes:
                    warnings.append(
                        f"PUT {endpoint.path} missing 200 or 204 response"
                    )
            elif endpoint.method == HttpMethod.DELETE:
                if "204" not in status_codes and "200" not in status_codes:
                    warnings.append(
                        f"DELETE {endpoint.path} missing 204 or 200 response"
                    )

            # Check for missing error responses
            has_client_error = any(
                code.startswith("4") for code in status_codes
            )
            has_server_error = any(
                code.startswith("5") for code in status_codes
            )

            if not has_client_error:
                warnings.append(
                    f"{endpoint.method.value.upper()} {endpoint.path} missing 4xx error responses"
                )

            if not has_server_error:
                warnings.append(
                    f"{endpoint.method.value.upper()} {endpoint.path} missing 5xx error responses"
                )

        return warnings

    def generate_consistency_report(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
        security_schemes: Dict[str, NormalizedSecurityScheme],
    ) -> Dict[str, Any]:
        """Generate comprehensive consistency report.

        Args:
            endpoints: List of normalized endpoints
            schemas: Dictionary of normalized schemas
            security_schemes: Dictionary of security schemes

        Returns:
            Dictionary with consistency analysis results
        """
        errors, warnings = self.validate_full_consistency(
            endpoints, schemas, security_schemes
        )

        report = {
            "summary": {
                "total_errors": len(errors),
                "total_warnings": len(warnings),
                "endpoints_analyzed": len(endpoints),
                "schemas_analyzed": len(schemas),
                "security_schemes_analyzed": len(security_schemes),
            },
            "errors": errors,
            "warnings": warnings,
            "statistics": {
                "error_categories": self._categorize_issues(errors),
                "warning_categories": self._categorize_issues(warnings),
                "consistency_score": self._calculate_consistency_score(
                    errors, warnings, endpoints, schemas
                ),
            },
            "recommendations": self._generate_recommendations(
                errors, warnings
            ),
        }

        return report

    def _categorize_issues(self, issues: List[str]) -> Dict[str, int]:
        """Categorize validation issues by type."""
        categories = defaultdict(int)

        for issue in issues:
            if "reference" in issue.lower() or "undefined" in issue.lower():
                categories["references"] += 1
            elif "parameter" in issue.lower():
                categories["parameters"] += 1
            elif "security" in issue.lower():
                categories["security"] += 1
            elif "schema" in issue.lower():
                categories["schemas"] += 1
            elif "response" in issue.lower():
                categories["responses"] += 1
            elif "naming" in issue.lower():
                categories["naming"] += 1
            else:
                categories["other"] += 1

        return dict(categories)

    def _calculate_consistency_score(
        self,
        errors: List[str],
        warnings: List[str],
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
    ) -> float:
        """Calculate overall consistency score (0-100)."""
        total_items = len(endpoints) + len(schemas)
        if total_items == 0:
            return 100.0

        # Weight errors more heavily than warnings
        penalty = len(errors) * 2 + len(warnings) * 0.5
        max_penalty = total_items * 2  # Assume max 2 issues per item

        score = max(0, 100 - (penalty / max_penalty * 100))
        return round(score, 2)

    def _generate_recommendations(
        self, errors: List[str], warnings: List[str]
    ) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        error_categories = self._categorize_issues(errors)
        warning_categories = self._categorize_issues(warnings)

        if error_categories.get("references", 0) > 0:
            recommendations.append(
                "Fix reference errors by ensuring all referenced schemas and security schemes are defined"
            )

        if error_categories.get("parameters", 0) > 0:
            recommendations.append(
                "Correct path parameter definitions to match path templates"
            )

        if warning_categories.get("security", 0) > 5:
            recommendations.append(
                "Review security configuration - many endpoints lack security requirements"
            )

        if warning_categories.get("naming", 0) > 0:
            recommendations.append(
                "Establish and follow consistent naming conventions across the API"
            )

        if warning_categories.get("responses", 0) > 10:
            recommendations.append(
                "Add missing standard HTTP response codes to improve API completeness"
            )

        return recommendations
