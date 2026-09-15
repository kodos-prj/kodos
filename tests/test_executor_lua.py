"""Tests for the Lua generic step runner (kod/lib/executor.lua) and its bridge."""

from pathlib import Path

import pytest

from kod.planner import Step
from kod.executor import StepError, execute_steps

SRC_DIR = Path(__file__).parent.parent / "src"


@pytest.fixture
def lua():
    from kod.lua_runtime import get_lua_runtime
    runtime = get_lua_runtime()
    runtime.execute(
        f"package.path = '{str(SRC_DIR)}/?.lua;{str(SRC_DIR)}/?/init.lua;' .. package.path"
    )
    return runtime


def _mod(lua):
    result = lua.require("kod.lib.planning.executor")
    return result[0] if isinstance(result, tuple) else result


def _step_table(lua, **kw):
    t = lua.table()
    for k, v in kw.items():
        if isinstance(v, (list, tuple)):
            arr = lua.table()
            for i, x in enumerate(v, 1):
                arr[i] = x
            t[k] = arr
        else:
            t[k] = v
    return t


class TestLuaRunner:
    def test_shell_step_succeeds(self, lua):
        mod = _mod(lua)
        steps = lua.table()
        steps[1] = _step_table(lua, kind="system", name="echo-step",
                               program="echo", args=("hi",), timeout_s=30)
        ctx = lua.table(); ctx["mount_point"] = "/"
        results = mod.run(steps, ctx, lua.table())
        assert results[1].success

    def test_warn_step_records_failure_without_raising(self, lua):
        mod = _mod(lua)
        steps = lua.table()
        steps[1] = _step_table(lua, kind="system", name="fail-step",
                               program="false", timeout_s=30, on_error="warn")
        ctx = lua.table(); ctx["mount_point"] = "/"
        results = mod.run(steps, ctx, lua.table())
        assert not results[1].success
        assert results[1].is_warning

    def test_abort_step_raises(self, lua):
        mod = _mod(lua)
        steps = lua.table()
        steps[1] = _step_table(lua, kind="system", name="fail-step",
                               program="false", timeout_s=30)
        ctx = lua.table(); ctx["mount_point"] = "/"
        with pytest.raises(Exception):
            mod.run(steps, ctx, lua.table())

    def test_metadata_only_step_is_noop(self, lua):
        mod = _mod(lua)
        steps = lua.table()
        steps[1] = _step_table(lua, kind="system", name="marker", program="")
        ctx = lua.table(); ctx["mount_point"] = "/"
        results = mod.run(steps, ctx, lua.table())
        assert results[1].success

    def test_unknown_kind_raises(self, lua):
        mod = _mod(lua)
        steps = lua.table()
        steps[1] = _step_table(lua, kind="wibble", name="x")
        ctx = lua.table(); ctx["mount_point"] = "/"
        with pytest.raises(Exception):
            mod.run(steps, ctx, lua.table())

    def test_timeout_kills_long_step(self, lua):
        mod = _mod(lua)
        steps = lua.table()
        steps[1] = _step_table(lua, kind="system", name="slow",
                               program="sleep", args=("5",), timeout_s=1, on_error="warn")
        ctx = lua.table(); ctx["mount_point"] = "/"
        results = mod.run(steps, ctx, lua.table())
        assert not results[1].success


class TestExecuteStepsLuaBridge:
    def test_named_system_step_dispatch(self):
        calls = []

        def fake_kernel(kernel, mp):
            calls.append((kernel, mp))

        results = execute_steps(
            [Step("system", "kernel-update", meta={"kernel": "linux-lts"})],
            {"kernel-update": fake_kernel}, "/mnt", True)
        assert calls == [("linux-lts", "/mnt")]
        assert results[0].success

    def test_shell_step_through_bridge(self):
        results = execute_steps(
            [Step("system", "echo-step", program="echo", args=("hi",), timeout_s=30)],
            {}, "/", False)
        assert results[0].success

    def test_warn_failure_through_bridge(self):
        results = execute_steps(
            [Step("system", "fail-step", program="false", timeout_s=30, on_error="warn")],
            {}, "/", False)
        assert not results[0].success
        assert results[0].is_warning

    def test_abort_failure_raises_steperror(self):
        with pytest.raises(StepError):
            execute_steps(
                [Step("system", "fail-step", program="false", timeout_s=30)],
                {}, "/", False)


class TestHooksThroughBridge:
    """Pre/post hooks fire through the Lua runner (executor.lua)."""

    def test_pre_hook_failure_aborts(self):
        def bad_pre(step, ctx):
            raise ValueError("pre boom")

        with pytest.raises(StepError):
            execute_steps(
                [Step("package", "git", program="true")],
                {}, "/mnt", True,
                hooks={"pre:package": [bad_pre]})

    def test_post_hook_failure_is_swallowed(self):
        def bad_post(step, ctx):
            raise ValueError("post boom")

        results = execute_steps(
            [Step("package", "git", program="true")],
            {}, "/mnt", True,
            hooks={"post:package": [bad_post]})
        assert results[0].success
