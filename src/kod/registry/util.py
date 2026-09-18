"""Shared registry utilities.

Helper functions used across registry module and CLI.
"""

from typing import Any

# Re-export exceptions for convenience
from kod.registry.programs import (
    ProgramError,
    ProgramNotFound,
    ProgramLoadError,
    CircularExtendError,
    ConfigValidationError,
    SchemaError,
)


def lua_to_dict(obj: Any) -> Any:
    """Convert lupa Lua objects to Python dicts/lists.
    
    Args:
        obj: Object potentially from Lua
        
    Returns:
        Python dict/list/value with all Lua tables converted to dicts
    """
    # Handle lupa LuaTable
    if hasattr(obj, "items") and not isinstance(obj, dict):
        try:
            return {k: lua_to_dict(v) for k, v in obj.items()}
        except (AttributeError, TypeError):
            return obj
    
    # Handle regular dict
    if isinstance(obj, dict):
        return {k: lua_to_dict(v) for k, v in obj.items()}
    
    # Handle lists/tuples
    if isinstance(obj, (list, tuple)):
        return [lua_to_dict(v) for v in obj]
    
    # Return as-is for scalars
    return obj


__all__ = [
    "lua_to_dict",
    "ProgramError",
    "ProgramNotFound",
    "ProgramLoadError",
    "CircularExtendError",
    "ConfigValidationError",
    "SchemaError",
]
