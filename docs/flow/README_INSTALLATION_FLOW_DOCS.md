# KodOS Installation Flow Documentation

This directory contains comprehensive analysis of the KodOS installation and rebuild system.

## Files Created

### 1. **START HERE: INSTALLATION_FLOW_SUMMARY.md**
Quick reference guide covering:
- Entry points and commands
- Install/rebuild flows at a glance
- Package handling pipeline
- All 13 Lua section modules
- Distro adapters
- Debugging tips

**Best for:** Getting started, quick lookups, big picture understanding

### 2. **KODOS_INSTALLATION_FLOW.md**
Detailed comprehensive reference with:
- All 13 installation phases with pseudocode
- Package aggregation (7 sources → 1 deduped list)
- Package type separation (normal/aur/flatpak)
- Step emission for Arch vs Debian
- Lua-Python integration architecture
- Atomic generation swap with rollback
- Error handling and recovery
- Execution order for install and rebuild

**Best for:** Understanding implementation details, tracing complex flows, deep dives

### 3. **INSTALLATION_FLOW_VISUAL.txt**
ASCII flow diagrams showing:
- Install phase (4 steps with tree structure)
- Rebuild phase (6 steps with tree structure)
- Package aggregation tree
- Package separation flows
- Lua-Python interaction diagram
- File location reference

**Best for:** Visual understanding, teaching others, quick navigation

### 4. **INSTALLATION_ANALYSIS_INDEX.md**
Navigation and index with:
- Quick start paths for different questions
- Key concepts explained
- File location reference
- Architecture patterns
- Testing and validation guide
- How to extend KodOS

**Best for:** Finding what you need, navigation, architecture patterns

## Quick Navigation

### "I want to understand the install flow"
1. INSTALLATION_FLOW_SUMMARY.md § "Installation Flow at a Glance"
2. INSTALLATION_FLOW_VISUAL.txt § "INSTALL PHASE"
3. KODOS_INSTALLATION_FLOW.md § "2. INSTALL FLOW"

### "I want to understand package handling"
1. INSTALLATION_FLOW_SUMMARY.md § "Package Handling"
2. INSTALLATION_FLOW_VISUAL.txt § "PACKAGE FLOW"
3. KODOS_INSTALLATION_FLOW.md § "3. PACKAGE HANDLING FLOW"

### "I need to modify code"
1. INSTALLATION_FLOW_SUMMARY.md § "File Locations"
2. KODOS_INSTALLATION_FLOW.md - Use file:line references to locate code
3. Source files for actual implementation

### "Something is broken, help me debug"
1. INSTALLATION_FLOW_SUMMARY.md § "Debugging Tips"
2. INSTALLATION_FLOW_VISUAL.txt - Trace to failure point
3. KODOS_INSTALLATION_FLOW.md § "9. ERROR HANDLING & ROLLBACK"

## Core Concepts

### The Step-Based Architecture
KodOS doesn't execute imperatively. Instead:
1. Config → Lua sections emit step tables
2. Steps are composed into a flat, ordered list
3. Steps are executed in order with hooks and error policies
4. State is stored as JSON snapshots

This allows dry-runs, golden-file testing, and easy debugging.

### Lua-Driven Configuration
- One .lua file describes entire system
- 13 Lua section modules parse config
- Each section emits deterministic steps
- Python orchestrates but doesn't implement config logic

### Generations (Copy-on-Write)
- Each rebuild creates a snapshot
- State files: installed_packages, enabled_services, packages.lock
- Atomic swap with rollback on failure
- System always bootable

## Quick Stats

- **Total Documentation:** ~2,000 lines
- **Python Modules Analyzed:** 11
- **Lua Sections:** 13
- **Main Flows:** Install, Rebuild, Package handling, Error recovery
- **Distro Adapters:** Arch, Debian (3 implementations)

## File Locations in Codebase

### Entry Points
- `src/kod/kod.py:427` - install command
- `src/kod/kod.py:639` - rebuild command
- `src/kod/kod.py:616` - plan command

### Planning & Execution
- `src/kod/planner.py:463` - build_plan, compose_steps_lua
- `src/kod/executor.py:36` - execute_steps
- `src/lua/kod/planning/planner.lua:140` - Lua section loader
- `src/lua/kod/planning/executor.lua:40` - Lua step executor

### Packages
- `src/lua/kod/sections/packages.lua:218` - aggregation
- `src/lua/kod/sections/packages.lua:260` - type separation
- `src/lua/kod/sections/packages.lua:295` - step emission
- `src/kod/system/packages.py:98` - get_packages_to_install

### Distros
- `src/kod/system/distro/base.py` - abstract interface
- `src/kod/system/distro/adapters/arch.py` - Arch implementation
- `src/kod/system/distro/adapters/debian.py` - Debian implementation

### Generation Management
- `src/kod/system/generations.py` - generation operations
- `src/kod/kod.py:156` - atomic generation swap

## Key Data Structures

### Step
```python
@dataclass(frozen=True)
class Step:
    kind: str           # disk|package|service|system|user|program
    name: str           # step identifier
    program: str        # command name
    args: tuple         # command arguments
    chroot: bool        # run inside chroot?
    timeout_s: int      # timeout in seconds
    on_error: str       # abort|warn
    meta: dict          # arbitrary metadata
```

### StepResult
```python
@dataclass(frozen=True)
class StepResult:
    step: Step
    success: bool
    error: Optional[str]
    is_warning: bool    # True if on_error='warn' and failed
```

## Common Patterns

### Section Module (Lua)
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

### Distro Adapter (Python)
```python
class DistroAdapter(ABC):
    @abstractmethod
    def proc_repos(self, conf, current_repos, update, mount_point):
        """Return (repos, repo_packages) dict"""
```

## Testing

### Dry-run preview
```bash
kod plan --baseline empty              # Preview install
kod plan --baseline current            # Preview rebuild
```

### Validate config
```bash
kod config validate -c config.lua      # Check syntax/semantics
kod config schema                      # View schema documentation
```

### Inspect state
```bash
cat /.generation                       # Current generation number
cat /kod/generations/{N}/installed_packages
cat /kod/generations/{N}/packages.lock
```

## Extension Points

### Add a new section
1. Create `src/lua/kod/sections/{name}.lua`
2. Implement `module.emit_steps(config, distro)`
3. Register in `planner.lua` Planner.sections list

### Add a new distro
1. Create `src/kod/system/distro/adapters/{distro}.py`
2. Extend `DistroAdapter` class
3. Register in `distro/factory.py`

### Add new package type (like Flatpak)
1. Extend `packages.lua:aggregate_*_packages()` to extract type
2. Add type filtering in `separate_packages()`
3. Emit steps in `emit_steps()` with appropriate commands

## Related Documents

- Main KodOS README
- Architecture documentation
- Configuration schema reference
- Test suite (tests/test_*.py)

---

**Generated:** 2026-09-23
**Scope:** Complete installation flow analysis
**Depth:** Entry points through distro adapters
