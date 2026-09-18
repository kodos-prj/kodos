# KodOS Developer Guide

This guide provides an overview of the KodOS codebase, development practices, and how to contribute to the project.

---

## Table of Contents

1. [Codebase Structure](#codebase-structure)
2. [Architecture Overview](#architecture-overview)
3. [Development Environment](#development-environment)
4. [Key Concepts](#key-concepts)
5. [Adding Features](#adding-features)
6. [Testing](#testing)
7. [Code Quality](#code-quality)
8. [Recent Changes](#recent-changes)

---

## Codebase Structure

```
kodos/
├── src/
│   ├── kod/                  # Python only
│   │   ├── __init__.py
│   │   ├── kod.py            # CLI entry point
│   │   ├── bootstrap.py      # Bootstrap bridge (calls Lua)
│   │   ├── executor.py       # Step executor (calls Lua)
│   │   ├── hooks.py          # Lifecycle hooks
│   │   ├── lua_runtime.py    # Lua VM management
│   │   ├── planner.py        # Step planner (calls Lua)
│   │   ├── cli/              # CLI subcommands
│   │   ├── config/           # Config loading & validation
│   │   ├── core/             # Core utilities
│   │   ├── registry/         # Plugin registry
│   │   └── system/           # System operations
│   │
│   └── lua/                  # Lua only (CLEAR SEPARATION)
│       └── kod/              # Root namespace
│           ├── bootstrap/    # System bootstrap
│           ├── core/         # Core schemas
│           ├── planning/     # Step composition
│           ├── registry/     # Program discovery
│           └── system/       # System definitions
│
├── tests/                    # Test suite
├── docs/                     # Documentation
└── pyproject.toml            # Project metadata
```

---

## Architecture Overview

**For a detailed overview, see [ARCHITECTURE.md](./ARCHITECTURE.md)**

KodOS follows a **planner-executor architecture**:

```
┌─────────────────────────────────────────────────────┐
│                   User Config (Lua)                 │
│                 ~/.kod/config.lua                   │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │   Planner (Python)      │
          │ Converts config → steps │
          └──────────┬──────────────┘
                     │
                     ▼
          ┌─────────────────────────┐
          │  Executor (Lua + Py)    │
          │  Runs steps in order    │
          └─────────────────────────┘
```

**Key modules:**
- **Planner** (`planner.py`) - Converts Lua config into deterministic step list
- **Executor** (`executor.py` + `src/lua/kod/planning/executor.lua`) - Runs steps, handles hooks
- **Config Loader** (`config/loader.py`) - Loads and parses Lua config files
- **Registry** (`registry/` + `src/lua/kod/registry/`) - Program discovery and inheritance
- **System** (`system/`) - Distro-specific operations (package, service, user mgmt)

---

## Python/Lua Separation

**Clear directory separation (as of Sep 18, 2026):**

- **Python code:** `src/kod/` (all Python files)
- **Lua code:** `src/lua/kod/` (all Lua files)

This provides 100% clarity:
- No confusion about file types
- IDE autocomplete works better
- Build tools can handle separately
- Single responsibility per directory

**Example imports:**

```python
# Python importing Python
from kod.config.loader import load_config
from kod.planner import build_plan

# Python importing Lua
lua = get_lua_runtime()
planner = lua.require('kod.planning.planner')

# Lua importing Lua
local schema = require('kod.core.schema')
local repos = require('kod.system.repos')
```

---

## Development Environment

### Prerequisites
- Python 3.10+
- Lua 5.1+
- `luac` (Lua compiler, for syntax validation)
- `uv` or `pip` (Python package management)

### Setup

```bash
# Clone repository
git clone https://github.com/kodos-prj/kodos.git
cd kodos

# Install development dependencies (if using uv)
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Or with pip
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Verification

```bash
# Check Python syntax
python3 -m py_compile src/kod/**/*.py

# Check Lua syntax
luac -o /dev/null src/kod/lib/**/*.lua

# Run tests
pytest tests/ -v
```

---

## Key Concepts

### 1. Configuration as Data (Lua)

Users define system state declaratively:

```lua
return {
    base_distribution = "arch",
    devices = { ... },
    packages = { "vim", "git", ... },
    services = { "sshd", "nginx", ... },
    users = { ... }
}
```

Config is **not executed code** — it's data that the planner reads and converts to steps.

### 2. Deterministic Planning

The same config always produces the same plan:
- No randomness in step generation
- No state-dependent logic (deterministic sorting, ordering)
- `kod plan` output matches `kod install` execution exactly

### 3. Planner → Executor Separation

**Planner** generates steps (side-effect free):
```python
steps = [
    {"kind": "disk", "program": "mkpart", ...},
    {"kind": "system", "program": "chroot", ...},
    {"kind": "package", "name": "vim", ...},
    {"kind": "service", "name": "sshd", ...},
]
```

**Executor** runs them in order (side-effectful):
```python
for step in steps:
    result = executor.run(step)
    if result.failed: handle_error(step, result)
```

### 4. Lua for Orchestration

While Python handles CLI and system operations, Lua handles:
- Bootstrap step composition (distro-specific disk/system ops)
- Program/section inheritance (override, extend)
- Step ordering and dependency resolution
- Hooks and customization

This allows users to customize system behavior via Lua without touching Python.

### 5. Single Source of Truth

When data exists in multiple places, Python is authoritative:
- Python validator is the source of truth (Lua validation was removed in recent refactoring)
- Merged program state is authoritative (intermediate caches removed)
- Python dispatches all system operations (packages, services, users)

---

## Adding Features

### Adding a New Section (e.g., "firewall")

1. **Define schema** in `src/kod/lib/core/schema.lua`:
   ```lua
   Schema.firewall = {
       description = "Firewall rules",
       fields = {
           rules = { type = "list", items = { type = "string" } }
       }
   }
   ```

2. **Create section module** in `src/kod/sections/firewall.lua`:
   ```lua
   return {
       emit_steps = function(config)
           if not config.firewall then return {} end
           local steps = {}
           for _, rule in ipairs(config.firewall.rules) do
               table.insert(steps, {
                   kind = "system",
                   name = "firewall:" .. rule,
                   program = "firewall-cmd",
                   args = { "--permanent", "--add-rule", rule },
                   order = 300
               })
           end
           return steps
       end
   }
   ```

3. **Register in planner** (`src/kod/lib/planning/planner.lua`):
   ```lua
   Planner.sections = {
       'base_distribution', ..., 'firewall'
   }
   ```

4. **Implement backend** in Python (e.g., `src/kod/system/firewall.py`):
   ```python
   def apply_firewall_rule(rule):
       # Distro-specific implementation
       pass
   ```

5. **Test** with:
   ```bash
   pytest tests/ -k firewall -v
   ```

### Adding a New Package Manager

1. **Define in `src/kod/lib/system/repos.lua`**
2. **Implement dispatch in `src/kod/system/packages.py`**
3. **Add tests in `tests/config/test_packages.py`**

---

## Testing

### Test Structure

```
tests/
├── config/          # Config loading, validation
├── core/            # Core functionality
├── integration/     # End-to-end workflows
└── fixtures/        # Test data, mock configs
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/config/test_loader.py -v

# Specific test
pytest tests/config/test_loader.py::test_load_arch_config -v

# With coverage
pytest tests/ --cov=src/kod --cov-report=html
```

### Writing Tests

Example test structure:

```python
import pytest
from kod.config.loader import load_config

def test_load_arch_config():
    config = load_config("example/testvm/configuration.lua")
    assert config.base_distribution == "arch"
    assert "vim" in config.packages
```

---

## Code Quality

### Style Guide

- **Python:** PEP 8 (use `black` or `ruff` for formatting)
- **Lua:** 4-space indentation, prefer local over global, clear function names
- **Git:** Atomic commits with clear messages

### Quality Checks

```bash
# Python style
ruff check src/
black --check src/

# Lua syntax
luac -o /dev/null src/kod/lib/**/*.lua

# Python syntax
python3 -m py_compile src/kod/**/*.py
```

### Git Workflow

```bash
# Create feature branch
git checkout -b feat/my-feature

# Make changes, run tests
pytest tests/ -v

# Verify quality
luac -o /dev/null src/kod/lib/**/*.lua
python3 -m py_compile src/kod/**/*.py

# Commit atomically
git add src/kod/my_module.py
git commit -m "feat: add firewall support

- Implement firewall section
- Add schema definitions
- Add backend dispatch
- Add tests"

# Push and create PR
git push origin feat/my-feature
```

---

## Recent Changes

### Lua Layer Refactoring (Sep 18, 2026)

The Lua layer was simplified to remove 1,603 lines (49% reduction):

- **Phase 1:** Deleted dead code + consolidated bootstrap modules
- **Phase 2-7:** Simplified caching, unified modules, removed defensive code

**See [LUA-LAYER-REFACTORING.md](./LUA-LAYER-REFACTORING.md) for full details.**

**Key improvements:**
- ✅ 6 files deleted, 5 files simplified
- ✅ 100% dead code verified (no false positives)
- ✅ All Lua syntax validated
- ✅ No breaking API changes
- ✅ Risk level: LOW

---

## Common Development Tasks

### Debugging a Plan

```python
from kod.lua_runtime import get_lua_runtime
from kod.planner import build_plan

lua = get_lua_runtime()
schema = lua.require('kod.core.schema')
planner = lua.require('kod.planning.planner')

# Load config and see steps generated
steps, err = planner.compose(config, "arch")
for step in steps:
    print(f"{step.order}: {step.name}")
```

### Adding a Lua Module

1. Create file in `src/lua/kod/<category>/`
2. Ensure valid Lua syntax: `luac -o /dev/null src/lua/kod/<category>/my_module.lua`
3. Return module table: `return { function1, function2, ... }`
4. Import in Python: `lua.require('kod.<category>.my_module')`

### Modifying Bootstrap Logic

Bootstrap logic is in `src/lua/kod/bootstrap/bootstrap.lua` and bridges to Python via `emit_bootstrap_steps()`.

- Edit Lua logic: `src/lua/kod/bootstrap/bootstrap.lua`
- Update Python bridge: `src/kod/bootstrap.py`
- Test: `pytest tests/config/test_compiler.py -v`

---

## Resources

- [ARCHITECTURE.md](./ARCHITECTURE.md) - System design overview
- [TESTING.md](./TESTING.md) - Detailed testing guide
- [extending.md](./extending.md) - User-facing extension guide
- [LUA-LAYER-REFACTORING.md](./LUA-LAYER-REFACTORING.md) - Recent refactoring details

---

## Questions?

If you have questions or need clarification:

1. Check the ARCHITECTURE.md for high-level overview
2. Review related test files for usage examples
3. Check git log for recent changes
4. Open an issue on GitHub

