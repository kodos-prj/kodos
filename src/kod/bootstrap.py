"""Bootstrap step emission via Lua modules.

Bridges Lua bootstrap-arch.lua / bootstrap-debian.lua to Python Step objects.
Ensures plan preview and execution produce identical step lists.
"""

from typing import Any, List, Optional
import os
from kod.planner import Step


def _convert_to_lua_table(lua, value):
    """Recursively convert Python dict/list to Lua table."""
    if isinstance(value, dict):
        t = lua.table()
        for k, v in value.items():
            t[k] = _convert_to_lua_table(lua, v)
        return t
    elif isinstance(value, (list, tuple)):
        t = lua.table()
        for i, v in enumerate(value, 1):
            t[i] = _convert_to_lua_table(lua, v)
        return t
    else:
        return value


def _lua_table_to_dict(lua_table):
    """Convert a Lua table to a Python dict."""
    if not hasattr(lua_table, "keys"):
        return lua_table
    
    result = {}
    for key in lua_table.keys():
        val = lua_table[key]
        if hasattr(val, "keys"):  # It's a Lua table
            result[key] = _lua_table_to_dict(val)
        else:
            result[key] = val
    return result


def emit_bootstrap_steps(conf: Any, predicted_partition_list: List[dict], distro: str = "arch") -> List[Step]:
    """Emit bootstrap steps via Lua module.
    
    Args:
        conf: Configuration object (dict, Lua table, or object with __dict__)
        predicted_partition_list: Pre-computed partition list from predict_partition_list()
        distro: Distribution name ("arch" or "debian")
    
    Returns:
        List of Step objects representing full bootstrap sequence
    
    Raises:
        FileNotFoundError: If Lua module not found
        RuntimeError: If Lua module fails to load or execute
    """
    from lupa import LuaRuntime
    
    # Always create a fresh Lua runtime to avoid runtime mixing issues
    lua = LuaRuntime()
    
    # Convert conf to dict first if it's a Lua table
    if hasattr(conf, "keys"):  # It's a Lua table
        conf = _lua_table_to_dict(conf)
    
    # Convert conf to Lua table in our runtime
    if hasattr(conf, "__dict__"):
        conf_lua = _convert_to_lua_table(lua, vars(conf))
    elif isinstance(conf, dict):
        conf_lua = _convert_to_lua_table(lua, conf)
    else:
        conf_lua = conf
    
    # Load bootstrap module
    module_name = f"bootstrap-{distro}"
    module_path = os.path.join(os.path.dirname(__file__), "lib", f"{module_name}.lua")
    
    if not os.path.exists(module_path):
        raise FileNotFoundError(f"Bootstrap module not found: {module_path}")
    
    with open(module_path) as f:
        bootstrap_code = f.read()
    
    try:
        bootstrap_module = lua.execute(bootstrap_code)
    except Exception as e:
        raise RuntimeError(f"Failed to load Lua bootstrap module {module_name}: {e}")
    
    # Convert partition_list to Lua table
    try:
        partition_list_lua = _convert_to_lua_table(lua, predicted_partition_list)
    except Exception as e:
        raise RuntimeError(f"Failed to convert partition list to Lua table: {e}")
    
    # Call Lua function
    try:
        steps_lua = bootstrap_module.emit_bootstrap_steps(conf_lua, partition_list_lua)
    except Exception as e:
        raise RuntimeError(f"Lua bootstrap module failed: {e}")
    
    # Convert Lua step tables back to Python Step objects
    steps = []
    try:
        # steps_lua is a Lua table with integer keys (1-indexed)
        for idx in range(1, len(steps_lua) + 1):
            step_lua = steps_lua[idx]
            
            # Extract args (Lua table -> list)
            args_lua = step_lua.args or lua.table()
            args_list = []
            for i in range(1, len(args_lua) + 1):
                args_list.append(str(args_lua[i]))
            
            # Extract meta (Lua table -> dict)
            meta_lua = step_lua.meta or lua.table()
            meta_dict = {}
            for key in meta_lua.keys():
                val = meta_lua[key]
                # Handle nested Lua tables in meta
                if hasattr(val, "keys"):  # It's a Lua table
                    nested_dict = {}
                    for nested_key in val.keys():
                        nested_dict[nested_key] = val[nested_key]
                    meta_dict[key] = nested_dict
                else:
                    meta_dict[key] = val
            
            step = Step(
                kind=str(step_lua.kind),
                name=str(step_lua.name),
                program=str(step_lua.program or ""),
                args=tuple(args_list),
                meta=meta_dict,
            )
            steps.append(step)
    except Exception as e:
        raise RuntimeError(f"Failed to convert Lua steps to Python Step objects: {e}")
    
    return steps
