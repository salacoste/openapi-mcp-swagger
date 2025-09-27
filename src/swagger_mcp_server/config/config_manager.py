"""Main configuration manager orchestrating all configuration operations."""

import copy
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .config_schema import ConfigurationSchema
from .env_extractor import EnvironmentConfigExtractor
from .template_manager import ConfigurationTemplateManager


class ConfigurationError(Exception):
    """Configuration-related error with user-friendly messages."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ConfigurationManager:
    """Main configuration manager coordinating all configuration operations."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_dir: Directory for configuration files (default: ~/.swagger-mcp-server)
        """
        self.config_dir = config_dir or (Path.home() / ".swagger-mcp-server")
        self.config_file = self.config_dir / "config.yaml"
        self.backup_dir = self.config_dir / "backups"

        # Initialize components
        self.schema = ConfigurationSchema()
        self.env_extractor = EnvironmentConfigExtractor()
        self.template_manager = ConfigurationTemplateManager()

        # Ensure directories exist
        self.config_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)

    async def load_configuration(
        self, config_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load configuration with hierarchy: defaults < file < environment.

        Args:
            config_file: Path to configuration file (default: ~/.swagger-mcp-server/config.yaml)

        Returns:
            Complete configuration dictionary

        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            # Start with default configuration
            config = self.schema.get_default_configuration()

            # Load from file if exists
            file_path = Path(config_file) if config_file else self.config_file
            if file_path.exists():
                file_config = self._load_config_file(file_path)
                config = self._merge_configurations(config, file_config)

            # Apply environment variable overrides
            env_config = self.env_extractor.extract_environment_config()
            if env_config:
                config = self._merge_configurations(config, env_config)

            # Validate final configuration
            errors = self._validate_complete_configuration(config)
            if errors:
                raise ConfigurationError(
                    "Configuration validation failed",
                    {"validation_errors": errors},
                )

            return config

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            else:
                raise ConfigurationError(
                    f"Failed to load configuration: {str(e)}"
                )

    def _load_config_file(self, file_path: Path) -> Dict[str, Any]:
        """Load configuration from YAML or JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Try YAML first, then JSON
            if file_path.suffix.lower() in [".yaml", ".yml"]:
                return yaml.safe_load(content) or {}
            elif file_path.suffix.lower() == ".json":
                return json.loads(content)
            else:
                # Auto-detect format
                try:
                    return yaml.safe_load(content) or {}
                except yaml.YAMLError:
                    return json.loads(content)

        except FileNotFoundError:
            return {}
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            raise ConfigurationError(
                f"Invalid configuration file format: {file_path}",
                {"parse_error": str(e)},
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to read configuration file: {file_path}",
                {"error": str(e)},
            )

    def _merge_configurations(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deep merge two configuration dictionaries."""
        result = copy.deepcopy(base)

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_configurations(result[key], value)
            else:
                result[key] = copy.deepcopy(value)

        return result

    def _validate_complete_configuration(
        self, config: Dict[str, Any]
    ) -> List[str]:
        """Validate complete configuration and return list of errors."""
        errors = []

        # Validate each configuration key
        for key in self.schema.get_all_configuration_keys():
            value = self.env_extractor.get_nested_config_value(config, key)
            if value is not None:
                is_valid, error_msg = self.schema.validate_configuration_value(
                    key, value
                )
                if not is_valid:
                    errors.append(error_msg)

        # Custom validation rules
        errors.extend(self._validate_cross_field_constraints(config))

        return errors

    def _validate_cross_field_constraints(
        self, config: Dict[str, Any]
    ) -> List[str]:
        """Validate constraints that span multiple configuration fields."""
        errors = []

        # SSL configuration validation
        ssl_config = self.env_extractor.get_nested_config_value(
            config, "server.ssl"
        )
        if ssl_config and ssl_config.get("enabled"):
            if not ssl_config.get("cert_file"):
                errors.append(
                    "SSL certificate file is required when SSL is enabled"
                )
            if not ssl_config.get("key_file"):
                errors.append(
                    "SSL private key file is required when SSL is enabled"
                )

        # File path validation
        log_file = self.env_extractor.get_nested_config_value(
            config, "logging.file"
        )
        if log_file:
            log_dir = Path(log_file).parent
            if not log_dir.exists():
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    errors.append(f"Cannot create log directory: {log_dir}")

        # Database path validation
        db_path = self.env_extractor.get_nested_config_value(
            config, "database.path"
        )
        if db_path:
            db_dir = Path(db_path).parent
            if not db_dir.exists():
                try:
                    db_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    errors.append(
                        f"Cannot create database directory: {db_dir}"
                    )

        return errors

    async def save_configuration(
        self, config: Dict[str, Any], config_file: Optional[str] = None
    ) -> None:
        """Save configuration to file.

        Args:
            config: Configuration dictionary to save
            config_file: Path to save configuration (default: ~/.swagger-mcp-server/config.yaml)

        Raises:
            ConfigurationError: If save operation fails
        """
        try:
            file_path = Path(config_file) if config_file else self.config_file

            # Create backup if file exists
            if file_path.exists():
                await self._create_backup(file_path)

            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Save configuration
            if file_path.suffix.lower() == ".json":
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
            else:
                # Default to YAML
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"# MCP Server Configuration\n")
                    f.write(f"# Generated on: {datetime.now().isoformat()}\n")
                    f.write(f"# File: {file_path}\n\n")
                    yaml.dump(
                        config, f, default_flow_style=False, sort_keys=False
                    )

        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {str(e)}")

    async def get_configuration_value(
        self, key: str, config_file: Optional[str] = None
    ) -> Any:
        """Get a specific configuration value.

        Args:
            key: Configuration key in dot notation
            config_file: Configuration file to read from

        Returns:
            Configuration value or None if not found
        """
        config = await self.load_configuration(config_file)
        return self.env_extractor.get_nested_config_value(config, key)

    async def set_configuration_value(
        self, key: str, value: Any, config_file: Optional[str] = None
    ) -> None:
        """Set a specific configuration value.

        Args:
            key: Configuration key in dot notation
            value: Value to set
            config_file: Configuration file to modify

        Raises:
            ConfigurationError: If validation fails or save fails
        """
        # Validate the value first
        is_valid, error_msg = self.schema.validate_configuration_value(
            key, value
        )
        if not is_valid:
            raise ConfigurationError(
                f"Invalid configuration value: {error_msg}"
            )

        # Load current configuration
        config = await self.load_configuration(config_file)

        # Set the new value
        self.env_extractor.set_nested_config(config, key, value)

        # Save updated configuration
        await self.save_configuration(config, config_file)

    async def reset_configuration(
        self, config_file: Optional[str] = None, template: str = "development"
    ) -> None:
        """Reset configuration to defaults or template.

        Args:
            config_file: Configuration file to reset
            template: Template to use for reset

        Raises:
            ConfigurationError: If reset operation fails
        """
        try:
            # Get template configuration
            if template:
                config = self.template_manager.get_template(template)
            else:
                config = self.schema.get_default_configuration()

            # Save configuration
            await self.save_configuration(config, config_file)

        except Exception as e:
            raise ConfigurationError(
                f"Failed to reset configuration: {str(e)}"
            )

    async def initialize_configuration(
        self,
        template: str = "development",
        config_file: Optional[str] = None,
        overwrite: bool = False,
    ) -> None:
        """Initialize configuration file with template.

        Args:
            template: Template name to use
            config_file: Configuration file path
            overwrite: Whether to overwrite existing file

        Raises:
            ConfigurationError: If initialization fails
        """
        try:
            file_path = Path(config_file) if config_file else self.config_file

            # Check if file exists and overwrite is not allowed
            if file_path.exists() and not overwrite:
                raise ConfigurationError(
                    f"Configuration file already exists: {file_path}",
                    {
                        "suggestion": "Use --force to overwrite or choose a different path"
                    },
                )

            # Get template configuration
            config = self.template_manager.get_template(template)

            # Validate template
            is_valid, errors = self.template_manager.validate_template(config)
            if not is_valid:
                raise ConfigurationError(
                    f"Template '{template}' is invalid",
                    {"validation_errors": errors},
                )

            # Save configuration
            await self.save_configuration(config, str(file_path))

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            else:
                raise ConfigurationError(
                    f"Failed to initialize configuration: {str(e)}"
                )

    async def validate_configuration(
        self, config_file: Optional[str] = None
    ) -> tuple[bool, List[str], List[str]]:
        """Validate configuration file.

        Args:
            config_file: Configuration file to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        try:
            config = await self.load_configuration(config_file)
            errors = self._validate_complete_configuration(config)
            warnings = self._get_configuration_warnings(config)

            return len(errors) == 0, errors, warnings

        except ConfigurationError as e:
            return False, [e.message], []

    def _get_configuration_warnings(self, config: Dict[str, Any]) -> List[str]:
        """Get configuration warnings (non-critical issues)."""
        warnings = []

        # Performance warnings
        cache_size = self.env_extractor.get_nested_config_value(
            config, "search.performance.cache_size_mb"
        )
        if cache_size and cache_size < 32:
            warnings.append(
                "Search cache size is quite small, consider increasing for better performance"
            )

        max_connections = self.env_extractor.get_nested_config_value(
            config, "server.max_connections"
        )
        if max_connections and max_connections > 500:
            warnings.append(
                "High connection limit may impact system resources"
            )

        # Security warnings
        ssl_enabled = self.env_extractor.get_nested_config_value(
            config, "server.ssl.enabled"
        )
        host = self.env_extractor.get_nested_config_value(
            config, "server.host"
        )
        if host == "0.0.0.0" and not ssl_enabled:
            warnings.append(
                "Server accepting external connections without SSL encryption"
            )

        # Logging warnings
        log_level = self.env_extractor.get_nested_config_value(
            config, "logging.level"
        )
        if log_level == "DEBUG":
            warnings.append(
                "Debug logging may impact performance and expose sensitive information"
            )

        return warnings

    async def _create_backup(self, file_path: Path) -> None:
        """Create backup of configuration file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            backup_path = self.backup_dir / backup_name

            shutil.copy2(file_path, backup_path)

            # Clean up old backups (keep last 10)
            backups = sorted(
                self.backup_dir.glob(f"{file_path.stem}_*{file_path.suffix}")
            )
            for old_backup in backups[:-10]:
                old_backup.unlink()

        except Exception:
            # Backup failure shouldn't stop configuration operations
            pass

    def get_configuration_help(self, key: Optional[str] = None) -> str:
        """Get help information for configuration.

        Args:
            key: Specific configuration key or None for general help

        Returns:
            Help text
        """
        if key:
            help_text = self.schema.get_configuration_help(key)
            if help_text:
                env_var = self.env_extractor.get_environment_variable_for_path(
                    key
                )
                if env_var:
                    help_text += f"\n\nEnvironment variable: {env_var}"
                return help_text
            else:
                return f"No help available for '{key}'"
        else:
            # General configuration help
            return """Configuration Management Help

Available configuration sections:
- server.*: Server host, port, connections, SSL settings
- database.*: Database path, pooling, backup settings
- search.*: Search engine, indexing, performance settings
- logging.*: Log level, format, file rotation settings
- features.*: Feature flags for metrics, health checks, rate limiting

Use dot notation to access nested settings:
  swagger-mcp-server config show server.port
  swagger-mcp-server config set server.port 9000

Templates available: development, staging, production, container

Environment variables:
All settings can be overridden with SWAGGER_MCP_* environment variables.
Use 'swagger-mcp-server config env-help' for details.
"""

    def get_environment_help(self) -> str:
        """Get help for environment variables."""
        env_docs = self.env_extractor.get_environment_documentation()

        help_text = "Environment Variable Configuration\n"
        help_text += "=" * 50 + "\n\n"

        for env_var, description in sorted(env_docs.items()):
            help_text += f"{env_var}\n  {description}\n\n"

        return help_text
