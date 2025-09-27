"""Custom MCP server exceptions and error handling framework.

Implements Story 2.5 error handling and resilience requirements.
"""

import logging
import time
from typing import Any, Dict, List, Optional


class MCPServerError(Exception):
    """Base exception for MCP server errors with JSON-RPC 2.0 compliance."""

    def __init__(
        self, code: int, message: str, data: Optional[Dict[str, Any]] = None
    ):
        """Initialize MCP server error.

        Args:
            code: JSON-RPC 2.0 error code
            message: Human-readable error message
            data: Additional error context and debugging information
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to JSON-RPC 2.0 error response format."""
        error_dict = {"code": self.code, "message": self.message}
        if self.data:
            error_dict["data"] = self.data
        return error_dict


class ValidationError(MCPServerError):
    """Parameter validation error (-32602 Invalid params)."""

    def __init__(
        self,
        parameter: str,
        message: str,
        value: Any = None,
        suggestions: Optional[List[str]] = None,
    ):
        """Initialize validation error.

        Args:
            parameter: Name of the invalid parameter
            message: Specific validation error message
            value: The invalid value that caused the error
            suggestions: List of suggested valid values
        """
        data = {"parameter": parameter, "error_type": "validation_error"}
        if value is not None:
            data["value"] = str(value)
        if suggestions:
            data["suggestions"] = suggestions

        super().__init__(
            code=-32602,
            message=f"Invalid parameter '{parameter}': {message}",
            data=data,
        )


class DatabaseConnectionError(MCPServerError):
    """Database connection failure (-32603 Internal error)."""

    def __init__(
        self,
        message: str = "Database connection failed",
        operation: str = "unknown",
    ):
        """Initialize database connection error.

        Args:
            message: Specific database error message
            operation: Database operation that failed
        """
        super().__init__(
            code=-32603,
            message=message,
            data={
                "error_type": "database_error",
                "operation": operation,
                "recoverable": True,
            },
        )


class DatabaseTimeoutError(MCPServerError):
    """Database operation timeout (-32603 Internal error)."""

    def __init__(self, operation: str, timeout_seconds: float):
        """Initialize database timeout error.

        Args:
            operation: Database operation that timed out
            timeout_seconds: Timeout value that was exceeded
        """
        super().__init__(
            code=-32603,
            message=f"Database operation '{operation}' timed out after {timeout_seconds}s",
            data={
                "error_type": "timeout_error",
                "operation": operation,
                "timeout_seconds": timeout_seconds,
                "recoverable": True,
            },
        )


class ResourceNotFoundError(MCPServerError):
    """Resource not found error (custom code -1001)."""

    def __init__(
        self,
        resource_type: str,
        identifier: str,
        suggestions: Optional[List[str]] = None,
    ):
        """Initialize resource not found error.

        Args:
            resource_type: Type of resource (endpoint, schema, etc.)
            identifier: Resource identifier that was not found
            suggestions: List of similar resources that exist
        """
        data = {
            "error_type": "not_found_error",
            "resource_type": resource_type,
            "identifier": identifier,
        }
        if suggestions:
            data["suggestions"] = suggestions

        super().__init__(
            code=-1001,
            message=f"{resource_type.title()} '{identifier}' not found",
            data=data,
        )


class ResourceExhaustedError(MCPServerError):
    """Resource exhaustion error (-32603 Internal error)."""

    def __init__(self, resource_type: str, current_usage: int, limit: int):
        """Initialize resource exhausted error.

        Args:
            resource_type: Type of resource exhausted (connections, memory, etc.)
            current_usage: Current resource usage
            limit: Resource limit that was exceeded
        """
        super().__init__(
            code=-32603,
            message=f"{resource_type.title()} limit exceeded: {current_usage}/{limit}",
            data={
                "error_type": "resource_exhausted",
                "resource_type": resource_type,
                "current_usage": current_usage,
                "limit": limit,
                "recoverable": True,
            },
        )


class ServiceUnavailableError(MCPServerError):
    """Service temporarily unavailable (-32603 Internal error)."""

    def __init__(
        self,
        service: str,
        reason: str,
        retry_after_seconds: Optional[int] = None,
    ):
        """Initialize service unavailable error.

        Args:
            service: Name of the unavailable service
            reason: Reason for unavailability
            retry_after_seconds: Suggested retry delay
        """
        data = {
            "error_type": "service_unavailable",
            "service": service,
            "reason": reason,
            "recoverable": True,
        }
        if retry_after_seconds:
            data["retry_after_seconds"] = retry_after_seconds

        super().__init__(
            code=-32603,
            message=f"Service '{service}' temporarily unavailable: {reason}",
            data=data,
        )


class CodeGenerationError(MCPServerError):
    """Code generation failure (custom code -1002)."""

    def __init__(self, format_type: str, endpoint: str, reason: str):
        """Initialize code generation error.

        Args:
            format_type: Code format that failed (curl, javascript, python)
            endpoint: Endpoint for which code generation failed
            reason: Specific reason for failure
        """
        super().__init__(
            code=-1002,
            message=f"Code generation failed for {format_type} format: {reason}",
            data={
                "error_type": "code_generation_error",
                "format": format_type,
                "endpoint": endpoint,
                "reason": reason,
                "recoverable": True,
            },
        )


class SchemaResolutionError(MCPServerError):
    """Schema dependency resolution error (custom code -1003)."""

    def __init__(
        self,
        component_name: str,
        reason: str,
        circular_refs: Optional[List[str]] = None,
    ):
        """Initialize schema resolution error.

        Args:
            component_name: Schema component that failed to resolve
            reason: Specific reason for failure
            circular_refs: List of circular references if detected
        """
        data = {
            "error_type": "schema_resolution_error",
            "component": component_name,
            "reason": reason,
        }
        if circular_refs:
            data["circular_references"] = circular_refs

        super().__init__(
            code=-1003,
            message=f"Schema resolution failed for '{component_name}': {reason}",
            data=data,
        )


class ErrorLogger:
    """Structured error logging for MCP server operations."""

    def __init__(self, logger: logging.Logger):
        """Initialize error logger.

        Args:
            logger: Python logger instance for error reporting
        """
        self.logger = logger

    def log_error(
        self,
        error: MCPServerError,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Log MCP server error with structured context.

        Args:
            error: MCP server error to log
            context: Additional context information
            request_id: Request ID for correlation
        """
        log_data = {
            "error_code": error.code,
            "error_message": error.message,
            "error_type": error.data.get("error_type", "unknown"),
            "timestamp": error.timestamp,
        }

        if request_id:
            log_data["request_id"] = request_id

        if context:
            log_data.update(context)

        if error.data:
            log_data["error_data"] = error.data

        # Log at appropriate level based on error severity
        if error.code in [-32600, -32601, -32602]:  # Client errors
            self.logger.warning("MCP client error", extra=log_data)
        elif error.data.get("recoverable", False):  # Recoverable server errors
            self.logger.warning("MCP recoverable error", extra=log_data)
        else:  # Non-recoverable server errors
            self.logger.error("MCP server error", extra=log_data)

    def log_operation_error(
        self,
        operation: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Log general operation error.

        Args:
            operation: Name of the operation that failed
            error: Exception that occurred
            context: Additional context information
            request_id: Request ID for correlation
        """
        log_data = {
            "operation": operation,
            "error_message": str(error),
            "error_type": type(error).__name__,
        }

        if request_id:
            log_data["request_id"] = request_id

        if context:
            log_data.update(context)

        self.logger.error("Operation failed", extra=log_data, exc_info=True)


def create_mcp_error_response(
    error: MCPServerError, request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create MCP protocol-compliant error response.

    Args:
        error: MCP server error
        request_id: Request ID from original request

    Returns:
        JSON-RPC 2.0 error response dictionary
    """
    response = {"jsonrpc": "2.0", "error": error.to_dict()}

    if request_id is not None:
        response["id"] = request_id

    return response


def sanitize_error_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize error data to remove sensitive information.

    Args:
        data: Raw error data dictionary

    Returns:
        Sanitized error data safe for client consumption
    """
    sensitive_keys = {
        "password",
        "token",
        "secret",
        "key",
        "auth",
        "credential",
        "database_url",
        "connection_string",
        "internal_id",
    }

    sanitized = {}
    for key, value in data.items():
        # Skip sensitive keys
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            continue

        # Recursively sanitize nested dictionaries
        if isinstance(value, dict):
            sanitized[key] = sanitize_error_data(value)
        elif isinstance(value, str) and len(value) > 500:
            # Truncate very long strings
            sanitized[key] = value[:500] + "... (truncated)"
        else:
            sanitized[key] = value

    return sanitized
