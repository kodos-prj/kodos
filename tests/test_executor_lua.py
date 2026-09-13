"""Tests for the Lua generic step runner (kod/lib/executor.lua) and its bridge."""

from pathlib import Path

import pytest

from kod.planner import Step
from kod.executor import Executor, StepError, execute_steps_lua

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
    result = lua.require("kod.lib.executor")
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
    def test_package_dispatch_gets_python_types(self):
        calls = []

        def fake_manage(mp, repos, action, pkgs, chroot=False):
            calls.append((mp, type(repos).__name__, action, pkgs, chroot))

        results = execute_steps_lua(
            [Step("package", "git", meta={"action": "install"})],
            {"manage_packages": fake_manage}, "/mnt", True)
        assert calls == [("/mnt", "NoneType", "install", ["git"], True)]
        assert results[0].success

    def test_service_dispatch(self):
        calls = []

        def fake_enable(svcs, mount_point="/mnt", use_chroot=False):
            calls.append((svcs, mount_point, use_chroot))

        results = execute_steps_lua(
            [Step("service", "sshd", meta={"action": "enable"})],
            {"enable_services": fake_enable}, "/mnt", False)
        assert calls == [(["sshd"], "/mnt", False)]
        assert results[0].success

    def test_named_system_step_dispatch(self):
        calls = []

        def fake_kernel(kernel, mp):
            calls.append((kernel, mp))

        results = execute_steps_lua(
            [Step("system", "kernel-update", meta={"kernel": "linux-lts"})],
            {"kernel-update": fake_kernel}, "/mnt", True)
        assert calls == [("linux-lts", "/mnt")]
        assert results[0].success

    def test_shell_step_through_bridge(self):
        results = execute_steps_lua(
            [Step("system", "echo-step", program="echo", args=("hi",), timeout_s=30)],
            {}, "/", False)
        assert results[0].success

    def test_warn_failure_through_bridge(self):
        results = execute_steps_lua(
            [Step("system", "fail-step", program="false", timeout_s=30, on_error="warn")],
            {}, "/", False)
        assert not results[0].success
        assert results[0].is_warning

    def test_abort_failure_raises_steperror(self):
        with pytest.raises(StepError):
            execute_steps_lua(
                [Step("system", "fail-step", program="false", timeout_s=30)],
                {}, "/", False)


class TestLuaMatchesPythonExecutor:
    """Same steps through both runners must give the same success sequence."""

    def test_equivalence(self):
        steps = [
            Step("system", "ok-echo", program="echo", args=("x",), timeout_s=30),
            Step("system", "warn-fail", program="false", timeout_s=30, on_error="warn"),
            Step("system", "marker", program=""),
        ]
        py = Executor(env={}).execute(steps, {"mount_point": "/", "use_chroot": False})
        lu = execute_steps_lua(steps, {}, "/", False)
        assert [r.success for r in py] == [r.success for r in lu]
        assert [r.is_warning for r in py] == [r.is_warning for r in lu]
