"""Installation and setup management package."""

from .compatibility import SystemCompatibilityChecker
from .manager import InstallationError, InstallationManager
from .uninstaller import UninstallationError, UninstallationManager

__all__ = [
    "InstallationManager",
    "InstallationError",
    "SystemCompatibilityChecker",
    "UninstallationManager",
    "UninstallationError",
]
