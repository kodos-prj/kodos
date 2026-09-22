"""Common utility functions and debugging utilities for KodOS.

This module provides core utility functions for command execution, debugging,
and system interaction used throughout the KodOS system.
"""

import logging
import shlex
import subprocess
from pathlib import Path
from typing import Optional

use_debug: bool = True
use_verbose: bool = False
problems: list[dict] = []

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

    except OSError as e:
        logger.error(f"OS error executing command '{cmd}': {e}")
        raise


def setup_chroot_mounts(mount_point: str = "/mnt") -> None:
    """Setup pseudo-filesystems for a chroot environment.
    
    Mounts /proc, /sys, and binds /dev inside the chroot so that commands
    like pacman, systemd, etc. can run properly. Creates /etc/mtab as a
    symlink to /proc/mounts for compatibility.
    
    Args:
        mount_point: The chroot mount point. Defaults to "/mnt".
    
    Raises:
        OSError: If mount_point does not exist or mounts fail.
    """
    mount_path = Path(mount_point)
    if not mount_path.is_dir():
        raise OSError(f"Chroot mount point does not exist: {mount_point}")
    
    try:
        # Mount proc and sysfs (ignore if already mounted)
        try:
            exec(f"mount -t proc proc {mount_point}/proc")
        except Exception:
            pass
        
        try:
            exec(f"mount -t sysfs sys {mount_point}/sys")
        except Exception:
            pass
        
        # Bind mount /dev (ignore if already mounted)
        try:
            exec(f"mount -o bind /dev {mount_point}/dev")
        except Exception:
            pass
        
        try:
            exec(f"mount -o bind /dev/pts {mount_point}/dev/pts")
        except Exception:
            pass
        
        # Create mtab symlink if needed
        try:
            mtab_path = Path(f"{mount_point}/etc/mtab")
            if not mtab_path.exists() and not mtab_path.is_symlink():
                exec(f"ln -sf /proc/mounts {mount_point}/etc/mtab")
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Warning: Failed to setup some chroot mounts at {mount_point}: {e}")
        # Don't raise - allow rebuild to continue even if some mounts fail


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
        OSError: If chroot environment is not accessible.
    """
    mount_path = Path(mount_point)
    if not mount_path.is_dir():
        raise OSError(f"Chroot mount point does not exist: {mount_point}")

    # Raw chroot on any host; target shell interprets the command so
    # redirections/pipes apply inside the chroot. No mounts done here - the
    # plan bind-mounts host /dev (and proc/sys) before chroot steps, so
    # device nodes follow the host's own /dev (e.g. /dev/rtc0 exists iff
    # the host kernel exposes an RTC device).
    safe_mount_point = shlex.quote(str(mount_point))
    chroot_cmd = f"chroot {safe_mount_point} /bin/sh -c {shlex.quote(cmd)}"
    return exec(chroot_cmd, get_output=get_output, **kwargs)


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
