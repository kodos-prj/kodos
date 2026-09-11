# Task 4: Update Bootstrap Integration for Schema-Aware Lua

## Requirement

Update the Python bootstrap (`src/kod/bootstrap.py`) to use the new Lua-based planner for step generation. The bootstrap should:

1. Load the configuration file
2. Validate it using Python validator
3. Call the Lua planner to compose steps
4. Execute steps in order

## Current Flow (Bootstrap)

```python
# OLD: bootstrap.py
config = load_config()
validate(config)
steps = generate_steps(config)  # Python planner with nested conditionals
execute_steps(steps)
```

## Target Flow (After Phase 5c)

```python
# NEW: bootstrap.py
config = load_config()
validate_schema(config)  # Python validator (uses Lua schema - Task 5)
steps = lua_planner.compose(config, distro)  # Lua planner (Task 3)
execute_steps(steps)
```

## File to Update

**`src/kod/bootstrap.py`** (REFACTOR)

Find the location where steps are generated and replace Python-based planner with Lua planner calls.

## Implementation Details

### 1. Lua Interpreter Setup
- Import lupa (or similar Lua interpreter library)
- Create Lua interpreter instance (reuse singleton if possible)
- Load Lua stdlib (os, table, string, etc.)
- Set Lua search path to include `src/kod/lib` and `src/kod/sections`

### 2. Load Lua Planner
```python
import lupa

lua = lupa.LuaRuntime()
planner = lua.require('kod.lib.planner')
```

### 3. Call Planner
```python
config = load_config()
distro = config.get('base_distribution', 'arch')

# Call Lua planner
steps, err = planner.compose(config, distro)

if err:
    raise ValueError(f"Planner error: {err}")

# steps is now a Lua table; convert to Python list
steps_list = list(steps.values()) if hasattr(steps, 'values') else steps
```

### 4. Handle Lua Data Types
- Lua tables ↔ Python dicts/lists conversion
- Lua functions are callable from Python
- Step objects (Lua tables) will have: name, description, command, order, on_distro, depends_on

### 5. Step Execution
- Iterate through steps (already sorted by planner)
- Execute each step's command
- Handle distro-specific execution (check on_distro field)
- Log progress and errors

### 6. Error Handling
- If Lua planner fails → catch and report
- If Lua module not found → fall back to Python planner (graceful degradation)
- Validate step format before execution

## Python Integration

### Dependency: lupa

Add to `requirements.txt` or `setup.py`:

```python
# If not already present
lupa>=1.14  # Lua interpreter for Python
```

### Configuration Paths

Ensure Lua can find modules:

```python
import sys
import os

# Set Lua package path
lua_path = os.path.join(os.path.dirname(__file__), '..', '..')
if hasattr(lua, 'eval'):
    lua.eval(f"""
        package.path = '{lua_path}/src/?.lua;{lua_path}/src/?/init.lua;' .. package.path
    """)
```

### Conversion Helpers

Create conversion functions for Lua ↔ Python:

```python
def lua_table_to_dict(lua_table):
    """Convert Lua table to Python dict/list"""
    result = {}
    for key, value in lua_table.items():
        if isinstance(value, dict):
            result[key] = lua_table_to_dict(value)
        else:
            result[key] = value
    return result

def lua_steps_to_python(lua_steps):
    """Convert Lua step array to Python list"""
    steps = []
    for i in range(1, len(lua_steps) + 1):  # Lua is 1-indexed
        step = lua_steps[i]
        steps.append(lua_table_to_dict(step))
    return steps
```

## Backward Compatibility

- Keep Python planner as fallback (if Lua fails, use Python)
- Don't remove Python planner code yet (Phase 5a may use it)
- Add feature flag/config option to enable/disable Lua planner:

```python
USE_LUA_PLANNER = os.getenv('KOD_USE_LUA_PLANNER', 'true').lower() == 'true'

if USE_LUA_PLANNER:
    try:
        steps = lua_planner.compose(config, distro)
    except Exception as e:
        print(f"Lua planner failed: {e}, falling back to Python")
        steps = python_planner.compose(config, distro)
else:
    steps = python_planner.compose(config, distro)
```

## Testing

Update `tests/test_bootstrap.py`:

```python
# Test Lua planner integration
# Test compose() is called correctly
# Test steps are returned in correct format
# Test distro parameter is passed
# Test error handling (missing Lua module, invalid config)
# Test fallback to Python planner
# Test step execution with Lua-generated steps
# Test end-to-end bootstrap with Lua planner
```

Also add Lua-specific bootstrap tests:

```python
# Test Lua interpreter initialization
# Test Lua module loading
# Test Lua ↔ Python data conversion
# Test that all 13 sections work through bootstrap
```

## Success Criteria

✅ Bootstrap loads Lua planner successfully  
✅ Config is passed to Lua planner  
✅ Lua planner returns steps (all 13 sections working)  
✅ Steps are executable (correct format)  
✅ Distro parameter is respected  
✅ Error handling works (graceful fallback)  
✅ Backward compatible (Python planner still works)  
✅ All 541+ existing tests pass  
✅ 15+ new bootstrap integration tests pass  
✅ No performance regression  

## File Changes

- **`src/kod/bootstrap.py`** — call Lua planner instead of Python
- **`requirements.txt` or `setup.py`** — add lupa dependency (if not present)
- **`tests/test_bootstrap.py`** — add integration tests
- **`tests/test_bootstrap_lua.py`** — add Lua-specific tests (NEW)

## File Size Expectation

- Bootstrap changes: ~50-100 lines modified/added
- Conversion helpers: ~30-50 lines
- Tests: ~200+ lines
- Total new code: ~300 lines

## Integration Chain

1. Config loaded from file
2. **Python validator** checks schema (Task 5 upcoming)
3. **Lua planner** composes steps (Task 3, completed)
4. **Bootstrap** executes steps
5. System boots with generated configuration

## Notes

- Lua interpreter setup can be done once (singleton pattern)
- Consider caching Lua planner module (avoid repeated requires)
- Error messages should be clear (Lua or Python?)
- Test both arch and debian distro paths
- Ensure step execution respects on_distro field
- Keep Python planner as reference/fallback during transition

## Related

- Lua Planner: `src/kod/lib/planner.lua` (Task 3, completed)
- Python Validator: (Task 5, upcoming)
- Full System Test: (Task 6, upcoming)

## Example Walkthrough

```python
# bootstrap.py
import lupa

def run_bootstrap(config_path):
    # Load configuration
    config = load_config(config_path)
    
    # Validate
    validate_config(config)  # Uses Python validator (reads Lua schema)
    
    # Get distro
    distro = config.get('base_distribution', 'arch')
    
    # Compose steps using Lua planner
    lua = lupa.LuaRuntime()
    lua.eval("package.path = './src/?.lua;./src/?/init.lua;' .. package.path")
    planner = lua.require('kod.lib.planner')
    
    steps, err = planner.compose(config, distro)
    if err:
        print(f"Error: {err}")
        return False
    
    # Execute steps
    for step in steps:
        print(f"Running: {step['name']}")
        execute_step(step, distro)
    
    return True
```
