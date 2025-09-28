"""OpenAPI 3.x specification compliance validation."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from openapi_spec_validator import validate_spec
    from openapi_spec_validator.exceptions import OpenAPIValidationError

    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.parser.base import ParseError, SwaggerParseError
from swagger_mcp_server.parser.error_handler import ErrorContext, ErrorHandler

logger = get_logger(__name__)


class OpenAPIVersion(Enum):
    """Supported OpenAPI versions."""

    SWAGGER_2_0 = "2.0"
    OPENAPI_3_0_0 = "3.0.0"
    OPENAPI_3_0_1 = "3.0.1"
    OPENAPI_3_0_2 = "3.0.2"
    OPENAPI_3_0_3 = "3.0.3"
    OPENAPI_3_1_0 = "3.1.0"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of OpenAPI validation."""

    is_valid: bool
    version: OpenAPIVersion
    errors: List[ParseError]
    warnings: List[ParseError]
    spec_url: Optional[str] = None
    validation_duration_ms: float = 0.0


class OpenAPIValidator:
    """Validates OpenAPI 3.x specification compliance."""

    def __init__(self, error_handler: ErrorHandler, strict_mode: bool = False):
        """Initialize OpenAPI validator.

        Args:
            error_handler: Error handler for recording issues
            strict_mode: If True, treat warnings as errors
        """
        self.error_handler = error_handler
        self.strict_mode = strict_mode
        self.logger = get_logger(__name__)

        # Version detection patterns
        self.version_patterns = {
            OpenAPIVersion.SWAGGER_2_0: r"^2\.0$",
            OpenAPIVersion.OPENAPI_3_0_0: r"^3\.0\.0$",
            OpenAPIVersion.OPENAPI_3_0_1: r"^3\.0\.1$",
            OpenAPIVersion.OPENAPI_3_0_2: r"^3\.0\.2$",
            OpenAPIVersion.OPENAPI_3_0_3: r"^3\.0\.3$",
            OpenAPIVersion.OPENAPI_3_1_0: r"^3\.1\.0$",
        }

    async def validate_specification(
        self, data: Dict[str, Any], file_path: str
    ) -> ValidationResult:
        """Validate OpenAPI specification compliance.

        Args:
            data: Parsed OpenAPI document
            file_path: Source file path

        Returns:
            Validation result with errors and warnings
        """
        import time

        start_time = time.time()

        try:
            # Detect OpenAPI version
            version = self._detect_openapi_version(data)

            self.logger.info(
                "Starting OpenAPI validation",
                file_path=file_path,
                detected_version=version.value,
                validator_available=VALIDATOR_AVAILABLE,
            )

            # Initialize result
            result = ValidationResult(
                is_valid=True, version=version, errors=[], warnings=[]
            )

            # Perform version-specific validation
            if version == OpenAPIVersion.SWAGGER_2_0:
                await self._validate_swagger_2_0(data, file_path, result)
            elif version in [
                OpenAPIVersion.OPENAPI_3_0_0,
                OpenAPIVersion.OPENAPI_3_0_1,
                OpenAPIVersion.OPENAPI_3_0_2,
                OpenAPIVersion.OPENAPI_3_0_3,
            ]:
                await self._validate_openapi_3_0(data, file_path, result)
            elif version == OpenAPIVersion.OPENAPI_3_1_0:
                await self._validate_openapi_3_1(data, file_path, result)
            else:
                error = ParseError(
                    message=f"Unsupported OpenAPI version: {version.value}",
                    error_type="UnsupportedVersion",
                    recoverable=False,
                    suggestion="Use supported versions: 2.0, 3.0.x, or 3.1.0",
                )
                result.errors.append(error)
                result.is_valid = False

            # Use openapi-spec-validator if available
            if VALIDATOR_AVAILABLE and result.is_valid:
                await self._validate_with_spec_validator(data, result)

            # Custom validation rules
            await self._apply_custom_validation_rules(data, file_path, result)

            # Final validation status
            result.is_valid = len(result.errors) == 0

            # Record errors in error handler
            for error in result.errors:
                self.error_handler.add_error(error)
            for warning in result.warnings:
                self.error_handler.add_error(warning)

            result.validation_duration_ms = (time.time() - start_time) * 1000

            self.logger.info(
                "OpenAPI validation completed",
                file_path=file_path,
                is_valid=result.is_valid,
                errors=len(result.errors),
                warnings=len(result.warnings),
                duration_ms=result.validation_duration_ms,
            )

            return result

        except Exception as e:
            error_msg = f"Validation failed: {str(e)}"
            self.logger.error(
                "OpenAPI validation error",
                error=error_msg,
                file_path=file_path,
            )

            result = ValidationResult(
                is_valid=False,
                version=OpenAPIVersion.UNKNOWN,
                errors=[
                    ParseError(
                        message=error_msg,
                        error_type="ValidationError",
                        recoverable=False,
                    )
                ],
                warnings=[],
                validation_duration_ms=(time.time() - start_time) * 1000,
            )

            return result

    def _detect_openapi_version(self, data: Dict[str, Any]) -> OpenAPIVersion:
        """Detect OpenAPI specification version.

        Args:
            data: Parsed document data

        Returns:
            Detected OpenAPI version
        """
        # Check for OpenAPI 3.x version
        openapi_version = data.get("openapi")
        if openapi_version:
            version_str = str(openapi_version)
            for version_enum, pattern in self.version_patterns.items():
                if version_enum != OpenAPIVersion.SWAGGER_2_0 and re.match(
                    pattern, version_str
                ):
                    return version_enum

            # Check for 3.x.x pattern (future versions)
            if re.match(r"^3\.\d+\.\d+$", version_str):
                self.logger.warning(
                    "Detected future OpenAPI 3.x version",
                    version=version_str,
                    message="Treating as OpenAPI 3.0.3 for validation",
                )
                return OpenAPIVersion.OPENAPI_3_0_3

        # Check for Swagger 2.0
        swagger_version = data.get("swagger")
        if swagger_version and str(swagger_version) == "2.0":
            return OpenAPIVersion.SWAGGER_2_0

        return OpenAPIVersion.UNKNOWN

    async def _validate_swagger_2_0(
        self, data: Dict[str, Any], file_path: str, result: ValidationResult
    ) -> None:
        """Validate Swagger 2.0 specification.

        Args:
            data: Document data
            file_path: Source file path
            result: Validation result to update
        """
        # Basic Swagger 2.0 validation
        required_fields = ["swagger", "info", "paths"]

        for field in required_fields:
            if field not in data:
                result.errors.append(
                    ParseError(
                        message=f"Missing required field: {field}",
                        error_type="MissingRequiredField",
                        recoverable=False,
                        suggestion=f"Add required field '{field}' to Swagger 2.0 document",
                    )
                )

        # Note about OpenAPI 3.x migration
        result.warnings.append(
            ParseError(
                message="Swagger 2.0 is deprecated, consider migrating to OpenAPI 3.x",
                error_type="DeprecatedVersion",
                recoverable=True,
                suggestion="Use OpenAPI 3.x for new APIs and consider migrating existing ones",
            )
        )

    async def _validate_openapi_3_0(
        self, data: Dict[str, Any], file_path: str, result: ValidationResult
    ) -> None:
        """Validate OpenAPI 3.0.x specification.

        Args:
            data: Document data
            file_path: Source file path
            result: Validation result to update
        """
        # Required root fields for OpenAPI 3.0
        required_fields = ["openapi", "info", "paths"]

        for field in required_fields:
            if field not in data:
                result.errors.append(
                    ParseError(
                        message=f"Missing required field: {field}",
                        error_type="MissingRequiredField",
                        recoverable=False,
                        suggestion=f"Add required field '{field}' to OpenAPI 3.0 document",
                    )
                )

        # Validate info object
        if "info" in data:
            await self._validate_info_object(data["info"], result)

        # Validate paths object
        if "paths" in data:
            await self._validate_paths_object(data["paths"], result)

        # Validate components if present
        if "components" in data:
            await self._validate_components_object(data["components"], result)

    async def _validate_openapi_3_1(
        self, data: Dict[str, Any], file_path: str, result: ValidationResult
    ) -> None:
        """Validate OpenAPI 3.1.0 specification.

        Args:
            data: Document data
            file_path: Source file path
            result: Validation result to update
        """
        # OpenAPI 3.1 has same basic structure as 3.0
        await self._validate_openapi_3_0(data, file_path, result)

        # Additional 3.1 specific validations can be added here
        result.warnings.append(
            ParseError(
                message="OpenAPI 3.1.0 support is experimental",
                error_type="ExperimentalVersion",
                recoverable=True,
                suggestion="Thoroughly test with your toolchain compatibility",
            )
        )

    async def _validate_with_spec_validator(
        self, data: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate using openapi-spec-validator library.

        Args:
            data: Document data
            result: Validation result to update
        """
        if not VALIDATOR_AVAILABLE:
            result.warnings.append(
                ParseError(
                    message="openapi-spec-validator not available for detailed validation",
                    error_type="ValidatorUnavailable",
                    recoverable=True,
                    suggestion="Install openapi-spec-validator for enhanced validation",
                )
            )
            return

        try:
            # Use the spec validator
            validate_spec(data)

        except OpenAPIValidationError as e:
            # Convert validator errors to our format
            result.errors.append(
                ParseError(
                    message=f"OpenAPI specification validation failed: {str(e)}",
                    error_type="SpecificationValidationError",
                    recoverable=False,
                    suggestion="Fix OpenAPI specification according to official schema",
                )
            )

        except Exception as e:
            result.warnings.append(
                ParseError(
                    message=f"Spec validator error: {str(e)}",
                    error_type="ValidatorError",
                    recoverable=True,
                    suggestion="Check if document structure is valid OpenAPI format",
                )
            )

    async def _validate_info_object(self, info: Any, result: ValidationResult) -> None:
        """Validate info object structure.

        Args:
            info: Info object data
            result: Validation result to update
        """
        if not isinstance(info, dict):
            result.errors.append(
                ParseError(
                    message="Info object must be an object",
                    error_type="InvalidInfoType",
                    recoverable=False,
                    suggestion="Ensure 'info' is an object with title and version",
                )
            )
            return

        # Required fields
        required_fields = ["title", "version"]
        for field in required_fields:
            if field not in info:
                result.errors.append(
                    ParseError(
                        message=f"Missing required field in info: {field}",
                        error_type="MissingRequiredField",
                        recoverable=False,
                        suggestion=f"Add required field 'info.{field}'",
                    )
                )

        # Type validation
        if "title" in info and not isinstance(info["title"], str):
            result.errors.append(
                ParseError(
                    message="Info title must be a string",
                    error_type="InvalidFieldType",
                    recoverable=False,
                    suggestion="Ensure 'info.title' is a string value",
                )
            )

        if "version" in info and not isinstance(info["version"], str):
            result.errors.append(
                ParseError(
                    message="Info version must be a string",
                    error_type="InvalidFieldType",
                    recoverable=False,
                    suggestion="Ensure 'info.version' is a string value",
                )
            )

    async def _validate_paths_object(
        self, paths: Any, result: ValidationResult
    ) -> None:
        """Validate paths object structure.

        Args:
            paths: Paths object data
            result: Validation result to update
        """
        if not isinstance(paths, dict):
            result.errors.append(
                ParseError(
                    message="Paths object must be an object",
                    error_type="InvalidPathsType",
                    recoverable=False,
                    suggestion="Ensure 'paths' is an object with path items",
                )
            )
            return

        # Validate each path
        for path_name, path_item in paths.items():
            if not isinstance(path_name, str) or not path_name.startswith("/"):
                result.errors.append(
                    ParseError(
                        message=f"Invalid path name: {path_name}",
                        error_type="InvalidPathName",
                        recoverable=True,
                        suggestion="Path names must be strings starting with '/'",
                    )
                )

            if not isinstance(path_item, dict):
                result.errors.append(
                    ParseError(
                        message=f"Path item must be an object: {path_name}",
                        error_type="InvalidPathItemType",
                        recoverable=True,
                        suggestion="Ensure path items are objects with operation methods",
                    )
                )

    async def _validate_components_object(
        self, components: Any, result: ValidationResult
    ) -> None:
        """Validate components object structure.

        Args:
            components: Components object data
            result: Validation result to update
        """
        if not isinstance(components, dict):
            result.errors.append(
                ParseError(
                    message="Components object must be an object",
                    error_type="InvalidComponentsType",
                    recoverable=False,
                    suggestion="Ensure 'components' is an object",
                )
            )
            return

        # Validate component sections
        valid_sections = [
            "schemas",
            "responses",
            "parameters",
            "examples",
            "requestBodies",
            "headers",
            "securitySchemes",
            "links",
            "callbacks",
        ]

        for section_name, section_data in components.items():
            if section_name not in valid_sections:
                result.warnings.append(
                    ParseError(
                        message=f"Unknown component section: {section_name}",
                        error_type="UnknownComponentSection",
                        recoverable=True,
                        suggestion=f"Valid sections: {', '.join(valid_sections)}",
                    )
                )

            if not isinstance(section_data, dict):
                result.errors.append(
                    ParseError(
                        message=f"Component section must be an object: {section_name}",
                        error_type="InvalidComponentSectionType",
                        recoverable=True,
                        suggestion="Component sections must be objects",
                    )
                )

    async def _apply_custom_validation_rules(
        self, data: Dict[str, Any], file_path: str, result: ValidationResult
    ) -> None:
        """Apply custom validation rules beyond standard OpenAPI validation.

        Args:
            data: Document data
            file_path: Source file path
            result: Validation result to update
        """
        # Check for common issues and best practices

        # 1. Check for empty paths
        paths = data.get("paths", {})
        if isinstance(paths, dict) and len(paths) == 0:
            result.warnings.append(
                ParseError(
                    message="No paths defined in API specification",
                    error_type="EmptyPaths",
                    recoverable=True,
                    suggestion="Add at least one path to make the API functional",
                )
            )

        # 2. Check for missing descriptions
        info = data.get("info", {})
        if isinstance(info, dict) and "description" not in info:
            result.warnings.append(
                ParseError(
                    message="API description is missing from info object",
                    error_type="MissingDescription",
                    recoverable=True,
                    suggestion="Add 'info.description' to help users understand your API",
                )
            )

        # 3. Check for security definitions usage
        if "components" in data and isinstance(data["components"], dict):
            security_schemes = data["components"].get("securitySchemes", {})
            global_security = data.get("security", [])

            if security_schemes and not global_security:
                result.warnings.append(
                    ParseError(
                        message="Security schemes defined but not used globally",
                        error_type="UnusedSecuritySchemes",
                        recoverable=True,
                        suggestion="Add global security requirements or apply to individual operations",
                    )
                )

        # 4. Check for server definitions
        servers = data.get("servers", [])
        if not servers:
            result.warnings.append(
                ParseError(
                    message="No servers defined",
                    error_type="MissingServers",
                    recoverable=True,
                    suggestion="Add server URLs to help users understand where to make requests",
                )
            )

        self.logger.debug(
            "Custom validation rules applied",
            file_path=file_path,
            additional_warnings=len(
                [
                    w
                    for w in result.warnings
                    if w.error_type.startswith("Missing")
                    or w.error_type.startswith("Empty")
                    or w.error_type.startswith("Unused")
                ]
            ),
        )
