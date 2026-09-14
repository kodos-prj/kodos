"""Executor for step-based rebuild and install workflows.

Runs steps from the planner in order, dispatching by kind, firing lifecycle hooks,
managing per-step timeouts, and enforcing on_error policies.

Spec: docs/superpowers/specs/2026-09-10-kod-planner-hooks-buildcache-design.md §5.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import logging
import concurrent.futures
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


class Executor:
    """Execute a list of steps from the planner.
    
    Dispatch table maps (kind, action) to callables. Pre/post hooks fire per step.
    On_error policy controls step failure handling (abort | warn).
    """
    
    def __init__(self, env: Dict[str, Any], logger_fn: Optional[Callable] = None):
        """Initialize executor.
        
        Args:
            env: Environment dict with callable functions for dispatch
                 (e.g., {"manage_packages": fn, "enable_services": fn, ...})
            logger_fn: Optional logging function (for tests). Defaults to logging.warning.
        """
        self.env = env
        self.logger_fn = logger_fn or (lambda msg: logger.warning(msg))
    
    def execute(self, steps: List[Step], ctx: Dict[str, Any], hooks: Optional[Dict[str, List[Callable]]] = None) -> List[StepResult]:
        """Execute steps in order.
        
        Args:
            steps: List of Step objects from planner
            ctx: Context dict (passed to hooks as second arg)
            hooks: Dict mapping event names (e.g., "pre:package") to list of callables
        
        Returns:
            List of StepResult objects (one per step)
        
        Raises:
            StepError: If any step with on_error='abort' fails or pre hook fails
        """
        hooks = hooks or {}
        results = []
        
        for step in steps:
            # Fire pre:kind hooks (error → abort)
            try:
                for hook in hooks.get(f"pre:{step.kind}", []):
                    hook(step, ctx)
            except Exception as e:
                raise StepError(f"pre:{step.kind} hook failed for step '{step.name}': {str(e)}")
            
            # Execute the step
            try:
                result = self._execute_step(step, ctx)
                results.append(result)
            except StepError as e:
                if step.on_error == "abort":
                    raise
                else:  # warn
                    self.logger_fn(f"Step '{step.name}' failed (on_error=warn): {str(e)}")
                    results.append(StepResult(step, success=False, error=str(e), is_warning=True))
                    continue
            
            # Fire post:kind hooks (error → log and continue)
            for hook in hooks.get(f"post:{step.kind}", []):
                try:
                    hook(step, ctx)
                except Exception as e:
                    self.logger_fn(f"post:{step.kind} hook error for step '{step.name}': {str(e)}")
        
        return results
    
    def _execute_step(self, step: Step, ctx: Dict[str, Any]) -> StepResult:
        """Execute a single step by kind and meta.action.
        
        Dispatch table:
        - package: manage_packages(root_path, repos, action, packages, chroot)
        - service: enable_services or disable_services
        - system: kernel-update, initramfs-update, update-packages
        - disk: raise error (not executable yet)
        - unknown: raise error
        
        Args:
            step: Step to execute
            ctx: Context dict (for hook access)
        
        Returns:
            StepResult
        
        Raises:
            StepError: If dispatch fails or kind unknown
        """
        def run_dispatch():
            """Inner function to run dispatch logic in executor."""
            # Dispatch by kind
            if step.kind == "package":
                action = step.meta.get("action")
                if action == "install":
                    fn = self.env.get("manage_packages")
                    if not fn:
                        raise StepError("manage_packages not in env")
                    fn(ctx.get("mount_point", "/"), ctx.get("repos"), "install", [step.name], chroot=ctx.get("use_chroot", False))
                elif action == "remove":
                    fn = self.env.get("manage_packages")
                    if not fn:
                        raise StepError("manage_packages not in env")
                    fn(ctx.get("mount_point", "/"), ctx.get("repos"), "remove", [step.name], chroot=ctx.get("use_chroot", False))
                else:
                    raise StepError(f"Unknown package action: {action}")
            
            elif step.kind == "service":
                action = step.meta.get("action")
                if action == "enable":
                    fn = self.env.get("enable_services")
                    if not fn:
                        raise StepError("enable_services not in env")
                    fn([step.name], mount_point=ctx.get("mount_point", "/"), use_chroot=ctx.get("use_chroot", False))
                elif action == "disable":
                    fn = self.env.get("disable_services")
                    if not fn:
                        raise StepError("disable_services not in env")
                    fn([step.name], mount_point=ctx.get("mount_point", "/"), use_chroot=ctx.get("use_chroot", False))
                else:
                    raise StepError(f"Unknown service action: {action}")
            
            elif step.kind == "system":
                # Named system steps (kernel-update, initramfs-update) dispatch
                # to env callables; the rest run as subprocess or no-op.
                fn = self.env.get(step.name)
                if callable(fn):
                    fn(step.meta.get("kernel"), ctx.get("mount_point", "/"))
                    return StepResult(step, success=True)

                # System steps can be metadata-only (empty program) or subprocess-based
                if step.program == "":
                    # Metadata-only step (no execution needed)
                    return StepResult(step, success=True, stdout="", stderr="")
                
                # Execute via subprocess
                import subprocess
                from kod import common
                
                cmd = " ".join([step.program] + list(step.args))
                
                # If step requires chroot, wrap command with chroot
                if step.chroot:
                    mount_point = ctx.get("mount_point", "/mnt")
                    cmd = f"chroot {mount_point} sh -c '{cmd}'"
                
                # Print command if verbose or debug mode
                if common.use_debug or common.use_verbose:
                    print(f">> {cmd}")
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=step.timeout_s, check=False)
                if result.returncode != 0:
                    raise StepError(f"System step '{step.name}' failed: {result.stderr}")
                return StepResult(step, success=True, stdout=result.stdout, stderr=result.stderr)
            
            elif step.kind == "disk":
                # Disk steps execute via subprocess
                import subprocess
                from kod import common
                
                cmd = " ".join([step.program] + list(step.args))
                
                # If step requires chroot, wrap command with chroot
                if step.chroot:
                    mount_point = ctx.get("mount_point", "/mnt")
                    cmd = f"chroot {mount_point} sh -c '{cmd}'"
                
                # Print command if verbose or debug mode
                if common.use_debug or common.use_verbose:
                    print(f">> {cmd}")
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=step.timeout_s, check=False)
                if result.returncode != 0:
                    raise StepError(f"Disk step '{step.name}' failed: {result.stderr}")
                return StepResult(step, success=True, stdout=result.stdout, stderr=result.stderr)
            
            else:
                raise StepError(f"Unknown step kind: {step.kind}")
            
            return StepResult(step, success=True)
        
        # Wrap dispatch in ThreadPoolExecutor for timeout support
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_dispatch)
                try:
                    return future.result(timeout=step.timeout_s)
                except concurrent.futures.TimeoutError:
                    raise StepError(f"Step '{step.name}' timed out after {step.timeout_s}s")
        except StepError:
            raise
        except Exception as e:
            raise StepError(f"Step '{step.name}' ({step.kind}) failed: {str(e)}")


def execute_steps_lua(steps: List[Step], env: Dict[str, Any], mount_point: str,
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
        uc = ctx_lua.use_chroot

        if kind == "package":
            action = meta.get("action")
            if action not in ("install", "remove"):
                raise StepError(f"Unknown package action: {action}")
            fn = env.get("manage_packages")
            if not fn:
                raise StepError("manage_packages not in env")
            fn(mp, repos, action, [name], chroot=uc)
        elif kind == "service":
            action = meta.get("action")
            fn = env.get("enable_services") if action == "enable" else env.get("disable_services")
            if action not in ("enable", "disable") or not fn:
                raise StepError(f"Unknown service action: {action}")
            fn([name], mount_point=mp, use_chroot=uc)
        elif kind == "system":
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

    module = lua.require("kod.lib.executor")
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
