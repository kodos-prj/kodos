# KodOS Architecture: Python Orchestration + Lua Execution

## Overview

KodOS uses a **dual-layer architecture**:
- **Python**: Orchestration, validation, and high-level control flow
- **Lua**: System operations, disk management, package handling, and step emission

This separation provides:
- **Clarity**: Each layer has a single responsibility
- **Testability**: Lua steps can be previewed without execution
- **Maintainability**: Configuration and logic co-located in one language per concern
- **Reusability**: Lua modules work standalone; Python can call them for preview

---

## Layer Responsibilities

### Python (`src/kod/`)

**Orchestration & Control**:
- `kod.py`: CLI commands (install, rebuild, plan, config)
- `planner.py`: Build execution plan by composing Lua modules
- `bootstrap.py`: Bootstrap-specific step emission
- `context.py`: Execution context (mount points, chroot, environment)

**Configuration & Validation**:
- `config/loader.py`: Load Lua config files, convert to Python dicts
- `config/validator.py`: Validate configuration against schema
- `config/schema.py`: Load Lua schema definitions for validation

**System State Management**:
- `system/generations.py`: Generation lifecycle (mount, unmount, fstab management)
- `system/packages.py`: Package locking, service tracking
- `system/boot.py`: Kernel/initramfs management

**Utilities**:
- `lua_utils.py`: Shared Lua↔Python conversion (single source of truth)
- `common.py`: Logging, execution, problem tracking
- `context.py`: Execution environment management

**Key Principle**: Python does NOT handle disk operations, formatting, or package installation.

### Lua (`src/lua/kod/`)

**Core Modules**:
- `core/schema.lua`: Configuration schema definitions (single source of truth)
- `core/bootstrap.lua`: Bootstrap operations (unified for arch/debian)
- `system/filesystem_types.lua`: Filesystem type → mkfs command mapping (single source)
- `system/disk.lua`: Disk operations (mount, umount, partitioning helpers)
- `system/repos.lua`: Repository and package management

**Section Modules** (emits install/rebuild steps):
- `sections/devices.lua`: Disk partitioning, formatting, mounting (sgdisk-based)
- `sections/boot.lua`: Boot loader and kernel setup
- `sections/packages.lua`: Package installation steps
- `sections/services.lua`: Service enablement steps
- `sections/users.lua`: User and group creation
- `sections/desktop.lua`: Desktop environment setup
- `sections/programs.lua`: Custom program setup

**Key Principle**: Lua emits steps (not executed directly); Python decides when/how to execute them.

---

## Data Flow

### Install Flow
```
CLI (kod.py)
  ↓
planner.py: compose_steps_lua()
  ↓ (loads Lua modules)
Lua sections/{devices,boot,packages,...}.lua
  ↓ (emits Step objects)
Python: execute_steps()
  ↓
System execution (sgdisk, mkfs, pacman, etc.)
```

### Rebuild Flow
```
CLI (kod.py rebuild)
  ↓
Load current generation state
  ↓
planner.py: plan_rebuild()
  ↓ (calls Lua)
Lua sections/packages.lua, sections/services.lua, ...
  ↓ (emits steps for changes)
Python: execute_steps()
  ↓
chroot into new generation
  ↓
System execution
```

### Config Loading Flow
```
User: kod.json (Lua config)
  ↓
config/loader.py: load_config_lua()
  ↓
Lua runtime executes config
  ↓
lua_utils.py: lua_table_to_python()
  ↓
Python dict (validated)
```

---

## Single Sources of Truth

### 1. Filesystem Type Mappings
**Location**: `src/lua/kod/system/filesystem_types.lua`
- Defines mkfs commands and GPT type codes
- Used by:
  - `devices.lua`: Generates sgdisk partitioning steps
  - `planner.py:plan_disk_steps()`: Generates preview steps
- **Why Lua?** Partitioning is fundamentally a disk operation; Lua owns that domain

### 2. Configuration Schema
**Location**: `src/lua/kod/core/schema.lua`
- Defines all config sections, field types, descriptions
- Used by:
  - `config/validator.py`: Validates user config
  - `planner.py`: Composes steps based on config
- **Why Lua?** Schema is config itself; centralizing avoids duplication

### 3. Lua-to-Python Conversion
**Location**: `src/kod/lua_utils.py:lua_table_to_python()`
- Unified function for converting lupa LuaTable → Python dict/list
- Used by:
  - `bootstrap.py`: Convert conf before re-Lua-fying
  - `schema.py`: Convert schema section definitions
  - `loader.py`: Convert loaded config
- **Why unified?** Detection of array vs dict must be consistent; one implementation, one place

---

## Key Architectural Decisions

### Why Lua for Sections?
1. **Steps are declarations**: Each section describes what to do, not how to do it
2. **Reusability**: Sections can be called independently (preview, dry-run, execute)
3. **Portability**: Lua is lightweight; sections don't depend on Python internals
4. **Clarity**: Distro-specific logic (arch vs debian) stays in Lua, not if/else in Python

### Why Python for Orchestration?
1. **Control flow**: Rebuild, error handling, generation management needs imperative logic
2. **State**: Tracking what's installed, enabled, current generation requires mutable state
3. **Integration**: Python ecosystem has better tools (Click for CLI, lupa for Lua bridge)
4. **Testing**: Easier to unit-test Python; Lua steps tested via preview comparison

### Why Both Languages?
1. **Separation of concerns**: Disk ops (Lua) don't need to know about packages (Python)
2. **Testability**: Dry-run and preview mode are free (Lua emits steps; Python doesn't execute)
3. **Maintainability**: Changes to step emission don't require Python rebuilds
4. **Performance**: Lua hot-path (step generation) is fast; Python handles orchestration overhead

---

## Module Organization

```
src/kod/
├── kod.py                      # CLI entry point
├── planner.py                  # Step composition
├── bootstrap.py                # Bootstrap-specific
├── context.py                  # Execution context
├── common.py                   # Shared utilities
├── lua_utils.py                # Lua↔Python conversion (unified)
├── config/
│   ├── loader.py              # Config file loading
│   ├── validator.py           # Config validation
│   └── schema.py              # Schema access
└── system/
    ├── generations.py         # Generation lifecycle
    ├── packages.py            # Package state
    ├── boot.py                # Boot management
    ├── users.py               # User management
    └── ...

src/lua/kod/
├── core/
│   ├── schema.lua             # Schema definitions (source of truth)
│   └── bootstrap.lua          # Bootstrap (arch/debian unified)
├── system/
│   ├── filesystem_types.lua   # FS type mappings (source of truth)
│   ├── disk.lua               # Disk helpers
│   └── repos.lua              # Repository management
└── sections/
    ├── devices.lua            # Partitioning/formatting
    ├── boot.lua               # Boot setup
    ├── packages.lua           # Package installation
    ├── services.lua           # Service enablement
    ├── users.lua              # User creation
    ├── desktop.lua            # Desktop setup
    └── programs.lua           # Custom programs
```

---

## Common Refactoring Patterns

See [MAINTENANCE.md](MAINTENANCE.md) for:
- How to add a new filesystem type
- How to add a new config section
- How to add a new installation step
- How to split Lua/Python responsibilities
- How to consolidate duplicated logic

---

## Phase Evolution

This architecture evolved through phases:
- **Phase 1-2**: Initial Python-only codebase
- **Phase 3-4**: Lua planner section introduced
- **Phase 5**: Full Lua section modules for install/rebuild (current)
- **Phase 5b**: Disk partitioning unified (sgdisk everywhere)
- **Phase 5c**: Lua-to-Python consolidation (single conversion function)

Current state: **Clean separation**, **single sources of truth**, **no duplication between layers**.

---

## Gotchas

1. **Lua tables are 1-indexed**: Python arrays are 0-indexed
   - Handled automatically by `lua_table_to_python()` via key detection

2. **Lua nil ≠ Python None**: Lua functions may return nil for missing values
   - Converted to None in `lua_table_to_python()`

3. **Step execution order**: Steps have `order` and `depends_on` fields
   - Planner composes them; execution engine respects ordering
   - See `planner.py:Step` for full spec

4. **Chroot context**: Many steps run in chroot during rebuild
   - Context tracks mount points; see `context.py` for how paths are resolved

---

## Testing Strategy

- **Dry-run**: Run planner without execution; compare generated steps
- **Preview**: JSON output of planned steps vs actual execution
- **Unit tests**: Individual Lua modules (via stub runner)
- **Integration**: Full install/rebuild cycle in isolated test VM

See [TEST.md](TEST.md) (when created) for full testing guide.
