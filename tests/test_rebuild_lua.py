"""Tests for the Lua rebuild diff planner (kod/lib/planning/rebuild.lua)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from kod.lua_runtime import get_lua_runtime

SRC_DIR = Path(__file__).parent.parent / "src"


@pytest.fixture
def lua():
    runtime = get_lua_runtime()
    runtime.execute(
        f"package.path = '{str(SRC_DIR)}/?.lua;{str(SRC_DIR)}/?/init.lua;' .. package.path"
    )
    return runtime


def _diff(lua, state_lua: str):
    result = lua.execute(f"""
        local steps = require('kod.planning.rebuild').diff({state_lua})
        local out = {{}}
        for _, s in ipairs(steps) do
            table.insert(out, s.kind .. " " .. s.name)
        end
        return out
    """)
    return [result[i] for i in range(1, len(result) + 1)]


class TestRebuildDiffLua:
    def test_install_remove_disable_enable_order(self, lua):
        steps = _diff(lua, """
            { next_packages = { packages = { "keep", "new" }, kernel = "linux" },
              current_packages = { packages = { "keep", "gone" }, kernel = "linux" },
              remove_packages = {},
              next_services = { "newsvc" },
              current_services = { "oldsvc" },
              disabled_services = { "oldsvc" },
              update = false, new_generation = false, kernel_update_required = false, distro = "arch" }
        """)
        assert steps == ["service oldsvc", "package gone", "package new",
                        "service newsvc", "lua-system boot-entry"]

    def test_new_generation_skips_disable(self, lua):
        steps = _diff(lua, """
            { next_packages = { packages = {}, kernel = "linux" },
              current_packages = { packages = {}, kernel = "linux" },
              remove_packages = {},
              next_services = {},
              current_services = { "oldsvc" },
              disabled_services = {},
              update = false, new_generation = true, kernel_update_required = false, distro = "arch" }
        """)
        assert steps == ["lua-system boot-entry"]

    def test_kernel_and_update_steps(self, lua):
        steps = _diff(lua, """
            { next_packages = { packages = {}, kernel = "linux-lts" },
              current_packages = { packages = {}, kernel = "linux" },
              remove_packages = {},
              next_services = {},
              current_services = {},
              disabled_services = {},
              update = true, new_generation = false, kernel_update_required = true, distro = "arch" }
        """)
        assert steps == ["system update-packages", "system boot_kernel_modules_config", "package linux-lts",
                        "lua-system kernel-update", "lua-system initramfs-update",
                        "lua-system boot-entry"]

    def test_explicit_remove_packages(self, lua):
        steps = _diff(lua, """
            { next_packages = { packages = { "keep" }, kernel = "linux" },
              current_packages = { packages = { "keep" }, kernel = "linux" },
              remove_packages = { "forced" },
              next_services = {},
              current_services = {},
              disabled_services = {},
              update = false, new_generation = false, kernel_update_required = false, distro = "arch" }
        """)
        assert steps == ["package forced", "lua-system boot-entry"]


class TestRebuildPlanAbsolute:
    """The Lua rebuild plan is locked to an absolute sequence (no Python oracle)."""

    def test_combined_diff_ordering(self):
        from kod.planner import plan_rebuild, render_plan
        from tests.test_planner import make_conf, make_dist, BASE_PKGS

        kwargs = dict(
            current_packages={"packages": ["keep", "gone", "extra"], "kernel": "linux"},
            current_services=["oldsvc", "sshd"],
            current_installed_packages={},
            update=True,
            new_generation=False,
        )
        with patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS):
            steps = plan_rebuild(
                make_conf(boot={"kernel": {"package": "linux-lts"}}, packages=["keep", "new"], services={"sshd": {}}),
                make_dist(kernel_update=True), **kwargs)
        lines = [l for l in render_plan(steps, "current").splitlines() if l[:1].isdigit()]
        # Note: oldsvc is NOT disabled because it's not in the disabled_services list.
        # Only services from explicitly disabled programs are removed during rebuild.
        assert lines == [
            "001 [system] update-packages: pacman -Syu --noconfirm --needed",
            '002 [package] extra: pacman -Rscn --noconfirm extra',
            '003 [package] gone: pacman -Rscn --noconfirm gone',
            '004 [package] linux-lts: pacman -S --noconfirm linux-lts',
            '005 [package] new: pacman -S --noconfirm new',
            '006 [system] kernel-update: {"kernel": "linux-lts"}',
            '007 [system] initramfs-update: {"kernel": "linux-lts"}',
            '008 [system] boot-entry: {"kernel": "linux-lts"}',
        ]

    def test_only_disabled_programs_services_are_removed(self, lua):
        """Only services from DISABLED programs should be removed.
        
        Services simply missing from next_services (not in config at all) should NOT be removed.
        Example: nix_daemon, tailscale, avahi - these are services on the system that aren't
        part of the config, so they should not be automatically disabled during rebuild.
        
        Only if a program is EXPLICITLY DISABLED (enable=false) should its service be removed.
        """
        steps = _diff(lua, """
            { next_packages = { packages = { "enabled_prog" }, kernel = "linux" },
              current_packages = { packages = { "enabled_prog", "disabled_prog", "external_prog" }, kernel = "linux" },
              remove_packages = {},
              next_services = { "enabled_svc" },
              current_services = { "enabled_svc", "disabled_svc", "external_svc" },
              disabled_services = { "disabled_svc" },
              update = false, new_generation = false, kernel_update_required = false, distro = "arch" }
        """)
        # Should remove: disabled_svc (from explicitly disabled program)
        # Should NOT remove: external_svc (service not in config at all)
        assert "service disabled_svc" in steps, f"Expected 'service disabled_svc' in {steps}"
        assert "service external_svc" not in steps, f"Should not disable external_svc, but got {steps}"
