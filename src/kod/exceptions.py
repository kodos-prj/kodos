"""Kodos exception hierarchy (Phases 1-5).

Structured exceptions replacing the global 'problems' list.
Enables better error handling, logging, and recovery.

Exception hierarchy:
    KodosError (base)
    ├── ConfigError
    │   ├── ValidationError
    │   ├── LoadError
    │   └── CompileError
    ├── PackageError
    │   ├── PackageInstallError
    │   ├── PackageNotFoundError
    │   └── DependencyError
    ├── SystemError
    │   ├── CommandError
    │   ├── UserError
    │   └── FilesystemError
    └── PluginError
        ├── PluginLoadError
        └── PluginValidationError

Each exception includes:
- Clear message describing the error
- Context (file, line, config key, package name, etc.)
- Suggestions for recovery when possible

Example:
    >>> try:
    ...     schema.validate(config)
    ... except ValidationError as e:
    ...     print(f"Config error at {e.location}: {e.message}")
    ...     print(f"Suggestion: {e.suggestion}")
"""

from typing import Optional, Dict, Any


class KodosError(Exception):
    """Base exception for all Kodos errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize KodosError.

        Args:
            message: Error message
            context: Additional context (file, line, key, etc.)
        """
        self.message = message
        self.context = context or {}
        super().__init__(self.format_message())

    def format_message(self) -> str:
        """Format error message with context."""
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx_str})"
        return self.message


# Configuration Errors


class ConfigError(KodosError):
    """Configuration error."""

    pass


class ValidationError(ConfigError):
    """Configuration validation failed."""

    def __init__(
        self,
        message: str,
        location: Optional[str] = None,
        suggestion: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize ValidationError.

        Args:
            message: Error message
            location: Where error occurred (config path, line number, etc.)
            suggestion: Suggestion for fixing the error
            context: Additional context
        """
        super().__init__(message, context)
        self.location = location
        self.suggestion = suggestion


class LoadError(ConfigError):
    """Failed to load configuration file."""

    pass


class CompileError(ConfigError):
    """Failed to compile configuration."""

    pass


# Package Errors


class PackageError(KodosError):
    """Package operation error."""

    pass


class PackageInstallError(PackageError):
    """Failed to install package."""

    pass


class PackageNotFoundError(PackageError):
    """Package not found in any repository."""

    pass


class DependencyError(PackageError):
    """Dependency resolution failed."""

    pass


# System Errors


class SystemError(KodosError):
    """System operation error."""

    pass


class CommandError(SystemError):
    """Shell command failed."""

    def __init__(
        self,
        message: str,
        command: Optional[str] = None,
        return_code: Optional[int] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize CommandError.

        Args:
            message: Error message
            command: Command that failed
            return_code: Process return code
            stdout: Standard output
            stderr: Standard error
            context: Additional context
        """
        super().__init__(message, context)
        self.command = command
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


class UserError(SystemError):
    """User management operation failed."""

    pass


class FilesystemError(SystemError):
    """Filesystem operation failed."""

    pass


# Plugin Errors


class PluginError(KodosError):
    """Plugin operation error."""

    pass


class PluginLoadError(PluginError):
    """Failed to load plugin."""

    pass


class PluginValidationError(PluginError):
    """Plugin validation failed."""

    pass
