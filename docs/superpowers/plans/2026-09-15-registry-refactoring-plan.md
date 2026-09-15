# Implementation Plan: Registry Refactoring + Lua Organization

**Status:** Ready for Implementation
**Duration:** 3-4 days
**Risk Level:** Medium (architectural change, but well-isolated)
**Phases:** 2 (sequential, Phase 2 starts after Phase 1 passes all tests)

---

## Phase 1: Move Registry to Lua (2-3 days)

### Step 1.1: Create Lua registry modules foundation
**Duration:** 4-6 hours
**Goal:** Establish registry.lua infrastructure before refactoring Python

**Files to Create:**
- `src/kod/lib/registry/loader.lua` (400 lines)
- `src/kod/lib/registry/inheritance.lua` (350 lines)

**Acceptance Criteria:**
- Both files can be loaded by lupa without errors
- Unit tests can import and test individual functions
- No external dependencies except lupa
- Code is well-commented

**Implementation Details:**

**loader.lua** (400 lines)
```lua
-- File I/O, program definition parsing, caching
-- Functions:
--   discover_builtin_files(dir) → {name: path}
--   discover_user_files(dir) → {name: path}
--   load_program_file(file_path) → {dict, error_msg}
--   get_cached_program(name) → {dict, nil}
--   set_cached_program(name, dict) → nil
--   clear_cache() → nil
```

Responsibilities:
- Read .lua files from filesystem (uses `io.*` and `dofile`)
- Execute Lua code: `return {...}`
- Handle parse errors, return (nil, error_msg) on failure
- Manage two caches: `_builtin_cache`, `_user_cache` (global tables)
- Never throw exceptions, always return tuples (result, error)

**inheritance.lua** (350 lines)
```lua
-- Inheritance logic, program merging, validation
-- Functions:
--   resolve_inheritance(program_name, visited) → {dict, error_msg}
--   merge_program_defs(builtin, user, parent) → {dict, error_msg}
--   validate_inheritance_chain(program) → {bool, error_msg}
--   detect_circular_inheritance(name, visited) → {bool, error_msg}
--   call_schema_validation(program, config) → {bool, errors_list}
```

Responsibilities:
- Walk inheritance chain (follow `_extends` field)
- Detect circular dependencies
- Merge builtin + user definitions correctly
- Call schema.lua validation
- Return (result, error) tuples, never throw

**Testing this step:**
```bash
cd /home/abuss/Work/devel/analysis/kodos
python3 -c "
import lupa
lua = lupa.LuaRuntime()
registry_loader = lua.execute(open('src/kod/lib/registry/loader.lua').read())
print('loader.lua loaded:', hasattr(registry_loader, 'discover_builtin_files'))
"
```

---

### Step 1.2: Write Lua unit tests
**Duration:** 3-4 hours
**Goal:** Test registry.lua logic in isolation via Python test harness

**Files to Create:**
- `tests/test_registry_loader_lua.py` (150 lines)
- `tests/test_registry_inheritance_lua.py` (200 lines)

**Test Structure:**

**test_registry_loader_lua.py**
```python
import lupa
import tempfile
from pathlib import Path

class TestRegistryLoaderLua:
    def setup_method(self):
        self.lua = lupa.LuaRuntime()
        self.registry = self.lua.execute(open('src/kod/lib/registry/loader.lua').read())
    
    def test_discover_builtin_files_empty(self):
        # Test with empty directory
        
    def test_discover_builtin_files_with_programs(self):
        # Test with sample .lua files
        
    def test_load_program_file_valid(self):
        # Test loading valid program definition
        
    def test_load_program_file_invalid_lua(self):
        # Test handling of Lua syntax errors
        
    def test_load_program_file_non_dict_return(self):
        # Test handling when .lua file returns non-dict
        
    def test_caching_behavior(self):
        # Test get_cached_program() and set_cached_program()
```

**test_registry_inheritance_lua.py**
```python
class TestRegistryInheritanceLua:
    def setup_method(self):
        # Load both loader.lua and inheritance.lua
        # Create mock program defs
        
    def test_simple_program_no_inheritance(self):
        # Load program with no _extends field
        
    def test_program_extends_builtin(self):
        # Load user program that extends builtin
        # Verify merge is correct
        
    def test_circular_inheritance_detection(self):
        # Create circular reference, verify error
        
    def test_merge_program_defs_preserves_user_fields(self):
        # Verify user fields override builtin
        
    def test_schema_validation_integration(self):
        # Call schema.lua validation from inheritance.lua
```

**Acceptance Criteria:**
- All tests pass
- >80% code coverage for registry.lua files
- Edge cases tested (empty dirs, invalid Lua, circular refs, etc.)

---

### Step 1.3: Refactor Python loader.py (thin bridge)
**Duration:** 2-3 hours
**Goal:** Replace complex Python logic with Lua calls

**Files to Refactor:**
- `src/kod/registry/loader.py` (341 → 100 lines)

**Old Structure (341 lines):**
```python
class PluginLoader:
    def discover_builtin(self) → dict
    def discover_user_plugins(self) → dict
    def _load_lua_def(file_path) → dict  [COMPLEX]
    def load_program(name, visited) → Program  [COMPLEX]
    def list_programs(self) → list
    def get_program_info(name) → dict
```

**New Structure (100 lines):**
```python
class PluginLoader:
    def __init__(self):
        # Load registry.lua once
        self.lua = lupa.LuaRuntime()
        self.registry_loader = self.lua.execute(open('registry/loader.lua').read())
        self.registry_inheritance = self.lua.execute(open('registry/inheritance.lua').read())
        self._cache = {}
    
    def discover_builtin_paths(self) → dict:
        # Use pathlib to find builtin .lua files
        
    def discover_user_paths(self) → dict:
        # Use pathlib to find user .lua files
        
    def load_program(self, name: str) → dict:
        # Call self.registry_inheritance.resolve_inheritance(name)
        # Convert Lua error tuple to Python exception
        # Cache and return
        
    def list_programs(self) → list:
        # Return sorted(builtin_paths.keys() | user_paths.keys())
        
    def get_program_info(self, name: str) → dict:
        # Load program, extract metadata
```

**Refactoring Steps:**
1. Remove `discover_builtin()`, `discover_user_plugins()` - replace with simpler pathlib versions
2. Remove `_load_lua_def()` - Lua handles this now
3. Remove complex `load_program()` with visited tracking - call registry.lua instead
4. Keep caching logic (Python dicts for mutable state)
5. Add error conversion: Lua (bool, error_msg) → Python exceptions

**Error Conversion Mapping:**
```python
def _convert_lua_error(self, name: str, result: tuple):
    success, error_msg = result if isinstance(result, tuple) else (result, None)
    if not success:
        if "not found" in error_msg:
            raise ProgramNotFound(error_msg)
        elif "circular" in error_msg:
            raise CircularExtendError(error_msg)
        elif "syntax" in error_msg:
            raise ProgramLoadError(error_msg)
        else:
            raise ProgramError(error_msg)
    return result[0]  # Return the dict
```

**Acceptance Criteria:**
- File shrinks from 341 → ~100 lines
- All existing tests pass (backward compatible)
- Error handling works (ProgramNotFound, CircularExtendError, etc.)
- Caching still works
- No external behavior changes

---

### Step 1.4: Refactor Python programs.py (simplified)
**Duration:** 2 hours
**Goal:** Remove duplicate validation logic, keep wrapper classes

**Files to Refactor:**
- `src/kod/registry/programs.py` (680 → 150 lines)

**Remove (logic now in Lua):**
- Complex schema validation (~200 lines) - now in registry/schema.lua
- Config generation logic (~100 lines) - keep only schema interface
- Duplicate error handling (~50 lines)

**Keep (thin Python wrapper):**
- Error hierarchy (25 lines)
  - ProgramError, ProgramNotFound, ProgramLoadError, CircularExtendError, ConfigValidationError, SchemaError
- Program class (50 lines)
  - Wraps Lua def dict
  - Provides `.get_schema()`, `.get_scope()`, `.name` properties
- Service validation (75 lines)
  - Validates systemd service fields
  - Checks service compatibility with scope

**New programs.py Structure (150 lines):**
```python
# Error hierarchy (unchanged)
class ProgramError(Exception): pass
class ProgramNotFound(ProgramError): pass
# ... (5 total)

# Program wrapper (simplified)
class Program:
    def __init__(self, name: str, lua_def: dict, parent: Optional['Program'] = None):
        self.name = name
        self.lua_def = lua_def
        self.parent = parent
    
    def get_scope(self) → str:
        # Return "system", "user", or "both"
    
    def get_schema(self) → dict:
        # Return program schema dict
    
    def get_default_config(self) → dict:
        # Return default values
    
    # Validate service if present
    def _validate_service(self):
        # Check service fields, ensure compatibility with scope
```

**Acceptance Criteria:**
- File shrinks from 680 → ~150 lines
- All existing tests pass (no behavior changes)
- Program class still works as before
- Error hierarchy unchanged

---

### Step 1.5: Update Python tests
**Duration:** 2-3 hours
**Goal:** Update existing tests to work with refactored code

**Files to Update:**
- `tests/registry/test_loader.py` (existing tests, no logic changes)
- `tests/registry/test_programs.py` (no changes needed)
- `tests/config/test_validator.py` (may need path updates)
- `tests/config/test_compiler.py` (may need path updates)

**Changes Needed:**
1. Update mocks to work with new loader.py
2. Update file paths (if tests reference paths)
3. Verify all 706 tests still pass
4. No test logic should change

**Acceptance Criteria:**
- All existing tests pass (706/706)
- No regressions
- Coverage maintained

---

### Step 1.6: Integration test & cleanup
**Duration:** 1 hour
**Goal:** Verify end-to-end flow, cleanup code

**Tasks:**
1. Run full test suite: `pytest tests/ -v`
2. Verify 706/706 pass
3. Check line counts:
   - loader.py: 341 → ~100 ✅
   - programs.py: 680 → ~150 ✅
   - registry.lua: 0 → ~750 ✅
4. Clean up any debug code, comments

**Acceptance Criteria:**
- 706/706 tests pass
- No warnings or errors
- Code is clean and well-commented
- Ready for Phase 2

---

## Phase 2: Organize Lua Files (1 day)

### Step 2.1: Create directory structure
**Duration:** 30 minutes
**Goal:** Create new module directories

**Commands:**
```bash
mkdir -p src/kod/lib/core
mkdir -p src/kod/lib/registry/builtin
mkdir -p src/kod/lib/planning
mkdir -p src/kod/lib/bootstrap
```

**No files moved yet**, just structure created.

---

### Step 2.2: Move files to new locations
**Duration:** 1 hour
**Goal:** Reorganize Lua files (Phase 1 already created registry/loader.lua and registry/inheritance.lua)

**File Moves:**
```bash
# Move builtin programs (from Phase 1 creation, they're already in registry/)
# src/kod/registry/builtin/*.lua → src/kod/lib/registry/builtin/
mv src/kod/registry/builtin/*.lua src/kod/lib/registry/builtin/
rmdir src/kod/registry/builtin

# Move repos utility to planning
mv src/kod/lib/repos.lua src/kod/lib/planning/repos.lua

# No moves for core/ (files already at right level, just organize conceptually)
# configs.lua, schema.lua, utils.lua stay at src/kod/lib/ for now
# (or can move to src/kod/lib/core/ if desired)
```

**Acceptance Criteria:**
- All files moved correctly
- No files lost or duplicated
- Directory structure matches design

---

### Step 2.3: Update Python imports
**Duration:** 1-2 hours
**Goal:** Fix all Python load paths for Lua files

**Files to Update:**
- `src/kod/registry/loader.py`
  - Change: `lua.execute(open('src/kod/lib/registry/loader.lua'))` (already correct)
  - Change: `lua.execute(open('src/kod/lib/registry/inheritance.lua'))` (already correct)

- Any other Python files that load Lua:
  - Search: `grep -r "lua.execute\|lupa\|dofile" src/kod --include="*.py"`
  - Update paths as needed

**Acceptance Criteria:**
- All Python lupa loads work
- No FileNotFoundError on Lua imports

---

### Step 2.4: Update Lua require() statements
**Duration:** 1-2 hours
**Goal:** Fix all cross-Lua imports

**Files to Update:**
- `src/kod/lib/planning/rebuild.lua`
  - Change: `require("lib/repos")` → `require("lib/planning/repos")`

- `src/kod/lib/planning/planner.lua`
  - Change: `require("lib/schema")` → `require("lib/core/schema")`
  - Change: `require("lib/repos")` → `require("lib/planning/repos")`

- `src/kod/lib/planning/executor.lua`
  - Change: any `require("lib/...")` paths

- `src/kod/lib/registry/inheritance.lua`
  - Change: `require("lib/schema")` → `require("lib/core/schema")`

**Find all require() statements:**
```bash
grep -r "require(" src/kod/lib --include="*.lua" | grep -v "lib/core\|lib/registry\|lib/planning\|lib/bootstrap"
```

**Acceptance Criteria:**
- All require() paths updated
- No unresolved requires

---

### Step 2.5: Run full test suite
**Duration:** 30 minutes
**Goal:** Verify no regressions after reorganization

**Tasks:**
1. Run: `pytest tests/ -v`
2. Verify: 706/706 pass
3. Check for any path-related errors

**Acceptance Criteria:**
- 706/706 tests pass
- No regressions
- No import errors

---

### Step 2.6: Cleanup & documentation
**Duration:** 30 minutes
**Goal:** Final cleanup, update any internal docs

**Tasks:**
1. Delete empty directories
2. Update code comments if needed
3. Verify directory structure
4. Document new organization in a brief comment file (optional)

**Acceptance Criteria:**
- Clean directory structure
- No orphaned files
- Well-organized codebase

---

## Overall Success Criteria

### Phase 1 Complete When:
- ✅ All 706 tests pass
- ✅ loader.py: 341 → ~100 lines
- ✅ programs.py: 680 → ~150 lines
- ✅ registry.lua: ~750 lines (split across loader.lua + inheritance.lua)
- ✅ Lua unit tests exist and pass
- ✅ Python bridge tests pass
- ✅ No regressions
- ✅ Code is clean and well-commented

### Phase 2 Complete When:
- ✅ All 706 tests pass
- ✅ Lua files organized into 5 modules
- ✅ All require() paths updated
- ✅ All Python Lua load paths updated
- ✅ No regressions
- ✅ Directory structure clean

---

## Commit Strategy

**After Phase 1 passes all tests:**
Commit as: `feat: Move registry logic to Lua (loader, inheritance, schema)`
- Files: registry/{loader,inheritance}.lua, refactored loader.py/programs.py, new tests

**After Phase 2 passes all tests:**
Commit as: `refactor: Organize Lua files into modular hierarchy (core, registry, planning, bootstrap)`
- Files: All moved .lua files, updated imports

---

## Known Issues & Contingencies

| Issue | Solution |
|-------|----------|
| Lua bidirectional calls fail | Verify lupa version supports this; fallback to Python coordination |
| Circular requires in Lua | Use delayed requires (require in function, not module level) |
| Path references break | Use relative paths from Lua perspective |
| Tests fail after Phase 1 | Revert changes, debug Lua-Python boundary carefully |
| Performance regression | Profile before/after, may need caching tuning |

---

## Time Estimate

| Phase | Step | Duration | Cumulative |
|-------|------|----------|-----------|
| 1 | 1.1: Create Lua modules | 4-6h | 4-6h |
| 1 | 1.2: Write Lua unit tests | 3-4h | 7-10h |
| 1 | 1.3: Refactor loader.py | 2-3h | 9-13h |
| 1 | 1.4: Refactor programs.py | 2h | 11-15h |
| 1 | 1.5: Update Python tests | 2-3h | 13-18h |
| 1 | 1.6: Integration & cleanup | 1h | 14-19h |
| 1 | **Phase 1 Total** | | **2-2.5 days** |
| 2 | 2.1: Create directories | 0.5h | 14.5-19.5h |
| 2 | 2.2: Move files | 1h | 15.5-20.5h |
| 2 | 2.3: Update Python imports | 1-2h | 16.5-22.5h |
| 2 | 2.4: Update Lua requires | 1-2h | 17.5-24.5h |
| 2 | 2.5: Run tests | 0.5h | 18-25h |
| 2 | 2.6: Cleanup | 0.5h | 18.5-25.5h |
| 2 | **Phase 2 Total** | | **1 day** |
| | **Grand Total** | | **3-3.5 days** |

---

## Ready to Execute

This plan is committed to git. Execution starts with Phase 1, Step 1.1.

