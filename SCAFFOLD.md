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
- [ ] Implement `kod/config/schema.py` — Schema definition
- [ ] Implement `kod/config/validator.py` — Validation logic
- [ ] Implement `kod/config/loader.py` — Lua config loading
- [ ] Implement `kod/config/compiler.py` — Dependency resolution
- [ ] Write tests for config system
- [ ] CLI: `kod config --schema`, `kod config validate`, `kod config compile`

**Success Criteria:**
- `kod config validate -c example/testvm` catches errors upfront
- Module imports work
- Dependency implications resolved (GNOME → gdm)

### Phase 2: Python Refactoring (Weeks 3-5)
- [ ] Create `kod/core/` module split
- [ ] Implement `kod/core/install.py` — Installation orchestration
- [ ] Implement `kod/core/rebuild.py` — Rebuild orchestration
- [ ] Implement `kod/core/user_config.py` — User management
- [ ] Create `kod/system/packages.py` — Package manager
- [ ] Create `kod/system/services.py` — Service manager
- [ ] Create `kod/system/boot.py` — Boot manager
- [ ] Update `arch.py` and `debian.py` to use Distribution base class
- [ ] Replace global error handling with structured exceptions
- [ ] Write tests for each module

**Success Criteria:**
- All existing functionality works (tests pass)
- Code is clearer and more modular
- Error handling uses exceptions (no global problems list)

### Phase 3: Program Registry (Week 6)
- [ ] Implement `kod/registry/programs.py` — Builtin programs (git, neovim, syncthing, etc.)
- [ ] Implement `kod/registry/loader.py` — Plugin discovery & loading
- [ ] Write plugin loading tests
- [ ] CLI: `kod registry list`, `kod registry info <name>`

**Success Criteria:**
- Users can define custom programs in `~/.kod/plugins/programs/`
- Builtin programs have schemas and config generators

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
| `config/schema.py` | ✅ Created | To be implemented |
| `config/validator.py` | ✅ Created | To be implemented |
| `config/loader.py` | ✅ Created | To be implemented |
| `config/compiler.py` | ✅ Created | To be implemented |
| `core/__init__.py` | ✅ Created | Phase 2 placeholder |
| `core/install.py` | ✅ Created | To be implemented |
| `core/rebuild.py` | ✅ Created | To be implemented |
| `core/user_config.py` | ✅ Created | To be implemented |
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
