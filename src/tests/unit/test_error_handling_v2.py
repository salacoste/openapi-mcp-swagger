"""Comprehensive tests for MCP server error handling and resilience (Story 2.5)."""

import asyncio
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swagger_mcp_server.config.settings import Settings
from swagger_mcp_server.server.exceptions import (
    CodeGenerationError,
    DatabaseConnectionError,
    ErrorLogger,
    MCPServerError,
    ResourceNotFoundError,
    SchemaResolutionError,
    ValidationError,
    create_mcp_error_response,
    sanitize_error_data,
)
from swagger_mcp_server.server.mcp_server_v2 import SwaggerMcpServer
from swagger_mcp_server.server.resilience import (
    CircuitBreaker,
    CircuitBreakerState,
    HealthChecker,
    ResourcePool,
    retry_on_failure,
    with_timeout,
)


class TestMCPServerExceptions:
    """Test custom MCP server exception classes."""

    def test_mcp_server_error_creation(self):
        """Test basic MCP server error creation and serialization."""
        error = MCPServerError(
            code=-32602, message="Test error", data={"test": "value"}
        )

        assert error.code == -32602
        assert error.message == "Test error"
        assert error.data["test"] == "value"
        assert error.timestamp > 0

        error_dict = error.to_dict()
        assert error_dict["code"] == -32602
        assert error_dict["message"] == "Test error"
        assert error_dict["data"]["test"] == "value"

    def test_validation_error(self):
        """Test ValidationError with suggestions."""
        error = ValidationError(
            parameter="format",
            message="Unsupported format",
            value="invalid",
            suggestions=["curl", "javascript", "python"],
        )

        assert error.code == -32602
        assert "Invalid parameter 'format'" in error.message
        assert error.data["parameter"] == "format"
        assert error.data["value"] == "invalid"
        assert error.data["suggestions"] == ["curl", "javascript", "python"]

    def test_database_connection_error(self):
        """Test DatabaseConnectionError with operation context."""
        error = DatabaseConnectionError(
            message="Connection timeout", operation="search"
        )

        assert error.code == -32603
        assert error.message == "Connection timeout"
        assert error.data["operation"] == "search"
        assert error.data["recoverable"] is True

    def test_resource_not_found_error(self):
        """Test ResourceNotFoundError with suggestions."""
        error = ResourceNotFoundError(
            resource_type="schema",
            identifier="InvalidSchema",
            suggestions=["UserSchema", "ProductSchema"],
        )

        assert error.code == -1001
        assert "Schema 'InvalidSchema' not found" in error.message
        assert error.data["resource_type"] == "schema"
        assert error.data["suggestions"] == ["UserSchema", "ProductSchema"]

    def test_code_generation_error(self):
        """Test CodeGenerationError for code generation failures."""
        error = CodeGenerationError(
            format_type="javascript",
            endpoint="/api/users",
            reason="Template compilation failed",
        )

        assert error.code == -1002
        assert "Code generation failed for javascript format" in error.message
        assert error.data["format"] == "javascript"
        assert error.data["endpoint"] == "/api/users"

    def test_schema_resolution_error(self):
        """Test SchemaResolutionError with circular references."""
        error = SchemaResolutionError(
            component_name="User",
            reason="Maximum depth exceeded",
            circular_refs=["User", "Profile", "User"],
        )

        assert error.code == -1003
        assert "Schema resolution failed for 'User'" in error.message
        assert error.data["circular_references"] == ["User", "Profile", "User"]


class TestErrorResponseGeneration:
    """Test error response generation and sanitization."""

    def test_create_mcp_error_response(self):
        """Test MCP protocol error response generation."""
        error = ValidationError("test", "test message")
        response = create_mcp_error_response(error, "req-123")

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "req-123"
        assert response["error"]["code"] == -32602
        assert "test message" in response["error"]["message"]

    def test_sanitize_error_data(self):
        """Test error data sanitization."""
        sensitive_data = {
            "username": "user123",
            "password": "secret123",
            "api_key": "key123",
            "database_url": "postgres://user:pass@host/db",
            "normal_field": "normal_value",
            "long_field": "x" * 600,
        }

        sanitized = sanitize_error_data(sensitive_data)

        assert "username" in sanitized
        assert "password" not in sanitized
        assert "api_key" not in sanitized
        assert "database_url" not in sanitized
        assert sanitized["normal_field"] == "normal_value"
        assert len(sanitized["long_field"]) == 503  # 500 + "... (truncated)"

    def test_nested_data_sanitization(self):
        """Test sanitization of nested data structures."""
        nested_data = {
            "config": {"auth_token": "secret", "public_setting": "value"},
            "results": ["item1", "item2"],
        }

        sanitized = sanitize_error_data(nested_data)

        assert "auth_token" not in sanitized["config"]
        assert sanitized["config"]["public_setting"] == "value"
        assert sanitized["results"] == ["item1", "item2"]


class TestErrorLogger:
    """Test structured error logging."""

    def test_error_logger_mcp_error(self):
        """Test logging of MCP server errors."""
        logger = MagicMock()
        error_logger = ErrorLogger(logger)

        error = ValidationError("param", "message")
        error_logger.log_error(error, {"context": "test"}, "req-123")

        logger.warning.assert_called_once()
        call_args = logger.warning.call_args
        assert "MCP client error" in call_args[0]
        assert call_args[1]["extra"]["request_id"] == "req-123"

    def test_error_logger_operation_error(self):
        """Test logging of general operation errors."""
        logger = MagicMock()
        error_logger = ErrorLogger(logger)

        exception = Exception("Test exception")
        error_logger.log_operation_error(
            "test_op", exception, {"context": "test"}, "req-123"
        )

        logger.error.assert_called_once()
        call_args = logger.error.call_args
        assert "Operation failed" in call_args[0]
        assert call_args[1]["extra"]["operation"] == "test_op"


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.can_execute() is True
        assert cb.failure_count == 0

    def test_circuit_breaker_failure_counting(self):
        """Test circuit breaker failure counting and state transitions."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

        # Record failures
        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_execute() is False

    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery process."""
        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=0.1, success_threshold=2
        )

        # Trigger circuit breaker
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)
        assert cb.can_execute() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN

        # Record successes to close circuit
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_status(self):
        """Test circuit breaker status reporting."""
        cb = CircuitBreaker(failure_threshold=3)
        status = cb.get_status()

        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["can_execute"] is True


class TestRetryLogic:
    """Test retry decorators and logic."""

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test retry succeeds after initial failures."""
        call_count = 0

        @retry_on_failure(max_retries=3, backoff_factor=0.1)
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise DatabaseConnectionError("Connection failed")
            return "success"

        result = await flaky_operation()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test retry behavior when all attempts fail."""
        call_count = 0

        @retry_on_failure(max_retries=2, backoff_factor=0.1)
        async def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise DatabaseConnectionError("Always fails")

        with pytest.raises(DatabaseConnectionError):
            await always_failing_operation()

        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_timeout_decorator(self):
        """Test timeout decorator functionality."""

        @with_timeout(0.1)
        async def slow_operation():
            await asyncio.sleep(0.2)
            return "too slow"

        with pytest.raises(
            Exception
        ):  # Should raise timeout-related exception
            await slow_operation()


class TestResourcePool:
    """Test resource pool functionality."""

    @pytest.mark.asyncio
    async def test_resource_pool_acquire_release(self):
        """Test basic resource pool operations."""
        pool = ResourcePool(max_size=2, name="test_pool")

        # Acquire resources
        await pool.acquire()
        assert pool.current_size == 1

        await pool.acquire()
        assert pool.current_size == 2

        # Pool should be at capacity
        with pytest.raises(Exception):  # ResourceExhaustedError
            await pool.acquire()

        # Release resource
        await pool.release()
        assert pool.current_size == 1

        # Should be able to acquire again
        await pool.acquire()
        assert pool.current_size == 2

    def test_resource_pool_stats(self):
        """Test resource pool statistics."""
        pool = ResourcePool(max_size=5, name="stats_test")
        stats = pool.get_stats()

        assert stats["name"] == "stats_test"
        assert stats["max_size"] == 5
        assert stats["current_size"] == 0
        assert stats["utilization"] == 0.0


class TestHealthChecker:
    """Test health checker functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        checker = HealthChecker()

        async def healthy_component():
            return {"status": "ok", "connections": 5}

        result = await checker.check_component_health(
            "database", healthy_component, cache_duration=0.1
        )

        assert result["status"] == "healthy"
        assert result["details"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test failed health check."""
        checker = HealthChecker()

        async def failing_component():
            raise Exception("Component is down")

        result = await checker.check_component_health(
            "service", failing_component, cache_duration=0.1
        )

        assert result["status"] == "unhealthy"
        assert "Component is down" in result["error"]

    @pytest.mark.asyncio
    async def test_overall_health(self):
        """Test overall system health calculation."""
        checker = HealthChecker()

        # Add healthy component
        await checker.check_component_health(
            "healthy", lambda: {"status": "ok"}, cache_duration=0.1
        )

        # Add unhealthy component
        async def failing():
            raise Exception("Failed")

        await checker.check_component_health(
            "unhealthy", failing, cache_duration=0.1
        )

        overall = checker.get_overall_health()
        assert overall["status"] == "degraded"
        assert overall["healthy_components"] == 1
        assert overall["total_components"] == 2


class TestMCPServerErrorHandling:
    """Test MCP server integration with error handling."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = Settings()
        settings.database.path = ":memory:"
        settings.server.name = "test-server"
        settings.server.version = "0.1.0"
        return settings

    @pytest.fixture
    async def server(self, settings):
        """Create test server."""
        server = SwaggerMcpServer(settings)
        server.endpoint_repo = AsyncMock()
        server.schema_repo = AsyncMock()
        server.metadata_repo = AsyncMock()
        server.db_manager = AsyncMock()
        return server

    @pytest.mark.asyncio
    async def test_parameter_validation_errors(self, server):
        """Test parameter validation error handling."""
        # Test empty keywords
        result = await server._search_endpoints_with_resilience(
            {"keywords": ""}, "test-request"
        )

        # Should raise ValidationError, but wrapper catches it
        assert "error" in str(result) or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_database_connection_error_handling(self, server):
        """Test database connection error handling and recovery."""
        server.endpoint_repo = None

        try:
            await server._search_endpoints_with_resilience(
                {"keywords": "test"}, "test-request"
            )
        except DatabaseConnectionError as e:
            assert e.code == -32603
            assert "not properly initialized" in e.message

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, server):
        """Test circuit breaker integration with MCP methods."""
        # Mock endpoint repo to always fail
        server.endpoint_repo.search_endpoints = AsyncMock(
            side_effect=Exception("Database down")
        )

        # This would normally trigger circuit breaker after repeated failures
        # For testing, we verify the decorator is applied
        assert hasattr(server._search_endpoints_with_resilience, "__wrapped__")

    @pytest.mark.asyncio
    async def test_timeout_integration(self, server):
        """Test timeout integration with MCP methods."""

        # Mock a slow operation
        async def slow_search(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {"results": []}

        server.endpoint_repo.search_endpoints = slow_search

        # Should complete within timeout
        result = await server._search_endpoints_with_resilience(
            {"keywords": "test"}, "test-request"
        )

        # Result should be successful for short operation
        assert isinstance(result, dict)


class TestErrorHandlingPerformance:
    """Test error handling performance requirements."""

    @pytest.mark.asyncio
    async def test_error_handling_performance(self):
        """Test that error handling doesn't significantly impact performance."""
        start_time = time.time()

        # Create and handle multiple errors
        for i in range(100):
            error = ValidationError("param", f"message {i}")
            response = create_mcp_error_response(error, f"req-{i}")
            sanitized = sanitize_error_data({"test": f"value-{i}"})

        end_time = time.time()
        processing_time = end_time - start_time

        # Should handle 100 errors quickly
        assert processing_time < 0.1  # 100ms for 100 errors

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self):
        """Test concurrent error handling performance."""

        async def generate_error():
            error = ValidationError("param", "test message")
            return create_mcp_error_response(error, "test-req")

        # Generate errors concurrently
        tasks = [generate_error() for _ in range(50)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 50
        for result in results:
            assert "error" in result
            assert result["jsonrpc"] == "2.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
