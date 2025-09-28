"""Progress tracking system for conversion pipeline."""

import time
from contextlib import contextmanager
from typing import List, Optional, Tuple

import click


class ConversionProgressTracker:
    """Tracks and displays conversion progress with detailed feedback."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.phases = [
            ("Validating input file", 5, "📋"),
            ("Preparing output directory", 3, "📁"),
            ("Parsing Swagger specification", 15, "📖"),
            ("Normalizing API structure", 20, "🔧"),
            ("Setting up database storage", 15, "💾"),
            ("Building search index", 25, "🔍"),
            ("Generating MCP server configuration", 10, "⚙️"),
            ("Creating deployment package", 10, "📦"),
            ("Validating generated server", 7, "✅"),
        ]
        self.current_phase = 0
        self.phase_start_time = None
        self.total_start_time = time.time()
        self.phase_durations = []

    @contextmanager
    def track_phase(self, phase_name: str):
        """Context manager for tracking individual phases with progress display."""
        phase_info = None
        icon = "📋"

        # Find phase info
        for name, weight, phase_icon in self.phases:
            if phase_name in name or name in phase_name:
                phase_info = (name, weight, phase_icon)
                icon = phase_icon
                break

        if not phase_info:
            # Unknown phase
            phase_info = (phase_name, 5, icon)

        self.phase_start_time = time.time()

        # Show phase start
        self._display_phase_start(phase_info[0], icon)

        try:
            yield
            duration = time.time() - self.phase_start_time
            self.phase_durations.append(duration)
            self._display_phase_complete(phase_info[0], icon, duration)
            self.current_phase += 1

        except Exception as e:
            duration = time.time() - self.phase_start_time
            self._display_phase_error(phase_info[0], icon, duration, str(e))
            raise

    def _display_phase_start(self, phase_name: str, icon: str):
        """Display phase start with progress information."""
        if self.current_phase == 0:
            click.echo("🚀 Starting Swagger to MCP Server conversion...")
            click.echo()

        # Calculate overall progress
        total_phases = len(self.phases)
        progress_percent = (self.current_phase / total_phases) * 100

        # Show current phase
        click.echo(f"{icon} {phase_name}...")

        if self.verbose:
            click.echo(
                f"   Progress: {self.current_phase}/{total_phases} phases "
                f"({progress_percent:.0f}%) completed"
            )

            # Show estimated time remaining
            if self.current_phase > 0:
                avg_phase_time = sum(self.phase_durations) / len(self.phase_durations)
                remaining_phases = total_phases - self.current_phase
                estimated_remaining = avg_phase_time * remaining_phases
                click.echo(
                    f"   Estimated time remaining: {self._format_duration(estimated_remaining)}"
                )

    def _display_phase_complete(self, phase_name: str, icon: str, duration: float):
        """Display phase completion with timing information."""
        if self.verbose:
            click.echo(
                f"   ✅ {phase_name} completed ({self._format_duration(duration)})"
            )
        else:
            # Simple progress indicator
            click.echo(f"   ✅ Complete ({self._format_duration(duration)})")

        # Show overall progress bar for non-verbose mode
        if not self.verbose:
            self._show_progress_bar()

        click.echo()

    def _display_phase_error(
        self, phase_name: str, icon: str, duration: float, error: str
    ):
        """Display phase error with diagnostic information."""
        click.echo(f"   ❌ {phase_name} failed after {self._format_duration(duration)}")

        if self.verbose:
            click.echo(f"   Error: {error}")

        click.echo()

    def _show_progress_bar(self):
        """Show simple ASCII progress bar."""
        total_phases = len(self.phases)
        completed = min(self.current_phase + 1, total_phases)
        progress_percent = (completed / total_phases) * 100

        bar_width = 30
        filled_width = int(bar_width * completed / total_phases)

        bar = "█" * filled_width + "░" * (bar_width - filled_width)
        click.echo(f"   Progress: [{bar}] {progress_percent:.0f}%")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 1:
            return f"{seconds * 1000:.0f}ms"
        elif seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        else:
            return f"{seconds / 3600:.1f}h"

    def show_final_summary(
        self, success: bool = True, total_duration: Optional[float] = None
    ):
        """Show final conversion summary."""
        if total_duration is None:
            total_duration = time.time() - self.total_start_time

        click.echo("=" * 60)

        if success:
            click.echo("🎉 Conversion completed successfully!")
        else:
            click.echo("❌ Conversion failed")

        click.echo(f"⏱️  Total time: {self._format_duration(total_duration)}")

        if success and self.verbose and self.phase_durations:
            click.echo()
            click.echo("📊 Phase breakdown:")
            phase_names = [
                phase[0] for phase in self.phases[: len(self.phase_durations)]
            ]
            for i, (name, duration) in enumerate(
                zip(phase_names, self.phase_durations)
            ):
                percentage = (duration / total_duration) * 100
                click.echo(
                    f"   {i+1}. {name}: {self._format_duration(duration)} ({percentage:.1f}%)"
                )

        click.echo("=" * 60)

    def estimate_remaining_time(self) -> Optional[str]:
        """Estimate remaining conversion time."""
        if self.current_phase == 0 or not self.phase_durations:
            return None

        # Calculate average time per phase
        avg_phase_time = sum(self.phase_durations) / len(self.phase_durations)

        # Weight remaining phases
        remaining_weight = sum(phase[1] for phase in self.phases[self.current_phase :])
        completed_weight = sum(phase[1] for phase in self.phases[: self.current_phase])

        if completed_weight > 0:
            # Adjust average time based on phase weights
            total_weight = sum(phase[1] for phase in self.phases)
            weight_factor = remaining_weight / completed_weight
            estimated_remaining = (
                avg_phase_time * len(self.phases[self.current_phase :]) * weight_factor
            )

            return self._format_duration(estimated_remaining)

        return None

    def get_progress_percentage(self) -> float:
        """Get current progress as percentage."""
        if not self.phases:
            return 0.0

        return (self.current_phase / len(self.phases)) * 100

    def get_phase_info(self) -> dict:
        """Get current phase information."""
        if self.current_phase < len(self.phases):
            current_phase_info = self.phases[self.current_phase]
            return {
                "current_phase": self.current_phase + 1,
                "total_phases": len(self.phases),
                "phase_name": current_phase_info[0],
                "phase_icon": current_phase_info[2],
                "progress_percentage": self.get_progress_percentage(),
                "estimated_remaining": self.estimate_remaining_time(),
            }
        else:
            return {
                "current_phase": len(self.phases),
                "total_phases": len(self.phases),
                "phase_name": "Completed",
                "phase_icon": "🎉",
                "progress_percentage": 100.0,
                "estimated_remaining": None,
            }


class ConversionTimer:
    """Simple timer for measuring conversion performance."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.phase_times = {}
        self.current_phase = None

    def start(self):
        """Start the overall timer."""
        self.start_time = time.time()

    def start_phase(self, phase_name: str):
        """Start timing a specific phase."""
        self.current_phase = phase_name
        self.phase_times[phase_name] = {"start": time.time()}

    def end_phase(self, phase_name: str = None):
        """End timing for a specific phase."""
        if phase_name is None:
            phase_name = self.current_phase

        if phase_name and phase_name in self.phase_times:
            self.phase_times[phase_name]["end"] = time.time()
            self.phase_times[phase_name]["duration"] = (
                self.phase_times[phase_name]["end"]
                - self.phase_times[phase_name]["start"]
            )

    def end(self):
        """End the overall timer."""
        self.end_time = time.time()

    def get_total_duration(self) -> float:
        """Get total conversion duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        else:
            return 0.0

    def get_phase_duration(self, phase_name: str) -> Optional[float]:
        """Get duration for a specific phase."""
        if phase_name in self.phase_times:
            return self.phase_times[phase_name].get("duration")
        return None

    def get_performance_report(self) -> dict:
        """Get comprehensive performance report."""
        total_duration = self.get_total_duration()

        report = {
            "total_duration": total_duration,
            "phases": {},
            "performance_metrics": {
                "conversion_rate": "endpoints_per_second",  # Will be calculated by pipeline
                "throughput": "mb_per_second",  # Will be calculated by pipeline
                "efficiency": "success_rate",  # Will be calculated by pipeline
            },
        }

        for phase_name, timing in self.phase_times.items():
            if "duration" in timing:
                report["phases"][phase_name] = {
                    "duration": timing["duration"],
                    "percentage": (timing["duration"] / total_duration * 100)
                    if total_duration > 0
                    else 0,
                }

        return report
