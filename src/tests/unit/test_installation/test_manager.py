"""Tests for InstallationManager."""

import os
import sys
import tempfile
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from swagger_mcp_server.installation.manager import InstallationManager, InstallationError


class TestInstallationManager:
    """Test cases for InstallationManager."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def manager(self, temp_home):
        """Create InstallationManager with temporary home."""
        with patch('pathlib.Path.home', return_value=temp_home):
            return InstallationManager()

    @pytest.fixture
    def mock_compatibility_checker(self):
        """Mock compatibility checker."""
        mock = Mock()
        mock.check_system_compatibility = AsyncMock(return_value={
            "compatible": True,
            "issues": [],
            "warnings": [],
            "system_info": {}
        })
        return mock

    def test_init(self, manager):
        """Test manager initialization."""
        assert manager.platform in ["windows", "darwin", "linux"]
        assert manager.python_version == sys.version_info
        assert manager.install_dir.name == ".swagger-mcp-server"
        assert manager.compatibility_checker is not None

    def test_is_already_setup_false(self, manager):
        """Test is_already_setup returns False when not set up."""
        assert not manager.is_already_setup()

    def test_is_already_setup_true(self, manager):
        """Test is_already_setup returns True when set up."""
        # Create required directories and files
        manager.install_dir.mkdir(parents=True)
        manager.config_dir.mkdir(parents=True)
        (manager.config_dir / "config.yaml").touch()

        assert manager.is_already_setup()

    @pytest.mark.asyncio
    async def test_perform_setup_compatibility_failure(self, manager):
        """Test setup fails when compatibility check fails."""
        with patch.object(manager.compatibility_checker, 'check_system_compatibility',
                         return_value={"compatible": False, "issues": ["Python too old"]}):

            with pytest.raises(InstallationError, match="System compatibility check failed"):
                await manager.perform_setup()

    @pytest.mark.asyncio
    async def test_perform_setup_success(self, manager):
        """Test successful setup process."""
        # Mock compatibility checker
        with patch.object(manager.compatibility_checker, 'check_system_compatibility',
                         return_value={
                             "compatible": True,
                             "issues": [],
                             "warnings": ["Low disk space"],
                             "system_info": {}
                         }):

            # Mock configuration manager
            mock_config_manager = Mock()
            mock_config_manager.initialize_configuration = AsyncMock()
            mock_config_manager.validate_configuration = AsyncMock(return_value=(True, [], []))

            with patch('swagger_mcp_server.config.ConfigurationManager',
                      return_value=mock_config_manager):

                result = await manager.perform_setup()

        # Verify result structure
        assert "steps_completed" in result
        assert "warnings" in result
        assert "errors" in result
        assert "timestamp" in result

        # Check that directories were created
        assert manager.install_dir.exists()
        assert manager.config_dir.exists()
        assert manager.data_dir.exists()
        assert manager.logs_dir.exists()
        assert manager.backup_dir.exists()

        # Check warnings are included
        assert "Low disk space" in result["warnings"]

    @pytest.mark.asyncio
    async def test_create_directory_structure(self, manager):
        """Test directory structure creation."""
        await manager.create_directory_structure()

        # Verify all directories exist
        assert manager.install_dir.exists()
        assert manager.config_dir.exists()
        assert manager.data_dir.exists()
        assert manager.logs_dir.exists()
        assert manager.backup_dir.exists()
        assert (manager.data_dir / "database").exists()
        assert (manager.data_dir / "search_index").exists()
        assert (manager.data_dir / "temp").exists()

    @pytest.mark.asyncio
    async def test_create_directory_structure_force(self, manager):
        """Test directory creation with force flag."""
        # Create directory first
        manager.install_dir.mkdir(parents=True)

        # Should not raise error with force=True
        await manager.create_directory_structure(force=True)
        assert manager.install_dir.exists()

    @pytest.mark.asyncio
    async def test_initialize_configuration(self, manager):
        """Test configuration initialization."""
        manager.config_dir.mkdir(parents=True)

        # Mock configuration manager
        mock_config_manager = Mock()
        mock_config_manager.initialize_configuration = AsyncMock()

        with patch('swagger_mcp_server.config.ConfigurationManager',
                  return_value=mock_config_manager):
            await manager.initialize_configuration()

        # Check servers.json was created
        servers_file = manager.config_dir / "servers.json"
        assert servers_file.exists()

        with open(servers_file) as f:
            servers_data = json.load(f)

        assert servers_data["version"] == "1.0"
        assert "servers" in servers_data
        assert "last_updated" in servers_data

    @pytest.mark.asyncio
    async def test_setup_data_directories(self, manager):
        """Test data directory setup."""
        await manager.setup_data_directories()

        assert (manager.data_dir / "database").exists()
        assert (manager.data_dir / "search_index").exists()
        assert (manager.data_dir / "temp").exists()

    @pytest.mark.asyncio
    async def test_setup_logging(self, manager):
        """Test logging setup."""
        manager.logs_dir.mkdir(parents=True)

        await manager.setup_logging()

        # Check log files were created
        assert (manager.logs_dir / "server.log").exists()
        assert (manager.logs_dir / "conversion.log").exists()
        assert (manager.logs_dir / "setup.log").exists()

    @pytest.mark.asyncio
    async def test_verify_installation_success(self, manager):
        """Test successful installation verification."""
        # Set up required directories and files
        await manager.create_directory_structure()
        await manager.setup_data_directories()
        await manager.setup_logging()

        # Mock configuration validation
        mock_config_manager = Mock()
        mock_config_manager.validate_configuration = AsyncMock(return_value=(True, [], []))

        with patch('swagger_mcp_server.installation.manager.ConfigurationManager',
                  return_value=mock_config_manager):

            result = await manager.verify_installation()

        assert result["status"] == "success"
        assert "components" in result
        assert "system_info" in result

    @pytest.mark.asyncio
    async def test_verify_installation_failure(self, manager):
        """Test installation verification with failures."""
        # Don't create directories to simulate failure

        result = await manager.verify_installation()

        assert result["status"] == "failed"
        assert len(result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_verify_directories_success(self, manager):
        """Test directory verification success."""
        await manager.create_directory_structure()

        result = await manager._verify_directories()

        assert result["working"] is True
        assert "All directories exist" in result["message"]

    @pytest.mark.asyncio
    async def test_verify_directories_failure(self, manager):
        """Test directory verification failure."""
        result = await manager._verify_directories()

        assert result["working"] is False
        assert "Missing directories" in result["message"]

    @pytest.mark.asyncio
    async def test_verify_configuration_success(self, manager):
        """Test configuration verification success."""
        mock_config_manager = Mock()
        mock_config_manager.validate_configuration = AsyncMock(return_value=(True, [], []))

        with patch('swagger_mcp_server.installation.manager.ConfigurationManager',
                  return_value=mock_config_manager):

            result = await manager._verify_configuration()

        assert result["working"] is True
        assert "Configuration valid" in result["message"]

    @pytest.mark.asyncio
    async def test_verify_configuration_failure(self, manager):
        """Test configuration verification failure."""
        mock_config_manager = Mock()
        mock_config_manager.validate_configuration = AsyncMock(return_value=(False, ["Error"], []))

        with patch('swagger_mcp_server.installation.manager.ConfigurationManager',
                  return_value=mock_config_manager):

            result = await manager._verify_configuration()

        assert result["working"] is False
        assert "Configuration errors" in result["message"]

    @pytest.mark.asyncio
    async def test_verify_permissions_success(self, manager):
        """Test permission verification success."""
        await manager.create_directory_structure()

        result = await manager._verify_permissions()

        assert result["working"] is True
        assert "Permissions OK" in result["message"]

    @pytest.mark.asyncio
    async def test_verify_dependencies_success(self, manager):
        """Test dependency verification success."""
        # Mock successful imports
        with patch('builtins.__import__', return_value=Mock()):
            result = await manager._verify_dependencies()

        assert result["working"] is True
        assert "All dependencies available" in result["message"]

    @pytest.mark.asyncio
    async def test_verify_dependencies_failure(self, manager):
        """Test dependency verification with missing modules."""
        def mock_import(name, *args, **kwargs):
            if name in ["click", "yaml"]:
                raise ImportError(f"No module named '{name}'")
            return Mock()

        with patch('builtins.__import__', side_effect=mock_import):
            result = await manager._verify_dependencies()

        assert result["working"] is False
        assert "Missing modules" in result["message"]

    @pytest.mark.asyncio
    async def test_gather_system_info(self, manager):
        """Test system information gathering."""
        result = await manager._gather_system_info()

        assert "platform" in result
        assert "python_version" in result
        assert "install_path" in result
        assert "python_executable" in result

    @pytest.mark.asyncio
    async def test_record_installation_metadata(self, manager):
        """Test installation metadata recording."""
        manager.install_dir.mkdir(parents=True)

        await manager.record_installation_metadata()

        metadata_file = manager.install_dir / "installation_metadata.json"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            metadata = json.load(f)

        assert "installation_date" in metadata
        assert "version" in metadata
        assert "platform" in metadata
        assert "python" in metadata

    def test_get_package_version(self, manager):
        """Test package version retrieval."""
        # Test fallback to unknown
        version = manager._get_package_version()
        assert version == "unknown"

    @pytest.mark.asyncio
    async def test_get_installation_info_not_installed(self, manager):
        """Test installation info when not installed."""
        result = await manager.get_installation_info()

        assert result["installed"] is False
        assert "install_directory" in result
        assert "platform" in result
        assert "python_version" in result

    @pytest.mark.asyncio
    async def test_get_installation_info_installed(self, manager):
        """Test installation info when installed."""
        # Set up installation
        await manager.create_directory_structure()
        await manager.record_installation_metadata()

        # Mock configuration manager
        mock_config_manager = Mock()
        mock_config_manager.validate_configuration = AsyncMock(return_value=(True, [], []))

        with patch('swagger_mcp_server.installation.manager.ConfigurationManager',
                  return_value=mock_config_manager):

            result = await manager.get_installation_info()

        assert result["installed"] is True
        assert "installation_metadata" in result
        assert "configuration_status" in result

    @pytest.mark.asyncio
    async def test_setup_error_handling(self, manager):
        """Test error handling during setup."""
        # Mock compatibility checker to raise exception
        with patch.object(manager.compatibility_checker, 'check_system_compatibility',
                         side_effect=Exception("Test error")):

            with pytest.raises(InstallationError, match="Setup failed"):
                await manager.perform_setup()