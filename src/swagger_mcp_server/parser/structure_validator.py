"""OpenAPI structure validation and preservation utilities."""

import copy
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Set, Union

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.parser.base import ParseError, SwaggerParseError
from swagger_mcp_server.parser.error_handler import ErrorContext, ErrorHandler

logger = get_logger(__name__)


class StructureValidator:
    """Validates and preserves OpenAPI document structure."""

    def __init__(self, error_handler: ErrorHandler, preserve_order: bool = True):
        """Initialize structure validator.

        Args:
            error_handler: Error handler for recording issues
            preserve_order: Whether to preserve key ordering
        """
        self.error_handler = error_handler
        self.preserve_order = preserve_order
        self.logger = get_logger(__name__)

        # OpenAPI required fields by section
        self.required_fields = {
            "root": {"openapi", "info", "paths"},
            "info": {"title", "version"},
            "paths": {},  # Paths object can be empty
            "components": {},  # Components is optional
        }

        # Expected types for major sections
        self.expected_types = {
            "openapi": str,
            "swagger": str,  # For Swagger 2.0
            "info": dict,
            "paths": dict,
            "components": dict,
            "servers": list,
            "security": list,
            "tags": list,
            "externalDocs": dict,
        }

    def validate_and_preserve_structure(
        self, data: Dict[str, Any], file_path: str
    ) -> Dict[str, Any]:
        """Validate OpenAPI structure and preserve all data.

        Args:
            data: Parsed JSON data
            file_path: Source file path for error context

        Returns:
            Validated and preserved structure

        Raises:
            SwaggerParseError: If structure is fundamentally invalid
        """
        try:
            # Create preserved copy
            if self.preserve_order and not isinstance(data, OrderedDict):
                preserved_data = self._convert_to_ordered_dict(data)
            else:
                preserved_data = copy.deepcopy(data)

            # Validate root structure
            self._validate_root_structure(preserved_data, file_path)

            # Validate and preserve major sections
            self._validate_info_section(preserved_data, file_path)
            self._validate_paths_section(preserved_data, file_path)
            self._validate_components_section(preserved_data, file_path)
            self._validate_servers_section(preserved_data, file_path)

            # Preserve all extensions and vendor properties
            self._preserve_extensions(preserved_data)

            # Validate data integrity
            self._validate_data_integrity(data, preserved_data, file_path)

            self.logger.info(
                "Structure validation completed",
                file_path=file_path,
                errors=len(self.error_handler.errors),
                warnings=len(self.error_handler.warnings),
                extensions_preserved=self._count_extensions(preserved_data),
            )

            return preserved_data

        except Exception as e:
            if isinstance(e, SwaggerParseError):
                raise
            raise SwaggerParseError(
                f"Structure validation failed: {str(e)}",
                "StructureValidationError",
                suggestion="Check OpenAPI specification format and required fields",
            )

    def _validate_root_structure(self, data: Dict[str, Any], file_path: str) -> None:
        """Validate root OpenAPI document structure.

        Args:
            data: Document data
            file_path: File path for error context
        """
        context = ErrorContext(file_path=file_path, section_path="root")

        # Check for OpenAPI or Swagger version
        openapi_version = data.get("openapi")
        swagger_version = data.get("swagger")

        if not openapi_version and not swagger_version:
            recovery, error = self.error_handler.handle_structure_error(
                "root", "openapi or swagger field", None, context
            )
            self.error_handler.add_error(error)

            if not error.recoverable:
                raise SwaggerParseError(
                    "Missing required 'openapi' or 'swagger' version field",
                    "MissingVersionField",
                )

        # Validate required root fields
        for field in self.required_fields["root"]:
            if field not in data:
                error = ParseError(
                    message=f"Missing required field: {field}",
                    error_type="MissingRequiredField",
                    context=f"Root level field: {field}",
                    recoverable=field != "openapi",
                    suggestion=f"Add required field '{field}' to document root",
                )
                self.error_handler.add_error(error)

        # Validate field types
        for field, expected_type in self.expected_types.items():
            if field in data and not isinstance(data[field], expected_type):
                recovery, error = self.error_handler.handle_structure_error(
                    f"root.{field}",
                    expected_type.__name__,
                    data[field],
                    context,
                )
                self.error_handler.add_error(error)

    def _validate_info_section(self, data: Dict[str, Any], file_path: str) -> None:
        """Validate info section structure.

        Args:
            data: Document data
            file_path: File path for error context
        """
        if "info" not in data:
            return

        info = data["info"]
        context = ErrorContext(file_path=file_path, section_path="info")

        if not isinstance(info, dict):
            recovery, error = self.error_handler.handle_structure_error(
                "info", "object", info, context
            )
            self.error_handler.add_error(error)
            return

        # Check required info fields
        for field in self.required_fields["info"]:
            if field not in info:
                error = ParseError(
                    message=f"Missing required field in info: {field}",
                    error_type="MissingRequiredField",
                    context=f"info.{field}",
                    recoverable=False,
                    suggestion=f"Add required field 'info.{field}'",
                )
                self.error_handler.add_error(error)

        # Validate field types
        field_types = {
            "title": str,
            "version": str,
            "description": str,
            "termsOfService": str,
            "contact": dict,
            "license": dict,
        }

        for field, expected_type in field_types.items():
            if field in info and not isinstance(info[field], expected_type):
                recovery, error = self.error_handler.handle_structure_error(
                    f"info.{field}",
                    expected_type.__name__,
                    info[field],
                    context,
                )
                self.error_handler.add_error(error)

    def _validate_paths_section(self, data: Dict[str, Any], file_path: str) -> None:
        """Validate paths section structure.

        Args:
            data: Document data
            file_path: File path for error context
        """
        if "paths" not in data:
            return

        paths = data["paths"]
        context = ErrorContext(file_path=file_path, section_path="paths")

        if not isinstance(paths, dict):
            recovery, error = self.error_handler.handle_structure_error(
                "paths", "object", paths, context
            )
            self.error_handler.add_error(error)
            return

        # Validate each path
        valid_http_methods = {
            "get",
            "put",
            "post",
            "delete",
            "options",
            "head",
            "patch",
            "trace",
        }

        for path_name, path_data in paths.items():
            if not isinstance(path_name, str) or not path_name.startswith("/"):
                error = ParseError(
                    message=f"Invalid path name: {path_name}",
                    error_type="InvalidPathName",
                    context=f"paths.{path_name}",
                    recoverable=True,
                    suggestion="Path names must be strings starting with '/'",
                )
                self.error_handler.add_error(error)
                continue

            if not isinstance(path_data, dict):
                recovery, error = self.error_handler.handle_structure_error(
                    f"paths.{path_name}", "object", path_data, context
                )
                self.error_handler.add_error(error)
                continue

            # Validate HTTP methods and operations
            for method_name, operation in path_data.items():
                if method_name.lower() in valid_http_methods:
                    if not isinstance(operation, dict):
                        (
                            recovery,
                            error,
                        ) = self.error_handler.handle_structure_error(
                            f"paths.{path_name}.{method_name}",
                            "object",
                            operation,
                            context,
                        )
                        self.error_handler.add_error(error)

    def _validate_components_section(
        self, data: Dict[str, Any], file_path: str
    ) -> None:
        """Validate components section structure.

        Args:
            data: Document data
            file_path: File path for error context
        """
        if "components" not in data:
            return

        components = data["components"]
        context = ErrorContext(file_path=file_path, section_path="components")

        if not isinstance(components, dict):
            recovery, error = self.error_handler.handle_structure_error(
                "components", "object", components, context
            )
            self.error_handler.add_error(error)
            return

        # Validate component subsections
        component_sections = [
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

        for section_name in component_sections:
            if section_name in components:
                section_data = components[section_name]
                if not isinstance(section_data, dict):
                    (
                        recovery,
                        error,
                    ) = self.error_handler.handle_structure_error(
                        f"components.{section_name}",
                        "object",
                        section_data,
                        context,
                    )
                    self.error_handler.add_error(error)

    def _validate_servers_section(self, data: Dict[str, Any], file_path: str) -> None:
        """Validate servers section structure.

        Args:
            data: Document data
            file_path: File path for error context
        """
        if "servers" not in data:
            return

        servers = data["servers"]
        context = ErrorContext(file_path=file_path, section_path="servers")

        if not isinstance(servers, list):
            recovery, error = self.error_handler.handle_structure_error(
                "servers", "array", servers, context
            )
            self.error_handler.add_error(error)
            return

        # Validate each server object
        for i, server in enumerate(servers):
            if not isinstance(server, dict):
                recovery, error = self.error_handler.handle_structure_error(
                    f"servers[{i}]", "object", server, context
                )
                self.error_handler.add_error(error)
                continue

            if "url" not in server:
                error = ParseError(
                    message=f"Server object missing required 'url' field at index {i}",
                    error_type="MissingRequiredField",
                    context=f"servers[{i}]",
                    recoverable=True,
                    suggestion="Add 'url' field to server object",
                )
                self.error_handler.add_error(error)

    def _preserve_extensions(self, data: Any) -> None:
        """Recursively preserve all extension properties (x-*).

        Args:
            data: Data to scan for extensions
        """
        if isinstance(data, dict):
            # Extensions are already preserved in the deep copy
            # Just log them for tracking
            extensions = [
                k for k in data.keys() if isinstance(k, str) and k.startswith("x-")
            ]
            if extensions:
                self.logger.debug(
                    "Extensions preserved",
                    extensions=extensions,
                    count=len(extensions),
                )

            # Recursively process nested objects
            for value in data.values():
                self._preserve_extensions(value)
        elif isinstance(data, list):
            for item in data:
                self._preserve_extensions(item)

    def _validate_data_integrity(
        self,
        original: Dict[str, Any],
        preserved: Dict[str, Any],
        file_path: str,
    ) -> None:
        """Validate that no data was lost during preservation.

        Args:
            original: Original parsed data
            preserved: Preserved data structure
            file_path: File path for error context
        """
        try:
            # Check that all original keys are preserved
            missing_keys = self._find_missing_keys(original, preserved)
            if missing_keys:
                error = ParseError(
                    message=f"Data integrity check failed: missing keys {missing_keys}",
                    error_type="DataIntegrityError",
                    context="Structure preservation",
                    recoverable=False,
                    suggestion="Report this as a parser bug",
                )
                self.error_handler.add_error(error)

            # Check extension preservation
            original_extensions = self._count_extensions(original)
            preserved_extensions = self._count_extensions(preserved)

            if preserved_extensions != original_extensions:
                self.logger.warning(
                    "Extension count mismatch",
                    original_count=original_extensions,
                    preserved_count=preserved_extensions,
                    file_path=file_path,
                )

        except Exception as e:
            self.logger.error(
                "Data integrity validation failed",
                error=str(e),
                file_path=file_path,
            )

    def _convert_to_ordered_dict(self, data: Any) -> Any:
        """Recursively convert dictionaries to OrderedDict to preserve key order.

        Args:
            data: Data to convert

        Returns:
            Converted data with OrderedDict instances
        """
        if isinstance(data, dict):
            ordered = OrderedDict()
            for key, value in data.items():
                ordered[key] = self._convert_to_ordered_dict(value)
            return ordered
        elif isinstance(data, list):
            return [self._convert_to_ordered_dict(item) for item in data]
        else:
            return data

    def _find_missing_keys(
        self, original: Any, preserved: Any, path: str = ""
    ) -> List[str]:
        """Find keys that exist in original but not in preserved data.

        Args:
            original: Original data
            preserved: Preserved data
            path: Current path for error reporting

        Returns:
            List of missing key paths
        """
        missing = []

        if isinstance(original, dict) and isinstance(preserved, dict):
            for key in original.keys():
                current_path = f"{path}.{key}" if path else str(key)
                if key not in preserved:
                    missing.append(current_path)
                else:
                    missing.extend(
                        self._find_missing_keys(
                            original[key], preserved[key], current_path
                        )
                    )
        elif isinstance(original, list) and isinstance(preserved, list):
            if len(original) != len(preserved):
                missing.append(
                    f"{path}[length mismatch: {len(original)} vs {len(preserved)}]"
                )
            else:
                for i, (orig_item, pres_item) in enumerate(zip(original, preserved)):
                    current_path = f"{path}[{i}]" if path else f"[{i}]"
                    missing.extend(
                        self._find_missing_keys(orig_item, pres_item, current_path)
                    )

        return missing

    def _count_extensions(self, data: Any) -> int:
        """Count extension properties recursively.

        Args:
            data: Data to scan

        Returns:
            Number of extension properties found
        """
        count = 0

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(key, str) and key.startswith("x-"):
                    count += 1
                count += self._count_extensions(value)
        elif isinstance(data, list):
            for item in data:
                count += self._count_extensions(item)

        return count
