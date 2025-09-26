"""System compatibility and dependency checking."""

import os
import sys
import shutil
import platform
import subprocess
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, Any, Optional
import psutil


class SystemCompatibilityChecker:
    """Checks system compatibility and dependencies."""

    def __init__(self):
        self.platform = platform.system().lower()
        self.python_version = sys.version_info

    async def check_system_compatibility(self) -> Dict[str, Any]:
        """Comprehensive system compatibility check."""
        compatibility_report = {
            "compatible": True,
            "issues": [],
            "warnings": [],
            "system_info": {}
        }

        # Python version check
        python_check = self.check_python_version()
        compatibility_report["system_info"]["python"] = python_check
        if not python_check["compatible"]:
            compatibility_report["compatible"] = False
            compatibility_report["issues"].append(python_check["message"])

        # Platform support check
        platform_check = self.check_platform_support()
        compatibility_report["system_info"]["platform"] = platform_check
        if not platform_check["supported"]:
            compatibility_report["compatible"] = False
            compatibility_report["issues"].append(platform_check["message"])

        # Disk space check
        disk_check = self.check_disk_space()
        compatibility_report["system_info"]["disk"] = disk_check
        if not disk_check["sufficient"]:
            compatibility_report["warnings"].append(disk_check["message"])

        # Memory check
        memory_check = self.check_memory()
        compatibility_report["system_info"]["memory"] = memory_check
        if not memory_check["sufficient"]:
            compatibility_report["warnings"].append(memory_check["message"])

        # Network connectivity check (optional)
        network_check = await self.check_network_connectivity()
        compatibility_report["system_info"]["network"] = network_check
        if not network_check["available"]:
            compatibility_report["warnings"].append(network_check["message"])

        # Permission check
        permission_check = self.check_permissions()
        compatibility_report["system_info"]["permissions"] = permission_check
        if not permission_check["adequate"]:
            compatibility_report["issues"].append(permission_check["message"])

        # Dependency availability check
        dependency_check = self.check_core_dependencies()
        compatibility_report["system_info"]["dependencies"] = dependency_check
        if dependency_check["missing"]:
            compatibility_report["warnings"].append(
                f"Some optional dependencies missing: {dependency_check['missing']}"
            )

        return compatibility_report

    def check_python_version(self) -> Dict[str, Any]:
        """Check Python version compatibility."""
        min_version = (3, 9)
        current_version = sys.version_info[:2]

        if current_version >= min_version:
            return {
                "compatible": True,
                "current": f"{current_version[0]}.{current_version[1]}",
                "required": f"{min_version[0]}.{min_version[1]}+",
                "message": f"Python {current_version[0]}.{current_version[1]} is supported"
            }
        else:
            return {
                "compatible": False,
                "current": f"{current_version[0]}.{current_version[1]}",
                "required": f"{min_version[0]}.{min_version[1]}+",
                "message": f"Python {min_version[0]}.{min_version[1]}+ required, found {current_version[0]}.{current_version[1]}"
            }

    def check_platform_support(self) -> Dict[str, Any]:
        """Check operating system support."""
        supported_platforms = ["windows", "darwin", "linux"]
        current_platform = platform.system().lower()

        if current_platform in supported_platforms:
            return {
                "supported": True,
                "platform": current_platform,
                "version": platform.release(),
                "message": f"{platform.system()} {platform.release()} is supported"
            }
        else:
            return {
                "supported": False,
                "platform": current_platform,
                "version": platform.release(),
                "message": f"{platform.system()} is not officially supported"
            }

    def check_disk_space(self, required_mb: int = 100) -> Dict[str, Any]:
        """Check available disk space."""
        try:
            install_path = Path.home()
            disk_usage = shutil.disk_usage(install_path)
            available_mb = disk_usage.free / (1024 * 1024)

            if available_mb >= required_mb:
                return {
                    "sufficient": True,
                    "available_mb": int(available_mb),
                    "required_mb": required_mb,
                    "message": f"{int(available_mb)}MB available (≥{required_mb}MB required)"
                }
            else:
                return {
                    "sufficient": False,
                    "available_mb": int(available_mb),
                    "required_mb": required_mb,
                    "message": f"Insufficient disk space: {int(available_mb)}MB available, {required_mb}MB required"
                }

        except Exception:
            return {
                "sufficient": True,  # Assume sufficient if can't check
                "message": "Could not check disk space"
            }

    def check_memory(self, required_mb: int = 512) -> Dict[str, Any]:
        """Check available system memory."""
        try:
            memory = psutil.virtual_memory()
            available_mb = memory.available / (1024 * 1024)
            total_mb = memory.total / (1024 * 1024)

            if available_mb >= required_mb:
                return {
                    "sufficient": True,
                    "available_mb": int(available_mb),
                    "total_mb": int(total_mb),
                    "required_mb": required_mb,
                    "message": f"{int(available_mb)}MB available (≥{required_mb}MB required)"
                }
            else:
                return {
                    "sufficient": False,
                    "available_mb": int(available_mb),
                    "total_mb": int(total_mb),
                    "required_mb": required_mb,
                    "message": f"Low memory: {int(available_mb)}MB available, {required_mb}MB recommended"
                }

        except Exception:
            return {
                "sufficient": True,  # Assume sufficient if can't check
                "message": "Could not check memory usage"
            }

    async def check_network_connectivity(self, timeout: int = 5) -> Dict[str, Any]:
        """Check basic network connectivity (optional for offline use)."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.get('https://pypi.org') as response:
                    if response.status == 200:
                        return {
                            "available": True,
                            "message": "Network connectivity available",
                            "details": "Can access PyPI for package updates"
                        }
                    else:
                        return {
                            "available": False,
                            "message": f"Network available but PyPI unreachable (status: {response.status})",
                            "details": "Package updates may not be available"
                        }

        except asyncio.TimeoutError:
            return {
                "available": False,
                "message": "Network connectivity timeout",
                "details": "Tool will work offline, but package updates unavailable"
            }
        except Exception as e:
            return {
                "available": False,
                "message": f"Network check failed: {str(e)}",
                "details": "Tool will work offline, but package updates unavailable"
            }

    def check_permissions(self) -> Dict[str, Any]:
        """Check file system permissions for installation."""
        home_dir = Path.home()
        install_dir = home_dir / ".swagger-mcp-server"

        permission_issues = []

        # Check if we can create directories in home
        try:
            test_dir = install_dir / "test_permissions"
            test_dir.mkdir(parents=True, exist_ok=True)
            test_dir.rmdir()
        except PermissionError:
            permission_issues.append("Cannot create directories in home folder")

        # Check if we can create files
        try:
            test_file = home_dir / ".swagger_mcp_test"
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            permission_issues.append("Cannot create files in home folder")

        # Check write permissions on existing install directory
        if install_dir.exists() and not os.access(install_dir, os.W_OK):
            permission_issues.append("No write permission on existing installation directory")

        return {
            "adequate": len(permission_issues) == 0,
            "message": "Permissions adequate" if not permission_issues else f"Permission issues: {len(permission_issues)}",
            "details": {"issues": permission_issues}
        }

    def check_core_dependencies(self) -> Dict[str, Any]:
        """Check availability of core Python dependencies."""
        core_modules = {
            "click": "Command-line interface framework",
            "yaml": "YAML configuration support",
            "whoosh": "Search engine",
            "psutil": "System utilities",
            "aiohttp": "HTTP client/server",
            "jsonref": "JSON reference resolution",
        }

        optional_modules = {
            "openapi_spec_validator": "OpenAPI validation",
            "structlog": "Structured logging",
            "aiofiles": "Async file operations"
        }

        available = []
        missing = []
        optional_missing = []

        # Check core modules
        for module, description in core_modules.items():
            try:
                __import__(module)
                available.append({"module": module, "description": description})
            except ImportError:
                missing.append({"module": module, "description": description})

        # Check optional modules
        for module, description in optional_modules.items():
            try:
                __import__(module)
                available.append({"module": module, "description": description})
            except ImportError:
                optional_missing.append({"module": module, "description": description})

        return {
            "available": available,
            "missing": [m["module"] for m in missing],
            "optional_missing": [m["module"] for m in optional_missing],
            "details": {
                "core_available": len(available),
                "core_missing": missing,
                "optional_missing": optional_missing
            }
        }

    def check_command_availability(self, commands: list) -> Dict[str, Any]:
        """Check if system commands are available."""
        available_commands = []
        missing_commands = []

        for command in commands:
            try:
                subprocess.run([command, "--version"],
                             capture_output=True,
                             check=True,
                             timeout=5)
                available_commands.append(command)
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                missing_commands.append(command)

        return {
            "available": available_commands,
            "missing": missing_commands,
            "all_available": len(missing_commands) == 0
        }

    def get_system_summary(self) -> Dict[str, Any]:
        """Get comprehensive system summary."""
        return {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor()
            },
            "python": {
                "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "implementation": platform.python_implementation(),
                "executable": sys.executable
            },
            "resources": {
                "cpu_count": psutil.cpu_count(),
                "memory_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "disk_free_gb": round(shutil.disk_usage(Path.home()).free / (1024**3), 2)
            }
        }