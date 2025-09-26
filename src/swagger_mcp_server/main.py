"""Main CLI entry point for the Swagger MCP Server Converter.

This module provides the command-line interface for converting Swagger/OpenAPI
specifications into MCP servers with intelligent search capabilities.
"""

import sys
import os
import traceback
import time
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path

import click
import structlog

from . import __version__

# Import server management components
try:
    from .management import MCPServerManager, ServerError
except ImportError:
    # Fall back if dependencies not available
    MCPServerManager = None
    ServerError = None


# Configure structured logging
logger = structlog.get_logger()


class CLIError(Exception):
    """Base CLI error with user-friendly messages."""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        self.message = message
        self.suggestion = suggestion
        super().__init__(message)


class CLIContext:
    """Global CLI context management."""

    def __init__(
        self,
        verbose: bool = False,
        quiet: bool = False,
        config_file: Optional[str] = None,
    ):
        self.verbose = verbose
        self.quiet = quiet
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file and environment."""
        config = {}

        # Load from config file if specified
        if self.config_file and os.path.exists(self.config_file):
            config.update(self._load_config_file(self.config_file))

        # Override with environment variables
        env_overrides = self._extract_env_config()
        config.update(env_overrides)

        return config

    def _load_config_file(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            import yaml

            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            raise CLIError(
                "PyYAML not installed",
                "Install PyYAML to use configuration files: pip install pyyaml",
            )
        except Exception as e:
            raise CLIError(
                f"Invalid configuration file: {e}",
                "Check YAML syntax and file format",
            )

    def _extract_env_config(self) -> Dict[str, Any]:
        """Extract configuration from environment variables."""
        config = {}

        # Map environment variables to config keys
        env_mappings = {
            "SWAGGER_MCP_PORT": "server.port",
            "SWAGGER_MCP_HOST": "server.host",
            "SWAGGER_MCP_VERBOSE": "logging.verbose",
            "SWAGGER_MCP_OUTPUT_DIR": "output.directory",
        }

        for env_var, config_key in env_mappings.items():
            if env_var in os.environ:
                self._set_nested_config(config, config_key, os.environ[env_var])

        return config

    def _set_nested_config(self, config: Dict, key_path: str, value: Any):
        """Set nested configuration value using dot notation."""
        keys = key_path.split(".")
        current = config

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value


def handle_cli_error(error: Exception, ctx: Optional[click.Context] = None):
    """Global CLI error handler."""
    try:
        if isinstance(error, CLIError):
            click.echo(f"Error: {error.message}", err=True)
            if error.suggestion:
                click.echo(f"Suggestion: {error.suggestion}", err=True)
        elif isinstance(error, click.ClickException):
            error.show()
        else:
            verbose = False
            if ctx and ctx.obj:
                verbose = ctx.obj.get("verbose", False)

            if verbose:
                click.echo(f"Unexpected error: {str(error)}", err=True)
                click.echo(traceback.format_exc(), err=True)
            else:
                click.echo(f"Unexpected error: {str(error)}", err=True)
                click.echo(
                    "Run with --verbose for detailed error information", err=True
                )

        sys.exit(1)
    except Exception as handler_error:
        # Fallback if error handler itself fails
        click.echo(f"Critical error in error handler: {handler_error}", err=True)
        sys.exit(1)


@click.group()
@click.version_option(version=__version__, prog_name="swagger-mcp-server")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output with detailed logging",
)
@click.option(
    "--quiet", "-q", is_flag=True, help="Enable quiet mode with minimal output"
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Configuration file path (YAML format)",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool, config: Optional[str]):
    """Universal Swagger → MCP Server Converter

    Transform any Swagger (OpenAPI) JSON file into an MCP server with intelligent
    search and retrieval capabilities for AI agents.

    The converter creates a fully functional MCP server that enables AI agents to:
    - Search and discover API endpoints by functionality
    - Retrieve detailed schema information for request/response structures
    - Generate code examples for API integration
    - Access comprehensive API documentation without context limits

    \b
    Common workflows:
      1. Convert Swagger file to MCP server
      2. Start the MCP server for AI agent connections
      3. Monitor server status and performance
      4. Customize server configuration as needed

    \b
    Examples:
      swagger-mcp-server convert api.json --output ./mcp-server
      swagger-mcp-server serve --port 8080
      swagger-mcp-server status --all
      swagger-mcp-server config show

    For detailed help on any command, use:
      swagger-mcp-server COMMAND --help
    """
    # Validate mutually exclusive options
    if verbose and quiet:
        raise click.BadParameter("Cannot use both --verbose and --quiet options")

    # Initialize global context
    ctx.ensure_object(dict)
    cli_context = CLIContext(verbose=verbose, quiet=quiet, config_file=config)

    ctx.obj["cli_context"] = cli_context
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["config"] = cli_context.config

    # Configure logging based on verbosity
    if verbose:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
        )
    elif quiet:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(40),  # ERROR level
        )


@cli.command()
@click.argument("swagger_file", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output directory for generated MCP server (default: ./mcp-server)",
)
@click.option(
    "--port",
    "-p",
    type=int,
    default=8080,
    help="Default port for the MCP server (default: 8080)",
)
@click.option(
    "--name",
    "-n",
    help="Custom name for the MCP server (default: based on Swagger file)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing output directory without confirmation",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview conversion without generating files",
)
@click.option(
    "--validate-only",
    is_flag=True,
    help="Validate Swagger file without conversion",
)
@click.option(
    "--skip-validation",
    is_flag=True,
    help="Skip generated server validation (faster but less safe)",
)
@click.pass_context
def convert(
    ctx: click.Context,
    swagger_file: str,
    output: Optional[str],
    port: int,
    name: Optional[str],
    force: bool,
    dry_run: bool,
    validate_only: bool,
    skip_validation: bool,
):
    """Convert Swagger file to MCP server.

    Converts an OpenAPI/Swagger JSON file into a fully functional MCP server
    with intelligent search and schema retrieval capabilities.

    The conversion process:
    1. Parses and validates the Swagger/OpenAPI specification
    2. Extracts endpoints, schemas, and documentation
    3. Creates search indexes for efficient API discovery
    4. Generates MCP server code with all required methods
    5. Sets up configuration files and documentation

    \b
    SWAGGER_FILE: Path to the Swagger/OpenAPI JSON file to convert

    \b
    Examples:
      # Basic conversion
      swagger-mcp-server convert api.json

      # Custom output directory and port
      swagger-mcp-server convert api.json --output ./my-mcp-server --port 9000

      # Preview conversion without generating files
      swagger-mcp-server convert api.json --dry-run

      # Validate Swagger file only
      swagger-mcp-server convert api.json --validate-only

      # Force overwrite existing directory
      swagger-mcp-server convert api.json --force

      # Custom server name
      swagger-mcp-server convert api.json --name "MyAPI-Server"
    """
    # Import conversion pipeline at module level to avoid scope issues
    from .conversion import ConversionPipeline, ConversionError

    try:
        cli_context = ctx.obj["cli_context"]

        # Setup conversion options
        conversion_options = {
            "port": port,
            "name": name,
            "force": force,
            "dry_run": dry_run,
            "validate_only": validate_only,
            "skip_validation": skip_validation,
            "verbose": cli_context.verbose,
            "quiet": cli_context.quiet,
        }

        # Initialize conversion pipeline
        pipeline = ConversionPipeline(swagger_file, output, conversion_options)

        # Run the appropriate operation
        if validate_only:
            _run_validate_only(pipeline)
        elif dry_run:
            _run_dry_run(pipeline)
        else:
            _run_full_conversion(pipeline, cli_context)

    except ConversionError as error:
        _handle_conversion_error(error, ctx)
    except Exception as error:
        handle_cli_error(error, ctx)


def _run_validate_only(pipeline):
    """Run validation-only mode."""
    import asyncio

    async def validate():
        await pipeline.validate_swagger_only()

    try:
        asyncio.run(validate())
        click.echo("✅ Swagger file validation successful")
        click.echo("📋 File is ready for conversion")
    except Exception as e:
        click.echo(f"❌ Swagger file validation failed: {str(e)}", err=True)
        sys.exit(1)


def _run_dry_run(pipeline):
    """Run dry-run mode to preview conversion."""
    import asyncio

    async def preview():
        return await pipeline.preview_conversion()

    try:
        preview_data = asyncio.run(preview())
        _display_conversion_preview(preview_data)
    except Exception as e:
        click.echo(f"❌ Conversion preview failed: {str(e)}", err=True)
        sys.exit(1)


def _run_full_conversion(pipeline, cli_context):
    """Run full conversion process."""
    import asyncio

    async def convert():
        return await pipeline.execute_conversion()

    try:
        if not cli_context.quiet:
            click.echo("🚀 Starting Swagger to MCP Server conversion...")
            click.echo()

        result = asyncio.run(convert())
        _display_conversion_success(result, cli_context.quiet)

    except Exception as e:
        click.echo(f"❌ Conversion failed: {str(e)}", err=True)
        sys.exit(1)


def _display_conversion_preview(preview_data: dict):
    """Display conversion preview information."""
    click.echo("🔍 Conversion Preview")
    click.echo("=" * 50)

    # API Information
    api_info = preview_data.get("api_info", {})
    click.echo(f"📊 API: {api_info.get('title', 'Unknown')} v{api_info.get('version', '1.0')}")
    if api_info.get("description"):
        click.echo(f"📝 Description: {api_info['description']}")

    click.echo()

    # Conversion Plan
    plan = preview_data.get("conversion_plan", {})
    click.echo("📋 Conversion Plan:")
    click.echo(f"   • Endpoints to process: {plan.get('endpoints_to_process', 0)}")
    click.echo(f"   • Schemas to process: {plan.get('schemas_to_process', 0)}")
    click.echo(f"   • Estimated duration: {plan.get('estimated_duration', 'Unknown')}")
    click.echo(f"   • Output directory: {plan.get('output_directory', 'Unknown')}")
    click.echo(f"   • Server name: {plan.get('server_name', 'Unknown')}")

    click.echo()

    # Generated Files
    generated_files = preview_data.get("generated_files", [])
    click.echo("📦 Files to be generated:")
    for file_desc in generated_files:
        click.echo(f"   • {file_desc}")

    click.echo()
    click.echo("To proceed with conversion, run without --dry-run")


def _display_conversion_success(result: dict, quiet: bool = False):
    """Display conversion success information."""
    if not quiet:
        click.echo()
        click.echo("🎉 Conversion completed successfully!")
        click.echo("=" * 50)

        # Conversion Summary
        conversion_summary = result.get("report", {}).get("conversion_summary", {})
        click.echo(f"⏱️  Duration: {conversion_summary.get('duration', 'Unknown')}")
        click.echo(f"📁 Output: {conversion_summary.get('output_directory', 'Unknown')}")

        # API Summary
        api_summary = result.get("report", {}).get("api_summary", {})
        click.echo(f"📊 API: {api_summary.get('title', 'Unknown')} v{api_summary.get('version', '1.0')}")
        click.echo(f"🔗 Endpoints: {api_summary.get('endpoints', 0)}")
        click.echo(f"📋 Schemas: {api_summary.get('schemas', 0)}")

        click.echo()

        # Next Steps
        next_steps = result.get("report", {}).get("next_steps", [])
        if next_steps:
            click.echo("🚀 Next steps:")
            for i, step in enumerate(next_steps, 1):
                click.echo(f"   {i}. {step}")

        click.echo()
        click.echo("📖 For detailed usage instructions, see README.md in the output directory")

    else:
        # Quiet mode - just essential info
        output_dir = result.get("output_directory", "Unknown")
        click.echo(f"✅ Conversion complete: {output_dir}")


def _handle_conversion_error(error, ctx):
    """Handle conversion-specific errors."""
    cli_context = ctx.obj.get("cli_context")
    verbose = cli_context.verbose if cli_context else False

    click.echo(f"❌ Conversion failed: {error.message}", err=True)

    if error.details:
        if verbose:
            click.echo("\n📋 Error details:", err=True)
            for key, value in error.details.items():
                if key == "troubleshooting" and isinstance(value, list):
                    click.echo("💡 Troubleshooting suggestions:", err=True)
                    for suggestion in value:
                        click.echo(f"   • {suggestion}", err=True)
                else:
                    click.echo(f"   {key}: {value}", err=True)
        else:
            troubleshooting = error.details.get("troubleshooting", [])
            if troubleshooting:
                click.echo("\n💡 Suggestions:", err=True)
                for suggestion in troubleshooting[:3]:  # Show top 3 suggestions
                    click.echo(f"   • {suggestion}", err=True)
                click.echo("   • Run with --verbose for more details", err=True)

    sys.exit(1)


@cli.command()
@click.option(
    "--port", "-p", type=int, default=8080, help="Port to run MCP server on"
)
@click.option(
    "--host", "-h", default="localhost", help="Host to bind MCP server to"
)
@click.option(
    "--config-file",
    type=click.Path(exists=True),
    help="MCP server configuration file",
)
@click.option(
    "--daemon", "-d", is_flag=True, help="Run server as background daemon"
)
@click.option(
    "--name", "-n", type=str, help="Server instance name"
)
@click.option(
    "--server-dir", type=click.Path(exists=True),
    help="Directory containing generated MCP server (default: current directory)"
)
@click.pass_context
def serve(
    ctx: click.Context,
    port: int,
    host: str,
    config_file: Optional[str],
    daemon: bool,
    name: Optional[str],
    server_dir: Optional[str],
):
    """Start MCP server.

    Starts a previously converted MCP server for AI agent connections.
    The server provides intelligent search and retrieval capabilities
    for the converted Swagger/OpenAPI specification.

    The server exposes three main MCP methods:
    - searchEndpoints: Find API endpoints by keyword/functionality
    - getSchema: Retrieve detailed schema definitions
    - getExample: Generate code examples for API usage

    \b
    Examples:
      # Start server on default port
      swagger-mcp-server serve

      # Custom port and host
      swagger-mcp-server serve --port 9000 --host 0.0.0.0

      # Start with custom configuration
      swagger-mcp-server serve --config-file ./server-config.yaml

      # Run as background daemon
      swagger-mcp-server serve --daemon --name my-api-server

      # Start server from specific directory
      swagger-mcp-server serve --server-dir ./test-mcp-server
    """
    try:
        if MCPServerManager is None:
            click.echo("❌ Server management not available. Install required dependencies:", err=True)
            click.echo("   pip install psutil aiohttp", err=True)
            sys.exit(1)

        cli_context = ctx.obj["cli_context"]

        # Build server configuration
        server_config = {
            "name": name or f"mcp-server-{port}",
            "host": host,
            "port": port,
            "config_file": config_file,
            "working_directory": server_dir or os.getcwd(),
            "api_title": "MCP Server",  # Will be read from actual config
        }

        # Start server
        asyncio.run(_serve_command(server_config, daemon, cli_context))

    except KeyboardInterrupt:
        click.echo("\n🛑 Server startup cancelled")
    except Exception as error:
        _handle_server_error(error, ctx)


@cli.command()
@click.option(
    "--all", "-a", is_flag=True, help="Show status of all MCP servers"
)
@click.option(
    "--server-id", "-s", type=str, help="Show status of specific server by ID"
)
@click.option(
    "--port", "-p", type=int, help="Show status of server on specific port"
)
@click.option(
    "--format",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
    help="Output format for status information",
)
@click.option(
    "--watch", "-w", is_flag=True, help="Continuously monitor server status"
)
@click.pass_context
def status(ctx: click.Context, all: bool, server_id: Optional[str], port: Optional[int], format: str, watch: bool):
    """Show MCP server status.

    Displays status information for running MCP servers including
    performance metrics, connection information, and health status.

    Status information includes:
    - Server process information (PID, uptime, memory usage)
    - Network connectivity (host, port, active connections)
    - Performance metrics (requests/sec, response times)
    - Health check results (connectivity, response time, MCP protocol)

    \b
    Examples:
      # Show status of all servers
      swagger-mcp-server status --all

      # Show specific server by ID
      swagger-mcp-server status --server-id mcp-server-8080-123456

      # Check specific port
      swagger-mcp-server status --port 9000

      # JSON output format
      swagger-mcp-server status --all --format json

      # Continuous monitoring
      swagger-mcp-server status --all --watch
    """
    try:
        if MCPServerManager is None:
            click.echo("❌ Server management not available. Install required dependencies:", err=True)
            click.echo("   pip install psutil aiohttp", err=True)
            sys.exit(1)

        cli_context = ctx.obj["cli_context"]

        # Run status command
        asyncio.run(_status_command(all, server_id, port, format, watch, cli_context))

    except KeyboardInterrupt:
        click.echo("\n🛑 Status monitoring stopped")
    except Exception as error:
        _handle_server_error(error, ctx)


@cli.command()
@click.argument("server_id", required=False)
@click.option(
    "--port", "-p", type=int, help="Stop server by port number"
)
@click.option(
    "--all", "-a", is_flag=True, help="Stop all running servers"
)
@click.option(
    "--force", "-f", is_flag=True, help="Force immediate shutdown"
)
@click.option(
    "--timeout", "-t", type=int, default=30, help="Graceful shutdown timeout in seconds"
)
@click.pass_context
def stop(ctx: click.Context, server_id: Optional[str], port: Optional[int], all: bool, force: bool, timeout: int):
    """Stop running MCP server(s).

    Gracefully shuts down MCP servers with proper cleanup and connection termination.
    Supports stopping by server ID, port number, or all servers at once.

    \b
    Examples:
      # Stop specific server by ID
      swagger-mcp-server stop mcp-server-8080-123456

      # Stop server by port
      swagger-mcp-server stop --port 8080

      # Stop all servers
      swagger-mcp-server stop --all

      # Force immediate shutdown
      swagger-mcp-server stop --server-id my-server --force

      # Custom timeout for graceful shutdown
      swagger-mcp-server stop --all --timeout 60
    """
    try:
        if MCPServerManager is None:
            click.echo("❌ Server management not available. Install required dependencies:", err=True)
            click.echo("   pip install psutil aiohttp", err=True)
            sys.exit(1)

        if not any([server_id, port, all]):
            click.echo("❌ Must specify server to stop: --server-id, --port, or --all", err=True)
            sys.exit(1)

        cli_context = ctx.obj["cli_context"]

        # Run stop command
        asyncio.run(_stop_command(server_id, port, all, force, timeout, cli_context))

    except KeyboardInterrupt:
        click.echo("\n🛑 Stop operation cancelled")
    except Exception as error:
        _handle_server_error(error, ctx)


@cli.command()
@click.argument("action", type=click.Choice(["show", "set", "reset", "validate", "init", "env-help"]))
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.option(
    "--template", "-t",
    type=click.Choice(["development", "staging", "production", "container"]),
    default="development",
    help="Configuration template for initialization"
)
@click.option(
    "--file", "-f",
    type=click.Path(),
    help="Configuration file to use (default: auto-detect)",
)
@click.option(
    "--force", is_flag=True,
    help="Force overwrite existing configuration file"
)
@click.option(
    "--format",
    type=click.Choice(["yaml", "json", "table"]),
    default="table",
    help="Output format for show command"
)
@click.pass_context
def config(
    ctx: click.Context,
    action: str,
    key: Optional[str],
    value: Optional[str],
    template: str,
    file: Optional[str],
    force: bool,
    format: str,
):
    """Manage configuration settings.

    Comprehensive configuration management for the MCP server with support for
    templates, environment variable overrides, and validation.

    Configuration hierarchy (highest to lowest priority):
    1. Command-line options
    2. Environment variables (SWAGGER_MCP_*)
    3. Local project configuration file
    4. Global user configuration file
    5. Built-in defaults

    \b
    Available configuration sections:
      server.*            - Server host, port, connections, SSL settings
      database.*          - Database path, pooling, backup settings
      search.*            - Search engine, indexing, performance settings
      logging.*           - Log level, format, file rotation settings
      features.*          - Feature flags for metrics, health checks, rate limiting

    \b
    Templates available:
      development         - Local development with debugging and relaxed settings
      staging             - Testing environment balancing production settings with debugging
      production          - Production deployment with security and performance optimization
      container           - Container deployment optimized for Docker/Kubernetes

    \b
    Examples:
      # Initialize configuration with development template
      swagger-mcp-server config init --template development

      # Show all configuration
      swagger-mcp-server config show

      # Show specific setting
      swagger-mcp-server config show server.port

      # Set configuration value
      swagger-mcp-server config set server.port 9000

      # Reset to template defaults
      swagger-mcp-server config reset

      # Validate configuration
      swagger-mcp-server config validate

      # Show environment variable help
      swagger-mcp-server config env-help
    """
    try:
        # Import configuration management system
        from .config import ConfigurationManager, ConfigurationError

        # Initialize configuration manager
        config_manager = ConfigurationManager(config_dir=None)

        # Execute action
        if action == "show":
            _config_show(config_manager, key, format)
        elif action == "set":
            _config_set(config_manager, key, value, file)
        elif action == "reset":
            _config_reset(config_manager, template, file)
        elif action == "validate":
            _config_validate(config_manager, file)
        elif action == "init":
            _config_init(config_manager, template, file, force)
        elif action == "env-help":
            _config_env_help(config_manager)

    except ConfigurationError as error:
        click.echo(f"❌ Configuration error: {error.message}", err=True)
        if error.details:
            for key, value in error.details.items():
                if key == "validation_errors" and isinstance(value, list):
                    click.echo("   Validation errors:", err=True)
                    for err in value:
                        click.echo(f"   • {err}", err=True)
                elif key == "suggestion":
                    click.echo(f"   💡 {value}", err=True)
        sys.exit(1)
    except Exception as error:
        handle_cli_error(error, ctx)


# Command aliases for improved user experience
@cli.command(hidden=True)  # Hidden from main help
@click.pass_context
def help(ctx: click.Context):
    """Show help information (alias for --help)."""
    click.echo(ctx.parent.get_help())


# Setup global error handling
def setup_error_handling():
    """Setup global CLI error handling."""

    def exception_handler(exc_type, exc_value, exc_traceback):
        try:
            current_ctx = click.get_current_context(silent=True)
            handle_cli_error(exc_value, current_ctx)
        except RuntimeError:
            # No Click context available, handle without context
            handle_cli_error(exc_value, None)

    sys.excepthook = exception_handler


# Initialize error handling when module is imported
setup_error_handling()


# Server management helper functions

async def _serve_command(server_config: Dict[str, Any], daemon: bool, cli_context: CLIContext):
    """Execute serve command asynchronously."""
    manager = MCPServerManager()

    try:
        if not cli_context.quiet:
            click.echo(f"🚀 Starting MCP server on {server_config['host']}:{server_config['port']}")
            if daemon:
                click.echo("🔄 Running in daemon mode")

        # Start server
        result = await manager.start_server(server_config, daemon=daemon)

        if daemon:
            click.echo(f"✅ MCP server started successfully")
            click.echo(f"   Server ID: {result['server_id']}")
            click.echo(f"   Process ID: {result['process_id']}")
            click.echo(f"   URL: http://{result['host']}:{result['port']}")
            click.echo(f"   Use 'swagger-mcp-server status' to monitor")
        else:
            click.echo(f"✅ MCP server running on {result['host']}:{result['port']}")
            click.echo("   Press Ctrl+C to stop server")

            # For interactive mode, we would block here
            # For now, just show success message
            click.echo("🚧 Interactive mode implementation coming soon")

    except ServerError as e:
        click.echo(f"❌ {e.message}", err=True)
        if e.suggestion:
            click.echo(f"💡 {e.suggestion}", err=True)
        raise


async def _status_command(all_servers: bool, server_id: Optional[str], port: Optional[int],
                         output_format: str, watch: bool, cli_context: CLIContext):
    """Execute status command asynchronously."""
    manager = MCPServerManager()

    try:
        if watch:
            # Continuous monitoring
            await _monitor_servers_continuously(manager, all_servers, server_id, port, output_format)
        else:
            # One-time status check
            await _get_and_display_status(manager, all_servers, server_id, port, output_format)

    except ServerError as e:
        click.echo(f"❌ {e.message}", err=True)
        if e.suggestion:
            click.echo(f"💡 {e.suggestion}", err=True)
        raise


async def _stop_command(server_id: Optional[str], port: Optional[int], all_servers: bool,
                       force: bool, timeout: int, cli_context: CLIContext):
    """Execute stop command asynchronously."""
    manager = MCPServerManager()

    try:
        servers_to_stop = []

        if all_servers:
            # Get all servers
            all_status = await manager.get_all_servers_status()
            servers_to_stop = [status["server"]["id"] for status in all_status]

            if not servers_to_stop:
                click.echo("ℹ️  No running servers found")
                return

        elif port:
            # Find server by port
            all_status = await manager.get_all_servers_status()
            for status in all_status:
                if status["server"]["port"] == port:
                    servers_to_stop.append(status["server"]["id"])
                    break

            if not servers_to_stop:
                click.echo(f"❌ No server found on port {port}", err=True)
                return

        elif server_id:
            servers_to_stop = [server_id]

        # Stop servers
        results = []
        for sid in servers_to_stop:
            try:
                if not cli_context.quiet:
                    method = "Force stopping" if force else "Stopping"
                    click.echo(f"🛑 {method} server: {sid}")

                result = await manager.stop_server(sid, force=force, timeout=timeout)
                results.append((sid, result, None))

                click.echo(f"✅ Server stopped: {sid} ({result['shutdown_time']:.1f}s)")

            except Exception as e:
                results.append((sid, None, str(e)))
                click.echo(f"❌ Failed to stop {sid}: {e}", err=True)

        # Summary
        successful = len([r for r in results if r[1] is not None])
        total = len(results)

        if successful == total:
            click.echo(f"✅ Successfully stopped {successful} server(s)")
        else:
            click.echo(f"⚠️  Stopped {successful}/{total} servers")

    except ServerError as e:
        click.echo(f"❌ {e.message}", err=True)
        if e.suggestion:
            click.echo(f"💡 {e.suggestion}", err=True)
        raise


async def _get_and_display_status(manager: MCPServerManager, all_servers: bool,
                                 server_id: Optional[str], port: Optional[int], output_format: str):
    """Get and display server status."""
    if server_id:
        # Get specific server status
        status_data = await manager.get_server_status(server_id)
        status_list = [status_data]
    elif port:
        # Find server by port
        all_status = await manager.get_all_servers_status()
        status_list = [s for s in all_status if s.get("server", {}).get("port") == port]

        if not status_list:
            click.echo(f"❌ No server found on port {port}", err=True)
            return
    else:
        # Get all servers or default behavior
        status_list = await manager.get_all_servers_status()

    if not status_list:
        click.echo("ℹ️  No running servers found")
        return

    # Display status
    if output_format == "json":
        import json
        click.echo(json.dumps({
            "timestamp": time.time(),
            "servers": status_list
        }, indent=2))
    elif output_format == "yaml":
        try:
            import yaml
            click.echo(yaml.dump({
                "timestamp": time.time(),
                "servers": status_list
            }, default_flow_style=False))
        except ImportError:
            click.echo("❌ PyYAML not installed. Use 'pip install pyyaml' for YAML output.", err=True)
            return
    else:
        # Table format
        _display_status_table(status_list)


async def _monitor_servers_continuously(manager: MCPServerManager, all_servers: bool,
                                       server_id: Optional[str], port: Optional[int], output_format: str):
    """Monitor servers continuously."""
    click.echo("🔄 Monitoring server status (Press Ctrl+C to stop)")
    click.echo("=" * 60)

    try:
        while True:
            # Clear screen for better readability
            if output_format == "table":
                click.clear()
                click.echo("🔄 MCP Server Status Monitor")
                click.echo(f"📅 Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                click.echo("=" * 60)

            await _get_and_display_status(manager, all_servers, server_id, port, output_format)

            # Wait before next update
            await asyncio.sleep(5)

    except KeyboardInterrupt:
        click.echo("\n🛑 Monitoring stopped")


def _display_status_table(status_list: List[Dict[str, Any]]):
    """Display status in table format."""
    if not status_list:
        click.echo("ℹ️  No servers to display")
        return

    click.echo(f"📊 MCP Server Status - {len(status_list)} server(s)")
    click.echo("=" * 80)

    for status in status_list:
        server = status.get("server", {})
        health = status.get("health", {})
        metrics = status.get("metrics", {})
        process_metrics = metrics.get("process", {})

        # Server identification
        click.echo(f"🖥️  Server: {server.get('name', 'Unknown')} (ID: {server.get('id', 'Unknown')})")

        # Status with emoji
        overall_health = health.get("overall_level", "unknown")
        status_emoji = {
            "healthy": "🟢",
            "warning": "🟡",
            "critical": "🔴",
            "unknown": "⚪"
        }.get(overall_health, "⚪")

        click.echo(f"   Status: {status_emoji} {overall_health}")

        # Connection info
        click.echo(f"   Address: {server.get('host')}:{server.get('port')}")
        click.echo(f"   PID: {server.get('pid')} | Uptime: {_format_uptime(status.get('uptime', 0))}")

        # Performance metrics
        cpu_percent = process_metrics.get("cpu_percent", 0)
        memory_mb = process_metrics.get("memory_mb", 0)
        connections = process_metrics.get("connections", 0)

        click.echo(f"   Resources: CPU {cpu_percent:.1f}% | Memory {memory_mb:.1f}MB | Connections {connections}")

        # Health issues
        issues = health.get("issues", [])
        if issues:
            click.echo("   ⚠️  Issues:")
            for issue in issues[:3]:  # Show up to 3 issues
                click.echo(f"      - {issue}")

        click.echo("-" * 40)


def _format_uptime(uptime_seconds: float) -> str:
    """Format uptime in human-readable format."""
    if uptime_seconds < 60:
        return f"{uptime_seconds:.0f}s"
    elif uptime_seconds < 3600:
        return f"{uptime_seconds/60:.0f}m"
    elif uptime_seconds < 86400:
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
    else:
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        return f"{days}d {hours}h"


def _handle_server_error(error: Exception, ctx: Optional[click.Context]):
    """Handle server management errors."""
    if isinstance(error, ServerError):
        click.echo(f"❌ {error.message}", err=True)
        if error.suggestion:
            click.echo(f"💡 {error.suggestion}", err=True)
        if error.details and ctx and ctx.obj.get("cli_context", {}).get("verbose"):
            click.echo("\n📋 Error details:", err=True)
            for key, value in error.details.items():
                click.echo(f"   {key}: {value}", err=True)
    else:
        handle_cli_error(error, ctx)


@cli.command()
@click.option("--force", "-f", is_flag=True,
              help="Force setup even if already initialized")
@click.option("--verify", "-v", is_flag=True,
              help="Verify installation without setup")
@click.option("--uninstall", is_flag=True,
              help="Uninstall and clean up all files")
@click.option("--preserve-config", is_flag=True,
              help="Preserve configuration during uninstall")
@click.option("--preserve-data", is_flag=True,
              help="Preserve user data during uninstall")
@click.pass_context
def setup(ctx: click.Context, force: bool, verify: bool, uninstall: bool,
          preserve_config: bool, preserve_data: bool):
    """Setup and installation management.

    Initialize the swagger-mcp-server environment, create necessary directories,
    and configure the system for first use. This command handles all setup
    requirements automatically.

    The setup process includes:
    - System compatibility verification
    - Directory structure creation
    - Configuration initialization
    - Database and search index setup
    - Installation verification

    \b
    Examples:
      # Initial setup
      swagger-mcp-server setup

      # Force re-setup (overwrites existing configuration)
      swagger-mcp-server setup --force

      # Verify existing installation
      swagger-mcp-server setup --verify

      # Clean uninstall
      swagger-mcp-server setup --uninstall

      # Uninstall but preserve configuration
      swagger-mcp-server setup --uninstall --preserve-config
    """
    try:
        # Import installation components
        from .installation import (
            InstallationManager,
            InstallationError,
            UninstallationManager,
            UninstallationError
        )

        if uninstall:
            asyncio.run(_handle_uninstall(preserve_config, preserve_data))
            return

        if verify:
            asyncio.run(_handle_verification())
            return

        # Perform setup
        asyncio.run(_handle_setup(force))

    except (InstallationError, UninstallationError) as e:
        _handle_installation_error(e, ctx)
    except Exception as e:
        handle_cli_error(e, ctx)


async def _handle_setup(force: bool):
    """Handle setup process."""
    from .installation import InstallationManager

    manager = InstallationManager()

    click.echo("🚀 Starting swagger-mcp-server setup...")

    # Check if already setup
    if manager.is_already_setup() and not force:
        click.echo("✅ System is already set up")
        click.echo("   Use --force to re-initialize or --verify to check installation")
        return

    # Perform setup steps
    result = await manager.perform_setup(force)

    # Display results
    click.echo("\n✅ Setup completed successfully!")
    click.echo("\nCompleted steps:")
    for step in result["steps_completed"]:
        click.echo(f"   ✓ {step}")

    if result["warnings"]:
        click.echo("\n⚠️  Warnings:")
        for warning in result["warnings"]:
            click.echo(f"   • {warning}")

    # Next steps guidance
    click.echo("\n🎉 Ready to use swagger-mcp-server!")
    click.echo("Next steps:")
    click.echo("   1. Convert a Swagger file: swagger-mcp-server convert api.json")
    click.echo("   2. Start MCP server: swagger-mcp-server serve")
    click.echo("   3. Check status: swagger-mcp-server status")


async def _handle_verification():
    """Handle installation verification."""
    from .installation import InstallationManager

    manager = InstallationManager()

    click.echo("🔍 Verifying swagger-mcp-server installation...")

    verification_result = await manager.verify_installation()

    if verification_result["status"] == "success":
        click.echo("✅ Installation verification successful!")

        # Display system information
        click.echo("\n📋 System Information:")
        sys_info = verification_result["system_info"]
        click.echo(f"   Platform: {sys_info['platform']}")
        click.echo(f"   Python: {sys_info['python_version']}")
        click.echo(f"   Installation: {sys_info['install_path']}")

        # Display component status
        click.echo("\n🧩 Component Status:")
        components = verification_result["components"]
        for component, status in components.items():
            status_emoji = "✅" if status["working"] else "❌"
            click.echo(f"   {status_emoji} {component}: {status['message']}")

        if verification_result.get("warnings"):
            click.echo("\n⚠️  Warnings:")
            for warning in verification_result["warnings"]:
                click.echo(f"   • {warning}")

    else:
        click.echo("❌ Installation verification failed!")
        click.echo("\nIssues found:")
        for issue in verification_result.get("issues", []):
            click.echo(f"   • {issue}")

        click.echo("\nTry running: swagger-mcp-server setup --force")


async def _handle_uninstall(preserve_config: bool, preserve_data: bool):
    """Handle uninstallation process."""
    from .installation import UninstallationManager

    click.echo("🗑️  Starting swagger-mcp-server uninstallation...")

    # Show preview of what will be removed
    uninstaller = UninstallationManager()
    preview = await uninstaller.get_uninstall_preview(preserve_config, preserve_data)

    if preview["will_remove"]:
        click.echo("\n📋 Will remove:")
        for item in preview["will_remove"]:
            click.echo(f"   • {item}")

    if preview["will_preserve"]:
        click.echo("\n💾 Will preserve:")
        for item in preview["will_preserve"]:
            click.echo(f"   • {item}")

    if preview["warnings"]:
        click.echo("\n⚠️  Warnings:")
        for warning in preview["warnings"]:
            click.echo(f"   • {warning}")

    # Confirm uninstallation
    if not click.confirm("\nProceed with uninstallation?"):
        click.echo("Uninstallation cancelled")
        return

    try:
        result = await uninstaller.perform_uninstallation(preserve_config, preserve_data)

        click.echo("✅ Uninstallation completed!")

        if result["removed_items"]:
            click.echo("\nRemoved items:")
            for item in result["removed_items"]:
                click.echo(f"   ✓ {item}")

        if result["preserved_items"]:
            click.echo("\nPreserved items:")
            for item in result["preserved_items"]:
                click.echo(f"   📁 {item}")

        if result["warnings"]:
            click.echo("\n⚠️  Warnings:")
            for warning in result["warnings"]:
                click.echo(f"   • {warning}")

    except Exception as e:
        click.echo(f"❌ Uninstallation encountered issues: {str(e)}")


def _handle_installation_error(error, ctx: Optional[click.Context]):
    """Handle installation-specific errors."""
    cli_context = ctx.obj.get("cli_context") if ctx and ctx.obj else None
    verbose = cli_context.verbose if cli_context else False

    click.echo(f"❌ Installation error: {error.message}", err=True)

    if error.details:
        if verbose:
            click.echo("\n📋 Error details:", err=True)
            for key, value in error.details.items():
                if key == "issues" and isinstance(value, list):
                    click.echo("   Issues:", err=True)
                    for issue in value:
                        click.echo(f"   • {issue}", err=True)
                elif key == "warnings" and isinstance(value, list):
                    click.echo("   Warnings:", err=True)
                    for warning in value:
                        click.echo(f"   • {warning}", err=True)
                else:
                    click.echo(f"   {key}: {value}", err=True)
        else:
            issues = error.details.get("issues", [])
            if issues:
                click.echo("\n💡 Issues:", err=True)
                for issue in issues[:3]:  # Show top 3 issues
                    click.echo(f"   • {issue}", err=True)
                if len(issues) > 3:
                    click.echo("   • Run with --verbose for more details", err=True)

    sys.exit(1)


# Configuration command helper functions

def _config_show(config_manager, key: Optional[str], format: str):
    """Show configuration values."""
    import asyncio

    async def show_config():
        try:
            config = await config_manager.load_configuration()

            if key:
                # Show specific key
                value = config_manager.env_extractor.get_nested_config_value(config, key)
                if value is None:
                    click.echo(f"❌ Configuration key '{key}' not found", err=True)
                    return

                if format == "json":
                    import json
                    click.echo(json.dumps({key: value}, indent=2))
                elif format == "yaml":
                    try:
                        import yaml
                        click.echo(yaml.dump({key: value}, default_flow_style=False))
                    except ImportError:
                        click.echo(f"{key}: {value}")
                else:
                    click.echo(f"{key}: {value}")
            else:
                # Show all configuration
                if format == "json":
                    import json
                    click.echo(json.dumps(config, indent=2))
                elif format == "yaml":
                    try:
                        import yaml
                        click.echo(yaml.dump(config, default_flow_style=False))
                    except ImportError:
                        _config_show_table(config)
                else:
                    _config_show_table(config)

        except Exception as e:
            click.echo(f"❌ Failed to load configuration: {str(e)}", err=True)

    asyncio.run(show_config())


def _config_show_table(config: Dict[str, Any], prefix: str = ""):
    """Display configuration in table format."""
    for key, value in config.items():
        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            click.echo(f"\n[{full_key}]")
            _config_show_table(value, full_key)
        else:
            click.echo(f"{full_key}: {value}")


def _config_set(config_manager, key: Optional[str], value: Optional[str], file: Optional[str]):
    """Set configuration value."""
    import asyncio

    if not key:
        click.echo("❌ Key is required for set action", err=True)
        return

    if not value:
        click.echo("❌ Value is required for set action", err=True)
        return

    async def set_config():
        try:
            await config_manager.set_configuration_value(key, value, file)
            click.echo(f"✅ Configuration updated: {key} = {value}")
        except Exception as e:
            click.echo(f"❌ Failed to set configuration: {str(e)}", err=True)

    asyncio.run(set_config())


def _config_reset(config_manager, template: str, file: Optional[str]):
    """Reset configuration to template defaults."""
    import asyncio

    async def reset_config():
        try:
            await config_manager.reset_configuration(file, template)
            click.echo(f"✅ Configuration reset to '{template}' template")
        except Exception as e:
            click.echo(f"❌ Failed to reset configuration: {str(e)}", err=True)

    asyncio.run(reset_config())


def _config_validate(config_manager, file: Optional[str]):
    """Validate configuration."""
    import asyncio

    async def validate_config():
        try:
            is_valid, errors, warnings = await config_manager.validate_configuration(file)

            if is_valid:
                click.echo("✅ Configuration is valid")
                if warnings:
                    click.echo("\n⚠️  Warnings:")
                    for warning in warnings:
                        click.echo(f"   • {warning}")
            else:
                click.echo("❌ Configuration validation failed")
                click.echo("\nErrors:")
                for error in errors:
                    click.echo(f"   • {error}")

                if warnings:
                    click.echo("\nWarnings:")
                    for warning in warnings:
                        click.echo(f"   • {warning}")
        except Exception as e:
            click.echo(f"❌ Failed to validate configuration: {str(e)}", err=True)

    asyncio.run(validate_config())


def _config_init(config_manager, template: str, file: Optional[str], force: bool):
    """Initialize configuration with template."""
    import asyncio

    async def init_config():
        try:
            await config_manager.initialize_configuration(template, file, force)
            click.echo(f"✅ Configuration initialized with '{template}' template")

            # Show next steps
            if not file:
                file = config_manager.config_file

            click.echo("\n📋 Next steps:")
            click.echo(f"   1. Review configuration: swagger-mcp-server config show")
            click.echo(f"   2. Customize settings: swagger-mcp-server config set KEY VALUE")
            click.echo(f"   3. Validate configuration: swagger-mcp-server config validate")
            click.echo(f"   4. Configuration file location: {file}")

        except Exception as e:
            click.echo(f"❌ Failed to initialize configuration: {str(e)}", err=True)

    asyncio.run(init_config())


def _config_env_help(config_manager):
    """Show environment variable help."""
    try:
        help_text = config_manager.get_environment_help()
        click.echo(help_text)
    except Exception as e:
        click.echo(f"❌ Failed to get environment help: {str(e)}", err=True)


if __name__ == "__main__":
    cli()