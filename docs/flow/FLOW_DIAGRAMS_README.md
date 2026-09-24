# KodOS Installation Process - Flow Diagrams & Documentation

This directory contains comprehensive documentation of the KodOS installation and rebuild process, including detailed flow diagrams, function call graphs, and architecture explanations.

## 📊 Flow Diagrams (Mermaid format)

### 1. **KODOS_INSTALLATION_FLOW.mmd** - Main Installation Pipeline
High-level overview of the entire install/rebuild process:
- CLI entry points → config loading → plan composition → execution
- Integration of 13 Lua sections (devices, packages, services, etc.)
- Package aggregation and separation (normal/AUR/flatpak)
- Lua-Python interop via lupa runtime
- State management and generation swapping

**Read this first** to understand the big picture.

### 2. **AUR_PACKAGE_BUILD_FLOW.mmd** - AUR Package Build Details
Step-by-step flow for building AUR packages (NEW in v2):
- yay-bin bootstrap from AUR
- kod user creation with proper shell configuration
- Sudoers setup for password-less elevation
- Building yay-bin safely with makepkg
- Building remaining AUR packages with yay
- Timeout and dependency management

**Read this** to understand how `brother-dcp-l2550dw` and `mission-center` get built.

### 3. **PACKAGE_STREAMS_FLOW.mmd** - Three-Stream Package Processing
How packages are aggregated, separated, and installed via three distinct pipelines:
- **Normal packages** → pacman -S
- **AUR packages** → build with yay, then install
- **Flatpak apps** → flatpak install (with network dependency)

Shows execution details for each stream and error conditions.

## 📄 Text Documentation

### INSTALLATION_FLOW_SUMMARY.md (413 lines)
Quick-reference guide with:
- 5 CLI entry points (install, rebuild, boot, uninstall, generations)
- High-level flow diagram in ASCII
- 13 major installation phases
- Package handling overview
- Distro adapter architecture
- Error handling and rollback
- Debugging tips

**START HERE** for quick understanding.

### KODOS_INSTALLATION_FLOW.md (650 lines)
Comprehensive detailed reference with:
- Complete phase-by-phase breakdown
- File:line references to actual code
- Pseudocode for complex flows
- Data structures and state management
- Lua-Python integration patterns
- Generation management (atomic swap, rollback)
- All 13 Lua sections documented

**Reference this** when implementing or debugging.

### INSTALLATION_FLOW_VISUAL.txt (528 lines)
ASCII art diagrams showing:
- Install phase (config → plan → execute)
- Rebuild phase (comparison → new plan → atomic swap)
- Package flow (aggregation → separation → three streams)
- Lua-Python interaction architecture
- Step execution with hooks and callbacks
- State files and JSON structure

**Use these** for whiteboard discussions or offline reference.

### INSTALLATION_ANALYSIS_INDEX.md (262 lines)
Navigation index with:
- Quick-start paths for different tasks
- Architecture patterns and design principles
- How to extend (new sections, new distros)
- File organization and import graph
- Known limitations and future work

**Consult this** when adding features.

### README_INSTALLATION_FLOW_DOCS.md
Overview and table of contents for all documentation files.

## 🎯 How to Use These Files

### I want to understand the overall architecture
1. Start with **INSTALLATION_FLOW_SUMMARY.md**
2. Look at **KODOS_INSTALLATION_FLOW.mmd**
3. Browse **INSTALLATION_FLOW_VISUAL.txt** for ASCII diagrams

### I want to debug the AUR package build
1. Read **AUR_PACKAGE_BUILD_FLOW.mmd**
2. Check **PACKAGE_STREAMS_FLOW.mmd** for the AUR stream
3. Reference **KODOS_INSTALLATION_FLOW.md** lines on packages.lua

### I want to add a new distro or feature
1. Start with **INSTALLATION_ANALYSIS_INDEX.md**
2. Study **KODOS_INSTALLATION_FLOW.md** architecture sections
3. Review existing Lua sections as templates

### I want to trace a specific function call
Use the **file:line** references in the documentation files. Example:
```
packages_build_aur_brother-dcp-l2550dw
└─ src/lua/kod/sections/packages.lua:442
   └─ emit_steps() generates this step
      └─ calls yay as kod user (unprivileged)
```

## 🏗️ Key Architectural Patterns

### 1. **Lua-Driven Step Emission**
Each Lua section (packages.lua, services.lua, etc.) implements `emit_steps(config, distro)` which:
- Analyzes configuration
- Returns ordered list of Step objects
- Is called sequentially by Python planner

### 2. **Package Aggregation**
packages.lua:aggregate_all_packages() collects from:
- desktop.environments[*].extra_packages
- hardware[*].extra_packages  
- programs[*].extra_packages
- users[user].programs[*].extra_packages
- fonts.packages
- system packages

Then separate_packages() splits by prefix (aur:, flatpak:, or normal).

### 3. **AUR Build Flow** (NEWLY FIXED)
For each AUR package:
1. Create unprivileged `kod` user with bash shell
2. Give kod user NOPASSWD sudo access
3. Build yay-bin from AUR (using makepkg as kod user)
4. Use yay (system-wide) to build other AUR packages
5. Each build runs in chroot with 900s timeout

**Why this works:**
- makepkg requires non-root execution (safety)
- kod user has bash shell to run commands
- kod user has sudo access to install packages
- yay orchestrates build + install atomically

### 4. **Atomic Generation Swap**
After successful rebuild:
1. Create btrfs backup snapshot
2. Move rootfs from next_generation → current position
3. Move old rootfs → previous generation
4. On failure: rollback all moves
5. On success: delete backup

Ensures system never in inconsistent state.

## 📊 Function Call Map

### Main CLI Entry Points (kod.py)
- `install()` (line 427) → build_plan() → execute_steps()
- `rebuild()` (line 739) → plan_rebuild() → execute_steps()
- `boot()` (line 689) → plan_boot()
- `uninstall()` (line 903)
- `generations()` (line 957)

### Planning Phase
- `build_plan()` (planner.py:463)
- `compose_steps_lua()` (planner.py:108)
- `plan_install()` → calls build_plan(baseline="empty")
- `plan_rebuild()` → calls build_plan(baseline="current")

### Lua Module Loading (via lupa)
- `get_lua_runtime()` → singleton Lua5.5 interpreter
- `lua.require("kod.sections.packages")` → loads packages.lua
- `planner_module.compose(config, distro)` (planning/planner.lua:140)
- Each section's `emit_steps(config, distro)`

### Package Processing
- `aggregate_all_packages()` (packages.lua:368)
  - ├─ aggregate_desktop_packages()
  - ├─ aggregate_hardware_packages()
  - ├─ aggregate_global_program_packages()
  - ├─ aggregate_user_program_packages()
  - └─ deduplicate_packages()
  
- `separate_packages()` (packages.lua:405)
  - → (normal_pkgs, aur_pkgs, flatpak_pkgs)
  
- `emit_steps()` (packages.lua:419)
  - For normal: pacman -S step
  - For AUR: 5-step sequence (user, sudoers, yay-bin, build each)
  - For flatpak: systemd service dispatch

### Execution Phase
- `execute_steps()` (executor.py:36)
- `lua.require("kod.planning.executor")` → runs Lua executor
- For each step:
  - pre:<kind> hooks
  - run_shell() with chroot wrapper
  - on_error policy (abort|warn)
  - post:<kind> hooks

### State Management
- `store_packages_services()` (packages.py)
  - → /kod/generations/N/installed_packages (JSON)
  - → /kod/generations/N/enabled_services (JSON)
  
- `generate_package_lock()` (distro/base.py)
  - → /kod/generations/N/packages.lock (JSON)
  
- `_swap_generations_atomic()` (kod.py:156)
  - Btrfs snapshot + move operations
  - Rollback on failure

## 📝 State Files & JSON Format

### installed_packages (line N)
```json
{
  "packages": ["vim", "git", "base-devel", "brother-dcp-l2550dw", "mission-center"],
  "kernel": "linux"
}
```

### enabled_services (line N)
```json
{
  "services": ["cosmic-greeter", "cups", "bluetooth", "...]
}
```

### packages.lock (line N)
```json
{
  "pacman": ["vim-9.0.1234-1-x86_64", "git-2.55.0-1", ...],
  "aur": ["brother-dcp-l2550dw-4.0.0-2", ...],
  "flatpak": ["com.visualstudio.code/23.1", ...]
}
```

## 🔧 Recent Changes (v2)

### AUR Package Installation - Complete Rewrite
**Problem:** AUR packages silently skipped, features like printer drivers missing.

**Solution:** 5-step AUR build sequence:
1. Install base-devel (required for makepkg)
2. Create kod unprivileged user
3. Configure sudoers (NOPASSWD for kod)
4. Build yay-bin from AUR as kod user
5. Use yay to build remaining AUR packages

**Files Changed:**
- src/lua/kod/sections/packages.lua (emit_steps function)
- src/kod/bootstrap.py (Lua-Python interop fix)
- src/kod/planner.py (package aggregation fix)

**Commits:**
- d61b2f6: Fix aggregation (Lua table conversion, global programs)
- 4debe9e: Bootstrap yay from AUR
- 7f5d75e: Fix build directory permissions
- c467bb7: Run yay as unprivileged user
- 044c5b0: Fix kod user shell to bash

## 📚 Additional Resources

- `/tmp/rebuild.log` - Live build logs during testing
- `example/testvm/configuration.lua` - Test configuration with AUR packages
- `src/lua/kod/planning/executor.lua` - Lua step execution engine
- `src/lua/kod/planning/planner.lua` - Lua plan composition

## 🚀 Next Steps

To verify these flows work end-to-end:
1. Run: `kod rebuild -c example/testvm/configuration.lua`
2. Check `/tmp/rebuild.log` for step execution
3. Verify AUR packages installed: brother-dcp-l2550dw, mission-center
4. Check services running: cups, bluetooth, etc.

