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
