"""Core functionality and configuration management for KodOS.

This module contains the main functionality for KodOS including Lua configuration
processing. It serves as the central orchestrator for the installation and
configuration process.
"""

import json
from pathlib import Path
from typing import Optional, Any, Dict

import lupa as lua

from kod.common import exec

# Import specialized modules - these will be imported where needed
# from .package_manager import *
# from .filesystem import *
# from .user_manager import *
# from .boot_manager import *
# from .system_config import *

#####################################################################################################

base_distribution: str = "arch"


def set_base_distribution(base_dist: str) -> Any:
    """Set the base distribution and return the corresponding module.

    Args:
        base_dist: The base distribution name ("debian" or "arch").

    Returns:
        The distribution-specific module.
    """
    global base_distribution
    base_distribution = base_dist
    if base_dist == "debian":
        import kod.debian as dist

        return dist
    import kod.arch as dist

    return dist


def load_config(config_filename: Optional[str]) -> Any:
    """Load configuration from a file and return it as a table.

    The configuration file is a Lua file that contains different sections to configure
    the different aspects of the system.

    Args:
        config_filename: Path to the configuration file.

    Returns:
        The loaded configuration as a Lua table.
    """
    luart = lua.LuaRuntime()

    if config_filename is None:
        config_filename = "/etc/kodos"

    if Path(config_filename).is_dir():
        config_filename = str(Path(config_filename) / "configuration.lua")

    print(f"Loading configuration from: {config_filename}")

    if not Path(config_filename).exists():
        print(f"Configuration file {config_filename} does not exist")
        return None

    # Add lib directory to Lua package path so require() can find the libraries
    lib_dir = Path(__file__).parent / "lib"
    config_dir = Path(config_filename).parent
    luart.execute(f'package.path = package.path .. ";{lib_dir}/?.lua;{config_dir}/?.lua"')

    # Load utils globally so list() and map() functions are available everywhere
    luart.execute("""
        local utils = require("utils")
        for k, v in pairs(utils) do
            _G[k] = v
        end
    """)

    with open(config_filename, "r") as config_file:
        luacode = config_file.read()

    # Use execute to run the code and capture the return value
    luart.execute(f"config_result = (function() {luacode} end)()")
    conf = luart.eval("config_result")

    if conf is not None:
        return conf

    print(f"Invalid Lua syntax: {config_filename}")
    return None


def load_repos() -> Optional[Dict[str, Any]]:
    """
    Load the repository configuration from the file /var/kod/repos.json.

    Returns a dictionary with the repository configuration, or None if the file
    does not exist or is not a valid JSON file.
    """
    repos = None
    with open("/var/kod/repos.json") as f:
        repos = json.load(f)
    return repos
