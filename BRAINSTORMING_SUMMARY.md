# Architecture Redesign Brainstorming - Summary

**Session Date:** 2026-09-09  
**Deliverables:** Comprehensive design spec + implementation plan  
**Branch:** `feat/architecture-redesign`  
**Status:** Ready for implementation

---

## What We Did

### 1. Identified Your Top 3 Priorities

From your codebase, you care most about:

1. **Python structure** — core.py is 2,038 lines with unclear boundaries
2. **Runtime performance** — distributed as `uv run kod`, not a binary; also config compilation during install
3. **Config complexity** — single .lua file, ad-hoc program configs, hard to extend

### 2. Designed Solutions for Each

#### Priority 1: Python Structure

**Problem:** core.py does install, rebuild, user-config, package mgmt, boot, services, filesystem all in one file.

**Solution:** Split by responsibility into focused modules:
- `kod/core/` — Orchestration (install.py, rebuild.py, user_config.py)
- `kod/system/` — System operations (packages.py, services.py, users.py, boot.py, filesystem.py)
- `kod/config/` — Config handling (loader, compiler, validator, schema)
- `kod/distributions/` — Distribution-specific (arch.py, debian.py, base.py)
- `kod/registry/` — Program definitions and plugins

**Impact:** Each file ~200-400 lines, testable in isolation, clear data flow

#### Priority 2: Runtime Performance

**Problem:** 
- CLI runs as `uv run kod` (2-3 second startup overhead)
- Config validation happens during install (hours wasted if config is wrong)

**Solutions:**
- Deferred: Binary distribution (PyInstaller) useful but not urgent
- Immediate: Add compilation phase before execution — validate config in seconds, not hours
- Enables: Pre-flight error detection, better UX

#### Priority 3: Config Complexity

**Problem:**
- One 300-line configuration.lua file with everything
- Program configs are Lua helper functions (users must know Lua)
- No module system, no schema, no extensibility

**Solutions:**
- **Modular imports:** Split config into modules (base, hardware, desktop, users) like NixOS
- **Declarative schema:** All options defined upfront with types, defaults, docs
- **Implicit dependencies:** Enabling GNOME auto-enables gdm, pulls in fonts
- **Program registry:** Central definition of available programs (git, neovim, syncthing, etc.)
- **Plugin system:** Users add custom programs by dropping .py files in `~/.kod/plugins/`

---

## Design Highlights

### NixOS-Style Configuration

**Before:**
```lua
return {
  repos = { ... },
  devices = { ... },
  boot = { ... },
  hardware = { ... },
  -- ... 300 lines in one file
}
```

**After:**
```lua
return {
  imports = {
    "modules/base",
    "modules/desktop/gnome",
    "modules/users/demo",
  },
  config = {
    hostname = "my-vm",
  }
}

-- modules/base/default.lua
return { config = { boot.kernel.package = "linux-lts", ... } }

-- modules/desktop/gnome.lua
return { config = { desktop.gnome.enable = true, ... } }
```

### Compilation Phase

**Before:** Install → Config parsing → Error at step 347 of 500 (4 hours wasted)

**After:** 
```
kod install -c config/
↓ Phase 1: Load config (parse Lua)
↓ Phase 2: Compile config (resolve modules, deps, defaults)
↓ Phase 3: Validate config (check types, constraints)
✓ Ready to execute (or error in seconds)
↓ Phase 4: Execute installation
```

### Program Registry

**Before:**
```lua
programs = {
  git = configs.git({ user_name = "...", user_email = "..." }),
  syncthing = configs.syncthing({ ... }),
}
```
(Users need to know Lua helper functions exist)

**After:**
```lua
programs = {
  git = {
    enable = true,
    user_name = "Demo",
    user_email = "demo@example.com",
  },
  syncthing = {
    enable = true,
    gui_address = "0.0.0.0:8384",
  },
}
```
(Declarative, discoverable, extensible)

---

## Concrete Deliverables

### 1. Specification Document
**File:** `docs/superpowers/specs/2026-09-09-architecture-redesign.md` (1,375 lines)

Covers:
- Problem analysis for each priority
- Layered architecture with diagrams
- Complete file/module breakdown with example code
- Configuration system design (imports, schema, compiler)
- Python module refactoring (system, core, distributions, registry)
- Error handling overhaul
- Testing strategy (unit + integration)
- 4 implementation phases with success criteria
- Backward compatibility path
- Risk analysis

### 2. Implementation Plan
**File:** `ARCHITECTURE_REDESIGN_PLAN.md`

Quick reference:
- Timeline (7 weeks across 4 phases)
- Next steps (review spec, request changes, approve)
- Key design decisions with rationale
- Files to be changed per phase

### 3. Development Branch
**Branch:** `feat/architecture-redesign`

Ready to start implementation whenever you approve.

---

## Implementation Phases

### Phase 1: Configuration System (Weeks 1-2)
**Goals:** Modular imports, schema validation, upfront error detection

**Deliverables:**
- `kod/config/schema.py` — Option definitions, types, defaults
- `kod/config/loader.py` — Load Lua, resolve imports
- `kod/config/compiler.py` — Flatten modules, compute dependencies
- `kod/config/validator.py` — Type-check against schema
- CLI: `kod config validate -c example/testvm`
- Unit tests for all above
- Backward compatibility maintained

**Success:** Config errors caught in seconds; users can run `kod config validate` before `kod install`

### Phase 2: Python Refactoring (Weeks 3-5)
**Goals:** Split core.py into focused modules

**Deliverables:**
- `kod/core/install.py`, `rebuild.py`, `user_config.py` (~150 lines each)
- `kod/system/packages.py`, `services.py`, `users.py`, `boot.py` (~100-150 lines each)
- `kod/distributions/base.py`, `arch.py`, `debian.py` (refactored)
- Error handling overhauled (structured exceptions)
- Unit tests per module
- Integration tests for workflows

**Success:** core.py is gone; each module < 400 lines; tests pass; no regressions

### Phase 3: Program Registry (Week 6)
**Goals:** Extensible, plugin-based program definitions

**Deliverables:**
- `kod/registry/programs.py` — Builtin program definitions (git, neovim, syncthing, etc.)
- `kod/registry/loader.py` — Plugin discovery from `~/.kod/plugins/`
- Unit tests
- Example plugin

**Success:** Users can add custom programs without modifying Kodos source

### Phase 4: Polish (Week 7)
**Goals:** Documentation, cleanup, final testing

**Deliverables:**
- Updated README with new config examples
- Extending guide (adding programs, modules)
- New CLI help text
- Remove dead code, simplify error messages
- Full test suite passing

**Success:** All tests pass, docs are clear, no regressions from current behavior

---

## Why This Design

### Alignment with Your Goals

✅ **Clear module boundaries** — Each file has one responsibility; easy to find code  
✅ **Testable in isolation** — Mock filesystem, packages, services separately  
✅ **Extensible** — Plugin system for programs, plugin system for modules  
✅ **NixOS-style** — Modular configs, declarative schema, implicit deps  
✅ **Backward compatible** — Existing configs still work during migration  
✅ **Performance win** — Config validation upfront, catches errors fast  

### What Gets Deleted

- Dead exception classes (CommandTimeoutError, UnsafeCommandError)
- Global `problems` list (fragile, replaced with exceptions)
- Trivial Path wrappers (exposed to Lua, no longer needed)
- 25 lines of commented-out config switching
- ~120 lines total of cruft removed

### What Gets Added

- Schema system (clear, discoverable options)
- Config compiler (implicit dependency resolution)
- Program registry (extensible without code changes)
- Focused modules (easier to understand and test)
- Plugin system (users add features without modifying source)

---

## Next Steps

### For You

1. **Review the specification** — Read `docs/superpowers/specs/2026-09-09-architecture-redesign.md`
2. **Request changes** if needed — Specific sections, trade-offs, priorities
3. **Approve** to proceed with implementation

### Then

Once approved, I can start **Phase 1** (configuration system) immediately:
- Build schema + validator + compiler
- Add CLI commands (`kod config validate`, `kod config --schema`)
- Write unit tests
- Maintain backward compatibility

---

## Assumptions Made

- **Lua stays as config language** — You like it; good fit for this use case
- **Backward compatibility matters** — Old configs must work during migration
- **Performance bottleneck is config validation time** — Hours wasted debugging invalid configs; upfront validation helps
- **Extensibility matters** — Users want to add programs, modules without touching source
- **Binary distribution deferred** — `uv run kod` is acceptable; focus on code structure first

---

## Questions?

- Does the design match your vision?
- Any sections to adjust or clarify?
- Preferred order (config system first, Python refactoring first, or parallel)?
- Ready to start Phase 1?

**The specification is complete and ready for review. Next step is your approval.**
