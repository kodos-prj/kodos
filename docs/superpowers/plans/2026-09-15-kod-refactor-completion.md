# Kodos Refactor Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Kodos architecture refactoring by eliminating backward-compatibility overhead, consolidating duplicate modules, simplifying over-engineered components, and preparing the codebase for full Phase 5d implementation.

**Architecture:** 
1. Eliminate lazy imports and __getattr__ overhead from core/__init__.py by resolving all re-exports at import time
2. Merge top-level filesystem.py into system/filesystem.py to eliminate duplication
3. Abstract distro-specific dependencies (get_kernel_file, get_base_packages) via factory or strategy pattern
4. Simplify Program class by removing speculative abstractions and error handling boilerplate
5. (Optional) Split kod.py CLI commands into modular subcommands in cli/ directory

**Tech Stack:** Python 3.14, pytest, lupa (Lua runtime), pathlib, typing

**Spec:** 
- Architecture: Phases 1-3 complete, Phase 5 ongoing
- Current state: 700 tests passing, 17 skipped
- Goal: Clean architecture, zero backward-compat shims, no duplicate modules

---

## Global Constraints

- **Minimum test pass rate:** 700 passing (current baseline)
- **No new dependencies:** Use stdlib only; lupa already installed
- **Python version floor:** 3.11+
- **File organization:** Keep registry/ as-is (Phase 3 complete), don't convert to Lua
- **Naming convention:** Follow existing patterns (snake_case functions, PascalCase classes)
- **Git discipline:** Small, focused commits per task (one feature per commit)

---

## File Structure

### Current Layout
```
src/kod/
├── __init__.py
├── kod.py                           # 685 lines: CLI entry, all commands mixed in
├── context.py                       # ✓ Context class (new, clean)
├── filesystem.py                    # 153 lines: FsEntry, get_partition_devices
├── system/
│   ├── filesystem.py                # 146 lines: generate_fstab, load_fstab, change_subvol, etc.
│   ├── boot.py                      # imports from system/distro/arch
│   ├── packages.py                  # imports from system/distro/arch
│   ├── distro/
│   │   ├── arch.py                  # ✓ (moved from top-level)
│   │   └── debian.py                # ✓ (moved from top-level)
│   └── ...
├── core/
│   ├── __init__.py                  # ✗ Has __getattr__ lazy imports (to remove)
│   └── user_config.py
├── registry/
│   ├── programs.py                  # 680 lines: Program class (can simplify)
│   ├── loader.py                    # 341 lines: plugin discovery
│   └── builtin/                     # .lua program definitions
└── ...
```

### After Refactoring
```
src/kod/
├── __init__.py
├── kod.py                           # ✓ Or split into cli/
├── context.py                       # ✓ (stays)
├── filesystem.py                    # ✗ MERGE INTO system/filesystem.py
├── system/
│   ├── filesystem.py                # ✓ CONSOLIDATED: all filesystem ops
│   ├── boot.py                      # ✓ Uses factory for distro selection
│   ├── packages.py                  # ✓ Uses factory for distro selection
│   ├── distro/
│   │   ├── __init__.py              # ✓ Exports factory: get_distro_module()
│   │   ├── arch.py                  # ✓ (unchanged)
│   │   └── debian.py                # ✓ (unchanged)
│   └── ...
├── core/
│   ├── __init__.py                  # ✓ SIMPLIFIED: direct exports, no __getattr__
│   └── user_config.py
├── registry/
│   ├── programs.py                  # ✓ SIMPLIFIED (optional)
│   ├── loader.py                    # ✓ (unchanged)
│   └── builtin/
└── ...
```

---

## Task Breakdown

### Task 1: Remove Lazy Imports from core/__init__.py

**Files:**
- Modify: `src/kod/core/__init__.py`
- Test: `tests/core/test_imports.py` (new)

**Interfaces:**
- **Consumes:** Core functions from system.packages, system.services, system.boot
- **Produces:** Direct imports (no __getattr__), all re-exports available at module load time

**Rationale:** 
Lazy imports via `__getattr__` add runtime overhead and make the dependency graph unclear. Since the file structure is now clean, collapse the lazy imports to direct imports at module level.

**Steps:**

- [ ] **Step 1: Understand current __getattr__ in core/__init__.py**

Read current `src/kod/core/__init__.py` lines 267-286 (the __getattr__ function). This maps function names to module imports. We'll flatten this.

- [ ] **Step 2: Write test to verify direct imports work**

```python
# tests/core/test_imports.py
import pytest

def test_core_imports_all_exports_at_load_time():
    """Verify all exports from kod.core are available without __getattr__."""
    from kod.core import (
        # Phase 2b re-exports from kod.system.packages
        get_packages_to_install,
        load_repos,
        load_package_lock,
        store_packages_services,
        get_packages_updates,
        update_all_packages,
        get_pending_packages,
        manage_packages_shell,
        # Phase 2b re-exports from kod.system.services
        enable_services,
        enable_user_services,
        get_services_to_enable,
        proc_desktop_services,
        proc_services,
        proc_services_to_enable,
        # Phase 2b re-exports from kod.system.boot
        create_boot_entry_hook,
        get_kernel_version,
        update_kernel_hook,
        update_initramfs_hook,
    )
    
    # Verify they are callable
    assert callable(get_packages_to_install)
    assert callable(enable_services)
    assert callable(create_boot_entry_hook)

def test_core_module_has_no_getattr():
    """Verify kod.core module does not use __getattr__."""
    import kod.core
    assert not hasattr(kod.core, '__getattr__'), \
        "kod.core should not have __getattr__ after refactoring"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /home/abuss/Work/devel/analysis/kodos
pytest tests/core/test_imports.py -xvs
```

Expected: FAIL on second assertion (module has __getattr__)

- [ ] **Step 4: Replace __getattr__ with direct imports**

Edit `src/kod/core/__init__.py`:
1. Delete the `__getattr__` function (lines ~267-286)
2. Add direct imports at the top after existing imports:

```python
# Phase 2b re-exports from kod.system.packages (direct import, no lazy load)
from kod.system.packages import (
    get_packages_to_install,
    load_repos,
    load_package_lock,
    store_packages_services,
    get_packages_updates,
    update_all_packages,
    get_pending_packages,
    manage_packages_shell,
)

# Phase 2b re-exports from kod.system.services (direct import, no lazy load)
from kod.system.services import (
    enable_services,
    enable_user_services,
    get_services_to_enable,
    proc_desktop_services,
    proc_services,
    proc_services_to_enable,
)

# Phase 2b re-exports from kod.system.boot (direct import, no lazy load)
from kod.system.boot import (
    create_boot_entry_hook,
    get_kernel_version,
    update_kernel_hook,
    update_initramfs_hook,
)
```

3. Update `__all__` to include the new imports (should already list them, verify)

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/core/test_imports.py -xvs
```

Expected: PASS (all imports available, no __getattr__)

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -q
```

Expected: 700+ passed, same count as before or higher

- [ ] **Step 7: Commit**

```bash
git add src/kod/core/__init__.py tests/core/test_imports.py
git commit -m "refactor(core): replace lazy __getattr__ with direct imports

- Remove __getattr__ function from core/__init__.py (Phase 2b overhead)
- Direct import all re-exports from system.packages, system.services, system.boot
- Add test to verify all exports available at load time
- No behavioral change, cleaner dependency graph
- Tests: 700+ passing"
```

---

### Task 2: Merge filesystem.py into system/filesystem.py

**Files:**
- Modify: `src/kod/system/filesystem.py`
- Modify: All files importing from `kod.filesystem`
- Test: `tests/system/test_filesystem.py` (update existing)

**Interfaces:**
- **Consumes:** FsEntry class, get_partition_devices() from old filesystem.py
- **Produces:** All functions and classes in `kod.system.filesystem`, old `kod.filesystem` no longer exists

**Rationale:** 
Two filesystem modules (top-level + system/) causes confusion. Consolidate into one module in system/ where all system operations live.

**Steps:**

- [ ] **Step 1: Identify all imports of kod.filesystem**

```bash
grep -r "from kod.filesystem\|import.*filesystem" src/kod tests --include="*.py" | grep -v "system/filesystem"
```

List all files that import from top-level filesystem.py. Should find ~5-10 files.

- [ ] **Step 2: Read both filesystem modules**

Read `src/kod/filesystem.py` (153 lines) and `src/kod/system/filesystem.py` (146 lines) to understand what each does.

Current state:
- `filesystem.py`: FsEntry class, get_partition_devices()
- `system/filesystem.py`: generate_fstab, load_fstab, change_subvol, create_next_generation, get_max_generation

After merge: all functions in `system/filesystem.py`

- [ ] **Step 3: Copy FsEntry and get_partition_devices to system/filesystem.py**

Edit `src/kod/system/filesystem.py`:
1. Copy the FsEntry class from `src/kod/filesystem.py` to the top of `src/kod/system/filesystem.py`
2. Copy get_partition_devices() function
3. Preserve all imports needed by FsEntry and get_partition_devices

- [ ] **Step 4: Update all imports across codebase**

Find all files importing from `kod.filesystem`:

```bash
grep -r "from kod.filesystem" src/kod tests --include="*.py"
```

For each file, replace:
- `from kod.filesystem import FsEntry` → `from kod.system.filesystem import FsEntry`
- `from kod.filesystem import get_partition_devices` → `from kod.system.filesystem import get_partition_devices`

- [ ] **Step 5: Delete old filesystem.py**

```bash
rm src/kod/filesystem.py
```

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -q
```

Expected: 700+ passed

- [ ] **Step 7: Commit**

```bash
git add src/kod/system/filesystem.py src/kod/*.py tests/**/*.py
git add -u src/kod/filesystem.py  # Stage deletion
git commit -m "refactor(filesystem): consolidate into system/filesystem.py

- Move FsEntry class from kod.filesystem to kod.system.filesystem
- Move get_partition_devices() to kod.system.filesystem
- Update all imports across codebase
- Delete top-level kod/filesystem.py (no longer needed)
- No behavioral change, eliminates duplication
- Tests: 700+ passing"
```

---

### Task 3: Create Distro Abstraction Factory

**Files:**
- Create: `src/kod/system/distro/factory.py` (new)
- Modify: `src/kod/system/boot.py`
- Modify: `src/kod/system/packages.py`
- Modify: `src/kod/system/distro/__init__.py`
- Test: `tests/system/test_distro_factory.py` (new)

**Interfaces:**
- **Consumes:** `kod.system.distro.arch`, `kod.system.distro.debian`
- **Produces:** `get_distro_module()` factory function, returns module with distro-specific functions

**Rationale:** 
system/boot.py and system/packages.py directly import from system/distro/arch.py, creating tight coupling. Use a factory function to abstract distro selection, making it easy to add new distros and avoid hardcoded imports.

**Steps:**

- [ ] **Step 1: Write test for factory function**

```python
# tests/system/test_distro_factory.py
import pytest

def test_get_distro_module_returns_arch_by_default():
    """Factory should return arch module by default."""
    from kod.system.distro.factory import get_distro_module
    
    distro = get_distro_module("arch")
    
    assert hasattr(distro, 'get_kernel_file')
    assert hasattr(distro, 'get_base_packages')
    assert hasattr(distro, 'proc_repos')

def test_get_distro_module_returns_debian():
    """Factory should return debian module when requested."""
    from kod.system.distro.factory import get_distro_module
    
    distro = get_distro_module("debian")
    
    assert hasattr(distro, 'get_kernel_file')
    assert hasattr(distro, 'get_base_packages')
    assert hasattr(distro, 'proc_repos')

def test_get_distro_module_raises_on_unknown():
    """Factory should raise ValueError on unknown distro."""
    from kod.system.distro.factory import get_distro_module
    
    with pytest.raises(ValueError, match="Unknown distro"):
        get_distro_module("unknown_distro")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/system/test_distro_factory.py -xvs
```

Expected: FAIL (factory module doesn't exist)

- [ ] **Step 3: Create factory module**

Create `src/kod/system/distro/factory.py`:

```python
"""Distro module factory (strategy pattern for distro selection).

Abstracts distro-specific imports so boot.py and packages.py don't hardcode
distro module names. Makes adding new distros easy.
"""

from typing import Any
import importlib


def get_distro_module(distro_name: str) -> Any:
    """Get the distro-specific module for the given distro.
    
    Args:
        distro_name: The distro name ("arch", "debian", etc.)
        
    Returns:
        The distro module (kod.system.distro.arch or kod.system.distro.debian)
        
    Raises:
        ValueError: If distro_name is not supported.
    """
    supported = {"arch", "debian"}
    
    if distro_name not in supported:
        raise ValueError(f"Unknown distro: {distro_name}. Supported: {supported}")
    
    # Use importlib to dynamically import the distro module
    module = importlib.import_module(f"kod.system.distro.{distro_name}")
    return module
```

- [ ] **Step 4: Update system/distro/__init__.py to export factory**

Edit `src/kod/system/distro/__init__.py`:

```python
"""Distribution-specific system management.

This package contains distribution-specific implementations for package management,
system configuration, and initialization. Currently supports Arch Linux with Debian
support available.
"""

from .factory import get_distro_module  # noqa: F401

__all__ = ["get_distro_module"]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/system/test_distro_factory.py -xvs
```

Expected: PASS

- [ ] **Step 6: Update system/boot.py to use factory**

Current code in `src/kod/system/boot.py` line 9:

```python
from kod.system.distro.arch import get_kernel_file
```

Replace with:

```python
from kod.system.distro.factory import get_distro_module
```

Then update calls to get_kernel_file to use:

```python
distro = get_distro_module("arch")
kernel_file, kver = distro.get_kernel_file(mount_point)
```

- [ ] **Step 7: Update system/packages.py to use factory**

Current code in `src/kod/system/packages.py` line 10:

```python
from kod.system.distro.arch import get_base_packages, get_list_of_dependencies
```

Replace with:

```python
from kod.system.distro.factory import get_distro_module
```

Then update calls to use:

```python
distro = get_distro_module("arch")
packages = distro.get_base_packages(conf)
deps = distro.get_list_of_dependencies(pkg)
```

- [ ] **Step 8: Run tests for boot and packages modules**

```bash
pytest tests/system/test_boot.py tests/system/test_packages.py -q
```

Expected: All tests pass

- [ ] **Step 9: Run full test suite**

```bash
pytest tests/ -q
```

Expected: 700+ passed

- [ ] **Step 10: Commit**

```bash
git add src/kod/system/distro/factory.py src/kod/system/distro/__init__.py src/kod/system/boot.py src/kod/system/packages.py tests/system/test_distro_factory.py
git commit -m "refactor(distro): add factory abstraction for distro selection

- Create kod/system/distro/factory.py with get_distro_module() function
- Replace direct imports in boot.py and packages.py with factory calls
- Makes distro-specific logic pluggable, easier to add new distros
- No behavioral change, cleaner dependency injection
- Tests: 700+ passing"
```

---

## Refactor Completion Checklist

### Must Complete (High Priority)
- [ ] Task 1: Remove lazy imports from core/__init__.py
- [ ] Task 2: Merge filesystem.py into system/filesystem.py
- [ ] Task 3: Create distro factory abstraction

### Verification After All Tasks
- [ ] Run full test suite: `pytest tests/ -q`
- [ ] Verify 700+ tests pass
- [ ] Check for import errors: `python -c "from kod.core import *"`
- [ ] Verify no lazy imports: `python -c "import kod.core; assert not hasattr(kod.core, '__getattr__')"`

---

## Execution Path

**Plan complete and saved to `docs/superpowers/plans/2026-09-15-kod-refactor-completion.md`**

**Two execution options:**

**1. Subagent-Driven (recommended)** 
- I dispatch a fresh subagent per task, review between tasks, fast iteration
- Best for: complex tasks, high risk, learning the codebase

**2. Inline Execution**
- Execute tasks in this session, batch execution with checkpoints
- Best for: quick fixes, straightforward refactoring

**Which approach would you prefer?**
