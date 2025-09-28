"""Tests for SystemCompatibilityChecker."""

import asyncio
import os
import platform
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from swagger_mcp_server.installation.compatibility import (
    SystemCompatibilityChecker,
)


class TestSystemCompatibilityChecker:
    """Test cases for SystemCompatibilityChecker."""

    @pytest.fixture
    def checker(self):
        """Create SystemCompatibilityChecker instance."""
        return SystemCompatibilityChecker()

    def test_init(self, checker):
        """Test checker initialization."""
        assert checker.platform in ["windows", "darwin", "linux"]
        assert checker.python_version == sys.version_info

    @pytest.mark.asyncio
    async def test_check_system_compatibility_success(self, checker):
        """Test successful system compatibility check."""
        # Mock all check methods to return success
        with (
            patch.object(
                checker,
                "check_python_version",
                return_value={"compatible": True, "message": "OK"},
            ),
            patch.object(
                checker,
                "check_platform_support",
                return_value={"supported": True, "message": "OK"},
            ),
            patch.object(
                checker,
                "check_disk_space",
                return_value={"sufficient": True, "message": "OK"},
            ),
            patch.object(
                checker,
                "check_memory",
                return_value={"sufficient": True, "message": "OK"},
            ),
            patch.object(
                checker,
                "check_network_connectivity",
                return_value={"available": True, "message": "OK"},
            ),
            patch.object(
                checker,
                "check_permissions",
                return_value={"adequate": True, "message": "OK"},
            ),
            patch.object(
                checker, "check_core_dependencies", return_value={"missing": []}
            ),
        ):
            result = await checker.check_system_compatibility()

        assert result["compatible"] is True
        assert len(result["issues"]) == 0
        assert "system_info" in result

    @pytest.mark.asyncio
    async def test_check_system_compatibility_python_failure(self, checker):
        """Test compatibility check with Python version failure."""
        with (
            patch.object(
                checker,
                "check_python_version",
                return_value={"compatible": False, "message": "Python too old"},
            ),
            patch.object(
                checker,
                "check_platform_support",
                return_value={"supported": True, "message": "OK"},
            ),
            patch.object(
                checker,
                "check_disk_space",
                return_value={"sufficient": True, "message": "OK"},
            ),
            patch.object(
                checker,
                "check_memory",
                return_value={"sufficient": True, "message": "OK"},
            ),
            patch.object(
                checker,
                "check_network_connectivity",
                return_value={"available": True, "message": "OK"},
            ),
            patch.object(
                checker,
                "check_permissions",
                return_value={"adequate": True, "message": "OK"},
            ),
            patch.object(
                checker, "check_core_dependencies", return_value={"missing": []}
            ),
        ):
            result = await checker.check_system_compatibility()

        assert result["compatible"] is False
        assert "Python too old" in result["issues"]

    def test_check_python_version_compatible(self, checker):
        """Test Python version check with compatible version."""
        result = checker.check_python_version()

        # Current Python should be compatible (test runs on Python 3.9+)
        assert result["compatible"] is True
        assert "supported" in result["message"]

    def test_check_python_version_incompatible(self, checker):
        """Test Python version check with incompatible version."""
        # Mock older Python version
        with patch("sys.version_info", (3, 8, 0)):
            result = checker.check_python_version()

        assert result["compatible"] is False
        assert "required" in result["message"]

    def test_check_platform_support_supported(self, checker):
        """Test platform support check with supported platform."""
        result = checker.check_platform_support()

        # Should be supported on any platform we test on
        assert result["supported"] is True
        assert result["platform"] in ["windows", "darwin", "linux"]

    def test_check_platform_support_unsupported(self, checker):
        """Test platform support check with unsupported platform."""
        with patch("platform.system", return_value="FakePlatform"):
            result = checker.check_platform_support()

        assert result["supported"] is False
        assert "not officially supported" in result["message"]

    def test_check_disk_space_sufficient(self, checker):
        """Test disk space check with sufficient space."""
        # Mock sufficient disk space
        mock_usage = Mock()
        mock_usage.free = 500 * 1024 * 1024  # 500MB

        with patch("shutil.disk_usage", return_value=mock_usage):
            result = checker.check_disk_space(required_mb=100)

        assert result["sufficient"] is True
        assert result["available_mb"] >= 100

    def test_check_disk_space_insufficient(self, checker):
        """Test disk space check with insufficient space."""
        # Mock insufficient disk space
        mock_usage = Mock()
        mock_usage.free = 50 * 1024 * 1024  # 50MB

        with patch("shutil.disk_usage", return_value=mock_usage):
            result = checker.check_disk_space(required_mb=100)

        assert result["sufficient"] is False
        assert "Insufficient disk space" in result["message"]

    def test_check_disk_space_error(self, checker):
        """Test disk space check with error."""
        with patch("shutil.disk_usage", side_effect=Exception("Disk error")):
            result = checker.check_disk_space()

        assert result["sufficient"] is True  # Assumes sufficient if can't check
        assert "Could not check disk space" in result["message"]

    def test_check_memory_sufficient(self, checker):
        """Test memory check with sufficient memory."""
        # Mock sufficient memory
        mock_memory = Mock()
        mock_memory.available = 1024 * 1024 * 1024  # 1GB
        mock_memory.total = 2 * 1024 * 1024 * 1024  # 2GB

        with patch("psutil.virtual_memory", return_value=mock_memory):
            result = checker.check_memory(required_mb=512)

        assert result["sufficient"] is True
        assert result["available_mb"] >= 512

    def test_check_memory_insufficient(self, checker):
        """Test memory check with insufficient memory."""
        # Mock insufficient memory
        mock_memory = Mock()
        mock_memory.available = 256 * 1024 * 1024  # 256MB
        mock_memory.total = 512 * 1024 * 1024  # 512MB

        with patch("psutil.virtual_memory", return_value=mock_memory):
            result = checker.check_memory(required_mb=512)

        assert result["sufficient"] is False
        assert "Low memory" in result["message"]

    def test_check_memory_error(self, checker):
        """Test memory check with error."""
        with patch("psutil.virtual_memory", side_effect=Exception("Memory error")):
            result = checker.check_memory()

        assert result["sufficient"] is True  # Assumes sufficient if can't check
        assert "Could not check memory usage" in result["message"]

    def test_check_permissions_adequate(self, checker):
        """Test permission check with adequate permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home", return_value=Path(temp_dir)):
                result = checker.check_permissions()

        assert result["adequate"] is True
        assert "Permissions adequate" in result["message"]

    def test_check_permissions_inadequate(self, checker):
        """Test permission check with inadequate permissions."""
        # Mock permission errors
        with (
            patch(
                "pathlib.Path.mkdir",
                side_effect=PermissionError("Permission denied"),
            ),
            patch(
                "pathlib.Path.touch",
                side_effect=PermissionError("Permission denied"),
            ),
        ):
            result = checker.check_permissions()

        assert result["adequate"] is False
        assert "Permission issues" in result["message"]

    def test_check_core_dependencies_available(self, checker):
        """Test core dependencies check with all available."""
        # Mock successful imports
        with patch("builtins.__import__", return_value=Mock()):
            result = checker.check_core_dependencies()

        assert len(result["missing"]) == 0
        assert len(result["available"]) > 0

    def test_check_core_dependencies_missing(self, checker):
        """Test core dependencies check with missing modules."""

        def mock_import(name, *args, **kwargs):
            if name in ["click", "yaml"]:
                raise ImportError(f"No module named '{name}'")
            return Mock()

        with patch("builtins.__import__", side_effect=mock_import):
            result = checker.check_core_dependencies()

        assert "click" in result["missing"]
        assert "yaml" in result["missing"]

    def test_check_command_availability_available(self, checker):
        """Test command availability check with available commands."""
        # Mock successful subprocess call
        with patch("subprocess.run", return_value=Mock(returncode=0)):
            result = checker.check_command_availability(["python", "pip"])

        assert "python" in result["available"]
        assert "pip" in result["available"]
        assert result["all_available"] is True

    def test_check_command_availability_missing(self, checker):
        """Test command availability check with missing commands."""
        # Mock failed subprocess call
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = checker.check_command_availability(["nonexistent"])

        assert "nonexistent" in result["missing"]
        assert result["all_available"] is False

    def test_get_system_summary(self, checker):
        """Test system summary generation."""
        result = checker.get_system_summary()

        assert "platform" in result
        assert "python" in result
        assert "resources" in result
        assert "system" in result["platform"]
        assert "version" in result["python"]
