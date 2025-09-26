"""Tests for configuration schema validation."""

import pytest
from swagger_mcp_server.config import ConfigurationSchema


class TestConfigurationSchema:
    """Test cases for ConfigurationSchema."""

    def test_get_default_configuration(self):
        """Test getting default configuration."""
        config = ConfigurationSchema.get_default_configuration()

        assert config is not None
        assert isinstance(config, dict)

        # Check all required sections exist
        required_sections = ["server", "database", "search", "logging", "features"]
        for section in required_sections:
            assert section in config

        # Check default values
        assert config["server"]["host"] == "localhost"
        assert config["server"]["port"] == 8080
        assert config["logging"]["level"] == "INFO"
        assert config["database"]["path"] == "./mcp_server.db"

    def test_get_configuration_help_valid_keys(self):
        """Test getting help for valid configuration keys."""
        # Test simple keys
        help_text = ConfigurationSchema.get_configuration_help("server.port")
        assert "port number" in help_text.lower()
        assert "1024-65535" in help_text

        help_text = ConfigurationSchema.get_configuration_help("server.host")
        assert "host address" in help_text.lower()

        help_text = ConfigurationSchema.get_configuration_help("logging.level")
        assert "verbosity" in help_text.lower()

        # Test nested keys
        help_text = ConfigurationSchema.get_configuration_help("server.ssl.enabled")
        assert "ssl" in help_text.lower() or "tls" in help_text.lower()

        help_text = ConfigurationSchema.get_configuration_help("features.metrics.enabled")
        assert "metrics" in help_text.lower()

    def test_get_configuration_help_invalid_keys(self):
        """Test getting help for invalid configuration keys."""
        help_text = ConfigurationSchema.get_configuration_help("nonexistent.key")
        assert help_text is None

        help_text = ConfigurationSchema.get_configuration_help("server.nonexistent")
        assert help_text is None

    def test_get_all_configuration_keys(self):
        """Test getting all configuration keys."""
        keys = ConfigurationSchema.get_all_configuration_keys()

        assert isinstance(keys, list)
        assert len(keys) > 0

        # Check that keys are in dot notation
        expected_keys = [
            "server.host",
            "server.port",
            "server.max_connections",
            "server.timeout",
            "server.ssl.enabled",
            "server.ssl.cert_file",
            "server.ssl.key_file",
            "database.path",
            "database.pool_size",
            "database.timeout",
            "logging.level",
            "logging.format",
            "logging.file",
            "search.engine",
            "search.index_directory",
            "features.metrics.enabled"
        ]

        for key in expected_keys:
            assert key in keys

        # Check keys are sorted
        assert keys == sorted(keys)

    def test_validate_configuration_value_valid_string(self):
        """Test validation of valid string values."""
        # Valid host
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.host", "localhost")
        assert is_valid is True
        assert error is None

        is_valid, error = ConfigurationSchema.validate_configuration_value("server.host", "example.com")
        assert is_valid is True
        assert error is None

        # Valid log level
        is_valid, error = ConfigurationSchema.validate_configuration_value("logging.level", "DEBUG")
        assert is_valid is True
        assert error is None

        is_valid, error = ConfigurationSchema.validate_configuration_value("logging.level", "INFO")
        assert is_valid is True
        assert error is None

    def test_validate_configuration_value_invalid_string(self):
        """Test validation of invalid string values."""
        # Invalid host (empty)
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.host", "")
        assert is_valid is False
        assert "host" in error.lower()

        # Invalid log level
        is_valid, error = ConfigurationSchema.validate_configuration_value("logging.level", "INVALID")
        assert is_valid is False
        assert "must be one of" in error

        # Non-string value for string field
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.host", 123)
        assert is_valid is False
        assert "must be a string" in error

    def test_validate_configuration_value_valid_integer(self):
        """Test validation of valid integer values."""
        # Valid port
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.port", 8080)
        assert is_valid is True
        assert error is None

        is_valid, error = ConfigurationSchema.validate_configuration_value("server.port", 1024)
        assert is_valid is True
        assert error is None

        is_valid, error = ConfigurationSchema.validate_configuration_value("server.port", 65535)
        assert is_valid is True
        assert error is None

        # Valid max connections
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.max_connections", 100)
        assert is_valid is True
        assert error is None

    def test_validate_configuration_value_invalid_integer(self):
        """Test validation of invalid integer values."""
        # Port too low
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.port", 1023)
        assert is_valid is False
        assert "at least 1024" in error

        # Port too high
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.port", 65536)
        assert is_valid is False
        assert "at most 65535" in error

        # Non-integer value for integer field
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.port", "8080")
        assert is_valid is False
        assert "must be an integer" in error

        # Negative connections
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.max_connections", -1)
        assert is_valid is False
        assert "at least 1" in error

    def test_validate_configuration_value_valid_float(self):
        """Test validation of valid float values."""
        # Valid field weights
        is_valid, error = ConfigurationSchema.validate_configuration_value("search.field_weights.endpoint_path", 1.5)
        assert is_valid is True
        assert error is None

        is_valid, error = ConfigurationSchema.validate_configuration_value("search.field_weights.summary", 1.0)
        assert is_valid is True
        assert error is None

        # Integers should be accepted for float fields
        is_valid, error = ConfigurationSchema.validate_configuration_value("search.field_weights.endpoint_path", 2)
        assert is_valid is True
        assert error is None

    def test_validate_configuration_value_invalid_float(self):
        """Test validation of invalid float values."""
        # Value too low
        is_valid, error = ConfigurationSchema.validate_configuration_value("search.field_weights.endpoint_path", 0.05)
        assert is_valid is False
        assert "at least 0.1" in error

        # Value too high
        is_valid, error = ConfigurationSchema.validate_configuration_value("search.field_weights.endpoint_path", 3.5)
        assert is_valid is False
        assert "at most 3.0" in error

        # Non-numeric value for float field
        is_valid, error = ConfigurationSchema.validate_configuration_value("search.field_weights.endpoint_path", "invalid")
        assert is_valid is False
        assert "must be a number" in error

    def test_validate_configuration_value_valid_boolean(self):
        """Test validation of valid boolean values."""
        # Valid boolean values
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.ssl.enabled", True)
        assert is_valid is True
        assert error is None

        is_valid, error = ConfigurationSchema.validate_configuration_value("server.ssl.enabled", False)
        assert is_valid is True
        assert error is None

        is_valid, error = ConfigurationSchema.validate_configuration_value("features.metrics.enabled", True)
        assert is_valid is True
        assert error is None

    def test_validate_configuration_value_invalid_boolean(self):
        """Test validation of invalid boolean values."""
        # Non-boolean value for boolean field
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.ssl.enabled", "true")
        assert is_valid is False
        assert "must be a boolean" in error

        is_valid, error = ConfigurationSchema.validate_configuration_value("features.metrics.enabled", 1)
        assert is_valid is False
        assert "must be a boolean" in error

    def test_validate_configuration_value_nullable_fields(self):
        """Test validation of nullable fields."""
        # Nullable string fields should accept None
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.ssl.cert_file", None)
        assert is_valid is True
        assert error is None

        is_valid, error = ConfigurationSchema.validate_configuration_value("server.ssl.key_file", None)
        assert is_valid is True
        assert error is None

        is_valid, error = ConfigurationSchema.validate_configuration_value("logging.file", None)
        assert is_valid is True
        assert error is None

        # Should also accept valid string values
        is_valid, error = ConfigurationSchema.validate_configuration_value("server.ssl.cert_file", "/path/to/cert.pem")
        assert is_valid is True
        assert error is None

    def test_validate_configuration_value_allowed_values(self):
        """Test validation of fields with allowed values."""
        # Valid search engine
        is_valid, error = ConfigurationSchema.validate_configuration_value("search.engine", "whoosh")
        assert is_valid is True
        assert error is None

        # Invalid search engine
        is_valid, error = ConfigurationSchema.validate_configuration_value("search.engine", "elasticsearch")
        assert is_valid is False
        assert "must be one of" in error
        assert "whoosh" in error

        # Valid log levels
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        for level in valid_levels:
            is_valid, error = ConfigurationSchema.validate_configuration_value("logging.level", level)
            assert is_valid is True, f"Level {level} should be valid"
            assert error is None

    def test_validate_configuration_value_regex_validation(self):
        """Test regex validation for string fields."""
        # Valid host patterns
        valid_hosts = ["localhost", "example.com", "test-server", "192.168.1.1", "server123"]
        for host in valid_hosts:
            is_valid, error = ConfigurationSchema.validate_configuration_value("server.host", host)
            assert is_valid is True, f"Host {host} should be valid"
            assert error is None

        # Invalid host patterns (if regex validation is implemented)
        # This depends on the actual regex pattern in the schema
        # For now, we test that the validation infrastructure works

    def test_validate_configuration_value_unknown_key(self):
        """Test validation of unknown configuration keys."""
        is_valid, error = ConfigurationSchema.validate_configuration_value("unknown.key", "value")
        assert is_valid is False
        assert "Invalid configuration path" in error or "Unknown configuration key" in error

    def test_schema_structure_consistency(self):
        """Test that schema structure is consistent."""
        schema = ConfigurationSchema.SCHEMA

        # Check that all top-level sections have proper structure
        for section_name, section_def in schema.items():
            assert "type" in section_def
            assert section_def["type"] == "dict"
            assert "schema" in section_def

            # Check nested structure
            for key, definition in section_def["schema"].items():
                assert "type" in definition

                if definition["type"] == "dict":
                    assert "schema" in definition
                else:
                    # Leaf nodes should have defaults
                    # (Note: some may not have defaults if they're required to be set)
                    pass

    def test_default_extraction_completeness(self):
        """Test that default extraction covers all schema elements."""
        defaults = ConfigurationSchema.get_default_configuration()
        schema = ConfigurationSchema.SCHEMA

        def check_defaults_recursive(defaults_dict, schema_dict, path=""):
            for key, definition in schema_dict.items():
                current_path = f"{path}.{key}" if path else key

                if definition.get("type") == "dict" and "schema" in definition:
                    # Nested dictionary
                    assert key in defaults_dict, f"Missing default section: {current_path}"
                    check_defaults_recursive(defaults_dict[key], definition["schema"], current_path)
                elif "default" in definition:
                    # Should have default value
                    assert key in defaults_dict, f"Missing default value: {current_path}"

        check_defaults_recursive(defaults, schema)

    def test_configuration_keys_completeness(self):
        """Test that all configuration keys are discoverable."""
        keys = ConfigurationSchema.get_all_configuration_keys()
        schema = ConfigurationSchema.SCHEMA

        def collect_keys_from_schema(schema_dict, prefix=""):
            expected_keys = []
            for key, definition in schema_dict.items():
                current_key = f"{prefix}.{key}" if prefix else key

                if definition.get("type") == "dict" and "schema" in definition:
                    # Nested dictionary - recurse
                    expected_keys.extend(collect_keys_from_schema(definition["schema"], current_key))
                elif "default" in definition or "type" in definition:
                    # Leaf value
                    expected_keys.append(current_key)

            return expected_keys

        expected_keys = collect_keys_from_schema(schema)

        # All expected keys should be in the returned keys
        for expected_key in expected_keys:
            assert expected_key in keys, f"Missing key: {expected_key}"

    def test_validation_error_messages(self):
        """Test that validation error messages are informative."""
        # Test various error conditions and check message quality
        test_cases = [
            ("server.port", "invalid", "must be an integer"),
            ("server.port", 99, "at least 1024"),
            ("server.port", 70000, "at most 65535"),
            ("logging.level", "INVALID", "must be one of"),
            ("server.ssl.enabled", "true", "must be a boolean"),
            ("search.field_weights.endpoint_path", -1.0, "at least 0.1")
        ]

        for key, value, expected_phrase in test_cases:
            is_valid, error = ConfigurationSchema.validate_configuration_value(key, value)
            assert is_valid is False
            assert expected_phrase in error, f"Error message for {key}={value} should contain '{expected_phrase}', got: {error}"