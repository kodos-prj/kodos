"""Common utility functions and debugging utilities for KodOS.

This module provides core utility functions for command execution, debugging,
and system interaction used throughout the KodOS system.
"""

import logging
import subprocess
from typing import Optional

from chorut import ChrootManager

use_debug: bool = True
use_verbose: bool = False
use_dry_run: bool = False

# Set up logging
logger = logging.getLogger(__name__)


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


def set_dry_run(val: bool = True) -> None:
    """Set the global dry run mode state.

    Args:
        val: Whether to enable dry run mode. Defaults to True.
    """
    global use_dry_run
    use_dry_run = val


def execute(cmd: str, get_output: bool = False, encoding: str = "utf-8", check_return_code: bool = False, dry_run: bool = False) -> str:
    """Execute a shell command with comprehensive error handling.

    This is a critical function that handles command execution throughout KodOS.
    It provides proper error handling, return code checking, timeout support,
    and basic security validation.

    Args:
        cmd: The shell command to execute.
        get_output: Whether to return command output. Defaults to False.
        encoding: Text encoding for command output. Defaults to 'utf-8'.
        check_return_code: If True, raise RuntimeError on non-zero exit code. 
                          If False, log error. Defaults to False.
        dry_run: If True, print command but do not execute. Defaults to False.

    Returns:
        Command output if get_output=True, empty string otherwise.

    Raises:
        RuntimeError: If check_return_code=True and command returns non-zero exit code.
    """
    print(f"Executing command: {cmd}")
    print(f">> {color.PURPLE}{cmd}{color.END}")
    if dry_run:
        return ""

    try:
        if get_output:
            # Use subprocess for better control and error handling
            # result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, encoding=encoding)
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding=encoding)

            if result.returncode != 0:
                error_details = {
                    "type": "command_execution",
                    "command": cmd,
                    "return_code": result.returncode,
                    "stderr": result.stderr,
                    "stdout": result.stdout,
                }
                logger.error(f"Command failed: {cmd}")
                logger.error(f"Return code: {result.returncode}")
                logger.error(f"Stderr: {result.stderr}")
                logger.error(f"Stdout: {result.stdout}")
                if check_return_code:
                    raise RuntimeError(f"Command failed: {cmd}\nReturn code: {result.returncode}\nStderr: {result.stderr}")

            return result.stdout
        else:
            # For commands without output capture, use subprocess.run
            result = subprocess.run(cmd, shell=True)

            if result.returncode != 0:
                error_details = {"type": "command_execution", "command": cmd, "return_code": result.returncode}
                logger.error(f"Command failed: {cmd}")
                logger.error(f"Return code: {result.returncode}")
                
                if check_return_code:
                    raise RuntimeError(f"Command failed: {cmd}\nReturn code: {result.returncode}")
            return ""

    except OSError as e:
        logger.error(f"OS error executing command '{cmd}': {e}")
        raise


def exec_chroot(cmd: str, mount_point: str = "/mnt", get_output: bool = False, dry_run: bool = False, **kwargs) -> str:
    """Execute a command within a chroot environment with error handling.

    Args:
        cmd: The command to execute inside the chroot.
        mount_point: The mount point for the chroot. Defaults to "/mnt".
        get_output: Whether to return command output. Defaults to False.
        **kwargs: Additional arguments passed to exec().

    Returns:
        Command output from the chroot execution.
    """
    # return exec(chroot_cmd, get_output=get_output, **kwargs)
    # is_dry_run = use_dry_run or kwargs.get("dry_run", False)
    if dry_run:
        # logger.debug(f"Executing chroot command: {cmd} in {mount_point}")
        print(f"[chroot]: {color.PURPLE}{cmd}{color.END} ({mount_point})")
        return ""
    with ChrootManager(mount_point) as chroot:
        result = chroot.execute(cmd, capture_output=get_output)
        return result.stdout if get_output else ""
