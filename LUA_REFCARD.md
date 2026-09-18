# KodOS Lua Layer - Technical Reference Card

## File Map & Status

| File | LOC | Status | Purpose |
|------|-----|--------|---------|
| `registry/loader.lua` | 164 | ❌ DELETE | Duplicate of registry.lua |
| `registry/inheritance.lua` | 271 | ⚠️ MERGE | Wrap logic into registry.lua |
| `registry/registry.lua` | 697 | ✅ KEEP | Main: load+merge+validate programs |
| `core/schema.lua` | 806 | ✅ KEEP | Schema definitions (13 sections) |
| `core/configs.lua` | 234 | ❌ DELETE | Speculative, never called |
| `core/utils.lua` | 61 | ❌ DELETE | Generic utils, never called |
| `planning/planner.lua` | 210 | ✅ KEEP | Compose steps from sections |
| `planning/executor.lua` | 93 | ✅ KEEP | Step runner orchestrator |
| `planning/rebuild.lua` | 119 | ✅ KEEP | Diff-based rebuild logic |
| `bootstrap/arch.lua` | 149 | ⚠️ MERGE | Merge with debian.lua |
| `bootstrap/debian.lua` | 150 | ⚠️ MERGE | 99% duplicate of arch.lua |
| `system/repos.lua` | 139 | ✅ KEEP | Package manager commands |
| `system/disk.lua` | 51 | ✅ KEEP | Disk partition builder |
| `system/mount.lua` | 87 | ❌ DELETE | Broken syntax, never called |
| `io/dotfile_manager.lua` | 37 | ❌ DELETE | Duplicate of configs.lua |

**TOTAL: 3,268 lines → 2,420 lines (26% reduction)**

---

## Function Call Map

```
Python Entrypoint
    │
    ├─→ registry.lua
    │    ├─ discover_builtin(dir)
    │    ├─ discover_user_files(dir)
    │    ├─ load_program_file(path)
    │    ├─ resolve_program(name, builtins, users)
    │    ├─ validate_config(prog_def, options)
    │    ├─ generate_config(prog_def, options)
    │    ├─ run_hook(prog_def, hook, ...)
    │    ├─ get_service(prog_def)
    │    ├─ load_program(name, config_home)
    │    └─ list_programs(config_home)
    │
    ├─→ schema.lua
    │    ├─ validate_field(schema_def, value)
    │    ├─ get_default(schema_def)
    │    ├─ has_field(config, path)
    │    └─ get_field_schema(path)
    │
    ├─→ planner.lua
    │    ├─ load_section(section_name) → section module
    │    ├─ sort_steps(steps)
    │    ├─ validate_config(config)
    │    ├─ merge_user_programs_services(config)
    │    └─ compose(config, distro) → [steps]
    │
    ├─→ bootstrap/arch.lua or debian.lua (should merge)
    │    └─ emit_bootstrap_steps(conf, partitions) → [disk+system steps]
    │
    ├─→ rebuild.lua
    │    ├─ to_set(list) → {v: true}
    │    ├─ sorted_diff(a, b) → [diff keys]
    │    └─ diff(state) → [steps]
    │
    ├─→ executor.lua
    │    ├─ shq(s) → quoted shell string
    │    ├─ run_shell(step, mount_point) → {success, error}
    │    └─ run(steps, ctx, dispatch, hooks) → [results]
    │
    └─→ repos.lua
         ├─ arch_repo(mirrors) → {type, mirrors, commands}
         ├─ aur_repo(name, url, ...) → {type, build, commands}
         ├─ flatpak_repo(repo, ...) → {type, commands}
         ├─ deb_repo(mirrors) → {type, mirrors, commands}
         ├─ install_cmd(distro, packages) → shell cmd
         ├─ remove_cmd(distro, packages) → shell cmd
         └─ update_cmd(distro) → shell cmd
```

---

## Data Structures

### Program Definition (from .lua config)
```lua
{
    name = "git",
    scope = "system" | "user" | "both",
    schema = {
        properties = {
            user = {type = "string", required = true},
            email = {type = "string", required = true},
            ...
        }
    },
    service = { name = "...", ... },  -- optional
    generate_config = function(prog_def, options) return config_str end,
    validate = function(prog_def, options) return ok, err end,  -- optional
    post_install = function(...) ... end,  -- optional hook
    _extends = "parent_program_name"  -- for inheritance
}
```

### Step (from planner)
```lua
{
    kind = "system" | "package" | "service" | "disk",
    name = "step-name",
    program = "program_name" or "",
    args = {...} or {},
    chroot = true | false,
    timeout_s = 300,
    on_error = "error" | "warn",
    depends_on = {...},  -- optional
    order = 0,  -- sort key
    meta = {...}  -- optional metadata
}
```

### Cache Hierarchy (Current)
```lua
_builtin_cache[program_name]  = builtin_def (populated by load_program_file)
_user_cache[program_name]     = merged_def (BUG: should be user-only, contains merged)
_merged_cache[program_name]   = merged_def (canonical merged result)
```

### Cache Hierarchy (Proposed)
```lua
_merged_cache[program_name] = merged_def (only cache needed)
```

---

## Inheritance Resolution Algorithm

1. **Input:** program_name, builtin_programs {name: path}, user_programs {name: path}
2. **Circular Detection:** Track visited set across recursion
3. **Load Phase:**
   - Load builtin_programs[name] if exists
   - Load user_programs[name] if exists
4. **Merge Logic:**
   - Both exist: user._extends must equal program_name → merge(builtin, user)
   - Only user: if user._extends, recursively load parent → merge(parent, user)
   - Only builtin: if builtin._extends, recursively load parent → merge(parent, builtin)
   - Neither: error "not found"
5. **Output:** merged_program_def or (nil, error_msg)

**Issue:** _user_cache is populated with merged, not user-only (semantic bug)

---

## Schema Validation Flow

Current (Broken):
```
Lua: registry.lua:validate_config(prog_def, options)
    └─ Validates against prog_def.schema
    └─ Returns (ok, err)
    └─ Called from Python validator.py

Python: kod/config/validator.py:validate_config(config_dict)
    └─ Re-validates entire config
    └─ Authoritative (runs on all configs)
    └─ Lua validation is redundant
```

Proposed:
```
Python: kod/config/validator.py (ONLY PATH)
    └─ Validates entire config
    └─ Calls program.validate(config) hook if defined
    └─ Lua validation layer removed
```

**Impact:** Remove 120 lines from registry.lua + 70 lines from schema.lua

---

## Bootstrap (Arch vs Debian)

### Current: Separate Files
- `arch.lua` (149 lines): disk ops → mounts → fstab + locale + hostname + bootloader="systemd-boot"
- `debian.lua` (150 lines): identical except bootloader="grub"

### Proposed: Merged File
```lua
-- bootstrap.lua
function M.emit_bootstrap_steps(conf, predicted_partitions, distro)
    local bootloader_type = distro == "arch" and "systemd-boot" or "grub"
    -- Rest is identical, use bootloader_type variable
    meta = {bootloader = bootloader_type}
end

return M
```

**Savings:** -149 lines (99% duplication)

---

## Caching Issues

### Problem: _user_cache Semantic Confusion

```lua
-- Lines 336-341: Load user file
if user_programs and _has_key(user_programs, program_name) then
    local user_path = _safe_get(user_programs, program_name)
    user_def, err = registry.load_program_file(user_path)
    if not user_def then
        return nil, err
    end
end

-- Lines 359-371: Merge with builtin
merged = registry._merge_defs(builtin_def, user_def)

-- Lines 399: BUG - Store merged in _user_cache, not user_cache
registry.set_user_cache(program_name, merged)  -- Should be _merged_cache only!
```

### Solution
- Remove `_builtin_cache` and `_user_cache`
- Keep only `_merged_cache`
- If distinction needed: load separately (not cached)

---

## Dead Code Audit

### Not Called Anywhere (Confirmed via grep)
1. `configs.lua` - all 6 functions (stow, dconf, git, syncthing, copy_file, systemd_mount)
2. `utils.lua` - all 5 functions (dumpTable, list, map, if_true, if_else)
3. `dotfile_manager.lua` - stow() (duplicate of configs.lua:stow)
4. `mount.lua` - systemd_mount() (plus broken syntax)
5. `inheritance.lua` - all public functions (wrapped by registry.lua)

### Broken Code
- `mount.lua` line 31: `local function systemd-mount(config)` – invalid identifier (- not allowed)
- `mount.lua` line 34: `for name, conf in config.pairs()` – missing `do`
- `mount.lua` line 84: semicolon instead of space after `end`

---

## Python Integration Points

```
kod/registry/loader.py
    └─ Loads registry.lua via lupa
    └─ Calls registry.lua:load_program(), list_programs()
    └─ Wraps in Program objects

kod/config/validator.py
    └─ Calls schema.lua:validate_field() OR Python validation
    └─ Should move all to Python

kod/planner.py
    └─ Calls planner.lua:compose()
    └─ Calls bootstrap/{arch,debian}.lua:emit_bootstrap_steps()
    └─ Calls rebuild.lua:diff()
    └─ Calls executor.lua:run()
```

---

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| load_program_file(path) | O(1) | Single file load, pcall(dofile) |
| resolve_program(name, ...) | O(n) | n = depth of inheritance chain |
| compose(config, distro) | O(m) | m = number of section modules |
| diff(state) | O(p log p) | p = packages, sorted_diff |
| run(steps) | O(s*c) | s = steps, c = command exec time |

**Cache Benefit:** Skips re-resolution if already cached (O(1) lookup)

---

## Recommended Refactor Phases

### PHASE 1: Delete Dead Code (0 risk)
- [ ] Delete loader.lua (verify Python uses registry.lua)
- [ ] Delete configs.lua, utils.lua
- [ ] Delete mount.lua, dotfile_manager.lua
- [ ] Merge arch.lua + debian.lua into bootstrap.lua
- [ ] Update Python bootstrap import

**Validation:** Run test suite, confirm no hidden callers

### PHASE 2: Cache Simplification (medium risk)
- [ ] Remove _builtin_cache, _user_cache from registry.lua
- [ ] Keep _merged_cache only
- [ ] Update any tests that inspect cache state

**Validation:** Profile repeated resolve_program() calls

### PHASE 3: Remove Redundant Helpers (low risk)
- [ ] Delete _safe_get(), _has_key() from registry.lua
- [ ] Replace with direct indexing, confirm lupa works
- [ ] Fallback if actual failures occur

**Validation:** Run full test suite, check for lupa indexing errors

### PHASE 4: Simplify Validation (medium risk)
- [ ] Move all validation to Python (kod/config/validator.py)
- [ ] Remove validate_config() from registry.lua
- [ ] Remove validate_field() recursion from schema.lua
- [ ] Keep type/enum/required checks only

**Validation:** Ensure custom program validate() hooks still work

---

## Quick Fix Checklist

```
[ ] Lint: Check mount.lua syntax (will fail on load)
[ ] Search: Confirm no hidden require('kod.lib.core.configs')
[ ] Search: Confirm no hidden require('kod.lib.core.utils')
[ ] Test: Run test suite against current code
[ ] Delete: loader.lua, configs.lua, utils.lua, mount.lua, dotfile_manager.lua
[ ] Merge: arch.lua + debian.lua → bootstrap.lua
[ ] Test: Run test suite after deletions
[ ] Python: Update loader.py to stop importing loader.lua
[ ] Python: Update planner.py to use single bootstrap.lua
[ ] Cache: Simplify to _merged_cache only (PHASE 2)
[ ] Helpers: Remove _safe_get, _has_key (PHASE 3)
[ ] Validation: Move to Python (PHASE 4)
```

---

Generated: 2026-09-18
Analysis: KodOS Lua Layer Over-Engineering Detection
