"""Installation and setup management package."""

from .manager import InstallationManager, InstallationError
from .compatibility import SystemCompatibilityChecker
from .uninstaller import UninstallationManager, UninstallationError

__all__ = [
    "InstallationManager",
    "InstallationError",
    "SystemCompatibilityChecker",
    "UninstallationManager",
    "UninstallationError",
]