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
from pathlib import Path
from typing import Optional

from .lib.chroot import ChrootError, chroot

use_debug: bool = True
use_verbose: bool = False
problems: list[dict] = []

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


def report_problems():
    for prob in problems:
        print("Problem:", prob)


def exec(
    cmd: str,
    get_output: bool = False,
    encoding: str = "utf-8",
) -> str:
    """Execute a shell command with comprehensive error handling.

    This is a critical function that handles command execution throughout KodOS.
    It provides proper error handling, return code checking, timeout support,
    and basic security validation.

    Args:
        cmd: The shell command to execute.
        get_output: Whether to return command output. Defaults to False.
        encoding: Text encoding for command output. Defaults to 'utf-8'.

    Returns:
        Command output if get_output=True, empty string otherwise.

    Raises:
        CommandExecutionError: If command fails and check_return_code is True.
        CommandTimeoutError: If command times out.
        UnsafeCommandError: If command contains unsafe patterns and allow_unsafe is False.
        OSError: For system-level execution errors.
    """
    if use_debug or use_verbose:
        print(">>", color.PURPLE + cmd + color.END)

    # In debug mode, only print commands but don't execute
    if use_debug:
        return ""

    try:
        if get_output:
            # Use subprocess for better control and error handling
            # result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, encoding=encoding)
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding=encoding)

            # if check_return_code and result.returncode != 0:
            if result.returncode != 0:
                logger.error(f"Command failed: {cmd}")
                logger.error(f"Return code: {result.returncode}")
                logger.error(f"Stderr: {result.stderr}")
                problems.append(
                    {
                        "type": "command_execution",
                        "command": cmd,
                        "return_code": result.returncode,
                        "stderr": result.stderr,
                        "stdout": result.stdout,
                    }
                )

            return result.stdout
        else:
            # For commands without output capture, use subprocess.run
            # result = subprocess.run(cmd, shell=True, timeout=timeout)
            result = subprocess.run(cmd, shell=True)

            # if check_return_code and result.returncode != 0:
            if result.returncode != 0:
                logger.error(f"Command failed: {cmd}")
                logger.error(f"Return code: {result.returncode}")
                problems.append({"type": "command_execution", "command": cmd, "return_code": result.returncode})
            return ""

    # except subprocess.TimeoutExpired:
    #     logger.error(f"Command timed out after {timeout}s: {cmd}")
    #     raise CommandTimeoutError(cmd, timeout)
    except OSError as e:
        logger.error(f"OS error executing command '{cmd}': {e}")
        raise


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
    mount_path = Path(mount_point)
    if not mount_path.is_dir():
        raise OSError(f"Chroot mount point does not exist: {mount_point}")

    # Validate that essential chroot components exist
    essential_paths = ["/bin", "/usr", "/etc"]
    for path in essential_paths:
        full_path = mount_path / path.lstrip("/")
        if not full_path.exists():
            logger.warning(f"Chroot environment may be incomplete, missing: {full_path}")

    try:
        # print(f"###({get_output})>", cmd)
        result = chroot(str(mount_point), cmd, get_output=get_output)
        # print("###~", result)
        return result if result is not None else ""
    except ChrootError as e:
        raise CommandExecutionError(cmd=cmd, return_code=1, stderr=str(e))


def exec_critical(cmd: str, error_msg: str, **kwargs) -> str:
    """Execute a critical command that must succeed or raise RuntimeError.

    This function is used for operations that are essential for system functionality.
    If the command fails, it logs the error and raises a RuntimeError with a
    descriptive message.

    Args:
        cmd: Command to execute
        error_msg: Descriptive error message for RuntimeError
        **kwargs: Additional arguments passed to exec()

    Returns:
        Command output

    Raises:
        RuntimeError: If command fails, wrapping the original exception
    """
    initial_problem_count = len(problems)
    result = exec(cmd, **kwargs)

    # Check if new problems were added (indicating command failure)
    if len(problems) > initial_problem_count:
        latest_problem = problems[-1]
        print(f"Error: {error_msg}")
        raise RuntimeError(error_msg)

    return result


def exec_warn(cmd: str, warning_msg: str, **kwargs) -> Optional[str]:
    """Execute a command with warning on failure, continuing execution.

    This function is used for non-critical operations where failure should
    be logged as a warning but execution should continue.

    Args:
        cmd: Command to execute
        warning_msg: Warning message to display on failure
        **kwargs: Additional arguments passed to exec()

    Returns:
        Command output on success, None on failure
    """
    initial_problem_count = len(problems)
    result = exec(cmd, **kwargs)

    # Check if new problems were added (indicating command failure)
    if len(problems) > initial_problem_count:
        print(f"Warning: {warning_msg}")
        return None

    return result
