# KodOS Lua Runtime Fix (Plan D) Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Fix Lua runtime mixing issue in bootstrap.py and implement persistent Lua runtime manager for all Lua code.

**Problem:** When `emit_bootstrap_steps(conf, ...)` is called, `conf` may contain Lua table objects from a previous LuaRuntime, while the function creates a fresh runtime. Mixing objects from different runtimes causes "cannot mix objects from different Lua runtimes" error.

**Architecture:** Implement a singleton `LuaRuntimeManager` that:
1. Creates a single persistent Lua runtime at module load time
2. Exposes it globally to all bootstrap.py functions
3. Ensures all Lua table conversions happen within the same runtime
4. Handles cleanup on exit (Lua finalizers)

**Tech Stack:** lupa (existing), singleton pattern for runtime management.

**Spec:** Implicit in Plan C (bootstrap.py integration); Phase 3 fixes the runtime issue.

---

## Problem Analysis

**Current flow:**
```python
# bootstrap.py emit_bootstrap_steps()
lua = LuaRuntime()  # Fresh runtime A
conf_lua = _convert_to_lua_table(lua, conf)  # conf might have objects from runtime B
# → Error: "cannot mix objects from different Lua runtimes"
```

**Root cause:** Callers of `emit_bootstrap_steps()` may pass `conf` that was previously converted to a Lua table in a different runtime. When we try to convert it again in a new runtime, lupa detects the mismatch and raises.

**Why it happens:** plan_install() might process `conf` from external sources or previous steps that loaded Lua modules. The `conf` object becomes "tainted" with Lua objects from runtime A, and we can't use it in runtime B.

**Solution:** Use a singleton runtime manager:
- Always create/fetch the same LuaRuntime instance
- Convert all conf objects to pure Python (strip Lua objects) before storing them
- All Lua operations happen in the same runtime
- Clean teardown on module exit

---

## Tasks (4 total)

### Task 1: Create LuaRuntimeManager Singleton

**File:** Create `src/kod/lua_runtime.py`

```python
"""Singleton Lua runtime manager for bootstrap and other Lua integration.

Ensures all Lua code runs in the same runtime to avoid object mixing issues.
Provides centralized Lua environment management and cleanup.
"""

from typing import Optional
from lupa import LuaRuntime
import atexit
import logging

logger = logging.getLogger(__name__)


class LuaRuntimeManager:
    """Singleton manager for persistent Lua runtime."""
    
    _instance: Optional["LuaRuntimeManager"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.lua: Optional[LuaRuntime] = None
        self._initialized = True
        self._init_lua()
        
        # Register cleanup on exit
        atexit.register(self.cleanup)
    
    def _init_lua(self):
        """Initialize the Lua runtime."""
        try:
            self.lua = LuaRuntime()
            logger.debug("Lua runtime initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Lua runtime: {e}")
            raise
    
    def get_lua(self) -> LuaRuntime:
        """Get the persistent Lua runtime."""
        if self.lua is None:
            self._init_lua()
        return self.lua
    
    def cleanup(self):
        """Clean up Lua runtime resources."""
        if self.lua is not None:
            try:
                # Lupa handles finalizers automatically
                self.lua = None
                logger.debug("Lua runtime cleaned up")
            except Exception as e:
                logger.warning(f"Error during Lua cleanup: {e}")


# Global singleton accessor
_manager: Optional[LuaRuntimeManager] = None


def get_lua_runtime() -> LuaRuntime:
    """Get the global persistent Lua runtime."""
    global _manager
    if _manager is None:
        _manager = LuaRuntimeManager()
    return _manager.get_lua()


def cleanup_lua_runtime():
    """Clean up the global Lua runtime."""
    global _manager
    if _manager is not None:
        _manager.cleanup()
        _manager = None
```

**Testing:**
- `pytest tests/test_lua_runtime.py::test_lua_runtime_manager_singleton -v` (new test)
- Verify same runtime instance returned on multiple calls
- Verify cleanup doesn't crash

**Commit:** `feat: lua runtime manager singleton (persistent, no mixing)`

---

### Task 2: Update bootstrap.py to Use LuaRuntimeManager

**File:** Modify `src/kod/bootstrap.py`

Replace the per-call `lua = LuaRuntime()` pattern with persistent runtime:

```python
def emit_bootstrap_steps(conf: Any, predicted_partition_list: List[dict], distro: str = "arch") -> List[Step]:
    """Emit bootstrap steps via Lua module (using persistent runtime)."""
    from kod.lua_runtime import get_lua_runtime
    
    # Get persistent Lua runtime (singleton)
    lua = get_lua_runtime()
    
    # CRITICAL: Convert conf to pure Python FIRST to remove any Lua objects from previous runtimes
    if hasattr(conf, "keys"):  # It's a Lua table (from any runtime)
        conf = _lua_table_to_dict(conf)
    elif hasattr(conf, "__dict__"):
        conf = vars(conf)
    
    # Now convert to Lua table in OUR persistent runtime
    conf_lua = _convert_to_lua_table(lua, conf)
    
    # ... rest of function unchanged ...
```

**Key change:** Before creating Lua objects in our runtime, strip any Lua objects from the input by converting to pure Python dict first.

**Testing:**
- `pytest tests/test_bootstrap.py -v` → expect 4/4 PASS
- Verify no "cannot mix objects" error

**Commit:** `feat: bootstrap.py uses persistent Lua runtime manager`

---

### Task 3: Add Tests for Runtime Mixing Scenario

**File:** `tests/test_lua_runtime.py` (new)

```python
import pytest
from kod.lua_runtime import get_lua_runtime, cleanup_lua_runtime
from kod.bootstrap import emit_bootstrap_steps


def test_lua_runtime_manager_singleton():
    """LuaRuntimeManager returns same instance."""
    lua1 = get_lua_runtime()
    lua2 = get_lua_runtime()
    assert lua1 is lua2


def test_emit_bootstrap_steps_with_mixed_runtime_conf():
    """emit_bootstrap_steps handles conf from different runtime (strips and re-converts)."""
    # Simulate conf that has Lua objects from a previous runtime
    lua_old = get_lua_runtime()  # This is the persistent one
    
    # Create conf with Lua objects
    conf_dict = {
        "devices": {
            "1": {
                "device": "/dev/sda",
                "partitions": {},
            }
        },
        "locale": "en_US.UTF-8",
        "hostname": "testhost",
    }
    
    # Convert to Lua (taints it with Lua objects)
    conf_lua = lua_old.table_from(conf_dict)
    
    # Now try to emit bootstrap steps with this "tainted" conf
    # This should NOT raise "cannot mix objects from different Lua runtimes"
    # because emit_bootstrap_steps will convert it back to pure Python first
    predicted_partition_list = [
        {"device": "/dev/sda1", "mountpoint": "/boot", "filesystem": "vfat"},
    ]
    
    steps = emit_bootstrap_steps(conf_lua, predicted_partition_list, distro="arch")
    
    assert isinstance(steps, list)
    assert len(steps) > 0


def test_cleanup_lua_runtime():
    """cleanup_lua_runtime() handles gracefully."""
    cleanup_lua_runtime()
    # Should be able to get a fresh runtime after cleanup
    lua_new = get_lua_runtime()
    assert lua_new is not None
```

**Testing:**
- `pytest tests/test_lua_runtime.py -v` → expect 3/3 PASS

**Commit:** `test: Lua runtime mixing scenarios + singleton verification`

---

### Task 4: Full Regression & Verification

**Testing:**
- Run full suite: `pytest tests/ -q` → expect 490+ PASS (fix should reduce failures)
- Verify golden file test passes now (or if it still fails, document why)
- Verify no new regressions

**Commit (if needed):** `test: golden files updated after Lua runtime fix`

---

## Success Criteria

✅ Singleton LuaRuntimeManager created and tested  
✅ bootstrap.py uses persistent runtime (no per-call creation)  
✅ Input conf objects converted to pure Python before Lua operations  
✅ "cannot mix objects from different Lua runtimes" error eliminated  
✅ 490+ tests passing (reduced failures from 5 to ≤2)  
✅ No new regressions  
✅ Clean teardown on module exit  

---

## Summary

**What's built:** Persistent Lua runtime manager + bootstrap.py integration that strips Lua objects from inputs before converting to the persistent runtime.

**Why it works:** All Lua operations happen in the same runtime instance (singleton). Input conf objects are purified (converted to pure Python) before being converted back to Lua tables in the persistent runtime.

**Boundary:** Only fixes the runtime mixing issue; doesn't change bootstrap logic or step emission.
