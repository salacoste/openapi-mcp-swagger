"""Configuration schema definition and validation."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ConfigurationSchema:
    """Configuration schema definition with validation rules."""

    # Core configuration schema with defaults and validation
    SCHEMA = {
        "server": {
            "type": "dict",
            "schema": {
                "host": {
                    "type": "string",
                    "default": "localhost",
                    "regex": r"^[a-zA-Z0-9.-]+$",
                    "help": "Server host address. Use '0.0.0.0' to accept connections from any IP.",
                },
                "port": {
                    "type": "integer",
                    "min": 1024,
                    "max": 65535,
                    "default": 8080,
                    "help": "Server port number. Must be between 1024-65535.",
                },
                "max_connections": {
                    "type": "integer",
                    "min": 1,
                    "max": 1000,
                    "default": 100,
                    "help": "Maximum number of concurrent client connections.",
                },
                "timeout": {
                    "type": "integer",
                    "min": 1,
                    "max": 300,
                    "default": 30,
                    "help": "Connection timeout in seconds.",
                },
                "ssl": {
                    "type": "dict",
                    "schema": {
                        "enabled": {
                            "type": "boolean",
                            "default": False,
                            "help": "Enable SSL/TLS encryption for secure connections.",
                        },
                        "cert_file": {
                            "type": "string",
                            "nullable": True,
                            "default": None,
                            "help": "Path to SSL certificate file (required if SSL enabled).",
                        },
                        "key_file": {
                            "type": "string",
                            "nullable": True,
                            "default": None,
                            "help": "Path to SSL private key file (required if SSL enabled).",
                        },
                    },
                },
            },
        },
        "database": {
            "type": "dict",
            "schema": {
                "path": {
                    "type": "string",
                    "default": "./mcp_server.db",
                    "help": "SQLite database file path. Can be relative or absolute.",
                },
                "pool_size": {
                    "type": "integer",
                    "min": 1,
                    "max": 50,
                    "default": 5,
                    "help": "Database connection pool size for concurrent operations.",
                },
                "timeout": {
                    "type": "integer",
                    "min": 1,
                    "max": 60,
                    "default": 10,
                    "help": "Database operation timeout in seconds.",
                },
                "backup": {
                    "type": "dict",
                    "schema": {
                        "enabled": {
                            "type": "boolean",
                            "default": True,
                            "help": "Enable automatic database backups.",
                        },
                        "interval": {
                            "type": "integer",
                            "min": 3600,
                            "default": 86400,
                            "help": "Backup interval in seconds (default: 24 hours).",
                        },
                        "retention": {
                            "type": "integer",
                            "min": 1,
                            "default": 7,
                            "help": "Number of backup files to retain.",
                        },
                    },
                },
            },
        },
        "search": {
            "type": "dict",
            "schema": {
                "engine": {
                    "type": "string",
                    "allowed": ["whoosh"],
                    "default": "whoosh",
                    "help": "Search engine backend (currently only Whoosh is supported).",
                },
                "index_directory": {
                    "type": "string",
                    "default": "./search_index",
                    "help": "Directory for search index files.",
                },
                "field_weights": {
                    "type": "dict",
                    "schema": {
                        "endpoint_path": {
                            "type": "float",
                            "min": 0.1,
                            "max": 3.0,
                            "default": 1.5,
                            "help": "Weight for endpoint path matching in search results.",
                        },
                        "summary": {
                            "type": "float",
                            "min": 0.1,
                            "max": 3.0,
                            "default": 1.2,
                            "help": "Weight for endpoint summary in search ranking.",
                        },
                        "description": {
                            "type": "float",
                            "min": 0.1,
                            "max": 3.0,
                            "default": 1.0,
                            "help": "Weight for description text in search ranking.",
                        },
                        "parameters": {
                            "type": "float",
                            "min": 0.1,
                            "max": 3.0,
                            "default": 0.8,
                            "help": "Weight for parameter matching in search results.",
                        },
                        "tags": {
                            "type": "float",
                            "min": 0.1,
                            "max": 3.0,
                            "default": 0.6,
                            "help": "Weight for tag matching in search results.",
                        },
                    },
                },
                "performance": {
                    "type": "dict",
                    "schema": {
                        "cache_size_mb": {
                            "type": "integer",
                            "min": 16,
                            "max": 1024,
                            "default": 64,
                            "help": "Search index cache size in megabytes.",
                        },
                        "max_results": {
                            "type": "integer",
                            "min": 10,
                            "max": 10000,
                            "default": 1000,
                            "help": "Maximum number of search results to return.",
                        },
                        "search_timeout": {
                            "type": "integer",
                            "min": 1,
                            "max": 30,
                            "default": 10,
                            "help": "Search operation timeout in seconds.",
                        },
                    },
                },
            },
        },
        "logging": {
            "type": "dict",
            "schema": {
                "level": {
                    "type": "string",
                    "allowed": ["DEBUG", "INFO", "WARNING", "ERROR"],
                    "default": "INFO",
                    "help": "Logging verbosity: DEBUG, INFO, WARNING, ERROR.",
                },
                "format": {
                    "type": "string",
                    "default": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "help": "Log message format string.",
                },
                "file": {
                    "type": "string",
                    "nullable": True,
                    "default": None,
                    "help": "Log file path. If not specified, logs to console only.",
                },
                "rotation": {
                    "type": "dict",
                    "schema": {
                        "enabled": {
                            "type": "boolean",
                            "default": False,
                            "help": "Enable log file rotation.",
                        },
                        "max_size_mb": {
                            "type": "integer",
                            "min": 1,
                            "max": 1000,
                            "default": 10,
                            "help": "Maximum log file size in megabytes before rotation.",
                        },
                        "backup_count": {
                            "type": "integer",
                            "min": 1,
                            "max": 10,
                            "default": 5,
                            "help": "Number of rotated log files to keep.",
                        },
                    },
                },
            },
        },
        "features": {
            "type": "dict",
            "schema": {
                "metrics": {
                    "type": "dict",
                    "schema": {
                        "enabled": {
                            "type": "boolean",
                            "default": True,
                            "help": "Enable performance metrics collection.",
                        },
                        "endpoint": {
                            "type": "string",
                            "default": "/metrics",
                            "help": "Metrics endpoint path.",
                        },
                    },
                },
                "health_check": {
                    "type": "dict",
                    "schema": {
                        "enabled": {
                            "type": "boolean",
                            "default": True,
                            "help": "Enable health check endpoint.",
                        },
                        "endpoint": {
                            "type": "string",
                            "default": "/health",
                            "help": "Health check endpoint path.",
                        },
                    },
                },
                "rate_limiting": {
                    "type": "dict",
                    "schema": {
                        "enabled": {
                            "type": "boolean",
                            "default": False,
                            "help": "Enable rate limiting for API requests.",
                        },
                        "requests_per_minute": {
                            "type": "integer",
                            "min": 1,
                            "max": 10000,
                            "default": 100,
                            "help": "Maximum requests per minute per client.",
                        },
                    },
                },
            },
        },
    }

    @classmethod
    def get_default_configuration(cls) -> Dict[str, Any]:
        """Generate default configuration from schema."""
        return cls._extract_defaults(cls.SCHEMA)

    @classmethod
    def _extract_defaults(cls, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively extract default values from schema."""
        defaults = {}

        for key, definition in schema.items():
            if isinstance(definition, dict):
                if definition.get("type") == "dict" and "schema" in definition:
                    # Nested dictionary
                    defaults[key] = cls._extract_defaults(definition["schema"])
                elif "default" in definition:
                    # Simple value with default
                    defaults[key] = definition["default"]

        return defaults

    @classmethod
    def get_configuration_help(cls, key: str) -> Optional[str]:
        """Get help text for a configuration key using dot notation."""
        keys = key.split(".")
        current_schema = cls.SCHEMA

        try:
            for k in keys:
                if k in current_schema:
                    if isinstance(current_schema[k], dict):
                        if "help" in current_schema[k]:
                            return current_schema[k]["help"]
                        elif "schema" in current_schema[k]:
                            current_schema = current_schema[k]["schema"]
                        else:
                            return None
                    else:
                        return None
                else:
                    return None
        except (KeyError, TypeError):
            return None

        return f"No help available for '{key}'"

    @classmethod
    def get_all_configuration_keys(cls) -> list[str]:
        """Get all available configuration keys in dot notation."""
        keys = []
        cls._collect_keys(cls.SCHEMA, "", keys)
        return sorted(keys)

    @classmethod
    def _collect_keys(
        cls, schema: Dict[str, Any], prefix: str, keys: list[str]
    ):
        """Recursively collect all configuration keys."""
        for key, definition in schema.items():
            current_key = f"{prefix}.{key}" if prefix else key

            if isinstance(definition, dict):
                if definition.get("type") == "dict" and "schema" in definition:
                    # Nested dictionary - recurse
                    cls._collect_keys(definition["schema"], current_key, keys)
                elif "default" in definition or "type" in definition:
                    # Leaf value
                    keys.append(current_key)

    @classmethod
    def validate_configuration_value(
        cls, key: str, value: Any
    ) -> tuple[bool, Optional[str]]:
        """Validate a single configuration value."""
        keys = key.split(".")
        current_schema = cls.SCHEMA

        try:
            # Navigate to the target schema
            for k in keys[:-1]:
                if k in current_schema and "schema" in current_schema[k]:
                    current_schema = current_schema[k]["schema"]
                else:
                    return False, f"Invalid configuration path: {key}"

            # Get the final key definition
            final_key = keys[-1]
            if final_key not in current_schema:
                return False, f"Unknown configuration key: {key}"

            definition = current_schema[final_key]

            # Validate based on type and constraints
            return cls._validate_value(value, definition, key)

        except Exception as e:
            return False, f"Validation error for {key}: {str(e)}"

    @classmethod
    def _validate_value(
        cls, value: Any, definition: Dict[str, Any], key: str
    ) -> tuple[bool, Optional[str]]:
        """Validate a value against its schema definition."""
        # Type validation
        expected_type = definition.get("type")

        if expected_type == "string" and not isinstance(value, str):
            return False, f"{key} must be a string"
        elif expected_type == "integer" and not isinstance(value, int):
            return False, f"{key} must be an integer"
        elif expected_type == "float" and not isinstance(value, (int, float)):
            return False, f"{key} must be a number"
        elif expected_type == "boolean" and not isinstance(value, bool):
            return False, f"{key} must be a boolean"

        # Range validation for numbers
        if expected_type in ["integer", "float"]:
            if "min" in definition and value < definition["min"]:
                return False, f"{key} must be at least {definition['min']}"
            if "max" in definition and value > definition["max"]:
                return False, f"{key} must be at most {definition['max']}"

        # Allowed values validation
        if "allowed" in definition and value not in definition["allowed"]:
            allowed = ", ".join(str(v) for v in definition["allowed"])
            return False, f"{key} must be one of: {allowed}"

        # Regex validation for strings
        if expected_type == "string" and "regex" in definition:
            import re

            if not re.match(definition["regex"], value):
                return False, f"{key} has invalid format"

        return True, None
