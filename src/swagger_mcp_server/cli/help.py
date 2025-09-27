"""Enhanced help system with examples and interactive guidance."""

from typing import Dict, List, Optional

import click


class EnhancedHelp:
    """Enhanced help system with examples and contextual guidance."""

    def __init__(self):
        self.examples = {
            "convert": [
                "Convert basic Swagger file:",
                "  swagger-mcp-server convert api.json",
                "",
                "Convert with custom output directory:",
                "  swagger-mcp-server convert api.json --output ./my-server",
                "",
                "Convert with specific port and name:",
                "  swagger-mcp-server convert api.json --port 9000 --name MyAPI",
                "",
                "Force overwrite existing directory:",
                "  swagger-mcp-server convert api.json --force",
            ],
            "serve": [
                "Start server on default port:",
                "  swagger-mcp-server serve",
                "",
                "Start server on custom port and host:",
                "  swagger-mcp-server serve --port 9000 --host 0.0.0.0",
                "",
                "Start with custom configuration file:",
                "  swagger-mcp-server serve --config-file ./server-config.yaml",
                "",
                "Run server as background daemon:",
                "  swagger-mcp-server serve --daemon",
            ],
            "status": [
                "Show current server status:",
                "  swagger-mcp-server status",
                "",
                "Show all running MCP servers:",
                "  swagger-mcp-server status --all",
                "",
                "Check specific port with JSON output:",
                "  swagger-mcp-server status --port 9000 --format json",
            ],
            "config": [
                "Show all configuration settings:",
                "  swagger-mcp-server config show",
                "",
                "Show specific configuration value:",
                "  swagger-mcp-server config show server.port",
                "",
                "Set configuration value:",
                "  swagger-mcp-server config set server.port 9000",
                "",
                "Reset all configuration to defaults:",
                "  swagger-mcp-server config reset",
                "",
                "Validate configuration file:",
                "  swagger-mcp-server config validate",
            ],
        }

        self.workflows = {
            "quick_start": [
                "Quick Start Workflow:",
                "1. Convert your Swagger file:",
                "   swagger-mcp-server convert api.json",
                "",
                "2. Start the MCP server:",
                "   swagger-mcp-server serve",
                "",
                "3. Check server status:",
                "   swagger-mcp-server status",
            ],
            "development": [
                "Development Workflow:",
                "1. Convert with custom settings:",
                "   swagger-mcp-server convert api.json --output ./dev-server --port 9000",
                "",
                "2. Configure development settings:",
                "   swagger-mcp-server config set logging.level debug",
                "",
                "3. Start server with verbose output:",
                "   swagger-mcp-server serve --verbose",
                "",
                "4. Monitor server performance:",
                "   swagger-mcp-server status --all --format json",
            ],
            "production": [
                "Production Deployment:",
                "1. Validate Swagger file first:",
                "   swagger-mcp-server config validate",
                "",
                "2. Convert with production settings:",
                "   swagger-mcp-server convert api.json --output /opt/mcp-server",
                "",
                "3. Start as daemon on specific interface:",
                "   swagger-mcp-server serve --host 0.0.0.0 --port 8080 --daemon",
                "",
                "4. Set up monitoring:",
                "   swagger-mcp-server status --all",
            ],
        }

        self.troubleshooting = {
            "common_issues": [
                "Common Issues and Solutions:",
                "",
                "Issue: 'Port already in use'",
                "Solution: Use a different port or find free port:",
                "  swagger-mcp-server serve --port 9000",
                "",
                "Issue: 'Invalid Swagger file'",
                "Solution: Validate your OpenAPI specification:",
                "  swagger-mcp-server config validate",
                "",
                "Issue: 'Permission denied'",
                "Solution: Check file permissions or use --force:",
                "  swagger-mcp-server convert api.json --force",
                "",
                "Issue: 'Configuration errors'",
                "Solution: Reset configuration to defaults:",
                "  swagger-mcp-server config reset",
            ],
            "debugging": [
                "Debugging Tips:",
                "",
                "Enable verbose output for detailed logs:",
                "  swagger-mcp-server --verbose serve",
                "",
                "Check system and dependency status:",
                "  swagger-mcp-server --version",
                "",
                "View current configuration:",
                "  swagger-mcp-server config show",
                "",
                "Test with minimal setup:",
                "  swagger-mcp-server convert simple.json --output /tmp/test",
            ],
        }

        self.configuration_help = {
            "keys": {
                "server.port": "Default server port (1024-65535)",
                "server.host": "Default server host (localhost, 0.0.0.0, etc.)",
                "output.directory": "Default output directory for converted servers",
                "logging.level": "Log level (debug, info, warning, error)",
                "logging.format": "Log format (json, console)",
                "search.index_size": "Maximum search index size in MB",
                "search.cache_size": "Search result cache size",
                "performance.timeout": "Request timeout in seconds",
                "performance.max_connections": "Maximum concurrent connections",
                "security.enable_auth": "Enable authentication (true/false)",
                "security.api_key": "API key for server access",
            },
            "examples": [
                "Configuration Examples:",
                "",
                "Set server to listen on all interfaces:",
                "  swagger-mcp-server config set server.host 0.0.0.0",
                "",
                "Enable debug logging:",
                "  swagger-mcp-server config set logging.level debug",
                "",
                "Set output directory for all conversions:",
                "  swagger-mcp-server config set output.directory /opt/mcp-servers",
                "",
                "Configure performance settings:",
                "  swagger-mcp-server config set performance.timeout 30",
                "  swagger-mcp-server config set performance.max_connections 100",
            ],
        }

    def get_command_examples(self, command: str) -> str:
        """Get examples for specific command."""
        if command in self.examples:
            return "\n".join(self.examples[command])
        return ""

    def get_workflow_help(self, workflow: str) -> str:
        """Get help for specific workflow."""
        if workflow in self.workflows:
            return "\n".join(self.workflows[workflow])
        return ""

    def get_troubleshooting_help(self, category: str) -> str:
        """Get troubleshooting help for specific category."""
        if category in self.troubleshooting:
            return "\n".join(self.troubleshooting[category])
        return ""

    def get_configuration_help(self, key: Optional[str] = None) -> str:
        """Get configuration help."""
        if key and key in self.configuration_help["keys"]:
            return f"{key}: {self.configuration_help['keys'][key]}"
        elif key is None:
            help_text = ["Available Configuration Keys:"]
            for k, desc in self.configuration_help["keys"].items():
                help_text.append(f"  {k:<25} - {desc}")
            help_text.extend(["", ""] + self.configuration_help["examples"])
            return "\n".join(help_text)
        else:
            return f"Unknown configuration key: {key}"

    def show_interactive_help(self):
        """Show interactive help menu."""
        while True:
            click.echo("\n📚 Interactive Help System")
            click.echo("=" * 50)
            click.echo("1. Command Examples")
            click.echo("2. Workflow Guides")
            click.echo("3. Troubleshooting")
            click.echo("4. Configuration Help")
            click.echo("5. Quick Reference")
            click.echo("0. Exit")

            choice = click.prompt(
                "\nSelect help topic",
                type=click.Choice(["0", "1", "2", "3", "4", "5"]),
                show_choices=False,
            )

            if choice == "0":
                break
            elif choice == "1":
                self._show_command_examples()
            elif choice == "2":
                self._show_workflow_guides()
            elif choice == "3":
                self._show_troubleshooting()
            elif choice == "4":
                self._show_configuration_help()
            elif choice == "5":
                self._show_quick_reference()

    def _show_command_examples(self):
        """Show command examples submenu."""
        commands = list(self.examples.keys())
        commands.append("back")

        while True:
            click.echo("\n📝 Command Examples")
            click.echo("-" * 30)
            for i, cmd in enumerate(commands):
                if cmd == "back":
                    click.echo(f"{i}. Back to main menu")
                else:
                    click.echo(f"{i + 1}. {cmd}")

            choice = click.prompt(
                "Select command",
                type=click.IntRange(0, len(commands)),
                show_choices=False,
            )

            if choice == 0 or commands[choice - 1] == "back":
                break
            else:
                command = commands[choice - 1]
                click.echo(f"\n{command.upper()} Examples:")
                click.echo("-" * 40)
                click.echo(self.get_command_examples(command))
                click.prompt(
                    "\nPress Enter to continue", default="", show_default=False
                )

    def _show_workflow_guides(self):
        """Show workflow guides submenu."""
        workflows = list(self.workflows.keys())
        workflows.append("back")

        while True:
            click.echo("\n🔄 Workflow Guides")
            click.echo("-" * 30)
            for i, workflow in enumerate(workflows):
                if workflow == "back":
                    click.echo(f"{i}. Back to main menu")
                else:
                    title = workflow.replace("_", " ").title()
                    click.echo(f"{i + 1}. {title}")

            choice = click.prompt(
                "Select workflow",
                type=click.IntRange(0, len(workflows)),
                show_choices=False,
            )

            if choice == 0 or workflows[choice - 1] == "back":
                break
            else:
                workflow = workflows[choice - 1]
                click.echo(f"\n{workflow.replace('_', ' ').title()}:")
                click.echo("-" * 40)
                click.echo(self.get_workflow_help(workflow))
                click.prompt(
                    "\nPress Enter to continue", default="", show_default=False
                )

    def _show_troubleshooting(self):
        """Show troubleshooting submenu."""
        categories = list(self.troubleshooting.keys())
        categories.append("back")

        while True:
            click.echo("\n🔧 Troubleshooting")
            click.echo("-" * 30)
            for i, category in enumerate(categories):
                if category == "back":
                    click.echo(f"{i}. Back to main menu")
                else:
                    title = category.replace("_", " ").title()
                    click.echo(f"{i + 1}. {title}")

            choice = click.prompt(
                "Select category",
                type=click.IntRange(0, len(categories)),
                show_choices=False,
            )

            if choice == 0 or categories[choice - 1] == "back":
                break
            else:
                category = categories[choice - 1]
                click.echo(f"\n{category.replace('_', ' ').title()}:")
                click.echo("-" * 40)
                click.echo(self.get_troubleshooting_help(category))
                click.prompt(
                    "\nPress Enter to continue", default="", show_default=False
                )

    def _show_configuration_help(self):
        """Show configuration help."""
        click.echo("\n⚙️ Configuration Help")
        click.echo("-" * 40)
        click.echo(self.get_configuration_help())
        click.prompt(
            "\nPress Enter to continue", default="", show_default=False
        )

    def _show_quick_reference(self):
        """Show quick reference card."""
        click.echo("\n⚡ Quick Reference")
        click.echo("-" * 40)
        click.echo("Essential Commands:")
        click.echo("  convert FILE         Convert Swagger to MCP server")
        click.echo("  serve               Start MCP server")
        click.echo("  status              Show server status")
        click.echo("  config show         Show configuration")
        click.echo("")
        click.echo("Common Options:")
        click.echo("  --verbose, -v       Enable verbose output")
        click.echo("  --quiet, -q         Enable quiet mode")
        click.echo("  --config, -c FILE   Use configuration file")
        click.echo("  --help              Show command help")
        click.echo("")
        click.echo("Quick Start:")
        click.echo("  swagger-mcp-server convert api.json")
        click.echo("  swagger-mcp-server serve")
        click.prompt(
            "\nPress Enter to continue", default="", show_default=False
        )


def format_help_text(ctx: click.Context, command_name: str) -> str:
    """Format enhanced help text with examples."""
    help_formatter = EnhancedHelp()

    # Get base help text
    base_help = ctx.get_help()

    # Add examples if available
    examples = help_formatter.get_command_examples(command_name)
    if examples:
        base_help += f"\n\nExamples:\n{examples}"

    return base_help


def show_command_help(command_name: str, detailed: bool = False):
    """Show help for a specific command."""
    help_formatter = EnhancedHelp()

    if detailed:
        # Show interactive help
        help_formatter.show_interactive_help()
    else:
        # Show examples for the command
        examples = help_formatter.get_command_examples(command_name)
        if examples:
            click.echo(f"\n{command_name.upper()} Examples:")
            click.echo("-" * 40)
            click.echo(examples)
        else:
            click.echo(f"No specific examples available for '{command_name}'")
            click.echo("Use 'swagger-mcp-server help' for interactive help")


# Custom Click command class with enhanced help
class EnhancedCommand(click.Command):
    """Click command with enhanced help formatting."""

    def format_help(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        """Format help with examples."""
        super().format_help(ctx, formatter)

        # Add examples section
        help_formatter = EnhancedHelp()
        examples = help_formatter.get_command_examples(self.name or "")
        if examples:
            formatter.write_paragraph()
            formatter.write_heading("Examples")
            formatter.write_text(examples)


# Custom Click group class with enhanced help
class EnhancedGroup(click.Group):
    """Click group with enhanced help formatting."""

    def format_help(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        """Format help with workflow information."""
        super().format_help(ctx, formatter)

        # Add workflow section
        help_formatter = EnhancedHelp()
        workflow = help_formatter.get_workflow_help("quick_start")
        if workflow:
            formatter.write_paragraph()
            formatter.write_heading("Quick Start")
            formatter.write_text(workflow)

        # Add interactive help notice
        formatter.write_paragraph()
        formatter.write_text(
            "For interactive help and detailed examples, run:\n"
            "swagger-mcp-server help"
        )
