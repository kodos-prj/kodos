"""Executor for step-based rebuild and install workflows.

Runs steps from the planner in order, dispatching by kind, firing lifecycle hooks,
managing per-step timeouts, and enforcing on_error policies.

Spec: docs/superpowers/specs/2026-09-10-kod-planner-hooks-buildcache-design.md §5.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from kod.bootstrap import _convert_to_lua_table
from kod.common import exec, exec_chroot
from kod.planner import Step
from kod.system.boot import get_kernel_file

logger = logging.getLogger(__name__)


class StepError(Exception):
    """Raised when a step fails and on_error='abort'."""

    pass


@dataclass(frozen=True)
class StepResult:
    """Result of executing a single step.

    Immutable record of what happened when a Step ran: whether it succeeded,
    what error (if any) occurred, and metadata for debugging/logging.

    Attributes:
        step: The Step that was executed (see planner.py).
        success: True if the step completed without error.
        error: Error message if step failed (on_error='abort') or warned
            (on_error='warn'). None if success=True.
        stdout: Captured stdout from step execution. None until implemented.
        stderr: Captured stderr from step execution. None until implemented.
        is_warning: True if step failed but on_error='warn', so execution
            continued. False for abort-steps or successful steps.
    """

    step: Step
    success: bool
    error: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    is_warning: bool = False


def execute_steps(
    steps: list[Step],
    mount_point: str,
    use_chroot: bool,
    repos: dict | None = None,
    hooks: dict[str, list[Callable]] | None = None,
) -> list[StepResult]:
    """Run steps via the Lua generic runner (kod/lib/executor.lua).

    Lua handles ordering, on_error policy, hooks, and chroot-wrapped shell
    steps (timeout-guarded, no output capture — lupa disables io.popen).
    Package/service/named-system steps dispatch to a Python callable built
    from repos; the system modules behind them move to Lua in a later phase.

    Raises StepError on abort-step failure or unknown kind.
    """
    import os

    import lupa

    from kod.lua_runtime import get_lua_runtime

    lua = get_lua_runtime()
    base_path = os.path.dirname(os.path.dirname(__file__))
    lua.execute(
        f"package.path = '{base_path}/?.lua;{base_path}/?/init.lua' .. package.path"
    )

    # Force reload of planning modules to ensure we have fresh code
    from kod.lua_runtime import LuaRuntimeManager

    manager = LuaRuntimeManager()
    manager.reload_modules([r"kod\.planning\..*"])

    steps_lua = _convert_to_lua_table(lua, [s.to_dict() for s in steps])

    ctx_data = {
        "mount_point": mount_point,
        "use_chroot": bool(use_chroot),
    }
    if repos is not None:
        ctx_data["repos"] = repos
    ctx_lua = _convert_to_lua_table(lua, ctx_data)

    dispatch_lua = lua.table()
    
    def dispatch_step(step, ctx_lua):
        """Dispatch package/service steps to Python handlers.
        
        Package and service steps have commands that need to be run with
        proper permissions. During install (chroot=True), they run in the chroot.
        During rebuild (chroot=False), they run on host with sudo.
        Returns None (success) or raises on failure.
        """
        try:
            kind = step.kind
            # Command is stored in meta since we don't want it in the step dict
            # (which would make Lua executor treat it as a shell step)
            meta = step.meta if step.meta is not None else {}
            cmd = meta.get("command") if meta else ""
            if not cmd:
                cmd = ""
            
            if kind == "package" or kind == "service":
                if not cmd:
                    return  # No-op step
                
                mp = ctx_lua.mount_point if ctx_lua else "/"
                # Safely access chroot field with default False
                chroot_needed = False
                try:
                    chroot_needed = bool(step.chroot)
                except:
                    chroot_needed = False
                
                if chroot_needed and mp != "/":
                    # During install: chroot into new mount point
                    exec_chroot(cmd, mount_point=mp)
                elif chroot_needed:
                    # chroot=True but mount_point is "/", run as-is (on current system)
                    exec(cmd)
                else:
                    # During rebuild: run on host with sudo
                    exec(f"sudo {cmd}")
            else:
                raise StepError(f"Unknown dispatch step kind: {kind}")
        except StepError:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise StepError(f"dispatch_step failed: {e}")
    
    dispatch_lua["step"] = dispatch_step
    
    # Inject Python exec functions for Lua system modules to call back
    # These are used by src/lua/kod/system/boot.lua
    dispatch_lua["_dispatch_python"] = lua.table()
    dispatch_lua["_dispatch_python"]["exec"] = lambda cmd, get_output=False: exec(cmd, get_output=get_output)
    dispatch_lua["_dispatch_python"]["exec_chroot"] = lambda cmd, **kw: exec_chroot(cmd, **kw)
    dispatch_lua["_dispatch_python"]["get_kernel_file"] = lambda mp, pkg="linux": get_kernel_file(mp, pkg)

    hooks_data = hooks or {}
    hooks_lua = _convert_to_lua_table(lua, hooks_data)

    module_result = lua.require("kod.planning.executor")
    # lupa returns a tuple (module, ...) when requiring Lua modules
    if isinstance(module_result, tuple):
        module = module_result[0]
    else:
        module = module_result
    try:
        results_lua = module.run(steps_lua, ctx_lua, dispatch_lua, hooks_lua)
    except lupa.LuaError as e:
        raise StepError(str(e))

    results = []
    for i in range(1, len(results_lua) + 1):
        r = results_lua[i]
        results.append(
            StepResult(
                steps[i - 1],
                bool(r.success),
                error=r.error,
                is_warning=bool(r.is_warning),
            )
        )
    return results
