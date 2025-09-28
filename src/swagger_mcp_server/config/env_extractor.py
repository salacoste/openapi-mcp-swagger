"""Environment variable configuration extraction for MCP server system."""

import os
from typing import Any, Dict, Union

from .exceptions import ConfigurationError


class EnvironmentConfigExtractor:
    """Extracts configuration from environment variables with systematic mapping."""

    ENV_PREFIX = "SWAGGER_MCP_"

    # Environment variable to configuration path mappings
    ENV_MAPPINGS = {
        # Server configuration
        "SWAGGER_MCP_SERVER_HOST": "server.host",
        "SWAGGER_MCP_SERVER_PORT": "server.port",
        "SWAGGER_MCP_SERVER_MAX_CONNECTIONS": "server.max_connections",
        "SWAGGER_MCP_SERVER_TIMEOUT": "server.timeout",
        "SWAGGER_MCP_SERVER_SSL_ENABLED": "server.ssl.enabled",
        "SWAGGER_MCP_SERVER_SSL_CERT": "server.ssl.cert_file",
        "SWAGGER_MCP_SERVER_SSL_KEY": "server.ssl.key_file",
        # Database configuration
        "SWAGGER_MCP_DB_PATH": "database.path",
        "SWAGGER_MCP_DB_POOL_SIZE": "database.pool_size",
        "SWAGGER_MCP_DB_TIMEOUT": "database.timeout",
        "SWAGGER_MCP_DB_BACKUP_ENABLED": "database.backup.enabled",
        "SWAGGER_MCP_DB_BACKUP_INTERVAL": "database.backup.interval",
        "SWAGGER_MCP_DB_BACKUP_RETENTION": "database.backup.retention",
        # Search configuration
        "SWAGGER_MCP_SEARCH_ENGINE": "search.engine",
        "SWAGGER_MCP_SEARCH_INDEX_DIR": "search.index_directory",
        "SWAGGER_MCP_SEARCH_WEIGHT_ENDPOINT": "search.field_weights.endpoint_path",
        "SWAGGER_MCP_SEARCH_WEIGHT_DESC": "search.field_weights.description",
        "SWAGGER_MCP_SEARCH_WEIGHT_PARAMS": "search.field_weights.parameters",
        "SWAGGER_MCP_SEARCH_CACHE_SIZE": "search.performance.cache_size_mb",
        "SWAGGER_MCP_SEARCH_MAX_RESULTS": "search.performance.max_results",
        # Logging configuration
        "SWAGGER_MCP_LOG_LEVEL": "logging.level",
        "SWAGGER_MCP_LOG_FORMAT": "logging.format",
        "SWAGGER_MCP_LOG_FILE": "logging.file",
        "SWAGGER_MCP_LOG_ROTATION_ENABLED": "logging.rotation.enabled",
        "SWAGGER_MCP_LOG_ROTATION_SIZE": "logging.rotation.max_size_mb",
        "SWAGGER_MCP_LOG_ROTATION_COUNT": "logging.rotation.backup_count",
    }

    def __init__(self):
        """Initialize environment extractor."""
        pass

    def extract_environment_config(self) -> Dict[str, Any]:
        """Extract configuration from environment variables.

        Returns:
            Dict containing configuration values extracted from environment
        """
        config = {}

        for env_var, config_path in self.ENV_MAPPINGS.items():
            if env_var in os.environ:
                try:
                    value = self.convert_env_value(os.environ[env_var], config_path)
                    self.set_nested_config(config, config_path, value)
                except Exception:
                    # Skip invalid environment variables silently
                    pass

        return config

    def convert_env_value(
        self, env_value: str, config_path: str
    ) -> Union[str, int, bool, float]:
        """Convert environment variable value to appropriate type.

        Args:
            env_value: Raw environment variable value
            config_path: Configuration path for type inference

        Returns:
            Converted value with appropriate type
        """
        # Boolean conversion
        boolean_paths = [
            "server.ssl.enabled",
            "database.backup.enabled",
            "logging.rotation.enabled",
        ]
        if config_path in boolean_paths:
            return env_value.lower() in ("true", "1", "yes", "on", "enabled")

        # Integer conversion
        integer_paths = [
            "server.port",
            "server.max_connections",
            "server.timeout",
            "database.pool_size",
            "database.timeout",
            "database.backup.interval",
            "database.backup.retention",
            "search.performance.cache_size_mb",
            "search.performance.max_results",
            "logging.rotation.max_size_mb",
            "logging.rotation.backup_count",
        ]
        if config_path in integer_paths:
            try:
                return int(env_value)
            except ValueError:
                raise ConfigurationError(
                    f"Invalid integer value for {config_path}: {env_value}"
                )

        # Float conversion for field weights
        if "field_weights" in config_path:
            try:
                return float(env_value)
            except ValueError:
                raise ConfigurationError(
                    f"Invalid float value for {config_path}: {env_value}"
                )

        # String value (default)
        return env_value

    def set_nested_config(self, config: Dict[str, Any], path: str, value: Any):
        """Set nested configuration value using dot notation.

        Args:
            config: Configuration dictionary to modify
            path: Dot-separated path (e.g., 'server.ssl.enabled')
            value: Value to set
        """
        keys = path.split(".")
        current = config

        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set the final value
        current[keys[-1]] = value

    def get_nested_config_value(self, config: Dict[str, Any], path: str) -> Any:
        """Get nested configuration value using dot notation.

        Args:
            config: Configuration dictionary to read from
            path: Dot-separated path (e.g., 'server.ssl.enabled')

        Returns:
            Value at the specified path, or None if not found
        """
        keys = path.split(".")
        current = config

        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return None

    def get_environment_variable_for_path(self, config_path: str) -> str:
        """Get the environment variable name for a configuration path.

        Args:
            config_path: Dot-separated configuration path

        Returns:
            Environment variable name if found, or constructed name
        """
        for env_var, path in self.ENV_MAPPINGS.items():
            if path == config_path:
                return env_var

        # If not found in mappings, construct based on path
        return self.ENV_PREFIX + config_path.upper().replace(".", "_")

    def get_environment_documentation(self) -> Dict[str, str]:
        """Get documentation for all supported environment variables.

        Returns:
            Dict mapping environment variable names to descriptions
        """
        return {
            # Server configuration
            "SWAGGER_MCP_SERVER_HOST": "Server host address (default: localhost)",
            "SWAGGER_MCP_SERVER_PORT": "Server port number (default: 8080)",
            "SWAGGER_MCP_SERVER_MAX_CONNECTIONS": "Maximum concurrent connections (default: 100)",
            "SWAGGER_MCP_SERVER_TIMEOUT": "Connection timeout in seconds (default: 30)",
            "SWAGGER_MCP_SERVER_SSL_ENABLED": "Enable SSL/TLS encryption (default: false)",
            "SWAGGER_MCP_SERVER_SSL_CERT": "Path to SSL certificate file",
            "SWAGGER_MCP_SERVER_SSL_KEY": "Path to SSL private key file",
            # Database configuration
            "SWAGGER_MCP_DB_PATH": "Database file path (default: ./mcp_server.db)",
            "SWAGGER_MCP_DB_POOL_SIZE": "Database connection pool size (default: 5)",
            "SWAGGER_MCP_DB_TIMEOUT": "Database operation timeout in seconds (default: 10)",
            "SWAGGER_MCP_DB_BACKUP_ENABLED": "Enable automatic database backups (default: true)",
            "SWAGGER_MCP_DB_BACKUP_INTERVAL": "Backup interval in seconds (default: 86400)",
            "SWAGGER_MCP_DB_BACKUP_RETENTION": "Number of backup files to retain (default: 7)",
            # Search configuration
            "SWAGGER_MCP_SEARCH_ENGINE": "Search engine implementation (default: whoosh)",
            "SWAGGER_MCP_SEARCH_INDEX_DIR": "Search index directory (default: ./search_index)",
            "SWAGGER_MCP_SEARCH_WEIGHT_ENDPOINT": "Weight for endpoint path matching (default: 1.5)",
            "SWAGGER_MCP_SEARCH_WEIGHT_DESC": "Weight for description matching (default: 1.0)",
            "SWAGGER_MCP_SEARCH_WEIGHT_PARAMS": "Weight for parameter matching (default: 0.8)",
            "SWAGGER_MCP_SEARCH_CACHE_SIZE": "Search cache size in MB (default: 64)",
            "SWAGGER_MCP_SEARCH_MAX_RESULTS": "Maximum search results (default: 1000)",
            # Logging configuration
            "SWAGGER_MCP_LOG_LEVEL": "Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)",
            "SWAGGER_MCP_LOG_FORMAT": "Log message format string",
            "SWAGGER_MCP_LOG_FILE": "Log file path (default: None - console only)",
            "SWAGGER_MCP_LOG_ROTATION_ENABLED": "Enable log file rotation (default: false)",
            "SWAGGER_MCP_LOG_ROTATION_SIZE": "Max log file size in MB before rotation (default: 10)",
            "SWAGGER_MCP_LOG_ROTATION_COUNT": "Number of backup log files to keep (default: 5)",
        }

    def get_current_environment_config(self) -> Dict[str, str]:
        """Get currently set environment variables related to configuration.

        Returns:
            Dict mapping environment variable names to their current values
        """
        current_env = {}

        for env_var in self.ENV_MAPPINGS.keys():
            if env_var in os.environ:
                current_env[env_var] = os.environ[env_var]

        return current_env

    def validate_environment_config(self) -> Dict[str, Any]:
        """Validate current environment configuration.

        Returns:
            Dict containing validation results with issues and suggestions
        """
        issues = []
        suggestions = []
        current_env = self.get_current_environment_config()

        # Check for common configuration issues
        if "SWAGGER_MCP_SERVER_HOST" in current_env:
            host = current_env["SWAGGER_MCP_SERVER_HOST"]
            if (
                host == "0.0.0.0"
                and "SWAGGER_MCP_SERVER_SSL_ENABLED" not in current_env
            ):
                issues.append(
                    "Server exposed on all interfaces without SSL configuration"
                )
                suggestions.append(
                    "Set SWAGGER_MCP_SERVER_SSL_ENABLED=true for security"
                )

        # Check for SSL configuration completeness
        ssl_enabled = current_env.get("SWAGGER_MCP_SERVER_SSL_ENABLED", "").lower()
        if ssl_enabled in ("true", "1", "yes", "on"):
            if "SWAGGER_MCP_SERVER_SSL_CERT" not in current_env:
                issues.append("SSL enabled but no certificate file specified")
                suggestions.append(
                    "Set SWAGGER_MCP_SERVER_SSL_CERT to certificate file path"
                )
            if "SWAGGER_MCP_SERVER_SSL_KEY" not in current_env:
                issues.append("SSL enabled but no private key file specified")
                suggestions.append(
                    "Set SWAGGER_MCP_SERVER_SSL_KEY to private key file path"
                )

        # Check for performance-related configurations
        if (
            "SWAGGER_MCP_SERVER_MAX_CONNECTIONS" in current_env
            and "SWAGGER_MCP_DB_POOL_SIZE" in current_env
        ):
            try:
                max_conn = int(current_env["SWAGGER_MCP_SERVER_MAX_CONNECTIONS"])
                pool_size = int(current_env["SWAGGER_MCP_DB_POOL_SIZE"])
                if max_conn > pool_size * 10:
                    issues.append(
                        "Database pool size may be too small for maximum connections"
                    )
                    suggestions.append(
                        f"Consider increasing SWAGGER_MCP_DB_POOL_SIZE to at least {max_conn // 10}"
                    )
            except ValueError:
                issues.append("Invalid numeric values in connection configuration")

        # Check for development vs production settings
        log_level = current_env.get("SWAGGER_MCP_LOG_LEVEL", "").upper()
        if log_level == "DEBUG":
            suggestions.append(
                "Debug logging is enabled - consider INFO or WARNING for production"
            )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "suggestions": suggestions,
            "environment_variables": current_env,
        }

    def generate_environment_template(self, template_type: str = "production") -> str:
        """Generate environment variable template file.

        Args:
            template_type: Type of template (development, staging, production)

        Returns:
            String containing environment variable template
        """
        lines = [
            "# MCP Server Environment Configuration",
            f"# Template: {template_type}",
            "# Generated by swagger-mcp-server",
            "",
            "# Server Configuration",
        ]

        if template_type == "development":
            lines.extend(
                [
                    "SWAGGER_MCP_SERVER_HOST=localhost",
                    "SWAGGER_MCP_SERVER_PORT=8080",
                    "SWAGGER_MCP_SERVER_MAX_CONNECTIONS=10",
                    "SWAGGER_MCP_SERVER_TIMEOUT=60",
                    "# SWAGGER_MCP_SERVER_SSL_ENABLED=false",
                    "",
                    "# Database Configuration",
                    "SWAGGER_MCP_DB_PATH=./dev_mcp_server.db",
                    "SWAGGER_MCP_DB_POOL_SIZE=2",
                    "SWAGGER_MCP_DB_BACKUP_ENABLED=false",
                    "",
                    "# Search Configuration",
                    "SWAGGER_MCP_SEARCH_INDEX_DIR=./dev_search_index",
                    "SWAGGER_MCP_SEARCH_CACHE_SIZE=32",
                    "SWAGGER_MCP_SEARCH_MAX_RESULTS=100",
                    "",
                    "# Logging Configuration",
                    "SWAGGER_MCP_LOG_LEVEL=DEBUG",
                    "SWAGGER_MCP_LOG_FILE=./dev_server.log",
                    "SWAGGER_MCP_LOG_ROTATION_ENABLED=false",
                ]
            )
        elif template_type == "production":
            lines.extend(
                [
                    "SWAGGER_MCP_SERVER_HOST=0.0.0.0",
                    "SWAGGER_MCP_SERVER_PORT=8080",
                    "SWAGGER_MCP_SERVER_MAX_CONNECTIONS=100",
                    "SWAGGER_MCP_SERVER_TIMEOUT=30",
                    "SWAGGER_MCP_SERVER_SSL_ENABLED=true",
                    "SWAGGER_MCP_SERVER_SSL_CERT=/etc/ssl/certs/mcp-server.crt",
                    "SWAGGER_MCP_SERVER_SSL_KEY=/etc/ssl/private/mcp-server.key",
                    "",
                    "# Database Configuration",
                    "SWAGGER_MCP_DB_PATH=/var/lib/mcp-server/mcp_server.db",
                    "SWAGGER_MCP_DB_POOL_SIZE=10",
                    "SWAGGER_MCP_DB_BACKUP_ENABLED=true",
                    "SWAGGER_MCP_DB_BACKUP_INTERVAL=86400",
                    "SWAGGER_MCP_DB_BACKUP_RETENTION=7",
                    "",
                    "# Search Configuration",
                    "SWAGGER_MCP_SEARCH_INDEX_DIR=/var/lib/mcp-server/search_index",
                    "SWAGGER_MCP_SEARCH_CACHE_SIZE=128",
                    "SWAGGER_MCP_SEARCH_MAX_RESULTS=1000",
                    "",
                    "# Logging Configuration",
                    "SWAGGER_MCP_LOG_LEVEL=INFO",
                    "SWAGGER_MCP_LOG_FILE=/var/log/mcp-server/server.log",
                    "SWAGGER_MCP_LOG_ROTATION_ENABLED=true",
                    "SWAGGER_MCP_LOG_ROTATION_SIZE=10",
                    "SWAGGER_MCP_LOG_ROTATION_COUNT=5",
                ]
            )
        else:  # staging
            lines.extend(
                [
                    "SWAGGER_MCP_SERVER_HOST=0.0.0.0",
                    "SWAGGER_MCP_SERVER_PORT=8080",
                    "SWAGGER_MCP_SERVER_MAX_CONNECTIONS=50",
                    "SWAGGER_MCP_SERVER_TIMEOUT=30",
                    "# SWAGGER_MCP_SERVER_SSL_ENABLED=false",
                    "",
                    "# Database Configuration",
                    "SWAGGER_MCP_DB_PATH=/opt/mcp-server/staging_mcp_server.db",
                    "SWAGGER_MCP_DB_POOL_SIZE=5",
                    "SWAGGER_MCP_DB_BACKUP_ENABLED=true",
                    "SWAGGER_MCP_DB_BACKUP_INTERVAL=43200",
                    "SWAGGER_MCP_DB_BACKUP_RETENTION=3",
                    "",
                    "# Search Configuration",
                    "SWAGGER_MCP_SEARCH_INDEX_DIR=/opt/mcp-server/staging_search_index",
                    "SWAGGER_MCP_SEARCH_CACHE_SIZE=64",
                    "SWAGGER_MCP_SEARCH_MAX_RESULTS=500",
                    "",
                    "# Logging Configuration",
                    "SWAGGER_MCP_LOG_LEVEL=INFO",
                    "SWAGGER_MCP_LOG_FILE=/var/log/mcp-server/staging_server.log",
                    "SWAGGER_MCP_LOG_ROTATION_ENABLED=true",
                    "SWAGGER_MCP_LOG_ROTATION_SIZE=5",
                    "SWAGGER_MCP_LOG_ROTATION_COUNT=3",
                ]
            )

        return "\n".join(lines)
