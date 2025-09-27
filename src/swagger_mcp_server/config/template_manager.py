"""Configuration template management for different deployment scenarios."""

import copy
from datetime import datetime
from typing import Any, Dict


class ConfigurationTemplateManager:
    """Manages configuration templates for different deployment scenarios."""

    def get_template(self, template_name: str) -> Dict[str, Any]:
        """Get configuration template by name.

        Args:
            template_name: Template name (development, staging, production)

        Returns:
            Configuration dictionary for the template

        Raises:
            ValueError: If template name is not recognized
        """
        templates = {
            "development": self.get_development_template,
            "staging": self.get_staging_template,
            "production": self.get_production_template,
        }

        if template_name not in templates:
            available = ", ".join(templates.keys())
            raise ValueError(
                f"Unknown template '{template_name}'. Available: {available}"
            )

        return templates[template_name]()

    def get_development_template(self) -> Dict[str, Any]:
        """Development environment template with debugging and relaxed settings.

        Optimized for:
        - Local development
        - Debugging and testing
        - Relaxed security settings
        - Verbose logging
        - Small resource usage
        """
        return {
            "server": {
                "host": "localhost",
                "port": 8080,
                "max_connections": 10,
                "timeout": 60,
                "ssl": {"enabled": False, "cert_file": None, "key_file": None},
            },
            "database": {
                "path": "./dev_mcp_server.db",
                "pool_size": 2,
                "timeout": 30,
                "backup": {
                    "enabled": False,
                    "interval": 86400,
                    "retention": 1,
                },
            },
            "search": {
                "engine": "whoosh",
                "index_directory": "./dev_search_index",
                "field_weights": {
                    "endpoint_path": 1.5,
                    "summary": 1.2,
                    "description": 1.0,
                    "parameters": 0.8,
                    "tags": 0.6,
                },
                "performance": {
                    "cache_size_mb": 32,
                    "max_results": 100,
                    "search_timeout": 30,
                },
            },
            "logging": {
                "level": "DEBUG",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "./dev_server.log",
                "rotation": {
                    "enabled": False,
                    "max_size_mb": 5,
                    "backup_count": 2,
                },
            },
            "features": {
                "metrics": {"enabled": True, "endpoint": "/metrics"},
                "health_check": {"enabled": True, "endpoint": "/health"},
                "rate_limiting": {
                    "enabled": False,
                    "requests_per_minute": 1000,
                },
            },
        }

    def get_production_template(self) -> Dict[str, Any]:
        """Production environment template with security and performance optimization.

        Optimized for:
        - Production deployment
        - Security hardening
        - Performance optimization
        - Comprehensive logging
        - Resource efficiency
        """
        return {
            "server": {
                "host": "0.0.0.0",
                "port": 8080,
                "max_connections": 100,
                "timeout": 30,
                "ssl": {
                    "enabled": True,
                    "cert_file": "/etc/ssl/certs/mcp-server.crt",
                    "key_file": "/etc/ssl/private/mcp-server.key",
                },
            },
            "database": {
                "path": "/var/lib/mcp-server/mcp_server.db",
                "pool_size": 10,
                "timeout": 10,
                "backup": {
                    "enabled": True,
                    "interval": 86400,  # 24 hours
                    "retention": 7,
                },
            },
            "search": {
                "engine": "whoosh",
                "index_directory": "/var/lib/mcp-server/search_index",
                "field_weights": {
                    "endpoint_path": 1.5,
                    "summary": 1.2,
                    "description": 1.0,
                    "parameters": 0.8,
                    "tags": 0.6,
                },
                "performance": {
                    "cache_size_mb": 128,
                    "max_results": 1000,
                    "search_timeout": 10,
                },
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "/var/log/mcp-server/server.log",
                "rotation": {
                    "enabled": True,
                    "max_size_mb": 10,
                    "backup_count": 5,
                },
            },
            "features": {
                "metrics": {"enabled": True, "endpoint": "/metrics"},
                "health_check": {"enabled": True, "endpoint": "/health"},
                "rate_limiting": {"enabled": True, "requests_per_minute": 100},
            },
        }

    def get_staging_template(self) -> Dict[str, Any]:
        """Staging environment template balancing production settings with debugging.

        Optimized for:
        - Staging/testing environment
        - Production-like settings
        - Enhanced logging for debugging
        - Moderate resource usage
        - Security testing
        """
        return {
            "server": {
                "host": "0.0.0.0",
                "port": 8080,
                "max_connections": 50,
                "timeout": 30,
                "ssl": {
                    "enabled": False,  # Often disabled in staging for easier testing
                    "cert_file": None,
                    "key_file": None,
                },
            },
            "database": {
                "path": "/opt/mcp-server/staging_mcp_server.db",
                "pool_size": 5,
                "timeout": 15,
                "backup": {
                    "enabled": True,
                    "interval": 43200,  # 12 hours
                    "retention": 3,
                },
            },
            "search": {
                "engine": "whoosh",
                "index_directory": "/opt/mcp-server/staging_search_index",
                "field_weights": {
                    "endpoint_path": 1.5,
                    "summary": 1.2,
                    "description": 1.0,
                    "parameters": 0.8,
                    "tags": 0.6,
                },
                "performance": {
                    "cache_size_mb": 64,
                    "max_results": 500,
                    "search_timeout": 15,
                },
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "/var/log/mcp-server/staging_server.log",
                "rotation": {
                    "enabled": True,
                    "max_size_mb": 5,
                    "backup_count": 3,
                },
            },
            "features": {
                "metrics": {"enabled": True, "endpoint": "/metrics"},
                "health_check": {"enabled": True, "endpoint": "/health"},
                "rate_limiting": {"enabled": True, "requests_per_minute": 200},
            },
        }

    def get_container_template(self) -> Dict[str, Any]:
        """Container deployment template optimized for Docker/Kubernetes.

        Optimized for:
        - Container deployment
        - Environment variable configuration
        - Stateless operation
        - Health checks
        - Minimal file system usage
        """
        return {
            "server": {
                "host": "0.0.0.0",
                "port": 8080,
                "max_connections": 100,
                "timeout": 30,
                "ssl": {
                    "enabled": False,  # Usually handled by ingress/load balancer
                    "cert_file": None,
                    "key_file": None,
                },
            },
            "database": {
                "path": "/data/mcp_server.db",
                "pool_size": 10,
                "timeout": 10,
                "backup": {
                    "enabled": False,  # Usually handled externally in containers
                    "interval": 86400,
                    "retention": 1,
                },
            },
            "search": {
                "engine": "whoosh",
                "index_directory": "/data/search_index",
                "field_weights": {
                    "endpoint_path": 1.5,
                    "summary": 1.2,
                    "description": 1.0,
                    "parameters": 0.8,
                    "tags": 0.6,
                },
                "performance": {
                    "cache_size_mb": 64,
                    "max_results": 1000,
                    "search_timeout": 10,
                },
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": None,  # Log to stdout for container logs
                "rotation": {
                    "enabled": False,
                    "max_size_mb": 10,
                    "backup_count": 1,
                },
            },
            "features": {
                "metrics": {"enabled": True, "endpoint": "/metrics"},
                "health_check": {"enabled": True, "endpoint": "/health"},
                "rate_limiting": {
                    "enabled": False,  # Usually handled by ingress
                    "requests_per_minute": 100,
                },
            },
        }

    def get_available_templates(self) -> Dict[str, str]:
        """Get list of available templates with descriptions.

        Returns:
            Dict mapping template names to descriptions
        """
        return {
            "development": "Local development with debugging and relaxed settings",
            "staging": "Testing environment balancing production settings with debugging",
            "production": "Production deployment with security and performance optimization",
            "container": "Container deployment optimized for Docker/Kubernetes",
        }

    def customize_template(
        self, template: Dict[str, Any], customizations: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply customizations to a template.

        Args:
            template: Base template configuration
            customizations: Customizations to apply (using dot notation)

        Returns:
            Customized configuration
        """
        from .env_extractor import EnvironmentConfigExtractor

        # Deep copy to avoid modifying the original template
        customized = copy.deepcopy(template)
        extractor = EnvironmentConfigExtractor()

        # Apply each customization
        for key, value in customizations.items():
            extractor.set_nested_config(customized, key, value)

        return customized

    def generate_template_documentation(self, template_name: str) -> str:
        """Generate documentation for a template.

        Args:
            template_name: Name of the template

        Returns:
            Markdown documentation for the template
        """
        try:
            template = self.get_template(template_name)
        except ValueError as e:
            return f"Error: {e}"

        descriptions = self.get_available_templates()
        description = descriptions.get(
            template_name, "No description available"
        )

        doc = f"""# {template_name.title()} Configuration Template

## Description
{description}

## Configuration Summary

### Server Settings
- Host: {template['server']['host']}
- Port: {template['server']['port']}
- Max Connections: {template['server']['max_connections']}
- SSL Enabled: {template['server']['ssl']['enabled']}

### Database Settings
- Path: {template['database']['path']}
- Pool Size: {template['database']['pool_size']}
- Backup Enabled: {template['database']['backup']['enabled']}

### Search Settings
- Engine: {template['search']['engine']}
- Index Directory: {template['search']['index_directory']}
- Cache Size: {template['search']['performance']['cache_size_mb']}MB

### Logging Settings
- Level: {template['logging']['level']}
- File: {template['logging']['file'] or 'Console only'}
- Rotation: {template['logging']['rotation']['enabled']}

### Features
- Metrics: {template['features']['metrics']['enabled']}
- Health Check: {template['features']['health_check']['enabled']}
- Rate Limiting: {template['features']['rate_limiting']['enabled']}

## Usage

```bash
# Initialize configuration with this template
swagger-mcp-server config init --template {template_name}

# View the configuration
swagger-mcp-server config show
```

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return doc

    def validate_template(
        self, template: Dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Validate a configuration template.

        Args:
            template: Configuration template to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        from .config_schema import ConfigurationSchema

        errors = []

        # Validate each configuration value
        for key in ConfigurationSchema.get_all_configuration_keys():
            from .env_extractor import EnvironmentConfigExtractor

            extractor = EnvironmentConfigExtractor()
            value = extractor.get_nested_config_value(template, key)

            if value is not None:
                (
                    is_valid,
                    error_msg,
                ) = ConfigurationSchema.validate_configuration_value(
                    key, value
                )
                if not is_valid:
                    errors.append(f"{key}: {error_msg}")

        return len(errors) == 0, errors
