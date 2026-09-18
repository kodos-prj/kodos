"""Lua-to-Python conversion utilities.

Single source of truth for converting lupa LuaTable objects to Python dict/list.

Key function:
  • lua_table_to_python(): Converts Lua table → Python dict/list
    - Detects array-ness from int keys (1-indexed in Lua → 0-indexed in Python)
    - Recursively handles nested tables
    - Preserves scalar values (str, int, bool, None)

Used by:
  • bootstrap.py: Convert config for re-Lua-fying
  • schema.py: Convert schema section definitions  
  • loader.py: Convert loaded config to Python dict

This consolidation (Phase 5c) removed 3 duplicate implementations:
  - bootstrap.py: _lua_table_to_dict (22 lines)
  - schema.py: _lua_table_to_dict (24 lines)
  - loader.py: _lua_to_python (36 lines)

See ARCHITECTURE.md for system design.
"""

from typing import Any


def lua_table_to_python(value: Any) -> Any:
    """Recursively convert lupa LuaTable to Python dict/list.
    
    Lua has one table type; this detects whether it's array-like (int keys 1..n)
    or dict-like (string/mixed keys) based on the key structure.
    
    Args:
        value: Any value, including LuaTable from lupa
        
    Returns:
        Python equivalent: dict, list, or scalar (str/int/bool/None)
    """
    # Handle Lua tables (from lupa) via duck typing
    if hasattr(value, 'items') and not isinstance(value, dict):
        items = dict(value.items())
        
        if not items:
            # Empty table → empty dict
            return {}
        
        # Check if it's an array (all int keys, 1-indexed, contiguous)
        keys = list(items.keys())
        if all(isinstance(k, int) for k in keys):
            sorted_keys = sorted(keys)
            if sorted_keys == list(range(1, len(sorted_keys) + 1)):
                # It's a proper Lua array (1-indexed, contiguous)
                return [lua_table_to_python(items[i]) for i in sorted_keys]
        
        # It's a dict: recursively convert values
        return {key: lua_table_to_python(val) for key, val in items.items()}
    
    # Handle Python collections
    elif isinstance(value, (list, tuple)):
        return [lua_table_to_python(v) for v in value]
    
    # Scalar values: str, int, float, bool, None
    else:
        return value
