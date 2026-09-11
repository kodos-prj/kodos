# Phase 5d: Structured Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 5d structured schema extensions with nested feature blocks for users, clarified desktop config, and namespaced service customization—enabling eszkoz and future production systems.

**Architecture:** Phase 5d implements nested feature blocks layerwise: (1) expand schema with block definitions, (2) create section modules for new features, (3) extend section emit_steps logic, (4) integrate into planner/validator, (5) comprehensive testing with eszkoz as primary test case.

**Tech Stack:** Lua (schema, section modules), Python 3.12+ (validator), lupa (Lua interpreter), pytest (testing)

**Spec:** `docs/superpowers/specs/2026-09-11-phase-5d-structured-schema-design.md` (approved design document)

## Global Constraints

- Maintain backward compatibility with Phase 5c schema
- All new fields/blocks optional (existing configs still work)
- No breaking changes to existing APIs
- Follow Phase 5c code style and patterns (Lua + Python)
- Schema is single source of truth (Lua first, Python derives)
- Nested feature blocks group related concerns
- Minimum test coverage: 541+ Phase 5c tests pass + 100+ new Phase 5d tests
- eszkoz config as primary integration test (validates entire system)

---

## File Structure & Decomposition

### Lua Schema & Sections (Core)
- `src/kod/lib/schema.lua` — MODIFY: Add nested block definitions to schema
- `src/kod/sections/boot.lua` — MODIFY: Support loader.include field
- `src/kod/sections/hardware.lua` — MODIFY: Add sane block support
- `src/kod/sections/users.lua` — MODIFY: Handle shell field (already exists)
- `src/kod/sections/users-advanced.lua` — NEW: Handle identity/ssh_keys/dotfiles blocks
- `src/kod/sections/dotfiles.lua` — NEW: Dotfile deployment logic
- `src/kod/sections/ssh-keys.lua` — NEW: SSH key setup logic
- `src/kod/sections/desktop.lua` — MODIFY: Support environments (rename from desktop_manager)
- `src/kod/sections/fonts.lua` — MODIFY: Support font_dir + packages
- `src/kod/sections/services.lua` — MODIFY: Support config block structure + systemd service

### Python Validator & Integration (Core)
- `src/kod/config/validator.py` — MODIFY: Validate nested blocks, config structures, all types
- `src/kod/planner.py` — MODIFY: Merge user-level programs/services into global
- `src/kod/bootstrap.py` — MODIFY: Support all new features end-to-end

### Tests (Comprehensive)
- `tests/test_phase5d_schema.py` — NEW: Schema validation for all block types
- `tests/test_phase5d_sections.lua` — NEW: Lua section tests for new features
- `tests/test_phase5d_integration.py` — NEW: End-to-end integration with eszkoz

### Documentation
- `docs/PHASE-5D-STRUCTURED-DESIGN.md` — NEW: Overview of Phase 5d architecture
- `docs/ADVANCED-USER-CONFIG.md` — NEW: Guide to user identity/ssh_keys/dotfiles blocks
- `docs/DESKTOP-ENVIRONMENTS.md` — NEW: Multi-environment configuration
- `docs/SERVICE-CUSTOMIZATION.md` — NEW: Service config block guide

---

## Task Decomposition

### Task 1: Expand Schema (Lua) — Core Nested Definitions

**Files:**
- Modify: `src/kod/lib/schema.lua`
- Test: `tests/test_phase5d_schema.py`

**Interfaces:**
- Consumes: Phase 5c schema (all 13 sections)
- Produces: Extended schema with nested blocks:
  - `users.USERNAME.identity` (name, hashed_password, groups)
  - `users.USERNAME.ssh_keys` (enabled, authorized[])
  - `users.USERNAME.dotfiles` (repo_url, source_dir, deploy_tool)
  - `users.USERNAME.programs` (nested program configs)
  - `users.USERNAME.services` (nested service configs)
  - `users.USERNAME.home_config` (dotfiles_repos[])
  - `desktop.display_manager` (string enum)
  - `desktop.environments` (gnome, plasma, cosmic, budgie, pantheon)
  - `services.<name>.config` (service_name, packages, settings)
  - `services.systemd` (mounts, units)
  - `boot.loader.include` (list)
  - `hardware.sane` (enable, extra_packages)
  - `fonts.font_dir`, `fonts.packages`

**Acceptance Criteria:**
- All nested block definitions in schema with proper types
- All new fields are optional
- Schema validates in Lua without errors
- Phase 5c schema fields unchanged
- Block definitions have clear documentation strings

---

### Task 2: Extend Boot Section — Bootloader Include

**Files:**
- Modify: `src/kod/sections/boot.lua`
- Test: `tests/test_phase5d_sections.lua` (boot tests)

**Interfaces:**
- Consumes: Schema with `boot.loader.include` field (list of strings)
- Produces: Steps for bootloader entry configuration
  - Step: `boot_loader_include_<entry_name>` (one per include)

**Acceptance Criteria:**
- Boot section loads without errors
- `emit_steps()` generates include steps when field present
- Backward compatible (no include steps when field absent)
- Works with systemd-boot and grub

---

### Task 3: Extend Hardware Section — SANE Support

**Files:**
- Modify: `src/kod/sections/hardware.lua`
- Test: `tests/test_phase5d_sections.lua` (hardware tests)

**Interfaces:**
- Consumes: Schema with `hardware.sane` block (enable, extra_packages)
- Produces: Steps for SANE installation
  - Step: `hardware_sane_install`
  - Step: `hardware_sane_extra_packages` (if extra_packages present)

**Acceptance Criteria:**
- Hardware section loads without errors
- SANE steps generated when sane.enabled = true
- No SANE steps when sane absent
- Uses correct package manager for distro

---

### Task 4: Create Users-Advanced Section — Identity/SSH/Dotfiles Blocks

**Files:**
- New: `src/kod/sections/users-advanced.lua`
- Test: `tests/test_phase5d_sections.lua` (users tests)

**Interfaces:**
- Consumes: Schema with user blocks:
  - `users.USERNAME.identity` (name, hashed_password, groups)
  - `users.USERNAME.ssh_keys` (enabled, authorized[])
  - `users.USERNAME.dotfiles` (repo_url, source_dir, deploy_tool)
- Produces: Steps for user setup
  - Step: `users_<name>_create` (useradd with shell)
  - Step: `users_<name>_identity_set_password` (if hashed_password)
  - Step: `users_<name>_identity_add_groups` (if groups)
  - Step: `users_<name>_ssh_setup` (if ssh_keys.enabled)
  - Step: `users_<name>_dotfiles_deploy` (if dotfiles.enabled)

**Acceptance Criteria:**
- Users-advanced module loads without errors
- Correct step generation for each block
- Proper execution order (create user → set password → add groups → setup SSH)
- Backward compatible (works without identity/ssh_keys/dotfiles blocks)
- Steps only generated if blocks present

---

### Task 5: Create SSH-Keys Section — SSH Key Management

**Files:**
- New: `src/kod/sections/ssh-keys.lua`
- Test: `tests/test_phase5d_sections.lua` (ssh-keys tests)

**Interfaces:**
- Consumes: Schema with `users.USERNAME.ssh_keys` block:
  - `.enabled` (boolean)
  - `.authorized` (list of public key strings)
- Produces: Steps for SSH key deployment
  - Step: `ssh_<user>_authorized_keys_create` (create ~/.ssh/authorized_keys)
  - Step: `ssh_<user>_authorized_keys_add` (add all keys)

**Acceptance Criteria:**
- SSH keys module loads without errors
- Creates ~/.ssh with correct permissions (700)
- Creates authorized_keys with correct permissions (600)
- Properly formatted key file
- Multiple keys supported

---

### Task 6: Create Dotfiles Section — Dotfile Deployment

**Files:**
- New: `src/kod/sections/dotfiles.lua`
- Test: `tests/test_phase5d_sections.lua` (dotfiles tests)

**Interfaces:**
- Consumes: Schema with `users.USERNAME.dotfiles` block:
  - `.enabled` (boolean)
  - `.repo_url` (git URL)
  - `.source_dir` (source directory, default ~/.dotfiles)
  - `.deploy_tool` (stow, symlink, or cp)
- Produces: Steps for dotfiles deployment
  - Step: `dotfiles_<user>_clone` (git clone repo if repo_url)
  - Step: `dotfiles_<user>_deploy` (deploy with specified tool)

**Acceptance Criteria:**
- Dotfiles module loads without errors
- Generates clone step if repo_url present
- Generates deploy step with correct tool
- No steps if dotfiles block absent
- Supports stow, symlink, and cp deployment tools

---

### Task 7: Extend Desktop Section — Environments (Renamed)

**Files:**
- Modify: `src/kod/sections/desktop.lua`
- Test: `tests/test_phase5d_sections.lua` (desktop tests)

**Interfaces:**
- Consumes: Schema with extended desktop config:
  - `desktop.display_manager` (string: gdm, sddm, cosmic-greeter, lightdm, lxdm)
  - `desktop.environments` (dict with per-DE configs):
    - `gnome.enabled`, `.extra_packages`, `.exclude_packages`
    - `plasma.enabled`, `.extra_packages`, `.exclude_packages`
    - `cosmic.enabled`, `.extra_packages`
    - `budgie.enabled`, `.extra_packages`, `.exclude_packages`
    - `pantheon.enabled`, `.extra_packages`
- Produces: Steps for each enabled environment
  - Step: `desktop_display_manager_install` (if display_manager specified)
  - Step: `desktop_<env>_install` (one per enabled environment)
  - Step: `desktop_<env>_extra_packages` (if extra_packages)
  - Step: `desktop_<env>_exclude_packages` (if exclude_packages)

**Acceptance Criteria:**
- Desktop section supports multiple environments
- Only enabled environments get steps
- Display manager installed if specified
- Extra packages installed, excluded packages removed
- Backward compatible (works with old structure)
- Uses correct distro-specific commands

---

### Task 8: Extend Fonts Section — Font Directory & Packages

**Files:**
- Modify: `src/kod/sections/fonts.lua`
- Test: `tests/test_phase5d_sections.lua` (fonts tests)

**Interfaces:**
- Consumes: Schema with extended fonts config:
  - `fonts.font_dir` (boolean: create ~/.local/share/fonts)
  - `fonts.packages` (list: font package names)
  - `fonts.monospace`, `.sans_serif`, `.emoji` (Phase 5c, still supported)
- Produces: Steps for font setup
  - Step: `fonts_dir_create` (if font_dir = true)
  - Step: `fonts_packages_install` (if packages present)
  - Step: `fonts_monospace_install` (if monospace present)
  - Step: `fonts_sans_serif_install` (if sans_serif present)
  - Step: `fonts_emoji_install` (if emoji present)

**Acceptance Criteria:**
- Fonts section supports both structures (Phase 5c and 5d)
- font_dir creates ~/.local/share/fonts with correct permissions
- packages list installs all packages
- Phase 5c structure (monospace/sans_serif/emoji) still works
- No conflicts when both structures present

---

### Task 9: Extend Services Section — Config Block Structure

**Files:**
- Modify: `src/kod/sections/services.lua`
- Test: `tests/test_phase5d_sections.lua` (services tests)

**Interfaces:**
- Consumes: Schema with extended service config:
  - `services.<name>.config.service_name` (override service name)
  - `services.<name>.config.packages.main` (override package name)
  - `services.<name>.config.packages.extra` (additional packages)
  - `services.<name>.config.settings` (per-service typed config dict)
  - `services.systemd.config.mounts` (systemd mounts)
  - `services.systemd.config.units` (systemd units)
- Produces: Enhanced service steps
  - Step: `service_<name>_package_main` (if config.packages.main)
  - Step: `service_<name>_package_extra` (if config.packages.extra)
  - Step: `service_<name>_config` (if config.settings)
  - Step: `service_<name>_enable` (use config.service_name if specified)
  - Step: `systemd_mounts_create` (if systemd mounts present)
  - Step: `systemd_units_create` (if systemd units present)

**Acceptance Criteria:**
- Services section loads without errors
- Config block structure validated
- Custom package names used when specified
- Extra packages installed
- Settings applied correctly
- Systemd service special-cased (mounts, units)
- Backward compatible (basic enable/start works without config)

---

### Task 10: Extend Planner — User-Level Programs & Services

**Files:**
- Modify: `src/kod/lib/planner.lua`
- Test: `tests/test_phase5d_integration.py` (planner tests)

**Interfaces:**
- Consumes: Config with nested user programs/services:
  - `config.users.<user>.programs.<program>.*`
  - `config.users.<user>.services.<service>.*`
- Produces: Merged global collections
  - Merges user-level programs into global programs
  - Merges user-level services into global services
  - Maintains execution order (user config after global)

**Acceptance Criteria:**
- Planner handles nested programs under users
- Planner handles nested services under users
- Execution order preserved (global → user)
- No duplicate step names
- Backward compatible (works without user-level programs/services)

---

### Task 11: Extend Python Validator — Nested Block Validation

**Files:**
- Modify: `src/kod/config/validator.py`
- Test: `tests/test_phase5d_schema.py` (validator tests)

**Interfaces:**
- Consumes: Config with all Phase 5d nested blocks
- Produces: Comprehensive validation errors
  - Type validation for all new fields
  - Enum validation (service names, environment names)
  - Required field checking (where applicable)
  - Nested field validation (3-4 levels deep)
  - Clear error messages with field paths

**Acceptance Criteria:**
- Validator accepts all valid Phase 5d configs
- Rejects invalid types (e.g., string where list expected)
- Rejects unknown environments/services
- Validates nested block structure
- Error messages include field path and expected type
- Backward compatible (Phase 5c configs still validate)

---

### Task 12: Comprehensive Integration Testing — eszkoz Config

**Files:**
- New: `tests/test_phase5d_integration.py`
- New: `tests/fixtures/eszkoz-config-5d.lua` (eszkoz adapted to Phase 5d structure)
- Modify: `tests/test_phase5d_schema.py`

**Interfaces:**
- Consumes: Full eszkoz configuration (adapted to Phase 5d structure)
- Produces: End-to-end validation
  - Loads eszkoz config successfully
  - Validates complete schema
  - Generates all ~400 eszkoz steps correctly
  - Verifies step execution order is deterministic
  - No regressions (541+ Phase 5c tests pass)

**Acceptance Criteria:**
- eszkoz config fully validates with Phase 5d schema
- All eszkoz features working (users, programs, services, desktop, etc)
- All ~400 steps generate in correct order
- 100+ new Phase 5d tests pass
- 541+ Phase 5c tests pass (no regressions)
- eszkoz serves as real-world validation

---

### Task 13: Documentation & Summary

**Files:**
- New: `docs/PHASE-5D-STRUCTURED-DESIGN.md` (already written, add final notes)
- New: `docs/ADVANCED-USER-CONFIG.md` (detailed user blocks guide)
- New: `docs/DESKTOP-ENVIRONMENTS.md` (multi-environment configuration)
- New: `docs/SERVICE-CUSTOMIZATION.md` (config block customization)
- Modify: `docs/SECTION-ORDER-PROCESSING.md` (add Phase 5d examples)
- Modify: `PHASE-5C-COMPLETION.md` (add Phase 5d status)

**Interfaces:**
- Consumes: All Phase 5d implementation
- Produces: Complete user documentation
  - What Phase 5d adds (architecture overview)
  - How to use each new feature (with examples)
  - Migration guide (Phase 5c → Phase 5d, optional)
  - API reference for new schema fields
  - Real-world example (eszkoz configuration)

**Acceptance Criteria:**
- All new features documented with examples
- Examples for each block type and customization
- Clear explanation of nested structure
- API reference complete
- Migration notes from Phase 5c (optional fields)

---

## Summary of Changes

### Schema Expansions (Lua)

| Section | New Blocks/Fields | Scope |
|---------|------------------|-------|
| users | identity, ssh_keys, dotfiles, programs, services, home_config | User-level config blocks |
| desktop | display_manager (new), environments (renamed from desktop_manager) | Multi-environment support |
| services | config block per service, systemd service | Namespaced customization |
| boot | loader.include | Bootloader entries |
| hardware | sane | Scanner support |
| fonts | font_dir, packages | Alternative font structure |

### New Lua Modules (3)
- `src/kod/sections/users-advanced.lua` (identity, SSH, password setup)
- `src/kod/sections/dotfiles.lua` (dotfile deployment)
- `src/kod/sections/ssh-keys.lua` (SSH key management)

### Modified Lua Files (7)
- `src/kod/lib/schema.lua` (core schema expansion)
- `src/kod/sections/boot.lua` (loader.include)
- `src/kod/sections/hardware.lua` (SANE support)
- `src/kod/sections/desktop.lua` (environments rename)
- `src/kod/sections/fonts.lua` (font_dir + packages)
- `src/kod/sections/services.lua` (config block)
- `src/kod/lib/planner.lua` (user programs/services merge)

### Python Modifications (3)
- `src/kod/config/validator.py` (nested block validation)
- `src/kod/planner.py` (integrated planner support)
- `src/kod/bootstrap.py` (end-to-end feature support)

### Test Coverage (3 files, 100+ tests)
- `tests/test_phase5d_schema.py` (block validation)
- `tests/test_phase5d_sections.lua` (section tests)
- `tests/test_phase5d_integration.py` (eszkoz end-to-end)

---

## Execution Path

**13 sequential tasks with clear dependencies:**

1. **Phase 1 (Setup):** Task 1 (schema expansion foundation)
2. **Phase 2 (Sections):** Tasks 2-9 (extend existing sections + create new ones)
3. **Phase 3 (Integration):** Tasks 10-11 (planner + validator integration)
4. **Phase 4 (Testing):** Task 12 (comprehensive integration testing)
5. **Phase 5 (Docs):** Task 13 (documentation & summary)

**Recommended execution:** Subagent-driven development (SDD)
- One subagent per task
- Two-stage review (design + implementation) per task
- Fast iteration with frequent commits
- Parallel execution possible for Tasks 2-9 (after Task 1)

**Estimated effort:** 18-24 hours (includes improved structure design time)

---

## Success Criteria

✅ Phase 5d schema with nested feature blocks fully implemented
✅ eszkoz configuration validates end-to-end
✅ All 13 new schema extensions working correctly
✅ 10 Lua files modified/created with new features
✅ 3 Python files integrated with new features
✅ 100+ new Phase 5d tests pass
✅ 541+ Phase 5c tests pass (zero regressions)
✅ Complete documentation for all new features
✅ Code follows Phase 5c patterns and style
✅ Ready for Phase 5e extensions or production deployment

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Complex nested validation | Comprehensive unit tests per block type, validator focused on clear errors |
| Planner integration bugs | Test user programs/services merge with simple and complex cases |
| Schema inconsistency | Single Lua source of truth, Python validator derives from Lua schema |
| Breaks Phase 5c configs | All new fields/blocks optional, Phase 5c tests as regression suite |
| Performance regression | Profile with eszkoz (~400 steps), cache schema, optimize validator |
| Missing edge cases | eszkoz as exhaustive real-world test case |

---

**Plan Status:** ✅ READY FOR IMPLEMENTATION

This plan implements the approved structured design with nested feature blocks, clarified desktop config, and namespaced service customization.

Proceed with subagent-driven development (SDD) using this plan task-by-task.
