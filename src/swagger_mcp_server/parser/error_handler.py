"""Error handling and recovery mechanisms for parser operations."""

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.parser.base import ParseError, SwaggerParseError

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""

    CRITICAL = "critical"  # Prevents parsing entirely
    ERROR = "error"  # Major issue but may be recoverable
    WARNING = "warning"  # Minor issue, parsing can continue
    INFO = "info"  # Informational message


class RecoveryStrategy(Enum):
    """Error recovery strategies."""

    FAIL_FAST = "fail_fast"  # Stop on first error
    SKIP_SECTION = "skip_section"  # Skip problematic section
    USE_DEFAULT = "use_default"  # Use default value
    PARTIAL_PARSE = "partial_parse"  # Parse what's possible
    RETRY = "retry"  # Retry with different approach


@dataclass
class ErrorContext:
    """Context information for an error."""

    file_path: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    section_path: Optional[str] = None  # e.g., "paths./users.get.responses"
    raw_content: Optional[str] = None
    surrounding_lines: Optional[List[str]] = None


@dataclass
class RecoveryAction:
    """Action to take for error recovery."""

    strategy: RecoveryStrategy
    description: str
    default_value: Optional[Any] = None
    retry_count: int = 0
    max_retries: int = 3


class ErrorHandler:
    """Handles parsing errors with recovery mechanisms."""

    def __init__(self, strict_mode: bool = False, max_errors: int = 100):
        """Initialize error handler.

        Args:
            strict_mode: If True, fail on any error
            max_errors: Maximum number of errors before giving up
        """
        self.strict_mode = strict_mode
        self.max_errors = max_errors
        self.errors: List[ParseError] = []
        self.warnings: List[ParseError] = []
        self.logger = get_logger(__name__)

    def handle_json_decode_error(
        self, error: json.JSONDecodeError, context: ErrorContext
    ) -> Tuple[RecoveryAction, ParseError]:
        """Handle JSON decode errors with recovery suggestions.

        Args:
            error: The JSON decode error
            context: Error context information

        Returns:
            Tuple of recovery action and parse error
        """
        # Analyze the error type and suggest recovery
        error_msg = error.msg
        line_no = getattr(error, "lineno", None)
        col_no = getattr(error, "colno", None)
        pos = getattr(error, "pos", None)

        parse_error = ParseError(
            message=f"JSON parsing failed: {error_msg}",
            error_type="JSONDecodeError",
            line_number=line_no,
            column_number=col_no,
            context=self._build_error_context(error_msg, context),
            recoverable=self._is_recoverable_json_error(error_msg),
            suggestion=self._get_json_error_suggestion(error_msg),
        )

        # Determine recovery strategy
        if "Expecting ',' delimiter" in error_msg:
            recovery = RecoveryAction(
                strategy=RecoveryStrategy.PARTIAL_PARSE,
                description="Try to parse valid sections before the error",
            )
        elif "Expecting property name enclosed in double quotes" in error_msg:
            recovery = RecoveryAction(
                strategy=RecoveryStrategy.SKIP_SECTION,
                description="Skip the malformed object property",
            )
        elif "Expecting ':' delimiter" in error_msg:
            recovery = RecoveryAction(
                strategy=RecoveryStrategy.USE_DEFAULT,
                description="Use empty object for malformed property",
                default_value={},
            )
        elif "Unterminated string" in error_msg:
            recovery = RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                description="Attempt to fix unterminated string",
                max_retries=1,
            )
        else:
            recovery = RecoveryAction(
                strategy=RecoveryStrategy.FAIL_FAST
                if self.strict_mode
                else RecoveryStrategy.PARTIAL_PARSE,
                description="Generic JSON error recovery",
            )

        return recovery, parse_error

    def handle_structure_error(
        self,
        section_path: str,
        expected_type: str,
        actual_value: Any,
        context: ErrorContext,
    ) -> Tuple[RecoveryAction, ParseError]:
        """Handle OpenAPI structure validation errors.

        Args:
            section_path: Path to the problematic section (e.g., "paths./users")
            expected_type: Expected data type
            actual_value: Actual value found
            context: Error context

        Returns:
            Tuple of recovery action and parse error
        """
        actual_type = type(actual_value).__name__

        parse_error = ParseError(
            message=f"Invalid structure at {section_path}: expected {expected_type}, got {actual_type}",
            error_type="StructureValidationError",
            context=f"Section: {section_path}, Value: {str(actual_value)[:100]}...",
            recoverable=True,
            suggestion=self._get_structure_error_suggestion(
                section_path, expected_type, actual_type
            ),
        )

        # Recovery strategies based on section and type mismatch
        if section_path.startswith("paths."):
            if expected_type == "object" and actual_type in ["list", "str"]:
                recovery = RecoveryAction(
                    strategy=RecoveryStrategy.SKIP_SECTION,
                    description=f"Skip invalid path definition: {section_path}",
                )
            else:
                recovery = RecoveryAction(
                    strategy=RecoveryStrategy.USE_DEFAULT,
                    description=f"Use empty object for {section_path}",
                    default_value={},
                )
        elif section_path.startswith("components.schemas."):
            recovery = RecoveryAction(
                strategy=RecoveryStrategy.USE_DEFAULT,
                description="Use basic string schema as fallback",
                default_value={
                    "type": "string",
                    "description": "Schema parsing failed",
                },
            )
        else:
            recovery = RecoveryAction(
                strategy=RecoveryStrategy.SKIP_SECTION,
                description=f"Skip problematic section: {section_path}",
            )

        return recovery, parse_error

    def handle_reference_error(
        self, ref_path: str, context: ErrorContext
    ) -> Tuple[RecoveryAction, ParseError]:
        """Handle $ref resolution errors.

        Args:
            ref_path: The reference path that failed to resolve
            context: Error context

        Returns:
            Tuple of recovery action and parse error
        """
        parse_error = ParseError(
            message=f"Failed to resolve reference: {ref_path}",
            error_type="ReferenceResolutionError",
            context=f"Reference: {ref_path}",
            recoverable=True,
            suggestion=f"Check if referenced component exists: {ref_path}",
        )

        # Strategy: leave reference as-is for later resolution
        recovery = RecoveryAction(
            strategy=RecoveryStrategy.PARTIAL_PARSE,
            description="Keep unresolved reference for later processing",
        )

        return recovery, parse_error

    def attempt_json_repair(
        self, json_text: str, error: json.JSONDecodeError
    ) -> Optional[str]:
        """Attempt to repair common JSON syntax errors.

        Args:
            json_text: Original JSON text
            error: The JSON decode error

        Returns:
            Repaired JSON text if possible, None otherwise
        """
        try:
            error_msg = error.msg
            pos = getattr(error, "pos", None)

            if not pos:
                return None

            # Common repair patterns
            repaired = json_text

            # Fix trailing commas
            if "Expecting property name" in error_msg:
                # Remove trailing comma before }
                repaired = re.sub(r",(\s*})", r"\1", repaired)
                repaired = re.sub(r",(\s*])", r"\1", repaired)

            # Fix missing commas
            elif "Expecting ',' delimiter" in error_msg:
                # This is harder to fix automatically
                return None

            # Fix unescaped quotes in strings
            elif "Unterminated string" in error_msg:
                # Try to find and escape unescaped quotes
                lines = repaired.split("\n")
                for i, line in enumerate(lines):
                    # Simple heuristic: escape quotes not at start/end of values
                    if '"' in line:
                        # This is a simplified fix - real implementation would be more complex
                        fixed_line = re.sub(
                            r'(?<!\\)"(?![\s,}\]])', r"\"", line
                        )
                        if fixed_line != line:
                            lines[i] = fixed_line
                repaired = "\n".join(lines)

            # Validate the repair
            try:
                json.loads(repaired)
                self.logger.info(
                    "Successfully repaired JSON",
                    original_error=error_msg,
                    repair_length=len(repaired) - len(json_text),
                )
                return repaired
            except json.JSONDecodeError:
                return None

        except Exception as e:
            self.logger.warning(
                "JSON repair attempt failed",
                error=str(e),
                original_error=error.msg,
            )
            return None

    def should_continue_parsing(self) -> bool:
        """Check if parsing should continue based on error count and severity.

        Returns:
            True if parsing should continue
        """
        if self.strict_mode and len(self.errors) > 0:
            return False

        return len(self.errors) < self.max_errors

    def add_error(self, error: ParseError) -> None:
        """Add an error to the error list.

        Args:
            error: Parse error to add
        """
        if error.recoverable:
            self.warnings.append(error)
        else:
            self.errors.append(error)

        self.logger.error(
            "Parse error recorded",
            error_type=error.error_type,
            message=error.message,
            recoverable=error.recoverable,
            total_errors=len(self.errors),
            total_warnings=len(self.warnings),
        )

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all errors and warnings.

        Returns:
            Error summary dictionary
        """
        return {
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "error_types": list(
                set(e.error_type for e in self.errors + self.warnings)
            ),
            "has_critical_errors": any(not e.recoverable for e in self.errors),
            "errors": [self._serialize_error(e) for e in self.errors],
            "warnings": [self._serialize_error(e) for e in self.warnings],
        }

    def _is_recoverable_json_error(self, error_msg: str) -> bool:
        """Check if a JSON error is recoverable.

        Args:
            error_msg: JSON error message

        Returns:
            True if error might be recoverable
        """
        recoverable_patterns = [
            "Expecting ',' delimiter",
            "Expecting property name",
            "Expecting ':' delimiter",
            "Unterminated string",
            "Extra data",
        ]

        return any(pattern in error_msg for pattern in recoverable_patterns)

    def _get_json_error_suggestion(self, error_msg: str) -> str:
        """Get suggestion for fixing JSON error.

        Args:
            error_msg: JSON error message

        Returns:
            Suggestion string
        """
        suggestions = {
            "Expecting ',' delimiter": "Add missing comma between object properties or array elements",
            "Expecting property name": "Remove trailing comma or add missing property name",
            "Expecting ':' delimiter": "Add colon between property name and value",
            "Unterminated string": "Add closing quote or escape quotes within string",
            "Extra data": "Remove extra characters after valid JSON ends",
        }

        for pattern, suggestion in suggestions.items():
            if pattern in error_msg:
                return suggestion

        return "Validate JSON syntax using a JSON validator tool"

    def _get_structure_error_suggestion(
        self, section_path: str, expected_type: str, actual_type: str
    ) -> str:
        """Get suggestion for fixing structure error.

        Args:
            section_path: Path to problematic section
            expected_type: Expected data type
            actual_type: Actual data type

        Returns:
            Suggestion string
        """
        if section_path.startswith("paths."):
            return f"Path definitions should be objects with HTTP method keys (get, post, etc.)"
        elif section_path.startswith("components.schemas."):
            return f"Schema definitions should be objects with OpenAPI schema properties"
        else:
            return (
                f"Convert {section_path} from {actual_type} to {expected_type}"
            )

    def _build_error_context(
        self, error_msg: str, context: ErrorContext
    ) -> str:
        """Build detailed error context string.

        Args:
            error_msg: Error message
            context: Error context information

        Returns:
            Context string
        """
        parts = [f"Error: {error_msg}"]

        if context.line_number:
            parts.append(f"Line: {context.line_number}")
        if context.column_number:
            parts.append(f"Column: {context.column_number}")
        if context.section_path:
            parts.append(f"Section: {context.section_path}")

        return " | ".join(parts)

    def _serialize_error(self, error: ParseError) -> Dict[str, Any]:
        """Serialize parse error for reporting.

        Args:
            error: Parse error to serialize

        Returns:
            Serialized error dictionary
        """
        return {
            "message": error.message,
            "type": error.error_type,
            "line": error.line_number,
            "column": error.column_number,
            "context": error.context,
            "recoverable": error.recoverable,
            "suggestion": error.suggestion,
        }
