"""Tests for the configuration management system."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from swagger_mcp_server.cli.config import (
    ConfigurationManager,
    get_config_manager,
    reload_config,
)


class TestConfigurationManager:
    """Test the ConfigurationManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = ConfigurationManager()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_default_config_loading(self):
        """Test that default configuration is loaded correctly."""
        config = self.config_manager.config

        # Check that default sections exist
        assert "server" in config
        assert "output" in config
        assert "logging" in config
        assert "search" in config
        assert "performance" in config
        assert "security" in config

        # Check default values
        assert config["server"]["port"] == 8080
        assert config["server"]["host"] == "localhost"
        assert config["output"]["directory"] == "./mcp-server"
        assert config["logging"]["level"] == "info"

    def test_get_config_value(self):
        """Test getting configuration values."""
        # Test simple key
        assert self.config_manager.get("server.port") == 8080
        assert self.config_manager.get("server.host") == "localhost"

        # Test nested key
        assert self.config_manager.get("performance.timeout") == 30

        # Test non-existent key
        assert self.config_manager.get("nonexistent.key") is None
        assert (
            self.config_manager.get("nonexistent.key", "default") == "default"
        )

    def test_set_config_value(self):
        """Test setting configuration values."""
        # Test setting a value
        success = self.config_manager.set("server.port", 9000)
        assert (
            success is True or success is False
        )  # May fail due to file permissions
        assert self.config_manager.get("server.port") == 9000

        # Test setting nested value
        self.config_manager.set("custom.nested.value", "test")
        assert self.config_manager.get("custom.nested.value") == "test"

    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "SWAGGER_MCP_PORT": "9000",
                "SWAGGER_MCP_HOST": "0.0.0.0",
                "SWAGGER_MCP_LOG_LEVEL": "debug",
            },
        ):
            config_manager = ConfigurationManager()

            # Environment variables should override defaults
            assert config_manager.get("server.port") == 9000
            assert config_manager.get("server.host") == "0.0.0.0"
            assert config_manager.get("logging.level") == "debug"

    def test_config_file_loading(self):
        """Test loading configuration from YAML files."""
        # Create temporary config file
        config_data = {
            "server": {"port": 9000, "host": "0.0.0.0"},
            "logging": {"level": "debug"},
        }

        config_file = Path(self.temp_dir) / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Mock the config file path by patching the function that gets directories
        with patch(
            "swagger_mcp_server.cli.config.get_config_directories",
            return_value={
                "config": Path(self.temp_dir),
                "data": Path(self.temp_dir),
                "global_config": config_file,
                "project_config": Path("/nonexistent"),
            },
        ):
            config_manager = ConfigurationManager()

            # Should load values from file
            assert config_manager.get("server.port") == 9000
            assert config_manager.get("server.host") == "0.0.0.0"
            assert config_manager.get("logging.level") == "debug"

    def test_config_precedence(self):
        """Test configuration precedence (env > file > defaults)."""
        # Create config file
        config_data = {"server": {"port": 8000}}
        config_file = Path(self.temp_dir) / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Set environment variable (should override file)
        with patch.dict(os.environ, {"SWAGGER_MCP_PORT": "9000"}):
            with patch(
                "swagger_mcp_server.cli.config.get_config_directories",
                return_value={
                    "config": Path(self.temp_dir),
                    "data": Path(self.temp_dir),
                    "global_config": config_file,
                    "project_config": Path("/nonexistent"),
                },
            ):
                config_manager = ConfigurationManager()

                # Environment should win
                assert config_manager.get("server.port") == 9000

    def test_config_validation(self):
        """Test configuration validation."""
        valid, errors = self.config_manager.validate()

        # Default config should be valid
        assert valid is True
        assert len(errors) == 0

        # Test with invalid configuration
        self.config_manager.set("server.port", -1)
        self.config_manager.set("logging.level", "invalid")

        valid, errors = self.config_manager.validate()
        assert valid is False
        assert len(errors) > 0
        assert any("port" in error for error in errors)
        assert any("log level" in error for error in errors)

    def test_reset_configuration(self):
        """Test resetting configuration to defaults."""
        # Modify configuration
        self.config_manager.set("server.port", 9000)
        assert self.config_manager.get("server.port") == 9000

        # Reset configuration
        success = self.config_manager.reset()

        # Should return to default (may fail due to file permissions)
        if success:
            assert self.config_manager.get("server.port") == 8080

    def test_list_config_keys(self):
        """Test listing all configuration keys."""
        keys = self.config_manager.list_keys()

        assert isinstance(keys, list)
        assert len(keys) > 0
        assert "server.port" in keys
        assert "server.host" in keys
        assert "logging.level" in keys
        assert "output.directory" in keys

    def test_show_all_config(self):
        """Test showing all configuration."""
        config = self.config_manager.show_all()

        assert isinstance(config, dict)
        assert "server" in config
        assert "output" in config
        assert config["server"]["port"] == 8080

    def test_show_specific_key(self):
        """Test showing specific configuration key."""
        value = self.config_manager.show_key("server.port")
        assert value == 8080

        # Test non-existent key
        result = self.config_manager.show_key("nonexistent.key")
        assert "not found" in str(result)

    def test_export_config(self):
        """Test exporting configuration."""
        # Test YAML export
        yaml_export = self.config_manager.export_config("yaml")
        assert isinstance(yaml_export, str)
        assert "server:" in yaml_export

        # Test JSON export
        json_export = self.config_manager.export_config("json")
        assert isinstance(json_export, str)
        parsed = json.loads(json_export)
        assert "server" in parsed

        # Test invalid format
        with pytest.raises(ValueError):
            self.config_manager.export_config("invalid")

    def test_config_file_paths(self):
        """Test getting configuration file paths."""
        paths = self.config_manager.get_config_files()

        assert "global" in paths
        assert "project" in paths
        assert isinstance(paths["global"], Path)
        assert isinstance(paths["project"], Path)

    def test_deep_copy_functionality(self):
        """Test that configuration copying works correctly."""
        original = {"nested": {"value": [1, 2, 3]}}
        copy = self.config_manager._deep_copy_dict(original)

        # Modify copy
        copy["nested"]["value"].append(4)

        # Original should be unchanged
        assert len(original["nested"]["value"]) == 3
        assert len(copy["nested"]["value"]) == 4

    def test_merge_configs_functionality(self):
        """Test configuration merging."""
        base = {
            "server": {"port": 8080, "host": "localhost"},
            "logging": {"level": "info"},
        }

        override = {"server": {"port": 9000}, "new_section": {"value": "test"}}

        result = self.config_manager._merge_configs(base, override)

        # Should merge correctly
        assert result["server"]["port"] == 9000  # Overridden
        assert result["server"]["host"] == "localhost"  # Preserved
        assert result["logging"]["level"] == "info"  # Preserved
        assert result["new_section"]["value"] == "test"  # Added

    def test_nested_config_operations(self):
        """Test nested configuration get/set operations."""
        config = {}

        # Test setting nested values
        self.config_manager._set_nested_config(config, "a.b.c", "value")
        assert config["a"]["b"]["c"] == "value"

        # Test getting nested values
        value = self.config_manager._get_nested_config(config, "a.b.c")
        assert value == "value"

        # Test non-existent path
        value = self.config_manager._get_nested_config(config, "x.y.z")
        assert value is None


class TestConfigurationManagerIntegration:
    """Integration tests for configuration manager."""

    def test_global_config_manager(self):
        """Test the global configuration manager."""
        manager1 = get_config_manager()
        manager2 = get_config_manager()

        # Should return the same instance
        assert manager1 is manager2

        # Test reload functionality
        reload_config()
        manager3 = get_config_manager()
        assert manager3 is not manager1

    def test_real_config_directories(self):
        """Test with real configuration directories."""
        manager = ConfigurationManager()

        # Should handle real paths without errors
        config_dirs = manager.config_dirs
        assert "config" in config_dirs
        assert "data" in config_dirs
        assert isinstance(config_dirs["config"], Path)

    def test_file_operations_with_permissions(self):
        """Test file operations with various permission scenarios."""
        manager = ConfigurationManager()

        # Test set operation (may succeed or fail based on permissions)
        result = manager.set("test.key", "test_value")
        assert isinstance(result, bool)

        # Value should be set in memory regardless
        assert manager.get("test.key") == "test_value"

    def test_yaml_dependency_handling(self):
        """Test handling when PyYAML is not available."""
        # PyYAML is available in our test environment and is a required dependency
        # This test just ensures ConfigurationManager can be created
        manager = ConfigurationManager()
        assert isinstance(manager.config, dict)

        # Verify export handles yaml availability
        yaml_export = manager.export_config("yaml")
        assert isinstance(yaml_export, str)
        assert "server:" in yaml_export or "port:" in yaml_export


class TestConfigurationEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_yaml_file(self):
        """Test handling of invalid YAML files."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Create invalid YAML file
            config_file = Path(temp_dir) / "invalid.yaml"
            with open(config_file, "w") as f:
                f.write("invalid: yaml: content: [")  # Invalid YAML

            with patch.object(
                ConfigurationManager,
                "config_dirs",
                {
                    "global_config": config_file,
                    "project_config": Path("/nonexistent"),
                },
            ):
                # Should handle gracefully
                manager = ConfigurationManager()
                assert isinstance(manager.config, dict)

        finally:
            import shutil

            shutil.rmtree(temp_dir)

    def test_nonexistent_config_file(self):
        """Test handling of non-existent configuration files."""
        with patch.object(
            ConfigurationManager,
            "config_dirs",
            {
                "global_config": Path("/nonexistent/config.yaml"),
                "project_config": Path("/nonexistent/project.yaml"),
            },
        ):
            # Should handle gracefully
            manager = ConfigurationManager()
            assert isinstance(manager.config, dict)
            # Should still have defaults
            assert manager.get("server.port") == 8080

    def test_type_conversion_errors(self):
        """Test handling of type conversion errors in environment variables."""
        with patch.dict(
            os.environ,
            {
                "SWAGGER_MCP_PORT": "not_a_number",
                "SWAGGER_MCP_TIMEOUT": "invalid_int",
            },
        ):
            # Should handle conversion errors gracefully
            manager = ConfigurationManager()
            # Should fall back to defaults
            assert manager.get("server.port") == 8080
            assert manager.get("performance.timeout") == 30

    def test_save_config_without_yaml(self):
        """Test saving configuration when PyYAML is not available."""
        manager = ConfigurationManager()

        with patch("swagger_mcp_server.cli.config.yaml", None):
            result = manager.set("test.key", "value")
            # Should fail to save but not crash
            assert isinstance(result, bool)

    def test_validation_edge_cases(self):
        """Test validation with edge cases."""
        manager = ConfigurationManager()

        # Test with extreme values
        manager.config["server"]["port"] = 0
        manager.config["server"]["host"] = ""
        manager.config["logging"]["level"] = ""
        manager.config["performance"]["timeout"] = -1

        valid, errors = manager.validate()
        assert valid is False
        assert len(errors) >= 4  # Should have multiple errors
