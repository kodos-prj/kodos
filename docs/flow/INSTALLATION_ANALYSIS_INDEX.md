# KodOS Installation Flow Analysis - Index

## Overview

This directory contains comprehensive documentation of the KodOS installation and rebuild architecture, with focus on:
- Main entry points and CLI commands
- Complete execution flow (planning → execution)
- Lua-Python integration layer
- Package handling (normal, AUR, flatpak)
- Service and system configuration
- Error handling and rollback mechanisms
- Generation management and state storage

## Files in This Analysis

### 1. INSTALLATION_FLOW_SUMMARY.md
**Start here** for quick navigation and overview.
- Entry points and main commands
- Install/rebuild flow at a glance
- Package handling (aggregation, separation, emission)
- Section modules overview
- Distro adapters
- Generation management
- Debugging tips

**Use this for**: Quick reference, big picture understanding, quick lookups

### 2. KODOS_INSTALLATION_FLOW.md
Complete detailed breakdown of all flows.
- 13 main sections covering each major phase
- Detailed pseudocode/call flows for both install and rebuild
- Package aggregation details (7 sources → single deduped list)
- Package type separation (normal/aur/flatpak)
- Install step emission for Arch vs Debian
- Lua-Python integration architecture
- Service and system configuration flows
- Distro-specific package flows (Arch vs Debian)
- User and dotfiles configuration
- Error handling, rollback, and cleanup
- Configuration schema flow
- Key data structures (Step, StepResult)
- Execution order for install and rebuild phases

**Use this for**: Deep understanding, implementation details, trace complex flows

### 3. INSTALLATION_FLOW_VISUAL.txt
ASCII flow diagrams showing execution paths.
- Install phase flowchart (4 main steps)
- Rebuild phase flowchart (6 main steps)
- Package aggregation tree
- Package separation and emission diagram
- Lua-Python interaction diagram
- File location reference

**Use this for**: Visual understanding, quick flow tracing, teaching others

## Quick Start Paths

### "I want to understand the install flow"
1. Read: INSTALLATION_FLOW_SUMMARY.md § "Installation Flow at a Glance"
2. View: INSTALLATION_FLOW_VISUAL.txt § "INSTALL PHASE"
3. Deep dive: KODOS_INSTALLATION_FLOW.md § "2. INSTALL FLOW"

### "I want to understand package handling"
1. Start: INSTALLATION_FLOW_SUMMARY.md § "Package Handling (Normal vs AUR vs Flatpak)"
2. Visual: INSTALLATION_FLOW_VISUAL.txt § "PACKAGE FLOW - AGGREGATION DETAIL"
3. Deep dive: KODOS_INSTALLATION_FLOW.md § "3. PACKAGE HANDLING FLOW"

### "I need to modify Lua sections"
1. Overview: INSTALLATION_FLOW_SUMMARY.md § "Section Modules (All 13)"
2. Details: KODOS_INSTALLATION_FLOW.md § "2. INSTALL FLOW" → "**Section Modules**"
3. Code: Check src/lua/kod/sections/{section_name}.lua

### "I need to add a new feature"
1. Understand: INSTALLATION_FLOW_SUMMARY.md § "Core Architecture"
2. Trace flow: Use INSTALLATION_FLOW_VISUAL.txt to find where feature fits
3. Implementation: Add step emission in relevant Lua section or extend distro adapter

### "The install/rebuild failed, debugging"
1. Check: INSTALLATION_FLOW_SUMMARY.md § "Debugging Tips"
2. Understand error context: 
   - Install failures → KODOS_INSTALLATION_FLOW.md § "4. POST-INSTALL FINALIZATION"
   - Rebuild failures → KODOS_INSTALLATION_FLOW.md § "6. STATE UPDATE & GENERATION SWAP"
3. Review error handling: KODOS_INSTALLATION_FLOW.md § "9. ERROR HANDLING & ROLLBACK"

## Key Concepts

### Step-Based Execution Model
KodOS doesn't execute code imperatively; it:
1. Composes a flat list of deterministic "Steps"
2. Serializes the plan (can preview via `kod plan`)
3. Executes steps in order with hooks and error policies
4. Stores state (packages, services) as JSON snapshots

This allows:
- Dry-runs and previews
- Deterministic, reproducible builds
- Golden-file testing of plans
- Easy debugging (inspect each step)

### Lua-Driven Configuration
All system configuration is declarative Lua tables:
- One .lua file describes entire system
- Lua modules (13 sections) parse config and emit steps
- Python orchestrates but doesn't implement configuration logic
- Allows complex logic (conditionals, loops) in config

### Generations (Copy-on-Write)
Each rebuild creates a new "generation" snapshot:
- Current system = generation N
- Rebuilds → generation N+1
- Can rollback to previous generation
- Atomic swap ensures system always bootable

### Distro Abstraction
Distro-specific logic isolated in adapters:
- Base class defines interface (proc_repos, refresh_package_db, etc.)
- Arch implementation handles pacman, yay, AUR
- Debian implementation handles apt, PPA, no AUR
- Easy to add new distros

## File Locations (Quick Reference)

### Main Entry
- **src/kod/kod.py:427-551** - install command
- **src/kod/kod.py:639-845** - rebuild command
- **src/kod/kod.py:616** - plan command

### Planning
- **src/kod/planner.py:394-461** - build_plan, compose_steps_lua
- **src/lua/kod/planning/planner.lua:140-206** - section loader & composer
- **src/lua/kod/planning/rebuild.lua:41-184** - rebuild diff planner

### Execution
- **src/kod/executor.py:36-113** - step executor controller
- **src/lua/kod/planning/executor.lua:40-99** - step runner (Lua)

### Packages
- **src/lua/kod/sections/packages.lua:218-241** - aggregation
- **src/lua/kod/sections/packages.lua:260-281** - type separation
- **src/lua/kod/sections/packages.lua:295-419** - step emission
- **src/kod/system/packages.py:98-145** - get_packages_to_install

### Distros
- **src/kod/system/distro/base.py** - abstract adapter interface
- **src/kod/system/distro/adapters/arch.py** - Arch implementation
- **src/kod/system/distro/adapters/debian.py** - Debian implementation

### Generation Management
- **src/kod/system/generations.py** - generation operations
- **src/kod/kod.py:156-267** - _swap_generations_atomic (critical)

### State Management
- **src/kod/system/packages.py:148+** - load_repos, load_packages_services, store_packages_services
- **src/kod/system/services.py:14-48** - get_services_to_enable

## Architecture Patterns

### Section Module (Lua)
```lua
local module = {
    schema = Schema.section_name,
    emit_steps = function(config, distro)
        return {...}  -- array of step tables
    end
}
return module
```

All 13 sections follow this pattern. Special case: packages.lua receives full config.

### Distro Adapter (Python)
```python
class DistroAdapter(ABC):
    @abstractmethod
    def proc_repos(self, conf, current_repos, update, mount_point):
        """Return (repos, repo_packages) dict"""
    
    @abstractmethod
    def generate_package_lock(self, mount_point, state_path):
        """Write packages.lock JSON"""
```

### Step Composition (Lua→Python)
```python
lua_steps = planner_module.compose(config_lua, distro)
steps = [_convert_lua_step_to_step(lua_step) for lua_step in lua_steps]
```

### Execution (Python→Lua)
```python
execute_steps(steps, env, mount_point, use_chroot)
  ↓
lua.require("kod.planning.executor")
  ↓
module.run(steps_lua, ctx_lua, dispatch_lua, hooks_lua)
```

## Testing & Validation

### Dry-Run
```bash
kod plan --baseline empty              # Preview install
kod plan --baseline current            # Preview rebuild
```

### Validation
```bash
kod config validate -c config.lua      # Check config syntax/semantics
kod config schema                      # View schema documentation
```

### State Inspection
```bash
cat /.generation                       # Current generation number
cat /kod/generations/{N}/installed_packages
cat /kod/generations/{N}/enabled_services
cat /kod/generations/{N}/packages.lock
```

## Known Issues & Limitations

1. **Lua-Python serialization**: lupa's LuaTable conversion can be slow with large configs
2. **Step output capture**: lupa disables io.popen, so no stdout/stderr capture from steps
3. **Error messages**: Lua errors don't always have full stack traces
4. **AUR builds**: Only works on Arch; Debian has no equivalent

## Extending KodOS

### Adding a new section
1. Create src/lua/kod/sections/{name}.lua
2. Implement module with schema and emit_steps()
3. Register in planner.lua Planner.sections list
4. Add entries to config schema

### Adding a new package type (like Flatpak)
1. Extend packages.lua:aggregate_*_packages() to extract flatpak: packages
2. Add flatpak: prefix filtering in separate_packages()
3. Emit steps in emit_steps() with flatpak install commands

### Supporting a new distro
1. Create src/kod/system/distro/adapters/{distro}.py
2. Extend DistroAdapter with distro-specific methods
3. Register in distro/factory.py get_distro_module()
4. Test proc_repos, refresh_package_db, generate_package_lock

## Document Statistics

- **INSTALLATION_FLOW_SUMMARY.md**: ~400 lines, quick reference format
- **KODOS_INSTALLATION_FLOW.md**: ~600 lines, detailed breakdown
- **INSTALLATION_FLOW_VISUAL.txt**: ~300 lines, ASCII diagrams
- **This file**: ~450 lines, index and navigation

Total: ~1800 lines of documentation

## Last Updated

**Date**: 2026-09-23
**Analyzed**: KodOS codebase (src/kod, src/lua)
**Scope**: Installation, rebuild, and package handling flows
**Depth**: Entry points through distro adapters, Lua-Python interop, atomic swaps

