"""Configuration loading and parsing (Phase 1).

Loads Lua configuration files and resolves module imports.

Key components:
- load_config(): Main entry point to load a config file
- _lua_to_python(): Convert lupa LuaTable to Python dict
- _resolve_imports(): Handle the new imports = {...} syntax

Example:
    >>> from kod.config.loader import load_config
    >>> config = load_config("example/testvm")
    >>> # config is now a Python dict with all imports resolved
"""

from typing import Any, Dict, Optional

from kod.core import load_config as lua_load_config


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
    # Use existing load_config to handle Lua + requires
    lua_config = lua_load_config(config_path)
    
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



