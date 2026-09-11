"""Kodos exceptions."""

from typing import Any, Dict, Optional


class KodosError(Exception):
    """Base exception for all Kodos errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.context = context or {}
        super().__init__(self.format_message())

    def format_message(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx_str})"
        return self.message


class ValidationError(KodosError):
    """Configuration validation failed."""

    def __init__(
        self,
        message: str,
        location: Optional[str] = None,
        suggestion: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, context)
        self.location = location
        self.suggestion = suggestion
