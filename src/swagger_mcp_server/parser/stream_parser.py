"""Stream-based JSON parser using ijson for memory-efficient processing."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union
import tracemalloc
import psutil
import os

try:
    import ijson
except ImportError:
    raise ImportError(
        "ijson library is required for stream parsing. "
        "Install with: pip install ijson"
    )

from swagger_mcp_server.parser.base import (
    BaseParser,
    ParserConfig,
    ParserType,
    ParseResult,
    ParseStatus,
    ParseMetrics,
    SwaggerParseError
)
from swagger_mcp_server.config.logging import get_logger

logger = get_logger(__name__)


class SwaggerStreamParser(BaseParser):
    """Memory-efficient stream-based parser for JSON Swagger/OpenAPI files."""

    def __init__(self, config: Optional[ParserConfig] = None):
        """Initialize stream parser.

        Args:
            config: Parser configuration
        """
        super().__init__(config)
        self._current_process = psutil.Process(os.getpid())

    def get_supported_extensions(self) -> list[str]:
        """Get supported file extensions.

        Returns:
            List of supported extensions
        """
        return ['.json']

    def get_parser_type(self) -> ParserType:
        """Get parser type.

        Returns:
            Parser type enum
        """
        return ParserType.OPENAPI_JSON

    async def parse(self, file_path: Union[str, Path]) -> ParseResult:
        """Parse JSON file using streaming approach.

        Args:
            file_path: Path to JSON file to parse

        Returns:
            ParseResult with parsed data and metrics
        """
        path = Path(file_path)
        metrics = ParseMetrics()

        try:
            # Start memory tracking
            if tracemalloc.is_tracing():
                tracemalloc.stop()
            tracemalloc.start()
            start_memory = self._get_memory_usage_mb()

            # Validate file constraints
            await self.validate_file_constraints(path)

            # Initialize metrics
            metrics.file_size_bytes = path.stat().st_size
            start_time = time.time()

            self.logger.info(
                "Starting stream parsing",
                file_path=str(path),
                file_size_mb=metrics.file_size_bytes / (1024 * 1024)
            )

            # Parse file using streaming approach
            result = ParseResult(
                status=ParseStatus.PARSING,
                file_path=path,
                metrics=metrics
            )

            # Use ijson for memory-efficient parsing
            parsed_data = await self._stream_parse_file(path, metrics)

            # Update metrics
            end_time = time.time()
            metrics.parse_duration_ms = (end_time - start_time) * 1000
            metrics.memory_peak_mb = max(
                metrics.memory_peak_mb,
                self._get_memory_usage_mb() - start_memory
            )

            # Extract basic API info
            if parsed_data:
                result.data = parsed_data
                result.openapi_version = self._extract_openapi_version(parsed_data)
                result.api_title = self._extract_api_title(parsed_data)
                result.api_version = self._extract_api_version(parsed_data)

                # Update quality metrics
                self._update_quality_metrics(parsed_data, metrics)

            result.status = ParseStatus.COMPLETED
            metrics.end_time = time.time()

            self.logger.info(
                "Stream parsing completed",
                file_path=str(path),
                duration_ms=metrics.parse_duration_ms,
                memory_peak_mb=metrics.memory_peak_mb,
                endpoints_found=metrics.endpoints_found,
                schemas_found=metrics.schemas_found
            )

            return result

        except Exception as e:
            metrics.end_time = time.time()
            error_msg = f"Failed to parse {path}: {str(e)}"

            self.logger.error(
                "Stream parsing failed",
                file_path=str(path),
                error=error_msg,
                error_type=type(e).__name__
            )

            if isinstance(e, SwaggerParseError):
                metrics.errors.append(e.to_parse_error())
                raise
            else:
                parse_error = SwaggerParseError(
                    error_msg,
                    "StreamParsingError",
                    suggestion="Check if file is valid JSON and not corrupted"
                )
                metrics.errors.append(parse_error.to_parse_error())

                return ParseResult(
                    status=ParseStatus.FAILED,
                    file_path=path,
                    metrics=metrics
                )

        finally:
            if tracemalloc.is_tracing():
                tracemalloc.stop()

    async def _stream_parse_file(self, file_path: Path, metrics: ParseMetrics) -> Dict[str, Any]:
        """Parse file using ijson streaming parser.

        Args:
            file_path: Path to file to parse
            metrics: Metrics object to update

        Returns:
            Parsed JSON data as dictionary

        Raises:
            SwaggerParseError: If parsing fails
        """
        try:
            # Open file and create parser
            with open(file_path, 'rb') as file:
                # Use ijson to parse the JSON incrementally
                parser = ijson.parse(file, buf_size=self.config.chunk_size_bytes)

                # Build the JSON structure incrementally
                result = await self._build_json_structure(parser, metrics)

                return result

        except json.JSONDecodeError as e:
            raise SwaggerParseError(
                f"Invalid JSON: {e.msg}",
                "InvalidJSON",
                line_number=getattr(e, 'lineno', None),
                column_number=getattr(e, 'colno', None),
                context=f"Position {e.pos}" if hasattr(e, 'pos') else None,
                suggestion="Validate JSON syntax using a JSON validator"
            )
        except IOError as e:
            raise SwaggerParseError(
                f"File I/O error: {str(e)}",
                "FileIOError",
                suggestion="Check file permissions and disk space"
            )

    async def _build_json_structure(
        self,
        parser,
        metrics: ParseMetrics
    ) -> Dict[str, Any]:
        """Build JSON structure from ijson parser events.

        Args:
            parser: ijson parser instance
            metrics: Metrics to update during parsing

        Returns:
            Complete JSON structure

        Raises:
            SwaggerParseError: If structure building fails
        """
        stack = [{}]  # Stack of objects/arrays being built
        current_key = None
        bytes_processed = 0
        last_progress_report = 0

        try:
            for event_type, value in parser:
                bytes_processed += len(str(value).encode('utf-8'))

                # Report progress if configured
                if (self.config.progress_callback and
                    bytes_processed - last_progress_report >= self.config.progress_interval_bytes):

                    self.config.progress_callback(bytes_processed, metrics.file_size_bytes)
                    last_progress_report = bytes_processed

                    # Check memory usage
                    current_memory = self._get_memory_usage_mb()
                    metrics.memory_peak_mb = max(metrics.memory_peak_mb, current_memory)

                    if current_memory > self.config.max_memory_mb:
                        raise SwaggerParseError(
                            f"Memory usage {current_memory:.1f}MB exceeds limit {self.config.max_memory_mb}MB",
                            "MemoryLimitExceeded",
                            suggestion="Increase memory limit or use a smaller file"
                        )

                # Allow other tasks to run
                if bytes_processed % (self.config.chunk_size_bytes * 10) == 0:
                    await asyncio.sleep(0)  # Yield control

                # Process ijson events
                if event_type == 'start_map':
                    new_obj = {}
                    if current_key is not None:
                        stack[-1][current_key] = new_obj
                        current_key = None
                    stack.append(new_obj)

                elif event_type == 'end_map':
                    if len(stack) > 1:
                        completed_obj = stack.pop()
                        if len(stack) == 1:  # Root object completed
                            stack[0] = completed_obj

                elif event_type == 'start_array':
                    new_array = []
                    if current_key is not None:
                        stack[-1][current_key] = new_array
                        current_key = None
                    stack.append(new_array)

                elif event_type == 'end_array':
                    if len(stack) > 1:
                        stack.pop()

                elif event_type == 'map_key':
                    current_key = value

                elif event_type in ['string', 'number', 'boolean', 'null']:
                    if current_key is not None:
                        stack[-1][current_key] = value
                        current_key = None
                    elif isinstance(stack[-1], list):
                        stack[-1].append(value)

            metrics.bytes_processed = bytes_processed

            # Final progress report
            if self.config.progress_callback:
                self.config.progress_callback(bytes_processed, metrics.file_size_bytes)

            return stack[0] if stack else {}

        except Exception as e:
            if isinstance(e, SwaggerParseError):
                raise
            raise SwaggerParseError(
                f"Failed to build JSON structure: {str(e)}",
                "StructureBuildError",
                suggestion="File may be corrupted or contain invalid JSON structure"
            )

    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB.

        Returns:
            Memory usage in megabytes
        """
        try:
            # Get memory info for current process
            memory_info = self._current_process.memory_info()
            return memory_info.rss / (1024 * 1024)  # Convert bytes to MB
        except:
            # Fallback to tracemalloc if psutil fails
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                return current / (1024 * 1024)
            return 0.0

    def _extract_openapi_version(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract OpenAPI version from parsed data.

        Args:
            data: Parsed JSON data

        Returns:
            OpenAPI version string if found
        """
        return data.get('openapi') or data.get('swagger')

    def _extract_api_title(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract API title from parsed data.

        Args:
            data: Parsed JSON data

        Returns:
            API title if found
        """
        info = data.get('info', {})
        return info.get('title') if isinstance(info, dict) else None

    def _extract_api_version(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract API version from parsed data.

        Args:
            data: Parsed JSON data

        Returns:
            API version if found
        """
        info = data.get('info', {})
        return info.get('version') if isinstance(info, dict) else None

    def _update_quality_metrics(self, data: Dict[str, Any], metrics: ParseMetrics) -> None:
        """Update quality metrics based on parsed data.

        Args:
            data: Parsed JSON data
            metrics: Metrics object to update
        """
        try:
            # Count endpoints
            paths = data.get('paths', {})
            if isinstance(paths, dict):
                endpoint_count = 0
                for path_data in paths.values():
                    if isinstance(path_data, dict):
                        # Count HTTP methods
                        http_methods = {'get', 'post', 'put', 'delete', 'patch', 'head', 'options', 'trace'}
                        endpoint_count += len([m for m in path_data.keys() if m.lower() in http_methods])
                metrics.endpoints_found = endpoint_count

            # Count schemas
            components = data.get('components', {})
            if isinstance(components, dict):
                schemas = components.get('schemas', {})
                if isinstance(schemas, dict):
                    metrics.schemas_found = len(schemas)

                # Count security schemes
                security_schemes = components.get('securitySchemes', {})
                if isinstance(security_schemes, dict):
                    metrics.security_schemes_found = len(security_schemes)

            # Count extensions (x-* properties)
            metrics.extensions_found = self._count_extensions(data)

        except Exception as e:
            self.logger.warning(
                "Failed to update quality metrics",
                error=str(e),
                error_type=type(e).__name__
            )

    def _count_extensions(self, obj: Any, count: int = 0) -> int:
        """Recursively count OpenAPI extensions (x-* properties).

        Args:
            obj: Object to scan for extensions
            count: Current count

        Returns:
            Total count of extensions found
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(key, str) and key.startswith('x-'):
                    count += 1
                count = self._count_extensions(value, count)
        elif isinstance(obj, list):
            for item in obj:
                count = self._count_extensions(item, count)

        return count