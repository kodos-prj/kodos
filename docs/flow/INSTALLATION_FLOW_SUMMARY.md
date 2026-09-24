# KodOS Installation Flow - Quick Summary

## What This Document Covers

This analysis maps the **complete installation and rebuild flow** for KodOS, including:
- Entry points and main commands
- How Lua section modules are composed into execution steps
- Package handling (normal, AUR, flatpak) 
- Service/system configuration
- The Lua-Python interop layer
- Error handling and rollback mechanisms

## Quick Navigation

| Document | Purpose |
|----------|---------|
| **KODOS_INSTALLATION_FLOW.md** | Detailed breakdown of all phases, flows, and interactions |
| **INSTALLATION_FLOW_VISUAL.txt** | ASCII diagrams showing execution flow for install/rebuild |
| This file | Quick reference and navigation guide |

## Core Architecture (One-Liner)

**KodOS = Schema-driven Lua sections → Step composition → Lua executor**

1. **Load** config (Lua file → Python object)
2. **Plan** steps (Lua sections emit step tables)
3. **Execute** steps (Lua orchestrator runs shell commands with hooks)
4. **State** storage (JSON snapshots of packages/services)

---

## Entry Points

```bash
kod install          # Full install from scratch (empty baseline)
kod rebuild          # Incremental update (current baseline)
kod plan             # Dry-run preview (no execution)
kod rebuild-user     # User-only config update
kod config validate  # Config validation
```

**File**: src/kod/kod.py

---

## Installation Flow at a Glance

```
1. load_config() → parse .lua config file
2. build_plan(baseline="empty") → compose_steps_lua()
   ├─ For each section (devices, packages, services, users, ...):
   │  ├─ Load section module via lua.require()
   │  ├─ Call section.emit_steps(config, distro)
   │  └─ Collect returned step tables
   ├─ sort_steps() → order by dependency
   └─ Return: list[Step]
3. execute_steps(steps, env, mount_point, use_chroot=True)
   ├─ Lua executor runs each step in order
   ├─ Shell commands wrapped in chroot if needed
   ├─ Fire pre/post hooks per step kind
   └─ Apply on_error policy (abort|warn)
4. store_packages_services() → write JSON state
5. generate_package_lock() → write version snapshot
6. Cleanup and done
```

**Files**: 
- kod.py:427-551
- planner.py:394-461
- executor.py:36-113
- planning/planner.lua:140-206

---

## Rebuild Flow at a Glance

```
1. _load_current_state() → read /.generation, load JSON
2. Prepare generation:
   if new_generation:
     └─ Create btrfs snapshot, mount at new_root_path
   else:
     └─ Snapshot for rollback, in-place at /
3. dist.proc_repos() → process repositories
4. build_plan(baseline="current", current_packages, current_services)
   └─ compose_rebuild_steps_lua() → diff-based step generation
5. execute_steps() → same as install
6. store_packages_services() + generate_package_lock()
7. _swap_generations_atomic() if not new_generation
8. Write /.generation marker
```

**Files**:
- kod.py:639-845
- planner.py:407-461
- planning/rebuild.lua:41-184

---

## Package Handling (Normal vs AUR vs Flatpak)

### Aggregation (Lua)
All packages from config sections are collected by packages.lua:aggregate_all_packages():
- Desktop environments + extra_packages
- Hardware packages + extra_packages
- System packages (config.packages)
- Font packages
- Global/user programs + extra_packages
- User services + extra_packages

**Result**: Single list with prefixes
- `"vim"` → Normal package
- `"aur:yay"` → AUR package
- `"flatpak:org.gnome.Evolution"` → Flatpak app

**File**: src/lua/kod/sections/packages.lua:218-241

### Type Separation (Lua)
```lua
separate_packages() → (normal_pkgs, aur_pkgs, flatpak_pkgs)
```

### Step Emission (Lua)
For Arch (AUR support):
```
Step 1 (order 490):    pacman -S normal_pkgs + base-devel + git
Step 2 (order 492):    useradd kod (build user)
Step 3 (order 493):    Add kod to sudoers
Step 4 (order 494):    Build & install yay
Step 5+ (order 500+):  For each AUR package: yay -S --noconfirm
```

For Debian (no AUR):
```
Step 1 (order 500):    apt-get install normal_pkgs
```

**File**: src/lua/kod/sections/packages.lua:295-419

---

## Service & System Configuration

### Services
Services come from:
- config.services
- config.desktop.*.services
- config.programs[*].services
- config.users[*].services

Aggregated by: src/lua/kod/sections/services.lua:aggregate_services()

### Kernel & Boot
Three system hooks fire during execution:
- `kernel-update` → copies kernel image to /boot/
- `initramfs-update` → runs dracut
- `boot-entry` → creates EFI/GRUB entry

**File**: src/kod/system/boot.py

---

## Lua-Python Interop

### Data Flow
```
Python dict/object
  ↓ _convert_to_lua_table()
Lua table
  ↓ lua.require(), section.emit_steps()
Lua step tables {kind, name, program, args, order, meta, ...}
  ↓ _convert_lua_step_to_step()
Python Step objects (frozen dataclass)
  ↓ execute_steps()
Lua executor runs steps
```

### Key Functions
- **get_lua_runtime()** → Singleton Lua state (lua_runtime.py)
- **_convert_to_lua_table()** → Python → Lua (bootstrap.py:20)
- **lua_table_to_python()** → Lua → Python (lua_utils.py)
- **_convert_lua_step_to_step()** → Lua step → Python Step (planner.py:52)

---

## Section Modules (All 13)

Load order in planner.lua:163-194:

| # | Module | Purpose | Key Function |
|---|--------|---------|---|
| 1 | base_distribution | Distro detection | Sets base_distribution |
| 2 | repos | Repository config | emit_steps() |
| 3 | devices | Disk operations | Partition/format/mount |
| 4 | boot | Boot loader | EFI/GRUB entries |
| 5 | hardware | Hardware packages | GPU drivers, etc. |
| 6 | locale | Locale setup | Timezone, lang |
| 7 | network | Network config | Hostname, DNS |
| 8 | users | User creation | useradd |
| 9 | desktop | DE/display | GNOME, KDE, etc. |
| 10 | fonts | Font installation | Font packages |
| 11 | packages | **Aggregates all** | emit_steps() for pacman/apt |
| 12 | services | Service enablement | systemctl enable |
| 13 | programs | System programs | Global program installs |

**File**: src/lua/kod/planning/planner.lua:8-12

---

## Distro Adapters

### Interface (Abstract)
- `proc_repos()` → Process repository config
- `refresh_package_db()` → Update package cache
- `kernel_update_required()` → Check if kernel needs updating
- `generate_package_lock()` → Capture installed versions

**File**: src/kod/system/distro/base.py

### Implementations
- **Arch** (adapters/arch.py) → pacman, yay, AUR support
- **Debian** (adapters/debian.py) → apt, PPA, no AUR

---

## Generation Management

### State Files (JSON)
```
/kod/generations/{N}/
├─ installed_packages    {"packages": [...], "kernel": "linux"}
├─ enabled_services      [list of service names]
├─ packages.lock         {pkg_name: version, ...}
├─ rootfs/               (btrfs subvolume)
└─ boot/                 (boot partition clone)
```

### Current State
```
/.generation             (current generation number)
/kod/current/            (symlink/mount points)
├─ old-rootfs            (snapshot for rollback)
├─ installed_packages    (copy during rebuild)
└─ enabled_services      (copy during rebuild)
```

**File**: src/kod/system/generations.py

---

## Atomic Generation Swap

Swaps rootfs with rollback on failure:

```
1. Create btrfs backup of current_rootfs
2. Move current_rootfs → new_generation/rootfs
3. Move old_rootfs → current_rootfs  ← CRITICAL POINT
4. Move state files to previous generation
5. On success: rm backup
6. On failure: restore from backup (rollback)
```

**File**: src/kod/kod.py:156-267

---

## Error Handling

### Per-Step Policies
```
step.on_error = "abort"   # Stop plan, raise StepError
step.on_error = "warn"    # Log warning, continue
```

### Rollback on Failure
```
catch Exception during rebuild:
  └─ _cleanup_failed_generation()
     ├─ Unmount new_root_path
     ├─ btrfs subvolume delete rootfs/boot
     └─ rm -rf generation_directory
```

**File**: src/kod/kod.py:554-591

---

## Key Data Structures

### Step (Python)
```python
@dataclass(frozen=True)
class Step:
    kind: str           # disk|package|service|system|user|program
    name: str           # step identifier
    program: str        # command name (pacman, useradd, etc.)
    args: tuple         # command arguments
    chroot: bool        # run inside chroot?
    timeout_s: int      # timeout in seconds
    on_error: str       # abort|warn
    meta: dict          # arbitrary metadata {kernel, order, depends_on, ...}
```

**File**: src/kod/planner.py:28-50

### StepResult (Python)
```python
@dataclass(frozen=True)
class StepResult:
    step: Step
    success: bool
    error: Optional[str]
    stdout: Optional[str]
    stderr: Optional[str]
    is_warning: bool    # True if on_error='warn' and failed
```

**File**: src/kod/executor.py:25-34

---

## Common Patterns

### Section Module Pattern
```lua
local module = {
    schema = Schema.section_name,
    
    emit_steps = function(config, distro)
        local steps = {}
        -- Emit step tables
        return steps
    end
}

return module
```

### Step Table Pattern
```lua
{
    kind = "package",          -- Required
    name = "packages_install", -- Required
    program = "pacman",        -- Command name
    args = {"-S", "--noconfirm", "vim"},  -- Args tuple
    command = "...",           -- Alternative to program+args
    chroot = true,             -- Run in chroot?
    order = 500,               -- Execution order
    timeout_s = 600,           -- Timeout in seconds
    on_error = "warn",         -- Error handling
    depends_on = {"pkg1"},     -- Dependencies
    meta = {custom = "data"},  -- Custom metadata
}
```

---

## Quick Reference: File Locations

### Python Core
- **kod.py** - CLI entry points (install, rebuild, plan, etc.)
- **planner.py** - Step composition (build_plan, compose_steps_lua)
- **executor.py** - Step execution (execute_steps)
- **bootstrap.py** - Bootstrap step emission
- **lua_runtime.py** - Lua singleton manager
- **config/loader.py** - Config file loading
- **system/packages.py** - Package state (aggregation, locking)
- **system/services.py** - Service state
- **system/boot.py** - Boot hooks (kernel, initramfs, entries)
- **system/distro/base.py** - Distro adapter interface
- **system/distro/adapters/*.py** - Distro-specific implementations
- **system/generations.py** - Generation management

### Lua Sections
- **sections/packages.lua** - Package aggregation & step emission
- **sections/services.lua** - Service aggregation
- **sections/users.lua** - User creation
- **sections/devices.lua** - Disk operations
- **sections/boot.lua** - Boot configuration
- **sections/desktop.lua** - Desktop environment
- (and 7 more: hardware, fonts, locale, network, repos, base_distribution, programs)

### Lua Planning
- **planning/planner.lua** - Main section loader & step composer
- **planning/executor.lua** - Step execution orchestrator
- **planning/rebuild.lua** - Rebuild diff planner

---

## Debugging Tips

1. **See the plan without executing**: `kod plan --baseline empty`
2. **Check current state**: Read `/.generation`, then examine `/kod/generations/{N}/*.json`
3. **Validate config**: `kod config validate -c {config_file}`
4. **View schema**: `kod config schema`
5. **Trace Lua errors**: Check stderr during `kod plan` or `kod rebuild`
6. **Check chroot mounts**: `mountpoint /mnt` after failed install
7. **Inspect step order**: Look for `order` field in plan output

---

## Related Documents

- KODOS_INSTALLATION_FLOW.md - Detailed step-by-step breakdown
- INSTALLATION_FLOW_VISUAL.txt - ASCII flow diagrams
- Architecture overview documents in main repo

---

**Generated**: 2026-09-23
**Scope**: Complete installation & rebuild flow analysis
**Focus**: Function calls, file locations, data flow, package handling
