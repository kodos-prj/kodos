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
