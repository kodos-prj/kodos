# KodOS Maintenance Guide

Quick reference for common refactoring tasks and maintenance patterns.

---

## Adding a New Filesystem Type

**Problem**: User wants to format partitions as `f2fs` or a new filesystem.

**Steps**:

1. **Add to Lua filesystem type table** (`src/lua/kod/system/filesystem_types.lua`):
   ```lua
   mkfs_commands = {
       -- ... existing entries
       f2fs = "mkfs.f2fs",           -- Add your command
   },
   gpt_type_codes = {
       -- ... existing entries
       f2fs = "8300",                -- Add GPT code
   }
   ```

2. **Verify it works**:
   - `devices.lua` and `planner.py` will automatically use the new type
   - No Python changes needed!

3. **Test**:
   ```bash
   # Test preview (doesn't execute)
   kod plan-install config.json | grep f2fs
   ```

**Why this works**: Both Lua (devices.lua) and Python (planner.py) read from the same Lua table via `lua_table_to_python()`.

---

## Adding a New Config Section

**Problem**: You need a new configuration option (e.g., `security`, `monitoring`).

**Steps**:

1. **Add schema definition** (`src/lua/kod/core/schema.lua`):
   ```lua
   security = {
       description = "Security hardening settings",
       firewall = {
           type = "string",
           description = "Firewall backend: iptables|nftables|ufw"
       },
       selinux = {
           type = "boolean",
           description = "Enable SELinux"
       }
   }
   ```

2. **Python picks it up automatically**:
   - `config/schema.py` loads Lua schema and caches it
   - `config/validator.py` validates against it

3. **Use in config** (`kod.json` or config.lua):
   ```json
   {
       "security": {
           "firewall": "nftables",
           "selinux": false
       }
   }
   ```

4. **Emit steps for it** (if needed):
   - Create `src/lua/kod/sections/security.lua`
   - Add to `planner.py:compose_steps_lua()` if it should be scheduled

---

## Adding a New Installation Step

**Problem**: You need to install custom software or run arbitrary commands during install.

**Steps**:

1. **Create section module** or use existing (`src/lua/kod/sections/programs.lua`):
   ```lua
   -- In sections/programs.lua emit_steps function:
   if config.programs and config.programs.myapp then
       table.insert(steps, {
           name = "programs_install_myapp",
           description = "Install MyApp",
           command = "pacman -S myapp",
           chroot = true,           -- Run inside the new root
           order = 50,              -- After packages
           depends_on = {"packages_install"}
       })
   end
   ```

2. **Planner composes it automatically**:
   - `planner.py:compose_steps_lua()` calls all section modules
   - Steps are ordered by `order` field

3. **Test the preview**:
   ```bash
   kod plan-install config.json | jq '.[] | select(.name | contains("myapp"))'
   ```

---

## Consolidating Duplicated Logic

**Pattern**: You find the same code in two places.

**Approach** (as done in Phase 5c):

1. **Create a shared utility**:
   ```python
   # src/kod/shared_utils.py
   def common_function():
       """Does the thing."""
       pass
   ```

2. **Update all callers**:
   ```python
   # Before
   from mod_a import _local_impl
   result = _local_impl(x)
   
   # After
   from shared_utils import common_function
   result = common_function(x)
   ```

3. **Delete old implementations**:
   ```bash
   # Remove _local_impl from mod_a
   # Remove duplicate from mod_b
   ```

4. **Test**:
   ```bash
   python -m py_compile src/kod/mod_a.py src/kod/mod_b.py
   ```

**Example from this session**: Lua-to-Python conversion
- Was: 3 copies of `_lua_table_to_dict()` / `_lua_to_python()`
- Now: 1 function `lua_table_to_python()` in `lua_utils.py`
- Callers: `bootstrap.py`, `schema.py`, `loader.py` all import it

---

## Fixing Architecture Issues

**Pattern**: You discover Lua and Python have overlapping responsibilities.

**Approach**:

1. **Identify the issue**:
   - Is logic split between both languages?
   - Is there a "source of truth" duplicated?

2. **Decide ownership**:
   - **Lua**: Disk operations, step emission, file formats
   - **Python**: Orchestration, state management, validation

3. **Consolidate**:
   - Move the logic to the "owner"
   - Have the other layer call it or consume its output
   - Delete the duplicate

**Examples from this session**:

| Issue | Resolution |
|-------|-----------|
| Partitioning tool split (parted vs sgdisk) | Unified to sgdisk in Lua; planner.py reads from same Lua table |
| Filesystem type mappings in Python | Moved to Lua `filesystem_types.lua`; both callers use it |
| Lua-to-Python conversion (3 copies) | Created `lua_utils.py`; all callers use it |
| module named `filesystem.py` but only handles generations | Renamed to `generations.py` for clarity |

---

## Removing Dead Code

**Pattern**: You find code that's never called.

**Checklist**:

1. **Verify it's unused**:
   ```bash
   grep -r "function_name" src/kod/ --include="*.py"
   # Should only appear in definition, not calls
   ```

2. **Check imports**:
   ```bash
   grep -r "from .* import function_name" src/
   # If imported but not used, remove from import
   ```

3. **Delete**:
   - Remove from source file
   - Remove from imports
   - Verify syntax: `python -m py_compile src/kod/mod.py`

4. **Commit**:
   ```bash
   git add -A
   git commit -m "refactor: remove unused function_name"
   ```

**From this session**:
- Removed unused service function imports from `kod.py`
- Removed duplicate `load_config_lua` import
- Removed unused `svc_name` variable from `services.lua`

---

## Moving Responsibility from Python to Lua

**Pattern**: A function in Python should really be Lua.

**Checklist**:

1. **Is it called during step emission?**
   - Yes → Move to Lua section module

2. **Is it configuration-related?**
   - Yes → Move to Lua schema or helper

3. **Does it operate on system state?**
   - If before execution → Move to Lua
   - If after execution → Keep in Python

4. **Implementation**:
   - Create Lua version
   - Update callers to use Lua version (via lua_runtime)
   - Delete Python version

**Example consideration** (not done yet):
- `config/validator.py` validates config
- Could move to Lua, but Python validation is running as final check
- Current: Python validates; Lua was placeholder → OK to keep as-is

---

## Code Quality Checks

### Syntax Verification
```bash
# Python
python -m py_compile src/kod/**/*.py

# Lua
luac -p src/lua/kod/**/*.lua
```

### Unused Imports
```bash
# Find unused imports (manual scan for now)
grep "^import\|^from" src/kod/mod.py | while read line; do
  pattern=$(echo "$line" | cut -d' ' -f3)
  count=$(grep -c "$pattern" src/kod/mod.py)
  [ $count -lt 2 ] && echo "Possible unused: $line"
done
```

### Circular Dependencies
```bash
# Python: Scan for imports
grep -r "^import\|^from" src/kod/ --include="*.py" | \
  awk -F: '{print $1}' | sort -u | while read file; do
    # Manual check: do A→B and B→A exist?
done
```

### Line Count by Module
```bash
wc -l src/kod/**/*.py | sort -rn | head -20
```

---

## Commit Message Patterns

**Good pattern** (used in this session):
```
refactor: <change type>

- <what changed>
- <why it matters>
- <impact (lines saved, issues fixed, etc)>

Verified:
  • Syntax check ✓
  • No orphaned imports ✓
  • Tests pass (if applicable) ✓
```

**Example**:
```
refactor: consolidate Lua-to-Python conversion

- Create lua_utils.py with unified lua_table_to_python()
- Remove _lua_table_to_dict from bootstrap.py (22 lines)
- Remove _lua_table_to_dict from schema.py (24 lines)
- Remove _lua_to_python from loader.py (36 lines)

Impact: ~60 lines eliminated, single source of truth for conversion

Verified:
  • All Python syntax ✓
  • No orphaned imports ✓
```

---

## When to Ask for Help

**Reach out** if:
- You're unsure whether logic should be Lua or Python
- You're finding the same code in 3+ places
- An import seems circular or wrong
- A refactor touches >10 files or >500 lines
- Tests fail after a change

**Check before asking**:
- Does `git diff` show exactly what you changed?
- Did syntax check pass?
- Are all imports present?

---

## Phase 5c Summary (Current)

✅ **Completed**:
- Lua↔Python separation is clear
- No duplication of filesystem type definitions
- Single source of truth for Lua table conversion
- Module naming reflects actual responsibility
- Dead code removed
- Bug fixed (exec_warn signature)

⚠️ **Known TODOs** (for future phases):
- [ ] Move more init/setup from Python to Lua sections
- [ ] Consolidate boot.py hook logic
- [ ] Add comprehensive error messages
- [ ] Improve dry-run clarity
- [ ] Add testing framework

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System design and layer responsibilities
- [TEST.md](TEST.md) - Testing guide (to be created)
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development workflow (to be created)
