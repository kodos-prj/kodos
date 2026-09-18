"""Kodos core configuration loading and Lua integration.

This module provides core system initialization:
- Configuration loading from Lua files
- Lua runtime setup with path helpers

Configuration data structure definitions and validation are in kod.config.
Distribution-specific operations are in kod.system.distro.
Package/service management is in kod.system.packages and kod.system.services.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any

# For backward compatibility, re-export Context
from kod.context import Context  # noqa: F401


# =============================================================================
# CORE CONFIGURATION LOADING
# =============================================================================

def load_config(config_filename: Optional[str]) -> Any:
    """Load configuration from a Lua file and return it as a table.

    The configuration file is a Lua file that contains different sections to configure
    the different aspects of the system. This function sets up the Lua runtime,
    configures package paths, and exposes Python path utilities to Lua.

    Args:
        config_filename: Path to the configuration file.
                        If None, defaults to /etc/kodos.
                        If a directory, loads configuration.lua from it.

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

    # Expose Python path utilities to Lua for configuration processing
    path_module = luart.table_from(
        {
            "is_dir": lambda path: Path(path).is_dir(),
            "is_file": lambda path: Path(path).is_file(),
            "home_dir": lambda: str(Path().home()),
            "exists": lambda path: Path(path).exists(),
            "absolute": lambda path: str(Path(path).absolute()),
            "expanduser": lambda path: str(Path(path).expanduser()),
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


__all__ = [
    "Context",
    "load_config",
]

