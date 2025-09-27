"""Configuration management system for the CLI - Compatibility Layer."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Union

import click

from .utils import get_config_directories, safe_file_operation


class ConfigurationManager:
    """Manages configuration loading, validation, and storage."""

    DEFAULT_CONFIG = {
        "server": {
            "port": 8080,
            "host": "localhost",
            "timeout": 30,
            "max_connections": 100,
        },
        "output": {
            "directory": "./mcp-server",
            "force_overwrite": False,
            "create_directories": True,
        },
        "logging": {
            "level": "info",
            "format": "console",
            "file": None,
        },
        "search": {
            "index_size": 100,  # MB
            "cache_size": 1000,  # number of results
            "enable_fuzzy": True,
        },
        "performance": {
            "timeout": 30,
            "max_connections": 100,
            "enable_metrics": True,
        },
        "security": {
            "enable_auth": False,
            "api_key": None,
            "allowed_hosts": ["localhost", "127.0.0.1"],
        },
    }

    ENVIRONMENT_MAPPINGS = {
        "SWAGGER_MCP_PORT": "server.port",
        "SWAGGER_MCP_HOST": "server.host",
        "SWAGGER_MCP_OUTPUT_DIR": "output.directory",
        "SWAGGER_MCP_LOG_LEVEL": "logging.level",
        "SWAGGER_MCP_LOG_FORMAT": "logging.format",
        "SWAGGER_MCP_VERBOSE": "logging.verbose",
        "SWAGGER_MCP_API_KEY": "security.api_key",
        "SWAGGER_MCP_TIMEOUT": "performance.timeout",
    }

    def __init__(self):
        """Initialize the configuration manager."""
        self.config_dirs = get_config_directories()
        self.config = self._load_configuration()

    def _load_configuration(self) -> Dict[str, Any]:
        """Load configuration from all sources with proper precedence."""
        # Start with defaults
        config = self._deep_copy_dict(self.DEFAULT_CONFIG)

        # Load global configuration
        global_config_path = self.config_dirs["global_config"]
        if global_config_path.exists():
            global_config = self._load_config_file(global_config_path)
            config = self._merge_configs(config, global_config)

        # Load project configuration
        project_config_path = self.config_dirs["project_config"]
        if project_config_path.exists():
            project_config = self._load_config_file(project_config_path)
            config = self._merge_configs(config, project_config)

        # Apply environment variable overrides
        env_config = self._load_env_config()
        config = self._merge_configs(config, env_config)

        return config

    def _load_config_file(self, file_path: Path) -> Dict[str, Any]:
        """Load configuration from a YAML file."""
        try:
            import yaml

            with open(file_path, "r") as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            click.echo(
                "Warning: PyYAML not installed, skipping YAML configuration files",
                err=True,
            )
            return {}
        except Exception as e:
            click.echo(
                f"Warning: Could not load config file {file_path}: {e}",
                err=True,
            )
            return {}

    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}

        for env_var, config_key in self.ENVIRONMENT_MAPPINGS.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                # Type conversion
                if config_key.endswith(
                    (
                        ".port",
                        ".timeout",
                        ".max_connections",
                        ".index_size",
                        ".cache_size",
                    )
                ):
                    try:
                        value = int(value)
                    except ValueError:
                        click.echo(
                            f"Warning: Invalid integer value for {env_var}: {value}",
                            err=True,
                        )
                        continue
                elif config_key.endswith(
                    (
                        ".enable_auth",
                        ".force_overwrite",
                        ".create_directories",
                        ".enable_fuzzy",
                        ".enable_metrics",
                    )
                ):
                    value = value.lower() in ("true", "1", "yes", "on")

                self._set_nested_config(config, config_key, value)

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

    def _get_nested_config(self, config: Dict, key_path: str) -> Any:
        """Get nested configuration value using dot notation."""
        keys = key_path.split(".")
        current = config

        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]

        return current

    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """Merge two configuration dictionaries recursively."""
        result = self._deep_copy_dict(base)

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def _deep_copy_dict(self, d: Dict) -> Dict:
        """Create a deep copy of a dictionary."""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._deep_copy_dict(value)
            elif isinstance(value, list):
                result[key] = value.copy()
            else:
                result[key] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key path."""
        value = self._get_nested_config(self.config, key)
        return value if value is not None else default

    def set(self, key: str, value: Any, global_config: bool = False) -> bool:
        """Set configuration value and save to file."""
        try:
            # Update in-memory config
            self._set_nested_config(self.config, key, value)

            # Choose config file
            config_file = (
                self.config_dirs["global_config"]
                if global_config
                else self.config_dirs["project_config"]
            )

            # Load existing config file
            if config_file.exists():
                existing_config = self._load_config_file(config_file)
            else:
                existing_config = {}

            # Update the specific key
            self._set_nested_config(existing_config, key, value)

            # Save to file
            return self._save_config_file(config_file, existing_config)

        except Exception as e:
            click.echo(f"Error setting configuration: {e}", err=True)
            return False

    def reset(self, global_config: bool = False) -> bool:
        """Reset configuration to defaults."""
        try:
            config_file = (
                self.config_dirs["global_config"]
                if global_config
                else self.config_dirs["project_config"]
            )

            if config_file.exists():
                config_file.unlink()

            # Reload configuration
            self.config = self._load_configuration()
            return True

        except Exception as e:
            click.echo(f"Error resetting configuration: {e}", err=True)
            return False

    def _save_config_file(
        self, file_path: Path, config: Dict[str, Any]
    ) -> bool:
        """Save configuration to YAML file."""
        try:
            import yaml

            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Save with backup
            def save_operation(path):
                with open(path, "w") as f:
                    yaml.dump(config, f, default_flow_style=False, indent=2)

            return safe_file_operation(save_operation, str(file_path))

        except ImportError:
            click.echo(
                "Error: PyYAML not installed, cannot save configuration",
                err=True,
            )
            return False
        except Exception as e:
            click.echo(f"Error saving configuration: {e}", err=True)
            return False

    def validate(self) -> tuple[bool, list[str]]:
        """Validate current configuration."""
        errors = []

        # Validate server configuration
        port = self.get("server.port")
        if not isinstance(port, int) or port < 1024 or port > 65535:
            errors.append(f"Invalid server port: {port} (must be 1024-65535)")

        host = self.get("server.host")
        if not isinstance(host, str) or not host:
            errors.append(f"Invalid server host: {host}")

        # Validate logging configuration
        log_level = self.get("logging.level")
        valid_levels = ["debug", "info", "warning", "error"]
        if log_level not in valid_levels:
            errors.append(
                f"Invalid log level: {log_level} (must be one of {valid_levels})"
            )

        # Validate output configuration
        output_dir = self.get("output.directory")
        if not isinstance(output_dir, str) or not output_dir:
            errors.append(f"Invalid output directory: {output_dir}")

        # Validate performance configuration
        timeout = self.get("performance.timeout")
        if not isinstance(timeout, int) or timeout <= 0:
            errors.append(
                f"Invalid timeout: {timeout} (must be positive integer)"
            )

        max_connections = self.get("performance.max_connections")
        if not isinstance(max_connections, int) or max_connections <= 0:
            errors.append(
                f"Invalid max_connections: {max_connections} (must be positive integer)"
            )

        # Validate search configuration
        index_size = self.get("search.index_size")
        if not isinstance(index_size, int) or index_size <= 0:
            errors.append(
                f"Invalid search index_size: {index_size} (must be positive integer)"
            )

        return len(errors) == 0, errors

    def show_all(self) -> Dict[str, Any]:
        """Get all configuration for display."""
        return self._deep_copy_dict(self.config)

    def show_key(self, key: str) -> Union[Any, str]:
        """Get specific configuration key for display."""
        value = self.get(key)
        if value is None:
            return f"Configuration key '{key}' not found"
        return value

    def list_keys(self) -> list[str]:
        """List all available configuration keys."""
        keys = []

        def extract_keys(config: Dict, prefix: str = ""):
            for key, value in config.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    extract_keys(value, full_key)
                else:
                    keys.append(full_key)

        extract_keys(self.DEFAULT_CONFIG)
        return sorted(keys)

    def get_config_files(self) -> Dict[str, Path]:
        """Get paths to configuration files."""
        return {
            "global": self.config_dirs["global_config"],
            "project": self.config_dirs["project_config"],
        }

    def export_config(self, format: str = "yaml") -> str:
        """Export current configuration in specified format."""
        if format.lower() == "json":
            return json.dumps(self.config, indent=2)
        elif format.lower() == "yaml":
            try:
                import yaml

                return yaml.dump(
                    self.config, default_flow_style=False, indent=2
                )
            except ImportError:
                return json.dumps(self.config, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")


# Global configuration manager instance
_config_manager = None


def get_config_manager() -> ConfigurationManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def reload_config():
    """Reload configuration from files."""
    global _config_manager
    _config_manager = None
