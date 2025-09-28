"""Tests for environment configuration extraction."""

import os
from unittest.mock import patch

import pytest

from swagger_mcp_server.config import EnvironmentConfigExtractor


class TestEnvironmentConfigExtractor:
    """Test cases for EnvironmentConfigExtractor."""

    @pytest.fixture
    def extractor(self):
        """Create EnvironmentConfigExtractor instance."""
        return EnvironmentConfigExtractor()

    def test_extract_environment_config_empty(self, extractor):
        """Test extracting environment config when no variables are set."""
        with patch.dict(os.environ, {}, clear=True):
            config = extractor.extract_environment_config()
            assert config == {}

    def test_extract_environment_config_with_variables(self, extractor):
        """Test extracting environment configuration with variables set."""
        env_vars = {
            "SWAGGER_MCP_SERVER_HOST": "test.example.com",
            "SWAGGER_MCP_SERVER_PORT": "9000",
            "SWAGGER_MCP_SERVER_MAX_CONNECTIONS": "200",
            "SWAGGER_MCP_SERVER_TIMEOUT": "60",
            "SWAGGER_MCP_SERVER_SSL_ENABLED": "true",
            "SWAGGER_MCP_DB_PATH": "/custom/path/db.sqlite",
            "SWAGGER_MCP_DB_POOL_SIZE": "10",
            "SWAGGER_MCP_LOG_LEVEL": "DEBUG",
            "SWAGGER_MCP_LOG_FILE": "/var/log/server.log",
            "SWAGGER_MCP_SEARCH_ENGINE": "whoosh",
        }

        with patch.dict(os.environ, env_vars):
            config = extractor.extract_environment_config()

            # Check server configuration
            assert config["server"]["host"] == "test.example.com"
            assert config["server"]["port"] == 9000
            assert config["server"]["max_connections"] == 200
            assert config["server"]["timeout"] == 60
            assert config["server"]["ssl"]["enabled"] is True

            # Check database configuration
            assert config["database"]["path"] == "/custom/path/db.sqlite"
            assert config["database"]["pool_size"] == 10

            # Check logging configuration
            assert config["logging"]["level"] == "DEBUG"
            assert config["logging"]["file"] == "/var/log/server.log"

            # Check search configuration
            assert config["search"]["engine"] == "whoosh"

    def test_type_conversion_integers(self, extractor):
        """Test type conversion for integer values."""
        env_vars = {
            "SWAGGER_MCP_SERVER_PORT": "8080",
            "SWAGGER_MCP_SERVER_MAX_CONNECTIONS": "100",
            "SWAGGER_MCP_DB_POOL_SIZE": "5",
            "SWAGGER_MCP_SEARCH_CACHE_SIZE": "64",
        }

        with patch.dict(os.environ, env_vars):
            config = extractor.extract_environment_config()

            assert isinstance(config["server"]["port"], int)
            assert isinstance(config["server"]["max_connections"], int)
            assert isinstance(config["database"]["pool_size"], int)
            assert isinstance(config["search"]["performance"]["cache_size_mb"], int)

    def test_type_conversion_floats(self, extractor):
        """Test type conversion for float values."""
        env_vars = {
            "SWAGGER_MCP_SEARCH_WEIGHT_ENDPOINT": "1.5",
            "SWAGGER_MCP_SEARCH_WEIGHT_DESC": "1.0",
        }

        with patch.dict(os.environ, env_vars):
            config = extractor.extract_environment_config()

            assert isinstance(config["search"]["field_weights"]["endpoint_path"], float)
            assert isinstance(config["search"]["field_weights"]["description"], float)

    def test_type_conversion_booleans(self, extractor):
        """Test type conversion for boolean values."""
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "on", "ON"]
        false_values = [
            "false",
            "False",
            "FALSE",
            "0",
            "no",
            "No",
            "off",
            "OFF",
        ]

        for true_val in true_values:
            with patch.dict(os.environ, {"SWAGGER_MCP_SERVER_SSL_ENABLED": true_val}):
                config = extractor.extract_environment_config()
                assert config["server"]["ssl"]["enabled"] is True

        for false_val in false_values:
            with patch.dict(os.environ, {"SWAGGER_MCP_SERVER_SSL_ENABLED": false_val}):
                config = extractor.extract_environment_config()
                assert config["server"]["ssl"]["enabled"] is False

    def test_type_conversion_invalid_integer(self, extractor):
        """Test handling of invalid integer values."""
        with patch.dict(os.environ, {"SWAGGER_MCP_SERVER_PORT": "invalid"}):
            config = extractor.extract_environment_config()
            # Should skip invalid values
            assert "server" not in config or "port" not in config.get("server", {})

    def test_type_conversion_invalid_float(self, extractor):
        """Test handling of invalid float values."""
        with patch.dict(
            os.environ,
            {"SWAGGER_MCP_SEARCH_FIELD_WEIGHTS_ENDPOINT_PATH": "invalid"},
        ):
            config = extractor.extract_environment_config()
            # Should skip invalid values
            assert "search" not in config or "field_weights" not in config.get(
                "search", {}
            )

    def test_get_nested_config_value(self, extractor):
        """Test getting nested configuration values."""
        config = {
            "server": {
                "host": "localhost",
                "port": 8080,
                "ssl": {"enabled": True, "cert_file": "/path/to/cert.pem"},
            },
            "database": {"path": "./test.db"},
        }

        # Test simple nested access
        assert extractor.get_nested_config_value(config, "server.host") == "localhost"
        assert extractor.get_nested_config_value(config, "server.port") == 8080
        assert extractor.get_nested_config_value(config, "database.path") == "./test.db"

        # Test deep nested access
        assert extractor.get_nested_config_value(config, "server.ssl.enabled") is True
        assert (
            extractor.get_nested_config_value(config, "server.ssl.cert_file")
            == "/path/to/cert.pem"
        )

        # Test non-existent keys
        assert extractor.get_nested_config_value(config, "nonexistent.key") is None
        assert extractor.get_nested_config_value(config, "server.nonexistent") is None
        assert (
            extractor.get_nested_config_value(config, "server.ssl.nonexistent") is None
        )

    def test_set_nested_config(self, extractor):
        """Test setting nested configuration values."""
        config = {}

        # Test setting simple nested value
        extractor.set_nested_config(config, "server.host", "localhost")
        assert config == {"server": {"host": "localhost"}}

        # Test setting deep nested value
        extractor.set_nested_config(config, "server.ssl.enabled", True)
        assert config["server"]["ssl"]["enabled"] is True

        # Test setting value in existing structure
        extractor.set_nested_config(config, "server.port", 8080)
        assert config["server"]["port"] == 8080
        assert config["server"]["host"] == "localhost"  # Should preserve existing

        # Test creating new branch
        extractor.set_nested_config(config, "database.path", "./test.db")
        assert config["database"]["path"] == "./test.db"

    def test_get_environment_variable_for_path(self, extractor):
        """Test getting environment variable name for configuration path."""
        assert (
            extractor.get_environment_variable_for_path("server.host")
            == "SWAGGER_MCP_SERVER_HOST"
        )
        assert (
            extractor.get_environment_variable_for_path("server.port")
            == "SWAGGER_MCP_SERVER_PORT"
        )
        assert (
            extractor.get_environment_variable_for_path("server.ssl.enabled")
            == "SWAGGER_MCP_SERVER_SSL_ENABLED"
        )
        assert (
            extractor.get_environment_variable_for_path("database.path")
            == "SWAGGER_MCP_DB_PATH"
        )
        assert (
            extractor.get_environment_variable_for_path("logging.level")
            == "SWAGGER_MCP_LOG_LEVEL"
        )

    def test_get_environment_documentation(self, extractor):
        """Test getting environment variable documentation."""
        docs = extractor.get_environment_documentation()

        assert isinstance(docs, dict)
        assert len(docs) > 0

        # Check that known variables are documented
        assert "SWAGGER_MCP_SERVER_HOST" in docs
        assert "SWAGGER_MCP_SERVER_PORT" in docs
        assert "SWAGGER_MCP_DB_PATH" in docs
        assert "SWAGGER_MCP_LOG_LEVEL" in docs

        # Check that descriptions are meaningful
        for var, desc in docs.items():
            assert isinstance(desc, str)
            assert len(desc) > 10  # Should have meaningful descriptions

    def test_environment_variable_precedence(self, extractor):
        """Test that environment variables take precedence."""
        # This test verifies the behavior expected in configuration hierarchy
        env_vars = {
            "SWAGGER_MCP_SERVER_HOST": "env.example.com",
            "SWAGGER_MCP_SERVER_PORT": "9000",
            "SWAGGER_MCP_LOG_LEVEL": "ERROR",
        }

        with patch.dict(os.environ, env_vars):
            config = extractor.extract_environment_config()

            # Environment values should be converted and available
            assert config["server"]["host"] == "env.example.com"
            assert config["server"]["port"] == 9000
            assert config["logging"]["level"] == "ERROR"

    def test_partial_environment_override(self, extractor):
        """Test that partial environment configuration works correctly."""
        # Only set some environment variables
        env_vars = {
            "SWAGGER_MCP_SERVER_PORT": "9000",
            "SWAGGER_MCP_LOG_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, env_vars):
            config = extractor.extract_environment_config()

            # Only the set variables should be in the config
            assert config["server"]["port"] == 9000
            assert config["logging"]["level"] == "DEBUG"

            # Other variables should not be present
            assert "host" not in config.get("server", {})
            assert "file" not in config.get("logging", {})

    def test_environment_variable_validation(self, extractor):
        """Test that environment variables are validated according to type."""
        # Test with valid values
        valid_env = {
            "SWAGGER_MCP_SERVER_PORT": "8080",
            "SWAGGER_MCP_SERVER_SSL_ENABLED": "true",
            "SWAGGER_MCP_SEARCH_WEIGHT_ENDPOINT": "1.5",
        }

        with patch.dict(os.environ, valid_env):
            config = extractor.extract_environment_config()
            assert config["server"]["port"] == 8080
            assert config["server"]["ssl"]["enabled"] is True
            assert config["search"]["field_weights"]["endpoint_path"] == 1.5

        # Test with invalid values (should be skipped)
        invalid_env = {
            "SWAGGER_MCP_SERVER_PORT": "not_a_number",
            "SWAGGER_MCP_SEARCH_FIELD_WEIGHTS_ENDPOINT_PATH": "not_a_float",
        }

        with patch.dict(os.environ, invalid_env):
            config = extractor.extract_environment_config()
            # Invalid values should be skipped
            assert "server" not in config or "port" not in config.get("server", {})
            assert "search" not in config or "field_weights" not in config.get(
                "search", {}
            )

    def test_complex_nested_environment_config(self, extractor):
        """Test complex nested environment configuration."""
        env_vars = {
            "SWAGGER_MCP_SERVER_SSL_ENABLED": "true",
            "SWAGGER_MCP_SERVER_SSL_CERT": "/etc/ssl/cert.pem",
            "SWAGGER_MCP_SERVER_SSL_KEY": "/etc/ssl/key.pem",
        }

        with patch.dict(os.environ, env_vars):
            config = extractor.extract_environment_config()

            # Check SSL configuration
            ssl_config = config["server"]["ssl"]
            assert ssl_config["enabled"] is True
            assert ssl_config["cert_file"] == "/etc/ssl/cert.pem"
            assert ssl_config["key_file"] == "/etc/ssl/key.pem"
