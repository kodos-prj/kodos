"""Common utility functions and debugging utilities for KodOS.

This module provides core utility functions for command execution, debugging,
and system interaction used throughout the KodOS system.
"""

import logging
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

use_debug: bool = True
use_verbose: bool = False

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class CommandExecutionError(Exception):
    """Raised when a command execution fails."""

    cmd: str
    return_code: int
    stderr: str = ""
    stdout: str = ""

    def __post_init__(self):
        super().__init__(f"Command failed with return code {self.return_code}: {self.cmd}")


@dataclass
class CommandTimeoutError(Exception):
    """Raised when a command execution times out."""

    cmd: str
    timeout: Optional[int]

    def __post_init__(self):
        timeout_str = f"{self.timeout}s" if self.timeout is not None else "unknown"
        super().__init__(f"Command timed out after {timeout_str}: {self.cmd}")


@dataclass
class UnsafeCommandError(Exception):
    """Raised when a command contains potentially unsafe characters."""

    cmd: str
    reason: str

    def __post_init__(self):
        super().__init__(f"Unsafe command rejected: {self.reason} in '{self.cmd}'")


class color:
    """ANSI color codes for terminal output formatting."""

    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def set_debug(val: bool = True) -> None:
    """Set the global debug mode state.

    Args:
        val: Whether to enable debug mode. Defaults to True.
    """
    global use_debug
    use_debug = val


def set_verbose(val: bool = True) -> None:
    """Set the global verbose mode state.

    Args:
        val: Whether to enable verbose mode. Defaults to True.
    """
    global use_verbose
    use_verbose = val


def _validate_command(cmd: str, allow_unsafe: bool = False) -> None:
    """Validate command for basic safety checks.

    Args:
        cmd: The command to validate
        allow_unsafe: Whether to allow potentially unsafe commands

    Raises:
        UnsafeCommandError: If command contains unsafe patterns and allow_unsafe is False
    """
    if not allow_unsafe:
        # Check for potentially dangerous patterns (Unix/Linux only)
        unsafe_patterns = [
            "rm -rf /",
            "rm -rf /*",
            ";rm -rf /",
            ";rm -rf /*",
            ">/dev/sd",
            "dd if=/dev/zero of=/dev/sd",
        ]

        cmd_lower = cmd.lower()
        for pattern in unsafe_patterns:
            if pattern in cmd_lower:
                raise UnsafeCommandError(cmd, f"Contains dangerous pattern: {pattern}")


def exec(
    cmd: str,
    get_output: bool = False,
    check_return_code: bool = True,
    timeout: Optional[int] = None,
    allow_unsafe: bool = False,
    encoding: str = "utf-8",
) -> str:
    """Execute a shell command with comprehensive error handling.

    This is a critical function that handles command execution throughout KodOS.
    It provides proper error handling, return code checking, timeout support,
    and basic security validation.

    Args:
        cmd: The shell command to execute.
        get_output: Whether to return command output. Defaults to False.
        check_return_code: Whether to check and raise on non-zero return codes. Defaults to True.
        timeout: Command timeout in seconds. None for no timeout.
        allow_unsafe: Whether to allow potentially unsafe commands. Defaults to False.
        encoding: Text encoding for command output. Defaults to 'utf-8'.

    Returns:
        Command output if get_output=True, empty string otherwise.

    Raises:
        CommandExecutionError: If command fails and check_return_code is True.
        CommandTimeoutError: If command times out.
        UnsafeCommandError: If command contains unsafe patterns and allow_unsafe is False.
        OSError: For system-level execution errors.
    """
    # Validate command safety
    _validate_command(cmd, allow_unsafe)

    if use_debug or use_verbose:
        print(">>", color.PURPLE + cmd + color.END)

    # In debug mode, only print commands but don't execute
    if use_debug:
        return ""

    try:
        if get_output:
            # Use subprocess for better control and error handling
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, encoding=encoding)

            if check_return_code and result.returncode != 0:
                logger.error(f"Command failed: {cmd}")
                logger.error(f"Return code: {result.returncode}")
                logger.error(f"Stderr: {result.stderr}")
                raise CommandExecutionError(cmd, result.returncode, result.stderr, result.stdout)

            return result.stdout
        else:
            # For commands without output capture, use subprocess.run
            result = subprocess.run(cmd, shell=True, timeout=timeout)

            if check_return_code and result.returncode != 0:
                logger.error(f"Command failed: {cmd}")
                logger.error(f"Return code: {result.returncode}")
                raise CommandExecutionError(cmd, result.returncode)

            return ""

    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {cmd}")
        raise CommandTimeoutError(cmd, timeout)
    except OSError as e:
        logger.error(f"OS error executing command '{cmd}': {e}")
        raise


def exec_safe(cmd: str, *args, **kwargs) -> str:
    """Execute a command with automatic shell escaping for arguments.

    This function provides a safer alternative to exec() by automatically
    escaping shell arguments to prevent injection attacks.

    Args:
        cmd: Base command (will be shell-escaped)
        *args: Additional arguments (will be shell-escaped)
        **kwargs: Additional keyword arguments passed to exec()

    Returns:
        Command output as returned by exec()
    """
    # Escape the base command and arguments
    escaped_cmd = shlex.quote(cmd)
    escaped_args = [shlex.quote(str(arg)) for arg in args]

    # Construct the full command
    full_cmd = escaped_cmd
    if escaped_args:
        full_cmd += " " + " ".join(escaped_args)

    return exec(full_cmd, **kwargs)


def exec_chroot(cmd: str, mount_point: str = "/mnt", get_output: bool = False, **kwargs) -> str:
    """Execute a command within a chroot environment with error handling.

    Args:
        cmd: The command to execute inside the chroot.
        mount_point: The mount point for the chroot. Defaults to "/mnt".
        get_output: Whether to return command output. Defaults to False.
        **kwargs: Additional arguments passed to exec().

    Returns:
        Command output from the chroot execution.

    Raises:
        CommandExecutionError: If chroot command fails.
        OSError: If chroot environment is not accessible.
    """
    # Validate that mount_point exists and is accessible
    if not os.path.isdir(mount_point):
        raise OSError(f"Chroot mount point does not exist: {mount_point}")

    # Validate that essential chroot components exist
    essential_paths = ["/bin", "/usr", "/etc"]
    for path in essential_paths:
        full_path = os.path.join(mount_point, path.lstrip("/"))
        if not os.path.exists(full_path):
            logger.warning(f"Chroot environment may be incomplete, missing: {full_path}")

    # Escape the mount point to prevent injection
    safe_mount_point = shlex.quote(mount_point)
    # Construct chroot command - using arch-chroot for Arch-specific functionality
    chroot_cmd = f"arch-chroot {safe_mount_point} {cmd}"

    return exec(chroot_cmd, get_output=get_output, **kwargs)


def exec_with_retry(cmd: str, max_retries: int = 3, retry_delay: float = 1.0, **kwargs) -> str:
    """Execute a command with automatic retry on failure.

    Args:
        cmd: Command to execute
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        **kwargs: Additional arguments passed to exec()

    Returns:
        Command output

    Raises:
        CommandExecutionError: If all retry attempts fail
    """
    import time

    for attempt in range(max_retries + 1):
        try:
            return exec(cmd, **kwargs)
        except CommandExecutionError as e:
            if attempt < max_retries:
                logger.warning(f"Command failed (attempt {attempt + 1}/{max_retries + 1}): {cmd}")
                logger.warning(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Command failed after {max_retries + 1} attempts: {cmd}")
                raise

    # This should never be reached
    raise RuntimeError(f"Unexpected exit from retry loop for command: {cmd}")
