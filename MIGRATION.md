# Kodos Refactoring Migration Guide

This guide explains how to migrate code from the old monolithic `core.py` structure to the new refactored architecture.

## Overview

**Old structure:** One large `core.py` (2038 lines) with all functionality
**New structure:** Split into focused modules by phase

## Phase 2: Migrating from core.py

### Installation Workflow

**Old code location:** `core.py:install()` and related functions

**New code location:** `kod/core/install.py:InstallWorkflow`

**Migration steps:**

1. Extract install logic from `core.py`
2. Create `InstallWorkflow` class in `kod/core/install.py`
3. Move orchestration logic (partition → filesystem → packages → users → services → boot)
4. Replace direct function calls with calls to `kod/system/*` modules
5. Replace global `problems` list with exceptions
6. Add logging for each step

**Example:**

```python
# OLD (core.py)
def install(config, root_path):
    # ... 500 lines ...
    partition(device)
    setup_filesystem(root_path)
    get_packages_to_install(config)
    manage_packages(...)
    # ... etc ...

# NEW (kod/core/install.py)
class InstallWorkflow:
    def __init__(self, plan, config):
        self.plan = plan
        self.config = config
        
    def execute(self):
        """Run full installation."""
        self._partition()
        self._setup_filesystem()
        self._install_packages()
        self._create_users()
        self._setup_services()
        self._setup_boot()
    
    def _install_packages(self):
        """Install packages using new PackageManager."""
        manager = PackageManager(self.distribution, self.repos)
        manager.install_packages(self.plan.packages)
```

### Package Management

**Old code location:** `core.py:manage_packages()`, `core.py:manage_packages_shell()`

**New code location:** `kod/system/packages.py:PackageManager`

**Migration:**

1. Create `PackageManager` class
2. Move repo grouping logic
3. Move command execution logic
4. Use exceptions instead of returning error lists
5. Add detailed logging

### Service Management

**Old code location:** Various functions in `core.py` for systemctl, etc.

**New code location:** `kod/system/services.py:ServiceManager`

### User Configuration

**Old code location:** `core.py:proc_user_programs()`, user setup logic

**New code location:** `kod/core/user_config.py:UserManager`

### Boot Configuration

**Old code location:** Boot-related functions in `core.py`

**New code location:** `kod/system/boot.py:BootManager`

## Error Handling Migration

### Replace Global Problems List

**Old pattern:**
```python
problems = []  # global list

def some_function():
    if error_occurs:
        problems.append("Error message")
    return problems  # return from every function
```

**New pattern:**
```python
class KodosError(Exception):
    """Base exception for Kodos."""
    pass

class PackageInstallError(KodosError):
    """Package installation failed."""
    pass

def some_function():
    if error_occurs:
        raise PackageInstallError("Error message")
    # Implicit success
```

### Structured Exceptions

Create exception hierarchy in `kod/common.py` or `kod/exceptions.py`:

```python
# kod/exceptions.py
class KodosError(Exception):
    """Base exception."""
    pass

class ConfigError(KodosError):
    """Configuration error."""
    pass

class ValidationError(ConfigError):
    """Validation failed."""
    pass

class PackageError(KodosError):
    """Package operation failed."""
    pass

class SystemError(KodosError):
    """System operation failed."""
    pass
```

## Distribution Abstraction

### Create Distribution Base Class

**Old:** Distro-specific functions mixed throughout

**New:** Each distro implements common interface

```python
# kod/distributions/base.py
class Distribution:
    """Base class for distributions."""
    
    def install_packages(self, packages: List[str]) -> None:
        raise NotImplementedError
    
    def install_to_root(self, packages: List[str], root: str) -> None:
        raise NotImplementedError

# kod/distributions/arch.py
class ArchDistribution(Distribution):
    def install_packages(self, packages: List[str]) -> None:
        exec(f"pacman -S --noconfirm {' '.join(packages)}")
    
    def install_to_root(self, packages: List[str], root: str) -> None:
        exec_chroot(f"pacman -S --noconfirm {' '.join(packages)}", root)

# kod/distributions/debian.py
class DebianDistribution(Distribution):
    def install_packages(self, packages: List[str]) -> None:
        exec(f"apt-get install -y {' '.join(packages)}")
    
    def install_to_root(self, packages: List[str], root: str) -> None:
        exec_chroot(f"apt-get install -y {' '.join(packages)}", root)
```

## Backward Compatibility

During migration:

1. **Keep old code working** — Don't delete `core.py` immediately
2. **Add new modules alongside** — New code in `kod/config/`, `kod/core/`, etc.
3. **Gradually replace calls** — Migrate call sites one by one
4. **Test extensively** — Both old and new paths must work
5. **Mark deprecations** — Use `@deprecated` decorator on old functions

```python
def deprecated(message: str):
    """Mark a function as deprecated."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import warnings
            warnings.warn(
                f"{func.__name__} is deprecated. {message}",
                DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator

@deprecated("Use kod.system.packages.PackageManager instead")
def manage_packages(repos, action, packages):
    # Old implementation
    pass
```

## Testing Strategy

Create tests for each new module before implementation:

```bash
tests/
├── config/
│   ├── test_schema.py
│   ├── test_validator.py
│   ├── test_loader.py
│   └── test_compiler.py
├── core/
│   ├── test_install.py
│   ├── test_rebuild.py
│   └── test_user_config.py
├── system/
│   ├── test_packages.py
│   ├── test_services.py
│   └── test_boot.py
└── registry/
    ├── test_programs.py
    └── test_loader.py
```

## Phase Order

1. **Phase 1: Config System**
   - No changes to existing `core.py`
   - New code is purely additive

2. **Phase 2: Python Refactoring**
   - Start migrating `core.py` functions
   - Keep old functions as deprecated wrappers
   - Update call sites gradually

3. **Phase 3: Program Registry**
   - New registry module (no impact on existing)

4. **Phase 4: Polish**
   - Remove deprecated code
   - Simplify error messages
   - Clean up dead code

5. **Phase 5: Custom Packages**
   - Add to new modules (no breaking changes)

## Checklist for Each Phase

- [ ] Specification written and approved
- [ ] New module files created with docstrings
- [ ] Tests written (can skip)
- [ ] Implementation fills in module functions
- [ ] Integration tests pass
- [ ] Old code deprecated (marked with @deprecated)
- [ ] Migration guide updated
- [ ] Git commit with clear message
- [ ] PR created, reviewed, approved

---

**Questions?** Refer to the architecture spec: `docs/superpowers/specs/2026-09-09-architecture-redesign.md`
