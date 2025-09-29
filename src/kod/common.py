"""Common utility functions and debugging utilities for KodOS.

This module provides core utility functions for command execution, debugging,
and system interaction used throughout the KodOS system.
"""

import os

use_debug: bool = True
use_verbose: bool = False


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


def exec(cmd: str, get_output: bool = False) -> str:
    """Execute a shell command with optional debug output.

    This is a critical function that handles command execution throughout KodOS.
    In debug mode, it prints the command being executed. In non-debug mode,
    it actually executes the command.

    Args:
        cmd: The shell command to execute.
        get_output: Whether to return command output. Defaults to False.

    Returns:
        Command output if get_output=True, empty string otherwise.
    """
    if use_debug or use_verbose:
        print(">>", color.PURPLE + cmd + color.END)
    if not use_debug:
        if get_output:
            return os.popen(cmd).read()
        else:
            os.system(cmd)
    return ""


def exec_chroot(cmd: str, mount_point: str = "/mnt", get_output: bool = False) -> str:
    """Execute a command within a chroot environment.

    Args:
        cmd: The command to execute inside the chroot.
        mount_point: The mount point for the chroot. Defaults to "/mnt".
        get_output: Whether to return command output. Defaults to False.

    Returns:
        Command output from the chroot execution.
    """
    chroot_cmd = f"arch-chroot {mount_point} "
    chroot_cmd += cmd
    return exec(chroot_cmd, get_output=True)
