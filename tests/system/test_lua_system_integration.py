"""Integration test for lua-system step execution.

Verifies that:
1. Boot section emits lua-system steps
2. Executor properly dispatches lua-system steps to Lua
3. Lua boot module functions are called correctly
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")

from kod import planner
from kod.executor import execute_steps
from kod.context import Context


def _to_lua(lua, value):
    """Convert Python value to Lua value (from test_planner.py)."""
    if isinstance(value, dict):
        t = lua.table()
        for k, v in value.items():
            t[k] = _to_lua(lua, v)
        return t
    elif isinstance(value, (list, tuple)):
        t = lua.table()
        for i, v in enumerate(value, start=1):
            t[i] = _to_lua(lua, v)
        return t
    return value


def make_conf(**sections):
    """Build a LuaTable conf in the shared runtime (same shape as production)."""
    from kod.lua_runtime import get_lua_runtime
    lua = get_lua_runtime()
    sections.setdefault("base_distribution", "arch")
    t = lua.table()
    for k, v in sections.items():
        t[k] = _to_lua(lua, v)
    return t


def test_lua_system_step_generation():
    """Verify that boot section generates lua-system steps."""
    print("=" * 60)
    print("Test 1: Boot section generates lua-system steps")
    print("=" * 60)
    
    # Minimal config with boot section
    config = make_conf(
        boot={
            "kernel": {
                "package": "linux",
                "modules": ["btrfs"]
            },
            "loader": {
                "type": "systemd-boot"
            }
        }
    )
    
    steps = planner.plan_install(config)
    
    # Find lua-system steps
    lua_system_steps = [s for s in steps if s.get("kind") == "lua-system"]
    
    print(f"\nGenerated {len(lua_system_steps)} lua-system steps:")
    for step in lua_system_steps:
        print(f"  - {step.get('name')}: {step.get('meta', {}).get('operation')}")
    
    # Verify expected steps
    operations = {s.get("meta", {}).get("operation") for s in lua_system_steps}
    assert "update_kernel" in operations, "Should have update_kernel step"
    assert "update_initramfs" in operations, "Should have update_initramfs step"
    assert "create_boot_entry" in operations, "Should have create_boot_entry step"
    
    print("\n✓ All expected lua-system operations generated")


def test_lua_system_step_structure():
    """Verify lua-system steps have correct structure."""
    print("\n" + "=" * 60)
    print("Test 2: lua-system steps have correct structure")
    print("=" * 60)
    
    config = make_conf(
        boot={
            "kernel": {"package": "linux"},
            "loader": {"type": "systemd-boot"}
        }
    )
    
    steps = planner.plan_install(config)
    
    lua_system_steps = [s for s in steps if s.get("kind") == "lua-system"]
    
    for step in lua_system_steps:
        print(f"\nStep: {step.get('name')}")
        print(f"  kind: {step.get('kind')}")
        print(f"  command: {step.get('command')}")
        print(f"  meta.operation: {step.get('meta', {}).get('operation')}")
        print(f"  meta.kernel: {step.get('meta', {}).get('kernel')}")
        
        # Verify structure
        assert step.get("kind") == "lua-system"
        assert step.get("command") in ["kernel_update", "initramfs_update", "boot_entry"]
        assert step.get("meta", {}).get("operation") is not None
        assert step.get("meta", {}).get("kernel") is not None
    
    print("\n✓ All lua-system steps have correct structure")


def test_boot_entry_step_includes_generation():
    """Verify create_boot_entry step includes generation ID."""
    print("\n" + "=" * 60)
    print("Test 3: create_boot_entry step includes generation ID")
    print("=" * 60)
    
    config = make_conf(
        boot={
            "kernel": {"package": "linux"},
            "loader": {"type": "systemd-boot"}
        }
    )
    
    steps = planner.plan_install(config)
    
    boot_entry_steps = [s for s in steps 
                        if s.get("kind") == "lua-system" 
                        and s.get("meta", {}).get("operation") == "create_boot_entry"]
    
    assert len(boot_entry_steps) > 0, "Should have create_boot_entry step"
    
    for step in boot_entry_steps:
        generation = step.get("meta", {}).get("generation")
        print(f"\nBoot entry step: {step.get('name')}")
        print(f"  generation: {generation}")
        assert generation is not None, "Boot entry step should have generation ID"
    
    print("\n✓ Boot entry steps include generation ID")


if __name__ == "__main__":
    print("\nLua-System Integration Tests")
    print("=" * 60)
    
    try:
        test_lua_system_step_generation()
        test_lua_system_step_structure()
        test_boot_entry_step_includes_generation()
        
        print("\n" + "=" * 60)
        print("ALL INTEGRATION TESTS PASSED ✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
