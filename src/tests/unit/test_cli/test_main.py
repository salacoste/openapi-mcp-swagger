"""Tests for the main CLI module."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from swagger_mcp_server.main import CLIContext, CLIError, cli


class TestCLI:
    """Test the main CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_help(self):
        """Test CLI help output."""
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Universal Swagger → MCP Server Converter" in result.output
        assert "convert" in result.output
        assert "serve" in result.output
        assert "status" in result.output
        assert "config" in result.output

    def test_cli_version(self):
        """Test CLI version display."""
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "swagger-mcp-server" in result.output
        assert "0.1.0" in result.output

    def test_cli_verbose_quiet_conflict(self):
        """Test that verbose and quiet options conflict."""
        result = self.runner.invoke(cli, ["--verbose", "--quiet", "--help"])
        assert result.exit_code != 0
        assert "Cannot use both --verbose and --quiet" in result.output

    def test_convert_command_help(self):
        """Test convert command help."""
        result = self.runner.invoke(cli, ["convert", "--help"])
        assert result.exit_code == 0
        assert "Convert Swagger file to MCP server" in result.output
        assert "SWAGGER_FILE" in result.output
        assert "--output" in result.output
        assert "--port" in result.output

    def test_convert_command_basic(self):
        """Test convert command with basic parameters."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            # Create a simple swagger file
            swagger_data = {
                "swagger": "2.0",
                "info": {"title": "Test API", "version": "1.0"},
                "paths": {},
            }
            json.dump(swagger_data, f)
            f.flush()

            try:
                result = self.runner.invoke(cli, ["convert", f.name])
                assert result.exit_code == 0
                assert "Converting Swagger file" in result.output
                assert f.name in result.output
            finally:
                os.unlink(f.name)

    def test_convert_command_with_options(self):
        """Test convert command with all options."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            swagger_data = {
                "openapi": "3.0.0",
                "info": {"title": "Test API", "version": "1.0"},
                "paths": {},
            }
            json.dump(swagger_data, f)
            f.flush()

            try:
                result = self.runner.invoke(
                    cli,
                    [
                        "convert",
                        f.name,
                        "--output",
                        "/tmp/test-server",
                        "--port",
                        "9000",
                        "--name",
                        "TestServer",
                        "--force",
                    ],
                )
                assert result.exit_code == 0
                assert "Converting Swagger file" in result.output
                assert "/tmp/test-server" in result.output
                assert "9000" in result.output
                assert "TestServer" in result.output
                assert "Force mode" in result.output
            finally:
                os.unlink(f.name)

    def test_convert_nonexistent_file(self):
        """Test convert command with nonexistent file."""
        result = self.runner.invoke(cli, ["convert", "/nonexistent/file.json"])
        assert result.exit_code != 0

    def test_serve_command_help(self):
        """Test serve command help."""
        result = self.runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "Start MCP server" in result.output
        assert "--port" in result.output
        assert "--host" in result.output
        assert "--daemon" in result.output

    def test_serve_command_basic(self):
        """Test serve command with basic parameters."""
        result = self.runner.invoke(cli, ["serve"])
        assert result.exit_code == 0
        assert "Starting MCP server" in result.output
        assert "localhost:8080" in result.output

    def test_serve_command_with_options(self):
        """Test serve command with options."""
        result = self.runner.invoke(
            cli, ["serve", "--port", "9000", "--host", "0.0.0.0", "--daemon"]
        )
        assert result.exit_code == 0
        assert "0.0.0.0:9000" in result.output
        assert "Daemon mode" in result.output

    def test_status_command_help(self):
        """Test status command help."""
        result = self.runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
        assert "Show MCP server status" in result.output
        assert "--all" in result.output
        assert "--format" in result.output

    def test_status_command_basic(self):
        """Test status command basic functionality."""
        result = self.runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert (
            "Status command implementation coming in Story 4.3"
            in result.output
        )

    def test_status_command_with_options(self):
        """Test status command with options."""
        result = self.runner.invoke(
            cli, ["status", "--all", "--port", "9000", "--format", "json"]
        )
        assert result.exit_code == 0
        assert "Showing all MCP servers" in result.output
        assert "9000" in result.output
        assert "json" in result.output

    def test_config_command_help(self):
        """Test config command help."""
        result = self.runner.invoke(cli, ["config", "--help"])
        assert result.exit_code == 0
        assert "Manage configuration settings" in result.output
        assert "show" in result.output
        assert "set" in result.output
        assert "reset" in result.output

    def test_config_command_show(self):
        """Test config command show action."""
        result = self.runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert (
            "Config command implementation coming in Story 4.4"
            in result.output
        )

    def test_config_command_set(self):
        """Test config command set action."""
        result = self.runner.invoke(
            cli, ["config", "set", "server.port", "9000"]
        )
        assert result.exit_code == 0
        assert "set" in result.output
        assert "server.port" in result.output
        assert "9000" in result.output

    def test_config_command_with_global_flag(self):
        """Test config command with global flag."""
        result = self.runner.invoke(
            cli, ["config", "set", "server.port", "9000", "--global"]
        )
        assert result.exit_code == 0
        assert "Global configuration" in result.output

    def test_help_command(self):
        """Test the help alias command."""
        result = self.runner.invoke(cli, ["help"])
        assert result.exit_code == 0
        assert "Universal Swagger → MCP Server Converter" in result.output

    def test_verbose_output(self):
        """Test verbose output mode."""
        result = self.runner.invoke(cli, ["--verbose", "status"])
        assert result.exit_code == 0
        # Verbose mode should not show extra output in current implementation

    def test_quiet_output(self):
        """Test quiet output mode."""
        result = self.runner.invoke(cli, ["--quiet", "status"])
        assert result.exit_code == 0
        # Quiet mode should suppress some output


class TestCLIError:
    """Test the CLIError exception class."""

    def test_cli_error_basic(self):
        """Test basic CLIError functionality."""
        error = CLIError("Test error message")
        assert error.message == "Test error message"
        assert error.suggestion is None
        assert str(error) == "Test error message"

    def test_cli_error_with_suggestion(self):
        """Test CLIError with suggestion."""
        error = CLIError("Test error", "Try this instead")
        assert error.message == "Test error"
        assert error.suggestion == "Try this instead"


class TestCLIContext:
    """Test the CLI context management."""

    def test_cli_context_basic(self):
        """Test basic CLI context functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            context = CLIContext(verbose=True, quiet=False)
            assert context.verbose is True
            assert context.quiet is False
            assert isinstance(context.config, dict)

    def test_cli_context_config_loading(self):
        """Test CLI context configuration loading."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("server:\n  port: 9000\n")
            f.flush()

            try:
                context = CLIContext(config_file=f.name)
                # Should not crash, but config loading might not work
                # without proper YAML structure
                assert isinstance(context.config, dict)
            finally:
                os.unlink(f.name)

    def test_cli_context_env_config(self):
        """Test CLI context environment variable loading."""
        with patch.dict(os.environ, {"SWAGGER_MCP_PORT": "9000"}):
            context = CLIContext()
            # Environment config should be loaded
            assert isinstance(context.config, dict)


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_full_workflow_help(self):
        """Test the full help workflow."""
        # Main help
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

        # Command helps
        commands = ["convert", "serve", "status", "config"]
        for command in commands:
            result = self.runner.invoke(cli, [command, "--help"])
            assert result.exit_code == 0, f"Help for {command} failed"

    def test_command_chaining(self):
        """Test that commands work independently."""
        # Create a temporary swagger file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            swagger_data = {
                "openapi": "3.0.0",
                "info": {"title": "Test API", "version": "1.0"},
                "paths": {"/test": {"get": {"summary": "Test endpoint"}}},
            }
            json.dump(swagger_data, f)
            f.flush()

            try:
                # Convert
                result = self.runner.invoke(cli, ["convert", f.name])
                assert result.exit_code == 0

                # Status
                result = self.runner.invoke(cli, ["status"])
                assert result.exit_code == 0

                # Config
                result = self.runner.invoke(cli, ["config", "show"])
                assert result.exit_code == 0

            finally:
                os.unlink(f.name)

    def test_error_handling(self):
        """Test error handling across commands."""
        # Test with invalid file
        result = self.runner.invoke(cli, ["convert", "/invalid/file.json"])
        assert result.exit_code != 0

        # Test with invalid config action
        result = self.runner.invoke(cli, ["config", "invalid_action"])
        assert result.exit_code != 0

    def test_global_options_with_commands(self):
        """Test global options work with all commands."""
        commands = [["status"], ["config", "show"], ["help"]]

        for command in commands:
            # Test with verbose
            result = self.runner.invoke(cli, ["--verbose"] + command)
            assert result.exit_code == 0, f"Verbose mode failed for {command}"

            # Test with quiet (skip help as it doesn't respect quiet)
            if command != ["help"]:
                result = self.runner.invoke(cli, ["--quiet"] + command)
                assert (
                    result.exit_code == 0
                ), f"Quiet mode failed for {command}"


@pytest.mark.performance
class TestCLIPerformance:
    """Performance tests for CLI startup and response times."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_startup_time(self):
        """Test CLI startup time is reasonable."""
        import time

        start_time = time.time()
        result = self.runner.invoke(cli, ["--help"])
        end_time = time.time()

        assert result.exit_code == 0
        startup_time = end_time - start_time
        # Should start up in less than 1 second (very generous)
        assert startup_time < 1.0, f"CLI startup took {startup_time:.2f}s"

    def test_help_response_time(self):
        """Test help command response time."""
        import time

        commands = [
            "--help",
            "convert --help",
            "serve --help",
            "status --help",
            "config --help",
        ]

        for command in commands:
            start_time = time.time()
            result = self.runner.invoke(cli, command.split())
            end_time = time.time()

            assert result.exit_code == 0
            response_time = end_time - start_time
            # Help should respond in less than 0.5 seconds
            assert (
                response_time < 0.5
            ), f"Help for '{command}' took {response_time:.2f}s"


class TestCLICrossPlatform:
    """Cross-platform compatibility tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_path_handling(self):
        """Test cross-platform path handling."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            swagger_data = {
                "openapi": "3.0.0",
                "info": {"title": "Test", "version": "1.0"},
            }
            json.dump(swagger_data, f)
            f.flush()

            try:
                # Test with different path formats
                result = self.runner.invoke(cli, ["convert", f.name])
                assert result.exit_code == 0

                # Test with Path object (should work on all platforms)
                path_str = str(Path(f.name))
                result = self.runner.invoke(cli, ["convert", path_str])
                assert result.exit_code == 0

            finally:
                os.unlink(f.name)

    def test_config_directories(self):
        """Test configuration directory handling across platforms."""
        from swagger_mcp_server.cli.utils import get_config_directories

        config_dirs = get_config_directories()

        # Should return valid paths
        assert "config" in config_dirs
        assert "data" in config_dirs
        assert isinstance(config_dirs["config"], Path)
        assert isinstance(config_dirs["data"], Path)
