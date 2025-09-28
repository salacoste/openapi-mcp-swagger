"""Main Swagger/OpenAPI parser with integrated components."""

import asyncio
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from swagger_mcp_server.config.logging import get_logger, log_parsing_progress
from swagger_mcp_server.parser.base import (
    BaseParser,
    ParseMetrics,
    ParserConfig,
    ParseResult,
    ParserType,
    ParseStatus,
    SwaggerParseError,
)
from swagger_mcp_server.parser.error_handler import ErrorContext, ErrorHandler
from swagger_mcp_server.parser.progress_reporter import (
    ProgressPhase,
    ProgressReporter,
)
from swagger_mcp_server.parser.stream_parser import SwaggerStreamParser
from swagger_mcp_server.parser.structure_validator import StructureValidator
from swagger_mcp_server.parser.validation import (
    OpenAPIValidator,
    ValidationResult,
)

logger = get_logger(__name__)


class SwaggerParser(BaseParser):
    """Main parser that orchestrates all parsing components."""

    def __init__(self, config: Optional[ParserConfig] = None):
        """Initialize main parser with all components.

        Args:
            config: Parser configuration
        """
        super().__init__(config)

        # Initialize components
        self.error_handler = ErrorHandler(
            strict_mode=self.config.strict_mode,
            max_errors=self.config.max_errors,
        )
        self.stream_parser = SwaggerStreamParser(config)
        self.structure_validator = StructureValidator(
            self.error_handler, preserve_order=self.config.preserve_order
        )
        self.openapi_validator = OpenAPIValidator(
            self.error_handler, strict_mode=self.config.strict_mode
        )
        self.progress_reporter = ProgressReporter(
            callback=self.config.progress_callback,
            interval_bytes=self.config.progress_interval_bytes,
        )

    def get_supported_extensions(self) -> list[str]:
        """Get supported file extensions.

        Returns:
            List of supported extensions
        """
        return [".json"]

    def get_parser_type(self) -> ParserType:
        """Get parser type.

        Returns:
            Parser type enum
        """
        return ParserType.OPENAPI_JSON

    async def parse(self, file_path: Union[str, Path]) -> ParseResult:
        """Parse Swagger/OpenAPI file with full processing pipeline.

        Args:
            file_path: Path to file to parse

        Returns:
            Complete parse result with validation and structure preservation
        """
        path = Path(file_path)
        start_time = time.time()

        try:
            # Initialize metrics and progress tracking
            metrics = ParseMetrics()
            metrics.file_size_bytes = path.stat().st_size

            self.logger.info(
                "Starting comprehensive Swagger parsing",
                file_path=str(path),
                file_size_mb=metrics.file_size_bytes / (1024 * 1024),
                pipeline_components=[
                    "stream_parser",
                    "structure_validator",
                    "openapi_validator",
                ],
            )

            # Phase 1: Stream Parsing
            await self.progress_reporter.start_phase(
                ProgressPhase.PARSING,
                "Parsing JSON structure",
                metrics.file_size_bytes,
            )

            parse_result = await self._parse_with_progress(path, metrics)

            if not parse_result.is_success:
                return parse_result

            # Phase 2: Structure Validation and Preservation
            await self.progress_reporter.start_phase(
                ProgressPhase.VALIDATION,
                "Validating OpenAPI structure",
                0,  # Structure validation is not byte-based
            )

            validated_data = await self._validate_structure_with_progress(
                parse_result.data, str(path), metrics
            )

            # Phase 3: OpenAPI Compliance Validation
            await self.progress_reporter.start_phase(
                ProgressPhase.VALIDATION, "Validating OpenAPI compliance", 0
            )

            validation_result = await self._validate_openapi_with_progress(
                validated_data, str(path), metrics
            )

            # Phase 4: Completion and Metrics
            await self.progress_reporter.complete("Parsing completed successfully")

            # Update final result
            final_result = ParseResult(
                status=ParseStatus.COMPLETED,
                data=validated_data,
                file_path=path,
                openapi_version=parse_result.openapi_version,
                api_title=parse_result.api_title,
                api_version=parse_result.api_version,
                metrics=metrics,
            )

            # Merge validation metrics
            if validation_result:
                metrics.validation_duration_ms = (
                    validation_result.validation_duration_ms
                )

            # Update final metrics
            end_time = time.time()
            total_duration = (end_time - start_time) * 1000
            metrics.parse_duration_ms = total_duration - metrics.validation_duration_ms

            # Collect all errors and warnings
            metrics.errors.extend(self.error_handler.errors)
            metrics.warnings.extend(self.error_handler.warnings)

            self.logger.info(
                "Comprehensive parsing completed",
                file_path=str(path),
                total_duration_ms=total_duration,
                parse_duration_ms=metrics.parse_duration_ms,
                validation_duration_ms=metrics.validation_duration_ms,
                endpoints_found=metrics.endpoints_found,
                schemas_found=metrics.schemas_found,
                errors=len(metrics.errors),
                warnings=len(metrics.warnings),
                success_rate=metrics.success_rate,
            )

            return final_result

        except Exception as e:
            await self.progress_reporter.fail(f"Parsing failed: {str(e)}")

            metrics.end_time = time.time()
            error_msg = f"Comprehensive parsing failed: {str(e)}"

            self.logger.error(
                "Comprehensive parsing failed",
                file_path=str(path),
                error=error_msg,
                error_type=type(e).__name__,
                duration_ms=(time.time() - start_time) * 1000,
            )

            if isinstance(e, SwaggerParseError):
                raise

            return ParseResult(
                status=ParseStatus.FAILED, file_path=path, metrics=metrics
            )

    async def _parse_with_progress(
        self, path: Path, metrics: ParseMetrics
    ) -> ParseResult:
        """Parse file with progress reporting.

        Args:
            path: File path
            metrics: Metrics to update

        Returns:
            Parse result from stream parser
        """
        # Set up progress callback for stream parser
        original_callback = self.config.progress_callback

        def progress_callback(bytes_processed: int, total_bytes: int):
            # Report to progress reporter
            asyncio.create_task(
                self.progress_reporter.update_progress(bytes_processed, total_bytes)
            )

            # Call original callback if exists
            if original_callback:
                original_callback(bytes_processed, total_bytes)

            # Log parsing progress
            progress_percent = (
                (bytes_processed / total_bytes) * 100 if total_bytes > 0 else 0
            )
            log_parsing_progress(
                logger,
                str(path),
                bytes_processed,
                total_bytes,
                progress_percent,
                phase="stream_parsing",
            )

        # Temporarily set progress callback
        self.config.progress_callback = progress_callback
        self.stream_parser.config.progress_callback = progress_callback

        try:
            result = await self.stream_parser.parse(path)
            await self.progress_reporter.complete_phase("JSON parsing completed")
            return result
        finally:
            # Restore original callback
            self.config.progress_callback = original_callback
            self.stream_parser.config.progress_callback = original_callback

    async def _validate_structure_with_progress(
        self, data: Dict[str, Any], file_path: str, metrics: ParseMetrics
    ) -> Dict[str, Any]:
        """Validate structure with progress reporting.

        Args:
            data: Parsed data
            file_path: File path
            metrics: Metrics to update

        Returns:
            Validated and preserved data
        """
        try:
            # Structure validation is typically fast, so we'll simulate progress
            await self.progress_reporter.update_progress(
                0, 100, "Starting structure validation"
            )

            validated_data = self.structure_validator.validate_and_preserve_structure(
                data, file_path
            )

            await self.progress_reporter.update_progress(
                100, 100, "Structure validation completed"
            )
            await self.progress_reporter.complete_phase(
                "Structure validation completed"
            )

            return validated_data

        except Exception as e:
            await self.progress_reporter.fail(f"Structure validation failed: {str(e)}")
            raise

    async def _validate_openapi_with_progress(
        self, data: Dict[str, Any], file_path: str, metrics: ParseMetrics
    ) -> Optional[ValidationResult]:
        """Validate OpenAPI compliance with progress reporting.

        Args:
            data: Validated data
            file_path: File path
            metrics: Metrics to update

        Returns:
            Validation result if validation is enabled
        """
        if not self.config.validate_openapi:
            await self.progress_reporter.complete_phase("OpenAPI validation skipped")
            return None

        try:
            await self.progress_reporter.update_progress(
                0, 100, "Starting OpenAPI validation"
            )

            validation_result = await self.openapi_validator.validate_specification(
                data, file_path
            )

            await self.progress_reporter.update_progress(
                100, 100, "OpenAPI validation completed"
            )
            await self.progress_reporter.complete_phase(
                f"OpenAPI validation completed ({'valid' if validation_result.is_valid else 'invalid'})"
            )

            return validation_result

        except Exception as e:
            await self.progress_reporter.fail(f"OpenAPI validation failed: {str(e)}")
            raise

    def get_parsing_metrics(self) -> Dict[str, Any]:
        """Get comprehensive parsing metrics.

        Returns:
            Dictionary with all parsing metrics
        """
        return {
            "stream_parser_metrics": {
                "memory_peak_mb": getattr(self.stream_parser, "_last_memory_peak", 0),
                "extensions_found": 0,  # Will be updated during parsing
            },
            "error_handler_metrics": self.error_handler.get_error_summary(),
            "validation_metrics": {
                "structure_validation_enabled": True,
                "openapi_validation_enabled": self.config.validate_openapi,
            },
            "progress_metrics": self.progress_reporter.get_metrics(),
        }

    def reset_state(self) -> None:
        """Reset parser state for new parsing operation."""
        self.error_handler = ErrorHandler(
            strict_mode=self.config.strict_mode,
            max_errors=self.config.max_errors,
        )
        self.structure_validator = StructureValidator(
            self.error_handler, preserve_order=self.config.preserve_order
        )
        self.openapi_validator = OpenAPIValidator(
            self.error_handler, strict_mode=self.config.strict_mode
        )
        self.progress_reporter.reset()

        self.logger.debug("Parser state reset for new operation")
