"""Uninstallation and cleanup management."""

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class UninstallationError(Exception):
    """Uninstallation-related error with context information."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class UninstallationManager:
    """Handles clean uninstallation and file cleanup."""

    def __init__(self):
        self.platform = platform.system().lower()
        self.install_dir = Path.home() / ".swagger-mcp-server"
        self.config_dir = self.install_dir / "config"
        self.data_dir = self.install_dir / "data"
        self.logs_dir = self.install_dir / "logs"
        self.backup_dir = self.install_dir / "backups"

    async def perform_uninstallation(
        self, preserve_config: bool = False, preserve_data: bool = False
    ) -> Dict[str, Any]:
        """Perform complete system uninstallation."""
        uninstall_results = {
            "removed_items": [],
            "preserved_items": [],
            "warnings": [],
            "errors": [],
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # Stop any running servers first
            await self._stop_running_servers(uninstall_results)

            # Remove or preserve user data
            if preserve_data:
                await self._preserve_user_data(uninstall_results)
            else:
                await self._remove_all_data(uninstall_results)

            # Selective cleanup based on preserve flags
            if preserve_config:
                await self._selective_cleanup(uninstall_results)
            else:
                await self._complete_cleanup(uninstall_results)

            # Try to uninstall pip package
            pip_result = await self._uninstall_pip_package()
            if pip_result["success"]:
                uninstall_results["removed_items"].append("pip package")
            else:
                uninstall_results["warnings"].append(pip_result["message"])

            # Clean up temporary files
            temp_cleanup = await self._cleanup_temp_files()
            uninstall_results["removed_items"].extend(temp_cleanup)

            # Create uninstallation log
            await self._create_uninstall_log(uninstall_results)

            return uninstall_results

        except Exception as e:
            uninstall_results["errors"].append(str(e))
            raise UninstallationError(
                f"Uninstallation failed: {str(e)}", uninstall_results
            )

    async def _stop_running_servers(self, results: Dict[str, Any]) -> None:
        """Stop any running MCP servers before uninstallation."""
        try:
            from ..management import MCPServerManager

            manager = MCPServerManager()
            all_servers = await manager.get_all_servers_status()

            if all_servers:
                results["warnings"].append(
                    f"Stopping {len(all_servers)} running servers"
                )

                for server_status in all_servers:
                    server_id = server_status["server"]["id"]
                    try:
                        await manager.stop_server(
                            server_id, force=True, timeout=10
                        )
                        results["removed_items"].append(
                            f"stopped server: {server_id}"
                        )
                    except Exception as e:
                        results["warnings"].append(
                            f"Could not stop server {server_id}: {e}"
                        )

        except ImportError:
            # Server management not available
            pass
        except Exception as e:
            results["warnings"].append(f"Error stopping servers: {e}")

    async def _preserve_user_data(self, results: Dict[str, Any]) -> None:
        """Preserve user data during uninstallation."""
        preserve_items = [
            (self.data_dir / "database", "user databases"),
            (self.config_dir / "config.yaml", "user configuration"),
            (self.config_dir / "servers.json", "server registry"),
        ]

        backup_dir = (
            Path.home()
            / f".swagger-mcp-server-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        backup_dir.mkdir(exist_ok=True)

        for item_path, description in preserve_items:
            if item_path.exists():
                try:
                    backup_path = backup_dir / item_path.name
                    if item_path.is_dir():
                        shutil.copytree(item_path, backup_path)
                    else:
                        shutil.copy2(item_path, backup_path)

                    results["preserved_items"].append(
                        f"{description}: backed up to {backup_path}"
                    )
                except Exception as e:
                    results["warnings"].append(
                        f"Could not backup {description}: {e}"
                    )

    async def _remove_all_data(self, results: Dict[str, Any]) -> None:
        """Remove all data directories."""
        if self.data_dir.exists():
            try:
                shutil.rmtree(self.data_dir)
                results["removed_items"].append(
                    f"data directory: {self.data_dir}"
                )
            except Exception as e:
                results["warnings"].append(
                    f"Could not remove data directory: {e}"
                )

    async def _selective_cleanup(self, results: Dict[str, Any]) -> None:
        """Selective cleanup preserving user configuration."""
        # Remove cache directories
        cache_dirs = [
            self.data_dir / "search_index",
            self.data_dir / "temp",
            self.install_dir / "__pycache__",
            self.install_dir / ".cache",
        ]

        for cache_dir in cache_dirs:
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir)
                    results["removed_items"].append(f"cache: {cache_dir.name}")
                except Exception as e:
                    results["warnings"].append(
                        f"Could not remove cache {cache_dir.name}: {e}"
                    )

        # Remove log files
        if self.logs_dir.exists():
            try:
                log_files = list(self.logs_dir.glob("*.log"))
                for log_file in log_files:
                    log_file.unlink()
                    results["removed_items"].append(f"log: {log_file.name}")

                # Remove logs directory if empty
                if not any(self.logs_dir.iterdir()):
                    self.logs_dir.rmdir()
                    results["removed_items"].append("logs directory")
            except Exception as e:
                results["warnings"].append(f"Could not remove log files: {e}")

        # Remove backup directory
        if self.backup_dir.exists():
            try:
                shutil.rmtree(self.backup_dir)
                results["removed_items"].append("backup directory")
            except Exception as e:
                results["warnings"].append(
                    f"Could not remove backup directory: {e}"
                )

        # Preserve configuration files
        config_files = ["config.yaml", "servers.json"]
        for config_file in config_files:
            config_path = self.config_dir / config_file
            if config_path.exists():
                results["preserved_items"].append(f"config: {config_file}")

    async def _complete_cleanup(self, results: Dict[str, Any]) -> None:
        """Complete cleanup removing all files."""
        if self.install_dir.exists():
            try:
                # Remove the entire installation directory
                shutil.rmtree(self.install_dir)
                results["removed_items"].append(
                    f"installation directory: {self.install_dir}"
                )
            except Exception as e:
                results["warnings"].append(
                    f"Could not remove installation directory: {e}"
                )

                # Try to remove individual components
                for subdir in [
                    self.config_dir,
                    self.data_dir,
                    self.logs_dir,
                    self.backup_dir,
                ]:
                    if subdir.exists():
                        try:
                            shutil.rmtree(subdir)
                            results["removed_items"].append(
                                f"directory: {subdir.name}"
                            )
                        except Exception as sub_e:
                            results["warnings"].append(
                                f"Could not remove {subdir.name}: {sub_e}"
                            )

    async def _uninstall_pip_package(self) -> Dict[str, Any]:
        """Attempt to uninstall the pip package."""
        try:
            # Check if package is installed
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", "swagger-mcp-server"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return {
                    "success": True,
                    "message": "Package not installed via pip",
                }

            # Uninstall the package
            uninstall_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "uninstall",
                    "swagger-mcp-server",
                    "-y",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if uninstall_result.returncode == 0:
                return {
                    "success": True,
                    "message": "Package uninstalled successfully",
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to uninstall package: {uninstall_result.stderr}",
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "Package uninstallation timed out",
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error during package uninstallation: {str(e)}",
            }

    async def _cleanup_temp_files(self) -> List[str]:
        """Clean up temporary files and directories."""
        removed_items = []

        # Common temporary locations
        temp_locations = [
            Path.home() / ".swagger_mcp_temp",
            Path("/tmp") / "swagger_mcp_server"
            if self.platform != "windows"
            else None,
            Path(os.getenv("TEMP", "")) / "swagger_mcp_server"
            if self.platform == "windows"
            else None,
        ]

        temp_locations = [loc for loc in temp_locations if loc is not None]

        for temp_location in temp_locations:
            if temp_location.exists():
                try:
                    if temp_location.is_dir():
                        shutil.rmtree(temp_location)
                    else:
                        temp_location.unlink()
                    removed_items.append(f"temp: {temp_location.name}")
                except Exception:
                    # Ignore temp file cleanup errors
                    pass

        return removed_items

    async def _create_uninstall_log(self, results: Dict[str, Any]) -> None:
        """Create a log of the uninstallation process."""
        try:
            uninstall_log = (
                Path.home()
                / f"swagger-mcp-server-uninstall-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            )

            log_content = f"""Swagger MCP Server Uninstallation Log
=====================================
Timestamp: {results['timestamp']}
Platform: {platform.system()} {platform.release()}
Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}

Removed Items:
{chr(10).join(f"  - {item}" for item in results['removed_items'])}

Preserved Items:
{chr(10).join(f"  - {item}" for item in results['preserved_items'])}

Warnings:
{chr(10).join(f"  - {warning}" for warning in results['warnings'])}

Errors:
{chr(10).join(f"  - {error}" for error in results['errors'])}

Uninstallation Status: {'Completed' if not results['errors'] else 'Completed with errors'}
"""

            with open(uninstall_log, "w") as f:
                f.write(log_content)

        except Exception:
            # Don't fail uninstallation if we can't write log
            pass

    async def get_uninstall_preview(
        self, preserve_config: bool = False, preserve_data: bool = False
    ) -> Dict[str, Any]:
        """Preview what would be removed during uninstallation."""
        preview = {"will_remove": [], "will_preserve": [], "warnings": []}

        if not self.install_dir.exists():
            preview["warnings"].append("Installation directory does not exist")
            return preview

        # Check what would be removed/preserved
        all_items = [
            (self.config_dir, "configuration directory"),
            (self.data_dir, "data directory"),
            (self.logs_dir, "logs directory"),
            (self.backup_dir, "backup directory"),
        ]

        for item_path, description in all_items:
            if item_path.exists():
                if preserve_config and "config" in description:
                    preview["will_preserve"].append(description)
                elif preserve_data and "data" in description:
                    preview["will_preserve"].append(description)
                else:
                    preview["will_remove"].append(description)

        # Check for running servers
        try:
            from ..management import MCPServerManager

            manager = MCPServerManager()
            all_servers = await manager.get_all_servers_status()
            if all_servers:
                preview["warnings"].append(
                    f"{len(all_servers)} running servers will be stopped"
                )
        except Exception:
            pass

        return preview
