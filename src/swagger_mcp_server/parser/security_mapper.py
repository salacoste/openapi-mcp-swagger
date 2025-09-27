"""Security scheme mapping and normalization for OpenAPI documents."""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.parser.models import (
    NormalizedSecurityFlow,
    NormalizedSecurityRequirement,
    NormalizedSecurityScheme,
    SecurityFlowType,
    SecuritySchemeLocation,
    SecuritySchemeType,
)

logger = get_logger(__name__)


class SecurityMapper:
    """Maps and normalizes OpenAPI security schemes and requirements."""

    def __init__(self):
        self.logger = get_logger(__name__)

        # Security scheme type mapping
        self.scheme_type_map = {
            "apiKey": SecuritySchemeType.API_KEY,
            "http": SecuritySchemeType.HTTP,
            "oauth2": SecuritySchemeType.OAUTH2,
            "openIdConnect": SecuritySchemeType.OPEN_ID_CONNECT,
            "mutualTLS": SecuritySchemeType.MUTUAL_TLS,
        }

        # API key location mapping
        self.location_map = {
            "query": SecuritySchemeLocation.QUERY,
            "header": SecuritySchemeLocation.HEADER,
            "cookie": SecuritySchemeLocation.COOKIE,
        }

        # OAuth2 flow type mapping
        self.flow_type_map = {
            "implicit": SecurityFlowType.IMPLICIT,
            "password": SecurityFlowType.PASSWORD,
            "clientCredentials": SecurityFlowType.CLIENT_CREDENTIALS,
            "authorizationCode": SecurityFlowType.AUTHORIZATION_CODE,
        }

    def normalize_security_schemes(
        self, components_data: Dict[str, Any]
    ) -> Tuple[Dict[str, NormalizedSecurityScheme], List[str], List[str]]:
        """Normalize all security schemes from OpenAPI components.

        Args:
            components_data: OpenAPI components object

        Returns:
            Tuple of (normalized_schemes, errors, warnings)
        """
        normalized_schemes = {}
        errors = []
        warnings = []

        if not isinstance(components_data, dict):
            errors.append("Components data must be a dictionary")
            return normalized_schemes, errors, warnings

        security_schemes = components_data.get("securitySchemes", {})
        if not isinstance(security_schemes, dict):
            warnings.append("Security schemes must be a dictionary")
            return normalized_schemes, errors, warnings

        self.logger.info(
            "Starting security scheme normalization",
            schemes_count=len(security_schemes),
        )

        for scheme_name, scheme_data in security_schemes.items():
            if not isinstance(scheme_name, str):
                warnings.append(
                    f"Skipping non-string scheme name: {scheme_name}"
                )
                continue

            if not isinstance(scheme_data, dict):
                errors.append(f"Security scheme must be object: {scheme_name}")
                continue

            try:
                normalized_scheme = self._normalize_single_scheme(
                    scheme_name=scheme_name, scheme_data=scheme_data
                )

                normalized_schemes[scheme_name] = normalized_scheme

            except Exception as e:
                error_msg = f"Failed to normalize security scheme {scheme_name}: {str(e)}"
                errors.append(error_msg)
                self.logger.error(
                    "Security scheme normalization failed",
                    scheme=scheme_name,
                    error=str(e),
                )

        self.logger.info(
            "Security scheme normalization completed",
            schemes_normalized=len(normalized_schemes),
            errors=len(errors),
            warnings=len(warnings),
        )

        return normalized_schemes, errors, warnings

    def _normalize_single_scheme(
        self, scheme_name: str, scheme_data: Dict[str, Any]
    ) -> NormalizedSecurityScheme:
        """Normalize a single security scheme.

        Args:
            scheme_name: Security scheme identifier
            scheme_data: Scheme definition data

        Returns:
            Normalized security scheme
        """
        # Handle references
        if "$ref" in scheme_data:
            return NormalizedSecurityScheme(
                name=scheme_name,
                type=SecuritySchemeType.HTTP,  # Will be resolved later
                description=f"Reference: {scheme_data['$ref']}",
                extensions={"$ref": scheme_data["$ref"]},
            )

        # Extract basic properties
        scheme_type_str = scheme_data.get("type")
        if not scheme_type_str:
            raise ValueError(f"Security scheme must have 'type' property")

        if scheme_type_str not in self.scheme_type_map:
            raise ValueError(
                f"Unknown security scheme type: {scheme_type_str}"
            )

        scheme_type = self.scheme_type_map[scheme_type_str]
        description = scheme_data.get("description")

        # Type-specific processing
        if scheme_type == SecuritySchemeType.API_KEY:
            return self._normalize_api_key_scheme(
                scheme_name, scheme_data, description
            )
        elif scheme_type == SecuritySchemeType.HTTP:
            return self._normalize_http_scheme(
                scheme_name, scheme_data, description
            )
        elif scheme_type == SecuritySchemeType.OAUTH2:
            return self._normalize_oauth2_scheme(
                scheme_name, scheme_data, description
            )
        elif scheme_type == SecuritySchemeType.OPEN_ID_CONNECT:
            return self._normalize_openid_scheme(
                scheme_name, scheme_data, description
            )
        elif scheme_type == SecuritySchemeType.MUTUAL_TLS:
            return self._normalize_mutual_tls_scheme(
                scheme_name, scheme_data, description
            )
        else:
            raise ValueError(
                f"Unsupported security scheme type: {scheme_type}"
            )

    def _normalize_api_key_scheme(
        self,
        scheme_name: str,
        scheme_data: Dict[str, Any],
        description: Optional[str],
    ) -> NormalizedSecurityScheme:
        """Normalize API key security scheme."""
        name = scheme_data.get("name")
        if not name:
            raise ValueError("API key scheme must have 'name' property")

        location_str = scheme_data.get("in")
        if not location_str:
            raise ValueError("API key scheme must have 'in' property")

        if location_str not in self.location_map:
            raise ValueError(f"Unknown API key location: {location_str}")

        location = self.location_map[location_str]

        return NormalizedSecurityScheme(
            name=scheme_name,
            type=SecuritySchemeType.API_KEY,
            description=description,
            api_key_name=name,
            api_key_location=location,
            extensions=self._extract_extensions(scheme_data),
        )

    def _normalize_http_scheme(
        self,
        scheme_name: str,
        scheme_data: Dict[str, Any],
        description: Optional[str],
    ) -> NormalizedSecurityScheme:
        """Normalize HTTP security scheme."""
        http_scheme = scheme_data.get("scheme")
        if not http_scheme:
            raise ValueError("HTTP scheme must have 'scheme' property")

        bearer_format = scheme_data.get("bearerFormat")

        return NormalizedSecurityScheme(
            name=scheme_name,
            type=SecuritySchemeType.HTTP,
            description=description,
            http_scheme=http_scheme,
            bearer_format=bearer_format,
            extensions=self._extract_extensions(scheme_data),
        )

    def _normalize_oauth2_scheme(
        self,
        scheme_name: str,
        scheme_data: Dict[str, Any],
        description: Optional[str],
    ) -> NormalizedSecurityScheme:
        """Normalize OAuth2 security scheme."""
        flows_data = scheme_data.get("flows", {})
        if not isinstance(flows_data, dict):
            raise ValueError("OAuth2 scheme must have 'flows' object")

        flows = {}
        for flow_name, flow_data in flows_data.items():
            if flow_name not in self.flow_type_map:
                continue

            if not isinstance(flow_data, dict):
                continue

            flow_type = self.flow_type_map[flow_name]
            normalized_flow = self._normalize_oauth2_flow(flow_type, flow_data)
            flows[flow_type] = normalized_flow

        return NormalizedSecurityScheme(
            name=scheme_name,
            type=SecuritySchemeType.OAUTH2,
            description=description,
            oauth2_flows=flows,
            extensions=self._extract_extensions(scheme_data),
        )

    def _normalize_oauth2_flow(
        self, flow_type: SecurityFlowType, flow_data: Dict[str, Any]
    ) -> NormalizedSecurityFlow:
        """Normalize OAuth2 flow."""
        authorization_url = flow_data.get("authorizationUrl")
        token_url = flow_data.get("tokenUrl")
        refresh_url = flow_data.get("refreshUrl")
        scopes = flow_data.get("scopes", {})

        return NormalizedSecurityFlow(
            type=flow_type,
            authorization_url=authorization_url,
            token_url=token_url,
            refresh_url=refresh_url,
            scopes=scopes,
            extensions=self._extract_extensions(flow_data),
        )

    def _normalize_openid_scheme(
        self,
        scheme_name: str,
        scheme_data: Dict[str, Any],
        description: Optional[str],
    ) -> NormalizedSecurityScheme:
        """Normalize OpenID Connect security scheme."""
        openid_connect_url = scheme_data.get("openIdConnectUrl")
        if not openid_connect_url:
            raise ValueError(
                "OpenID Connect scheme must have 'openIdConnectUrl'"
            )

        return NormalizedSecurityScheme(
            name=scheme_name,
            type=SecuritySchemeType.OPEN_ID_CONNECT,
            description=description,
            openid_connect_url=openid_connect_url,
            extensions=self._extract_extensions(scheme_data),
        )

    def _normalize_mutual_tls_scheme(
        self,
        scheme_name: str,
        scheme_data: Dict[str, Any],
        description: Optional[str],
    ) -> NormalizedSecurityScheme:
        """Normalize Mutual TLS security scheme."""
        return NormalizedSecurityScheme(
            name=scheme_name,
            type=SecuritySchemeType.MUTUAL_TLS,
            description=description,
            extensions=self._extract_extensions(scheme_data),
        )

    def analyze_security_requirements(
        self, security_requirements: List[List[NormalizedSecurityRequirement]]
    ) -> Dict[str, Any]:
        """Analyze security requirements for patterns and insights.

        Args:
            security_requirements: List of security requirement alternatives

        Returns:
            Dictionary with analysis results
        """
        analysis = {
            "total_alternatives": len(security_requirements),
            "schemes_used": set(),
            "scope_patterns": {},
            "security_levels": {},
            "optional_security": False,
            "multi_scheme_auth": False,
        }

        if not security_requirements:
            analysis["optional_security"] = True
            return analysis

        for alternative_group in security_requirements:
            if not alternative_group:
                analysis["optional_security"] = True
                continue

            if len(alternative_group) > 1:
                analysis["multi_scheme_auth"] = True

            for requirement in alternative_group:
                scheme_id = requirement.scheme_id
                analysis["schemes_used"].add(scheme_id)

                # Analyze scope patterns
                scopes = requirement.scopes
                for scope in scopes:
                    if scope not in analysis["scope_patterns"]:
                        analysis["scope_patterns"][scope] = 0
                    analysis["scope_patterns"][scope] += 1

                # Determine security level
                if len(scopes) == 0:
                    level = "basic"
                elif len(scopes) <= 3:
                    level = "standard"
                else:
                    level = "granular"

                if scheme_id not in analysis["security_levels"]:
                    analysis["security_levels"][scheme_id] = level

        # Convert sets to lists for JSON serialization
        analysis["schemes_used"] = list(analysis["schemes_used"])

        return analysis

    def validate_security_consistency(
        self,
        security_schemes: Dict[str, NormalizedSecurityScheme],
        security_requirements: List[List[NormalizedSecurityRequirement]],
    ) -> List[str]:
        """Validate consistency between security schemes and requirements.

        Args:
            security_schemes: Available security schemes
            security_requirements: Security requirements used

        Returns:
            List of validation error messages
        """
        errors = []
        scheme_names = set(security_schemes.keys())

        # Check that all referenced schemes exist
        for alternative_group in security_requirements:
            for requirement in alternative_group:
                scheme_id = requirement.scheme_id
                if scheme_id not in scheme_names:
                    errors.append(
                        f"Security requirement references undefined scheme: {scheme_id}"
                    )

        # Validate OAuth2 scopes
        for alternative_group in security_requirements:
            for requirement in alternative_group:
                scheme_id = requirement.scheme_id
                if scheme_id in security_schemes:
                    scheme = security_schemes[scheme_id]
                    if scheme.type == SecuritySchemeType.OAUTH2:
                        validation_errors = self._validate_oauth2_scopes(
                            requirement, scheme
                        )
                        errors.extend(validation_errors)

        return errors

    def _validate_oauth2_scopes(
        self,
        requirement: NormalizedSecurityRequirement,
        scheme: NormalizedSecurityScheme,
    ) -> List[str]:
        """Validate OAuth2 scopes against scheme definition."""
        errors = []

        if not scheme.oauth2_flows:
            return errors

        # Collect all available scopes from all flows
        available_scopes = set()
        for flow in scheme.oauth2_flows.values():
            if flow.scopes:
                available_scopes.update(flow.scopes.keys())

        # Check that required scopes are available
        for required_scope in requirement.scopes:
            if required_scope not in available_scopes:
                errors.append(
                    f"OAuth2 requirement uses undefined scope '{required_scope}' "
                    f"for scheme '{requirement.scheme_id}'"
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

    def get_security_statistics(
        self,
        security_schemes: Dict[str, NormalizedSecurityScheme],
        security_requirements: List[List[NormalizedSecurityRequirement]],
    ) -> Dict[str, Any]:
        """Generate statistics about security configuration.

        Args:
            security_schemes: Available security schemes
            security_requirements: Security requirements

        Returns:
            Dictionary with security statistics
        """
        stats = {
            "total_schemes": len(security_schemes),
            "scheme_types": {},
            "auth_required": len(security_requirements) > 0,
            "optional_auth": False,
            "multi_factor_auth": False,
            "oauth2_flows": {},
            "most_used_scopes": {},
            "security_coverage": 0.0,
        }

        # Analyze scheme types
        for scheme in security_schemes.values():
            scheme_type = scheme.type.value
            if scheme_type not in stats["scheme_types"]:
                stats["scheme_types"][scheme_type] = 0
            stats["scheme_types"][scheme_type] += 1

            # OAuth2 flow analysis
            if (
                scheme.type == SecuritySchemeType.OAUTH2
                and scheme.oauth2_flows
            ):
                for flow_type in scheme.oauth2_flows.keys():
                    flow_name = flow_type.value
                    if flow_name not in stats["oauth2_flows"]:
                        stats["oauth2_flows"][flow_name] = 0
                    stats["oauth2_flows"][flow_name] += 1

        # Analyze requirements
        if security_requirements:
            analysis = self.analyze_security_requirements(
                security_requirements
            )
            stats["optional_auth"] = analysis["optional_security"]
            stats["multi_factor_auth"] = analysis["multi_scheme_auth"]
            stats["most_used_scopes"] = analysis["scope_patterns"]

            # Calculate security coverage (schemes used vs available)
            if security_schemes:
                used_schemes = len(analysis["schemes_used"])
                total_schemes = len(security_schemes)
                stats["security_coverage"] = used_schemes / total_schemes

        return stats
