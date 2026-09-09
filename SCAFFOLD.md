# Kodos Architecture Redesign - Implementation Scaffold

This directory contains the refactored codebase for the Kodos architecture redesign (Phases 1-5).

See `docs/superpowers/specs/2026-09-09-architecture-redesign.md` for the full specification.

## Review & Design Documents

Before implementing, read these materials:

- **`REVIEW.md`** — Comprehensive review of spec and scaffold
  - Architecture coherence assessment
  - Missing pieces and how to fix them
  - Implementation readiness (B grade: ready with pre-work)
  - Critical issues to resolve before Phase 2

- **`docs/cli-architecture.md`** — CLI design and command structure
  - Recommended: subcommand groups (config, install, registry, package)
  - Framework options (Click or Argparse)
  - Phase 1 deliverable

- **`docs/phase3-plugins.md`** — Plugin loading and validation
  - Error scenarios (syntax, conflicts, cycles)
  - Plugin schema definition
  - Logging and user-facing error messages
  - Testing strategy

- **`docs/phase5-security.md`** — Custom package security model
  - Threat model (upstream compromise, trojanized templates)
  - MVP approach: source hash verification + user approval
  - Audit logging and cache integrity
  - User workflows and best practices

## Directory Structure

```
src/kod/
├── config/           Phase 1: Configuration System
│   ├── __init__.py
│   ├── schema.py     Schema definition & validation
│   ├── validator.py  Configuration validator
│   ├── loader.py     Lua config loader
│   └── compiler.py   Dependency resolution & compilation
│
├── core/             Phase 2: Python Refactoring
│   ├── __init__.py
│   ├── install.py    Installation workflow
│   ├── rebuild.py    Rebuild workflow
│   └── user_config.py User configuration
│
├── system/           Phase 2: System Operations
│   ├── __init__.py
│   ├── packages.py   Package management
│   ├── packages_custom.py  Custom packages (Phase 5)
│   ├── services.py   Service management
│   └── boot.py       Boot configuration
│
├── registry/         Phase 3: Program Registry
│   ├── __init__.py
│   ├── programs.py   Builtin program definitions
│   ├── loader.py     Plugin loader
│   └── build_templates.py  Build templates (Phase 5)
│
├── (legacy files)    Gradual migration from existing
│   ├── core.py       Old monolithic core (to be refactored)
│   ├── arch.py       Distro-specific (to be updated)
│   ├── debian.py     Distro-specific (to be updated)
│   └── ...
```

## Implementation Phases

### Phase 1: Configuration System (Weeks 1-2)
- [x] Implement `kod/config/schema.py` — Schema definition
- [x] Implement `kod/config/validator.py` — Validation logic
- [x] Implement `kod/config/loader.py` — Lua config loading
- [x] Implement `kod/config/compiler.py` — Dependency resolution
- [x] Write tests for config system (validator + loader + compiler + CLI)
- [x] CLI: `kod config validate`
- [x] CLI: `kod config --schema`, `kod config compile`

**Success Criteria:**
- ✅ `kod config validate -c example/testvm` catches errors upfront
- ✅ `kod config compile -c example/testvm` resolves dependencies
- ✅ `kod config --schema` shows available options
- ✅ 21 tests passing (validator, loader, compiler, CLI)

### Phase 2: Python Refactoring (Weeks 3-5)

**Phase 2a (COMPLETE):** Module extraction with backward compatibility
- [x] Create `kod/core/` module split
- [x] Implement `kod/core/install.py` — Installation orchestration (wrapped)
- [x] Implement `kod/core/rebuild.py` — Rebuild orchestration (wrapped)
- [x] Implement `kod/core/user_config.py` — User management (wrapped)
- [x] Create `kod/system/packages.py` — Package manager (wrapped)
- [x] Create `kod/system/services.py` — Service manager (wrapped)
- [x] Create `kod/system/boot.py` — Boot manager (wrapped)
- [x] Create `kod/system/filesystem.py` — Filesystem manager (wrapped)
- [x] Create `kod/system/users.py` — User manager (wrapped)

**Phase 2b (COMPLETE):** Move implementations from _core.py to new modules
- [x] Move `kod/system/filesystem.py` implementations
- [x] Move `kod/system/users.py` implementations
- [x] Move `kod/system/services.py` implementations
- [x] Move `kod/system/boot.py` implementations
- [x] Move `kod/system/packages.py` implementations
- [x] Move `kod/core/rebuild.py` implementations
- [x] Move `kod/core/user_config.py` implementations
- [x] Move `kod/core/install.py` implementation (main orchestrator)
- [x] Cleanup `_core.py` re-export layer
- [x] Final verification and testing

**Success Criteria (Phase 2 - ACHIEVED):**
- ✅ New module structure in place (workflows + operations)
- ✅ 8 new modules created with backward-compatible wrappers
- ✅ All existing tests still pass (59 passed, 10 skipped, 1 pre-existing failure)
- ✅ Import paths work for both old and new styles
- ✅ Phase 2b: All implementations moved, _core.py reduced from 2,054 → 563 lines (73% reduction)
- ✅ Full backward compatibility: both old `from kod.core import X` and new `from kod.system.X import Y` work

### Phase 3: Program Registry (Week 6)
- [x] Implement `kod/registry/programs.py` — Builtin programs (git, neovim, syncthing, etc.)
- [x] Implement `kod/registry/loader.py` — Plugin discovery & loading
- [x] Write plugin loading tests
- [x] CLI: `kod registry list`, `kod registry info <name>`

**Success Criteria (COMPLETE):**
- ✅ Users can define custom programs in `~/.kod/plugins/programs/`
- ✅ Builtin programs have schemas and config generators
- ✅ Comprehensive extending guide at `docs/extending.md`
- ✅ Example custom program at `docs/examples/custom_program.lua`
- ✅ Program Registry section added to README.md

### Phase 4: Polish & Docs (Week 7)
- [ ] Update README with new examples
- [ ] Write "Extending Kodos" guide
- [ ] Add CLI help for new commands
- [ ] Run full integration tests
- [ ] Remove dead code and legacy files
- [ ] Clean up error messages

**Success Criteria:**
- All tests pass
- Docs are clear
- No regressions: `kod install` and `kod rebuild` work end-to-end

### Phase 5: Custom Package Support (Weeks 8-9)
- [ ] Implement `kod/registry/build_templates.py` — Build templates
- [ ] Extend `kod/config/schema.py` — Custom package schema
- [ ] Implement `kod/system/packages_custom.py` — Custom package builder
- [ ] Implement package caching and metadata
- [ ] Plugin system for custom templates
- [ ] CLI: `kod package build`, `kod package list`, `kod package cache --clean`

**Success Criteria:**
- Users can define custom packages in config
- Packages build and cache correctly
- Custom templates loadable from `~/.kod/plugins/build_templates/`

## File Status

| File | Status | Notes |
|------|--------|-------|
| `config/__init__.py` | ✅ Created | Phase 1 placeholder |
| `config/schema.py` | ✅ Implemented | Top-level option types (validated against real configs) |
| `config/validator.py` | ✅ Implemented | Typo detection + type checks, handles lupa LuaTables |
| `config/loader.py` | ✅ Implemented | Converts Lua tables to Python dicts, preserves arrays |
| `config/compiler.py` | ✅ Implemented | Desktop manager → display manager dependencies |
| ~~`core/` package~~ | ⚠️ Removed | Name collision: shadows old `core.py`. Recreate in Phase 2 when core.py is split |
| `system/__init__.py` | ✅ Created | Phase 2 placeholder |
| `system/packages.py` | ✅ Created | To be implemented |
| `system/services.py` | ✅ Created | To be implemented |
| `system/boot.py` | ✅ Created | To be implemented |
| `system/users.py` | ✅ Created | To be implemented |
| `system/filesystem.py` | ✅ Created | To be implemented |
| `system/packages_custom.py` | ✅ Created | To be implemented (Phase 5) |
| `registry/__init__.py` | ✅ Created | Phase 3 placeholder |
| `registry/programs.py` | ✅ Created | To be implemented |
| `registry/loader.py` | ✅ Created | To be implemented |
| `registry/build_templates.py` | ✅ Created | To be implemented (Phase 5) |
| `exceptions.py` | ✅ Created | Exception hierarchy (Phases 1-5) |
| `distributions/base.py` | ✅ Created | Base class for distro implementations |
| `core.py` | ⏳ Existing | Gradual refactoring → new modules |
| `arch.py` | ⏳ Existing | To be updated for new structure |
| `debian.py` | ⏳ Existing | To be updated for new structure |

## Next Steps

1. **Phase 1 starts:** Implement config system
   - Read `kod/config/schema.py` and fill in the implementation
   - Add unit tests in `tests/test_config.py`

2. **Create tests directory:**
   ```bash
   mkdir -p tests/{config,core,system,registry}
   ```

3. **Track progress:** Update this scaffold as implementations complete

4. **Backward compatibility:** Keep old code working while refactoring

## Git Workflow

- Main branch: `main`
- Feature branch: `feat/architecture-redesign`
- Implementation PRs: One per phase or component

Status:
- ✅ Architecture spec approved
- ✅ Scaffold created
- ⏳ Implementation begins with Phase 1
