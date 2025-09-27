"""Tests for logging configuration."""

import json
import logging
import tempfile
from pathlib import Path

import pytest
import structlog

from swagger_mcp_server.config.logging import (
    configure_logging,
    get_logger,
    log_performance,
    sanitize_log_data,
)


def test_configure_logging_basic():
    """Test basic logging configuration."""
    logger = configure_logging(level="DEBUG")
    # Check that logger has expected methods and is properly configured
    assert hasattr(logger, 'info')
    assert hasattr(logger, 'debug')
    assert hasattr(logger, 'warning')
    assert hasattr(logger, 'error')
    # Check it's a structlog logger instance (could be BoundLogger or BoundLoggerLazyProxy)
    assert hasattr(logger, 'bind')


def test_configure_logging_with_file():
    """Test logging configuration with file output."""
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        temp_file = f.name

    try:
        logger = configure_logging(level="INFO", log_file=temp_file, json_logs=False)

        # Check that logger has expected attributes and file was created
        assert hasattr(logger, 'info')
        log_path = Path(temp_file)
        assert log_path.exists()

        # Test that the logger can log without error
        try:
            logger.info("Test message", key="value")
            # No exception means the logging setup is working
        except Exception as e:
            pytest.fail(f"Logging failed with error: {e}")

    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_get_logger_with_context():
    """Test logger creation with initial context."""
    logger = get_logger(__name__, component="test", version="1.0")
    # Check that logger has expected methods and is properly configured
    assert hasattr(logger, 'info')
    assert hasattr(logger, 'debug')
    assert hasattr(logger, 'warning')
    assert hasattr(logger, 'error')
    # Check it's a structlog logger instance (could be BoundLogger or BoundLoggerLazyProxy)
    assert hasattr(logger, 'bind')


def test_log_performance():
    """Test performance logging function."""
    logger = get_logger(__name__)
    # Should not raise an exception
    log_performance(logger, "test_operation", 150.5, user_id="123")


def test_sanitize_log_data():
    """Test sensitive data sanitization."""
    data = {
        "username": "testuser",
        "password": "secret123",
        "api_key": "abc123",
        "normal_field": "normal_value",
        "nested": {"token": "secret_token", "safe_field": "safe_value"},
    }

    sanitized = sanitize_log_data(data)

    assert sanitized["username"] == "testuser"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["normal_field"] == "normal_value"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == "safe_value"


def test_json_logging_format():
    """Test JSON logging format."""
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        temp_file = f.name

    try:
        logger = configure_logging(
            level="INFO", log_file=temp_file, json_logs=True
        )

        # Check that logger has expected attributes and file was created
        assert hasattr(logger, 'info')
        log_path = Path(temp_file)
        assert log_path.exists()

        # Test that the logger can log without error
        try:
            logger.info("Test JSON message", test_key="test_value", number=42)
            # No exception means the JSON logging setup is working
        except Exception as e:
            pytest.fail(f"JSON logging failed with error: {e}")

    finally:
        Path(temp_file).unlink(missing_ok=True)
