"""Executor for step-based rebuild and install workflows.

Runs steps from the planner in order, dispatching by kind, firing lifecycle hooks,
managing per-step timeouts, and enforcing on_error policies.

Spec: docs/superpowers/specs/2026-09-10-kod-planner-hooks-buildcache-design.md §5.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import logging
from kod.planner import Step


logger = logging.getLogger(__name__)


class StepError(Exception):
    """Raised when a step fails and on_error='abort'."""
    pass


@dataclass(frozen=True)
class StepResult:
    """Result of executing a single step."""
    step: Step
    success: bool
    error: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    is_warning: bool = False  # True if this is on_error='warn' failure


def execute_steps(steps: List[Step], env: Dict[str, Any], mount_point: str,
                      use_chroot: bool, repos: Optional[Dict] = None,
                      hooks: Optional[Dict[str, List[Callable]]] = None) -> List[StepResult]:
    """Run steps via the Lua generic runner (kod/lib/executor.lua).

    Lua handles ordering, on_error policy, hooks, and chroot-wrapped shell
    steps (timeout-guarded, no output capture — lupa disables io.popen).
    Package/service/named-system steps dispatch to a Python callable built
    from env; the system modules behind them move to Lua in a later phase.

    Raises StepError on abort-step failure or unknown kind.
    """
    import os
    import lupa
    from kod.lua_runtime import get_lua_runtime

    lua = get_lua_runtime()
    base_path = os.path.dirname(os.path.dirname(__file__))
    lua.execute(f"package.path = '{base_path}/?.lua;{base_path}/?/init.lua' .. package.path")

    def dispatch_step(step, ctx_lua):
        kind = step.kind
        name = step.name
        meta = {}
        if step.meta is not None:
            for k in step.meta.keys():
                meta[k] = step.meta[k]
        mp = ctx_lua.mount_point

        if kind == "system":
            fn = env.get(name)
            if callable(fn):
                fn(meta.get("kernel"), mp)
        else:
            raise StepError(f"Unknown step kind: {kind}")

    steps_lua = lua.table()
    for i, s in enumerate(steps, 1):
        t = lua.table()
        t["kind"] = s.kind
        t["name"] = s.name
        t["program"] = s.program
        args = lua.table()
        for j, a in enumerate(s.args, 1):
            args[j] = a
        t["args"] = args
        t["chroot"] = s.chroot
        t["timeout_s"] = s.timeout_s
        t["on_error"] = s.on_error
        if s.meta:
            meta = lua.table()
            for k, v in s.meta.items():
                meta[k] = v
            t["meta"] = meta
        steps_lua[i] = t

    ctx_lua = lua.table()
    ctx_lua["mount_point"] = mount_point
    ctx_lua["use_chroot"] = bool(use_chroot)
    if repos is not None:
        ctx_lua["repos"] = repos

    dispatch_lua = lua.table()
    dispatch_lua["step"] = dispatch_step

    hooks_lua = lua.table()
    for k, v in (hooks or {}).items():
        arr = lua.table()
        for j, h in enumerate(v, 1):
            arr[j] = h
        hooks_lua[k] = arr

    module = lua.require("kod.lib.planning.executor")
    try:
        results_lua = module.run(steps_lua, ctx_lua, dispatch_lua, hooks_lua)
    except lupa.LuaError as e:
        raise StepError(str(e))

    results = []
    for i in range(1, len(results_lua) + 1):
        r = results_lua[i]
        results.append(StepResult(steps[i - 1], bool(r.success), error=r.error,
                                 is_warning=bool(r.is_warning)))
    return results
