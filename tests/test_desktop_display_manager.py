"""Display manager install is gated on at least one enabled environment."""

import pytest
from pathlib import Path

from kod.lua_runtime import get_lua_runtime


SRC_DIR = Path(__file__).parent.parent / "src"


@pytest.fixture
def lua():
    rt = get_lua_runtime()
    rt.execute(f"""
        package.path = '{SRC_DIR}/?.lua;{SRC_DIR}/?/init.lua;' .. package.path
    """)
    return rt


def _dm_step_names(lua, envs_lua):
    lua.execute(f"""
        local d = require('kod.sections.desktop')
        config = {{
            display_manager = "lightdm",
            environments = {{{envs_lua}}},
        }}
        result = d.emit_steps(config, 'arch')
        names = {{}}
        for _, s in ipairs(result) do names[#names + 1] = s.name end
    """)
    t = lua.eval("names")
    return [t[i] for i in sorted(t)]


def test_no_dm_when_all_environments_disabled(lua):
    names = _dm_step_names(lua, "gnome = { enable = false }, plasma = { enable = false }")
    assert not [n for n in names if n.startswith("desktop_display_manager")]


def test_dm_installed_when_an_environment_is_enabled(lua):
    names = _dm_step_names(lua, "gnome = { enable = true }, plasma = { enable = false }")
    assert "desktop_display_manager_install" in names
    assert "desktop_display_manager_enable" in names


def test_dm_enabled_by_default_when_environment_has_no_enable_key(lua):
    # Same semantics as the environments loop: enable ~= false counts as enabled.
    names = _dm_step_names(lua, "gnome = {}")
    assert "desktop_display_manager_install" in names
