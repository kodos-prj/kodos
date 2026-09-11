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
    lua_runtime = get_lua_runtime()
    
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
    conf_lua = lua_runtime.table_from(conf_dict)
    
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
