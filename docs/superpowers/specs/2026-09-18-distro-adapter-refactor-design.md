# Distro Adapter Refactor: Design Specification

**Date**: September 18, 2026  
**Author**: Architecture Refactoring Session  
**Status**: Ready for Implementation  
**Scope**: KodOS Phase 5d—Distro Module Architecture

---

## Executive Summary

The distro layer (`src/kod/system/distro/`) contains **800 lines of 95% duplicated code** across arch.py and debian.py. This specification defines a **Strategy Pattern refactor** using base adapter class + concrete distro subclasses to eliminate duplication, establish single sources of truth, and simplify adding new distros.

**Expected outcome:**
- Remove ~600 lines of duplication
- Establish clear adapter interface
- No breaking API changes
- Enable single-source maintenance of common logic

---

## Problem Statement

### Current Architecture Issues

#### 1. Massive Copy-Paste Duplication

| Function | Duplication | Status |
|----------|-------------|--------|
| `get_base_packages()` | 100% logic, 0% params | Config differs only; flow identical |
| `install_essentials_pkgs()` | 95% logic, 5% commands | Same flow, different tool commands |
| `get_kernel_file()` | 90% logic, 10% parsing | Same algorithm, different file parsing |
| `get_list_of_dependencies()` | 100% identical code | Direct copy-paste |
| `proc_repos()` | 95% logic | Distro checks only differ |
| `refresh_package_db()` | 100% logic, 0% params | Exact same code in both files |
| `kernel_update_required()` | 90% logic | Same comparison, different output parser |
| `generale_package_lock()` | 100% logic, 0% params | Exact same code (with typo!) |

#### 2. Bugs From Duplication

1. **debian.py line 175**: `get_list_of_dependencies()` calls `pacman -Sgq` (Arch-specific command)
   - Will fail on Debian systems
   - Artifact of copy-paste without adaptation

2. **Function name typo**: `generale_package_lock()` → should be `generate_package_lock()`
   - Exists in both files
   - Typo duplicated everywhere

3. **Inconsistent error handling**: Missing validation in some places, verbose in others
   - No consistency across distros
   - Bug fixes must be applied twice

#### 3. No Abstraction Layer

- Factory exists (`distro/factory.py`) but only does dynamic imports
- Callers (kod.py, boot.py) directly call distro functions
- No unified interface; each distro module has independent function signatures
- Adding a new distro means copying 800+ lines

#### 4. Code Organization

Current structure:
```
distro/
├── factory.py        # Dynamic import dispatcher (doesn't reduce duplication)
├── arch.py           # 380 lines (100% execution, 95% duplicated)
├── debian.py         # 420 lines (100% execution, 95% duplicated)
└── __init__.py
```

**Problem**: factory doesn't unify the interface; it only avoids hardcoding import names.

---

## Solution Design

### Architecture

**Strategy Pattern with Adapter Base Class**:

```
distro/
├── base.py                  # DistroAdapter base class (common logic)
│   └── ~400 lines: all algorithms implemented once
├── adapters/
│   ├── arch.py             # ArchAdapter(DistroAdapter)
│   │   └── ~80 lines: override distro-specific methods only
│   └── debian.py           # DebianAdapter(DistroAdapter)
│       └── ~100 lines: override distro-specific methods only
├── factory.py              # get_distro_module() → loads adapter class
├── __init__.py             # Export public API
└── (removed: old arch.py, debian.py)
```

### Base Adapter Class (base.py)

**Purpose**: Single source of truth for all distro-agnostic logic.

**Public interface** (all distros implement these):

```python
class DistroAdapter:
    """Base class for distro-specific package management.
    
    Subclasses override distro-specific parsing/command generation.
    Common algorithms live here (once).
    """
    
    # To be overridden by subclasses
    @property
    def package_manager(self) -> str:
        """e.g., 'pacman', 'apt' — used in error messages"""
        raise NotImplementedError
    
    def _get_base_packages_config(self, conf: Any) -> dict:
        """Distro-specific base packages list.
        
        Return: {"kernel": "...", "base": [...]}
        """
        raise NotImplementedError
    
    def _install_command(self, packages: list, mount_point: str) -> str:
        """Distro-specific install command (pacstrap vs apt).
        
        Return: shell command string
        """
        raise NotImplementedError
    
    def _parse_kernel_file(self, output: str) -> Tuple[str, str]:
        """Parse kernel file path from distro-specific output.
        
        Args: Raw output from package manager query
        Return: (kernel_file_path, kernel_version)
        """
        raise NotImplementedError
    
    def _parse_installed_packages(self, output: str) -> dict:
        """Parse installed package list (dpkg vs pacman format).
        
        Return: {package_name: version, ...}
        """
        raise NotImplementedError
    
    # Common logic (implemented once in base class)
    def get_base_packages(self, conf: Any) -> dict:
        """Public: Get packages to install. Uses _get_base_packages_config()."""
        packages = self._get_base_packages_config(conf)
        if conf.boot and conf.boot.kernel and conf.boot.kernel.package:
            packages["kernel"] = conf.boot.kernel.package
        return packages
    
    def install_essentials_pkgs(self, base_pkgs: dict, mount_point: str) -> None:
        """Public: Install packages. Uses _install_command()."""
        cmd = self._install_command(base_pkgs, mount_point)
        exec(cmd)
    
    def get_kernel_file(self, mount_point: str, package: str = "linux") -> Tuple[str, str]:
        """Public: Get kernel file. Uses _parse_kernel_file()."""
        # Common logic: query package manager, validate output, parse
        output = self._query_package_manager_kernel(mount_point, package)
        if not output.strip():
            raise RuntimeError(f"No kernel found for {package}")
        return self._parse_kernel_file(output)
    
    def generate_package_lock(self, mount_point: str, state_path: str) -> None:
        """Public: Generate packages.lock file. Uses _parse_installed_packages()."""
        # Common logic: query, parse, write
        output = exec_chroot("get packages", mount_point=mount_point, get_output=True)
        packages = self._parse_installed_packages(output)
        with open(f"{state_path}/packages.lock", "w") as f:
            # Common write logic
            for pkg, ver in packages.items():
                f.write(f"{pkg} {ver}\n")
    
    # ... (all other public methods, each using override methods)
```

### Arch Adapter (adapters/arch.py)

**Purpose**: Arch-specific implementations only (~80 lines).

```python
from kod.system.distro.base import DistroAdapter

class ArchAdapter(DistroAdapter):
    """Arch Linux specific package management."""
    
    @property
    def package_manager(self) -> str:
        return "pacman"
    
    def _get_base_packages_config(self, conf: Any) -> dict:
        """Arch-specific base packages."""
        microcode = self._detect_cpu_microcode()
        return {
            "kernel": "linux",
            "base": [
                "base", "base-devel", "debugedit", "fakeroot", microcode,
                "btrfs-progs", "linux-firmware", "bash-completion", "mlocate",
                "sudo", "schroot", "whois", "dracut", "git", "arch-install-scripts",
            ],
        }
    
    def _install_command(self, packages: list, mount_point: str) -> str:
        kernel = packages["kernel"]
        base = packages["base"]
        return f"pacstrap -K {mount_point} {kernel} {' '.join(base)}"
    
    def _parse_kernel_file(self, output: str) -> Tuple[str, str]:
        """Parse: 'arch kernel-package     6.10.10-arch1-1 /usr/lib/modules/6.10.10-arch1-1/vmlinuz'"""
        kernel_file = output.split(" ")[-1].strip()
        kver = kernel_file.split("/")[-2]
        if not kver or kver.isspace():
            raise RuntimeError(f"Could not extract kernel version from {kernel_file}")
        return kernel_file, kver
    
    def _parse_installed_packages(self, output: str) -> dict:
        """Parse: 'linux 6.10.10-arch1-1'"""
        packages = {}
        for line in output.split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    packages[parts[0]] = parts[1]
        return packages
    
    # ... (other Arch-specific overrides)
```

### Debian Adapter (adapters/debian.py)

**Purpose**: Debian-specific implementations only (~100 lines).

```python
from kod.system.distro.base import DistroAdapter

class DebianAdapter(DistroAdapter):
    """Debian/Ubuntu specific package management."""
    
    @property
    def package_manager(self) -> str:
        return "apt"
    
    def _get_base_packages_config(self, conf: Any) -> dict:
        """Debian-specific base packages."""
        return {
            "kernel": "linux-image-amd64",
            "base": [
                "btrfs-progs", "systemd-boot", "locales",
                "sudo", "schroot", "whois", "dracut", "git",
            ],
        }
    
    def _install_command(self, packages: list, mount_point: str) -> str:
        exec("apt install -y debootstrap gdisk")
        exec("debootstrap --merged-usr testing /mnt")
        kernel = packages["kernel"]
        base = packages["base"]
        return f"apt-get install -y {kernel} {' '.join(base)}"
    
    def _parse_kernel_file(self, output: str) -> Tuple[str, str]:
        """Parse apt-cache depends output: extracts kernel package name."""
        kernel_package = output.split(":")[1].strip()
        kver = kernel_package.split("-", 2)[-1]
        if not kver or kver.isspace():
            raise RuntimeError(f"Could not extract version from {kernel_package}")
        return kernel_package, kver
    
    def _parse_installed_packages(self, output: str) -> dict:
        """Parse dpkg -l format: 'ii  package-name  version  arch  description'"""
        packages = {}
        for line in output.split("\n"):
            if line.startswith("ii "):
                parts = re.split(r"\s+", line.strip())
                if len(parts) >= 3:
                    packages[parts[1]] = parts[2]
        return packages
    
    # ... (other Debian-specific overrides)
```

### Factory (factory.py, modified)

**Purpose**: Load adapter class, not just the module.

```python
def get_distro_module(distro_name: str) -> DistroAdapter:
    """Get distro adapter instance.
    
    Args:
        distro_name: "arch" or "debian"
        
    Returns:
        Adapter instance (ArchAdapter or DebianAdapter)
    """
    supported = {"arch": "ArchAdapter", "debian": "DebianAdapter"}
    
    if distro_name not in supported:
        raise ValueError(f"Unknown distro: {distro_name}")
    
    module = importlib.import_module(f"kod.system.distro.adapters.{distro_name}")
    adapter_class = getattr(module, supported[distro_name])
    return adapter_class()  # Return instance, not class
```

---

## API Compatibility

### External Interface (kod.py, boot.py)

**Before:**
```python
dist = get_distro_module("arch")
dist.get_base_packages(conf)
dist.install_essentials_pkgs(packages, mount_point)
```

**After:**
```python
dist = get_distro_module("arch")
dist.get_base_packages(conf)
dist.install_essentials_pkgs(packages, mount_point)
```

**Result**: Identical. No callers need to change.

---

## Testing Strategy

### Base Class Testing

Test common logic once in `tests/system/test_distro_base.py`:
- Algorithm correctness
- Error handling consistency
- Edge cases (malformed output, missing packages, etc.)

### Adapter-Specific Testing

Test parsing/command generation in `tests/system/test_distro_adapters.py`:
- Arch: kernel file parsing (Arch format)
- Debian: dpkg parsing (Debian format)
- Each adapter's package lists
- Each adapter's install command generation

### Integration Testing

Verify adapters work end-to-end with existing kod.py flow:
- `kod install` with Arch config
- `kod rebuild` with Debian config
- Package lock generation

---

## Files Created/Modified/Deleted

### Create

| File | Lines | Purpose |
|------|-------|---------|
| `src/kod/system/distro/base.py` | ~400 | DistroAdapter base class |
| `src/kod/system/distro/adapters/__init__.py` | ~5 | Package marker |
| `src/kod/system/distro/adapters/arch.py` | ~80 | ArchAdapter |
| `src/kod/system/distro/adapters/debian.py` | ~100 | DebianAdapter |

### Modify

| File | Changes |
|------|---------|
| `src/kod/system/distro/factory.py` | Update import path to adapters/ |
| `src/kod/system/distro/__init__.py` | Ensure export of get_distro_module() |
| `tests/system/test_distro_factory.py` | Update imports + add adapter tests |

### Delete

| File | Reason |
|------|--------|
| `src/kod/system/distro/arch.py` | Consolidated into base + ArchAdapter |
| `src/kod/system/distro/debian.py` | Consolidated into base + DebianAdapter |

---

## Implementation Phases

### Phase 1: Abstraction (base.py)

1. Create `base.py` with DistroAdapter class
2. Implement all public methods (common logic)
3. Define abstract methods for overrides (parsing, commands)
4. Add docstrings and validation

### Phase 2: Arch Adapter

1. Create `adapters/arch.py`
2. Implement ArchAdapter with overrides for:
   - CPU microcode detection
   - Base packages
   - Kernel file parsing
   - Package lock parsing
   - Install command
3. Verify against original arch.py logic

### Phase 3: Debian Adapter

1. Create `adapters/debian.py`
2. Implement DebianAdapter with overrides for:
   - Base packages (no microcode auto-detect yet)
   - Kernel file parsing (apt-cache format)
   - Package lock parsing (dpkg format)
   - Install command (debootstrap + apt)
3. Fix debian.py bugs (pacman → apt)

### Phase 4: Factory & Integration

1. Update `factory.py` to instantiate adapters
2. Update `__init__.py` exports
3. Verify kod.py imports work without changes
4. Test end-to-end with both distros

### Phase 5: Testing & Cleanup

1. Write adapter-specific tests
2. Run existing test suite
3. Delete old arch.py and debian.py
4. Verify no regressions

---

## Metrics & Success Criteria

### Code Reduction

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total distro module lines | 800 | 590 | **-210** |
| Duplicated lines | ~760 | 0 | **-760** |
| Lines per adapter | N/A | ~90 avg | **-290** |

### Quality

- ✅ No breaking API changes
- ✅ All common logic in one place (single source of truth)
- ✅ Bug fixes apply everywhere
- ✅ Clear interface for adding new distros
- ✅ All existing tests pass

### Maintainability

- ✅ New distro = create one adapter class (~100 lines)
- ✅ Bug in common logic = fix once
- ✅ Test base once, override tests only for parsing

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Extraction bugs during consolidation | Medium | High—install failures | Code review diff carefully; test both distros |
| Parsing logic differs from original | Medium | Medium—subtle bugs | Compare output parsing line-by-line |
| Missed edge cases in base class | Low | Medium—edge case failures | Add comprehensive test suite for parsing |
| Import breakage in kod.py | Low | High—build fails | Test imports immediately after factory changes |

---

## Future Extensibility

### Adding a New Distro (e.g., Fedora)

1. Create `adapters/fedora.py`
2. Subclass DistroAdapter
3. Override 5-10 methods (package lists, parsing, commands)
4. Add to factory.py supported list
5. Write adapter-specific tests
6. No changes to base logic needed

**Effort**: ~100 lines, 2-3 hours

---

## Rollback Plan

If critical issues discovered:

1. Revert the refactor commit
2. Old code is preserved in git history
3. No data loss (all logic is the same)
4. Can identify issue and re-apply fix

---

## Questions Resolved

**Q: Why strategy pattern instead of inheritance chain?**  
A: Strategy is simpler—single level of overrides, not cascading. Easier to understand and test.

**Q: What about distro detection?**  
A: Caller (kod.py) provides distro name; factory just instantiates. Detection is separate concern (config → distro name).

**Q: Will this slow things down?**  
A: No. One extra method call per distro adapter initialization. Negligible (<1ms).

**Q: What about Lua?**  
A: These are execution operations (package manager calls, I/O), not config extraction. They belong in Python per Phase 5 architecture.

---

## References

- **Current code**: src/kod/system/distro/{arch,debian}.py
- **Factory**: src/kod/system/distro/factory.py
- **Callers**: src/kod/kod.py, src/kod/system/boot.py
- **Tests**: tests/system/test_distro_*.py
- **Architecture doc**: docs/superpowers/ARCHITECTURE.md

---

**Status**: Ready for implementation review. Approved for Phase 5d implementation.

