"""Progress reporting system for parsing operations."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from swagger_mcp_server.config.logging import get_logger

logger = get_logger(__name__)


class ProgressPhase(Enum):
    """Different phases of parsing operation."""

    INITIALIZATION = "initialization"
    PARSING = "parsing"
    VALIDATION = "validation"
    NORMALIZATION = "normalization"
    STORAGE = "storage"
    COMPLETION = "completion"


@dataclass
class ProgressEvent:
    """Progress event data."""

    phase: ProgressPhase
    progress_percent: float
    message: str
    timestamp: float = field(default_factory=time.time)
    bytes_processed: int = 0
    total_bytes: int = 0
    estimated_remaining_ms: Optional[float] = None


@dataclass
class PhaseMetrics:
    """Metrics for a single phase."""

    phase: ProgressPhase
    start_time: float
    end_time: Optional[float] = None
    bytes_processed: int = 0
    total_bytes: int = 0
    progress_percent: float = 0.0
    events: List[ProgressEvent] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        """Get phase duration in milliseconds."""
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    @property
    def is_completed(self) -> bool:
        """Check if phase is completed."""
        return self.end_time is not None

    @property
    def processing_speed_mb_per_sec(self) -> float:
        """Calculate processing speed in MB/s."""
        if self.duration_ms == 0 or self.bytes_processed == 0:
            return 0.0
        mb_processed = self.bytes_processed / (1024 * 1024)
        seconds = self.duration_ms / 1000
        return mb_processed / seconds


# Type alias for progress callback
ProgressCallback = Callable[[ProgressEvent], None]


class ProgressReporter:
    """Reports progress during parsing operations."""

    def __init__(
        self,
        callback: Optional[ProgressCallback] = None,
        interval_bytes: int = 1024 * 1024  # 1MB
    ):
        """Initialize progress reporter.

        Args:
            callback: Optional callback for progress events
            interval_bytes: Minimum bytes between progress reports
        """
        self.callback = callback
        self.interval_bytes = interval_bytes
        self.logger = get_logger(__name__)

        # State tracking
        self.current_phase: Optional[ProgressPhase] = None
        self.phase_metrics: Dict[ProgressPhase, PhaseMetrics] = {}
        self.last_report_bytes = 0
        self.last_report_time = 0.0
        self.operation_start_time = time.time()

        # Overall progress
        self.total_operation_bytes = 0
        self.total_processed_bytes = 0

    async def start_operation(self, total_bytes: int = 0, description: str = "Processing") -> None:
        """Start a new parsing operation.

        Args:
            total_bytes: Total bytes to process (if known)
            description: Operation description
        """
        self.operation_start_time = time.time()
        self.total_operation_bytes = total_bytes
        self.total_processed_bytes = 0
        self.phase_metrics.clear()

        event = ProgressEvent(
            phase=ProgressPhase.INITIALIZATION,
            progress_percent=0.0,
            message=description,
            total_bytes=total_bytes
        )

        await self._emit_event(event)

        self.logger.info(
            "Progress tracking started",
            total_bytes=total_bytes,
            description=description
        )

    async def start_phase(
        self,
        phase: ProgressPhase,
        description: str,
        phase_total_bytes: int = 0
    ) -> None:
        """Start a new processing phase.

        Args:
            phase: Phase type
            description: Phase description
            phase_total_bytes: Total bytes for this phase
        """
        # Complete previous phase if needed
        if self.current_phase and self.current_phase != phase:
            await self.complete_phase("Phase completed")

        self.current_phase = phase
        current_time = time.time()

        # Initialize phase metrics
        self.phase_metrics[phase] = PhaseMetrics(
            phase=phase,
            start_time=current_time,
            total_bytes=phase_total_bytes
        )

        event = ProgressEvent(
            phase=phase,
            progress_percent=0.0,
            message=description,
            total_bytes=phase_total_bytes
        )

        await self._emit_event(event)

        self.logger.debug(
            "Phase started",
            phase=phase.value,
            description=description,
            phase_total_bytes=phase_total_bytes
        )

    async def update_progress(
        self,
        bytes_processed: int,
        total_bytes: int,
        message: Optional[str] = None
    ) -> None:
        """Update progress within current phase.

        Args:
            bytes_processed: Bytes processed so far
            total_bytes: Total bytes for current phase
            message: Optional progress message
        """
        if not self.current_phase:
            return

        current_time = time.time()

        # Check if we should report (based on bytes or time interval)
        bytes_since_last = bytes_processed - self.last_report_bytes
        time_since_last = current_time - self.last_report_time

        should_report = (
            bytes_since_last >= self.interval_bytes or
            time_since_last >= 1.0 or  # At least every second
            bytes_processed >= total_bytes  # Always report completion
        )

        if not should_report:
            return

        # Calculate progress percentage
        progress_percent = (bytes_processed / total_bytes * 100) if total_bytes > 0 else 0

        # Update phase metrics
        phase_metrics = self.phase_metrics[self.current_phase]
        phase_metrics.bytes_processed = bytes_processed
        phase_metrics.total_bytes = total_bytes
        phase_metrics.progress_percent = progress_percent

        # Estimate remaining time
        estimated_remaining = self._estimate_remaining_time(
            bytes_processed, total_bytes, phase_metrics.start_time
        )

        event = ProgressEvent(
            phase=self.current_phase,
            progress_percent=progress_percent,
            message=message or f"{self.current_phase.value.title()} in progress",
            bytes_processed=bytes_processed,
            total_bytes=total_bytes,
            estimated_remaining_ms=estimated_remaining
        )

        phase_metrics.events.append(event)
        await self._emit_event(event)

        # Update tracking variables
        self.last_report_bytes = bytes_processed
        self.last_report_time = current_time
        self.total_processed_bytes += bytes_since_last

        self.logger.debug(
            "Progress updated",
            phase=self.current_phase.value,
            progress_percent=progress_percent,
            bytes_processed=bytes_processed,
            total_bytes=total_bytes,
            estimated_remaining_ms=estimated_remaining
        )

    async def complete_phase(self, message: str = "Phase completed") -> None:
        """Complete the current phase.

        Args:
            message: Completion message
        """
        if not self.current_phase:
            return

        current_time = time.time()
        phase_metrics = self.phase_metrics[self.current_phase]
        phase_metrics.end_time = current_time

        event = ProgressEvent(
            phase=self.current_phase,
            progress_percent=100.0,
            message=message,
            bytes_processed=phase_metrics.bytes_processed,
            total_bytes=phase_metrics.total_bytes
        )

        phase_metrics.events.append(event)
        await self._emit_event(event)

        self.logger.info(
            "Phase completed",
            phase=self.current_phase.value,
            duration_ms=phase_metrics.duration_ms,
            bytes_processed=phase_metrics.bytes_processed,
            processing_speed_mb_per_sec=phase_metrics.processing_speed_mb_per_sec
        )

        self.current_phase = None

    async def complete(self, message: str = "Operation completed successfully") -> None:
        """Complete the entire operation.

        Args:
            message: Completion message
        """
        # Complete current phase if active
        if self.current_phase:
            await self.complete_phase("Final phase completed")

        total_duration = (time.time() - self.operation_start_time) * 1000

        event = ProgressEvent(
            phase=ProgressPhase.COMPLETION,
            progress_percent=100.0,
            message=message,
            bytes_processed=self.total_processed_bytes,
            total_bytes=self.total_operation_bytes
        )

        await self._emit_event(event)

        self.logger.info(
            "Operation completed",
            total_duration_ms=total_duration,
            total_bytes_processed=self.total_processed_bytes,
            phases_completed=len(self.phase_metrics),
            overall_speed_mb_per_sec=self._calculate_overall_speed()
        )

    async def fail(self, error_message: str) -> None:
        """Report operation failure.

        Args:
            error_message: Error description
        """
        event = ProgressEvent(
            phase=self.current_phase or ProgressPhase.COMPLETION,
            progress_percent=0.0,  # Reset to indicate failure
            message=f"Failed: {error_message}",
            bytes_processed=self.total_processed_bytes,
            total_bytes=self.total_operation_bytes
        )

        await self._emit_event(event)

        self.logger.error(
            "Operation failed",
            error_message=error_message,
            current_phase=self.current_phase.value if self.current_phase else None,
            bytes_processed=self.total_processed_bytes
        )

    async def cancel(self, reason: str = "Operation cancelled") -> None:
        """Report operation cancellation.

        Args:
            reason: Cancellation reason
        """
        event = ProgressEvent(
            phase=self.current_phase or ProgressPhase.COMPLETION,
            progress_percent=0.0,
            message=f"Cancelled: {reason}",
            bytes_processed=self.total_processed_bytes,
            total_bytes=self.total_operation_bytes
        )

        await self._emit_event(event)

        self.logger.warning(
            "Operation cancelled",
            reason=reason,
            current_phase=self.current_phase.value if self.current_phase else None
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive progress metrics.

        Returns:
            Dictionary with all progress metrics
        """
        total_duration = (time.time() - self.operation_start_time) * 1000

        return {
            "operation_duration_ms": total_duration,
            "total_bytes_processed": self.total_processed_bytes,
            "total_operation_bytes": self.total_operation_bytes,
            "overall_speed_mb_per_sec": self._calculate_overall_speed(),
            "phases": {
                phase.value: {
                    "duration_ms": metrics.duration_ms,
                    "bytes_processed": metrics.bytes_processed,
                    "total_bytes": metrics.total_bytes,
                    "progress_percent": metrics.progress_percent,
                    "processing_speed_mb_per_sec": metrics.processing_speed_mb_per_sec,
                    "is_completed": metrics.is_completed,
                    "events_count": len(metrics.events)
                }
                for phase, metrics in self.phase_metrics.items()
            },
            "current_phase": self.current_phase.value if self.current_phase else None
        }

    def reset(self) -> None:
        """Reset progress reporter for new operation."""
        self.current_phase = None
        self.phase_metrics.clear()
        self.last_report_bytes = 0
        self.last_report_time = 0.0
        self.operation_start_time = time.time()
        self.total_operation_bytes = 0
        self.total_processed_bytes = 0

        self.logger.debug("Progress reporter reset")

    async def _emit_event(self, event: ProgressEvent) -> None:
        """Emit progress event to callback.

        Args:
            event: Progress event to emit
        """
        if self.callback:
            try:
                # Handle both sync and async callbacks
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(event)
                else:
                    self.callback(event)
            except Exception as e:
                self.logger.warning(
                    "Progress callback error",
                    error=str(e),
                    event_phase=event.phase.value
                )

    def _estimate_remaining_time(
        self,
        bytes_processed: int,
        total_bytes: int,
        start_time: float
    ) -> Optional[float]:
        """Estimate remaining time based on current progress.

        Args:
            bytes_processed: Bytes processed so far
            total_bytes: Total bytes to process
            start_time: Phase start time

        Returns:
            Estimated remaining time in milliseconds, or None if cannot estimate
        """
        if bytes_processed <= 0 or total_bytes <= 0 or bytes_processed >= total_bytes:
            return None

        elapsed_time = time.time() - start_time
        if elapsed_time <= 0:
            return None

        # Calculate processing rate
        processing_rate = bytes_processed / elapsed_time  # bytes per second
        remaining_bytes = total_bytes - bytes_processed

        # Estimate remaining time
        estimated_seconds = remaining_bytes / processing_rate
        return estimated_seconds * 1000  # Convert to milliseconds

    def _calculate_overall_speed(self) -> float:
        """Calculate overall processing speed in MB/s.

        Returns:
            Overall processing speed
        """
        if self.total_processed_bytes == 0:
            return 0.0

        total_duration_seconds = (time.time() - self.operation_start_time)
        if total_duration_seconds <= 0:
            return 0.0

        mb_processed = self.total_processed_bytes / (1024 * 1024)
        return mb_processed / total_duration_seconds