# Plan A: `kod plan` Read-Only Preview — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-09-10-kod-planner-hooks-buildcache-design.md` (§3 step model, §4 planner, §9 CLI)
**Date:** 2026-09-10
**Status:** Ready for execution

## Goal

Ship `kod plan -c <config> [--baseline empty|current]` and `kod rebuild --dry-run`: a read-only preview of every action install/rebuild would take, built from the *same* state functions the real flows use. **Zero changes to the install/rebuild execution paths** — this plan adds one new module, one new CLI command, one flag, and tests.

## Architecture

- New module `src/kod/planner.py`: `Step` dataclass, `plan_disk_steps`, `plan_install`, `plan_rebuild`, `build_plan`, `render_plan`. Pure assembly over existing functions; executes nothing.
- `src/kod/kod.py`: new `plan` command + `_load_current_state()` helper + `--dry-run` flag on `rebuild` (early return before any side effect).

## Step model (spec §3)

```
kind:    disk | package | service | program | user | system | build
name:    str
program: str          # executable/command; "" for phase-marker steps
args:    [str]        # argument vector, no shell interpretation
chroot:  bool         (default False — preview only; executor concern)
timeout_s: int        (default 300)
on_error: abort | warn (default abort)
meta:    {}           # kind-specific payload
```

Notes vs spec:
- Spec §3 lists kinds `package|service|program|user|build`. This plan adds **`disk`** (bootstrap ops, spec §6 — the spec's kind list is silent on them; disk steps are required for `--baseline empty` to preview disk operations) and **`system`** (one-off install phases: base-packages, repos, configure-system, bootloader, kod-user, update-packages). `build` is accepted by the model but never emitted here (Phase 5a prerequisite, Plan B).
- Step order = execution order of the corresponding flow (`install`: kod.py:180-224; `rebuild`: kod.py:365-391).

## Global constraints

1. **Determinism** (spec §3: golden-file testable): every list derived from a Python `set` is `sorted()` before step emission; `render_plan` serializes `meta` with `json.dumps(meta, sort_keys=True)`.
2. **No execution**: planner calls only read-only functions. Specifically it must NOT call `proc_repos` (writes `/var/kod/repos.json`, runs chroot commands), `create_partitions`/`create_filesystem_hierarchy` (run `wipefs`/`mkfs`), or any `exec*`.
3. **`/proc/cpuinfo`**: `get_packages_to_install` → `kod.arch.get_base_packages` reads `/proc/cpuinfo` (Linux-only, machine-dependent). All tests that reach it patch `kod.system.packages.get_base_packages` with a fixed dict. Real CLI runs on the Linux target only — no guard needed.
4. **Test fixtures are real LuaTables** (via `lupa.LuaRuntime().table_from(...)`), matching production conf shape; missing sections behave as nil → `None`, exactly like lupa tables in prod.
5. Existing suite stays green (spec §10): full `pytest` run at the end of every task is cheap enough to skip per-task; run it once at Task 9 and after any unexpected failure.

## Files

- Create: `src/kod/planner.py`
- Modify: `src/kod/kod.py` (add `_load_current_state`, `plan` command, `--dry-run` on `rebuild`)
- Create: `tests/test_planner.py`
- Create: `tests/golden/plan-testvm-empty.txt` (Task 8)

---

## Task 1: Step model + render_plan

**Files:** Create `src/kod/planner.py`; create `tests/test_planner.py`

**Test (failing first):**

```python
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
```

**Implementation (in `src/kod/planner.py`):**

```python
"""Read-only execution plan builder for KodOS install/rebuild.

Builds a flat, ordered list of Steps describing what install or rebuild would
do, without executing anything. Consumes the same state functions the real
flows use so preview output matches actual behavior (spec: planner section).
"""

import json
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass(frozen=True)
class Step:
    kind: str  # disk | package | service | program | user | system | build
    name: str
    program: str = ""
    args: tuple = ()
    chroot: bool = False
    timeout_s: int = 300
    on_error: str = "abort"  # abort | warn
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "name": self.name,
            "program": self.program,
            "args": list(self.args),
            "chroot": self.chroot,
            "timeout_s": self.timeout_s,
            "on_error": self.on_error,
            "meta": self.meta,
        }


def render_plan(steps: List[Step], baseline: str, config_path: Optional[str] = None) -> str:
    """Render steps as deterministic text (golden-file testable)."""
    lines = ["# kod plan", f"# baseline={baseline} config={config_path or '<default>'}"]
    for i, s in enumerate(steps, 1):
        cmd = " ".join([s.program, *s.args]).strip()
        line = f"{i:03d} [{s.kind}] {s.name}:"
        if cmd:
            line += f" {cmd}"
        if s.meta:
            line += f" {json.dumps(s.meta, sort_keys=True)}"
        lines.append(line)
    return "\n".join(lines) + "\n"
```

**Verify:** `uv run pytest tests/test_planner.py -q` → 4 passed.
**Commit:** `feat: step model and deterministic plan rendering`

---

## Task 2: Disk bootstrap steps (read-only emitter)

Mirrors the command sequence of `create_disk_partitions` (src/kod/filesystem.py:232-324) without executing it. Same suffix rule as `get_partition_devices` (filesystem.py:350-351), same `end` computation (line 285), same `_filesystem_type`/`_filesystem_cmd` tables (lines 13-38).

**Files:** Modify `src/kod/planner.py`; modify `tests/test_planner.py`

**Test (failing first):**

```python
class TestDiskSteps:
    def test_wipe_partition_format_sequence(self):
        from kod.planner import plan_disk_steps

        conf = make_conf(devices={
            "disk0": {"device": "/dev/vda", "partitions": {
                "1": {"name": "boot", "size": "512M", "type": "esp", "mountpoint": "/boot"},
                "2": {"name": "root", "size": "100%", "type": "btrfs", "mountpoint": "/"},
            }},
        })
        steps = plan_disk_steps(conf)
        assert [(s.kind, s.name) for s in steps] == [
            ("disk", "wipe:/dev/vda"),
            ("disk", "partition:boot"),
            ("disk", "format:boot"),
            ("disk", "partition:root"),
            ("disk", "format:root"),
        ]
        assert steps[0].args == ("-a", "/dev/vda")
        # 100% size -> end=0, esp type ef00 (filesystem.py:285-289)
        assert steps[3].args == ("-n", "0:0:0", "-t", "0:8300", "-c", "0:root", "/dev/vda")
        assert steps[1].args == ("-n", "0:0:+512M", "-t", "0:ef00", "-c", "0:boot", "/dev/vda")
        assert steps[4].program == "mkfs.btrfs -f"
        assert steps[4].args == ("/dev/vda2",)
        assert steps[3].meta == {"size": "100%", "filesystem": "btrfs", "mountpoint": "/"}

    def test_nvme_device_suffix(self):
        from kod.planner import plan_disk_steps

        conf = make_conf(devices={
            "disk0": {"device": "/dev/nvme0n1", "partitions": {
                "1": {"name": "root", "size": "100%", "type": "noformat", "mountpoint": "/"},
            }},
        })
        steps = plan_disk_steps(conf)
        # nvme -> 'p' suffix (filesystem.py:350); noformat -> no format step, no -t flag
        assert steps[1].args == ("-n", "0:0:0", "-c", "0:root", "/dev/nvme0n1")
        assert len(steps) == 2

    def test_no_devices(self):
        from kod.planner import plan_disk_steps

        assert plan_disk_steps(make_conf()) == []
```

**Implementation (append to `src/kod/planner.py`):**

```python
def plan_disk_steps(conf: Any) -> List[Step]:
    """Emit wipe/partition/format steps from conf.devices. Read-only.

    Mirrors create_disk_partitions command sequence (kod/filesystem.py) without
    executing it. Divergence: fs types missing from _filesystem_type skip the
    -t flag instead of raising (preview must not crash on partial tables).
    """
    from kod.filesystem import _filesystem_cmd, _filesystem_type

    steps: List[Step] = []
    devices = conf.devices
    if not devices:
        return steps
    for d_id in sorted(devices.keys()):
        disk = devices[d_id]
        device = disk["device"]
        suffix = "p" if ("nvme" in device or "mmcblk" in device) else ""
        steps.append(Step("disk", f"wipe:{device}", program="wipefs", args=("-a", device)))
        partitions = disk["partitions"]
        if not partitions:
            continue
        for pid in sorted(partitions.keys()):
            part = partitions[pid]
            name = part["name"]
            size = part["size"]
            fs = part["type"]
            mountpoint = part["mountpoint"]
            blockdevice = f"{device}{suffix}{pid}"
            end = "0" if size == "100%" else f"+{size}"
            args = [f"-n", f"0:0:{end}"]
            ptype = _filesystem_type.get(fs)
            if ptype:
                args += ["-t", f"0:{ptype}"]
            args += ["-c", f"0:{name}", device]
            steps.append(Step("disk", f"partition:{name}", program="sgdisk", args=tuple(args),
                              meta={"size": size, "filesystem": fs, "mountpoint": mountpoint}))
            fmt = _filesystem_cmd.get(fs)
            if fmt:
                steps.append(Step("disk", f"format:{name}", program=fmt, args=(blockdevice,),
                                  meta={"filesystem": fs}))
    return steps
```

The real command is one shell string (filesystem.py:289); the Step splits it into an arg vector — test and implementation both use the split form.

**Verify:** `uv run pytest tests/test_planner.py -q` → 7 passed.
**Commit:** `feat: read-only disk step emitter for plan preview`

---

## Task 3: Install baseline plan (`--baseline empty`)

Assembles the full install preview in execution order (kod.py:180-224): disk → base-packages → repos → configure-system → bootloader → kod-user → packages → services → users/programs/user-services.

**Files:** Modify `src/kod/planner.py`; modify `tests/test_planner.py`

**Test (failing first):**

```python
BASE_PKGS = {"kernel": "linux-lts",
             "base": ["base", "base-devel", "intel-ucode"]}


class TestPlanInstall:
    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_full_order_and_content(self, _mock):
        from kod.planner import plan_install

        conf = make_conf(
            devices={"disk0": {"device": "/dev/vda", "partitions": {
                "1": {"name": "boot", "size": "512M", "type": "esp", "mountpoint": "/boot"}}}},
            repos={"official": {}, "aur": {"package": "yay"}},
            packages=["git"],
            services={"sshd": {}},
            users={"bob": {"programs": {"vim": {"enable": True, "deploy_config": True}}}},
        )
        steps = plan_install(conf)
        kinds_names = [(s.kind, s.name) for s in steps]
        assert kinds_names[0] == ("disk", "wipe:/dev/vda")
        # system phase steps in install-flow order (kod.py:186-213)
        phases = [n for k, n in kinds_names if k == "system"]
        assert phases == ["base-packages", "repos", "configure-system", "bootloader", "kod-user"]
        # packages: "git" from conf.packages; "vim" from bob's enabled program
        # (_proc_user_programs adds program names as packages too)
        pkgs = [s for s in steps if s.kind == "package"]
        assert [p.name for p in pkgs] == ["git", "vim"]
        assert pkgs[0].meta == {"action": "install", "repo": "official"}
        base_step = next(s for s in steps if s.name == "base-packages")
        assert base_step.meta == {"kernel": "linux-lts", "base": ["base", "base-devel", "intel-ucode"]}
        repos_step = next(s for s in steps if s.name == "repos")
        assert repos_step.meta == {"repos": ["aur", "official"], "base_packages": {"aur": "yay"}}

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_repo_prefix_parsing(self, _mock):
        from kod.planner import plan_install

        conf = make_conf(packages=["git", "aur:mylib"])
        pkgs = [s for s in plan_install(conf) if s.kind == "package"]
        assert {p.name: p.meta["repo"] for p in pkgs} == {"git": "official", "mylib": "aur"}

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_services_users_programs(self, _mock):
        from kod.planner import plan_install

        conf = make_conf(
            services={"sshd": {}},
            users={"bob": {
                "programs": {"vim": {"enable": True, "deploy_config": True},
                             "off": {"enable": False}},
                "services": {"gpg": {"enable": True}}}},
        )
        steps = plan_install(conf)
        svcs = [(s.name, s.meta) for s in steps if s.kind == "service"]
        assert ("sshd", {"action": "enable"}) in svcs
        assert ("gpg", {"action": "enable", "user": "bob"}) in svcs
        users = [s.name for s in steps if s.kind == "user"]
        progs = [(s.name, s.meta) for s in steps if s.kind == "program"]
        assert users == ["bob"]
        assert progs == [("bob/vim", {"deploy_config": True, "run_script": False})]
```

**Implementation (append to `src/kod/planner.py`):**

```python
def plan_install(conf: Any) -> List[Step]:
    """Full install preview over an empty baseline. Read-only."""
    from kod._core import Context
    from kod.system.packages import get_packages_to_install
    from kod.system.services import get_services_to_enable

    steps = plan_disk_steps(conf)

    pkgs, _remove = get_packages_to_install(conf)
    base_info = {k: v for k, v in pkgs.items() if k != "packages"}
    steps.append(Step("system", "base-packages",
                      meta={k: (sorted(v) if isinstance(v, list) else v)
                            for k, v in base_info.items()}))

    repo_meta: dict = {}
    repos_conf = conf.repos
    if repos_conf is not None:
        repo_meta["repos"] = sorted(repos_conf.keys())
        base_pkgs = {r: d["package"] for r, d in repos_conf.items() if "package" in d}
        if base_pkgs:
            repo_meta["base_packages"] = base_pkgs
    steps.append(Step("system", "repos", meta=repo_meta))
    steps.append(Step("system", "configure-system"))
    steps.append(Step("system", "bootloader"))
    steps.append(Step("system", "kod-user"))

    for pkg in sorted(pkgs["packages"]):
        if ":" in pkg:
            repo, name = pkg.split(":", 1)
        else:
            repo, name = "official", pkg
        steps.append(Step("package", name, meta={"action": "install", "repo": repo}))

    ctx = Context(user="root", stage="install")
    for svc in get_services_to_enable(ctx, conf):
        steps.append(Step("service", svc, meta={"action": "enable"}))

    users = conf.users
    if users is not None:
        for user in sorted(users.keys()):
            info = users[user]
            steps.append(Step("user", user))
            programs = info.programs
            if programs:
                for pname in sorted(programs.keys()):
                    prog = programs[pname]
                    if prog.enable:
                        steps.append(Step(
                            "program", f"{user}/{pname}",
                            meta={"deploy_config": bool(prog.deploy_config),
                                  "run_script": bool(prog.config and "command" in prog.config)}))
            services = info.services
            if services:
                for sname in sorted(services.keys()):
                    if services[sname].enable:
                        steps.append(Step("service", sname,
                                          meta={"action": "enable", "user": user}))
    return steps
```

Notes:
- `get_packages_to_install` internally calls the hard-imported `kod.arch.get_base_packages` (packages.py:11) — tests patch it; production is Linux where `/proc/cpuinfo` exists.
- `pkgs["base"]` is a list → sorted for determinism; `kernel` is a str.
- No `proc_repos` call (stateful): repo base packages are read straight from `conf.repos[*]["package"]`.

**Verify:** `uv run pytest tests/test_planner.py -q` → all pass.
**Commit:** `feat: install baseline plan preview`

---

## Task 4: Rebuild baseline plan (`--baseline current`)

Mirrors the rebuild diff flow (kod.py:343-391): disable removed services → remove packages (failures ignored in prod → `on_error="warn"`) → install packages → kernel hooks → enable new services. Package diff reuses `get_packages_updates` (packages.py:546) so preview can't drift from execution.

**Files:** Modify `src/kod/planner.py`; modify `tests/test_planner.py`

**Test (failing first):**

```python
def make_dist(kernel_update=False):
    from types import SimpleNamespace

    return SimpleNamespace(kernel_update_required=lambda *a, **k: kernel_update)


class TestPlanRebuild:
    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_diff_mapping(self, _mock):
        from kod.planner import plan_rebuild

        conf = make_conf(packages=["keep", "new"])
        current_packages = {"packages": ["keep", "gone"], "kernel": "linux"}
        steps = plan_rebuild(conf, make_dist(), current_packages, [], {})
        acts = {s.name: s.meta["action"] for s in steps if s.kind == "package"}
        assert acts == {"gone": "remove", "new": "install"}  # "keep" satisfied -> no step
        removed = next(s for s in steps if s.name == "gone")
        assert removed.on_error == "warn"

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_service_diff_and_order(self, _mock):
        from kod.planner import plan_rebuild

        conf = make_conf(services={"newsvc": {}})
        current_packages = {"packages": [], "kernel": "linux"}
        steps = plan_rebuild(conf, make_dist(), current_packages, ["oldsvc"], {})
        names = [s.name for s in steps if s.kind == "service"]
        assert names == ["oldsvc", "newsvc"]  # disable before enable (kod.py:365-391)
        acts = {s.name: s.meta["action"] for s in steps if s.kind == "service"}
        assert acts == {"oldsvc": "disable", "newsvc": "enable"}

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_new_generation_skips_disable(self, _mock):
        from kod.planner import plan_rebuild

        conf = make_conf(services={})
        steps = plan_rebuild(conf, make_dist(), {"packages": []}, ["oldsvc"], {},
                             new_generation=True)
        assert not [s for s in steps if s.kind == "service"]

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_kernel_hook_step(self, _mock):
        from kod.planner import plan_rebuild

        conf = make_conf(boot={"kernel": {"package": "linux-lts"}})
        current_packages = {"packages": [], "kernel": "linux"}
        steps = plan_rebuild(conf, make_dist(kernel_update=True), current_packages, [], {})
        hooks = [s for s in steps if s.kind == "program"]
        assert [(s.name, s.meta) for s in hooks] == [("kernel-update:linux-lts", {"hooks": 2})]

    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_update_flag(self, _mock):
        from kod.planner import plan_rebuild

        conf = make_conf()
        steps = plan_rebuild(conf, make_dist(), {"packages": []}, [], {}, update=True)
        assert steps[0] == Step("system", "update-packages")
```

**Implementation (append to `src/kod/planner.py`):**

```python
def plan_rebuild(conf: Any, dist: Any, current_packages: dict, current_services: List[str],
                 current_installed_packages: Optional[dict] = None, update: bool = False,
                 new_generation: bool = False, mount_point: str = "/") -> List[Step]:
    """Rebuild preview over the current generation. Read-only.

    Reuses get_packages_updates so the package diff cannot drift from what
    rebuild actually runs (spec: one planner, two baselines).
    """
    from kod._core import Context
    from kod.system.packages import get_packages_to_install, get_packages_updates
    from kod.system.services import get_services_to_enable

    steps: List[Step] = []
    if update:
        steps.append(Step("system", "update-packages"))

    next_packages, remove_packages = get_packages_to_install(conf)
    to_install, to_remove, _to_update, hooks = get_packages_updates(
        dist, current_packages, next_packages, remove_packages,
        current_installed_packages or {}, mount_point)

    ctx = Context(user="root", stage="rebuild")
    next_services = get_services_to_enable(ctx, conf)

    if not new_generation:
        for svc in sorted(set(current_services) - set(next_services)):
            steps.append(Step("service", svc, meta={"action": "disable"}))
    for pkg in sorted(to_remove):
        steps.append(Step("package", pkg, meta={"action": "remove"}, on_error="warn"))
    for pkg in sorted(to_install):
        steps.append(Step("package", pkg, meta={"action": "install"}))
    if hooks:
        steps.append(Step("program", f"kernel-update:{next_packages.get('kernel', 'linux')}",
                          meta={"hooks": len(hooks)}))
    for svc in sorted(set(next_services) - set(current_services)):
        steps.append(Step("service", svc, meta={"action": "enable"}))
    return steps
```

Notes:
- `packages_to_update` from `get_packages_updates` is intentionally dropped: rebuild never consumes it (kod.py:349-382) — per-package updates happen only via the repo-level `--update` path.
- `hooks` are callables (kernel update/initramfs closures); the plan records count + kernel, not the callables (spec §3: structured data only).

**Verify:** `uv run pytest tests/test_planner.py -q` → all pass.
**Commit:** `feat: rebuild baseline plan preview with package/service diff`

---

## Task 5: `build_plan` dispatch

**Files:** Modify `src/kod/planner.py`; modify `tests/test_planner.py`

**Test (failing first):**

```python
class TestBuildPlan:
    @patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS)
    def test_dispatch(self, _mock):
        from kod.planner import build_plan

        conf = make_conf(packages=["git"])
        empty = build_plan(conf, baseline="empty")
        # install plan starts with system phases; rebuild plan never has them
        assert [s.name for s in empty if s.kind == "system"][:2] == ["base-packages", "repos"]

        current = build_plan(conf, make_dist(), baseline="current",
                             current_packages={"packages": []}, current_services=[])
        assert not [s for s in current if s.name == "base-packages"]
```

**Implementation (append to `src/kod/planner.py`):**

```python
def build_plan(conf: Any, dist: Any = None, baseline: str = "current",
               current_packages: Optional[dict] = None, current_services: Optional[List[str]] = None,
               current_installed_packages: Optional[dict] = None, update: bool = False,
               new_generation: bool = False) -> List[Step]:
    if baseline == "empty":
        return plan_install(conf)
    if baseline != "current":
        raise ValueError(f"unknown baseline: {baseline}")
    return plan_rebuild(conf, dist, current_packages or {}, current_services or [],
                        current_installed_packages, update=update,
                        new_generation=new_generation)
```

**Verify:** `uv run pytest tests/test_planner.py -q` → all pass.
**Commit:** `feat: build_plan baseline dispatch`

---

## Task 6: `kod plan` CLI command + state resolution

**Files:** Modify `src/kod/kod.py`; modify `tests/test_planner.py`

Add to `src/kod/kod.py` (near the other commands; imports already present: `load_packages_services`, `load_package_lock`, `set_base_distribution`, `click`, `Path`):

```python
def _load_current_state() -> Tuple[str, dict, list, dict]:
    """Resolve current generation state read-only. Raises ClickException with hint."""
    try:
        with open("/.generation") as f:
            gen = int(f.readline().strip())
        state_path = f"/kod/generations/{gen}"
        if not Path(f"{state_path}/installed_packages").is_file():
            raise FileNotFoundError(state_path)
        current_packages, current_services = load_packages_services(state_path)
        installed_lock = (load_package_lock(state_path)
                          if Path(f"{state_path}/packages.lock").is_file() else {})
        return state_path, current_packages, current_services, installed_lock
    except (FileNotFoundError, OSError):
        raise click.ClickException(
            "No KodOS generation found on this system. "
            "Use --baseline empty for install previews."
        )


@cli.command()
@click.option("-c", "--config", default=None, help="System configuration file")
@click.option("--baseline", type=click.Choice(["empty", "current"]), default="current",
              help="State to diff against (default: current)")
def plan(config: Optional[str], baseline: str) -> None:
    "Print the execution plan; never executes"
    from kod.planner import build_plan, render_plan

    conf = load_config(config)
    base_distribution = conf.base_distribution
    base_distribution = "arch" if base_distribution is None else base_distribution
    dist = set_base_distribution(base_distribution)

    kwargs: dict = {}
    if baseline == "current":
        _state_path, cur_pkgs, cur_svcs, cur_lock = _load_current_state()
        kwargs = {"current_packages": cur_pkgs, "current_services": cur_svcs,
                  "current_installed_packages": cur_lock}
    steps = build_plan(conf, dist, baseline=baseline, **kwargs)
    print(render_plan(steps, baseline, config))
```

Notes:
- Spec §4: missing-generation error must hint at `--baseline empty` — covered by `_load_current_state`.

**Test (failing first):**

```python
class TestPlanCli:
    @patch("kod.kod._load_current_state",
           return_value=("/kod/generations/1", {"packages": []}, [], {}))
    @patch("kod.kod.load_config")
    def test_plan_current_baseline(self, mock_load, _mock_state):
        from click.testing import CliRunner
        from kod.kod import cli

        mock_load.return_value = make_conf(packages=["git"])
        with patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS):
            result = CliRunner().invoke(cli, ["plan", "--baseline", "current"])
        assert result.exit_code == 0, result.output
        assert "# kod plan" in result.output
        assert "baseline=current" in result.output

    @patch("kod.kod.load_config")
    def test_plan_empty_baseline_needs_no_state(self, mock_load):
        from click.testing import CliRunner
        from kod.kod import cli

        mock_load.return_value = make_conf()
        with patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS):
            result = CliRunner().invoke(cli, ["plan", "--baseline", "empty"])
        assert result.exit_code == 0, result.output
        assert "baseline=empty" in result.output

    @patch("kod.kod.load_config")
    def test_plan_missing_generation_hints_empty(self, mock_load):
        from click.testing import CliRunner
        from kod.kod import cli

        mock_load.return_value = make_conf()
        result = CliRunner().invoke(cli, ["plan"])  # default baseline=current
        assert result.exit_code != 0
        assert "--baseline empty" in result.output
```

**Verify:** `uv run pytest tests/test_planner.py -q` → all pass.
**Commit:** `feat: kod plan CLI command with current/empty baselines`

---

## Task 7: `kod rebuild --dry-run`

**Files:** Modify `src/kod/kod.py`; modify `tests/test_planner.py`

In the `rebuild` command (kod.py:265-269): add option and early return **before any side effect** (insert after `dist = set_base_distribution(base_distribution)`, i.e. before `get_max_generation()`):

```python
@click.option("--dry-run", is_flag=True, help="Print the plan; do not execute")
def rebuild(config: Optional[str], new_generation: bool = False, update: bool = False,
            dry_run: bool = False) -> None:
    ...
    dist = set_base_distribution(base_distribution)

    if dry_run:
        from kod.planner import build_plan, render_plan

        _state_path, cur_pkgs, cur_svcs, cur_lock = _load_current_state()
        steps = build_plan(conf, dist, baseline="current", current_packages=cur_pkgs,
                           current_services=cur_svcs, current_installed_packages=cur_lock,
                           update=update)
        print(render_plan(steps, "current", config))
        return
```

**Test (failing first):**

```python
class TestRebuildDryRun:
    @patch("kod.kod._load_current_state",
           return_value=("/kod/generations/1", {"packages": []}, [], {}))
    @patch("kod.kod.load_config")
    def test_dry_run_prints_plan_and_executes_nothing(self, mock_load, _mock_state):
        from click.testing import CliRunner
        from kod.kod import cli

        mock_load.return_value = make_conf()
        with patch("kod.system.packages.get_base_packages", return_value=BASE_PKGS), \
             patch("kod.kod.exec") as mock_exec:
            result = CliRunner().invoke(cli, ["rebuild", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "# kod plan" in result.output
        mock_exec.assert_not_called()

    def test_dry_run_flag_registered(self):
        from click.testing import CliRunner
        from kod.kod import cli

        result = CliRunner().invoke(cli, ["rebuild", "--help"])
        assert "--dry-run" in result.output
```

**Verify:** `uv run pytest tests/test_planner.py -q` → all pass.
**Commit:** `feat: rebuild --dry-run via shared planner`

---

## Task 8: Golden file — `example/testvm`, empty baseline

End-to-end determinism check on the real Lua config (spec §10 golden files; this is the Python-emitter side of the two-step bootstrap port, spec §6).

**Files:** Create `tests/golden/plan-testvm-empty.txt` (via env-var write); modify `tests/test_planner.py`

**Test:**

```python
GOLDEN = Path(__file__).parent / "golden" / "plan-testvm-empty.txt"


class TestGolden:
    @patch("kod.system.packages.get_base_packages", return_value={
        "kernel": "linux-lts",
        "base": ["arch-install-scripts", "bash-completion", "base", "base-devel",
                 "btrfs-progs", "dracut", "git", "intel-ucode", "linux-firmware",
                 "mlocate", "schroot", "sudo", "whois"],
    })
    def test_testvm_empty_baseline_golden(self, _mock):
        from kod._core import load_config as load_lua
        from kod.planner import plan_install, render_plan

        conf = load_lua(str(EXAMPLE / "configuration.lua"))
        out = render_plan(plan_install(conf), "empty", "example/testvm/configuration.lua")
        if os.environ.get("KODOS_WRITE_GOLDEN"):
            GOLDEN.parent.mkdir(exist_ok=True)
            GOLDEN.write_text(out)
            pytest.skip("golden written")
        assert out == GOLDEN.read_text()

    @patch("kod.system.packages.get_base_packages", return_value={
        "kernel": "linux-lts",
        "base": ["arch-install-scripts", "bash-completion", "base", "base-devel",
                 "btrfs-progs", "dracut", "git", "intel-ucode", "linux-firmware",
                 "mlocate", "schroot", "sudo", "whois"],
    })
    def test_testvm_preview_sanity(self, _mock):
        from kod._core import load_config as load_lua
        from kod.planner import plan_install

        conf = load_lua(str(EXAMPLE / "configuration.lua"))
        steps = plan_install(conf)
        assert ("disk", "wipe:/dev/vda") in [(s.kind, s.name) for s in steps]
        assert any(s.kind == "package" and s.meta["action"] == "install" for s in steps)
```

Add at top of test file: `import os` and `EXAMPLE = Path(__file__).parent.parent / "example" / "testvm"` (same pattern as tests/config/test_cli.py:9).

**Procedure:**
1. `KODOS_WRITE_GOLDEN=1 uv run pytest tests/test_planner.py::TestGolden -q` → writes golden, skips.
2. Inspect `tests/golden/plan-testvm-empty.txt` for sanity: first step wipes `/dev/vda`; partition steps match the config's disk layout; system phase steps in order; package count plausible (>10); no `exec`-style output noise.
3. Re-run without env var → green.

**Commit:** `test: golden plan output for example/testvm empty baseline`

---

## Task 9: Full regression + wrap-up

**Verify:**
```
uv run pytest tests/ -q
```
All existing 422+ tests plus the new planner suite must pass. (No execution-path code was touched, so failures here indicate a real import/circular-dependency issue — fix at the root, e.g. lazy imports inside planner functions already guard against `kod._core` cycles.)

**Manual smoke (optional; Linux target only — `get_base_packages` reads `/proc/cpuinfo`):**
```
uv run kod plan --baseline empty -c example/testvm/configuration.lua
```

**Commit:** none expected (tests only). If anything changed, commit as `fix: planner regression fixes`.

---

## Out of scope for this plan (Plan B)

- Executor adoption: `install`/`rebuild` executing the plan object (spec §5).
- Lifecycle hooks mechanism replacing `hooks_to_run` (spec §7).
- Lua bootstrap emitter port + Python-vs-Lua golden diff (spec §6 step 2).
- `build:<name>` steps + Phase 5a cache integration (spec §8) — gated on Phase 5a landing.
- `rebuild-user` planner adoption (spec §11).
