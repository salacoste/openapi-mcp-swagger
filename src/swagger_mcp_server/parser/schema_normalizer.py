"""Main OpenAPI Schema Normalization Engine orchestrator."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.parser.consistency_validator import (
    ConsistencyValidator,
)
from swagger_mcp_server.parser.endpoint_normalizer import EndpointNormalizer
from swagger_mcp_server.parser.extension_handler import ExtensionHandler
from swagger_mcp_server.parser.models import (
    NormalizedEndpoint,
    NormalizedSchema,
    NormalizedSecurityScheme,
)
from swagger_mcp_server.parser.schema_processor import SchemaProcessor
from swagger_mcp_server.parser.search_optimizer import (
    SearchIndex,
    SearchOptimizer,
)
from swagger_mcp_server.parser.security_mapper import SecurityMapper

logger = get_logger(__name__)


@dataclass
class NormalizationResult:
    """Result of the complete normalization process."""

    endpoints: List[NormalizedEndpoint]
    schemas: Dict[str, NormalizedSchema]
    security_schemes: Dict[str, NormalizedSecurityScheme]
    search_index: SearchIndex
    errors: List[str]
    warnings: List[str]
    statistics: Dict[str, Any]
    consistency_report: Dict[str, Any]


@dataclass
class NormalizationConfig:
    """Configuration for the normalization process."""

    validate_consistency: bool = True
    optimize_for_search: bool = True
    include_extensions: bool = True
    performance_mode: bool = False  # Skip some validations for speed
    max_circular_refs: int = 10  # Maximum circular reference depth
    enable_search_optimization: bool = True


class SchemaNormalizer:
    """Main orchestrator for OpenAPI schema normalization."""

    def __init__(self, config: Optional[NormalizationConfig] = None):
        self.config = config or NormalizationConfig()
        self.logger = get_logger(__name__)

        # Initialize components
        self.endpoint_normalizer = EndpointNormalizer()
        self.schema_processor = SchemaProcessor()
        self.security_mapper = SecurityMapper()
        self.extension_handler = ExtensionHandler()
        self.consistency_validator = ConsistencyValidator()
        self.search_optimizer = SearchOptimizer()

    def normalize_openapi_document(
        self, openapi_data: Dict[str, Any]
    ) -> NormalizationResult:
        """Normalize a complete OpenAPI document.

        Args:
            openapi_data: Complete OpenAPI document

        Returns:
            NormalizationResult with all normalized components
        """
        self.logger.info(
            "Starting OpenAPI document normalization",
            openapi_version=openapi_data.get("openapi", "unknown"),
        )

        all_errors = []
        all_warnings = []

        try:
            # Step 1: Extract and normalize endpoints
            self.logger.info("Step 1: Normalizing endpoints")
            (
                endpoints,
                endpoint_errors,
                endpoint_warnings,
            ) = self._normalize_endpoints(openapi_data)
            all_errors.extend(endpoint_errors)
            all_warnings.extend(endpoint_warnings)

            # Step 2: Process schema definitions
            self.logger.info("Step 2: Processing schemas")
            schemas, schema_errors, schema_warnings = self._process_schemas(
                openapi_data
            )
            all_errors.extend(schema_errors)
            all_warnings.extend(schema_warnings)

            # Step 3: Map security schemes
            self.logger.info("Step 3: Mapping security schemes")
            (
                security_schemes,
                security_errors,
                security_warnings,
            ) = self._map_security_schemes(openapi_data)
            all_errors.extend(security_errors)
            all_warnings.extend(security_warnings)

            # Step 4: Process extensions (optional)
            if self.config.include_extensions:
                self.logger.info("Step 4: Processing extensions")
                extension_warnings = self._process_extensions(
                    endpoints, schemas, security_schemes
                )
                all_warnings.extend(extension_warnings)

            # Step 5: Validate consistency
            consistency_report = {}
            if self.config.validate_consistency and not self.config.performance_mode:
                self.logger.info("Step 5: Validating consistency")
                consistency_report = self._validate_consistency(
                    endpoints, schemas, security_schemes
                )
                all_errors.extend(consistency_report.get("errors", []))
                all_warnings.extend(consistency_report.get("warnings", []))

            # Step 6: Optimize for search
            search_index = None
            if self.config.optimize_for_search:
                self.logger.info("Step 6: Optimizing for search")
                search_index = self._optimize_for_search(
                    endpoints, schemas, security_schemes
                )

            # Step 7: Generate statistics
            self.logger.info("Step 7: Generating statistics")
            statistics = self._generate_statistics(
                endpoints, schemas, security_schemes, search_index
            )

            # Create final result
            result = NormalizationResult(
                endpoints=endpoints,
                schemas=schemas,
                security_schemes=security_schemes,
                search_index=search_index,
                errors=all_errors,
                warnings=all_warnings,
                statistics=statistics,
                consistency_report=consistency_report,
            )

            self.logger.info(
                "OpenAPI document normalization completed",
                endpoints=len(endpoints),
                schemas=len(schemas),
                security_schemes=len(security_schemes),
                errors=len(all_errors),
                warnings=len(all_warnings),
                success=len(all_errors) == 0,
            )

            return result

        except Exception as e:
            self.logger.error("Critical error during normalization", error=str(e))
            # Return partial result with error
            return NormalizationResult(
                endpoints=[],
                schemas={},
                security_schemes={},
                search_index=None,
                errors=[f"Critical normalization error: {str(e)}"],
                warnings=all_warnings,
                statistics={},
                consistency_report={},
            )

    def _normalize_endpoints(
        self, openapi_data: Dict[str, Any]
    ) -> Tuple[List[NormalizedEndpoint], List[str], List[str]]:
        """Normalize all endpoints from OpenAPI document."""
        paths_data = openapi_data.get("paths", {})
        global_security = openapi_data.get("security", [])

        if not paths_data:
            self.logger.warning("No paths found in OpenAPI document")
            return [], [], ["No API paths defined"]

        return self.endpoint_normalizer.normalize_endpoints(paths_data, global_security)

    def _process_schemas(
        self, openapi_data: Dict[str, Any]
    ) -> Tuple[Dict[str, NormalizedSchema], List[str], List[str]]:
        """Process all schema definitions from OpenAPI document."""
        components_data = openapi_data.get("components", {})

        if not components_data or "schemas" not in components_data:
            self.logger.info("No schema definitions found")
            return {}, [], ["No schema definitions found"]

        return self.schema_processor.process_schemas(components_data, openapi_data)

    def _map_security_schemes(
        self, openapi_data: Dict[str, Any]
    ) -> Tuple[Dict[str, NormalizedSecurityScheme], List[str], List[str]]:
        """Map all security schemes from OpenAPI document."""
        components_data = openapi_data.get("components", {})

        if not components_data or "securitySchemes" not in components_data:
            self.logger.info("No security schemes found")
            return {}, [], ["No security schemes defined"]

        return self.security_mapper.normalize_security_schemes(components_data)

    def _process_extensions(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
        security_schemes: Dict[str, NormalizedSecurityScheme],
    ) -> List[str]:
        """Process and validate extensions across all components."""
        warnings = []

        # Collect all extensions
        all_extensions = []

        # Extensions from endpoints
        for endpoint in endpoints:
            if hasattr(endpoint, "extensions") and endpoint.extensions:
                extension_warnings = self.extension_handler.validate_extensions(
                    endpoint.extensions
                )
                warnings.extend(extension_warnings)
                all_extensions.append(endpoint.extensions)

        # Extensions from schemas
        for schema in schemas.values():
            if hasattr(schema, "extensions") and schema.extensions:
                extension_warnings = self.extension_handler.validate_extensions(
                    schema.extensions
                )
                warnings.extend(extension_warnings)
                all_extensions.append(schema.extensions)

        # Extensions from security schemes
        for scheme in security_schemes.values():
            if hasattr(scheme, "extensions") and scheme.extensions:
                extension_warnings = self.extension_handler.validate_extensions(
                    scheme.extensions
                )
                warnings.extend(extension_warnings)
                all_extensions.append(scheme.extensions)

        # Generate extension statistics
        if all_extensions:
            extension_stats = self.extension_handler.get_extension_statistics(
                all_extensions
            )
            self.logger.info(
                "Extension processing completed",
                total_extensions=extension_stats["total_extension_properties"],
                unique_extensions=extension_stats["unique_extensions"],
            )

        return warnings

    def _validate_consistency(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
        security_schemes: Dict[str, NormalizedSecurityScheme],
    ) -> Dict[str, Any]:
        """Validate consistency across all normalized components."""
        return self.consistency_validator.generate_consistency_report(
            endpoints, schemas, security_schemes
        )

    def _optimize_for_search(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
        security_schemes: Dict[str, NormalizedSecurityScheme],
    ) -> Optional[SearchIndex]:
        """Optimize normalized data for search operations."""
        try:
            search_index = self.search_optimizer.optimize_for_search(
                endpoints, schemas, security_schemes
            )

            # Apply performance optimizations if enabled
            if self.config.enable_search_optimization:
                search_index = self.search_optimizer.optimize_search_performance(
                    search_index
                )

            return search_index

        except Exception as e:
            self.logger.error("Failed to optimize for search", error=str(e))
            return None

    def _generate_statistics(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
        security_schemes: Dict[str, NormalizedSecurityScheme],
        search_index: Optional[SearchIndex],
    ) -> Dict[str, Any]:
        """Generate comprehensive statistics about normalized data."""
        stats = {
            "normalization": {
                "total_endpoints": len(endpoints),
                "total_schemas": len(schemas),
                "total_security_schemes": len(security_schemes),
                "openapi_version": "3.0+",  # Detected version
            },
            "endpoints": {},
            "schemas": {},
            "security": {},
            "search": {},
            "quality_metrics": {},
        }

        # Endpoint statistics
        if endpoints:
            stats["endpoints"] = self.endpoint_normalizer.get_endpoint_statistics(
                endpoints
            )

        # Security statistics
        if security_schemes:
            # Create mock security requirements for statistics
            security_requirements = []
            for endpoint in endpoints:
                if hasattr(endpoint, "security") and endpoint.security:
                    security_requirements.extend(endpoint.security)

            stats["security"] = self.security_mapper.get_security_statistics(
                security_schemes, security_requirements
            )

        # Search statistics
        if search_index:
            stats["search"] = self.search_optimizer.get_search_statistics(search_index)

        # Quality metrics
        stats["quality_metrics"] = self._calculate_quality_metrics(
            endpoints, schemas, security_schemes
        )

        return stats

    def _calculate_quality_metrics(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
        security_schemes: Dict[str, NormalizedSecurityScheme],
    ) -> Dict[str, Any]:
        """Calculate quality metrics for the normalized data."""
        metrics = {
            "documentation_coverage": 0.0,
            "schema_complexity": 0.0,
            "security_coverage": 0.0,
            "completeness_score": 0.0,
            "overall_quality_score": 0.0,
        }

        if not endpoints:
            return metrics

        # Documentation coverage
        documented_endpoints = sum(
            1 for ep in endpoints if ep.description or ep.summary
        )
        metrics["documentation_coverage"] = documented_endpoints / len(endpoints) * 100

        # Schema complexity (average properties per schema)
        if schemas:
            total_properties = sum(
                len(schema.properties) for schema in schemas.values()
            )
            metrics["schema_complexity"] = total_properties / len(schemas)

        # Security coverage
        secured_endpoints = sum(1 for ep in endpoints if ep.security)
        if endpoints:
            metrics["security_coverage"] = secured_endpoints / len(endpoints) * 100

        # Completeness score (endpoints with operation IDs)
        complete_endpoints = sum(1 for ep in endpoints if ep.operation_id)
        metrics["completeness_score"] = complete_endpoints / len(endpoints) * 100

        # Overall quality score (weighted average)
        quality_components = [
            (metrics["documentation_coverage"], 0.3),
            (metrics["security_coverage"], 0.2),
            (metrics["completeness_score"], 0.3),
            (min(100, metrics["schema_complexity"] * 10), 0.2),  # Cap at 100
        ]

        weighted_sum = sum(score * weight for score, weight in quality_components)
        metrics["overall_quality_score"] = weighted_sum

        return metrics

    def get_normalization_summary(self, result: NormalizationResult) -> Dict[str, Any]:
        """Generate a human-readable summary of normalization results.

        Args:
            result: Normalization result to summarize

        Returns:
            Dictionary with summary information
        """
        summary = {
            "success": len(result.errors) == 0,
            "components": {
                "endpoints": len(result.endpoints),
                "schemas": len(result.schemas),
                "security_schemes": len(result.security_schemes),
            },
            "issues": {
                "errors": len(result.errors),
                "warnings": len(result.warnings),
            },
            "quality": result.statistics.get("quality_metrics", {}),
            "search_ready": result.search_index is not None,
            "recommendations": [],
        }

        # Add recommendations based on results
        if result.consistency_report and "recommendations" in result.consistency_report:
            summary["recommendations"].extend(
                result.consistency_report["recommendations"]
            )

        # Quality-based recommendations
        quality = summary["quality"]
        if quality.get("documentation_coverage", 0) < 50:
            summary["recommendations"].append(
                "Consider adding descriptions to more endpoints for better documentation"
            )

        if quality.get("security_coverage", 0) < 80:
            summary["recommendations"].append(
                "Review security requirements - many endpoints may lack proper authentication"
            )

        if quality.get("completeness_score", 0) < 70:
            summary["recommendations"].append(
                "Add operation IDs to endpoints to improve API tooling compatibility"
            )

        return summary
