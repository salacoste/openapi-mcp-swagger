"""Configuration-related exceptions."""

from typing import Any, Dict, Optional


class ConfigurationError(Exception):
    """Configuration-related error with user-friendly messages."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message
