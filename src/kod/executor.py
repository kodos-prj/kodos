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
