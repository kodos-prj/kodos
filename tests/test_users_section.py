"""Tests for users.lua per-user program/service config deployment steps."""

import pytest
from kod.lua_runtime import get_lua_runtime
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "src"


@pytest.fixture
def lua():
    runtime = get_lua_runtime()
    runtime.execute(
        f"package.path = '{str(SRC_DIR)}/?.lua;{str(SRC_DIR)}/?/init.lua;' .. package.path"
    )
    return runtime


def _emit_users(lua, config_lua: str):
    """Run users section emit_steps with the given Lua config table."""
    result = lua.execute(f"""
        local steps = require('kod.sections.users').emit_steps({config_lua}, 'arch')
        local names = {{}}
        for _, s in pairs(steps) do
            table.insert(names, s.name)
        end
        return names
    """)
    return [result[i] for i in range(1, len(result) + 1)]


class TestUserProgramConfigSteps:
    def test_program_config_closure_emits_captured_commands(self, lua):
        names = _emit_users(lua, """
            { alice = { programs = {
                git = { enable = true, config = {
                    command = function(ctx, c)
                        ctx.execute("git config --global user.name \\"Antal Buss\\"")
                        ctx:execute("git config --global user.email \\"a@b.c\\"")
                    end,
                    stages = { "install", "rebuild-user" },
                } },
            } } }
        """)
        assert "users_alice_program_git_1" in names
        assert "users_alice_program_git_2" in names

    def test_rebuild_user_only_closure_not_planned(self, lua):
        names = _emit_users(lua, """
            { alice = { programs = {
                dconf = { enable = true, config = {
                    command = function(ctx, c)
                        ctx.execute("gsettings set org.gnome.desktop shell \\"gnome-shell\\"")
                    end,
                    stages = { "rebuild-user" },
                } },
            } } }
        """)
        assert not [n for n in names if "dconf" in n]

    def test_program_without_command_emits_nothing(self, lua):
        names = _emit_users(lua, """
            { alice = { programs = { vim = { enable = true, deploy_config = true } } } }
        """)
        assert not [n for n in names if "program_vim" in n]

    def test_service_config_closure_emits_steps(self, lua):
        names = _emit_users(lua, """
            { alice = { services = {
                syncthing = { enable = true, config = {
                    command = function(ctx, c)
                        ctx.execute("mkdir -p ~/.config/systemd/user/")
                    end,
                    stages = { "install" },
                } },
            } } }
        """)
        assert "users_alice_service_syncthing_1" in names
