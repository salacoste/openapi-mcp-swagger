"""CLI utility functions and helpers."""

import os
import sys
import time
import subprocess
from typing import Optional, Dict, Any, List
from pathlib import Path

import click


def validate_swagger_file(file_path: str) -> bool:
    """Validate that the file exists and appears to be a valid Swagger file."""
    if not os.path.exists(file_path):
        return False

    # Check file extension
    if not file_path.lower().endswith(('.json', '.yaml', '.yml')):
        return False

    # Basic content validation (full validation happens during conversion)
    try:
        if file_path.lower().endswith('.json'):
            import json
            with open(file_path, 'r') as f:
                data = json.load(f)
        else:
            import yaml
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)

        # Check for OpenAPI/Swagger indicators
        return (
            'swagger' in data or
            'openapi' in data or
            'info' in data or
            'paths' in data
        )
    except Exception:
        return False


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


def check_port_available(port: int, host: str = "localhost") -> bool:
    """Check if a port is available for binding."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            return result != 0
    except Exception:
        return False


def find_free_port(start_port: int = 8080, end_port: int = 8180) -> Optional[int]:
    """Find the next available port in the given range."""
    for port in range(start_port, end_port + 1):
        if check_port_available(port):
            return port
    return None


def confirm_action(message: str, default: bool = False) -> bool:
    """Ask user for confirmation with a yes/no prompt."""
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        response = click.prompt(
            message + suffix,
            default="y" if default else "n",
            show_default=False,
            type=str
        ).lower().strip()

        if response in ('y', 'yes'):
            return True
        elif response in ('n', 'no'):
            return False
        else:
            click.echo("Please answer 'y' or 'n'")


def create_directory_safely(path: str, force: bool = False) -> bool:
    """Create directory with safety checks and user confirmation."""
    path_obj = Path(path)

    if path_obj.exists():
        if not path_obj.is_dir():
            click.echo(f"Error: {path} exists but is not a directory", err=True)
            return False

        if not force and any(path_obj.iterdir()):
            if not confirm_action(
                f"Directory {path} is not empty. Continue anyway?",
                default=False
            ):
                return False

    try:
        path_obj.mkdir(parents=True, exist_ok=True)
        return True
    except OSError as e:
        click.echo(f"Error creating directory {path}: {e}", err=True)
        return False


def get_terminal_width() -> int:
    """Get terminal width for formatting output."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80  # Default width


def print_table(headers: List[str], rows: List[List[str]], max_width: Optional[int] = None):
    """Print a formatted table to the console."""
    if not rows:
        return

    if max_width is None:
        max_width = get_terminal_width()

    # Calculate column widths
    col_widths = [len(header) for header in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Adjust widths if table is too wide
    total_width = sum(col_widths) + len(headers) * 3 - 1
    if total_width > max_width:
        # Proportionally reduce column widths
        reduction_factor = max_width / total_width
        col_widths = [int(w * reduction_factor) for w in col_widths]

    # Print header
    header_row = " | ".join(
        header.ljust(col_widths[i]) for i, header in enumerate(headers)
    )
    click.echo(header_row)
    click.echo("-" * len(header_row))

    # Print rows
    for row in rows:
        formatted_row = " | ".join(
            str(cell).ljust(col_widths[i])[:col_widths[i]]
            for i, cell in enumerate(row)
        )
        click.echo(formatted_row)


def print_status_indicator(
    status: str,
    message: str,
    details: Optional[str] = None,
    color: Optional[str] = None
):
    """Print a status indicator with optional details."""
    status_colors = {
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "info": "blue",
        "working": "cyan"
    }

    # Status icons
    status_icons = {
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
        "info": "ℹ️",
        "working": "🔄"
    }

    icon = status_icons.get(status, "•")
    color = color or status_colors.get(status, "white")

    click.echo(f"{icon} ", nl=False)
    click.secho(message, fg=color)

    if details:
        click.echo(f"   {details}", color="bright_black")


def measure_performance(func):
    """Decorator to measure function execution time."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            return result, execution_time
        except Exception as e:
            execution_time = time.time() - start_time
            raise e
    return wrapper


def get_system_info() -> Dict[str, Any]:
    """Get basic system information for debugging."""
    import platform
    import sys

    return {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": sys.version,
        "executable": sys.executable,
        "working_directory": os.getcwd(),
    }


def check_dependencies() -> Dict[str, bool]:
    """Check if required dependencies are available."""
    dependencies = {
        "click": False,
        "structlog": False,
        "mcp": False,
        "pydantic": False,
        "ijson": False,
        "whoosh": False,
    }

    for dep in dependencies:
        try:
            __import__(dep)
            dependencies[dep] = True
        except ImportError:
            dependencies[dep] = False

    return dependencies


def print_version_info(detailed: bool = False):
    """Print version information and optionally system details."""
    from .. import __version__, __author__

    click.echo(f"swagger-mcp-server version {__version__}")
    click.echo(f"Author: {__author__}")

    if detailed:
        click.echo("\nSystem Information:")
        sys_info = get_system_info()
        for key, value in sys_info.items():
            click.echo(f"  {key}: {value}")

        click.echo("\nDependency Status:")
        deps = check_dependencies()
        for dep, available in deps.items():
            status = "✅ Available" if available else "❌ Missing"
            click.echo(f"  {dep}: {status}")


def safe_file_operation(operation, file_path: str, backup: bool = True) -> bool:
    """Safely perform file operations with optional backup."""
    if backup and os.path.exists(file_path):
        backup_path = f"{file_path}.backup"
        try:
            import shutil
            shutil.copy2(file_path, backup_path)
        except Exception as e:
            click.echo(f"Warning: Could not create backup: {e}", err=True)

    try:
        operation(file_path)
        return True
    except Exception as e:
        click.echo(f"Error during file operation: {e}", err=True)
        # Restore backup if available
        if backup and os.path.exists(f"{file_path}.backup"):
            try:
                import shutil
                shutil.move(f"{file_path}.backup", file_path)
                click.echo("Restored from backup", err=True)
            except Exception:
                pass
        return False


def find_project_root() -> Optional[Path]:
    """Find the project root directory by looking for project markers."""
    current = Path.cwd()
    markers = ["pyproject.toml", "setup.py", ".git", "swagger-mcp.yaml"]

    while current != current.parent:
        if any((current / marker).exists() for marker in markers):
            return current
        current = current.parent

    return None


def get_config_directories() -> Dict[str, Path]:
    """Get standard configuration directories for different platforms."""
    import platform

    home = Path.home()
    system = platform.system()

    if system == "Windows":
        config_dir = home / "AppData" / "Roaming" / "swagger-mcp-server"
        data_dir = home / "AppData" / "Local" / "swagger-mcp-server"
    elif system == "Darwin":  # macOS
        config_dir = home / "Library" / "Application Support" / "swagger-mcp-server"
        data_dir = home / "Library" / "Application Support" / "swagger-mcp-server"
    else:  # Linux and other Unix-like
        config_dir = home / ".config" / "swagger-mcp-server"
        data_dir = home / ".local" / "share" / "swagger-mcp-server"

    return {
        "config": config_dir,
        "data": data_dir,
        "global_config": config_dir / "config.yaml",
        "project_config": Path.cwd() / "swagger-mcp.yaml"
    }


def setup_logging(verbose: bool = False, quiet: bool = False):
    """Setup structured logging with appropriate levels."""
    import structlog
    import logging

    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        format="%(message)s",
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.dev.ConsoleRenderer(colors=True)
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )