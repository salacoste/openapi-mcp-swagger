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
    assert isinstance(logger, structlog.stdlib.BoundLogger)


def test_configure_logging_with_file():
    """Test logging configuration with file output."""
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        temp_file = f.name

    try:
        logger = configure_logging(level="INFO", log_file=temp_file)
        logger.info("Test message", key="value")

        # Check file was created and contains log
        log_path = Path(temp_file)
        assert log_path.exists()
        content = log_path.read_text()
        assert "Test message" in content

    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_get_logger_with_context():
    """Test logger creation with initial context."""
    logger = get_logger(__name__, component="test", version="1.0")
    assert isinstance(logger, structlog.stdlib.BoundLogger)


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
        logger.info("Test JSON message", test_key="test_value", number=42)

        # Read and parse JSON log
        log_path = Path(temp_file)
        content = log_path.read_text().strip()
        log_entry = json.loads(content.split("\n")[-1])  # Get last log line

        assert "Test JSON message" in log_entry["event"]
        assert log_entry["test_key"] == "test_value"
        assert log_entry["number"] == 42
        assert "timestamp" in log_entry

    finally:
        Path(temp_file).unlink(missing_ok=True)
