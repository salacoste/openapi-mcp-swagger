"""Logging configuration using structlog for structured logging."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from structlog.types import FilteringBoundLogger


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_logs: bool = True,
    enable_performance_logging: bool = True
) -> FilteringBoundLogger:
    """Configure structured logging with structlog.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path for file logging
        json_logs: Whether to use JSON formatting
        enable_performance_logging: Whether to enable performance logging

    Returns:
        Configured structlog logger
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend([
            structlog.processors.CallsiteParameterAdder(
                parameters=[structlog.processors.CallsiteParameter.FILENAME,
                           structlog.processors.CallsiteParameter.LINENO]
            ),
            structlog.dev.ConsoleRenderer(colors=True)
        ])

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    # Add file handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler with 10MB max size, 30-day retention
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)

        # JSON format for file logs
        file_formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(file_formatter)

        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


def get_logger(name: str, **initial_context: Any) -> FilteringBoundLogger:
    """Get a logger instance with optional initial context.

    Args:
        name: Logger name (typically __name__)
        **initial_context: Initial context to bind to logger

    Returns:
        Configured logger with bound context
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


def log_performance(
    logger: FilteringBoundLogger,
    operation: str,
    duration_ms: float,
    **context: Any
) -> None:
    """Log performance metrics in a structured format.

    Args:
        logger: Structlog logger instance
        operation: Name of the operation being measured
        duration_ms: Duration in milliseconds
        **context: Additional context to include
    """
    logger.info(
        "Performance metric",
        operation=operation,
        duration_ms=duration_ms,
        metric_type="performance",
        **context
    )


def log_api_request(
    logger: FilteringBoundLogger,
    method: str,
    endpoint: str,
    response_time_ms: float,
    status_code: int,
    **context: Any
) -> None:
    """Log API request metrics.

    Args:
        logger: Structlog logger instance
        method: HTTP method
        endpoint: API endpoint
        response_time_ms: Response time in milliseconds
        status_code: HTTP status code
        **context: Additional context
    """
    logger.info(
        "API request",
        http_method=method,
        endpoint=endpoint,
        response_time_ms=response_time_ms,
        status_code=status_code,
        metric_type="api_request",
        **context
    )


def log_database_query(
    logger: FilteringBoundLogger,
    query_type: str,
    execution_time_ms: float,
    rows_affected: int = 0,
    **context: Any
) -> None:
    """Log database query metrics.

    Args:
        logger: Structlog logger instance
        query_type: Type of query (SELECT, INSERT, UPDATE, etc.)
        execution_time_ms: Query execution time in milliseconds
        rows_affected: Number of rows affected/returned
        **context: Additional context
    """
    logger.debug(
        "Database query",
        query_type=query_type,
        execution_time_ms=execution_time_ms,
        rows_affected=rows_affected,
        metric_type="database_query",
        **context
    )


def log_parsing_progress(
    logger: FilteringBoundLogger,
    file_path: str,
    bytes_processed: int,
    total_bytes: int,
    progress_percent: float,
    **context: Any
) -> None:
    """Log file parsing progress.

    Args:
        logger: Structlog logger instance
        file_path: Path to file being processed
        bytes_processed: Number of bytes processed so far
        total_bytes: Total number of bytes to process
        progress_percent: Progress as percentage (0-100)
        **context: Additional context
    """
    logger.info(
        "Parsing progress",
        file_path=file_path,
        bytes_processed=bytes_processed,
        total_bytes=total_bytes,
        progress_percent=progress_percent,
        metric_type="parsing_progress",
        **context
    )


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive information from log data.

    Args:
        data: Dictionary that may contain sensitive information

    Returns:
        Sanitized dictionary with sensitive values masked
    """
    sensitive_keys = {
        'password', 'token', 'key', 'secret', 'authorization',
        'api_key', 'access_token', 'refresh_token', 'jwt'
    }

    sanitized = data.copy()

    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)

    return sanitized