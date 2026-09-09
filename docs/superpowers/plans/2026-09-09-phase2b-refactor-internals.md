# Phase 2b: Refactor Core.py Internals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incrementally move function implementations from monolithic `_core.py` to the new modular structure (`kod/system/*` and `kod/core/*`) while maintaining full backward compatibility.

**Architecture:** Phase 2a created thin wrapper modules that import from `_core.py`. Phase 2b moves the actual implementations to those modules, keeping `_core.py` as a backward-compatibility re-export layer. Dependencies are resolved by moving related functions together and updating internal calls.

**Tech Stack:** Python 3.9+, existing modules (`kod.arch`, `kod.common`, `kod.filesystem`), pytest for testing.

**Spec:** docs/superpowers/specs/2026-09-09-architecture-redesign.md (Phase 2 - Module Extraction and Refactoring)

## Global Constraints

- **Backward Compatibility:** All imports must continue to work: `from kod.core import X` must work at every step
- **No Circular Dependencies:** `kod.system.*` modules never import from `kod.core` (workflows)
- **Test Coverage:** All 59 existing tests must pass after every task; new tests added as implementations are refactored
- **Monolithic Core:** `kod._core.py` remains as re-export layer until Phase 3 (can be deleted then)

---

## File Structure

### Current State (Phase 2a)
```
src/kod/
├── _core.py                 # Monolithic module (2,054 lines, 59 functions)
├── core/
│   ├── __init__.py          # Re-exports from _core.py (backward compat)
│   ├── install.py           # Thin wrappers (to be refactored)
│   ├── rebuild.py           # Thin wrappers (to be refactored)
│   └── user_config.py       # Thin wrappers (to be refactored)
└── system/
    ├── __init__.py          # Re-exports module names
    ├── packages.py          # Thin wrappers (to be refactored)
    ├── services.py          # Thin wrappers (to be refactored)
    ├── boot.py              # Thin wrappers (to be refactored)
    ├── filesystem.py        # Thin wrappers (to be refactored)
    └── users.py             # Thin wrappers (to be refactored)
```

### After Phase 2b
```
src/kod/
├── _core.py                 # Re-export layer only (backward compat)
├── core/
│   ├── __init__.py          # Re-exports from new modules
│   ├── install.py           # Full implementation + wrappers
│   ├── rebuild.py           # Full implementation + wrappers
│   └── user_config.py       # Full implementation + wrappers
└── system/
    ├── __init__.py          # Module exports
    ├── packages.py          # Full implementation (no wrappers)
    ├── services.py          # Full implementation (no wrappers)
    ├── boot.py              # Full implementation (no wrappers)
    ├── filesystem.py        # Full implementation (no wrappers)
    └── users.py             # Full implementation (no wrappers)
```

**Key Decision:** System modules have actual implementations; core modules wrap them for orchestration.

---

## Dependency Analysis

### Functions by Category

**System Operations (kod.system):**
- **packages.py:** 8 functions - depends on helpers in `kod.arch` (get_base_packages, etc.)
- **services.py:** 4 functions - direct implementations, minimal dependencies
- **boot.py:** 5 functions - depends on `kod.arch` (get_kernel_file), `kod.common` (exec_chroot)
- **filesystem.py:** 8 functions - direct implementations, uses `Path` and file I/O
- **users.py:** 4 functions - direct implementations, uses `kod.common` (exec_chroot)

**Workflow Orchestration (kod.core):**
- **install.py:** `configure_system()` - orchestrates multiple system operations
- **rebuild.py:** 3 functions - generation management
- **user_config.py:** 2 functions - user configuration management

### Refactoring Order (Simplest → Complex)

1. **filesystem.py** - No external dependencies; pure file I/O (8 functions)
2. **users.py** - Minimal dependencies on `kod.common` (4 functions)
3. **services.py** - Moderate dependencies, isolated logic (4 functions)
4. **boot.py** - Depends on `kod.arch`, more complex (5 functions)
5. **packages.py** - Complex dependencies on multiple arch functions (8 functions)
6. **rebuild.py** - Calls filesystem functions; orchestration (3 functions)
7. **user_config.py** - Calls multiple helpers (2 functions)
8. **install.py** - Calls all system operations; orchestration (1 function)

**Rationale:** Start with modules with the fewest dependencies, build up to orchestrators.

---

## Tasks

### Task 1: Refactor kod/system/filesystem.py

**Files:**
- Modify: `src/kod/system/filesystem.py`
- Modify: `src/kod/_core.py`
- Modify: `src/kod/core/__init__.py`
- Test: `tests/system/test_filesystem.py` (already exists, may add helpers)

**Interfaces:**
- Consumes: `kod.common.exec`, `Path` (stdlib)
- Produces: 8 functions in `kod.system.filesystem`:
  - `create_filesystem_hierarchy(partition_list, mount_point)`
  - `generate_fstab(partition_list, mount_point)`
  - `load_fstab(root_path)`
  - `update_fstab(root_path, new_mount_point_map)`
  - `create_next_generation(boot_part, root_part, generation)`
  - `change_subvol(partition_list, subvol, mount_points)`
  - `set_ro_mount(mount_point)`
  - `change_ro_mount(root_path)`

**Refactoring Pattern:**
1. Extract function implementations from `_core.py:422-1900` (grep for function definitions)
2. Move body to `kod/system/filesystem.py`
3. Update `_core.py` to import and re-export: `from kod.system.filesystem import update_fstab`
4. Verify wrappers in `kod/system/filesystem.py` now call local versions, not `_core`
5. Update `kod/core/__init__.py` exports if needed
6. Test and commit

**Implementation Steps:**

- [ ] **Step 1: Identify and extract filesystem.py implementations**

From `src/kod/_core.py`, find these function definitions and note their line ranges:
- `generate_fstab` (grep line number)
- `load_fstab`
- `create_filesystem_hierarchy`
- `update_fstab`
- `change_subvol`
- `set_ro_mount`
- `change_ro_mount`
- `create_next_generation`

Run: `grep -n "^def generate_fstab\|^def load_fstab\|^def create_filesystem_hierarchy\|^def update_fstab\|^def change_subvol\|^def set_ro_mount\|^def change_ro_mount\|^def create_next_generation" src/kod/_core.py`

- [ ] **Step 2: Read the implementations from _core.py**

For each function found in Step 1, read its full implementation including docstring. Note any helper functions it calls (e.g., if `generate_fstab` calls `exec_chroot`, that's a dependency).

Run: For each function at line N, `sed -n 'N,N+50p' src/kod/_core.py` and continue until you find the next function definition.

- [ ] **Step 3: Read current kod/system/filesystem.py**

`cat src/kod/system/filesystem.py` to see the thin wrapper structure.

- [ ] **Step 4: Create new filesystem.py with actual implementations**

Modify `src/kod/system/filesystem.py` to:
- Keep the imports at the top
- Replace each wrapper function with the actual implementation from `_core.py`
- Remove the internal wrapper imports (e.g., `from kod.core import ...`)
- Add necessary imports for any dependencies (e.g., `from kod.common import exec`)

Example pattern:
```python
# OLD: from kod.core import generate_fstab as _generate_fstab
# NEW: from kod.common import exec  # if needed

def generate_fstab(partition_list: List, mount_point: str) -> None:
    """[docstring from _core.py]"""
    # [actual implementation body from _core.py]
```

- [ ] **Step 5: Update _core.py to re-export from filesystem**

At the top of `src/kod/_core.py`, add:
```python
from kod.system.filesystem import (
    generate_fstab,
    load_fstab,
    create_filesystem_hierarchy,
    update_fstab,
    change_subvol,
    set_ro_mount,
    change_ro_mount,
    create_next_generation,
)
```

Remove the original function definitions from `_core.py` (or comment them out temporarily for safety).

- [ ] **Step 6: Verify backward compatibility**

Test that old imports still work:
```bash
python -c "from kod.core import update_fstab; print('✓ backward compat works')"
python -c "from kod.system.filesystem import update_fstab; print('✓ new import works')"
```

- [ ] **Step 7: Run filesystem tests**

`pytest tests/system/test_filesystem.py -v`

Expected: 3 passed (no changes to test logic, just implementation location).

- [ ] **Step 8: Run full test suite**

`pytest tests/ -q`

Expected: 59 passed, 10 skipped, 1 failed (no new failures).

- [ ] **Step 9: Commit**

```bash
git add src/kod/system/filesystem.py src/kod/_core.py
git commit -m "Phase 2b: move kod/system/filesystem.py implementations from _core.py"
```

---

### Task 2: Refactor kod/system/users.py

**Files:**
- Modify: `src/kod/system/users.py`
- Modify: `src/kod/_core.py`
- Test: `tests/system/test_users.py`

**Interfaces:**
- Consumes: `kod.common.exec_chroot`
- Produces: 4 functions in `kod.system.users`:
  - `proc_users(ctx, conf)`
  - `create_user(ctx, user, info)`
  - `proc_user_home(ctx, user, info)`
  - `create_kod_user(mount_point)`

**Steps:** (Same pattern as Task 1, but for users functions)

- [ ] **Step 1: Find users.py implementations in _core.py**

`grep -n "^def proc_users\|^def create_user\|^def proc_user_home\|^def create_kod_user" src/kod/_core.py`

- [ ] **Step 2: Extract and read implementations**

For each line from Step 1, read the function body completely.

- [ ] **Step 3: Read current kod/system/users.py**

`cat src/kod/system/users.py`

- [ ] **Step 4: Implement actual code in users.py**

Replace wrappers with actual implementations from `_core.py`.

- [ ] **Step 5: Update _core.py to re-export**

Add to top of `_core.py`:
```python
from kod.system.users import (
    proc_users,
    create_user,
    proc_user_home,
    create_kod_user,
)
```

Remove original definitions from `_core.py`.

- [ ] **Step 6: Verify backward compatibility**

```bash
python -c "from kod.core import create_user; print('✓')"
python -c "from kod.system.users import create_user; print('✓')"
```

- [ ] **Step 7: Run users tests**

`pytest tests/system/test_users.py -v`

Expected: 3 passed.

- [ ] **Step 8: Run full test suite**

`pytest tests/ -q`

Expected: 59 passed, 10 skipped, 1 failed.

- [ ] **Step 9: Commit**

```bash
git add src/kod/system/users.py src/kod/_core.py
git commit -m "Phase 2b: move kod/system/users.py implementations from _core.py"
```

---

### Task 3: Refactor kod/system/services.py

**Files:**
- Modify: `src/kod/system/services.py`
- Modify: `src/kod/_core.py`
- Test: `tests/system/test_services.py`

**Interfaces:**
- Consumes: `kod.common.exec_chroot`
- Produces: 4 functions in `kod.system.services`:
  - `enable_services(ctx, services, mount_point)`
  - `proc_services_to_enable(ctx, conf)`
  - `manage_services(ctx, services, action, mount_point)`
  - `proc_services(conf)`

**Steps:** (Same pattern as Tasks 1-2)

- [ ] **Step 1: Find services.py implementations in _core.py**

`grep -n "^def enable_services\|^def proc_services_to_enable\|^def manage_services\|^def proc_services" src/kod/_core.py`

- [ ] **Step 2: Extract and read implementations**

For each line, read the full function body.

- [ ] **Step 3: Read current kod/system/services.py**

`cat src/kod/system/services.py`

- [ ] **Step 4: Implement actual code in services.py**

Replace wrappers with actual implementations.

- [ ] **Step 5: Update _core.py to re-export**

Add imports and remove definitions.

- [ ] **Step 6: Verify backward compatibility**

Test old and new imports.

- [ ] **Step 7: Run services tests**

`pytest tests/system/test_services.py -v`

Expected: 4 passed.

- [ ] **Step 8: Run full test suite**

`pytest tests/ -q`

Expected: 59 passed, 10 skipped, 1 failed.

- [ ] **Step 9: Commit**

```bash
git add src/kod/system/services.py src/kod/_core.py
git commit -m "Phase 2b: move kod/system/services.py implementations from _core.py"
```

---

### Task 4: Refactor kod/system/boot.py

**Files:**
- Modify: `src/kod/system/boot.py`
- Modify: `src/kod/_core.py`
- Test: `tests/system/test_boot.py`

**Interfaces:**
- Consumes: `kod.common.exec_chroot`, `kod.arch.get_kernel_file`
- Produces: 5 functions in `kod.system.boot`:
  - `setup_bootloader(conf, partition_list, dist)`
  - `create_boot_entry(kernel_package, initramfs_img, partition_list, dist, cmdline=None)`
  - `get_kernel_version(mount_point)`
  - `update_kernel_hook(kernel_package, mount_point)`
  - `update_initramfs_hook(kernel_package, mount_point)`

**Key Note:** These functions have some interdependencies (e.g., `create_boot_entry` calls `get_kernel_version`). After moving, internal calls should resolve to local implementations.

**Steps:**

- [ ] **Step 1: Find boot.py implementations in _core.py**

`grep -n "^def setup_bootloader\|^def create_boot_entry\|^def get_kernel_version\|^def update_kernel_hook\|^def update_initramfs_hook" src/kod/_core.py`

- [ ] **Step 2: Extract and read implementations**

For each function, read the full body and note if it calls other functions in the list (internal calls).

- [ ] **Step 3: Read current kod/system/boot.py**

`cat src/kod/system/boot.py`

- [ ] **Step 4: Implement actual code in boot.py**

Replace wrappers with actual implementations. For internal calls (e.g., if `create_boot_entry` calls `get_kernel_version`), ensure they resolve to the local version in this module.

- [ ] **Step 5: Update _core.py to re-export**

Add imports and remove definitions.

- [ ] **Step 6: Verify backward compatibility**

Test imports.

- [ ] **Step 7: Run boot tests**

`pytest tests/system/test_boot.py -v`

Expected: 3 passed.

- [ ] **Step 8: Run full test suite**

`pytest tests/ -q`

Expected: 59 passed, 10 skipped, 1 failed.

- [ ] **Step 9: Commit**

```bash
git add src/kod/system/boot.py src/kod/_core.py
git commit -m "Phase 2b: move kod/system/boot.py implementations from _core.py"
```

---

### Task 5: Refactor kod/system/packages.py

**Files:**
- Modify: `src/kod/system/packages.py`
- Modify: `src/kod/_core.py`
- Test: `tests/system/test_packages.py`

**Interfaces:**
- Consumes: `kod.arch` (get_base_packages, etc.), `kod.common` (exec, exec_chroot)
- Produces: 8 functions in `kod.system.packages`:
  - `get_packages_to_install(conf)`
  - `manage_packages(ctx, packages, action, mount_point=None, chroot=False)`
  - `load_repos()`
  - `load_package_lock(state_path)`
  - `store_packages_services(state_path, packages, services)`
  - `get_packages_updates(repos, current)`
  - `update_all_packages(mount_point, new_generation, repos)`
  - `get_pending_packages(packages_to_install)`

**Complex Note:** `get_packages_to_install` calls several helpers (proc_desktop, proc_hardware, etc.). Some of these are also in `_core.py`. Decision: Move all helpers together into packages.py as internal functions.

**Steps:**

- [ ] **Step 1: Find packages.py implementations in _core.py**

`grep -n "^def get_packages_to_install\|^def manage_packages\|^def load_repos\|^def load_package_lock\|^def store_packages_services\|^def get_packages_updates\|^def update_all_packages\|^def get_pending_packages" src/kod/_core.py`

Also find helper functions:
`grep -n "^def proc_desktop\|^def proc_hardware\|^def proc_services\|^def proc_user_programs\|^def proc_system_packages\|^def proc_fonts" src/kod/_core.py`

- [ ] **Step 2: Extract and read implementations**

Read all main functions and all helpers. Note any interdependencies.

- [ ] **Step 3: Read current kod/system/packages.py**

`cat src/kod/system/packages.py`

- [ ] **Step 4: Implement actual code in packages.py**

Move all implementations (main functions + helpers) to packages.py. Helpers can be internal (no public export), main functions are public.

- [ ] **Step 5: Update _core.py to re-export**

Add imports for the 8 public functions only.

- [ ] **Step 6: Verify backward compatibility**

Test imports.

- [ ] **Step 7: Run packages tests**

`pytest tests/system/test_packages.py -v`

Expected: 3 passed.

- [ ] **Step 8: Run full test suite**

`pytest tests/ -q`

Expected: 59 passed, 10 skipped, 1 failed.

- [ ] **Step 9: Commit**

```bash
git add src/kod/system/packages.py src/kod/_core.py
git commit -m "Phase 2b: move kod/system/packages.py implementations from _core.py"
```

---

### Task 6: Refactor kod/core/rebuild.py

**Files:**
- Modify: `src/kod/core/rebuild.py`
- Modify: `src/kod/_core.py`
- Test: `tests/core/test_rebuild.py`

**Interfaces:**
- Consumes: `kod.system.filesystem` (create_next_generation), `kod.common` (exec)
- Produces: 3 functions in `kod.core.rebuild`:
  - `create_next_generation(boot_part, root_part, generation)`
  - `get_generation(mount_point)`
  - `get_max_generation()`

**Note:** These were already partially moved to filesystem.py in Task 1. This task updates the rebuild.py wrappers to call the filesystem versions directly (not through _core).

**Steps:**

- [ ] **Step 1: Verify implementations exist in filesystem.py**

Already moved in Task 1. Check `src/kod/system/filesystem.py` has `create_next_generation`.

- [ ] **Step 2: Find remaining rebuild functions in _core.py**

`grep -n "^def get_generation\|^def get_max_generation" src/kod/_core.py`

Extract and read these functions (they may not have been moved yet).

- [ ] **Step 3: Read current kod/core/rebuild.py**

`cat src/kod/core/rebuild.py`

- [ ] **Step 4: Update rebuild.py implementations**

If `get_generation` and `get_max_generation` are still in `_core.py`, move them into rebuild.py. Update `create_next_generation` call to import from filesystem instead of _core.

Pattern:
```python
from kod.system.filesystem import create_next_generation
from kod.common import exec

def get_max_generation() -> int:
    # Implementation from _core.py
```

- [ ] **Step 5: Update _core.py to re-export**

Add imports for the 3 functions.

- [ ] **Step 6: Verify backward compatibility**

Test imports.

- [ ] **Step 7: Run rebuild tests**

`pytest tests/core/test_rebuild.py -v`

Expected: 3 passed.

- [ ] **Step 8: Run full test suite**

`pytest tests/ -q`

Expected: 59 passed, 10 skipped, 1 failed.

- [ ] **Step 9: Commit**

```bash
git add src/kod/core/rebuild.py src/kod/_core.py
git commit -m "Phase 2b: move kod/core/rebuild.py implementations from _core.py"
```

---

### Task 7: Refactor kod/core/user_config.py

**Files:**
- Modify: `src/kod/core/user_config.py`
- Modify: `src/kod/_core.py`
- Test: `tests/core/test_user_config.py`

**Interfaces:**
- Consumes: `kod.system.users` (create_user, etc.), `kod.common` (exec_chroot)
- Produces: 2 functions in `kod.core.user_config`:
  - `configure_user_dotfiles(ctx, user, user_configs, dotfile_mngrs)`
  - `configure_user_scripts(ctx, user, user_configs)`

**Steps:**

- [ ] **Step 1: Find user_config implementations in _core.py**

`grep -n "^def configure_user_dotfiles\|^def configure_user_scripts" src/kod/_core.py`

- [ ] **Step 2: Extract and read implementations**

Read both functions.

- [ ] **Step 3: Read current kod/core/user_config.py**

`cat src/kod/core/user_config.py`

- [ ] **Step 4: Implement actual code in user_config.py**

Replace wrappers with actual implementations.

- [ ] **Step 5: Update _core.py to re-export**

Add imports and remove definitions.

- [ ] **Step 6: Verify backward compatibility**

Test imports.

- [ ] **Step 7: Run user_config tests**

`pytest tests/core/test_user_config.py -v`

Expected: 2 passed.

- [ ] **Step 8: Run full test suite**

`pytest tests/ -q`

Expected: 59 passed, 10 skipped, 1 failed.

- [ ] **Step 9: Commit**

```bash
git add src/kod/core/user_config.py src/kod/_core.py
git commit -m "Phase 2b: move kod/core/user_config.py implementations from _core.py"
```

---

### Task 8: Refactor kod/core/install.py

**Files:**
- Modify: `src/kod/core/install.py`
- Modify: `src/kod/_core.py`
- Test: `tests/core/test_install.py`

**Interfaces:**
- Consumes: `kod.system` (all modules), `kod.common` (exec_chroot), `kod.config`
- Produces: 1 function in `kod.core.install`:
  - `configure_system(conf, partition_list, mount_point)`

**Most Complex Task:** `configure_system` is a 125-line monolithic function that orchestrates multiple system operations. It's the highest-level workflow.

**Steps:**

- [ ] **Step 1: Find configure_system in _core.py**

`grep -n "^def configure_system" src/kod/_core.py`

- [ ] **Step 2: Extract and read the full implementation**

Read all 125+ lines of the function carefully. Note which system operations it calls (filesystem, services, etc.).

- [ ] **Step 3: Read current kod/core/install.py**

`cat src/kod/core/install.py`

- [ ] **Step 4: Implement actual code in install.py**

Move the full configure_system implementation to install.py. Update any internal calls to use the new module structure:
- Instead of calling `_exec_chroot(...)`, call `exec_chroot(...)`
- Instead of calling `_load_fstab(...)`, call `load_fstab(...)`
- etc.

Pattern:
```python
from kod.system.filesystem import generate_fstab, load_fstab
from kod.system.services import enable_services
from kod.common import exec_chroot

def configure_system(conf: Any, partition_list: List, mount_point: str) -> None:
    """[full docstring from _core.py]"""
    # [full implementation body from _core.py, with internal calls updated]
```

- [ ] **Step 5: Update _core.py to re-export**

Add import for configure_system.

- [ ] **Step 6: Verify backward compatibility**

Test import.

- [ ] **Step 7: Run install tests**

`pytest tests/core/test_install.py -v`

Expected: 1 passed.

- [ ] **Step 8: Run full test suite**

`pytest tests/ -q`

Expected: 59 passed, 10 skipped, 1 failed.

- [ ] **Step 9: Commit**

```bash
git add src/kod/core/install.py src/kod/_core.py
git commit -m "Phase 2b: move kod/core/install.py implementations from _core.py"
```

---

### Task 9: Cleanup and final _core.py audit

**Files:**
- Modify: `src/kod/_core.py`

**Purpose:** After all implementations have been moved, `_core.py` should contain only:
1. Imports from new modules (for re-export)
2. The backward-compatibility module docstring
3. Constants like `os_release`, `base_distribution`
4. Possibly a few pure utility functions (if any exist)

**Steps:**

- [ ] **Step 1: List what remains in _core.py**

Run: `grep -n "^def " src/kod/_core.py | head -20`

Expected: Should see mostly helper imports and re-exports, not original implementations.

- [ ] **Step 2: Identify helper functions vs re-exports**

For any function still in `_core.py`, check if it's:
- A helper only called internally by other functions (should be moved to the module that calls it)
- A helper called by multiple modules (consider moving to a new `kod.system.helpers` or leaving as-is if backward compat needed)
- A utility like path normalization (document and keep in `_core.py` as part of backward compat layer)

- [ ] **Step 3: Review imports in _core.py**

All imports at the top should be:
- `from kod.system.X import ...` or `from kod.core.Y import ...` (re-exports)
- Standard library imports (`glob`, `json`, `os`, `re`, `Path`, etc.) - keep for utilities
- External imports (`lupa`) - keep for constants/utilities
- `from kod.arch`, `from kod.common`, `from kod.filesystem` - keep (these are dependencies)

- [ ] **Step 4: Verify no circular imports**

Test:
```bash
python -c "import kod.system.packages; print('✓ packages loads')"
python -c "import kod.core.install; print('✓ install loads')"
python -c "from kod import core; print('✓ core package loads')"
```

- [ ] **Step 5: Generate _core.py audit report**

Count remaining lines and functions:
```bash
wc -l src/kod/_core.py
grep "^def " src/kod/_core.py | wc -l
```

Expected: Significantly reduced from 2,054 lines and 59 functions.

- [ ] **Step 6: Add comment header to _core.py**

At the top (after the docstring), add:
```python
# Phase 2b: This module is now a backward-compatibility layer.
# All implementations have been moved to kod.system.* and kod.core.* modules.
# New code should import from those modules directly.
# Existing code importing from kod.core continues to work via re-exports below.
```

- [ ] **Step 7: Run full test suite**

`pytest tests/ -q`

Expected: 59 passed, 10 skipped, 1 failed.

- [ ] **Step 8: Commit**

```bash
git add src/kod/_core.py
git commit -m "Phase 2b: cleanup _core.py - now pure backward-compat re-export layer"
```

---

### Task 10: Final verification and Phase 2b summary

**Files:**
- Modify: `SCAFFOLD.md`
- Create: `PHASE_2B_SUMMARY.md` (optional, for documentation)

**Purpose:** Verify Phase 2b is complete and document the refactoring results.

**Steps:**

- [ ] **Step 1: Run full test suite one more time**

`pytest tests/ -v`

Expected: 59 passed, 10 skipped, 1 failed (pre-existing).

- [ ] **Step 2: Test backward compatibility**

Create a test script to verify all old import patterns still work:
```bash
python -c "
from kod.core import configure_system, get_packages_to_install
from kod.core import create_user, proc_services
from kod.core import setup_bootloader, get_kernel_version
from kod.core import update_fstab, load_fstab
print('✓ All backward-compat imports work')
"
```

- [ ] **Step 3: Test new import patterns**

```bash
python -c "
from kod.system.packages import get_packages_to_install
from kod.system.users import create_user
from kod.system.services import proc_services
from kod.system.boot import setup_bootloader
from kod.system.filesystem import update_fstab
from kod.core.install import configure_system
from kod.core.rebuild import get_max_generation
from kod.core.user_config import configure_user_dotfiles
print('✓ All new imports work')
"
```

- [ ] **Step 4: Verify git status is clean**

`git status`

Expected: "working tree clean"

- [ ] **Step 5: Generate Phase 2b commit log**

`git log --oneline | head -10`

Expected: 10 Phase 2b commits (one per task).

- [ ] **Step 6: Update SCAFFOLD.md**

Change Phase 2b status from "in progress" to "complete". Example:
```markdown
## Phase 2b: Function Internals Refactoring
- [x] Move kod/system/filesystem.py implementations
- [x] Move kod/system/users.py implementations
- [x] Move kod/system/services.py implementations
- [x] Move kod/system/boot.py implementations
- [x] Move kod/system/packages.py implementations
- [x] Move kod/core/rebuild.py implementations
- [x] Move kod/core/user_config.py implementations
- [x] Move kod/core/install.py implementations
- [x] Cleanup _core.py re-export layer
- [x] Final verification and documentation

**Result:** 59 tests passing, 10 skipped, 1 pre-existing failure. All implementations moved to new modules. Full backward compatibility maintained. Old imports continue to work.
```

- [ ] **Step 7: Commit final update**

```bash
git add SCAFFOLD.md
git commit -m "Phase 2b complete: all implementations refactored to modular structure"
```

---

## Success Criteria

After all tasks complete:

✅ **Functionality preserved:** All 59 tests pass; no new regressions
✅ **Backward compatibility:** Old imports (`from kod.core import X`) still work
✅ **New module structure:** All implementations in `kod.system.*` and `kod.core.*`
✅ **Clean re-export layer:** `_core.py` is ~10-20% of original size, pure re-exports
✅ **No circular imports:** All module dependencies flow correctly
✅ **Git history:** Clear commit per task showing what moved where
✅ **Documentation:** SCAFFOLD.md updated; Phase 2b complete

---

## Notes for Implementers

1. **Dependencies:** Each task builds on previous ones. If a task calls a function from a later task (e.g., rebuild.py calls filesystem.py), move the dependency first or update imports after both are done.

2. **Import gotchas:** Python imports can be tricky with circular dependencies. If you see "circular import" errors:
   - Check that `kod.system.*` modules never import `kod.core.*` (workflows should not be in operations)
   - Check that `kod.core.*` modules import operations, not vice versa
   - Use `from kod.system.X import func` inside functions (lazy import) if needed

3. **Re-export pattern in _core.py:**
   ```python
   # At top of _core.py after docstring:
   from kod.system.packages import (
       get_packages_to_install,
       manage_packages,
       # ... etc
   )
   # DO NOT repeat the function definition
   # Just the import exposes it as if defined here
   ```

4. **Testing:** After each task, always run the full test suite (`pytest tests/ -q`), not just the task's module tests. This catches hidden interdependencies.

5. **Helpers:** Some functions in `_core.py` are helpers called by others (e.g., `proc_desktop` is called by `get_packages_to_install`). When you move the main function, move the helpers it calls too, and make them internal (no underscore prefix needed unless private).

---
