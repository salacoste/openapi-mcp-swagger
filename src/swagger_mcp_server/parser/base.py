"""Base parser interface and data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from swagger_mcp_server.config.logging import get_logger

logger = get_logger(__name__)


class ParserType(Enum):
    """Supported parser types."""

    SWAGGER_JSON = "swagger_json"
    OPENAPI_JSON = "openapi_json"
    OPENAPI_YAML = "openapi_yaml"


class ParseStatus(Enum):
    """Parser execution status."""

    PENDING = "pending"
    PARSING = "parsing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ParseError:
    """Represents a parsing error with context."""

    message: str
    error_type: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    context: Optional[str] = None
    recoverable: bool = False
    suggestion: Optional[str] = None


@dataclass
class ParseMetrics:
    """Parsing performance and quality metrics."""

    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    file_size_bytes: int = 0
    bytes_processed: int = 0
    memory_peak_mb: float = 0.0
    parse_duration_ms: float = 0.0
    validation_duration_ms: float = 0.0

    # Quality metrics
    endpoints_found: int = 0
    schemas_found: int = 0
    security_schemes_found: int = 0
    extensions_found: int = 0

    # Error metrics
    errors: List[ParseError] = field(default_factory=list)
    warnings: List[ParseError] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate based on errors."""
        total_issues = len(self.errors) + len(self.warnings)
        if total_issues == 0:
            return 1.0
        return 1.0 - (len(self.errors) / (total_issues + self.endpoints_found))

    @property
    def processing_speed_mb_per_sec(self) -> float:
        """Calculate processing speed in MB/s."""
        if self.parse_duration_ms == 0:
            return 0.0
        mb_processed = self.file_size_bytes / (1024 * 1024)
        seconds = self.parse_duration_ms / 1000
        return mb_processed / seconds


@dataclass
class ParseResult:
    """Result of parsing operation."""

    status: ParseStatus
    data: Optional[Dict[str, Any]] = None
    metrics: ParseMetrics = field(default_factory=ParseMetrics)
    file_path: Optional[Path] = None
    openapi_version: Optional[str] = None
    api_title: Optional[str] = None
    api_version: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Check if parsing was successful."""
        return self.status == ParseStatus.COMPLETED and self.data is not None

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.metrics.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.metrics.warnings) > 0


@dataclass
class ParserConfig:
    """Parser configuration options."""

    # Memory management
    max_file_size_mb: int = 10
    max_memory_mb: int = 2048  # 2GB RAM limit
    chunk_size_bytes: int = 8192

    # Processing options
    validate_openapi: bool = True
    preserve_order: bool = True
    strict_mode: bool = False

    # Progress reporting
    progress_callback: Optional[Callable[[int, int], None]] = None
    progress_interval_bytes: int = 1024 * 1024  # 1MB

    # Error handling
    max_errors: int = 100
    continue_on_error: bool = True
    collect_warnings: bool = True


# Type alias for progress callback
ProgressCallback = Callable[[int, int], None]  # (bytes_processed, total_bytes)


class BaseParser(ABC):
    """Abstract base parser for different file formats."""

    def __init__(self, config: Optional[ParserConfig] = None):
        """Initialize parser with configuration.

        Args:
            config: Parser configuration, defaults to ParserConfig()
        """
        self.config = config or ParserConfig()
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def parse(self, file_path: Union[str, Path]) -> ParseResult:
        """Parse the given file.

        Args:
            file_path: Path to the file to parse

        Returns:
            ParseResult with parsed data and metrics

        Raises:
            SwaggerParseError: If parsing fails with unrecoverable error
        """
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions.

        Returns:
            List of file extensions (e.g., ['.json', '.yaml'])
        """
        pass

    @abstractmethod
    def get_parser_type(self) -> ParserType:
        """Get the parser type.

        Returns:
            ParserType enum value
        """
        pass

    def can_parse(self, file_path: Union[str, Path]) -> bool:
        """Check if this parser can handle the given file.

        Args:
            file_path: Path to the file to check

        Returns:
            True if parser can handle this file type
        """
        path = Path(file_path)
        return path.suffix.lower() in self.get_supported_extensions()

    async def validate_file_constraints(self, file_path: Path) -> None:
        """Validate file meets size and format constraints.

        Args:
            file_path: Path to file to validate

        Raises:
            SwaggerParseError: If file doesn't meet constraints
        """
        if not file_path.exists():
            raise SwaggerParseError(
                f"File not found: {file_path}", "FileNotFound"
            )

        # Check file size
        file_size = file_path.stat().st_size
        max_size = self.config.max_file_size_mb * 1024 * 1024

        if file_size > max_size:
            raise SwaggerParseError(
                f"File size {file_size / (1024*1024):.1f}MB exceeds maximum "
                f"{self.config.max_file_size_mb}MB",
                "FileTooLarge",
            )

        self.logger.info(
            "File validation passed",
            file_path=str(file_path),
            file_size_mb=file_size / (1024 * 1024),
        )


class ParserFactory:
    """Factory for creating appropriate parsers based on file type."""

    def __init__(self):
        self._parsers: Dict[ParserType, type] = {}
        self.logger = get_logger(__name__)

    def register_parser(
        self, parser_type: ParserType, parser_class: type
    ) -> None:
        """Register a parser class for a specific type.

        Args:
            parser_type: Type of parser
            parser_class: Parser class to register
        """
        self._parsers[parser_type] = parser_class
        self.logger.debug(
            "Parser registered",
            parser_type=parser_type.value,
            parser_class=parser_class.__name__,
        )

    def create_parser(
        self,
        file_path: Union[str, Path],
        config: Optional[ParserConfig] = None,
    ) -> BaseParser:
        """Create appropriate parser for the given file.

        Args:
            file_path: Path to file to parse
            config: Parser configuration

        Returns:
            Parser instance for the file type

        Raises:
            SwaggerParseError: If no suitable parser found
        """
        path = Path(file_path)

        # Determine parser type based on file extension and content
        parser_type = self._detect_parser_type(path)

        if parser_type not in self._parsers:
            raise SwaggerParseError(
                f"No parser available for type: {parser_type.value}",
                "UnsupportedFileType",
            )

        parser_class = self._parsers[parser_type]
        return parser_class(config)

    def _detect_parser_type(self, file_path: Path) -> ParserType:
        """Detect the appropriate parser type for a file.

        Args:
            file_path: Path to the file

        Returns:
            Detected parser type

        Raises:
            SwaggerParseError: If file type cannot be determined
        """
        extension = file_path.suffix.lower()

        if extension == ".json":
            # For JSON files, we'll assume OpenAPI/Swagger JSON
            # Could be enhanced with content sniffing
            return ParserType.OPENAPI_JSON
        elif extension in [".yaml", ".yml"]:
            return ParserType.OPENAPI_YAML
        else:
            raise SwaggerParseError(
                f"Unsupported file extension: {extension}",
                "UnsupportedFileType",
                suggestion="Supported formats: .json, .yaml, .yml",
            )

    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions.

        Returns:
            List of supported extensions
        """
        extensions = set()
        for parser_type in self._parsers:
            # This would need to be implemented per parser
            if parser_type in [
                ParserType.SWAGGER_JSON,
                ParserType.OPENAPI_JSON,
            ]:
                extensions.add(".json")
            elif parser_type == ParserType.OPENAPI_YAML:
                extensions.update([".yaml", ".yml"])

        return sorted(list(extensions))


class SwaggerParseError(Exception):
    """Custom exception for parsing errors."""

    def __init__(
        self,
        message: str,
        error_type: str,
        line_number: Optional[int] = None,
        column_number: Optional[int] = None,
        context: Optional[str] = None,
        suggestion: Optional[str] = None,
        recoverable: bool = False,
    ):
        """Initialize parsing error.

        Args:
            message: Error message
            error_type: Type/category of error
            line_number: Line number where error occurred
            column_number: Column number where error occurred
            context: Additional context about the error
            suggestion: Suggestion for fixing the error
            recoverable: Whether parsing can continue despite this error
        """
        super().__init__(message)
        self.error_type = error_type
        self.line_number = line_number
        self.column_number = column_number
        self.context = context
        self.suggestion = suggestion
        self.recoverable = recoverable

    def to_parse_error(self) -> ParseError:
        """Convert to ParseError dataclass.

        Returns:
            ParseError representation
        """
        return ParseError(
            message=str(self),
            error_type=self.error_type,
            line_number=self.line_number,
            column_number=self.column_number,
            context=self.context,
            recoverable=self.recoverable,
            suggestion=self.suggestion,
        )
