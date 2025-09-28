"""Tests for UninstallationManager."""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from swagger_mcp_server.installation.uninstaller import (
    UninstallationError,
    UninstallationManager,
)


class TestUninstallationManager:
    """Test cases for UninstallationManager."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def manager(self, temp_home):
        """Create UninstallationManager with temporary home."""
        with patch("pathlib.Path.home", return_value=temp_home):
            return UninstallationManager()

    @pytest.fixture
    def setup_installation(self, manager):
        """Set up a mock installation structure."""
        # Create directories
        manager.install_dir.mkdir(parents=True)
        manager.config_dir.mkdir(parents=True)
        manager.data_dir.mkdir(parents=True)
        manager.logs_dir.mkdir(parents=True)
        manager.backup_dir.mkdir(parents=True)

        # Create some files
        (manager.config_dir / "config.yaml").write_text("test config")
        (manager.config_dir / "servers.json").write_text('{"test": "data"}')
        (manager.data_dir / "database" / "test.db").mkdir(parents=True)
        (manager.data_dir / "database" / "test.db" / "data.sqlite").write_text(
            "test db"
        )
        (manager.logs_dir / "server.log").write_text("test log")

        return manager

    def test_init(self, manager):
        """Test manager initialization."""
        assert manager.platform in ["windows", "darwin", "linux"]
        assert manager.install_dir.name == ".swagger-mcp-server"

    @pytest.mark.asyncio
    async def test_perform_uninstallation_complete(self, setup_installation):
        """Test complete uninstallation."""
        manager = setup_installation

        # Mock server manager to avoid import issues
        with patch(
            "swagger_mcp_server.management.MCPServerManager",
            side_effect=ImportError,
        ):
            result = await manager.perform_uninstallation()

        assert "removed_items" in result
        assert "preserved_items" in result
        assert "warnings" in result
        assert "errors" in result
        assert "timestamp" in result

        # Check that installation directory was removed
        assert not manager.install_dir.exists()

    @pytest.mark.asyncio
    async def test_perform_uninstallation_preserve_config(self, setup_installation):
        """Test uninstallation with config preservation."""
        manager = setup_installation

        with patch(
            "swagger_mcp_server.management.MCPServerManager",
            side_effect=ImportError,
        ):
            result = await manager.perform_uninstallation(preserve_config=True)

        # Check that config files are in preserved items
        preserved_files = [
            item for item in result["preserved_items"] if "config" in item
        ]
        assert len(preserved_files) > 0

    @pytest.mark.asyncio
    async def test_perform_uninstallation_preserve_data(self, setup_installation):
        """Test uninstallation with data preservation."""
        manager = setup_installation

        with patch(
            "swagger_mcp_server.management.MCPServerManager",
            side_effect=ImportError,
        ):
            result = await manager.perform_uninstallation(preserve_data=True)

        # Should create backup directory
        backup_created = any(
            "backed up to" in item for item in result["preserved_items"]
        )
        assert backup_created

    @pytest.mark.asyncio
    async def test_perform_uninstallation_error_handling(self, manager):
        """Test error handling during uninstallation."""
        # Mock an error condition
        with patch.object(
            manager,
            "_stop_running_servers",
            side_effect=Exception("Test error"),
        ):
            with pytest.raises(UninstallationError, match="Uninstallation failed"):
                await manager.perform_uninstallation()

    @pytest.mark.asyncio
    async def test_stop_running_servers_no_servers(self, manager):
        """Test stopping servers when no servers are running."""
        results = {"warnings": [], "removed_items": []}

        # Mock empty server list
        mock_manager = Mock()
        mock_manager.get_all_servers_status = AsyncMock(return_value=[])

        with patch(
            "swagger_mcp_server.management.MCPServerManager",
            return_value=mock_manager,
        ):
            await manager._stop_running_servers(results)

        # Should not add any warnings or items
        assert len(results["warnings"]) == 0
        assert len(results["removed_items"]) == 0

    @pytest.mark.asyncio
    async def test_stop_running_servers_with_servers(self, manager):
        """Test stopping servers when servers are running."""
        results = {"warnings": [], "removed_items": []}

        # Mock server list
        mock_servers = [
            {"server": {"id": "server1"}},
            {"server": {"id": "server2"}},
        ]
        mock_manager = Mock()
        mock_manager.get_all_servers_status = AsyncMock(return_value=mock_servers)
        mock_manager.stop_server = AsyncMock()

        with patch(
            "swagger_mcp_server.management.MCPServerManager",
            return_value=mock_manager,
        ):
            await manager._stop_running_servers(results)

        # Should add warning about stopping servers
        assert len(results["warnings"]) == 1
        assert "Stopping 2 running servers" in results["warnings"][0]

        # Should add removed items for each server
        assert len(results["removed_items"]) == 2

    @pytest.mark.asyncio
    async def test_stop_running_servers_import_error(self, manager):
        """Test stopping servers when server management is not available."""
        results = {"warnings": [], "removed_items": []}

        # Mock ImportError for server manager
        with patch(
            "swagger_mcp_server.management.MCPServerManager",
            side_effect=ImportError,
        ):
            await manager._stop_running_servers(results)

        # Should not fail and not add any items
        assert len(results["warnings"]) == 0
        assert len(results["removed_items"]) == 0

    @pytest.mark.asyncio
    async def test_preserve_user_data(self, setup_installation):
        """Test user data preservation."""
        manager = setup_installation
        results = {"preserved_items": [], "warnings": []}

        await manager._preserve_user_data(results)

        # Should create backup directory and preserve items
        assert len(results["preserved_items"]) > 0

        # Check that backup directory was created
        backup_dirs = list(Path.home().glob(".swagger-mcp-server-backup-*"))
        assert len(backup_dirs) > 0

    @pytest.mark.asyncio
    async def test_preserve_user_data_error(self, manager):
        """Test user data preservation with errors."""
        results = {"preserved_items": [], "warnings": []}

        # Create test directories and files
        manager.data_dir.mkdir(parents=True, exist_ok=True)
        manager.config_dir.mkdir(parents=True, exist_ok=True)
        (manager.data_dir / "database").mkdir(parents=True, exist_ok=True)
        (manager.config_dir / "config.yaml").write_text("test config")
        (manager.config_dir / "servers.json").write_text("{}")

        # Mock shutil.copytree to raise error
        with patch("shutil.copytree", side_effect=Exception("Copy error")):
            await manager._preserve_user_data(results)

        # Should add warnings about failed backups
        assert len(results["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_remove_all_data(self, setup_installation):
        """Test removing all data."""
        manager = setup_installation
        results = {"removed_items": [], "warnings": []}

        await manager._remove_all_data(results)

        # Should remove data directory
        assert not manager.data_dir.exists()
        assert len(results["removed_items"]) == 1

    @pytest.mark.asyncio
    async def test_remove_all_data_error(self, manager):
        """Test data removal with errors."""
        # Create data directory
        manager.data_dir.mkdir(parents=True)
        results = {"removed_items": [], "warnings": []}

        # Mock rmtree to raise error
        with patch("shutil.rmtree", side_effect=Exception("Remove error")):
            await manager._remove_all_data(results)

        # Should add warning about failed removal
        assert len(results["warnings"]) == 1

    @pytest.mark.asyncio
    async def test_selective_cleanup(self, setup_installation):
        """Test selective cleanup preserving config."""
        manager = setup_installation
        results = {"removed_items": [], "preserved_items": [], "warnings": []}

        await manager._selective_cleanup(results)

        # Should preserve config files
        config_preserved = any("config:" in item for item in results["preserved_items"])
        assert config_preserved

        # Should remove cache and logs
        assert len(results["removed_items"]) > 0

    @pytest.mark.asyncio
    async def test_complete_cleanup(self, setup_installation):
        """Test complete cleanup removing everything."""
        manager = setup_installation
        results = {"removed_items": [], "warnings": []}

        await manager._complete_cleanup(results)

        # Should remove entire installation directory
        assert not manager.install_dir.exists()
        assert len(results["removed_items"]) == 1

    @pytest.mark.asyncio
    async def test_complete_cleanup_fallback(self, setup_installation):
        """Test complete cleanup with fallback to individual removal."""
        manager = setup_installation
        results = {"removed_items": [], "warnings": []}

        # Mock rmtree to fail on main directory but succeed on subdirectories
        original_rmtree = shutil.rmtree

        def mock_rmtree(path, *args, **kwargs):
            if path == manager.install_dir:
                raise Exception("Cannot remove main directory")
            return original_rmtree(path, *args, **kwargs)

        with patch("shutil.rmtree", side_effect=mock_rmtree):
            await manager._complete_cleanup(results)

        # Should add warning and try individual removal
        assert len(results["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_uninstall_pip_package_not_installed(self, manager):
        """Test pip package uninstallation when not installed."""
        # Mock pip show to return non-zero (not installed)
        mock_result = Mock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = await manager._uninstall_pip_package()

        assert result["success"] is True
        assert "not installed via pip" in result["message"]

    @pytest.mark.asyncio
    async def test_uninstall_pip_package_success(self, manager):
        """Test successful pip package uninstallation."""
        # Mock pip show to return success (installed)
        mock_show_result = Mock()
        mock_show_result.returncode = 0

        # Mock pip uninstall to return success
        mock_uninstall_result = Mock()
        mock_uninstall_result.returncode = 0

        with patch(
            "subprocess.run",
            side_effect=[mock_show_result, mock_uninstall_result],
        ):
            result = await manager._uninstall_pip_package()

        assert result["success"] is True
        assert "uninstalled successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_uninstall_pip_package_failure(self, manager):
        """Test failed pip package uninstallation."""
        # Mock pip show to return success (installed)
        mock_show_result = Mock()
        mock_show_result.returncode = 0

        # Mock pip uninstall to return failure
        mock_uninstall_result = Mock()
        mock_uninstall_result.returncode = 1
        mock_uninstall_result.stderr = "Uninstall failed"

        with patch(
            "subprocess.run",
            side_effect=[mock_show_result, mock_uninstall_result],
        ):
            result = await manager._uninstall_pip_package()

        assert result["success"] is False
        assert "Failed to uninstall package" in result["message"]

    @pytest.mark.asyncio
    async def test_cleanup_temp_files(self, manager):
        """Test temporary file cleanup."""
        # Create some temporary directories
        temp_dir = Path.home() / ".swagger_mcp_temp"
        temp_dir.mkdir(parents=True)
        (temp_dir / "temp_file.txt").write_text("test")

        result = await manager._cleanup_temp_files()

        assert len(result) > 0
        assert not temp_dir.exists()

    @pytest.mark.asyncio
    async def test_cleanup_temp_files_error(self, manager):
        """Test temporary file cleanup with errors."""
        # Create temp directory but mock removal to fail
        temp_dir = Path.home() / ".swagger_mcp_temp"
        temp_dir.mkdir(parents=True)

        with patch("shutil.rmtree", side_effect=Exception("Remove error")):
            result = await manager._cleanup_temp_files()

        # Should not raise error, just ignore failures
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_create_uninstall_log(self, manager):
        """Test uninstallation log creation."""
        # Clean up any existing log files first
        existing_logs = list(Path.home().glob("swagger-mcp-server-uninstall-*.log"))
        for log_file in existing_logs:
            log_file.unlink()

        results = {
            "timestamp": "2023-01-01T12:00:00",
            "removed_items": ["item1", "item2"],
            "preserved_items": ["config.yaml"],
            "warnings": ["warning1"],
            "errors": [],
        }

        await manager._create_uninstall_log(results)

        # Check that log file was created
        log_files = list(Path.home().glob("swagger-mcp-server-uninstall-*.log"))
        assert len(log_files) > 0

        # Check log content
        log_content = log_files[0].read_text()
        assert "Swagger MCP Server Uninstallation Log" in log_content
        assert "item1" in log_content
        assert "config.yaml" in log_content

    @pytest.mark.asyncio
    async def test_create_uninstall_log_error(self, manager):
        """Test uninstallation log creation with error."""
        results = {
            "timestamp": "2023-01-01T12:00:00",
            "removed_items": [],
            "preserved_items": [],
            "warnings": [],
            "errors": [],
        }

        # Mock open to raise error
        with patch("builtins.open", side_effect=Exception("Write error")):
            # Should not raise error
            await manager._create_uninstall_log(results)

    @pytest.mark.asyncio
    async def test_get_uninstall_preview_no_installation(self, manager):
        """Test uninstall preview when not installed."""
        result = await manager.get_uninstall_preview()

        assert "warnings" in result
        assert "Installation directory does not exist" in result["warnings"]

    @pytest.mark.asyncio
    async def test_get_uninstall_preview_with_installation(self, setup_installation):
        """Test uninstall preview with existing installation."""
        manager = setup_installation

        # Mock server manager
        with patch(
            "swagger_mcp_server.management.MCPServerManager",
            side_effect=ImportError,
        ):
            result = await manager.get_uninstall_preview()

        assert "will_remove" in result
        assert "will_preserve" in result
        assert len(result["will_remove"]) > 0

    @pytest.mark.asyncio
    async def test_get_uninstall_preview_preserve_config(self, setup_installation):
        """Test uninstall preview with config preservation."""
        manager = setup_installation

        with patch(
            "swagger_mcp_server.management.MCPServerManager",
            side_effect=ImportError,
        ):
            result = await manager.get_uninstall_preview(preserve_config=True)

        # Config should be in preserved items
        config_preserved = any("config" in item for item in result["will_preserve"])
        assert config_preserved

    @pytest.mark.asyncio
    async def test_get_uninstall_preview_with_running_servers(self, setup_installation):
        """Test uninstall preview with running servers."""
        manager = setup_installation

        # Mock running servers
        mock_servers = [{"server": {"id": "server1"}}]
        mock_manager = Mock()
        mock_manager.get_all_servers_status = AsyncMock(return_value=mock_servers)

        with patch(
            "swagger_mcp_server.management.MCPServerManager",
            return_value=mock_manager,
        ):
            result = await manager.get_uninstall_preview()

        # Should warn about stopping servers
        server_warning = any(
            "running servers will be stopped" in warning
            for warning in result["warnings"]
        )
        assert server_warning
