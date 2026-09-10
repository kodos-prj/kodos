"""Tests for kod/planner.py (Plan A: read-only plan preview)."""

from dataclasses import replace
from unittest.mock import patch

import lupa
import pytest


def make_conf(**sections):
    """Build a LuaTable conf, same shape as production (nil for missing keys)."""
    return lupa.LuaRuntime().table_from(sections)


class TestStepModel:
    def test_defaults(self):
        from kod.planner import Step

        s = Step("package", "git")
        assert s.program == ""
        assert s.args == ()
        assert s.chroot is False
        assert s.timeout_s == 300
        assert s.on_error == "abort"
        assert s.meta == {}

    def test_to_dict_roundtrip(self):
        from kod.planner import Step

        s = Step("package", "git", program="pacman", args=("-S", "git"),
                 on_error="warn", meta={"repo": "official"})
        d = s.to_dict()
        assert d == {
            "kind": "package", "name": "git", "program": "pacman",
            "args": ["-S", "git"], "chroot": False, "timeout_s": 300,
            "on_error": "warn", "meta": {"repo": "official"},
        }

    def test_render_is_deterministic(self):
        from kod.planner import Step, render_plan

        steps = [Step("package", "b", meta={"x": 1, "a": 2}), Step("service", "sshd")]
        assert render_plan(steps, "empty") == render_plan(steps, "empty")

    def test_render_format(self):
        from kod.planner import Step, render_plan

        out = render_plan(
            [Step("disk", "wipe:/dev/vda", program="wipefs", args=("-a", "/dev/vda")),
             Step("system", "base-packages", meta={"kernel": "linux"}),
             Step("system", "bootloader")],
            "empty", "example/testvm/configuration.lua")
        lines = out.splitlines()
        assert lines[0] == "# kod plan"
        assert lines[1] == "# baseline=empty config=example/testvm/configuration.lua"
        assert lines[2] == "001 [disk] wipe:/dev/vda: wipefs -a /dev/vda"
        assert lines[3] == '002 [system] base-packages: {"kernel": "linux"}'
        assert lines[4] == "003 [system] bootloader:"
