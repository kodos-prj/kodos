"""Bootstrap step emission from unified Lua module.

Bridges Lua bootstrap.lua (architecture-agnostic, supports arch/debian) to Python Step objects.
Works like other sections (devices.lua, packages.lua, ...) but is called separately for bootstrap phase.

Key responsibility: Call Lua bootstrap module, convert output Steps to Python.
Does NOT execute; execution is handled by execute_steps() in kod.py.

Note: Ensures plan preview and execution produce identical step lists.

See ARCHITECTURE.md for system design.
"""

from typing import Any, List
import os
from kod.planner import Step
from kod.lua_utils import lua_table_to_python


def _convert_to_lua_table(lua, value):
     """Recursively convert Python dict/list/object to Lua table."""
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
     elif hasattr(value, '__dict__') and not isinstance(value, type):
         # Convert objects with __dict__ (but not classes themselves)
         t = lua.table()
         for k, v in value.__dict__.items():
             t[k] = _convert_to_lua_table(lua, v)
         return t
     else:
         return value


def emit_bootstrap_steps(conf: Any, predicted_partition_list: List[dict], distro: str = "arch") -> List[Step]:
    """Emit bootstrap steps via Lua module (using persistent runtime).
    
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
    from kod.lua_runtime import get_lua_runtime
    
    # Get persistent Lua runtime (singleton) - avoids "cannot mix objects from different Lua runtimes"
    lua = get_lua_runtime()
    
    # CRITICAL: Convert conf to pure Python FIRST to remove any Lua objects from previous runtimes
    if hasattr(conf, "keys"):  # It's a Lua table (from any runtime)
        conf = lua_table_to_python(conf)
    
    # Now convert to Lua table in OUR persistent runtime
    if hasattr(conf, "__dict__"):
        conf_lua = _convert_to_lua_table(lua, vars(conf))
    elif isinstance(conf, dict):
        conf_lua = _convert_to_lua_table(lua, conf)
    else:
        conf_lua = conf
    
    # Load unified bootstrap module (supports both arch and debian)
    module_name = "bootstrap"
    module_path = os.path.join(os.path.dirname(__file__), "lib", "bootstrap", "bootstrap.lua")
    
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
    
    # Call Lua function with distro parameter
    try:
        steps_lua = bootstrap_module.emit_bootstrap_steps(conf_lua, partition_list_lua, distro)
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
