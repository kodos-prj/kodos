"""Configuration loading and parsing.

Loads Lua configuration files, sets up Lua runtime, and converts results to Python.

Key components:
- load_config_lua(): Load raw Lua config with runtime setup
- load_config(): Load config and convert to Python dict
- _lua_to_python(): Convert lupa LuaTable to Python dict/list

Example:
    >>> from kod.config.loader import load_config
    >>> config = load_config("example/testvm")
    >>> # config is now a Python dict with all imports resolved
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from kod.lua_runtime import get_lua_runtime


def load_config_lua(config_filename: Optional[str]) -> Any:
    """Load configuration from a Lua file and return it as a Lua table.

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
    
    # Use persistent Lua runtime (singleton) to avoid runtime mixing issues
    luart = get_lua_runtime()

    if config_filename is None:
        config_filename = "/etc/kodos"

    if Path(config_filename).is_dir():
        config_filename = str(Path(config_filename).joinpath("configuration.lua"))

    print(f"Config file: {config_filename}")
    config_path = Path(config_filename).resolve().parents[0]
    luart.execute(f"package.path = '{config_path}/?.lua;' .. package.path")
    lib_path = Path(__file__).resolve().parents[2]  # Go up to src/kod/ directory
    luart.execute(f"package.path = '{lib_path}/kod/lib/?.lua;' .. package.path")
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


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load config from Lua file and convert to Python dict.
    
    Handles:
    - Lua files (configuration.lua)
    - Directories (loads configuration.lua from directory)
    - Lua require() statements
    - New imports = {...} syntax (converted to require() calls)
    
    Args:
        config_path: Path to config file or directory. Defaults to /etc/kodos.
    
    Returns:
        Configuration as a Python dict.
    
    Raises:
        FileNotFoundError: If config file not found.
        SyntaxError: If Lua syntax is invalid.
    """
    # Load Lua config with runtime setup
    lua_config = load_config_lua(config_path)
    
    # Convert lupa LuaTable to Python dict
    return _lua_to_python(lua_config)


def _lua_to_python(value: Any) -> Any:
    """Recursively convert lupa LuaTable to Python dict/list.
    
    Lua has one table type; detect array-ness from int keys 1..n.
    ponytail: handles the common case of Lua tables (no custom objects).
    """
    # Check if it's a Lua table by duck typing (has .items() method)
    if hasattr(value, 'items') and not isinstance(value, dict):
        # Could be array (int keys 1..n) or dict (string keys)
        items = dict(value.items())
        
        if not items:
            # Empty table → empty dict
            return {}
        
        # Check if it's an array (all int keys from 1..n)
        keys = list(items.keys())
        if all(isinstance(k, int) for k in keys):
            # Likely a Lua array (1-indexed)
            sorted_keys = sorted(keys)
            if sorted_keys == list(range(1, len(sorted_keys) + 1)):
                # It's a proper array: convert to Python list
                result = [_lua_to_python(items[i]) for i in sorted_keys]
                return result
        
        # It's a dict: recursively convert values
        result = {}
        for key, val in items.items():
            result[key] = _lua_to_python(val)
        return result
    
    elif isinstance(value, (list, tuple)):
        return [_lua_to_python(v) for v in value]
    else:
        # Scalar: string, number, bool, nil → keep as-is
        return value


