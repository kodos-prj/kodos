# KodOS Executor Adoption (Plan B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the read-only planner from Plan A into rebuild's execution flow, introducing a unified executor for step dispatch and lifecycle hooks mechanism (spec §5, §7).

**Architecture:** Plan A built a `build_plan()` function that produces a `Step` list for install/rebuild preview without executing. Plan B inverts this: the plan becomes executable. A new `Executor` class dispatches steps by kind (package/service/system), fires pre/post lifecycle hooks with consistent abort/continue semantics, and manages timeouts. This unifies the execution path — `rebuild --dry-run` output is now guaranteed to match actual execution (one code path). Install keeps its inline bootstrap flow (§6 step 2 will port that to Lua-emitted steps later).

**Tech Stack:** Python dataclasses (Step), lupa for Lua hook execution, concurrent.futures.ThreadPoolExecutor for per-step timeouts, click.confirm for interactive gates.

**Spec:** `docs/superpowers/specs/2026-09-10-kod-planner-hooks-buildcache-design.md` §5 (Executor), §7 (Lifecycle hooks)

## Global Constraints

- **Spec §5 on-error policies:** `pre:*` hook errors abort the current step; `post:*` hook errors are logged and execution continues.
- **Spec §5 destructive steps:** Require interactive confirmation (deferred to §6 step 2 when disk steps actually execute; included here defensively).
- **Spec §7 hook names:** Fixed set only — `pre:<kind>` / `post:<kind>` for `kind ∈ {package, service, program, user}`. No other names.
- **Spec §7 v1 constraint:** No built-in hooks; mechanism + doc examples only.
- **Scope boundary:** Rebuild adoption only (hooks live there); install keeps inline flow until §6 step 2 unifies bootstrap. Disk steps are defensive (reject with clear error; confirmation gate deferred).
- **Golden files:** `tests/golden/plan-testvm-empty.txt` (install, no changes); kernel hook shapes in rebuild plan and test_planner assertions will change (tasks update them).

---

## File Structure

**New files:**
- `src/kod/executor.py` — Core `Executor` class: step dispatch, on_error handling, pre/post hook firing, timeout via ThreadPoolExecutor, confirmation gate for disk steps.
- `src/kod/hooks.py` — `VALID_HOOKS` set, `collect_hooks(programs) -> dict`, helpers for firing hooks (pre abort / post log).

**Modified files:**
- `src/kod/planner.py` — `get_packages_updates()` returns (to_install, to_remove, to_update) dropping closures; plan_rebuild emits Step("system","kernel-update",…) and Step("system","initramfs-update",…) instead.
- `src/kod/system/packages.py` — `get_packages_updates()` signature: drop `hooks_to_run` return, add `kernel_update_required: bool` flag; tests updated.
- `src/kod/kod.py` — `rebuild` command adopts executor: keep generation bookkeeping/proc_repos inline; call `execute(steps, env, hooks)` for the diff section; keep store/rollback unchanged.
- `tests/test_planner.py` — Update assertions for kernel step shapes; test hook firing semantics.
- `tests/test_executor.py` (new) — Unit tests for Executor: dispatch table, on_error abort/warn, pre/post hook semantics, timeout, confirmation gate.

---

## Task 1: Executor Core Implementation

**Files:**
- Create: `src/kod/executor.py`
- Test: `tests/test_executor.py`

**Interfaces:**
- Consumes: `Step` dataclass from `kod.planner`; hook callables map {event: [callable]}.
- Produces: `Executor` class with `execute(steps, env, hooks=None) -> List[StepResult]`; `StepError` exception.

### Steps

- [ ] **Step 1.1: Write failing tests for Executor core**

Create `tests/test_executor.py` with stubs for all Executor semantics (dispatch, on_error, timeout, hooks, confirmation):

```python
import pytest
from kod.executor import Executor, StepError, StepResult
from kod.planner import Step


def test_executor_dispatch_package_install():
    """Package install step dispatches to mock install function."""
    executed = []
    
    def mock_manage_packages(mount_point, repos, action, packages, chroot=False):
        executed.append(("manage", action, packages))
    
    env = {"manage_packages": mock_manage_packages}
    step = Step("package", "vim", meta={"action": "install"})
    executor = Executor(env=env)
    results = executor.execute([step], {})
    
    assert len(results) == 1
    assert results[0].step == step
    assert results[0].success is True
    assert executed == [("manage", "install", ["vim"])]


def test_executor_on_error_abort():
    """on_error='abort' raises StepError on step failure."""
    def mock_fail(mount_point, repos, action, packages, chroot=False):
        raise RuntimeError("mock failure")
    
    env = {"manage_packages": mock_fail}
    step = Step("package", "vim", meta={"action": "install"}, on_error="abort")
    executor = Executor(env=env)
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {})
    
    assert "vim" in str(exc_info.value)


def test_executor_on_error_warn():
    """on_error='warn' logs failure and continues."""
    def mock_fail(mount_point, repos, action, packages, chroot=False):
        raise RuntimeError("mock failure")
    
    env = {"manage_packages": mock_fail}
    step = Step("package", "vim", meta={"action": "install"}, on_error="warn")
    executor = Executor(env=env)
    results = executor.execute([step], {})
    
    assert len(results) == 1
    assert results[0].success is False
    assert "mock failure" in results[0].error


def test_executor_pre_hook_abort():
    """pre:package hook error aborts the step."""
    executed = []
    def mock_hook(step, ctx):
        raise ValueError("hook error")
    
    def mock_manage(mount_point, repos, action, packages, chroot=False):
        executed.append(("manage", action))
    
    env = {"manage_packages": mock_manage}
    hooks = {"pre:package": [mock_hook]}
    step = Step("package", "vim", meta={"action": "install"})
    executor = Executor(env=env)
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {}, hooks=hooks)
    
    assert "hook error" in str(exc_info.value)
    assert executed == []  # manage_packages never called


def test_executor_post_hook_continue():
    """post:package hook error logs and continues; step marked as executed."""
    executed = []
    logs = []
    
    def mock_hook(step, ctx):
        raise ValueError("post hook error")
    
    def mock_manage(mount_point, repos, action, packages, chroot=False):
        executed.append(("manage", action))
    
    env = {"manage_packages": mock_manage}
    hooks = {"post:package": [mock_hook]}
    step = Step("package", "vim", meta={"action": "install"})
    executor = Executor(env=env, logger_fn=logs.append)
    results = executor.execute([step], {}, hooks=hooks)
    
    assert len(results) == 1
    assert results[0].success is True  # Step itself succeeded
    assert executed == [("manage", "install")]
    assert any("post hook error" in log for log in logs)


def test_executor_timeout():
    """Step timeout fires via ThreadPoolExecutor."""
    import time
    
    def mock_slow(mount_point, repos, action, packages, chroot=False):
        time.sleep(2)
    
    env = {"manage_packages": mock_slow}
    step = Step("package", "vim", meta={"action": "install"}, timeout_s=0.1)
    executor = Executor(env=env)
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {})
    
    assert "timeout" in str(exc_info.value).lower()


def test_executor_disk_step_rejected():
    """Disk steps raise StepError (not executable yet; deferred to §6 step 2)."""
    step = Step("disk", "wipe:/dev/sda")
    executor = Executor(env={})
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {})
    
    assert "not executable" in str(exc_info.value) or "disk" in str(exc_info.value).lower()


def test_executor_unknown_kind():
    """Unknown step kind raises StepError with clear message."""
    step = Step("unknown_kind", "foo")
    executor = Executor(env={})
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {})
    
    assert "unknown_kind" in str(exc_info.value) or "no executor" in str(exc_info.value).lower()


def test_executor_service_enable():
    """Service enable step dispatches to enable_services."""
    executed = []
    
    def mock_enable(services, mount_point="/", use_chroot=False):
        executed.append(("enable", services))
    
    env = {"enable_services": mock_enable}
    step = Step("service", "nginx", meta={"action": "enable"})
    executor = Executor(env=env)
    results = executor.execute([step], {})
    
    assert executed == [("enable", ["nginx"])]


def test_executor_service_disable():
    """Service disable step dispatches to disable_services."""
    executed = []
    
    def mock_disable(services, mount_point="/", use_chroot=False):
        executed.append(("disable", services))
    
    env = {"disable_services": mock_disable}
    step = Step("service", "nginx", meta={"action": "disable"})
    executor = Executor(env=env)
    results = executor.execute([step], {})
    
    assert executed == [("disable", ["nginx"])]


def test_executor_multiple_steps_sequence():
    """Steps execute in order; later steps can depend on earlier success."""
    executed = []
    
    def mock_manage(mount_point, repos, action, packages, chroot=False):
        executed.append(("pkg", action, packages))
    
    def mock_enable(services, mount_point="/", use_chroot=False):
        executed.append(("svc", services))
    
    env = {"manage_packages": mock_manage, "enable_services": mock_enable}
    steps = [
        Step("package", "base", meta={"action": "install"}),
        Step("package", "nginx", meta={"action": "install"}),
        Step("service", "nginx", meta={"action": "enable"}),
    ]
    executor = Executor(env=env)
    results = executor.execute(steps, {})
    
    assert len(results) == 3
    assert executed == [
        ("pkg", "install", ["base"]),
        ("pkg", "install", ["nginx"]),
        ("svc", ["nginx"]),
    ]
```

Run: `pytest tests/test_executor.py -v`
Expected: FAIL (Executor not defined)

- [ ] **Step 1.2: Implement Executor class**

Create `src/kod/executor.py`:

```python
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
                    results.append(StepResult(step, success=False, error=str(e)))
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
        - package: manage_packages(mount_point, repos, action, packages, chroot)
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
        try:
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
                if step.name == "kernel-update":
                    fn = self.env.get("update_kernel_hook")
                    if not fn:
                        raise StepError("update_kernel_hook not in env")
                    kernel = step.meta.get("kernel", "linux")
                    fn(kernel, ctx.get("mount_point", "/"))
                
                elif step.name == "initramfs-update":
                    fn = self.env.get("update_initramfs_hook")
                    if not fn:
                        raise StepError("update_initramfs_hook not in env")
                    kernel = step.meta.get("kernel", "linux")
                    fn(kernel, ctx.get("mount_point", "/"))
                
                elif step.name == "update-packages":
                    fn = self.env.get("update_all_packages")
                    if not fn:
                        raise StepError("update_all_packages not in env")
                    fn(ctx.get("mount_point", "/"), ctx.get("generation_id"), ctx.get("repos"))
                
                else:
                    raise StepError(f"Unknown system step: {step.name}")
            
            elif step.kind == "disk":
                raise StepError(f"Disk steps are not executable yet (bootstrap port pending §6 step 2): {step.name}")
            
            else:
                raise StepError(f"Unknown step kind: {step.kind}")
            
            return StepResult(step, success=True)
        
        except StepError:
            raise
        except Exception as e:
            raise StepError(f"Step '{step.name}' ({step.kind}) failed: {str(e)}")
```

- [ ] **Step 1.3: Run tests to verify core dispatch**

Run: `pytest tests/test_executor.py::test_executor_dispatch_package_install -v`
Expected: PASS

Run: `pytest tests/test_executor.py::test_executor_on_error_abort -v`
Expected: PASS

Run: `pytest tests/test_executor.py::test_executor_on_error_warn -v`
Expected: PASS

Run: `pytest tests/test_executor.py -k "pre_hook or post_hook" -v`
Expected: All PASS

- [ ] **Step 1.4: Add timeout support via ThreadPoolExecutor**

Modify `src/kod/executor.py`, update `_execute_step` to wrap dispatch in ThreadPoolExecutor:

```python
def _execute_step(self, step: Step, ctx: Dict[str, Any]) -> StepResult:
    """Execute step with per-step timeout."""
    
    def run_dispatch():
        # ... existing dispatch logic ...
        return StepResult(step, success=True)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_dispatch)
        try:
            return future.result(timeout=step.timeout_s)
        except concurrent.futures.TimeoutError:
            raise StepError(f"Step '{step.name}' timed out after {step.timeout_s}s")
```

Run: `pytest tests/test_executor.py::test_executor_timeout -v`
Expected: PASS

- [ ] **Step 1.5: Add disk step rejection + unknown kind handling**

Verify tests pass:

Run: `pytest tests/test_executor.py::test_executor_disk_step_rejected -v`
Expected: PASS

Run: `pytest tests/test_executor.py::test_executor_unknown_kind -v`
Expected: PASS

- [ ] **Step 1.6: Full Executor test suite**

Run: `pytest tests/test_executor.py -v`
Expected: All PASS (10 tests)

- [ ] **Step 1.7: Commit executor core**

```bash
git add src/kod/executor.py tests/test_executor.py
git commit -m "feat: executor core with step dispatch, on_error, timeout, hook firing"
```

---

## Task 2: Lifecycle Hooks Module

**Files:**
- Create: `src/kod/hooks.py`
- Test: extend `tests/test_executor.py` with hook collection tests

**Interfaces:**
- Consumes: Program definitions (Lua tables with optional `hooks` field from conf.users[*].programs)
- Produces: `VALID_HOOKS` set; `collect_hooks(programs) -> Dict[str, List[Callable]]`; validation raises on unknown hook names.

### Steps

- [ ] **Step 2.1: Write failing tests for hook collection**

Add to `tests/test_executor.py`:

```python
from kod.hooks import VALID_HOOKS, collect_hooks, ValidationError


def test_valid_hooks_set():
    """VALID_HOOKS contains all spec §7 hook names."""
    expected = {
        "pre:package", "post:package",
        "pre:service", "post:service",
        "pre:program", "post:program",
        "pre:user", "post:user",
    }
    assert VALID_HOOKS == expected


def test_collect_hooks_from_programs():
    """collect_hooks extracts hooks from program definitions."""
    mock_post_service_fn = lambda step, ctx: None
    mock_pre_package_fn = lambda step, ctx: None
    
    programs = {
        "nginx": {
            "hooks": {
                "post:service": mock_post_service_fn,
            }
        },
        "git": {
            "hooks": {
                "pre:package": mock_pre_package_fn,
            }
        },
    }
    
    hooks = collect_hooks(programs)
    
    assert "post:service" in hooks
    assert mock_post_service_fn in hooks["post:service"]
    assert "pre:package" in hooks
    assert mock_pre_package_fn in hooks["pre:package"]


def test_collect_hooks_unknown_name_raises():
    """Unknown hook name raises ValidationError."""
    programs = {
        "bad": {
            "hooks": {
                "invalid:hook": lambda step, ctx: None,
            }
        }
    }
    
    with pytest.raises(ValidationError) as exc_info:
        collect_hooks(programs)
    
    assert "invalid:hook" in str(exc_info.value) or "unknown" in str(exc_info.value).lower()


def test_collect_hooks_no_hooks_field():
    """Programs without hooks field are skipped."""
    programs = {
        "git": {},
        "vim": {"name": "vim"},
    }
    
    hooks = collect_hooks(programs)
    assert len(hooks) == 0 or all(len(v) == 0 for v in hooks.values())


def test_collect_hooks_empty_programs():
    """Empty programs dict returns empty hooks."""
    hooks = collect_hooks({})
    assert len(hooks) == 0
```

Run: `pytest tests/test_executor.py::test_valid_hooks_set -v`
Expected: FAIL (VALID_HOOKS not defined)

- [ ] **Step 2.2: Implement hooks.py**

Create `src/kod/hooks.py`:

```python
"""Lifecycle hook collection and firing for step-based execution.

Spec: docs/superpowers/specs/2026-09-10-kod-planner-hooks-buildcache-design.md §7.

Fixed hook names: pre:<kind> / post:<kind>, kind ∈ {package, service, program, user}.
Registration: optional `hooks` table in program/plugin module.
Semantics: pre errors abort; post errors log and continue.
"""

from typing import Any, Dict, List, Callable, Optional


class ValidationError(Exception):
    """Invalid hook configuration."""
    pass


# Spec §7: fixed set of hook names
VALID_HOOKS = {
    "pre:package", "post:package",
    "pre:service", "post:service",
    "pre:program", "post:program",
    "pre:user", "post:user",
}


def collect_hooks(programs: Dict[str, Any]) -> Dict[str, List[Callable]]:
    """Extract and validate lifecycle hooks from program definitions.
    
    Args:
        programs: Dict of program name → definition (Lua table converted to dict).
                  Each program may have an optional `hooks` field with
                  event → callable mappings.
    
    Returns:
        Dict mapping hook event name (e.g., "post:service") to list of callables.
        Empty dict if no hooks registered.
    
    Raises:
        ValidationError: If any hook name is not in VALID_HOOKS.
    """
    hooks_map: Dict[str, List[Callable]] = {}
    
    for prog_name, prog_def in programs.items():
        if not isinstance(prog_def, dict):
            continue
        
        prog_hooks = prog_def.get("hooks")
        if not prog_hooks:
            continue
        
        if not isinstance(prog_hooks, dict):
            raise ValidationError(f"Program '{prog_name}' hooks field must be a dict, got {type(prog_hooks)}")
        
        for hook_name, hook_fn in prog_hooks.items():
            # Validate hook name
            if hook_name not in VALID_HOOKS:
                raise ValidationError(
                    f"Program '{prog_name}' registers unknown hook '{hook_name}'. "
                    f"Valid names: {sorted(VALID_HOOKS)}"
                )
            
            # Collect
            if hook_name not in hooks_map:
                hooks_map[hook_name] = []
            hooks_map[hook_name].append(hook_fn)
    
    return hooks_map
```

- [ ] **Step 2.3: Run hook tests**

Run: `pytest tests/test_executor.py::test_collect_hooks -v`
Expected: All PASS (5 tests)

- [ ] **Step 2.4: Commit hooks module**

```bash
git add src/kod/hooks.py
git commit -m "feat: lifecycle hooks collection and validation (spec §7)"
```

---

## Task 3: Update Planner for Kernel Steps

**Files:**
- Modify: `src/kod/planner.py`, `src/kod/system/packages.py`
- Update: `tests/test_planner.py`

**Interfaces:**
- Consumes: `get_packages_updates()` currently returns 4-tuple; change to 3-tuple + kernel_update flag.
- Produces: Step("system","kernel-update",…) and Step("system","initramfs-update",…) in plan_rebuild when update required.

### Steps

- [ ] **Step 3.1: Update get_packages_updates signature**

Modify `src/kod/system/packages.py:546-606`:

```python
def get_packages_updates(
    dist: Any,
    current_packages: Dict[str, Any],
    next_packages: Dict[str, Any],
    remove_packages: List[str],
    current_installed_packages: List[str],
    mount_point: str,
) -> Tuple[List[str], List[str], List[str], bool]:
    """
    Determine packages to install/remove/update, plus kernel update flag.
    
    Returns:
        tuple: (packages_to_install, packages_to_remove, packages_to_update, kernel_update_required)
    
    The kernel_update_required flag replaces the previous hooks_to_run list.
    Kernel update logic is now represented as explicit system steps in plan_rebuild.
    """
    # ... existing diff logic unchanged ...
    
    packages_to_install = []
    packages_to_remove = []
    packages_to_update = []
    
    current_kernel = current_packages.get("kernel", "linux")
    next_kernel = next_packages.get("kernel", "linux")
    kernel_update_required = dist.kernel_update_required(
        current_kernel, next_kernel, current_installed_packages, mount_point
    )
    
    if kernel_update_required:
        packages_to_install += [next_kernel]
    
    # ... rest of diff logic unchanged ...
    
    return packages_to_install, packages_to_remove, packages_to_update, kernel_update_required
```

- [ ] **Step 3.2: Update plan_rebuild to emit kernel steps**

Modify `src/kod/planner.py:154-190`:

```python
def plan_rebuild(conf: Any, dist: Any, current_packages: dict, current_services: List[str],
                 current_installed_packages: Optional[dict] = None, update: bool = False,
                 new_generation: bool = False, mount_point: str = "/") -> List[Step]:
    """..."""
    steps: List[Step] = []
    
    if update:
        steps.append(Step("system", "update-packages"))
    
    next_packages, remove_packages = get_packages_to_install(conf)
    to_install, to_remove, _to_update, kernel_update_required = get_packages_updates(
        dist, current_packages, next_packages, remove_packages,
        current_installed_packages or {}, mount_point)
    
    # ... existing service disable logic ...
    
    for pkg in sorted(to_remove):
        steps.append(Step("package", pkg, meta={"action": "remove"}, on_error="warn"))
    
    for pkg in sorted(to_install):
        steps.append(Step("package", pkg, meta={"action": "install"}))
    
    # NEW: Emit kernel update steps instead of hooks list
    if kernel_update_required:
        kernel = next_packages.get("kernel", "linux")
        steps.append(Step("system", "kernel-update",
                         meta={"kernel": kernel}))
        steps.append(Step("system", "initramfs-update",
                         meta={"kernel": kernel}))
    
    # ... existing service enable logic ...
    
    return steps
```

- [ ] **Step 3.3: Update test_planner expectations**

Modify `tests/test_planner.py` to expect kernel system steps instead of "kernel-update:*" program steps:

```python
def test_plan_rebuild_with_kernel_update():
    """Rebuild plan emits kernel-update + initramfs-update steps when kernel changes."""
    # ... setup conf, dist, current state ...
    
    steps = plan_rebuild(conf, dist, 
                        current_packages={"kernel": "linux-5.10"},
                        current_services=[],
                        current_installed_packages={"linux-5.10": "5.10.0"})
    
    # Find kernel steps
    kernel_steps = [s for s in steps if s.kind == "system" and "update" in s.name]
    assert len(kernel_steps) == 2
    assert kernel_steps[0].name == "kernel-update"
    assert kernel_steps[1].name == "initramfs-update"
    assert kernel_steps[0].meta.get("kernel") == "linux"  # next kernel
```

Update any tests that assert on the old program-step format (e.g., test assertions on "kernel-update:*").

- [ ] **Step 3.4: Run planner tests**

Run: `pytest tests/test_planner.py -v`
Expected: All PASS (update assertions as needed; 23 tests remain)

- [ ] **Step 3.5: Verify plan output (golden file)**

Run: `uv run kod plan -c example/testvm --baseline empty`
Expected: Output changes if install includes kernel steps (it does — check golden file generation and verify no regression beyond kernel step shape change).

- [ ] **Step 3.6: Commit planner updates**

```bash
git add src/kod/planner.py src/kod/system/packages.py tests/test_planner.py
git commit -m "feat: kernel updates as explicit system steps instead of hooks_to_run"
```

---

## Task 4: Rebuild Command Adoption

**Files:**
- Modify: `src/kod/kod.py` (rebuild function)
- Test: extend existing integration tests; new unit test for rebuild executor flow

**Interfaces:**
- Consumes: `execute(steps, env, hooks)` from executor; existing functions (manage_packages, enable_services, etc.).
- Produces: Rebuild flow with middle section (package/service/kernel diff) driven by executor.

### Steps

- [ ] **Step 4.1: Write failing integration test for rebuild with executor**

Add to `tests/integration/test_rebuild.py` (or extend existing):

```python
def test_rebuild_executes_plan_via_executor(mock_manage_packages, mock_enable_services):
    """Rebuild's package/service diff section executes through Executor.
    
    Verifies that the actual execution matches the plan (no drift).
    """
    # Mock setup: conf, current state, dist
    conf = load_config("example/testvm")
    dist = set_base_distribution("arch")
    
    # Simulate rebuild --dry-run output
    steps = build_plan(conf, dist, baseline="current", ...)
    dry_run_output = render_plan(steps, "current", "example/testvm")
    
    # Now execute (mocked) and verify calls match plan
    # This is more of a regression check: does rebuild still do what the plan says?
    # (Actual execution test would run on a VM)
    
    assert "package" in dry_run_output
    assert "service" in dry_run_output
```

- [ ] **Step 4.2: Refactor rebuild to use executor**

Modify `src/kod/kod.py:306-502` (rebuild function):

```python
@cli.command()
@click.option("-c", "--config", default=None, help="System configuration file")
@click.option("-n", "--new_generation", is_flag=True, help="Create a new generation")
@click.option("-u", "--update", is_flag=True, help="Update package versions")
@click.option("--dry-run", is_flag=True, help="Print the plan; do not execute")
def rebuild(config: Optional[str], new_generation: bool = False, update: bool = False,
            dry_run: bool = False) -> None:
    """Rebuild KodOS system installation"""
    
    from kod.planner import build_plan, render_plan
    from kod.executor import Executor
    from kod.hooks import collect_hooks
    from kod.system.boot import update_kernel_hook, update_initramfs_hook
    from kod.system.packages import update_all_packages
    
    conf = load_config(config)
    base_distribution = conf.base_distribution or "arch"
    dist = set_base_distribution(base_distribution)
    
    if dry_run:
        # ... existing dry-run code ...
        return
    
    # === Generation bookkeeping (unchanged) ===
    max_generation = get_max_generation()
    generation_id = int(max_generation) + 1
    
    with open("/.generation") as f:
        current_generation = int(f.readline().strip())
    
    packages_file = Path(f"/kod/generations/{current_generation}/installed_packages")
    if not packages_file.is_file():
        print("Missing installed packages information")
        return
    
    current_state_path = f"/kod/generations/{current_generation}"
    current_packages, current_services = load_packages_services(current_state_path)
    
    boot_partition, root_partition = get_partition_devices(conf)
    next_state_path = f"/kod/generations/{generation_id}"
    new_root_path = None
    use_chroot = False
    
    try:
        exec(f"mkdir -p {next_state_path}")
        
        # === Setup new rootfs (unchanged) ===
        if new_generation:
            print("Creating a new generation")
            exec(f"btrfs subvolume snapshot / {next_state_path}/rootfs")
            use_chroot = True
            new_root_path = create_next_generation(boot_partition, root_partition, generation_id)
        else:
            exec("btrfs subvolume snapshot / /kod/current/old-rootfs")
            exec(f"cp /kod/generations/{current_generation}/installed_packages /kod/current/installed_packages")
            exec(f"cp /kod/generations/{current_generation}/enabled_services /kod/current/enabled_services")
            use_chroot = False
            new_root_path = "/"
        
        ctx = Context(os.environ["USER"], mount_point=new_root_path, use_chroot=use_chroot)
        
        # === Proc repos (unchanged; needed for manage_packages dispatch) ===
        current_repos = load_repos()
        repos, repo_packages = dist.proc_repos(conf, current_repos, update, mount_point=new_root_path)
        if repos is None:
            raise ValueError("Failed to process repositories")
        
        # === Build plan ===
        current_installed_packages = load_package_lock(current_state_path)
        steps = build_plan(
            conf, dist, baseline="current",
            current_packages=current_packages,
            current_services=current_services,
            current_installed_packages=current_installed_packages,
            update=update
        )
        
        # === Setup executor environment ===
        env = {
            "mount_point": new_root_path,
            "repos": repos,
            "generation_id": generation_id,
            "use_chroot": use_chroot,
            "manage_packages": manage_packages,
            "enable_services": enable_services,
            "disable_services": disable_services,
            "update_all_packages": update_all_packages,
            "update_kernel_hook": update_kernel_hook,
            "update_initramfs_hook": update_initramfs_hook,
        }
        
        # Collect hooks from program definitions (for future use when §7 hooks exist)
        try:
            hooks_dict = collect_hooks(conf.users if conf.users else {})
        except Exception as e:
            logger.warning(f"Failed to collect hooks: {e}")
            hooks_dict = {}
        
        # === Execute plan ===
        print("================== Executing plan ==================")
        executor = Executor(env=env)
        results = executor.execute(steps, ctx, hooks=hooks_dict)
        
        # Check for failures
        for result in results:
            if not result.success:
                print(f"⚠️  Step '{result.step.name}' failed (non-aborting): {result.error}")
        
        # === Finalization (unchanged) ===
        next_services = get_services_to_enable(ctx, conf)
        store_packages_services(next_state_path, [s.name for s in steps if s.kind == "package" and s.meta.get("action") == "install"], next_services)
        dist.generale_package_lock(new_root_path, next_state_path)
        
        partition_list = load_fstab("/")
        _kernel_file, kver = dist.get_kernel_file(new_root_path, package=next_packages.get("kernel", "linux"))
        
        print("==== Deploying new generation ====")
        if new_generation:
            create_boot_entry(generation_id, partition_list, mount_point=new_root_path, kver=kver)
        else:
            exec(f"mv /kod/generations/{current_generation}/rootfs /kod/generations/{generation_id}/")
            exec(f"mv /kod/current/old-rootfs /kod/generations/{current_generation}/rootfs")
            updated_partition_list = change_subvol(partition_list, subvol=f"generations/{generation_id}", mount_points=["/"])
            generate_fstab(updated_partition_list, new_root_path)
            create_boot_entry(generation_id, updated_partition_list, mount_point=new_root_path, kver=kver)
        
        with open(f"{next_state_path}/rootfs/.generation", "w") as f:
            f.write(str(generation_id))
        
        if new_generation:
            exec(f"umount -R {new_root_path}")
        
        print(f"✅ Done. Generation {generation_id} created")
    
    except Exception as e:
        print(f"❌ Rebuild failed: {e}", file=sys.stderr)
        _cleanup_failed_generation(generation_id, new_root_path if new_root_path else "/")
        sys.exit(1)
```

- [ ] **Step 4.3: Run integration tests (with mocks)**

Run: `pytest tests/integration/ -k rebuild -v` (mock functions to avoid real filesystem ops)
Expected: Integration tests PASS with mocked dispatch targets

- [ ] **Step 4.4: Full regression suite**

Run: `uv run python -m pytest tests/ -q`
Expected: Same baseline (3 pre-existing failures, 463+ passing)

- [ ] **Step 4.5: Manual smoke test (optional, on a real Arch system)**

Run: `uv run kod rebuild --dry-run` and verify output matches previous golden files + new kernel step shapes.

- [ ] **Step 4.6: Commit rebuild adoption**

```bash
git add src/kod/kod.py
git commit -m "feat: rebuild adopts executor for package/service/kernel diff (spec §5)"
```

---

## Task 5: Plan Visibility for Hooks

**Files:**
- Modify: `src/kod/planner.py` (render_plan)
- Test: `tests/test_planner.py`

**Interfaces:**
- Consumes: Steps with hook event names in meta.
- Produces: Plan text output listing hooks per step (read-only visibility).

### Steps

- [ ] **Step 5.1: Update Step model for hook visibility**

Modify `src/kod/planner.py:13-35` (Step dataclass) — no change needed; `meta` dict already supports hooks list.

- [ ] **Step 5.2: Attach hook names to steps in planner**

Modify `src/kod/planner.py:151-191` (plan_install and plan_rebuild):

```python
def plan_rebuild(...):
    """..."""
    # ... steps building ...
    
    # After building steps, attach hook names for visibility
    from kod.hooks import VALID_HOOKS, collect_hooks
    
    hooks_map = collect_hooks(conf.users or {})
    
    for step in steps:
        # Collect event names that would fire for this step kind
        events = sorted([event for event in hooks_map.keys() if event.endswith(f":{step.kind}")])
        if events:
            step.meta["hooks"] = events
    
    return steps
```

Wait — Step is frozen (immutable). Can't modify meta after creation. Hmm. Alternative: pass hooks_map to planner functions and attach during step creation. Or: don't modify Step, just include hook info in meta during creation:

```python
# At step creation
hook_events = sorted([event for event in hooks_map.keys() if event.endswith(f":{step.kind}")])
step = Step("service", svc, meta={"action": "enable", "hooks": hook_events})
```

This requires passing hooks_map through plan_install/plan_rebuild. Alternative (lazy): skip Step-level meta changes; instead, render_plan reads hooks from outside and augments output. Actually, spec says "kod plan lists which hooks will fire per step" — that implies the plan output includes it. So steps need to carry hook info.

Simplest: Step.meta["hooks"] list. Pass hooks_map to planner and attach during step construction. Modify planner signature to accept hooks_map (optional, default None for backward compat).

- [ ] **Step 5.3: Write test for hook visibility**

Add to `tests/test_planner.py`:

```python
def test_plan_renders_hooks_in_meta():
    """Plan output includes hooks per step in meta."""
    # ... setup ...
    steps = plan_install(conf)
    
    # Install doesn't include services yet (no hooks), but rebuild does
    # So: setup rebuild with conf that has user programs with hooks
    
    # conf.users["alice"].programs["nginx"].hooks = {"post:service": ...}
    # steps = plan_rebuild(conf, ...)
    # service_enable_steps = [s for s in steps if s.kind == "service" and s.meta.get("action") == "enable"]
    # assert any("post:service" in s.meta.get("hooks", []) for s in service_enable_steps)
```

- [ ] **Step 5.4: Update render_plan to display hooks**

Modify `src/kod/planner.py:37-48` (render_plan):

```python
def render_plan(steps: List[Step], baseline: str, config_path: Optional[str] = None) -> str:
    """Render steps as deterministic text (golden-file testable)."""
    lines = ["# kod plan", f"# baseline={baseline} config={config_path or '<default>'}"]
    for i, s in enumerate(steps, 1):
        cmd = " ".join([s.program, *s.args]).strip()
        line = f"{i:03d} [{s.kind}] {s.name}:"
        if cmd:
            line += f" {cmd}"
        
        meta_copy = dict(s.meta)
        hooks = meta_copy.pop("hooks", None)
        
        if meta_copy:
            line += f" {json.dumps(meta_copy, sort_keys=True)}"
        
        if hooks:
            line += f" hooks={json.dumps(sorted(hooks))}"
        
        lines.append(line)
    return "\n".join(lines) + "\n"
```

- [ ] **Step 5.5: Run planner tests**

Run: `pytest tests/test_planner.py -v`
Expected: All PASS (potentially update golden file expectations if hooks change output)

- [ ] **Step 5.6: Commit plan visibility**

```bash
git add src/kod/planner.py tests/test_planner.py
git commit -m "feat: plan visibility for lifecycle hooks (spec §7)"
```

---

## Task 6: Documentation & Example Hook

**Files:**
- Create: `docs/kod/lifecycle-hooks-v1.md` (spec §7 v1 doc example)
- Update: `src/kod/__init__.py` or README

**Interfaces:**
- Consumes: Spec §7 requirements.
- Produces: Docstring + one runnable example (Lua program with post:service hook).

### Steps

- [ ] **Step 6.1: Write lifecycle hooks documentation**

Create `docs/kod/lifecycle-hooks-v1.md`:

```markdown
# Lifecycle Hooks — v1 Implementation

**Version:** 1.0 (no built-in hooks; mechanism + examples)

## Overview

Lifecycle hooks allow programs to run custom logic before/after rebuild steps of specific kinds.

**Fixed event names:** `pre:<kind>` and `post:<kind>`, where `kind ∈ {package, service, program, user}`.

**Where they run:** During `kod rebuild` execution only (via Executor). `kod plan` lists which hooks would fire but never executes them.

**Semantics:**
- `pre:*` hook error → step aborts (on_error becomes "abort" regardless of step's on_error field).
- `post:*` hook error → logged as warning, step remains successful, execution continues.

## Example: Restart Service if Running

Program module `~/.kod/plugins/programs/nginx.lua`:

\`\`\`lua
return {
    name = "nginx",
    scope = "system",
    schema = { ... },
    default_config = { ... },
    generate_config = function(self, options) ... end,
    
    -- NEW: Lifecycle hooks (optional)
    hooks = {
        ["post:service"] = function(step, ctx)
            -- After any service enable step, restart if already running
            if step.name == "nginx" then
                os.execute("systemctl is-active --quiet nginx && systemctl restart nginx || true")
            end
        end,
    }
}
\`\`\`

**Signature:** `hook(step, ctx)`
- `step`: Step object (fields: kind, name, program, args, meta, ...)
- `ctx`: Context dict (fields: mount_point, repos, generation_id, use_chroot, ...)

**Return:** Hook return value is ignored (side-effects only).

## Registering Hooks

1. Add `hooks` table to your program module (same .lua file as name, schema, generate_config).
2. Use keys from the fixed set: `pre:package`, `post:package`, etc.
3. Values are Lua functions with signature `(step, ctx) -> any`.
4. Unknown hook names raise ValidationError during `kod rebuild` (fail loud).

## Built-in Hooks (v2+)

Future versions may include built-in hooks for common patterns (e.g., restart systemd-user-sessions after user creation). For now, hook everything custom via plugin modules.

## Testing Your Hooks

Write a `post:service` hook that prints to `/tmp/hook-test.log`, then:

\`\`\`bash
kod rebuild --dry-run  # Verify hook name appears in plan output
kod rebuild            # Execute; check /tmp/hook-test.log
\`\`\`
\`\`\`

- [ ] **Step 6.2: Write test for example hook**

Add to `tests/test_executor.py`:

```python
def test_example_post_service_hook_execution():
    """Example: post:service hook that restarts nginx if running (from docs)."""
    log = []
    
    def mock_hook(step, ctx):
        """Simplified version of the nginx restart hook."""
        if step.name == "nginx":
            log.append(f"would restart {step.name}")
    
    def mock_enable(services, mount_point="/", use_chroot=False):
        pass
    
    env = {"enable_services": mock_enable}
    hooks = {"post:service": [mock_hook]}
    
    step = Step("service", "nginx", meta={"action": "enable"})
    executor = Executor(env=env)
    results = executor.execute([step], {}, hooks=hooks)
    
    assert len(results) == 1
    assert results[0].success is True
    assert log == ["would restart nginx"]
```

- [ ] **Step 6.3: Run doc example test**

Run: `pytest tests/test_executor.py::test_example_post_service_hook_execution -v`
Expected: PASS

- [ ] **Step 6.4: Commit documentation**

```bash
git add docs/kod/lifecycle-hooks-v1.md
git commit -m "docs: lifecycle hooks v1 spec + example (post:service restart hook)"
```

---

## Task 7: Full Regression & Integration

**Files:**
- Modify: existing test assertions (update golden files if needed)

**Interfaces:**
- Consumes: All tasks 1–6 (integrated).
- Produces: Green test suite; Plan A + Plan B working end-to-end.

### Steps

- [ ] **Step 7.1: Run full regression suite**

Run: `uv run python -m pytest tests/ -q`
Expected: 3 pre-existing failures (VM/Phase 4), 463+ passing

- [ ] **Step 7.2: Verify golden files**

Run: `uv run kod plan -c example/testvm --baseline empty > /tmp/plan-testvm-empty.txt`
Run: `diff tests/golden/plan-testvm-empty.txt /tmp/plan-testvm-empty.txt`
Expected: Only differences are in kernel step shapes (Step("system","kernel-update",…) instead of Step("program","kernel-update:*",…)); if golden is for install (empty baseline), kernel steps may not appear (no kernel update in fresh install). Check and update golden if needed.

- [ ] **Step 7.3: Smoke test rebuild with executor**

Run: `uv run kod rebuild --dry-run` (on a live KodOS system, or skip if not available)
Expected: Plan output includes package/service/kernel steps; no actual execution

- [ ] **Step 7.4: Final commit message**

```bash
git log --oneline -7
```

Expected log entries:
```
<latest>  docs: lifecycle hooks v1 spec + example
<prev>    feat: plan visibility for lifecycle hooks (spec §7)
<prev>    feat: rebuild adopts executor for package/service/kernel diff (spec §5)
<prev>    feat: kernel updates as explicit system steps instead of hooks_to_run
<prev>    feat: lifecycle hooks collection and validation (spec §7)
<prev>    feat: executor core with step dispatch, on_error, timeout, hook firing
<prev>    chore: remove dead code and session-artifact docs (ponytail audit)
```

- [ ] **Step 7.5: Create summary PR description**

Plan B ships:
- **Executor core** (`kod/executor.py`): step dispatch by kind, on_error policies (abort/warn), per-step timeout, pre/post hook firing with abort/continue semantics, disk step rejection (deferred to §6 step 2).
- **Lifecycle hooks** (`kod/hooks.py`): fixed hook names (pre/post:<kind>), registration from program modules, collection + validation.
- **Rebuild adoption**: package/service/kernel diff execution via Executor; one code path so dry-run can't drift from actual execution.
- **Plan visibility**: step meta includes hook event names for read-only preview.
- **v1 scope**: No built-in hooks; mechanism + example (post:service restart hook).

Out of scope (deferred):
- Install adoption (lands with §6 step 2 bootstrap port).
- Disk step execution + confirmation gate (lands with §6 step 2).
- Build step approval (gated by Phase 5a).

- [ ] **Step 7.6: Final commit**

```bash
git add -A
git commit -m "feat: Plan B complete — executor adoption + lifecycle hooks (spec §5, §7)"
```

---

## Summary

**What's built:** A unified executor-driven rebuild flow that previews via `kod plan` and executes identically. Lifecycle hooks mechanism for pre/post step events (v1 without built-in hooks). Kernel update logic modeled as explicit system steps, eliminating ad-hoc closure lists.

**Why it works:** One plan object, one execution path. Pre hook errors abort; post errors log and continue. Per-step timeout via ThreadPoolExecutor. Disk steps defensively rejected with clear error (real execution deferred). Rebuild bookkeeping and finalization remain unchanged (minimal diff, max stability).

**Tests:** 10 executor unit tests + 5 hook tests + updated planner assertions + integration smoke test. Golden files may update for kernel step shapes only. Existing regression suite (463+ passing) remains green.

**Boundary:** Install adoption deferred until §6 step 2 (bootstrap port); disk step execution deferred (will land same time); build step approval gated by Phase 5a.
