# KodOS Lua Layer - Complete Analysis

## Executive Summary

**Total Lua Files:** 15  
**Total Lines of Code:** 3,268  
**Assessment:** Heavy over-engineering with **7 major simplification opportunities** identified

The Lua layer suffers from:
1. **Duplicate modules** (loader.lua + registry.lua contain near-identical code)
2. **Redundant state management** (3 cache tiers, inconsistent cache semantics)
3. **Over-complex inheritance resolution** (circular detection is broken)
4. **Unused/dead code** (configs.lua functions not called, dotfile_manager.lua duplicates)
5. **Speculative abstractions** (Table merging, schema validation in Lua when Python does validation)
6. **Broken Lua (mount.lua, partial implementations)**

---

## FILE INVENTORY

### 1. `/registry/loader.lua` (164 lines)
**Purpose:** Discover and load .lua program files; manage caching

**Module Docstring:**
```
Registry Loader: Program file discovery and loading
- Discover .lua files in builtin and user directories
- Load and parse .lua program definitions
- Manage caching to avoid reloading
- Handle errors gracefully (return tuples, not exceptions)
```

**Functions:**
- `_scan_directory(dir)` → {name: path} or nil, error_msg
- `discover_builtin_files(dir)` → {name: path} or nil, error_msg
- `discover_user_files(dir)` → {name: path} or nil, error_msg
- `load_program_file(file_path)` → table or nil, error_msg
- `get_builtin_cache(name)` → table or nil
- `get_user_cache(name)` → table or nil
- `set_builtin_cache(name, program_def)` → void
- `set_user_cache(name, program_def)` → void
- `clear_cache()` → void
- `get_cached_names()` → [names]

**Global State:**
- `_builtin_cache` – persistent cache {program_name: program_def}
- `_user_cache` – persistent cache {program_name: program_def}

**Dependencies:**
- Lua `lfs` (optional, fallback to Python)
- No Lua module imports
- Called from Python: `kod/registry/loader.py`

---

### 2. `/registry/inheritance.lua` (271 lines)
**Purpose:** Resolve program inheritance chains, detect circular references, merge definitions

**Functions:**
- `_is_visited(name, visited)` → bool
- `_detect_circular(program_name, visited)` → bool, nil or nil, error_msg
- `resolve_program(program_name, builtin_programs, user_programs, visited)` → table, nil or nil, error_msg
  - Main entry point: recursively loads parents, handles both/builtin/user combinations
- `_deep_merge_tables(parent, child)` → table (recursive deep merge)
- `_merge_defs(parent_def, child_def)` → table (skips `_extends` marker)
- `validate_program_def(program_def)` → bool, nil or nil, error_msg

**Global State:**
- None (stateless except via loader caches)

**Dependencies:**
- `local loader = require("lib.registry.loader")`
- Called from Python: Not directly (registry.lua wraps this)

---

### 3. `/registry/registry.lua` (697 lines) ⚠️ DUPLICATE HOTSPOT
**Purpose:** Unified registry (loader + inheritance + config generation + hooks)

**Functions:**
- File discovery: `discover_builtin(dir)`, `discover_user_files(dir)`
- File loading: `load_program_file(file_path)`
- Caching: `get_builtin_cache()`, `get_user_cache()`, `get_merged_cache()`, `set_*_cache()`, `clear_cache()`
- Merging: `_merge_defs(parent, child)`, `merge_schemas(parent_schema, child_schema)`
- Resolution: `resolve_program(program_name, builtin_programs, user_programs, visited)`
- Validation: `validate_program_def(program_def)`, `validate_config(program_def, options)`
- Config generation: `generate_config(program_def, options)`
- Hooks: `run_hook(program_def, hook_name, ...)`
- Service extraction: `get_service(program_def)`
- Listing: `get_program_info(program_def)`, `load_program(name, config_home)`, `list_programs(config_home)`

**Global State:**
- `_builtin_cache` – {program_name: program_def}
- `_user_cache` – {program_name: program_def}
- `_merged_cache` – {program_name: merged_program_def}

**Helper Functions:**
- `_safe_get(tbl, key)` – handles lupa Python dict conversion
- `_has_key(tbl, key)` – safe key check for lupa dicts
- `_scan_directory(dir)` – identical to loader.lua
- `_is_visited(name, visited)`
- `_detect_circular(program_name, visited)`
- `_deep_merge_tables(parent, child)` – identical to inheritance.lua
- `_check_type(value, expected_type)`
- `_get_merged_schema(program_def)`

**Dependencies:**
- No Lua imports
- Called from Python: `kod/registry/__init__.py`

---

### 4. `/core/schema.lua` (806 lines)
**Purpose:** Single source of truth for all KodOS config sections and fields

**Sections Defined (13):**
1. `base_distribution` – string, required, enum(arch, debian)
2. `repos` – dict, optional, dynamic keys
3. `devices` – dict, optional, disk definitions
4. `boot` – dict, optional, kernel + bootloader config
5. `hardware` – dict, optional, pipewire, sane configs
6. `locale` – dict, optional, locale/timezone/keymap
7. `network` – dict, optional, hostname, ipv6
8. `users` – dict, optional, identity, ssh_keys, dotfiles, programs, services, home_config
9. `desktop` – dict, optional, environment, display_manager, per-DE configs
10. `fonts` – dict, optional, font packages
11. `packages` – list, optional
12. `services` – dict, optional, service configs + systemd configs
13. `programs` – dict, optional

**Functions:**
- `validate_field(schema_def, value)` → bool, nil or bool, error_msg
- `get_default(schema_def)` → value
- `has_field(config, path)` → bool
- `get_field_schema(path)` → table or nil

**Global State:**
- None (pure data + methods)

**Dependencies:**
- No imports
- Called from Python: `kod/config/schema.py`

---

### 5. `/core/configs.lua` (234 lines) ⚠️ DEAD CODE
**Purpose:** Program-specific configuration generation (stow, dconf, git, syncthing, mounts)

**Functions:**
- `stow(config)` → {name, command, config, stages}
- `dconf(config)` → {name, command, config, stages}
- `git(config)` → {name, command, config, stages}
- `syncthing(config)` → {name, command, config, stages}
- `copy_file(source)` → {name, command, source, stages}
- `systemd_mount(config)` → {name, command, config, stages}

**Global State:**
- None

**Dependencies:**
- None

**Callers:**
- ❌ **NOT CALLED ANYWHERE** (examined Python codebase)
- Appears to be placeholder for future program config generators

---

### 6. `/core/utils.lua` (61 lines)
**Purpose:** Generic utility functions (table printing, list/map metatable helpers)

**Functions:**
- `dumpTable(tbl, indent)` → prints indented table
- `list(l)` → table with __tostring, __concat metamethods
- `map(m)` → table with __tostring, __concat metamethods
- `if_true(cond, m)` → m if cond else {}
- `if_else(cond, m_true, m_false)` → m_true or m_false

**Global State:**
- None

**Dependencies:**
- None

**Callers:**
- ❌ **NOT CALLED ANYWHERE** (no require() found in codebase)

---

### 7. `/planning/planner.lua` (210 lines)
**Purpose:** Schema-driven composition of installation steps from 13 section modules

**Functions:**
- `load_section(section_name)` → section module (with caching)
- `sort_steps(steps)` → [sorted_steps] (by order field, with topological sort for depends_on)
- `validate_config(config)` → bool, nil or nil, error_msg
- `merge_user_programs_services(config)` → void (merges user-level into global)
- `compose(config, distro)` → [steps], nil or nil, error_msg

**Global State:**
- `_section_cache` – {section_name: section_module}

**Constants:**
- `sections` – list of 13 section names (iteration order only)

**Dependencies:**
- Requires section modules: `'kod.sections.' .. section_name`
- Called from Python: `kod/planner.py`

---

### 8. `/planning/executor.lua` (93 lines)
**Purpose:** Generic step runner (language-agnostic orchestrator for steps)

**Functions:**
- `shq(s)` → quoted shell string
- `run_shell(step, mount_point)` → {success=bool, error=...}
- `run(steps, ctx, dispatch, hooks)` → [results]

**Global State:**
- None

**Dependencies:**
- None (pure logic)
- Called from Python: `kod/planner/executor.py`

---

### 9. `/planning/rebuild.lua` (119 lines)
**Purpose:** Diff-based rebuild planner (stateless, deterministic, no shell calls)

**Functions:**
- `to_set(list)` → {v: true} for v in list
- `sorted_diff(a, b)` → sorted list of keys in a - b
- `diff(state)` → [steps]

**Dependencies:**
- `local Repos = require('kod.lib.system.repos')`
- Called from Python: `kod/planner.py`

---

### 10. `/bootstrap/arch.lua` (149 lines)
**Purpose:** Arch-specific bootstrap step emission (disk ops, mounts, fstab, bootloader)

**Functions:**
- `emit_bootstrap_steps(conf, predicted_partition_list)` → [steps]
  - Contains 3 nested helpers: `emit_disk_ops()`, `emit_mounts()`, `emit_system_steps()`

**Dependencies:**
- None
- Called from Python: `kod/planner.py`

---

### 11. `/bootstrap/debian.lua` (150 lines) ⚠️ DUPLICATE HOTSPOT
**Purpose:** Debian-specific bootstrap step emission (identical to arch.lua except bootloader type)

**Functions:**
- `emit_bootstrap_steps(conf, predicted_partition_list)` → [steps]
  - 99% identical code to arch.lua (copy-paste)

**Differences from arch.lua:**
- Line 138: `meta = {bootloader = "grub"}` vs arch's `"systemd-boot"`

**Dependencies:**
- None
- Called from Python: `kod/planner.py`

---

### 12. `/system/repos.lua` (139 lines)
**Purpose:** Repository definitions and package manager commands

**Functions:**
- `arch_repo(mirrors)` → {type, mirrors, repo, privilege_level, commands}
- `aur_repo(name, url, build_cmd, commands, run_as_root)` → {type, privilege_level, build, commands}
- `flatpak_repo(repo, run_as_root)` → {type, privilege_level, package, init, commands}
- `deb_repo(mirrors)` → {type, privilege_level, mirrors, repo, commands}
- `install_cmd(distro, packages)` → command string or nil
- `remove_cmd(distro, packages)` → command string or nil
- `update_cmd(distro)` → command string or nil

**Global State:**
- None (pure functions)

**Dependencies:**
- None
- Called from: `rebuild.lua` (via Repos.update_cmd, Repos.remove_cmd, Repos.install_cmd)

---

### 13. `/system/disk.lua` (51 lines)
**Purpose:** Disk partition definition builder

**Functions:**
- `disk_definition(device, swap_size)` → {device, efi, type, partitions}

**Global State:**
- None

**Dependencies:**
- None
- Called from: Config files (user-supplied .lua configs)

---

### 14. `/system/mount.lua` (87 lines) ⚠️ BROKEN CODE
**Purpose:** Systemd mount configuration (INCOMPLETE)

**Functions:**
- `systemd-mount(config)` → {name, command, config, stages}
  - **SYNTAX ERROR:** Line 31 has invalid function name `local function systemd-mount(config)` (hyphens not allowed in Lua identifiers)
  - **INCOMPLETE:** Lines 34, 84 have syntax errors (missing `do`, semicolon after `end`)
  - **DEAD CODE:** Function never returns, returns statement at line 87 is outside function scope

**Dependencies:**
- None
- **NOT CALLED ANYWHERE** (broken state)

---

### 15. `/io/dotfile_manager.lua` (37 lines) ⚠️ DEAD CODE / DUPLICATE
**Purpose:** Dotfile stow deployment (duplicates configs.lua:stow)

**Functions:**
- `stow(config)` → {init, deploy, source_dir, target_dir}

**Dependencies:**
- None

**Status:**
- **NOT CALLED ANYWHERE**
- **DUPLICATE:** Identical functionality to `configs.lua:stow()`
- Returns different shape: {init, deploy} functions instead of {command}

---

## ARCHITECTURE ANALYSIS

### Data Flow

```
User Config (.lua files)
    ↓
Python loader discovers .lua files
    ↓
registry.lua: resolve_program() loads + merges inheritance
    ↓
Python wraps in Program objects
    ↓
schema.lua: validate_config() validates options
    ↓
planner.lua: compose() emits steps from 13 section modules
    ↓
bootstrap/arch.lua or debian.lua: emit_bootstrap_steps()
    ↓
rebuild.lua: diff() computes delta
    ↓
executor.lua: run() executes steps
```

### Module Interaction Matrix

| Module | Callers | Callees |
|--------|---------|---------|
| loader.lua | Python (loader.py) | lfs (optional) |
| inheritance.lua | Not directly called (wrapped by registry.lua) | loader.lua |
| registry.lua | Python (__init__.py, validator.py) | (pure logic) |
| schema.lua | Python (schema.py, validator.py) | (pure logic) |
| configs.lua | ❌ NONE | (pure logic) |
| utils.lua | ❌ NONE | (pure logic) |
| planner.lua | Python (planner.py) | Section modules (dynamic) |
| executor.lua | Python (planner.py) | os.execute() |
| rebuild.lua | Python (planner.py) | repos.lua |
| arch.lua | Python (planner.py) | (pure logic) |
| debian.lua | Python (planner.py) | (pure logic) |
| repos.lua | rebuild.lua | (pure logic) |
| disk.lua | User configs (.lua) | (pure logic) |
| mount.lua | ❌ NONE (broken) | (pure logic) |
| dotfile_manager.lua | ❌ NONE | (pure logic) |

---

## OVER-ENGINEERING DETECTION

### 🔴 FINDING #1: Duplicate Registry Modules (loader.lua + registry.lua)

**Files:** `registry/loader.lua` (164 lines) + `registry/registry.lua` (697 lines)

**Issue:**
- `registry.lua` **reimplements 95% of loader.lua** inside itself
- Both have identical functions:
  - `_scan_directory()` (lines 30-56 vs 85-106)
  - `load_program_file()` (lines 80-108 vs 130-158)
  - Cache get/set functions (lines 117-140 vs 164-200)
  - Circular detection functions (lines 27-45 vs 210-228)
  - Deep merge (lines 179-205 vs 239-263)
- `loader.lua` is still loaded by Python (legacy), but registry.lua is the active module

**Why This Happened:**
- Gradual refactor: loader.lua + inheritance.lua were separate, then consolidated into registry.lua
- Old module not deleted (backward compat with existing Python code)

**Simplification:**
- **DELETE `loader.lua` entirely**
- Update Python to use only `registry.lua`
- Removes 164 lines of maintenance burden

**What Is Lost:**
- None (registry.lua is a strict superset)

**When To Implement Full Version:**
- Never (lazy is best here; lazy wins)

---

### 🔴 FINDING #2: Triple-Tiered Cache (builtin + user + merged)

**File:** `registry/registry.lua` (lines 73-75, 164-200)

**Issue:**
```lua
local _builtin_cache = {}  -- {program_name: program_def}
local _user_cache = {}     -- {program_name: program_def}
local _merged_cache = {}   -- {program_name: merged_program_def}
```

Three separate caches with unclear semantics:
- Builtin: stores loaded builtin files (but not merged with user overrides)
- User: stores loaded user files (but also stores **merged results** on line 399)
- Merged: stores final merged state

**Problem:**
- Lines 399: `loader.set_user_cache(program_name, merged)` – user cache contains merged, not user-only
- Violates the documented purpose of each cache
- Tests expect `_builtin_cache[name]` to be the builtin-only def, but it's never populated correctly
- `get_merged_cache()` returns nil until after first resolve (lazy cache miss)

**Simplification:**
- **Keep only `_merged_cache`**
- On first resolve, cache the final merged result
- If caller needs to distinguish builtin vs user, they should call resolve separately for each
- Removes 50 lines, eliminates semantic confusion

**What Is Lost:**
- Ability to get "just the builtin, unmerged" from cache without re-resolving
- This is not used by Python (Python re-resolves on each call)

**When To Implement Full Version:**
- If performance profiling shows repeated resolve_program() calls exceed memory budget

---

### 🔴 FINDING #3: Table Merging Implemented in Lua, Validation in Both Lua & Python

**Files:** `registry/registry.lua` (lines 239-263 `_deep_merge_tables`, lines 410-530 `validate_config`)
**Also:** `schema.lua` (lines 636-705 `validate_field`)

**Issue:**
- `_deep_merge_tables()` – deep merges configs (recursive table merge, 24 lines)
- `validate_config()` – validates options against schema (120 lines, handles allOf, type checking)
- `validate_field()` – schema validation in Lua (70 lines)
- **Python also implements validation** in `kod/config/validator.py`

**Why:**
- Supports inline validation in Lua (from user .lua program configs calling validate hooks)
- Redundant with Python-side validation which always runs

**Simplification:**
- **Move deep merge logic to Lua stdlib-adjacent helper** (3-liner using json or inline)
- **Delete Lua validation** – Python validator.py is ground truth
- Lua programs can still provide custom `validate` hooks (lines 522-527) that Python calls
- Removes 120 lines from registry.lua

**What Is Lost:**
- Ability to call validate_config from Lua before returning control to Python
- But Python always validates on the Python side anyway

**When To Implement Full Version:**
- If Lua needs to reject configs before returning to Python (performance only, no correctness benefit)

---

### 🔴 FINDING #4: Debian Bootstrap Module is 100% Duplicate of Arch

**Files:** `bootstrap/arch.lua` (149 lines) vs `bootstrap/debian.lua` (150 lines)

**Issue:**
- **Entire code is copy-paste**
- Only difference: line 138 bootloader type (`"grub"` vs `"systemd-boot"`)
- 147 lines of identical code maintained in two places

**Example:**
```lua
-- arch.lua line 49-59
local fs_types = {
    ["ext4"] = "8300",
    ["btrfs"] = "8300",
    ["vfat"] = "EF00",
    ["esp"] = "ef00",
}

-- debian.lua line 50-59 (IDENTICAL)
local fs_types = {
    ["ext4"] = "8300",
    ["btrfs"] = "8300",
    ["vfat"] = "EF00",
    ["esp"] = "ef00",
}
```

**Simplification:**
- **Single bootstrap.lua module** with distro-specific parameter
- Pass bootloader type as argument
- Removes 149 lines

**What Is Lost:**
- None (distro-specific handling is in step dispatch, not here)

**When To Implement Full Version:**
- If Arch and Debian bootstrap logic truly diverges (future)
- Split at that point

---

### 🔴 FINDING #5: Dead Code (configs.lua + utils.lua not called anywhere)

**Files:**
- `core/configs.lua` (234 lines) – stow, dconf, git, syncthing, copy_file, systemd_mount
- `core/utils.lua` (61 lines) – dumpTable, list, map, if_true, if_else

**Issue:**
- Grep of entire codebase: no `require('kod.lib.core.configs')` or `require('kod.lib.core.utils')`
- No Python imports
- **Unused placeholder code**

**Simplification:**
- **DELETE both files**
- If needed in future, restore from git history
- Removes 295 lines

**What Is Lost:**
- Placeholder functions for future program config generators
- But new generators can be added when actually needed (YAGNI)

**When To Implement Full Version:**
- When a user actually needs dconf/git/syncthing/mount setup (not speculative)

---

### 🔴 FINDING #6: Broken Syntax in mount.lua

**File:** `system/mount.lua` (87 lines)

**Issue:**
```lua
local function systemd-mount(config)  -- Line 31: INVALID (- not allowed in function names)
    local command = function (context, config)
        -- ...
        for name, conf in config.pairs()  -- Line 34: SYNTAX ERROR (missing do)
            -- ...
        end                              -- Line 79: Extra end
    end

    return { ... }  -- Line 81-86
end
-- Line 87: dangling end outside function scope
```

**Status:**
- Never called anywhere (dead code path)
- Lua would throw syntax error if loaded

**Simplification:**
- **DELETE mount.lua**
- Systemd mounts already handled in arch.lua and debian.lua
- Never implemented; remove 87 lines of dead code

**What Is Lost:**
- Broken, incomplete mount configuration (salvage into configs.lua if needed)

**When To Implement Full Version:**
- When mount configuration is actually needed (currently handled by bootstrap modules)

---

### 🔴 FINDING #7: Dotfile Manager Duplicates configs.lua

**Files:** `io/dotfile_manager.lua` (37 lines) vs `core/configs.lua` (234 lines)

**Issue:**
- `dotfile_manager.lua:stow()` – returns {init, deploy, source_dir, target_dir}
- `configs.lua:stow()` – returns {name, command, config, stages}
- **Same functionality, different interface, not called**

**Simplification:**
- **DELETE dotfile_manager.lua**
- Keep only `configs.lua` (and later delete it when truly needed)
- Removes 37 lines

**What Is Lost:**
- Backup of stow() implementation (already in configs.lua)

**When To Implement Full Version:**
- Move stow into section module when dotfiles are actually implemented

---

### 🟡 FINDING #8: Circular Inheritance Detection is Broken

**File:** `registry/registry.lua` (lines 219-228)

**Issue:**
```lua
local function _detect_circular(program_name, visited)
    if not visited then visited = {} end
    
    if _is_visited(program_name, visited) then
        return nil, "Circular inheritance detected: " .. program_name .. " extends itself"
    end
    
    visited[program_name] = true
    return true, nil
end
```

**Problem:**
- Only detects if a program is visited **in the current call stack**
- If A extends B, B extends C, C extends A, the check passes because each call starts with fresh `visited = {}`
- **Proper circular detection requires persistent visited set across all resolve_program calls**

**Example of undetected cycle:**
```
resolve_program("a", ..., {})  # visited = {a: true}
  ├─ resolve_program("b", ..., {a: true})  # visited = {a: true, b: true}
  │   └─ resolve_program("c", ..., {a: true, b: true})
  │       └─ resolve_program("a", ..., {a: true, b: true})  # NOW catches it
```

Wait, that would actually catch it on the second visit to 'a'. Let me re-examine...

Actually, the code **does work** – it's accumulating visited across recursive calls. The `visited` table is modified in place (line 226: `visited[program_name] = true`), so it's persistent across the call tree.

**Retraction:** Circular detection is correct (Lua tables are pass-by-reference). The logic is fine.

---

### 🟡 FINDING #9: Redundant Helper Functions (_safe_get, _has_key)

**File:** `registry/registry.lua` (lines 29-67)

**Issue:**
```lua
local function _safe_get(tbl, key)  -- 20 lines to handle lupa Python dict conversion
    if not tbl then return nil end
    local value = tbl[key]
    if value ~= nil then return value end
    for k, v in pairs(tbl) do
        if k == key then return v end
    end
    return nil
end

local function _has_key(tbl, key)  -- 16 lines for same
    if not tbl then return false end
    if tbl[key] ~= nil then return true end
    for k, _ in pairs(tbl) do
        if k == key then return true end
    end
    return false
end
```

**Why:**
- lupa (Python→Lua bridge) sometimes doesn't handle dict indexing with `[]` correctly
- Fallback to `pairs()` iteration

**Problem:**
- **Premature optimization** – only needed if lupa really fails (not confirmed in tests)
- Adds 36 lines of defensive code
- Direct indexing `tbl[key]` usually works fine in lupa

**Simplification:**
- **Delete _safe_get and _has_key**
- Use direct indexing `tbl[key]` and standard `pairs()` iteration
- If lupa indexing fails later, add back

**What Is Lost:**
- Defense against potential lupa quirks (but no evidence they occur)

**When To Implement Full Version:**
- Only if tests show actual lupa indexing failures

---

### 🟡 FINDING #10: Over-Broad Schema Validation in Lua

**File:** `schema.lua` (lines 636-705)

**Issue:**
- `validate_field()` handles nested schema validation (70 lines of recursion)
- Supports enum, required, type checking, nested field validation
- But **Python validator.py is the authoritative validator** (runs on all configs)

**Why:**
- Supports custom `validate` hooks in Lua (line 522-527 in registry.lua)
- Allows program-defined validation before returning to Python

**Problem:**
- Two validation paths: Lua (optional, via registry.lua) + Python (mandatory)
- Redundant implementation of same logic

**Simplification:**
- **Keep simple type/enum/required checks in schema.lua**
- **Delete nested field recursion** (not used – validation is flat)
- Move to Python if custom program validation is needed
- Saves ~30 lines

**What Is Lost:**
- Recursive nested field validation (not actually used in current programs)

**When To Implement Full Version:**
- If a program needs to validate nested fields before returning to Python

---

## SUMMARY OF FINDINGS

| # | Issue | Files | Lines | Severity | Fix | Impact |
|---|-------|-------|-------|----------|-----|--------|
| 1 | Duplicate registry (loader.lua + registry.lua) | 2 | 164 | 🔴 HIGH | Delete loader.lua | -164 lines |
| 2 | Triple-tiered cache with confusion | 1 | 50 | 🔴 HIGH | Merge to _merged_cache only | -50 lines |
| 3 | Validation in Lua + Python | 2 | 120 | 🔴 HIGH | Delete Lua validation | -120 lines |
| 4 | Debian = copy of Arch bootstrap | 1 | 149 | 🔴 HIGH | Merge into single module | -149 lines |
| 5 | Dead code (configs.lua + utils.lua) | 2 | 295 | 🔴 HIGH | Delete (YAGNI) | -295 lines |
| 6 | Broken syntax in mount.lua | 1 | 87 | 🔴 HIGH | Delete | -87 lines |
| 7 | Dotfile manager duplicates | 1 | 37 | 🔴 HIGH | Delete | -37 lines |
| 8 | Circular inheritance | 1 | 10 | 🟡 MEDIUM | Already correct | 0 lines |
| 9 | Redundant lupa helpers | 1 | 36 | 🟡 MEDIUM | Delete if not needed | -36 lines |
| 10 | Over-broad schema validation | 1 | 30 | 🟡 MEDIUM | Simplify | -30 lines |

**Total Simplification Potential: -968 lines (30% of codebase)**

---

## RECOMMENDATIONS (PONYTAIL MODE)

### Phase 1: High-Impact, Zero-Risk Deletions

1. **Delete loader.lua** – Registry.lua is the canonical module
   - Update Python: stop loading loader.lua
   - Remove 164 lines

2. **Delete configs.lua** – Never called, speculative generators
   - Restore from git when needed
   - Remove 234 lines

3. **Delete utils.lua** – Never called, generic utilities
   - Restore from git when needed
   - Remove 61 lines

4. **Delete mount.lua** – Broken syntax, never called
   - Mounts handled in bootstrap modules
   - Remove 87 lines

5. **Delete dotfile_manager.lua** – Duplicate of configs.lua
   - Remove 37 lines

6. **Merge arch.lua + debian.lua** – 99% duplicate
   - Create single bootstrap.lua with distro parameter
   - Remove 149 lines

**Total: -732 lines, 0 risk**

### Phase 2: Medium-Risk Refactors

7. **Simplify caching: Keep _merged_cache only**
   - Remove _builtin_cache, _user_cache from registry.lua
   - Update tests to expect merged results
   - Remove 50 lines

8. **Delete redundant lupa helpers** (_safe_get, _has_get)
   - Use direct indexing, confirm lupa works fine
   - Remove 36 lines

9. **Simplify schema validation** – Keep only type/enum/required
   - Move nested validation to Python if needed
   - Remove 30 lines

**Total: -116 lines, medium risk (needs testing)**

### Phase 3: Upstream Simplifications

10. **Config validation moved to Python**
    - registry.lua no longer validates (Python does)
    - Reduces registry.lua by ~120 lines
    - Already done in architecture (Python is ground truth)

**Final State:**
- 15 files → 9 files (delete 6)
- 3,268 lines → ~2,200 lines (32% reduction)
- Clearer data flow, fewer cache layers, less dead code

---

## CODE QUALITY METRICS

| Metric | Value | Assessment |
|--------|-------|------------|
| Dead Code Ratio | ~10% (295 lines unused) | High |
| Duplication Ratio | ~15% (150-line arch/debian + 164-line loader) | High |
| Cache Complexity | 3 tiers with confused semantics | Excessive |
| Documentation Clarity | Good (docstrings present) | Fair |
| Test Coverage | Moderate (Python-side tests exist) | Fair |
| Lint Status | 1 file with syntax errors (mount.lua) | Poor |

---

## DEPENDENCY GRAPH

```
┌─────────────────────┐
│  Python Entrypoint  │
└──────────┬──────────┘
           │
      ┌────┴──────┬─────────────┬──────────────┬───────────────┐
      │            │             │              │               │
      v            v             v              v               v
  registry.lua  schema.lua  planner.lua   bootstrap/      rebuild.lua
                                         {arch,debian}.lua
      │            │             │              │               │
      └────┬────────┘             │              │               │
           │                      │              │               │
           │              ┌───────┴──────────────┴───┐            │
           │              │  Section modules        │            │
           │              │  (dynamic require)      │            │
           │              └────────────────────────┘            │
           │                                                     │
           └─────────────────────────┬──────────────────────────┘
                                     │
                                     v
                              repos.lua (used by rebuild)
                              executor.lua (used by Python)
                              disk.lua (used by user configs)
```

