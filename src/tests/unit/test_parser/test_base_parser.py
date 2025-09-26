"""Tests for base parser interface and data structures."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from datetime import datetime

from swagger_mcp_server.parser.base import (
    BaseParser, ParserConfig, ParserFactory, ParserType, ParseStatus,
    ParseResult, ParseMetrics, ParseError, SwaggerParseError
)


class MockParser(BaseParser):
    """Mock parser for testing base functionality."""

    def get_supported_extensions(self) -> list[str]:
        return ['.json']

    def get_parser_type(self) -> ParserType:
        return ParserType.OPENAPI_JSON

    async def parse(self, file_path):
        return ParseResult(status=ParseStatus.COMPLETED)


class TestParseError:
    """Test ParseError dataclass functionality."""

    def test_parse_error_creation(self):
        """Test creating ParseError with all fields."""
        error = ParseError(
            message="Test error",
            error_type="TestError",
            line_number=10,
            column_number=5,
            context="test context",
            recoverable=True,
            suggestion="Fix the test"
        )

        assert error.message == "Test error"
        assert error.error_type == "TestError"
        assert error.line_number == 10
        assert error.column_number == 5
        assert error.context == "test context"
        assert error.recoverable is True
        assert error.suggestion == "Fix the test"

    def test_parse_error_minimal(self):
        """Test creating ParseError with minimal fields."""
        error = ParseError(message="Simple error", error_type="SimpleError")

        assert error.message == "Simple error"
        assert error.error_type == "SimpleError"
        assert error.line_number is None
        assert error.recoverable is False


class TestParseMetrics:
    """Test ParseMetrics functionality."""

    def test_parse_metrics_creation(self):
        """Test creating ParseMetrics with default values."""
        metrics = ParseMetrics()

        assert isinstance(metrics.start_time, datetime)
        assert metrics.end_time is None
        assert metrics.file_size_bytes == 0
        assert metrics.bytes_processed == 0
        assert metrics.endpoints_found == 0
        assert len(metrics.errors) == 0
        assert len(metrics.warnings) == 0

    def test_success_rate_no_issues(self):
        """Test success rate calculation with no errors."""
        metrics = ParseMetrics()
        metrics.endpoints_found = 10

        assert metrics.success_rate == 1.0

    def test_success_rate_with_errors(self):
        """Test success rate calculation with errors."""
        metrics = ParseMetrics()
        metrics.endpoints_found = 10
        metrics.errors = [ParseError("error1", "Error"), ParseError("error2", "Error")]
        metrics.warnings = [ParseError("warning1", "Warning")]

        # Formula: 1.0 - (errors / (total_issues + endpoints))
        expected = 1.0 - (2 / (3 + 10))
        assert abs(metrics.success_rate - expected) < 0.001

    def test_processing_speed_calculation(self):
        """Test processing speed calculation."""
        metrics = ParseMetrics()
        metrics.file_size_bytes = 2 * 1024 * 1024  # 2MB
        metrics.parse_duration_ms = 1000  # 1 second

        expected_speed = 2.0  # 2MB/s
        assert abs(metrics.processing_speed_mb_per_sec - expected_speed) < 0.001

    def test_processing_speed_zero_duration(self):
        """Test processing speed with zero duration."""
        metrics = ParseMetrics()
        metrics.file_size_bytes = 1024 * 1024  # 1MB
        metrics.parse_duration_ms = 0

        assert metrics.processing_speed_mb_per_sec == 0.0


class TestParseResult:
    """Test ParseResult functionality."""

    def test_parse_result_success(self):
        """Test successful parse result."""
        result = ParseResult(
            status=ParseStatus.COMPLETED,
            data={"openapi": "3.0.0"},
            file_path=Path("test.json")
        )

        assert result.is_success is True
        assert result.has_errors is False
        assert result.has_warnings is False

    def test_parse_result_with_errors(self):
        """Test parse result with errors."""
        metrics = ParseMetrics()
        metrics.errors.append(ParseError("Test error", "TestError"))
        metrics.warnings.append(ParseError("Test warning", "TestWarning"))

        result = ParseResult(
            status=ParseStatus.COMPLETED,
            data={"openapi": "3.0.0"},
            metrics=metrics
        )

        assert result.has_errors is True
        assert result.has_warnings is True

    def test_parse_result_failed(self):
        """Test failed parse result."""
        result = ParseResult(status=ParseStatus.FAILED)

        assert result.is_success is False


class TestParserConfig:
    """Test ParserConfig functionality."""

    def test_parser_config_defaults(self):
        """Test default parser configuration values."""
        config = ParserConfig()

        assert config.max_file_size_mb == 10
        assert config.max_memory_mb == 2048
        assert config.chunk_size_bytes == 8192
        assert config.validate_openapi is True
        assert config.preserve_order is True
        assert config.strict_mode is False
        assert config.progress_callback is None
        assert config.progress_interval_bytes == 1024 * 1024
        assert config.max_errors == 100
        assert config.continue_on_error is True
        assert config.collect_warnings is True

    def test_parser_config_custom(self):
        """Test custom parser configuration."""
        def dummy_callback(processed, total):
            pass

        config = ParserConfig(
            max_file_size_mb=5,
            strict_mode=True,
            progress_callback=dummy_callback
        )

        assert config.max_file_size_mb == 5
        assert config.strict_mode is True
        assert config.progress_callback is dummy_callback


class TestBaseParser:
    """Test BaseParser abstract functionality."""

    @pytest.fixture
    def mock_parser(self):
        """Create mock parser for testing."""
        return MockParser()

    @pytest.fixture
    def temp_json_file(self, tmp_path):
        """Create temporary JSON file for testing."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"openapi": "3.0.0", "info": {"title": "Test", "version": "1.0"}}')
        return json_file

    @pytest.fixture
    def large_temp_file(self, tmp_path):
        """Create large temporary file for testing size limits."""
        large_file = tmp_path / "large.json"
        # Create a file larger than default limit (10MB)
        large_content = '{"data": "' + 'x' * (11 * 1024 * 1024) + '"}'
        large_file.write_text(large_content)
        return large_file

    def test_parser_initialization(self, mock_parser):
        """Test parser initialization."""
        assert mock_parser.config is not None
        assert isinstance(mock_parser.config, ParserConfig)

    def test_parser_initialization_with_config(self):
        """Test parser initialization with custom config."""
        config = ParserConfig(strict_mode=True)
        parser = MockParser(config)

        assert parser.config.strict_mode is True

    def test_can_parse_supported_extension(self, mock_parser):
        """Test can_parse with supported file extension."""
        assert mock_parser.can_parse("test.json") is True
        assert mock_parser.can_parse(Path("test.json")) is True

    def test_can_parse_unsupported_extension(self, mock_parser):
        """Test can_parse with unsupported file extension."""
        assert mock_parser.can_parse("test.yaml") is False
        assert mock_parser.can_parse("test.txt") is False

    async def test_validate_file_constraints_success(self, mock_parser, temp_json_file):
        """Test successful file constraint validation."""
        # Should not raise exception
        await mock_parser.validate_file_constraints(temp_json_file)

    async def test_validate_file_constraints_not_found(self, mock_parser):
        """Test file constraint validation with missing file."""
        with pytest.raises(SwaggerParseError) as exc_info:
            await mock_parser.validate_file_constraints(Path("nonexistent.json"))

        assert "File not found" in str(exc_info.value)
        assert exc_info.value.error_type == "FileNotFound"

    async def test_validate_file_constraints_too_large(self, mock_parser, large_temp_file):
        """Test file constraint validation with oversized file."""
        with pytest.raises(SwaggerParseError) as exc_info:
            await mock_parser.validate_file_constraints(large_temp_file)

        assert "exceeds maximum" in str(exc_info.value)
        assert exc_info.value.error_type == "FileTooLarge"


class TestSwaggerParseError:
    """Test SwaggerParseError exception."""

    def test_swagger_parse_error_creation(self):
        """Test creating SwaggerParseError with all parameters."""
        error = SwaggerParseError(
            message="Test parsing error",
            error_type="TestError",
            line_number=5,
            column_number=10,
            context="test context",
            suggestion="fix suggestion",
            recoverable=True
        )

        assert str(error) == "Test parsing error"
        assert error.error_type == "TestError"
        assert error.line_number == 5
        assert error.column_number == 10
        assert error.context == "test context"
        assert error.suggestion == "fix suggestion"
        assert error.recoverable is True

    def test_swagger_parse_error_to_parse_error(self):
        """Test converting SwaggerParseError to ParseError."""
        error = SwaggerParseError(
            message="Test error",
            error_type="TestError",
            recoverable=True
        )

        parse_error = error.to_parse_error()

        assert isinstance(parse_error, ParseError)
        assert parse_error.message == "Test error"
        assert parse_error.error_type == "TestError"
        assert parse_error.recoverable is True


class TestParserFactory:
    """Test ParserFactory functionality."""

    @pytest.fixture
    def factory(self):
        """Create parser factory for testing."""
        return ParserFactory()

    @pytest.fixture
    def temp_json_file(self, tmp_path):
        """Create temporary JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"test": "data"}')
        return json_file

    def test_factory_initialization(self, factory):
        """Test factory initialization."""
        assert len(factory._parsers) == 0

    def test_register_parser(self, factory):
        """Test registering a parser."""
        factory.register_parser(ParserType.OPENAPI_JSON, MockParser)

        assert ParserType.OPENAPI_JSON in factory._parsers
        assert factory._parsers[ParserType.OPENAPI_JSON] == MockParser

    def test_create_parser_success(self, factory, temp_json_file):
        """Test creating parser for supported file type."""
        factory.register_parser(ParserType.OPENAPI_JSON, MockParser)

        parser = factory.create_parser(temp_json_file)

        assert isinstance(parser, MockParser)

    def test_create_parser_unsupported_type(self, factory, temp_json_file):
        """Test creating parser for unsupported file type."""
        # Don't register any parsers

        with pytest.raises(SwaggerParseError) as exc_info:
            factory.create_parser(temp_json_file)

        assert "No parser available" in str(exc_info.value)
        assert exc_info.value.error_type == "UnsupportedFileType"

    def test_create_parser_with_config(self, factory, temp_json_file):
        """Test creating parser with custom config."""
        factory.register_parser(ParserType.OPENAPI_JSON, MockParser)
        config = ParserConfig(strict_mode=True)

        parser = factory.create_parser(temp_json_file, config)

        assert isinstance(parser, MockParser)
        assert parser.config.strict_mode is True

    def test_detect_parser_type_json(self, factory):
        """Test detecting parser type for JSON file."""
        parser_type = factory._detect_parser_type(Path("test.json"))
        assert parser_type == ParserType.OPENAPI_JSON

    def test_detect_parser_type_yaml(self, factory):
        """Test detecting parser type for YAML file."""
        parser_type = factory._detect_parser_type(Path("test.yaml"))
        assert parser_type == ParserType.OPENAPI_YAML

        parser_type = factory._detect_parser_type(Path("test.yml"))
        assert parser_type == ParserType.OPENAPI_YAML

    def test_detect_parser_type_unsupported(self, factory):
        """Test detecting parser type for unsupported file."""
        with pytest.raises(SwaggerParseError) as exc_info:
            factory._detect_parser_type(Path("test.txt"))

        assert "Unsupported file extension" in str(exc_info.value)
        assert exc_info.value.error_type == "UnsupportedFileType"

    def test_get_supported_extensions(self, factory):
        """Test getting supported extensions."""
        factory.register_parser(ParserType.OPENAPI_JSON, MockParser)

        extensions = factory.get_supported_extensions()

        assert '.json' in extensions
        assert isinstance(extensions, list)