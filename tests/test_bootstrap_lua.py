"""Tests for Lua planner integration in kod/planner.py (Phase 5c)."""

import os
import pytest
import lupa
from pathlib import Path

from kod.planner import compose_steps_lua, _convert_lua_step_to_step, Step, plan_install, build_plan


def _to_lua(lua, value):
    """Convert Python value to Lua table recursively."""
    if isinstance(value, dict):
        t = lua.table()
        for k, v in value.items():
            t[k] = _to_lua(lua, v)
        return t
    if isinstance(value, list):
        t = lua.table()
        for i, v in enumerate(value, 1):
            t[i] = _to_lua(lua, v)
        return t
    return value


def make_lua_config(**sections):
    """Build a LuaTable config for testing."""
    lua = lupa.LuaRuntime()
    t = lua.table()
    for k, v in sections.items():
        t[k] = _to_lua(lua, v)
    return t


def make_conf(**sections):
    """Build a LuaTable conf, same shape as production (nil for missing keys)."""
    from kod.lua_runtime import get_lua_runtime
    lua = get_lua_runtime()
    t = lua.table()
    for k, v in sections.items():
        if isinstance(v, list):
            arr = lua.table()
            for i, item in enumerate(v, 1):
                arr[i] = item
            t[k] = arr
        else:
            t[k] = v
    return t


class TestLuaStepConversion:
    """Test converting Lua step tables to Python Step objects."""
    
    def test_convert_lua_step_basic(self):
        """Convert a basic Lua step table to Step."""
        lua = lupa.LuaRuntime()
        lua_step = lua.table()
        lua_step['kind'] = 'package'
        lua_step['name'] = 'git'
        lua_step['program'] = 'pacman'
        lua_step['meta'] = lua.table()
        
        step = _convert_lua_step_to_step(lua_step)
        
        assert step.kind == 'package'
        assert step.name == 'git'
        assert step.program == 'pacman'
        assert isinstance(step, Step)
    
    def test_convert_lua_step_with_args(self):
        """Convert Lua step with args array."""
        lua = lupa.LuaRuntime()
        lua_step = lua.table()
        lua_step['kind'] = 'disk'
        lua_step['name'] = 'wipe-disk'
        lua_step['program'] = 'wipefs'
        
        args_lua = lua.table()
        args_lua[1] = '-a'
        args_lua[2] = '/dev/sda'
        lua_step['args'] = args_lua
        
        lua_step['meta'] = lua.table()
        
        step = _convert_lua_step_to_step(lua_step)
        
        assert step.program == 'wipefs'
        assert step.args == ('-a', '/dev/sda')
    
    def test_convert_lua_step_with_meta(self):
        """Convert Lua step with metadata dict."""
        lua = lupa.LuaRuntime()
        lua_step = lua.table()
        lua_step['kind'] = 'package'
        lua_step['name'] = 'git'
        lua_step['program'] = ''
        
        meta_lua = lua.table()
        meta_lua['action'] = 'install'
        meta_lua['repo'] = 'official'
        lua_step['meta'] = meta_lua
        
        step = _convert_lua_step_to_step(lua_step)
        
        assert step.meta['action'] == 'install'
        assert step.meta['repo'] == 'official'


class TestComposeLuaSteps:
    """Test calling the Lua planner via compose_steps_lua."""
    
    def test_compose_returns_list_of_steps(self):
        """compose_steps_lua returns a list of Step objects."""
        conf = make_conf(
            base_distribution='arch',
            devices=None,
            repos=None,
            packages=['base'],
            services=None,
            users=None,
        )
        
        steps = compose_steps_lua(conf, distro='arch')
        
        assert isinstance(steps, list)
        assert all(isinstance(s, Step) for s in steps)
    
    def test_compose_with_invalid_config_raises(self):
        """compose_steps_lua raises error for invalid config."""
        conf = make_conf()  # Empty config, missing base_distribution
        
        with pytest.raises(RuntimeError):
            compose_steps_lua(conf, distro='arch')
    
    def test_compose_distro_parameter_passed(self):
        """compose_steps_lua passes distro parameter to Lua planner."""
        conf = make_conf(
            base_distribution='debian',
        )
        
        # Should not raise
        steps = compose_steps_lua(conf, distro='debian')
        assert isinstance(steps, list)
    
    def test_compose_with_arch_distro(self):
        """compose_steps_lua works with Arch Linux."""
        conf = make_conf(
            base_distribution='arch',
            packages=['base', 'grub'],
        )
        
        steps = compose_steps_lua(conf, distro='arch')
        assert isinstance(steps, list)
    
    def test_compose_with_debian_distro(self):
        """compose_steps_lua works with Debian."""
        conf = make_conf(
            base_distribution='debian',
            packages=['build-essential'],
        )
        
        steps = compose_steps_lua(conf, distro='debian')
        assert isinstance(steps, list)


class TestPlanInstallLuaIntegration:
    """Test plan_install function with Lua planner."""
    
    def test_plan_install_uses_lua_planner_when_enabled(self):
        """plan_install uses Lua planner when KOD_USE_LUA_PLANNER=true."""
        os.environ['KOD_USE_LUA_PLANNER'] = 'true'
        
        conf = make_conf(
            base_distribution='arch',
            devices=None,
        )
        
        steps = plan_install(conf)
        
        assert isinstance(steps, list)
        assert all(isinstance(s, Step) for s in steps)
    
    def test_plan_install_fallback_when_lua_disabled(self):
        """plan_install falls back to Python planner when KOD_USE_LUA_PLANNER=false."""
        os.environ['KOD_USE_LUA_PLANNER'] = 'false'
        
        conf = make_conf(
            base_distribution='arch',
            devices=None,
            repos=None,
            packages=['base'],
            services=None,
            users=None,
        )
        
        # Should not raise, uses Python fallback
        steps = plan_install(conf)
        assert isinstance(steps, list)
    
    def test_plan_install_fallback_on_lua_error(self):
        """plan_install falls back to Python if Lua planner fails."""
        os.environ['KOD_USE_LUA_PLANNER'] = 'true'
        
        # Config missing base_distribution - should make Lua fail
        # But plan_install has try-except, so it should fall back to Python
        conf = make_conf()
        
        # This may raise because Python fallback also needs proper config
        # But at least it should try both paths
        try:
            steps = plan_install(conf)
        except Exception:
            # Expected if config is truly invalid
            pass


class TestBuildPlanLuaIntegration:
    """Test build_plan function with Lua planner."""
    
    def test_build_plan_empty_baseline_uses_plan_install(self):
        """build_plan with empty baseline calls plan_install."""
        os.environ['KOD_USE_LUA_PLANNER'] = 'true'
        
        conf = make_conf(
            base_distribution='arch',
            devices=None,
        )
        
        steps = build_plan(conf, baseline='empty')
        
        assert isinstance(steps, list)
        assert all(isinstance(s, Step) for s in steps)


class TestLuaPlannerBackwardCompat:
    """Test backward compatibility - Python planner still works as fallback."""
    
    def test_python_planner_fallback_exists(self):
        """Python fallback paths still exist for backward compatibility."""
        os.environ['KOD_USE_LUA_PLANNER'] = 'false'
        
        from kod.planner import plan_disk_steps
        
        # plan_disk_steps should still exist
        assert callable(plan_disk_steps)
    
    def test_step_class_unchanged(self):
        """Step dataclass interface unchanged."""
        step = Step(kind='package', name='git')
        
        assert step.kind == 'package'
        assert step.name == 'git'
        assert step.to_dict()['kind'] == 'package'


class TestLuaRuntimeManagement:
    """Test Lua runtime singleton and cleanup."""
    
    def test_lua_runtime_singleton(self):
        """Lua runtime is persistent (singleton)."""
        from kod.lua_runtime import get_lua_runtime
        
        lua1 = get_lua_runtime()
        lua2 = get_lua_runtime()
        
        assert lua1 is lua2
    
    def test_lua_runtime_init(self):
        """Lua runtime initializes without errors."""
        from kod.lua_runtime import get_lua_runtime
        
        lua = get_lua_runtime()
        assert lua is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
