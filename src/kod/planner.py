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


def _attach_hooks_to_steps(steps: List[Step], hooks_map: dict) -> List[Step]:
    """Attach hook event names to step metadata for visibility.
    
    Args:
        steps: List of Step objects
        hooks_map: Dict mapping hook event name → list of callables
    
    Returns:
        New list of Steps with hook names added to meta (frozen Step pattern).
    """
    if not hooks_map:
        return steps
    
    result = []
    for step in steps:
        # Find hook events that would fire for this step's kind
        hook_events = sorted([event for event in hooks_map.keys() if event.endswith(f":{step.kind}")])
        
        if hook_events:
            # Create new Step with updated meta (frozen dataclass pattern)
            new_meta = dict(step.meta)
            new_meta["hooks"] = hook_events
            step = Step(
                step.kind, step.name,
                program=step.program, args=step.args,
                chroot=step.chroot, timeout_s=step.timeout_s,
                on_error=step.on_error, meta=new_meta
            )
        result.append(step)
    
    return result


def render_plan(steps: List[Step], baseline: str, config_path: Optional[str] = None) -> str:
    """Render steps as deterministic text (golden-file testable)."""
    lines = ["# kod plan", f"# baseline={baseline} config={config_path or '<default>'}"]
    for i, s in enumerate(steps, 1):
        cmd = " ".join([s.program, *s.args]).strip()
        line = f"{i:03d} [{s.kind}] {s.name}:"
        if cmd:
            line += f" {cmd}"
        
        # Extract hooks separately for special formatting
        meta_copy = dict(s.meta)
        hooks = meta_copy.pop("hooks", None)
        
        if meta_copy:
            line += f" {json.dumps(meta_copy, sort_keys=True)}"
        
        if hooks:
            line += f" hooks={json.dumps(sorted(hooks))}"
        
        lines.append(line)
    return "\n".join(lines) + "\n"


def predict_partition_list(conf: Any) -> List[dict]:
    """Predict partition_list from conf.devices without execution.
    
    Pre-computes the list of partitions that will be created, used as input
    to Lua bootstrap modules. Must NOT execute any filesystem operations.
    
    Args:
        conf: Configuration object with conf.devices
    
    Returns:
        List of dicts: [{device: "/dev/sda1", mountpoint: "/boot", filesystem: "vfat"}, ...]
    
    Logic:
    - For each device in conf.devices (sorted by ID):
      - Determine suffix ("p" for nvme/mmcblk, "" for sda/sdb)
      - For each partition in device.partitions (sorted by ID):
        - Compute device name: device + suffix + partition_id
        - Extract mountpoint, filesystem from partition config
        - Add to list
    
    Note: Validation is lenient for plan preview (test configs may be incomplete).
    """
    partitions = []
    devices = conf.devices
    if not devices:
        return partitions
    
    for d_id in sorted(devices.keys()):
        disk = devices[d_id]
        device = disk["device"]
        suffix = "p" if ("nvme" in device or "mmcblk" in device) else ""
        disk_partitions = disk["partitions"] if disk["partitions"] else {}
        
        if not disk_partitions:
            continue
        
        for pid in sorted(disk_partitions.keys()):
            part = disk_partitions[pid]
            name = part["name"]
            fs = part["type"]
            mountpoint = part["mountpoint"]
            blockdevice = f"{device}{suffix}{pid}"
            
            partitions.append({
                "device": blockdevice,
                "mountpoint": mountpoint,
                "filesystem": fs,
            })
    
    return partitions


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


def plan_install(conf: Any) -> List[Step]:
    """Full install preview over an empty baseline. Read-only.
    
    Integrates Lua bootstrap emission (disk + mount + system config) with
    package, service, and user management steps.
    """
    from kod._core import Context
    from kod.system.packages import get_packages_to_install
    from kod.system.services import get_services_to_enable
    from kod.bootstrap import emit_bootstrap_steps
    import logging
    
    logger = logging.getLogger(__name__)
    steps = []
    
    # Step 1: Pre-compute partition list from conf (Option B)
    predicted_partition_list = predict_partition_list(conf)
    
    # Step 2: Emit bootstrap steps via Lua module (disk + mount + system config)
    distro = conf.base_distribution or "arch"
    try:
        bootstrap_steps = emit_bootstrap_steps(conf, predicted_partition_list, distro=distro)
        steps.extend(bootstrap_steps)
    except Exception as e:
        # If Lua bootstrap fails, fall back to plan_disk_steps (backward compat)
        logger.warning(f"Lua bootstrap failed: {e}; falling back to plan_disk_steps")
        steps.extend(plan_disk_steps(conf))
    
    # Step 3: Add package management steps
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
    
    # Step 4: Add system configuration steps
    steps.append(Step("system", "configure-system"))
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
    
    # Attach hook event names for visibility in plan output
    from kod.hooks import collect_hooks
    try:
        hooks_map = collect_hooks(conf.users or {})
        steps = _attach_hooks_to_steps(steps, hooks_map)
    except Exception:
        # If hook collection fails, proceed without hooks (backward compat)
        pass
    
    return steps


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
    to_install, to_remove, _to_update, kernel_update_required = get_packages_updates(
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
    
    # Emit kernel update as explicit system steps instead of hooks
    if kernel_update_required:
        kernel = next_packages.get("kernel", "linux")
        steps.append(Step("system", "kernel-update", meta={"kernel": kernel}))
        steps.append(Step("system", "initramfs-update", meta={"kernel": kernel}))
    
    for svc in sorted(set(next_services) - set(current_services)):
         steps.append(Step("service", svc, meta={"action": "enable"}))
    
    # Attach hook event names for visibility in plan output
    from kod.hooks import collect_hooks
    try:
        hooks_map = collect_hooks(conf.users or {})
        steps = _attach_hooks_to_steps(steps, hooks_map)
    except Exception:
        # If hook collection fails, proceed without hooks (backward compat)
        pass
    
    return steps


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
