"""Configuration schema access.

The Lua module kod/lib/schema.lua is the single source of truth for all
configuration sections. This module loads it into plain Python dicts.
"""

import os
from typing import Dict

# Lazy-loaded Lua schema (cached)
_lua_schema_cache = None


def get_lua_schema() -> Dict:
    """Load the Lua schema (single source of truth) and cache it.

    Returns:
        Dict mapping section name to its schema definition.

    Raises:
        RuntimeError: if the Lua runtime or schema module cannot be loaded;
            validation cannot proceed without the schema.
    """
    global _lua_schema_cache

    if _lua_schema_cache is not None:
        return _lua_schema_cache

    try:
        from kod.lua_runtime import get_lua_runtime

        lua = get_lua_runtime()
        # src/ dir (this file lives in src/kod/config/)
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        lua.execute(f"package.path = '{base_path}/?.lua;{base_path}/?/init.lua;' .. package.path")
        result = lua.require('kod.lib.schema')
        schema_module = result[0] if isinstance(result, tuple) else result
    except Exception as e:
        raise RuntimeError(f"Failed to load Lua schema (kod.lib.schema): {e}") from e

    # Convert Lua schema to Python dict
    schema = {}
    for section_name in [
        'base_distribution', 'repos', 'devices', 'boot', 'hardware',
        'locale', 'network', 'users', 'desktop', 'fonts',
        'packages', 'services', 'programs'
    ]:
        section_def = schema_module[section_name]
        schema[section_name] = _lua_table_to_dict(section_def)

    _lua_schema_cache = schema
    return schema


def _lua_table_to_dict(lua_table) -> Dict:
    """Convert a Lua table to plain Python dict/list recursively.

    Array tables (int keys 1..n) become lists, hash tables become dicts.
    Non-table values (str, int, bool, ...) pass through unchanged.

    Args:
        lua_table: Lua table from lupa (or an already-converted value)

    Returns:
        Python dict/list representation
    """
    if lua_table is None or isinstance(lua_table, (str, int, float, bool)):
        return lua_table

    try:
        items = list(lua_table.items())
    except (AttributeError, TypeError):
        # Not a mapping (e.g. Python list), return as-is
        return lua_table

    keys = [key for key, _ in items]
    if keys and all(isinstance(key, int) and not isinstance(key, bool) for key in keys):
        return [_lua_table_to_dict(value) for _, value in sorted(items)]
    return {key: _lua_table_to_dict(value) for key, value in items}
