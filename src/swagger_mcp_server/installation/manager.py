"""Installation management system for swagger-mcp-server."""

import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .compatibility import SystemCompatibilityChecker


class InstallationError(Exception):
    """Installation-related error with context information."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class InstallationManager:
    """Manages installation, setup, and verification processes."""

    def __init__(self):
        self.platform = platform.system().lower()
        self.python_version = sys.version_info
        self.install_dir = Path.home() / ".swagger-mcp-server"
        self.config_dir = self.install_dir / "config"
        self.data_dir = self.install_dir / "data"
        self.logs_dir = self.install_dir / "logs"
        self.backup_dir = self.install_dir / "backups"
        self.compatibility_checker = SystemCompatibilityChecker()

    def is_already_setup(self) -> bool:
        """Check if system is already set up."""
        return (
            self.install_dir.exists()
            and self.config_dir.exists()
            and (self.config_dir / "config.yaml").exists()
        )

    async def perform_setup(self, force: bool = False) -> Dict[str, Any]:
        """Perform complete system setup."""
        setup_results = {
            "steps_completed": [],
            "warnings": [],
            "errors": [],
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Step 1: System compatibility check
            compatibility_result = (
                await self.compatibility_checker.check_system_compatibility()
            )

            if not compatibility_result["compatible"]:
                raise InstallationError(
                    "System compatibility check failed",
                    {"issues": compatibility_result["issues"]},
                )

            setup_results["steps_completed"].append("System compatibility verified")
            setup_results["warnings"].extend(compatibility_result.get("warnings", []))

            # Step 2: Create directory structure
            await self.create_directory_structure(force)
            setup_results["steps_completed"].append("Directory structure created")

            # Step 3: Initialize configuration
            await self.initialize_configuration(force)
            setup_results["steps_completed"].append("Configuration initialized")

            # Step 4: Set up database and search directories
            await self.setup_data_directories()
            setup_results["steps_completed"].append("Data directories configured")

            # Step 5: Create initial logging setup
            await self.setup_logging()
            setup_results["steps_completed"].append("Logging configured")

            # Step 6: Verify installation
            verification_result = await self.verify_installation()
            setup_results["steps_completed"].append("Installation verified")

            if verification_result.get("warnings"):
                setup_results["warnings"].extend(verification_result["warnings"])

            # Step 7: Record installation metadata
            await self.record_installation_metadata()
            setup_results["steps_completed"].append("Installation metadata recorded")

            return setup_results

        except Exception as e:
            setup_results["errors"].append(str(e))
            raise InstallationError(f"Setup failed: {str(e)}", setup_results)

    async def create_directory_structure(self, force: bool = False) -> None:
        """Create required directory structure."""
        directories = [
            self.install_dir,
            self.config_dir,
            self.data_dir,
            self.logs_dir,
            self.backup_dir,
            self.data_dir / "database",
            self.data_dir / "search_index",
            self.data_dir / "temp",
        ]

        for directory in directories:
            if directory.exists() and not force:
                continue

            directory.mkdir(parents=True, exist_ok=True)

            # Set appropriate permissions
            if self.platform != "windows":
                os.chmod(directory, 0o755)

    async def initialize_configuration(self, force: bool = False) -> None:
        """Initialize configuration files."""
        from ..config import ConfigurationManager

        config_file = self.config_dir / "config.yaml"

        if config_file.exists() and not force:
            return

        # Initialize with development template for first-time setup
        config_manager = ConfigurationManager(config_dir=self.install_dir)
        await config_manager.initialize_configuration(
            "development", str(config_file), force
        )

        # Create servers registry file
        servers_file = self.config_dir / "servers.json"
        if not servers_file.exists() or force:
            initial_servers = {
                "version": "1.0",
                "servers": {},
                "last_updated": datetime.now().isoformat(),
            }
            with open(servers_file, "w") as f:
                json.dump(initial_servers, f, indent=2)

    async def setup_data_directories(self) -> None:
        """Set up database and search index directories."""
        # Create database directory with proper structure
        db_dir = self.data_dir / "database"
        db_dir.mkdir(parents=True, exist_ok=True)

        # Create search index directory
        search_dir = self.data_dir / "search_index"
        search_dir.mkdir(parents=True, exist_ok=True)

        # Create temp directory for processing
        temp_dir = self.data_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

    async def setup_logging(self) -> None:
        """Set up logging configuration."""
        # Create log files with proper permissions
        log_files = [
            self.logs_dir / "server.log",
            self.logs_dir / "conversion.log",
            self.logs_dir / "setup.log",
        ]

        for log_file in log_files:
            if not log_file.exists():
                log_file.touch()

                # Set appropriate permissions
                if self.platform != "windows":
                    os.chmod(log_file, 0o644)

    async def verify_installation(self) -> Dict[str, Any]:
        """Verify installation completeness and functionality."""
        verification_result = {
            "status": "success",
            "components": {},
            "system_info": {},
            "warnings": [],
            "issues": [],
        }

        try:
            # Check directory structure
            verification_result["components"][
                "directories"
            ] = await self._verify_directories()

            # Check configuration files
            verification_result["components"][
                "configuration"
            ] = await self._verify_configuration()

            # Check permissions
            verification_result["components"][
                "permissions"
            ] = await self._verify_permissions()

            # Check Python dependencies
            verification_result["components"][
                "dependencies"
            ] = await self._verify_dependencies()

            # Gather system information
            verification_result["system_info"] = await self._gather_system_info()

            # Check for any component failures
            failed_components = [
                name
                for name, result in verification_result["components"].items()
                if not result.get("working", True)
            ]

            if failed_components:
                verification_result["status"] = "failed"
                verification_result["issues"].extend(
                    [
                        f"Component '{name}' verification failed"
                        for name in failed_components
                    ]
                )

        except Exception as e:
            verification_result["status"] = "error"
            verification_result["issues"].append(f"Verification error: {str(e)}")

        return verification_result

    async def _verify_directories(self) -> Dict[str, Any]:
        """Verify directory structure."""
        required_dirs = [
            self.install_dir,
            self.config_dir,
            self.data_dir,
            self.logs_dir,
            self.backup_dir,
        ]

        missing_dirs = [d for d in required_dirs if not d.exists()]

        return {
            "working": len(missing_dirs) == 0,
            "message": "All directories exist"
            if not missing_dirs
            else f"Missing directories: {missing_dirs}",
            "details": {
                "required": len(required_dirs),
                "existing": len(required_dirs) - len(missing_dirs),
                "missing": [str(d) for d in missing_dirs],
            },
        }

    async def _verify_configuration(self) -> Dict[str, Any]:
        """Verify configuration files."""
        try:
            from ..config import ConfigurationManager

            config_manager = ConfigurationManager(config_dir=self.install_dir)
            (
                is_valid,
                errors,
                warnings,
            ) = await config_manager.validate_configuration()

            return {
                "working": is_valid,
                "message": "Configuration valid"
                if is_valid
                else f"Configuration errors: {len(errors)}",
                "details": {"errors": errors, "warnings": warnings},
            }
        except Exception as e:
            return {
                "working": False,
                "message": f"Configuration verification failed: {str(e)}",
                "details": {"error": str(e)},
            }

    async def _verify_permissions(self) -> Dict[str, Any]:
        """Verify file and directory permissions."""
        permission_issues = []

        # Check write permissions on key directories
        dirs_to_check = [
            self.install_dir,
            self.config_dir,
            self.data_dir,
            self.logs_dir,
        ]

        for directory in dirs_to_check:
            if not os.access(directory, os.W_OK):
                permission_issues.append(f"No write permission: {directory}")

        return {
            "working": len(permission_issues) == 0,
            "message": "Permissions OK"
            if not permission_issues
            else f"Permission issues: {len(permission_issues)}",
            "details": {"issues": permission_issues},
        }

    async def _verify_dependencies(self) -> Dict[str, Any]:
        """Verify Python dependencies are available."""
        required_modules = [
            "click",
            "yaml",
            "aiofiles",
            "whoosh",
            "psutil",
            "aiohttp",
            "jsonref",
            "openapi_spec_validator",
        ]

        missing_modules = []

        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)

        return {
            "working": len(missing_modules) == 0,
            "message": "All dependencies available"
            if not missing_modules
            else f"Missing modules: {missing_modules}",
            "details": {
                "required": len(required_modules),
                "available": len(required_modules) - len(missing_modules),
                "missing": missing_modules,
            },
        }

    async def _gather_system_info(self) -> Dict[str, Any]:
        """Gather system information for verification report."""
        return {
            "platform": f"{platform.system()} {platform.release()}",
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "install_path": str(self.install_dir),
            "python_executable": sys.executable,
            "architecture": platform.machine(),
            "processor": platform.processor() if platform.processor() else "Unknown",
        }

    async def record_installation_metadata(self) -> None:
        """Record installation metadata for tracking and support."""
        metadata = {
            "installation_date": datetime.now().isoformat(),
            "version": self._get_package_version(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
            "python": {
                "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "executable": sys.executable,
                "implementation": platform.python_implementation(),
            },
            "installation_path": str(self.install_dir),
            "directories": {
                "config": str(self.config_dir),
                "data": str(self.data_dir),
                "logs": str(self.logs_dir),
                "backup": str(self.backup_dir),
            },
        }

        metadata_file = self.install_dir / "installation_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def _get_package_version(self) -> str:
        """Get package version."""
        try:
            from ..__version__ import __version__

            return __version__
        except ImportError:
            return "unknown"

    async def get_installation_info(self) -> Dict[str, Any]:
        """Get comprehensive installation information."""
        info = {
            "installed": self.is_already_setup(),
            "install_directory": str(self.install_dir),
            "platform": self.platform,
            "python_version": f"{self.python_version.major}.{self.python_version.minor}",
        }

        if self.is_already_setup():
            # Load metadata if available
            metadata_file = self.install_dir / "installation_metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                    info["installation_metadata"] = metadata
                except Exception:
                    pass

            # Add configuration status
            try:
                from ..config import ConfigurationManager

                config_manager = ConfigurationManager(config_dir=self.install_dir)
                (
                    is_valid,
                    errors,
                    warnings,
                ) = await config_manager.validate_configuration()
                info["configuration_status"] = {
                    "valid": is_valid,
                    "errors": len(errors),
                    "warnings": len(warnings),
                }
            except Exception as e:
                info["configuration_status"] = {"error": str(e)}

        return info
