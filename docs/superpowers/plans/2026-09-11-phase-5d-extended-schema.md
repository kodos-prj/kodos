# Phase 5d: Extended Schema for Advanced Configuration - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Phase 5c schema to support advanced user configuration, complex desktop environments, service customization, and additional hardware features—enabling real-world production systems like eszkoz.

**Architecture:** Phase 5d extends the Phase 5c schema layerwise: (1) expand schema definitions in Lua, (2) create section modules for new features, (3) extend section modules with new emit_steps logic, (4) update Python validator to handle new nested structures, (5) comprehensive testing with eszkoz config as primary test case.

**Tech Stack:** Lua (schema, section modules), Python 3.12+ (validator), lupa (Lua interpreter), pytest (testing)

**Spec:** `docs/ESZKOZ-SCHEMA-REVIEW.md` (defines all extensions needed)

## Global Constraints

- Maintain backward compatibility with Phase 5c schema
- All new schema fields optional (existing configs still work)
- No breaking changes to existing APIs
- Follow Phase 5c code style and patterns (Lua + Python)
- Test all extensions with eszkoz config as reference
- Minimum Phase 5c tests: 541 existing tests pass + 100+ new Phase 5d tests
- Schema is single source of truth (Lua first, Python derives)

---

## File Structure & Decomposition

### Lua Schema & Sections
- `src/kod/lib/schema.lua` — MODIFY: Add new fields to existing sections
- `src/kod/sections/boot.lua` — MODIFY: Support loader.include
- `src/kod/sections/hardware.lua` — MODIFY: Add SANE support
- `src/kod/sections/users.lua` — NEW: User-level advanced config
- `src/kod/sections/desktop.lua` — MODIFY: Support multiple DEs + display_manager
- `src/kod/sections/fonts.lua` — MODIFY: Support font_dir + packages array
- `src/kod/sections/services.lua` — MODIFY: Support service customization
- `src/kod/sections/dotfiles.lua` — NEW: Dotfile manager
- `src/kod/sections/ssh_keys.lua` — NEW: SSH key management

### Python Validator & Integration
- `src/kod/config/validator.py` — MODIFY: Handle nested user config, new structures
- `src/kod/planner.py` — MODIFY: Support nested programs/services under users
- `src/kod/bootstrap.py` — MODIFY: Handle advanced config features

### Tests
- `tests/test_phase5d_schema.py` — NEW: Schema validation for all extensions
- `tests/test_phase5d_sections.lua` — NEW: Lua tests for new section features
- `tests/test_phase5d_integration.py` — NEW: End-to-end with eszkoz config
- `tests/fixtures/eszkoz-config-compliant.lua` — NEW: eszkoz adapted to Phase 5d

### Documentation
- `docs/PHASE-5D-EXTENSIONS.md` — NEW: What Phase 5d adds over Phase 5c
- `docs/ADVANCED-USER-CONFIG.md` — NEW: User-level programs, services, dotfiles
- `docs/DESKTOP-ENVIRONMENTS.md` — NEW: Multi-DE configuration guide

---

## Task Decomposition

### Task 1: Extend Schema (Lua) — Core Definitions

**Files:**
- Modify: `src/kod/lib/schema.lua`
- Test: `tests/test_phase5d_schema.py`

**Interfaces:**
- Consumes: Phase 5c schema (all 13 sections)
- Produces: Extended schema with new optional fields:
  - `boot.loader.include` (list of bootloader entries)
  - `hardware.sane` (SANE scanner config)
  - `users.USERNAME.name`, `.hashed_password`, `.extra_groups`, `.openssh_authorized`, `.dotfile_manager`, `.home_config`
  - `users.USERNAME.programs` (nested program configs)
  - `users.USERNAME.services` (nested service configs)
  - `desktop.display_manager` (string, display manager name)
  - `desktop.desktop_manager` (dict with per-DE configs)
  - `fonts.font_dir` (boolean), `fonts.packages` (list)
  - `services.*.service_name`, `services.*.settings`, `services.*.package`, `services.*.extra_packages`
  - `services.systemd` (systemd mount/unit config)

**Acceptance Criteria:**
- All new fields defined in schema with proper types
- All new fields are optional (Phase 5c configs unaffected)
- Schema file validates in Lua without errors
- All 13 original sections still present and unchanged

---

### Task 2: Extend Boot Section — Bootloader Include

**Files:**
- Modify: `src/kod/sections/boot.lua`
- Modify: `src/kod/lib/schema.lua:boot.loader.include`
- Test: `tests/test_phase5d_sections.lua` (boot tests)

**Interfaces:**
- Consumes: Schema with `boot.loader.include` field (list of strings)
- Produces: Steps for bootloader entry configuration
  - Step: `boot_loader_include_<name>` (one per include entry)

**Acceptance Criteria:**
- Boot section loads without errors
- `emit_steps()` generates include steps when field present
- Include steps use correct boot manager commands (systemd-boot, grub)
- No include steps generated when field absent (backward compatible)

---

### Task 3: Extend Hardware Section — SANE Support

**Files:**
- Modify: `src/kod/sections/hardware.lua`
- Modify: `src/kod/lib/schema.lua:hardware.sane`
- Test: `tests/test_phase5d_sections.lua` (hardware tests)

**Interfaces:**
- Consumes: Schema with `hardware.sane` section (dict with enable, extra_packages)
- Produces: Steps for SANE installation and configuration
  - Step: `hardware_sane_install` (install sane package)
  - Step: `hardware_sane_extra_packages` (install extra packages if present)

**Acceptance Criteria:**
- Hardware section loads without errors
- `emit_steps()` generates SANE steps when field present
- SANE steps use correct package manager for distro
- No SANE steps when field absent

---

### Task 4: Create Users Section (Advanced) — User-Level Config

**Files:**
- New: `src/kod/sections/users-advanced.lua`
- Modify: `src/kod/lib/schema.lua:users.USERNAME.*`
- Test: `tests/test_phase5d_sections.lua` (users tests)

**Interfaces:**
- Consumes: Schema with expanded user fields:
  - `.name` (display name)
  - `.hashed_password` (password hash)
  - `.extra_groups` (list of group names)
  - `.openssh_authorized.keys` (list of SSH public keys)
  - `.dotfile_manager` (config object)
  - `.home_config` (home directory config dict)
- Produces: Steps for user creation and configuration
  - Step: `users_<name>_create` (useradd)
  - Step: `users_<name>_set_password` (chpasswd or usermod)
  - Step: `users_<name>_add_groups` (usermod -G)
  - Step: `users_<name>_ssh_authorized_keys` (add keys to ~/.ssh/authorized_keys)
  - Step: `users_<name>_dotfiles_setup` (deploy dotfiles)

**Acceptance Criteria:**
- New users-advanced module loads without errors
- Generates user creation steps in correct order
- SSH keys properly deployed
- Dotfiles manager called if configured
- Backward compatible (works with minimal user config too)

---

### Task 5: Create Dotfiles Section — Dotfile Management

**Files:**
- New: `src/kod/sections/dotfiles.lua`
- Modify: `src/kod/lib/schema.lua:users.USERNAME.dotfile_manager`
- Test: `tests/test_phase5d_sections.lua` (dotfiles tests)

**Interfaces:**
- Consumes: Dotfile config (dict):
  - `source_dir` (where dotfiles live)
  - `target_dir` (where to deploy)
  - `repo_url` (git repo to clone)
- Produces: Steps for dotfile deployment
  - Step: `dotfiles_<user>_clone` (git clone repo)
  - Step: `dotfiles_<user>_deploy` (stow or symlink)

**Acceptance Criteria:**
- Dotfiles module loads without errors
- Generates clone step if repo_url present
- Generates deploy step with correct tool (stow, symlink, etc.)
- No steps if dotfile_manager not configured

---

### Task 6: Create SSH Keys Section — SSH Key Management

**Files:**
- New: `src/kod/sections/ssh-keys.lua`
- Modify: `src/kod/lib/schema.lua:users.USERNAME.openssh_authorized`
- Test: `tests/test_phase5d_sections.lua` (ssh-keys tests)

**Interfaces:**
- Consumes: SSH config (dict):
  - `.keys` (list of public key strings)
- Produces: Steps for SSH key setup
  - Step: `ssh_<user>_authorized_keys_setup` (create ~/.ssh/authorized_keys)
  - Step: `ssh_<user>_add_key_<N>` (add each key)

**Acceptance Criteria:**
- SSH keys module loads without errors
- Generates keys in correct ~/.ssh/authorized_keys format
- Correct permissions (600 for authorized_keys, 700 for ~/.ssh)
- Multiple keys supported

---

### Task 7: Extend Desktop Section — Multi-DE Support

**Files:**
- Modify: `src/kod/sections/desktop.lua`
- Modify: `src/kod/lib/schema.lua:desktop.*`
- Test: `tests/test_phase5d_sections.lua` (desktop tests)

**Interfaces:**
- Consumes: Schema with extended desktop config:
  - `desktop.display_manager` (string: gdm, sddm, cosmic-greeter, lightdm)
  - `desktop.desktop_manager` (dict with per-DE configs):
    - `gnome.enable`, `gnome.exclude_packages`, `gnome.extra_packages`
    - `plasma.enable`, `plasma.extra_packages`
    - `cosmic.enable`
    - `budgie.enable`, `budgie.extra_packages`
    - `pantheon.enable`
- Produces: Steps for each enabled DE
  - Step: `desktop_display_manager_install` (install display manager)
  - Step: `desktop_<de>_install` (install selected DE)
  - Step: `desktop_<de>_extra_packages` (install extra packages)
  - Step: `desktop_<de>_exclude_packages` (remove unwanted packages)

**Acceptance Criteria:**
- Desktop section supports multiple DEs
- Only enabled DEs get steps generated
- Display manager installed if specified
- Extra packages installed, excluded packages removed
- Correct distro-specific commands

---

### Task 8: Extend Fonts Section — Alternative Font Structure

**Files:**
- Modify: `src/kod/sections/fonts.lua`
- Modify: `src/kod/lib/schema.lua:fonts.*`
- Test: `tests/test_phase5d_sections.lua` (fonts tests)

**Interfaces:**
- Consumes: Schema with extended fonts config:
  - `fonts.font_dir` (boolean: create font directory)
  - `fonts.packages` (list: font package names, alternative to monospace/sans_serif/emoji)
- Produces: Steps for font installation
  - Step: `fonts_dir_create` (create font directory if needed)
  - Step: `fonts_packages_install` (install packages from list)

**Acceptance Criteria:**
- Fonts section supports both structures (Phase 5c and Phase 5d)
- font_dir creates ~/.local/share/fonts if needed
- packages list installs all packages
- Backward compatible (monospace/sans_serif/emoji still work)

---

### Task 9: Extend Services Section — Service Customization

**Files:**
- Modify: `src/kod/sections/services.lua`
- Modify: `src/kod/lib/schema.lua:services.*`
- Test: `tests/test_phase5d_sections.lua` (services tests)

**Interfaces:**
- Consumes: Schema with extended service config:
  - `services.<name>.service_name` (override default service name)
  - `services.<name>.settings` (config dict for service)
  - `services.<name>.package` (override package name)
  - `services.<name>.extra_packages` (additional packages to install)
  - `services.systemd` (special section for systemd units/mounts)
- Produces: Enhanced service steps
  - Step: `service_<name>_package_install` (install custom package if specified)
  - Step: `service_<name>_extra_packages` (install extra packages)
  - Step: `service_<name>_config` (apply settings)
  - Step: `service_<name>_enable` (enable service, use custom service_name)

**Acceptance Criteria:**
- Services section supports all new customization fields
- Custom package names used when specified
- Extra packages installed
- Settings applied to service config
- Systemd service special-cased (mount points, units)
- Backward compatible (basic enable/start still works)

---

### Task 10: Extend Planner — Nested Programs & Services

**Files:**
- Modify: `src/kod/lib/planner.lua`
- Test: `tests/test_phase5d_integration.py` (planner tests)

**Interfaces:**
- Consumes: Config with nested user programs/services:
  - `config.users.<user>.programs.<program>.*`
  - `config.users.<user>.services.<service>.*`
- Produces: Steps from nested structures
  - Merges user-level programs into global programs
  - Merges user-level services into global services
  - Maintains execution order (user config after global)

**Acceptance Criteria:**
- Planner handles nested programs under users
- Planner handles nested services under users
- Execution order preserved
- No duplicate step names
- Backward compatible (users without nested programs/services work)

---

### Task 11: Extend Python Validator — Handle New Structures

**Files:**
- Modify: `src/kod/config/validator.py`
- Test: `tests/test_phase5d_schema.py` (validator tests)

**Interfaces:**
- Consumes: Config with all Phase 5d extensions
- Produces: Validation errors for invalid configs
  - Type validation (all new fields)
  - Enum validation (service names, DE names)
  - Required field checking (where applicable)
  - Nested field validation (3 levels)

**Acceptance Criteria:**
- Validator accepts all valid Phase 5d configs
- Rejects invalid types (e.g., string where list expected)
- Rejects unknown services/DEs/programs
- Error messages include field path and expected type
- Backward compatible (Phase 5c configs still validate)

---

### Task 12: Comprehensive Testing — eszkoz Config

**Files:**
- New: `tests/test_phase5d_integration.py`
- New: `tests/fixtures/eszkoz-config-5d.lua`
- Modify: `tests/test_phase5d_schema.py`

**Interfaces:**
- Consumes: Full eszkoz configuration
- Produces: Test suite validating entire Phase 5d
  - Loads eszkoz config
  - Validates schema
  - Composes all steps
  - Verifies step order and dependencies

**Acceptance Criteria:**
- eszkoz config fully validates
- All ~400 eszkoz steps generated correctly
- Step execution order is deterministic
- No regressions (541+ Phase 5c tests pass)
- 100+ new Phase 5d tests pass

---

### Task 13: Documentation & Cleanup

**Files:**
- New: `docs/PHASE-5D-EXTENSIONS.md`
- New: `docs/ADVANCED-USER-CONFIG.md`
- New: `docs/DESKTOP-ENVIRONMENTS.md`
- Modify: `docs/SECTION-ORDER-PROCESSING.md` (add Phase 5d examples)
- Modify: `PHASE-5C-COMPLETION.md` (add Phase 5d status)

**Interfaces:**
- Consumes: All Phase 5d implementation
- Produces: Complete documentation for users
  - What Phase 5d adds
  - How to use advanced features
  - DE configuration examples
  - User-level program/service examples

**Acceptance Criteria:**
- All new features documented
- Examples for each extension
- Migration guide from Phase 5c
- API reference for new schema fields

---

## Summary of Changes

### Schema Expansions (Lua)

| Section | New Fields | Optional |
|---------|-----------|----------|
| boot.loader | include (list) | ✅ |
| hardware | sane (dict) | ✅ |
| users.* | name, hashed_password, extra_groups, openssh_authorized, dotfile_manager, home_config, programs, services | ✅ |
| desktop | display_manager (string), desktop_manager (dict) | ✅ |
| fonts | font_dir (bool), packages (list) | ✅ |
| services.* | service_name, settings, package, extra_packages | ✅ |
| services | systemd (dict) | ✅ |

### New Lua Modules

- `src/kod/sections/users-advanced.lua` (user creation, groups, passwords)
- `src/kod/sections/dotfiles.lua` (dotfile deployment)
- `src/kod/sections/ssh-keys.lua` (SSH key management)

### Python Modifications

- Validator: Handle nested user config, new types
- Planner: Merge nested programs/services into global
- Bootstrap: Support all new features

### Test Coverage

- 100+ new Phase 5d tests
- eszkoz as primary integration test
- All Phase 5c tests still pass (no regressions)

---

## Execution Path

This plan has **13 independent tasks** with clear dependencies:

1. **Phase 1** (Setup): Task 1 (schema expansion)
2. **Phase 2** (Sections): Tasks 2-9 (extend existing sections + create new ones)
3. **Phase 3** (Integration): Tasks 10-11 (planner + validator)
4. **Phase 4** (Testing): Task 12 (comprehensive integration)
5. **Phase 5** (Docs): Task 13 (documentation)

**Recommended execution:** Subagent-driven development (SDD)
- One subagent per task (parallel possible for independent tasks)
- Two-stage review (design + implementation)
- Fast iteration, frequent commits

**Estimated effort:** 15-20 hours total (varies by parallelization)

---

## Success Criteria

✅ eszkoz configuration fully validates and generates correct steps
✅ All 13 new schema extensions working
✅ 9 new section modules (extensions + new)
✅ 100+ new tests, all passing
✅ 541+ Phase 5c tests pass (no regressions)
✅ Complete documentation for all new features
✅ Ready for Phase 5e or production deployment

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Breaks Phase 5c configs | All new fields optional, Phase 5c tests as regression suite |
| Complex nested validation | Comprehensive unit tests per section, validator tests |
| Schema inconsistency | Single Lua source of truth, Python derives |
| Performance issues | Caching, profile with eszkoz (400+ steps) |
| Missing edge cases | eszkoz as exhaustive test case (real system) |

---

**Plan Status:** ✅ READY FOR IMPLEMENTATION

Two execution options:

1. **Subagent-Driven (Recommended)** — I dispatch fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach would you prefer?**
