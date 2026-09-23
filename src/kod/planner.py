"""Execution plan builder (step composer) for KodOS install/rebuild.

Composes a flat, ordered list of Steps describing what install or rebuild would
do, by calling Lua section modules and converting their output.

Key responsibility: Transform configuration → ordered Steps (via Lua).
Does NOT execute steps; that's planner.py's job.

Step sources:
  - devices.lua: Disk partitioning, formatting, mounting
  - boot.lua: Boot loader setup
  - packages.lua: Package installation
  - services.lua: Service enablement
  - users.lua: User creation
  - ... (other sections)

Step outputs are JSON-serializable (for preview, dry-run, logging).

See ARCHITECTURE.md for system design.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any


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


def _convert_lua_step_to_step(lua_step: Any) -> Step:
    """Convert a Lua step table to a Python Step object.
    
    Args:
        lua_step: A Lua table with step fields
        
    Returns:
        A Step object
    """
    # Extract fields from Lua table (use attribute access for Lupa LuaTable)
    kind = str(lua_step.kind or lua_step.step_kind or "system")
    name = str(lua_step.name or "")
    program = str(lua_step.program or lua_step.command or "")
    
    # Extract args (convert from Lua table to Python tuple)
    args = ()
    args_lua = lua_step.args
    if args_lua:
        args_list = []
        for i in range(1, len(args_lua) + 1):
            if i in args_lua:  # Check if index exists
                args_list.append(str(args_lua[i]))
        args = tuple(args_list)
    
    # Extract meta (convert from Lua table to Python dict)
    meta = {}
    meta_lua = lua_step.meta
    if meta_lua and hasattr(meta_lua, "keys"):
        for key in meta_lua.keys():
            val = meta_lua[key]
            if hasattr(val, "keys"):
                # Nested Lua table - convert to dict
                nested = {}
                for nkey in val.keys():
                    nested[nkey] = val[nkey]
                meta[key] = nested
            else:
                meta[key] = val
    
    # Extract other Step fields
    chroot = bool(lua_step.chroot or False)
    timeout_s = int(lua_step.timeout_s or 300)
    on_error = str(lua_step.on_error or "abort")
    
    return Step(
        kind=kind,
        name=name,
        program=program,
        args=args,
        chroot=chroot,
        timeout_s=timeout_s,
        on_error=on_error,
        meta=meta,
    )


def compose_steps_lua(config: Any, distro: str = "arch") -> list[Step]:
    """Call the Lua planner to compose steps from all sections.
    
    This replaces the manual Python composition in plan_install() with
    the schema-driven Lua planner that loads all section modules.
    
    Args:
        config: Configuration object (dict, Lua table, or object with __dict__)
        distro: Distribution name ("arch" or "debian")
    
    Returns:
        List of Step objects in execution order
        
    Raises:
        RuntimeError: If Lua planner fails (can be caught for fallback)
    """
    import logging
    import os

    from kod.lua_runtime import get_lua_runtime
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get persistent Lua runtime
        lua = get_lua_runtime()
        
        # Force reload of Lua modules to pick up code changes
        lua.reload_modules(['kod\\..*'])
        
        # Set Lua package.path to include src/kod/lib and src/kod/sections
        base_path = os.path.dirname(os.path.dirname(__file__))
        lua_path = f"{base_path}/?.lua;{base_path}/?/init.lua"
        lua.execute(f"package.path = '{lua_path}' .. package.path")
        
        # Convert config to Lua table if needed
        from kod.bootstrap import _convert_to_lua_table
        if hasattr(config, "__dict__"):
            config_lua = _convert_to_lua_table(lua, vars(config))
        elif isinstance(config, dict):
            config_lua = _convert_to_lua_table(lua, config)
        else:
            config_lua = config
        
        # Load and call Lua planner
        # lua.require() returns (module, filename) tuple
        result = lua.require("kod.planning.planner")
        planner_module = result[0] if isinstance(result, tuple) else result
        
        # Call the compose method on the planner object
        lua_steps, error_msg = planner_module.compose(planner_module, config_lua, distro)
        
        if error_msg:
            logger.warning(f"Lua planner warnings: {error_msg}")
        
        if not lua_steps:
            if error_msg:
                raise RuntimeError(f"Lua planner failed: {error_msg}")
            logger.warning("Lua planner returned no steps")
            return []
        
        # Convert Lua steps to Python Step objects
        steps = []
        try:
            # lua_steps is a Lua table with integer keys (1-indexed)
            for idx in range(1, len(lua_steps) + 1):
                lua_step = lua_steps[idx]
                step = _convert_lua_step_to_step(lua_step)
                steps.append(step)
        except Exception as e:
            logger.error(f"Failed to convert Lua steps: {e}")
            raise RuntimeError(f"Failed to convert Lua steps to Python: {e}")
        
        return steps
        
    except Exception as e:
        raise RuntimeError(f"Lua planner failed: {e}")


def compose_rebuild_steps_lua(state: dict) -> list[Step]:
    """Call the Lua rebuild diff planner (kod/lib/rebuild.lua).

    Pure table ops in Lua; all state (package/service sets, kernel flag) is
    passed in as plain data. Fallback to the Python diff on any failure.
    """
    from kod.lua_runtime import get_lua_runtime

    try:
        lua = get_lua_runtime()
        
        # Force reload of Lua modules to pick up code changes
        lua.reload_modules(['kod\\..*'])

        base_path = os.path.dirname(os.path.dirname(__file__))
        lua_path = f"{base_path}/?.lua;{base_path}/?/init.lua"
        lua.execute(f"package.path = '{lua_path}' .. package.path")

        from kod.bootstrap import _convert_to_lua_table
        state_lua = _convert_to_lua_table(lua, state)

        result = lua.require("kod.planning.rebuild")
        module = result[0] if isinstance(result, tuple) else result

        steps_lua = module.diff(state_lua)

        steps = []
        for idx in range(1, len(steps_lua) + 1):
            steps.append(_convert_lua_step_to_step(steps_lua[idx]))
        return steps

    except Exception as e:
        raise RuntimeError(f"Lua rebuild planner failed: {e}")


def _attach_hooks_to_steps(steps: list[Step], hooks_map: dict) -> list[Step]:
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
        hook_events = sorted([event for event in hooks_map if event.endswith(f":{step.kind}")])
        
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


def render_plan(steps: list[Step], baseline: str, config_path: str | None = None) -> str:
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


def predict_partition_list(conf: Any) -> list[dict]:
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
            fs = part["type"]
            mountpoint = part["mountpoint"]
            blockdevice = f"{device}{suffix}{pid}"
            
            partitions.append({
                "device": blockdevice,
                "mountpoint": mountpoint,
                "filesystem": fs,
            })
    
    return partitions


def plan_disk_steps(conf: Any) -> list[Step]:
    """Emit wipe/partition/format steps from conf.devices. Read-only.

    Calls Lua filesystem_types module to get mkfs commands and GPT type codes
    (single source of truth with devices.lua).
    """
    from kod.lua_runtime import get_lua_runtime

    steps: list[Step] = []
    devices = conf.devices
    if not devices:
        return steps
    
    # Get filesystem type tables from Lua (single source of truth with devices.lua)
    try:
        lua = get_lua_runtime()
        fs_types = lua.require("kod.system.filesystem_types")
        mkfs_commands = dict(fs_types.mkfs_commands)
        gpt_type_codes = dict(fs_types.gpt_type_codes)
    except Exception as e:
        print(f"Warning: could not load filesystem_types from Lua: {e}")
        mkfs_commands = {}
        gpt_type_codes = {}
    
    for d_id in sorted(devices.keys()):
        disk = devices[d_id]
        device = disk["device"]
        suffix = "p" if ("nvme" in device or "mmcblk" in device) else ""
        steps.append(Step("disk", f"wipe:{device}", program="wipefs", args=("-a", device)))
        
        # Initialize GPT partition table
        steps.append(Step("disk", f"init-gpt:{device}", program="sgdisk", args=("-Z", device),
                          meta={"device": device}))
        
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
            
            # Build sgdisk args: -n 0:0:SIZE -t 0:TYPE -c 0:NAME device
            # Size format: +512MiB, +10GiB for relative sizing, or 0 for remaining space
            end_sector = "0" if size == "100%" else f"+{size}"
            args = ["-n", f"0:0:{end_sector}"]
            gpt_type = gpt_type_codes.get(fs)
            if gpt_type:
                args += ["-t", f"0:{gpt_type}"]
            args += ["-c", f"0:{name}", device]
            
            steps.append(Step("disk", f"partition:{name}", program="sgdisk", args=tuple(args),
                              meta={"size": size, "filesystem": fs, "mountpoint": mountpoint}))
            
            # Format if filesystem is defined and has a mkfs command
            fmt = mkfs_commands.get(fs)
            if fmt:
                steps.append(Step("disk", f"format:{name}", program=fmt, args=(blockdevice,),
                                  meta={"filesystem": fs}))
    return steps


def plan_install(conf: Any) -> list[Step]:
    """Full install preview over an empty baseline. Read-only."""
    distro = conf.base_distribution or "arch"
    steps = compose_steps_lua(conf, distro)
    from kod.hooks import collect_hooks
    try:
        hooks_map = collect_hooks(conf.users or {})
        steps = _attach_hooks_to_steps(steps, hooks_map)
    except Exception:
        pass
    return steps


def plan_rebuild(conf: Any, dist: Any, current_packages: dict, current_services: list[str],
                 current_installed_packages: dict | None = None, update: bool = False,
                 new_generation: bool = False, mount_point: str = "/") -> list[Step]:
    """Rebuild preview over the current generation. Read-only."""
    import logging
    import sys

    from kod.context import Context
    from kod.hooks import collect_hooks
    from kod.system.packages import get_packages_to_install
    from kod.system.services import get_services_to_enable
    
    logger = logging.getLogger(__name__)

    next_packages, remove_packages = get_packages_to_install(conf)
    ctx = Context(user="root", stage="rebuild")
    next_services = get_services_to_enable(ctx, conf)

    # DEBUG: Print to stderr so it definitely shows up
    print(f"DEBUG: current_packages={list(current_packages.get('packages', []))}", file=sys.stderr)
    print(f"DEBUG: next_packages={list(next_packages.get('packages', []))}", file=sys.stderr)
    print(f"DEBUG: remove_packages={list(remove_packages or [])}", file=sys.stderr)

    kernel_update_required = dist.kernel_update_required(
        current_packages.get("kernel", "linux"),
        next_packages.get("kernel", "linux"),
        current_installed_packages or {}, mount_point)
    steps = compose_rebuild_steps_lua({
        "next_packages": {"packages": list(next_packages.get("packages", [])),
                         "kernel": next_packages.get("kernel", "linux")},
        "current_packages": {"packages": list(current_packages.get("packages", [])),
                             "kernel": current_packages.get("kernel", "linux")},
        "remove_packages": list(remove_packages or []),
        "next_services": list(next_services),
        "current_services": list(current_services or []),
        "update": update,
        "new_generation": new_generation,
        "kernel_update_required": kernel_update_required,
        "distro": conf.base_distribution or "arch",
    })
    try:
        hooks_map = collect_hooks(conf.users or {})
        steps = _attach_hooks_to_steps(steps, hooks_map)
    except Exception:
        pass
    return steps


def build_plan(conf: Any, dist: Any = None, baseline: str = "current",
               current_packages: dict | None = None, current_services: list[str] | None = None,
               current_installed_packages: dict | None = None, update: bool = False,
               new_generation: bool = False) -> list[Step]:
    if baseline == "empty":
        return plan_install(conf)
    if baseline != "current":
        raise ValueError(f"unknown baseline: {baseline}")
    return plan_rebuild(conf, dist, current_packages or {}, current_services or [],
                        current_installed_packages, update=update,
                        new_generation=new_generation)
