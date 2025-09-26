"""Tests for configuration template management."""

import pytest
from swagger_mcp_server.config import ConfigurationTemplateManager


class TestConfigurationTemplateManager:
    """Test cases for ConfigurationTemplateManager."""

    @pytest.fixture
    def template_manager(self):
        """Create ConfigurationTemplateManager instance."""
        return ConfigurationTemplateManager()

    def test_get_development_template(self, template_manager):
        """Test development template retrieval."""
        template = template_manager.get_development_template()

        assert template is not None
        assert template["server"]["host"] == "localhost"
        assert template["server"]["port"] == 8080
        assert template["server"]["max_connections"] == 10
        assert template["server"]["ssl"]["enabled"] is False
        assert template["logging"]["level"] == "DEBUG"
        assert template["features"]["rate_limiting"]["enabled"] is False

    def test_get_production_template(self, template_manager):
        """Test production template retrieval."""
        template = template_manager.get_production_template()

        assert template is not None
        assert template["server"]["host"] == "0.0.0.0"
        assert template["server"]["port"] == 8080
        assert template["server"]["max_connections"] == 100
        assert template["server"]["ssl"]["enabled"] is True
        assert template["logging"]["level"] == "INFO"
        assert template["features"]["rate_limiting"]["enabled"] is True

    def test_get_staging_template(self, template_manager):
        """Test staging template retrieval."""
        template = template_manager.get_staging_template()

        assert template is not None
        assert template["server"]["host"] == "0.0.0.0"
        assert template["server"]["port"] == 8080
        assert template["server"]["max_connections"] == 50
        assert template["server"]["ssl"]["enabled"] is False  # Disabled for easier testing
        assert template["logging"]["level"] == "INFO"
        assert template["features"]["rate_limiting"]["enabled"] is True

    def test_get_container_template(self, template_manager):
        """Test container template retrieval."""
        template = template_manager.get_container_template()

        assert template is not None
        assert template["server"]["host"] == "0.0.0.0"
        assert template["server"]["port"] == 8080
        assert template["server"]["ssl"]["enabled"] is False  # Handled by ingress
        assert template["database"]["path"] == "/data/mcp_server.db"
        assert template["search"]["index_directory"] == "/data/search_index"
        assert template["logging"]["file"] is None  # Log to stdout
        assert template["features"]["rate_limiting"]["enabled"] is False  # Handled by ingress

    def test_get_template_by_name(self, template_manager):
        """Test getting templates by name."""
        dev_template = template_manager.get_template("development")
        assert dev_template["logging"]["level"] == "DEBUG"

        prod_template = template_manager.get_template("production")
        assert prod_template["logging"]["level"] == "INFO"

        staging_template = template_manager.get_template("staging")
        assert staging_template["server"]["max_connections"] == 50

        container_template = template_manager.get_template("container")
        assert container_template["database"]["path"] == "/data/mcp_server.db"

    def test_get_template_invalid_name(self, template_manager):
        """Test getting template with invalid name."""
        with pytest.raises(ValueError) as exc_info:
            template_manager.get_template("invalid_template")

        assert "Unknown template" in str(exc_info.value)
        assert "development, staging, production" in str(exc_info.value)

    def test_get_available_templates(self, template_manager):
        """Test getting list of available templates."""
        templates = template_manager.get_available_templates()

        assert isinstance(templates, dict)
        assert "development" in templates
        assert "staging" in templates
        assert "production" in templates
        assert "container" in templates

        # Check descriptions exist
        assert "local development" in templates["development"].lower()
        assert "production deployment" in templates["production"].lower()
        assert "testing environment" in templates["staging"].lower()
        assert "container deployment" in templates["container"].lower()

    def test_customize_template(self, template_manager):
        """Test template customization."""
        base_template = template_manager.get_development_template()

        customizations = {
            "server.port": 9000,
            "logging.level": "WARNING",
            "features.metrics.enabled": False
        }

        customized = template_manager.customize_template(base_template, customizations)

        # Check customizations applied
        assert customized["server"]["port"] == 9000
        assert customized["logging"]["level"] == "WARNING"
        assert customized["features"]["metrics"]["enabled"] is False

        # Check original values preserved
        assert customized["server"]["host"] == "localhost"
        assert customized["server"]["max_connections"] == 10

        # Ensure original template wasn't modified
        assert base_template["server"]["port"] == 8080
        assert base_template["logging"]["level"] == "DEBUG"

    def test_customize_template_nested_creation(self, template_manager):
        """Test template customization with creating new nested structures."""
        base_template = template_manager.get_development_template()

        customizations = {
            "new_section.nested.value": "test",
            "server.new_setting": True
        }

        customized = template_manager.customize_template(base_template, customizations)

        # Check new nested structure created
        assert customized["new_section"]["nested"]["value"] == "test"
        assert customized["server"]["new_setting"] is True

    def test_generate_template_documentation(self, template_manager):
        """Test template documentation generation."""
        doc = template_manager.generate_template_documentation("development")

        assert "# Development Configuration Template" in doc
        assert "Host: localhost" in doc
        assert "Port: 8080" in doc
        assert "SSL Enabled: False" in doc
        assert "Level: DEBUG" in doc
        assert "swagger-mcp-server config init --template development" in doc

    def test_generate_template_documentation_production(self, template_manager):
        """Test production template documentation generation."""
        doc = template_manager.generate_template_documentation("production")

        assert "# Production Configuration Template" in doc
        assert "Host: 0.0.0.0" in doc
        assert "SSL Enabled: True" in doc
        assert "Level: INFO" in doc

    def test_generate_template_documentation_invalid(self, template_manager):
        """Test documentation generation for invalid template."""
        doc = template_manager.generate_template_documentation("invalid")
        assert "Error:" in doc

    def test_validate_template_valid(self, template_manager):
        """Test validation of valid templates."""
        dev_template = template_manager.get_development_template()
        is_valid, errors = template_manager.validate_template(dev_template)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_template_invalid(self, template_manager):
        """Test validation of invalid template."""
        invalid_template = {
            "server": {
                "port": 99,  # Invalid port (too low)
                "host": "",  # Invalid empty host
                "max_connections": -1  # Invalid negative connections
            },
            "logging": {
                "level": "INVALID_LEVEL"
            }
        }

        is_valid, errors = template_manager.validate_template(invalid_template)

        assert is_valid is False
        assert len(errors) > 0
        assert any("port" in error for error in errors)
        assert any("host" in error for error in errors)
        assert any("level" in error for error in errors)

    def test_template_consistency(self, template_manager):
        """Test that all templates have consistent structure."""
        templates = ["development", "staging", "production", "container"]

        required_sections = ["server", "database", "search", "logging", "features"]
        required_server_keys = ["host", "port", "max_connections", "timeout", "ssl"]

        for template_name in templates:
            template = template_manager.get_template(template_name)

            # Check all required sections exist
            for section in required_sections:
                assert section in template, f"Template {template_name} missing section {section}"

            # Check server section has required keys
            for key in required_server_keys:
                assert key in template["server"], f"Template {template_name} missing server.{key}"

            # Check SSL subsection
            ssl_section = template["server"]["ssl"]
            assert "enabled" in ssl_section
            assert "cert_file" in ssl_section
            assert "key_file" in ssl_section

    def test_template_environment_specific_values(self, template_manager):
        """Test that templates have appropriate environment-specific values."""
        dev_template = template_manager.get_development_template()
        prod_template = template_manager.get_production_template()
        staging_template = template_manager.get_staging_template()
        container_template = template_manager.get_container_template()

        # Development should have debugging features
        assert dev_template["logging"]["level"] == "DEBUG"
        assert dev_template["server"]["max_connections"] == 10  # Low for development
        assert dev_template["features"]["rate_limiting"]["enabled"] is False

        # Production should be secure and performant
        assert prod_template["server"]["ssl"]["enabled"] is True
        assert prod_template["logging"]["level"] == "INFO"
        assert prod_template["features"]["rate_limiting"]["enabled"] is True
        assert prod_template["server"]["max_connections"] == 100

        # Staging should balance production and development
        assert staging_template["server"]["ssl"]["enabled"] is False  # For testing
        assert staging_template["logging"]["level"] == "INFO"
        assert staging_template["server"]["max_connections"] == 50

        # Container should be stateless
        assert container_template["logging"]["file"] is None
        assert container_template["database"]["backup"]["enabled"] is False
        assert "/data/" in container_template["database"]["path"]

    def test_template_deep_copy_independence(self, template_manager):
        """Test that template modifications don't affect cached templates."""
        template1 = template_manager.get_development_template()
        template2 = template_manager.get_development_template()

        # Modify first template
        template1["server"]["port"] = 9999
        template1["server"]["new_key"] = "test"

        # Second template should be unaffected
        assert template2["server"]["port"] == 8080
        assert "new_key" not in template2["server"]

    def test_template_customization_preserves_original(self, template_manager):
        """Test that template customization preserves the original template."""
        original = template_manager.get_development_template()
        original_port = original["server"]["port"]

        customizations = {"server.port": 9000}
        customized = template_manager.customize_template(original, customizations)

        # Original should be unchanged
        assert original["server"]["port"] == original_port
        # Customized should have new value
        assert customized["server"]["port"] == 9000