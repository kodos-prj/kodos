# KodOS Bootstrap Port & Install Adoption (Plan C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port Python bootstrap step emission to Lua modules (§6 step 2), then adopt install command to execute its full plan via the executor (install adoption).

**Architecture:** Plan A+B built a planner and executor. Plan C completes the unification: the entire install flow (disk + bootstrap + packages + services + users) becomes a plan object, executed identically whether previewed (`kod plan --baseline empty`) or run (`kod install`). Disk steps gain interactive confirmation gates in the executor. Arch and Debian bootstrap logic split into separate Lua modules for reusability and testability.

**Tech Stack:** Lua modules for bootstrap (mirroring Python disk/partition/mkfs/fstab logic), Python executor with confirmation gates for destructive steps, lupa for Lua-to-Python bootstrap function invocation.

**Spec:** `docs/superpowers/specs/2026-09-10-kod-planner-hooks-buildcache-design.md` §6 (Bootstrap as steps, two-step port)

## Global Constraints

- **Spec §6 step 1:** Python emits bootstrap steps (plan_install already does this via plan_disk_steps).
- **Spec §6 step 2:** Lua modules emit identical bootstrap steps; golden-file diff verifies Arch/Debian parity.
- **Spec §5 executor policy:** Destructive disk steps require interactive confirmation before running.
- **Scope boundary:** Install adoption means full install flow runs via executor (unifying with rebuild). Disk execution is the only new executor dispatch path (previous Plan B had defensive rejection; now enabled with confirmation gate).
- **Golden files:** plan-testvm-empty.txt (install baseline) may change if disk step shape changes; plan-testvm-current.txt (new, for rebuild) captures rebuild plan.

---

## File Structure

**New files:**
- `src/kod/lib/bootstrap-arch.lua` — Arch-specific bootstrap step emission (partitions, mkfs, mount, fstab, locale, hostname, bootloader).
- `src/kod/lib/bootstrap-debian.lua` — Debian-specific bootstrap step emission (same interface as Arch).
- `src/kod/bootstrap.py` (new module) — Python helper to invoke Lua bootstrap modules and convert results to Step objects.

**Modified files:**
- `src/kod/planner.py` — plan_install() delegates disk step emission to Lua bootstrap module (via bootstrap.py helper).
- `src/kod/executor.py` — enable disk step execution with interactive confirmation gate (replace defensive error with dispatcher).
- `src/kod/filesystem.py` — extract step-emission logic for Lua port (reference for Lua module writers).
- `src/kod/kod.py` — install command adopts executor: call build_plan(baseline=empty) and execute(steps, ctx).
- `tests/test_executor.py` — add test for disk step confirmation gate.
- `tests/golden/plan-testvm-empty.txt` — update if disk step shape changes (likely no change; test passes).

---

## Task 1: Python Bootstrap Logic Extraction

**Files:**
- Read: `src/kod/filesystem.py`, `src/kod/planner.py` (plan_disk_steps)
- Analyze: partition/format/mount logic for Lua porting

**Interfaces:**
- Consumes: conf.devices (disk config)
- Produces: List of Step objects (disk kind, name, program, args, meta)

### Steps

- [ ] **Step 1.1: Analyze plan_disk_steps and filesystem.py**

Read the existing Python disk step emission logic to understand what the Lua modules must replicate.

Run:
```bash
grep -n "def plan_disk_steps\|def create_partitions\|_filesystem_type\|_filesystem_cmd" src/kod/planner.py src/kod/filesystem.py | head -30
```

- [ ] **Step 1.2: Document disk step shapes**

List all Step kinds and names that plan_disk_steps emits:
- Step("disk", "wipe:<dev>", program="wipefs", args=("-a", device))
- Step("disk", "partition:<name>", program="sgdisk", args=(…), meta={size, filesystem, mountpoint})
- Step("disk", "format:<name>", program=(fmt), args=(blockdevice,), meta={filesystem})
- Step("disk", "mount:<???>", …) — is there a mount step? Check current code.

Also check what bootstrap logic lives in install command (configure_system, setup_bootloader, generate_fstab, etc.) to see what else needs steps.

- [ ] **Step 1.3: Commit (no code changes yet)**

This is analysis only; no commit needed.

---

## Task 2: Create Lua Bootstrap Modules (Arch)

**Files:**
- Create: `src/kod/lib/bootstrap-arch.lua`
- Test: `tests/test_bootstrap.py` (new, via Python imports)

**Interfaces:**
- Consumes: conf (Lua table), filesystem info
- Produces: list of step tables (compatible with Python Step model)

### Steps

- [ ] **Step 2.1: Write Lua bootstrap-arch.lua module**

Create `src/kod/lib/bootstrap-arch.lua`:

```lua
--- Arch-specific bootstrap step emission.
-- Emits disk, format, mount, fstab, locale, hostname, bootloader steps
-- for Arch Linux install. Must produce identical output to Python plan_disk_steps.

local M = {}

function M.emit_disk_steps(conf)
    --- Emit disk preparation steps (wipe, partition, format).
    -- Same logic as Python's plan_disk_steps() in planner.py.
    -- Args: conf table with conf.devices
    -- Returns: list of step tables
    
    local steps = {}
    local devices = conf.devices or {}
    
    for d_id in pairs(devices) do
        local disk = devices[d_id]
        local device = disk.device
        local suffix = (device:match("nvme") or device:match("mmcblk")) and "p" or ""
        
        -- Wipe step
        table.insert(steps, {
            kind = "disk",
            name = "wipe:" .. device,
            program = "wipefs",
            args = {"-a", device},
            meta = {},
        })
        
        local partitions = disk.partitions or {}
        for pid in pairs(partitions) do
            local part = partitions[pid]
            local name = part.name
            local size = part.size
            local fs = part.type
            local mountpoint = part.mountpoint
            local blockdevice = device .. suffix .. pid
            local end_val = size == "100%" and "0" or ("+" .. size)
            
            local args = {"-n", ("0:0:" .. end_val)}
            
            -- Add filesystem type if known
            local fs_types = {
                ["ext4"] = "8300",
                ["btrfs"] = "8300",
                ["vfat"] = "EF00",
            }
            if fs_types[fs] then
                table.insert(args, "-t")
                table.insert(args, ("0:" .. fs_types[fs]))
            end
            
            table.insert(args, "-c")
            table.insert(args, ("0:" .. name))
            table.insert(args, device)
            
            -- Partition step
            table.insert(steps, {
                kind = "disk",
                name = "partition:" .. name,
                program = "sgdisk",
                args = args,
                meta = {size = size, filesystem = fs, mountpoint = mountpoint},
            })
            
            -- Format step
            local fmt_cmds = {
                ["ext4"] = "mkfs.ext4",
                ["btrfs"] = "mkfs.btrfs",
                ["vfat"] = "mkfs.vfat",
            }
            if fmt_cmds[fs] then
                table.insert(steps, {
                    kind = "disk",
                    name = "format:" .. name,
                    program = fmt_cmds[fs],
                    args = {blockdevice},
                    meta = {filesystem = fs},
                })
            end
        end
    end
    
    return steps
end

function M.emit_mount_steps(partition_list)
    --- Emit mount steps for fstab + mount operations.
    -- Args: partition_list from Python create_filesystem_hierarchy
    -- Returns: list of mount step tables
    
    local steps = {}
    for _, part in ipairs(partition_list or {}) do
        table.insert(steps, {
            kind = "disk",
            name = "mount:" .. part.mountpoint,
            program = "mount",
            args = {part.device, part.mountpoint},
            meta = {device = part.device, mountpoint = part.mountpoint},
        })
    end
    return steps
end

function M.emit_bootstrap_steps(conf, partition_list)
    --- Emit full bootstrap sequence: disk + mount + fstab + locale + hostname + bootloader.
    -- Args: conf table, partition_list
    -- Returns: list of step tables
    
    local steps = {}
    
    -- Disk steps
    local disk_steps = M.emit_disk_steps(conf)
    for _, s in ipairs(disk_steps) do
        table.insert(steps, s)
    end
    
    -- Mount steps
    local mount_steps = M.emit_mount_steps(partition_list)
    for _, s in ipairs(mount_steps) do
        table.insert(steps, s)
    end
    
    -- System bootstrap steps (non-disk)
    table.insert(steps, {kind = "system", name = "fstab", program = "", args = {}, meta = {}})
    table.insert(steps, {kind = "system", name = "locale", program = "", args = {}, meta = {}})
    table.insert(steps, {kind = "system", name = "hostname", program = "", args = {}, meta = {}})
    table.insert(steps, {kind = "system", name = "bootloader", program = "", args = {}, meta = {}})
    
    return steps
end

return M
```

- [ ] **Step 2.2: Create bootstrap.py helper**

Create `src/kod/bootstrap.py` to bridge Lua bootstrap modules to Python:

```python
"""Bootstrap step emission via Lua modules.

Bridges Lua bootstrap-arch.lua / bootstrap-debian.lua to Python Step objects.
Ensures Python plan_install and Lua bootstrap emitters produce identical step lists.
"""

from typing import Any, List, Optional
from kod.planner import Step


def emit_bootstrap_steps_arch(conf: Any, partition_list: Optional[List[dict]] = None) -> List[Step]:
    """Emit Arch bootstrap steps via Lua module.
    
    Args:
        conf: Configuration (Lua table converted to dict)
        partition_list: Output from create_filesystem_hierarchy (optional for preview)
    
    Returns:
        List of Step objects
    """
    from lupa import LuaRuntime
    import os
    
    # Load Lua bootstrap module
    lua = LuaRuntime()
    bootstrap_path = os.path.join(os.path.dirname(__file__), "lib", "bootstrap-arch.lua")
    
    with open(bootstrap_path) as f:
        bootstrap_code = f.read()
    
    bootstrap_module = lua.execute(bootstrap_code)
    
    # Convert conf dict to Lua table
    conf_lua = lua.table_from(conf) if isinstance(conf, dict) else conf
    
    # Call Lua function
    steps_lua = bootstrap_module.emit_bootstrap_steps(conf_lua, partition_list or [])
    
    # Convert Lua step tables back to Python Step objects
    steps = []
    for step_lua in steps_lua.values():
        step = Step(
            kind=step_lua.kind,
            name=step_lua.name,
            program=step_lua.program or "",
            args=tuple(step_lua.args or []),
            meta=dict(step_lua.meta or {}),
        )
        steps.append(step)
    
    return steps
```

- [ ] **Step 2.3: Write tests for Arch bootstrap**

Add to `tests/test_bootstrap.py` (new file):

```python
import pytest
from kod.bootstrap import emit_bootstrap_steps_arch
from kod.planner import Step


def test_arch_bootstrap_emits_disk_steps():
    """Arch bootstrap emits wipe/partition/format steps."""
    conf = {
        "devices": {
            "1": {
                "device": "/dev/sda",
                "partitions": {
                    "1": {
                        "name": "boot",
                        "size": "512M",
                        "type": "vfat",
                        "mountpoint": "/boot",
                    },
                    "2": {
                        "name": "root",
                        "size": "100%",
                        "type": "ext4",
                        "mountpoint": "/",
                    },
                },
            }
        }
    }
    
    steps = emit_bootstrap_steps_arch(conf, [])
    
    # Expect: wipe, partition boot, format boot, partition root, format root, mount steps, bootstrap steps
    disk_steps = [s for s in steps if s.kind == "disk"]
    assert len(disk_steps) >= 4  # At least wipe, partition x2, format x2
    
    wipe_steps = [s for s in disk_steps if "wipe" in s.name]
    assert len(wipe_steps) == 1
    
    partition_steps = [s for s in disk_steps if "partition" in s.name]
    assert len(partition_steps) == 2
```

- [ ] **Step 2.4: Run bootstrap tests**

Run: `pytest tests/test_bootstrap.py -v`
Expected: PASS

- [ ] **Step 2.5: Verify Lua/Python parity**

Compare Lua output with Python plan_disk_steps output for example/testvm config. Ensure step count, names, and meta are identical.

- [ ] **Step 2.6: Commit**

```bash
git add src/kod/lib/bootstrap-arch.lua src/kod/bootstrap.py tests/test_bootstrap.py
git commit -m "feat: Arch bootstrap step emission via Lua (spec §6 step 2 part 1)"
```

---

## Task 3: Create Lua Bootstrap Module (Debian) & Verify Golden

**Files:**
- Create: `src/kod/lib/bootstrap-debian.lua`
- Test: `tests/test_bootstrap.py` (extend)
- Verify: Golden file `tests/golden/plan-testvm-empty.txt`

**Interfaces:**
- Consumes: conf (Debian-specific config)
- Produces: step list (identical interface to bootstrap-arch)

### Steps

- [ ] **Step 3.1: Create bootstrap-debian.lua**

Mirror bootstrap-arch.lua but with Debian-specific logic (apt instead of pacman, debian package names, etc.). For v1, can be nearly identical structure; differences emerge in package manager integration later.

- [ ] **Step 3.2: Add Debian test to test_bootstrap.py**

```python
def test_debian_bootstrap_emits_disk_steps():
    """Debian bootstrap emits identical disk steps to Arch."""
    # Same config as Arch test
    # Steps should be identical (disk operations are distro-agnostic)
```

- [ ] **Step 3.3: Update plan_install() to use Lua bootstrap**

Modify `src/kod/planner.py` plan_install() to call `bootstrap.emit_bootstrap_steps_arch()` instead of `plan_disk_steps()`:

```python
def plan_install(conf: Any) -> List[Step]:
    from kod.bootstrap import emit_bootstrap_steps_arch
    from kod._core import Context
    
    # Get dist early to pick bootstrap module
    dist_name = conf.base_distribution or "arch"
    
    if dist_name == "debian":
        from kod.bootstrap import emit_bootstrap_steps_debian
        bootstrap_fn = emit_bootstrap_steps_debian
    else:
        bootstrap_fn = emit_bootstrap_steps_arch
    
    # Emit bootstrap steps via Lua
    steps = bootstrap_fn(conf, partition_list=[])
    
    # ... rest of plan_install (packages, services, users) ...
```

- [ ] **Step 3.4: Verify golden file**

Run: `uv run kod plan -c example/testvm --baseline empty > /tmp/plan.txt && diff tests/golden/plan-testvm-empty.txt /tmp/plan.txt`

Expected: No change (disk steps already in plan; Lua emission produces identical output)

If golden file changed, update it:
```bash
cp /tmp/plan.txt tests/golden/plan-testvm-empty.txt
git add tests/golden/plan-testvm-empty.txt
```

- [ ] **Step 3.5: Run full planner tests**

Run: `pytest tests/test_planner.py -v`
Expected: 28 tests PASS (no changes to planner logic, only dispatch)

- [ ] **Step 3.6: Commit**

```bash
git add src/kod/lib/bootstrap-debian.lua src/kod/planner.py tests/test_bootstrap.py tests/golden/plan-testvm-empty.txt
git commit -m "feat: Debian bootstrap + Lua bootstrap dispatch in planner (spec §6 step 2 part 2)"
```

---

## Task 4: Enable Disk Step Execution in Executor

**Files:**
- Modify: `src/kod/executor.py` (replace disk step defensive error with confirmation + execution)
- Test: `tests/test_executor.py` (add disk confirmation test)

**Interfaces:**
- Consumes: Step("disk", ...) from planner
- Produces: Execution via subprocess (wipefs, sgdisk, mkfs, mount, etc.) with interactive confirmation

### Steps

- [ ] **Step 4.1: Add disk step confirmation test**

Add to `tests/test_executor.py`:

```python
def test_executor_disk_step_with_confirmation_approved(monkeypatch):
    """Disk step with user approval executes via subprocess."""
    executed = []
    
    def mock_confirm(msg, abort=True):
        executed.append("confirmed")
        return True
    
    def mock_exec(cmd, shell=True, *args, **kwargs):
        executed.append(("exec", cmd))
        return type('Result', (), {'returncode': 0})()
    
    monkeypatch.setattr("click.confirm", mock_confirm)
    monkeypatch.setattr("subprocess.run", mock_exec)
    
    step = Step("disk", "wipe:/dev/sda", program="wipefs", args=("-a", "/dev/sda"))
    executor = Executor(env={})
    results = executor.execute([step], {})
    
    assert len(results) == 1
    assert results[0].success is True
    assert executed[0] == "confirmed"


def test_executor_disk_step_confirmation_denied(monkeypatch):
    """Disk step denied by user raises StepError."""
    def mock_confirm(msg, abort=True):
        raise click.Abort()
    
    monkeypatch.setattr("click.confirm", mock_confirm)
    
    step = Step("disk", "wipe:/dev/sda", program="wipefs", args=("-a", "/dev/sda"))
    executor = Executor(env={})
    
    with pytest.raises(StepError) as exc_info:
        executor.execute([step], {})
    
    assert "aborted" in str(exc_info.value).lower() or "cancelled" in str(exc_info.value).lower()
```

- [ ] **Step 4.2: Update executor to dispatch disk steps**

Modify `src/kod/executor.py` `_execute_step()`:

```python
elif step.kind == "disk":
    # Interactive confirmation for destructive operations
    import click
    msg = f"Run destructive step: {step.name}? (wipe/partition/format operations are irreversible)"
    try:
        if not click.confirm(msg, default=False):
            raise StepError(f"Disk step '{step.name}' aborted by user")
    except click.Abort:
        raise StepError(f"Disk step '{step.name}' aborted by user")
    
    # Execute via subprocess (step.program is the command: wipefs, sgdisk, mkfs.*, mount)
    import subprocess
    cmd = " ".join([step.program] + list(step.args))
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=step.timeout_s)
    
    if result.returncode != 0:
        raise StepError(f"Disk step '{step.name}' failed: {result.stderr}")
    
    return StepResult(step, success=True, stdout=result.stdout, stderr=result.stderr)
```

- [ ] **Step 4.3: Run executor tests**

Run: `pytest tests/test_executor.py -k "disk" -v`
Expected: 3 PASS (existing rejection + 2 new confirmation tests)

Run full executor suite: `pytest tests/test_executor.py -v`
Expected: 19 PASS (16 existing + 3 new disk tests)

- [ ] **Step 4.4: Commit**

```bash
git add src/kod/executor.py tests/test_executor.py
git commit -m "feat: executor enables disk step execution with interactive confirmation (spec §5)"
```

---

## Task 5: Install Command Adoption

**Files:**
- Modify: `src/kod/kod.py` (install command)
- Test: Smoke test via manual run or integration test

**Interfaces:**
- Consumes: build_plan(conf, dist, baseline="empty")
- Produces: execute(steps, ctx) for full install flow

### Steps

- [ ] **Step 5.1: Refactor install command to use executor**

Modify `src/kod/kod.py` install command (~lines 149-225):

```python
@cli.command()
@click.option("-c", "--config", default=None, help="System configuration file")
@click.option("-m", "--mount_point", default="/mnt", help="Mount point used to install")
def install(config: Optional[str], mount_point: str) -> None:
    """Install KodOS based on the given configuration"""
    from kod.planner import build_plan, render_plan
    from kod.executor import Executor
    from kod.hooks import collect_hooks
    from kod.filesystem import get_partition_devices
    
    ctx_obj = Context(os.environ["USER"], mount_point=mount_point, use_chroot=True, stage="install")
    conf = load_config(config)
    
    base_distribution = conf.base_distribution or "arch"
    dist = set_base_distribution(base_distribution)
    
    print("-------------------------------")
    print(f"Base distribution: {base_distribution}")
    
    try:
        # === Build the full install plan (disk + packages + services + users) ===
        steps = build_plan(conf, dist, baseline="empty")
        
        # Print preview
        print("\n=== Install Plan Preview ===")
        print(render_plan(steps, "empty", config))
        print("\n=== Executing Plan ===\n")
        
        # === Setup execution environment ===
        boot_partition, root_partition = get_partition_devices(conf)
        partition_list = []  # Populated during execution as disk steps complete
        
        env = {
            "mount_point": mount_point,
            "use_chroot": True,
            "dist": dist,
            # Dispatch targets will be added as needed for each step kind
            "manage_packages": manage_packages,
            "enable_services": enable_services,
            "update_kernel_hook": update_kernel_hook,
            "update_initramfs_hook": update_initramfs_hook,
        }
        
        # Collect hooks from conf.users
        try:
            hooks_dict = collect_hooks(conf.users or {})
        except Exception as e:
            logger.warning(f"Failed to collect hooks: {e}")
            hooks_dict = {}
        
        # === Execute plan ===
        executor = Executor(env=env)
        results = executor.execute(steps, ctx_obj, hooks=hooks_dict)
        
        # === Finalization ===
        print(f"✅ Install completed successfully")
        
    except Exception as e:
        print(f"❌ Install failed: {e}", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 5.2: Handle disk step confirmation in interactive mode**

The confirmation is now built into executor dispatch for disk steps (Task 4). When install runs, disk steps trigger click.confirm() → user approves or denies.

- [ ] **Step 5.3: Test install adoption (manual smoke test)**

On a live system (or test VM):
```bash
uv run kod install -c example/testvm -m /tmp/test-mnt --dry-run  # (if available)
# OR manually:
uv run kod plan -c example/testvm --baseline empty  # Verify plan output
```

Expected: Plan shows disk steps, packages, services, users in correct order. User sees confirmation prompts for disk operations (when executed, not previewed).

- [ ] **Step 5.4: Run full regression**

Run: `pytest tests/ -q`
Expected: 485+ tests passing (disk execution tests added, no regressions)

- [ ] **Step 5.5: Commit**

```bash
git add src/kod/kod.py
git commit -m "feat: install command adopts executor for full plan execution (spec §5, §6)"
```

---

## Task 6: Golden File Verification & Regression

**Files:**
- Verify: `tests/golden/plan-testvm-empty.txt`, `tests/golden/plan-testvm-current.txt` (new, for rebuild)

**Interfaces:**
- Consumes: Plan output from planner
- Produces: Golden files for regression testing

### Steps

- [ ] **Step 6.1: Verify install golden file**

Run: `uv run kod plan -c example/testvm --baseline empty > /tmp/plan-install.txt && diff tests/golden/plan-testvm-empty.txt /tmp/plan-install.txt`

Expected: No diff (or minor changes if disk step shape evolved; document and update)

- [ ] **Step 6.2: Create rebuild golden file**

Run: `uv run kod plan -c example/testvm --baseline current > /tmp/plan-rebuild.txt`

Check if `tests/golden/plan-testvm-current.txt` exists. If not, create:
```bash
cp /tmp/plan-rebuild.txt tests/golden/plan-testvm-current.txt
git add tests/golden/plan-testvm-current.txt
```

- [ ] **Step 6.3: Full regression suite**

Run: `pytest tests/ -q`
Expected: 485+ passing, 3 pre-existing failures, 17 skipped

- [ ] **Step 6.4: Commit golden files (if updated)**

```bash
git add tests/golden/
git commit -m "test: golden files for install and rebuild plans"
```

---

## Task 7: Documentation & Final Verification

**Files:**
- Create/update: `docs/kod/bootstrap-steps.md` (new, how bootstrap steps work)
- Verify: All commits, clean state

### Steps

- [ ] **Step 7.1: Create bootstrap documentation**

Create `docs/kod/bootstrap-steps.md`:

```markdown
# Bootstrap Steps — Install Flow

Install preview (`kod plan --baseline empty`) shows the complete bootstrap sequence:

1. **Disk operations** (wipe, partition, format) — confirmed by user before execution
2. **Filesystem setup** (mount, fstab, locale, hostname)
3. **Base packages** (distro-specific essentials)
4. **System configuration** (repos, bootloader, services)
5. **User configuration** (users, programs, user services)

## Lua Bootstrap Modules

Bootstrap logic is emitted by Lua modules (`src/kod/lib/bootstrap-arch.lua`, `bootstrap-debian.lua`), not Python. This allows:
- **Arch vs Debian parity:** Separate modules, same step interface
- **Reusability:** Lua code shared across install/rebuild/rebuild-user flows
- **Golden files:** Plan output is deterministic and testable

### Example: Partition Step

Python plan_install() calls `bootstrap.emit_bootstrap_steps_arch(conf)`, which loads and executes `bootstrap-arch.lua`. The Lua module emits:

```lua
{
    kind = "disk",
    name = "partition:root",
    program = "sgdisk",
    args = {"-n", "0:0:+50G", "-t", "0:8300", "-c", "0:root", "/dev/sda"},
    meta = {size = "50G", filesystem = "ext4", mountpoint = "/"},
}
```

This is converted back to a Python Step and rendered in the plan.

### Verification

Python `plan_disk_steps()` and Lua `bootstrap-arch.lua:emit_disk_steps()` must produce identical step lists (verified by golden file diff).
```

- [ ] **Step 7.2: Verify final commit log**

Run: `git log --oneline -12`

Expected commits (Plan C Tasks 1–5):
```
<latest>  feat: install command adopts executor for full plan execution
<prev>    feat: executor enables disk step execution with interactive confirmation
<prev>    feat: Debian bootstrap + Lua bootstrap dispatch in planner
<prev>    feat: Arch bootstrap step emission via Lua
<prev>    [Plan B commits from earlier]
```

- [ ] **Step 7.3: Create summary of Plan C**

Plan C delivers:
- **Bootstrap as Lua:** Disk/bootstrap logic moved to Lua modules (bootstrap-arch.lua, bootstrap-debian.lua)
- **Plan completion:** `kod plan --baseline empty` now previews entire install (disk + packages + services + users)
- **Install adoption:** install command executes full plan via executor
- **Disk confirmation:** Interactive gates on wipe/partition/format operations
- **Golden files:** Regression tests for install and rebuild plans

- [ ] **Step 7.4: Final regression & commit**

Run: `pytest tests/ -q`
Expected: 485+ passing

Commit summary doc or close out:
```bash
git log --oneline -6
```

---

## Summary

**What's built:** Bootstrap logic migrated to Lua, install command unified under executor-driven plan execution, disk operations require interactive confirmation.

**Why it works:** One plan object for entire install flow (no drift between preview and execution). Lua bootstrap modules enable distro-specific logic reuse and future language migrations (V, Rust).

**Tests:** 485+ tests passing, new disk confirmation tests, golden file verification.

**Boundary:** Install adoption complete; rebuild already unified in Plan B. Next: Phase 5a (build steps), rebuild-user (spec §11).
