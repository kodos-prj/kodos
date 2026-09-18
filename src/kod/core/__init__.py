"""Kodos orchestration workflows (Phase 3 complete).

This module provides high-level workflows for system operations:
- Configuration loading (Lua-based)
- User configuration processing (dotfiles, configs, services)
- Package and service state management
- Base distribution selection and setup

For backward compatibility, all core functions are provided here.
This module replaces the legacy _core module.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

# System/common utilities
from kod.common import exec, exec_chroot
from kod.context import Context  # noqa: F401
from kod.system.filesystem import (
    generate_fstab,  # noqa: F401
    load_fstab,  # noqa: F401
    change_subvol,  # noqa: F401
)
from kod.system.users import (
    proc_user_home,  # noqa: F401
)

# Phase 2b re-exports from kod.system.packages (direct import, no lazy load)
from kod.system.packages import (
    get_packages_to_install,
    load_repos,
    load_package_lock,
    store_packages_services,
    get_packages_updates,
    update_all_packages,
    get_pending_packages,
    manage_packages_shell,
)

# Phase 2b re-exports from kod.system.services (direct import, no lazy load)
from kod.system.services import (
    enable_services,
    enable_user_services,
    get_services_to_enable,
    proc_desktop_services,
    proc_services,
    proc_services_to_enable,
)

# Phase 2b re-exports from kod.system.boot (direct import, no lazy load)
from kod.system.boot import (
    create_boot_entry_hook,
    get_kernel_version,
    update_kernel_hook,
    update_initramfs_hook,
)


# =============================================================================
# BASE DISTRIBUTION SELECTION
# =============================================================================

base_distribution: str = "arch"


def set_base_distribution(base_dist: str) -> Any:
    """Set the base distribution and use Arch directly (no dynamic import).

    Args:
        base_dist: The base distribution name ("debian" or "arch").

    Returns:
        The distribution-specific module.
    """
    global base_distribution
    base_distribution = base_dist

    # For now, use Arch directly
    import kod.system.distro.arch as dist
    return dist


# =============================================================================
# HELPER PATH FUNCTIONS (used by load_config to provide to Lua)
# =============================================================================

def is_dir(path: str) -> bool:
    """Check if path is a directory."""
    return Path(path).is_dir()


def is_file(path: str) -> bool:
    """Check if path is a file."""
    return Path(path).is_file()


def home_dir() -> str:
    """Get the home directory."""
    return Path().home()


def exists(path: str) -> bool:
    """Check if path exists."""
    return Path(path).exists()


def absolute(path: str) -> str:
    """Get absolute path."""
    return str(Path(path).absolute())


def expanduser(path: str) -> str:
    """Expand user home directory in path."""
    return str(Path(path).expanduser())


# =============================================================================
# CORE CONFIGURATION LOADING
# =============================================================================

def load_config(config_filename: Optional[str]) -> Any:
    """Load configuration from a Lua file and return it as a table.

    The configuration file is a Lua file that contains different sections to configure
    the different aspects of the system.

    Args:
        config_filename: Path to the configuration file.

    Returns:
        The loaded configuration as a Lua table.
    """

    from kod.lua_runtime import get_lua_runtime
    
    # Use persistent Lua runtime (singleton) to avoid runtime mixing issues
    luart = get_lua_runtime()

    if config_filename is None:
        config_filename = "/etc/kodos"

    if Path(config_filename).is_dir():
        config_filename = str(Path(config_filename).joinpath("configuration.lua"))

    print(f"Config file: {config_filename}")
    config_path = Path(config_filename).resolve().parents[0]
    luart.execute(f"package.path = '{config_path}/?.lua;' .. package.path")
    lib_path = Path(__file__).resolve().parents[1]  # Go up to kod/ directory
    luart.execute(f"package.path = '{lib_path}/lib/?.lua;' .. package.path")
    luart.execute("package.path = 'kod/lib/?.lua;' .. package.path")
    luart.execute("print(package.path)")
    print("Loading default libraries")

    path_module = luart.table_from(
        {
            "is_dir": is_dir,
            "is_file": is_file,
            "home_dir": home_dir,
            "exists": exists,
            "absolute": absolute,
            "expanduser": expanduser,
        }
    )

    # Make the path module available in Lua
    luart.globals()["path"] = path_module

    default_libs = """
list = require("utils").list
map = require("utils").map
If = require("utils").if_true
IfElse = require("utils").if_else
    """
    luart.execute(default_libs)
    with open(config_filename) as f:
        config_data = f.read()
        conf = luart.execute(config_data)
    return conf


# =============================================================================
# GENERATION AND PACKAGE/SERVICE STATE MANAGEMENT
# =============================================================================

# get_max_generation is now in kod.system.filesystem

def load_packages_services(state_path: str) -> Tuple[Optional[Dict[str, List[str]]], Optional[List[str]]]:
    """Load the list of packages and services from state.

    Args:
        state_path (str): The path to the state directory where the package and service
            information is stored.

    Returns:
        tuple: A tuple containing two elements:
            - packages (dict): A dictionary containing the packages to install.
            - services (list): A list of system services that are enabled.
    """
    with open(f"{state_path}/installed_packages", "r") as f:
        packages = json.load(f)
    with open(f"{state_path}/enabled_services", "r") as f:
        services = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    return packages, services





__all__ = [
    "Context",
    "load_config",
    "load_packages_services",
    "generate_fstab",
    "load_fstab",
    "change_subvol",
    "proc_user_home",
    "set_base_distribution",
    # Path helpers
    "is_dir",
    "is_file",
    "home_dir",
    "exists",
    "absolute",
    "expanduser",
    # Phase 2b re-exports from kod.system.packages
    "get_packages_to_install",
    "load_repos",
    "load_package_lock",
    "store_packages_services",
    "get_packages_updates",
    "update_all_packages",
    "get_pending_packages",
    "manage_packages_shell",
    # Phase 2b re-exports from kod.system.services
    "enable_services",
    "enable_user_services",
    "get_services_to_enable",
    "proc_desktop_services",
    "proc_services",
    "proc_services_to_enable",
    # Phase 2b re-exports from kod.system.boot
    "create_boot_entry_hook",
    "get_kernel_version",
    "update_kernel_hook",
    "update_initramfs_hook",
]
