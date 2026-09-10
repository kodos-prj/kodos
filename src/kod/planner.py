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
