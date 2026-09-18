# KodOS Python Codebase Analysis - Summary

## Overview

The KodOS project is a system installation and management framework for Arch Linux and Debian distributions. It uses a hybrid Python/Lua architecture where Python handles orchestration and Lua handles compute logic.

**Total Python Files:** 36  
**Total Lines:** ~6,500+ LOC  
**Architecture:** Configuration-driven, step-based execution with read-only plan preview  

---

## Core Architecture

### Three Main Pipelines

#### 1. Configuration Pipeline
```
Lua file → Load → Python dict → Validate → Compile → Executable config
           (loader)              (schema)   (depends)   (registry)
```

- **Input:** TOML/Lua configuration files in `/etc/kodos/` or specified path
- **Processing:** 
  - `kod.config.loader` - Parse Lua files to Python dicts
  - `kod.config.validator` - Validate against Lua schema (single source of truth)
  - `kod.config.compiler` - Resolve implicit dependencies (e.g., GNOME → gdm)
- **Output:** Compiled configuration ready for execution

#### 2. Plan Generation Pipeline
```
Config → Parse sections → Call Lua planner → Step list → Render text
         (multiple)         (per distro)                    (preview)
```

- **Input:** Compiled configuration
- **Processing:**
  - `kod.planner` routes to correct Lua planner module
  - Lua planner generates Step objects (kind, name, program, args, meta)
  - Steps include metadata for hooks and error handling
- **Output:** List of Step objects (read-only, no execution)

#### 3. Execution Pipeline
```
Steps → Lua executor → Dispatch → System operations → Results
        (generic)       (Python)    (packages,
                                     services,
                                     filesystem,
                                     users)
```

- **Input:** Step list from planner
- **Processing:**
  - `kod.executor` calls Lua generic runner (kod/lib/executor.lua)
  - Lua runner handles ordering, timeouts, on_error policies
  - Python dispatch layer handles system-specific steps
- **Output:** StepResult list (success/failure, error messages)

---

## Project Organization

### Layered Architecture

```
┌─────────────────────────────────────┐
│  USER INTERFACE (CLI)               │
│  kod.py - Click framework           │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  ORCHESTRATION LAYER                │
│  kod.core - System workflows         │
│  kod.config - Config pipeline        │
│  kod.registry_wrapper - Phase 1/2    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  EXECUTION LAYER                    │
│  kod.planner - Plan builder         │
│  kod.executor - Step runner         │
│  kod.bootstrap - Lua bridge         │
│  kod.hooks - Lifecycle management   │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  SYSTEM OPERATIONS LAYER            │
│  kod.system.* - Packages, services, │
│                 boot, filesystem,   │
│                 users               │
│  kod.system.distro.* - Distro       │
│                         specific    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  FOUNDATION LAYER                   │
│  kod.common - Command exec          │
│  kod.context - Execution context    │
│  kod.lua_runtime - Singleton Lua    │
│  kod.exceptions - Error hierarchy   │
└─────────────────────────────────────┘
```

### Module Categories

**CORE MODULES** (business logic, heavy computation):
- Planner, Executor, Bootstrap, Config validation/compilation, Registry, System operations

**UTILITY MODULES** (support services):
- Command execution, Lua runtime management, Context wrapping, Error handling

**INTERFACE MODULES** (user-facing):
- Main CLI, Registry CLI, Orchestration wrappers

---

## Key Workflows

### Install Workflow
1. Load configuration file (Lua)
2. Convert to Python dict
3. Validate against Lua schema
4. Compile config (resolve dependencies)
5. Build execution plan from empty baseline
6. Execute steps via Lua runner
7. Record generation 0 state (packages, services)

**Use:** `kod install`  
**Baseline:** empty  
**Generation:** 0

### Rebuild Workflow
1. Load current generation state (/.generation, /kod/generations/N/)
2. Load configuration file
3. Compile config
4. Build diff plan (compare against current state)
5. Execute steps (create new generation or update current)
6. Finalize (move subvolumes, update fstab, increment generation)

**Use:** `kod rebuild` or `kod rebuild --new-generation`  
**Baseline:** current  
**Generation:** N (incremented)

### Plan Preview Workflow
1-4. Same as rebuild
5. Render step list as text (golden-file testable)
6. Print to stdout

**Use:** `kod plan`  
**Side effects:** None (read-only)

---

## Critical Components

### 1. Lua Runtime (Singleton)
- **Location:** `kod.lua_runtime.LuaRuntimeManager`
- **Purpose:** Prevent "cannot mix objects from different Lua runtimes" errors
- **Lifetime:** Process lifetime, cleanup on exit via atexit
- **Used by:** Bootstrap, planner, executor, config schema, registry

### 2. Configuration Schema
- **Location:** `kod.config.schema` (loads from `kod/lib/core/schema.lua`)
- **Role:** Single source of truth for all configuration structure
- **Cached:** Lazy-loaded and cached on first access
- **Used by:** Validator, compiler, template generator

### 3. Step Model
- **Location:** `kod.planner.Step` (frozen dataclass)
- **Fields:** kind, name, program, args, chroot, timeout_s, on_error, meta
- **Immutability:** Converted to dict for Lua, then to list of results

### 4. Program Registry
- **Location:** `kod.registry` (with Phase 1/2 wrapper in `kod.registry_wrapper`)
- **Discovery:** Builtin programs (`kod/registry/builtin/`) + user plugins (`~/.kod/plugins/programs/`)
- **Loading:** Lua loader.lua handles inheritance and merging
- **Validation:** JSON schema validation and test execution

### 5. Distro Abstraction
- **Location:** `kod.system.distro.factory` (strategy pattern)
- **Supported:** Arch Linux, Debian
- **Abstracts:** Package managers (pacman vs apt), kernel paths, boot setup

---

## Phase Transitions

### Phase 1/2: Registry Migration
- **Current:** Python registry as fallback
- **Wrapper:** `kod.registry_wrapper` (thin orchestration)
- **Future:** Call Lua registry directly (kod/lib/registry/registry.lua)
- **Impact:** No API change for consumers

### Phase 3: Programs in Config
- **Current:** Config compiler loads and validates programs
- **Status:** Complete
- **Next:** Program hooks attached to steps before execution

### Phase 5c: Lua Schema Authority
- **Current:** Config schema loads from Lua (single source of truth)
- **Status:** Active
- **Benefit:** Eliminates schema duplication between Python and Lua

---

## Design Patterns

1. **Singleton:** `LuaRuntimeManager` prevents runtime mixing
2. **Strategy:** `distro.factory` allows runtime distro selection
3. **Frozen Dataclass:** `Step` ensures immutability
4. **Re-export Hub:** `kod.core` consolidates system operations for clean API
5. **Hook Pattern:** Lifecycle hooks collected before execution, fired during steps
6. **Error Aggregation:** Validator collects all errors, reports comprehensively

---

## Global State Management

| Variable | Location | Purpose |
|----------|----------|---------|
| `use_debug` | `kod.common` | Debug mode (if True, `exec()` prints but doesn't run) |
| `use_verbose` | `kod.common` | Verbose output flag |
| `problems` | `kod.common` | List of accumulated execution problems |
| `_manager` | `kod.lua_runtime` | Global Lua runtime singleton |
| `_lua_schema_cache` | `kod.config.schema` | Cached Lua schema (lazy-loaded) |

---

## Important Implementation Details

### Command Execution
- `kod.common.exec()` handles command execution with error tracking
- In debug mode: prints commands but doesn't execute
- Returns stdout if `get_output=True`, empty string otherwise
- Tracks all failures in global `problems` list

### Chroot Handling
- `kod.common.exec_chroot()` wraps commands in `chroot`
- Used during install/rebuild to target mounted filesystem
- Raw chroot: no additional mounts (host /dev, /proc, /sys are bind-mounted by plan)

### Context Execution
- `kod.context.Context` wraps command execution
- Supports user switching via `su` or direct execution
- Tracks mount point, stage (install/rebuild), and chroot mode

### Lua Integration
- All Lua interaction goes through singleton runtime
- Python→Lua conversion: dicts/lists to Lua tables recursively
- Lua→Python conversion: tables with int keys 1..n become lists, string keys become dicts

---

## File Organization

**Root level:** Main entry points and core infrastructure
- `kod.py` - Click CLI
- `kod.planner.py` - Plan generation
- `kod.executor.py` - Step execution
- `kod.bootstrap.py` - Lua bootstrap bridge
- `kod.common.py` - Command execution utilities

**Subdirectories:**
- `cli/` - CLI command modules
- `config/` - Configuration pipeline
- `core/` - Core workflows and re-exports
- `registry/` - Program registry system
- `system/` - System operations (packages, services, boot, filesystem, users)

**Lua code:**
- `lib/` - Lua library directory (separate from Python)

---

## Typical Usage Flows

### System Administrator: Fresh Install
```bash
kod config validate -c /path/to/config.lua
kod plan -c /path/to/config.lua  # Preview
kod install -c /path/to/config.lua -m /mnt
```

### System Administrator: Update System
```bash
kod plan -c /path/to/config.lua --baseline current
kod rebuild -c /path/to/config.lua
# Or with new generation:
kod rebuild -c /path/to/config.lua --new-generation
```

### User: Rebuild User Config
```bash
kod rebuild-user -c /path/to/config.lua --user alice
```

### Developer: Debug Configuration
```bash
kod config schema --section boot  # Show boot config schema
kod registry list                 # List available programs
kod registry info git             # Show git program details
kod config init --distro arch     # Generate template
```

---

## Dependencies

**External Libraries:**
- `click` - CLI framework
- `lupa` - Lua/Python interoperability
- `pathlib` - Path manipulation (stdlib)
- `subprocess` - Command execution (stdlib)
- `json` - JSON parsing (stdlib)

**Internal Dependencies:**
- All Python modules depend on `kod.common` (command execution)
- All Lua integration depends on `kod.lua_runtime`
- Execution workflows depend on `kod.planner` and `kod.executor`

---

## Code Statistics

| Module | Lines | Purpose |
|--------|-------|---------|
| kod.py | 748 | Main CLI interface |
| kod.system.packages | 582 | Package management |
| kod.registry.programs | 527 | Program definitions |
| kod.planner | 412 | Plan generation |
| kod.config.validator | 595 | Config validation |
| kod.registry.loader | 254 | Plugin loading |
| kod.config.compiler | 260 | Dependency resolution |
| Others | ~1500 | Utilities and system ops |
| **TOTAL** | **~6500+** | **36 Python files** |

---

## Next Steps for Understanding

1. **For CLI usage:** Read `kod.py` and understand Click command structure
2. **For config pipeline:** Follow `kod.config` modules in order: loader → schema → validator → compiler
3. **For execution:** Understand `kod.planner` Step model, then `kod.executor` dispatch
4. **For distro support:** Study `kod.system.distro.factory` pattern and specific implementations
5. **For registry:** Study `kod.registry.programs` Program class, then `kod.registry.loader`

---

## Known Simplifications (marked with ponytail comments)

1. **Global lock on Lua runtime** - Prevents concurrent execution, upgrade to per-account locks if throughput matters
2. **Naive O(n²) schema validation** - Works fine for current config sizes, upgrade if schema grows large
3. **Distro selection at module init** - Currently supports only Arch (Debian present but less tested)
4. **Privilege level mapping** - Legacy `run_as_root` boolean mapping to new `privilege_level` field

---

Generated: 2026-09-18
Codebase Version: Phase 3 Complete, Phase 5c Active
Total Files Analyzed: 36 Python modules
