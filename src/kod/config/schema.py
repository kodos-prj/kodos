"""Configuration schema access.

The Lua module kod.core.schema (in src/lua/kod/core/schema.lua) is the single 
source of truth for all configuration sections. This module loads it into 
plain Python dicts for validation and documentation.
"""

import os
from typing import Dict
from kod.lua_utils import lua_table_to_python

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
        result = lua.require('kod.core.schema')
        schema_module = result[0] if isinstance(result, tuple) else result
    except Exception as e:
        raise RuntimeError(f"Failed to load Lua schema (kod.core.schema): {e}") from e

    # Convert Lua schema to Python dict
    schema = {}
    for section_name in [
        'base_distribution', 'repos', 'devices', 'boot', 'hardware',
        'locale', 'network', 'users', 'desktop', 'fonts',
        'packages', 'services', 'programs'
    ]:
        section_def = schema_module[section_name]
        schema[section_name] = lua_table_to_python(section_def)

    _lua_schema_cache = schema
    return schema
