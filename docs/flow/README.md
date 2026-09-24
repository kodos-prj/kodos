# KodOS Installation Flow Documentation

Complete architectural documentation and flow diagrams for the KodOS installation and rebuild process.

## 📚 Start Here

**First time?** Start with **[FLOW_DIAGRAMS_README.md](FLOW_DIAGRAMS_README.md)** for an overview of all documentation.

**Want quick facts?** See **[INSTALLATION_FLOW_SUMMARY.md](INSTALLATION_FLOW_SUMMARY.md)** for quick reference.

**Need deep dive?** Read **[KODOS_INSTALLATION_FLOW.md](KODOS_INSTALLATION_FLOW.md)** for comprehensive breakdown with file:line references.

## 📊 Mermaid Flow Diagrams

Interactive flow diagrams (render in GitHub, VS Code, or any Mermaid viewer):

### Installation Process

1. **[KODOS_INSTALLATION_FLOW.mmd](KODOS_INSTALLATION_FLOW.mmd)** - Main installation pipeline
   - CLI → config → plan → execution flow
   - Integration of all 13 Lua sections
   - Package stream separation (normal/AUR/flatpak)
   - Generation management and state

2. **[AUR_PACKAGE_BUILD_FLOW.mmd](AUR_PACKAGE_BUILD_FLOW.mmd)** - AUR package build details
   - Step-by-step AUR build sequence (5 stages)
   - yay-bin bootstrap from AUR
   - kod user creation and configuration
   - makepkg execution as unprivileged user
   - Building remaining AUR packages with yay

3. **[PACKAGE_STREAMS_FLOW.mmd](PACKAGE_STREAMS_FLOW.mmd)** - Three-stream package processing
   - Normal packages (pacman)
   - AUR packages (build + install)
   - Flatpak apps (systemd service)
   - Stream-specific execution details and error handling

### Rebuild Process

4. **[REBUILD_PROCESS_FLOW.mmd](REBUILD_PROCESS_FLOW.mmd)** - Complete rebuild pipeline (NEW)
   - Detailed flow from `kod rebuild` CLI through atomic swap
   - **All function calls with file:line references**
   - Diff computation (current vs target state)
   - Only changed sections executed (baseline='current')
   - Atomic generation swap with rollback capability
   - State management and lock file generation

## 📖 Text Documentation

Comprehensive guides with file:line references and pseudocode:

### Installation Process

1. **[INSTALLATION_FLOW_SUMMARY.md](INSTALLATION_FLOW_SUMMARY.md)** (12 KB)
   - Quick reference guide
   - 5 CLI entry points
   - 13 major installation phases
   - Package handling overview
   - Distro adapter architecture
   - Error handling and debugging

2. **[KODOS_INSTALLATION_FLOW.md](KODOS_INSTALLATION_FLOW.md)** (24 KB)
   - Detailed phase-by-phase breakdown
   - All functions with file:line references
   - Pseudocode for complex flows
   - Data structures and state files
   - Lua-Python integration patterns
   - Generation management details

3. **[INSTALLATION_FLOW_VISUAL.txt](INSTALLATION_FLOW_VISUAL.txt)** (23 KB)
   - ASCII box diagrams
   - Package aggregation flow
   - Lua-Python interaction
   - Step execution with hooks
   - State file structure

### Rebuild Process

5. **[REBUILD_PROCESS_REFERENCE.md](REBUILD_PROCESS_REFERENCE.md)** (400+ lines, NEW)
   - Complete function signatures with examples
   - Phase-by-phase breakdown of rebuild flow
   - **Key difference: baseline='current' and diff computation**
   - Lua executor internals and step execution
   - Atomic generation swap mechanism with btrfs
   - Rollback procedures on failure
   - State file formats and lock generation
   - Full call sequence from CLI to swap
   - Error handling and on_error policies

### Navigation & Reference

6. **[INSTALLATION_ANALYSIS_INDEX.md](INSTALLATION_ANALYSIS_INDEX.md)** (9 KB)
   - Navigation index for all documentation
   - Quick-start paths for different tasks
   - Architecture patterns and design principles
   - How to extend the system
   - File organization guide

## 🔍 How to Use These Files

### I want to understand the overall architecture
1. Read: **INSTALLATION_FLOW_SUMMARY.md**
2. Study: **KODOS_INSTALLATION_FLOW.mmd** (visual)
3. Reference: **INSTALLATION_FLOW_VISUAL.txt** (ASCII diagrams)

### I want to understand the rebuild process
1. Read: **REBUILD_PROCESS_FLOW.mmd** (visual with all function calls)
2. Study: **REBUILD_PROCESS_REFERENCE.md** (complete reference)
3. Key section: "Diff Computation" and "Atomic Generation Swap"

### I want to debug AUR package installation
1. Read: **AUR_PACKAGE_BUILD_FLOW.mmd**
2. Check: **PACKAGE_STREAMS_FLOW.mmd** (AUR stream)
3. Reference: **KODOS_INSTALLATION_FLOW.md** (packages.lua section)

### I want to add a new feature or distro
1. Start: **INSTALLATION_ANALYSIS_INDEX.md**
2. Study: **KODOS_INSTALLATION_FLOW.md** (architecture sections)
3. Review: Existing Lua sections as templates

### I want to trace a specific function call
Use **file:line** references throughout documentation:
- **REBUILD_PROCESS_FLOW.mmd** - All functions labeled with file:line (visual)
- **REBUILD_PROCESS_REFERENCE.md** - Full signatures and examples

Example:
```
plan_rebuild()          → kod.py:751
├─ build_plan()         → planner.py:463
│  └─ compose_steps_lua() → planner.py:108
│     └─ packages.lua:emit_steps()
│        ├─ aggregate_all_packages() → packages.lua:368
│        ├─ separate_packages() → packages.lua:405
│        └─ emit_steps() → packages.lua:419
└─ execute_steps() → executor.py:36
   └─ planning/executor.lua:40
```

## 🏗️ Key Architectural Patterns

### Lua-Driven Step Emission
Each Lua section implements `emit_steps(config, distro)`:
- Analyzes configuration
- Returns ordered Step objects
- Called sequentially by Python planner

### Package Aggregation Pipeline
```
aggregate_all_packages()
  ├─ desktop.environments[*].extra_packages
  ├─ hardware[*].extra_packages
  ├─ programs[*].extra_packages
  ├─ users[user].programs[*].extra_packages
  └─ fonts.packages
    ↓
  separate_packages()
    ├─ normal_pkgs → pacman -S
    ├─ aur_pkgs → [5-step build]
    └─ flatpak_pkgs → flatpak install
```

### AUR Build Sequence (NEW in v2)
```
Order 490: install base-devel + git
Order 492: create kod user (bash shell)
Order 493: configure sudoers (NOPASSWD: ALL)
Order 494: build yay-bin (sudo -u kod makepkg)
Order 500+: build each AUR package (sudo -u kod yay -S)
```

### Atomic Generation Swap
After successful rebuild:
1. Create btrfs backup snapshot
2. Move rootfs from next_gen → current
3. Move old rootfs → previous generation
4. On failure: rollback all moves
5. On success: delete backup

## 📍 File Organization

```
docs/flow/
├─ README.md (this file)
├─ FLOW_DIAGRAMS_README.md (overview & how to use)
├─
├─ Installation Process:
├─ KODOS_INSTALLATION_FLOW.mmd (main flow - Mermaid)
├─ AUR_PACKAGE_BUILD_FLOW.mmd (AUR detail - Mermaid)
├─ PACKAGE_STREAMS_FLOW.mmd (three streams - Mermaid)
├─ INSTALLATION_FLOW_SUMMARY.md (quick reference)
├─ KODOS_INSTALLATION_FLOW.md (detailed reference)
├─ INSTALLATION_FLOW_VISUAL.txt (ASCII diagrams)
├─
├─ Rebuild Process:
├─ REBUILD_PROCESS_FLOW.mmd (rebuild flow - Mermaid, with all function calls)
├─ REBUILD_PROCESS_REFERENCE.md (detailed reference, 400+ lines)
├─
└─ INSTALLATION_ANALYSIS_INDEX.md (navigation index)
```

## 🔧 Recent Changes (v2 & v3)

### v3: Rebuild Process Documentation (NEW)
Added comprehensive rebuild flow diagrams and reference:
- `REBUILD_PROCESS_FLOW.mmd` - Complete Mermaid flow with all function calls
- `REBUILD_PROCESS_REFERENCE.md` - 400+ line detailed reference
- **Key differences from install:**
  - Diff computation (current vs target state)
  - `baseline='current'` skips unchanged sections
  - Atomic generation swap instead of new generation
  - Rollback capability via btrfs backup

### v2: AUR Package Installation - Complete Rewrite
**Problem:** AUR packages silently skipped during install/rebuild

**Solution:** 5-step AUR build sequence with proper user/permission handling
- Build yay-bin from AUR first
- Create unprivileged kod user with bash shell
- Configure sudoers for password-less sudo
- Use yay to build remaining AUR packages

**Files Changed:**
- `src/lua/kod/sections/packages.lua` (emit_steps)
- `src/kod/bootstrap.py` (Lua-Python interop)
- `src/kod/planner.py` (package aggregation)

**Commits:**
- d61b2f6: Fix aggregation
- 4debe9e: Bootstrap yay from AUR
- 7f5d75e: Fix build directory permissions
- c467bb7: Run yay as unprivileged user
- 044c5b0: Fix kod user shell to bash
- c2e55d4: Add rebuild process diagrams

## 📚 Additional References

- **Code:** `src/lua/kod/sections/packages.lua` - AUR build logic
- **Code:** `src/lua/kod/planning/executor.lua` - Step execution engine
- **Code:** `src/kod/planner.py` - Plan composition in Python
- **Logs:** `/tmp/rebuild.log` - Live rebuild output
- **Config:** `example/testvm/configuration.lua` - Test config with AUR packages

## 🚀 Verification

To verify the installation flow works end-to-end:
```bash
kod rebuild -c example/testvm/configuration.lua
# Check /tmp/rebuild.log for:
# - yay-bin built successfully
# - AUR packages built (brother-dcp-l2550dw, mission-center)
# - Services enabled (cups, bluetooth)
```

---

Last updated: 2026-09-23
Generated by: KodOS architecture analysis workflow
