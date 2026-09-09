# Phase 3 Enhancement: System & User Programs - Implementation Plan

**Date:** 2026-09-09  
**Duration:** ~5-6 hours (estimated)  
**Objective:** Enable programs to be configured at system level AND/OR user level based on each program's scope

---

## Overview

Current limitation: Programs only work at user level.

**Enhancement:** Programs can declare their scope:
- `"system"` — Only configurable at system level (e.g., firewall)
- `"user"` — Only configurable at user level (e.g., git, neovim)
- `"both"` — Configurable at system and/or user level (e.g., syncthing)

This enables:
- System-wide defaults (git, syncthing)
- Per-user overrides
- System-level services (without per-user config)

---

## Implementation Tasks

### Task 1: Update Program Class (0.5h)

**What:** Add `scope` field to Program class with validation

**Where:** `src/kod/registry/programs.py`

**Changes:**
1. Add `scope` parameter to `Program.__init__(name, lua_def, parent=None, scope=None)`
2. Extract `scope` from Lua definition: `lua_def.get("scope", "user")`
3. Validate scope value: must be "system", "user", or "both"
4. Store as property: `self.scope`
5. Add `get_scope()` method returning the scope
6. Update `get_program_info()` to include scope in returned dict
7. Raise `SchemaError` if invalid scope value

**Tests:**
- Program with each scope: "system", "user", "both"
- Default scope when missing: should be "user"
- Invalid scope value raises SchemaError
- get_scope() returns correct value

**Acceptance:**
- Program class recognizes and validates scope field
- Default is "user" (backward compatible)
- Error on invalid scope value

---

### Task 2: Update PluginLoader (0.5h)

**What:** Extract and store scope metadata when loading programs

**Where:** `src/kod/registry/loader.py`

**Changes:**
1. In `load_program(name)`: after creating Program object, extract scope
2. If Lua definition has `scope` field, pass to Program constructor
3. If no `scope` field, Program uses default "user"
4. Store scope in Program object
5. Update `get_program_info()` to show scope

**Tests:**
- Builtin program (git.lua) shows scope: "user"
- User plugin can define scope
- Missing scope defaults to "user"
- Scope persists through caching

**Acceptance:**
- PluginLoader extracts scope from Lua programs
- Scope passed to Program class
- get_program_info includes scope in metadata

---

### Task 3: Update Validator (1h)

**What:** Enforce program scope during validation

**Where:** `src/kod/config/validator.py`

**Changes:**
1. Create `_validate_program_scope(program_name, program, scope_location)` helper
   - `program_name`: name of program (e.g., "git")
   - `program`: Program object
   - `scope_location`: where it's used ("system" or "user.alice")
   
2. For system-level programs (top-level `programs` section):
   - Check `program.scope` in ["system", "both"]
   - If not, raise ValidationError with clear message
   
3. For user-level programs (inside `users.alice.programs`):
   - Check `program.scope` in ["user", "both"]
   - If not, raise ValidationError with clear message

4. Update `_validate_programs_section()` to accept scope_location parameter
   - Call from validator: `_validate_programs_section(config["programs"], "system")`
   - Call from user validation: `_validate_programs_section(users[name]["programs"], f"user.{name}")`

5. Error messages must include:
   - What program was used
   - Where it was used (system or user level)
   - What scopes are allowed
   - Available programs for that scope

**Error Message Examples:**
```
✗ Validation Error
Program 'git' (scope: user) cannot be used at system level.
Fix: Move 'programs.git' to 'users.alice.programs.git'

Available system-level programs: syncthing
```

```
✗ Validation Error
Program 'firewall' (scope: system) cannot be used at user level.
Fix: Move 'users.alice.programs.firewall' to top-level 'programs.firewall'

Available user-level programs: git, neovim, syncthing
```

**Tests:**
- System-level git program → validation error
- User-level firewall program → validation error (no firewall yet, but example)
- System-level syncthing → validation passes
- User-level syncthing → validation passes
- Both syncthing at system and user level → both pass
- Clear error messages

**Acceptance:**
- Program scope enforced correctly
- Validation accepts valid scopes
- Validation rejects invalid scopes
- Error messages are helpful

---

### Task 4: Update Compiler (1h)

**What:** Compile programs from both system and user levels, with merging

**Where:** `src/kod/config/compiler.py`

**Changes:**
1. Extend `_compile_programs()` to handle both system and user level:
   ```python
   # System-level programs
   if "programs" in config:
       compiled["programs"] = {}
       for name, options in config["programs"].items():
           program = loader.load_program(name)
           compiled["programs"][name] = {
               "program": program,
               "options": options,
               "config": program.generate_config(options),
               "scope": "system"
           }
   
   # User-level programs (inside each user)
   for user_name, user_config in config["users"].items():
       if "programs" in user_config:
           compiled["users"][user_name]["programs"] = {}
           for name, options in user_config["programs"].items():
               program = loader.load_program(name)
               
               # Check if same program at system level
               if name in compiled.get("programs", {}):
                   # Merge: user overrides system
                   base_options = compiled["programs"][name]["options"]
                   merged_options = {**base_options, **options}
               else:
                   merged_options = options
               
               compiled["users"][user_name]["programs"][name] = {
                   "program": program,
                   "options": merged_options,
                   "config": program.generate_config(merged_options),
                   "scope": "user",
                   "overrides_system": name in compiled.get("programs", {})
               }
   ```

2. Compilation flow:
   - System-level first (provides defaults)
   - User-level second (can override system)
   - Merging: user options override system options

3. Store metadata:
   - `scope`: "system" or "user"
   - `overrides_system`: boolean, if user overrides system config

**Tests:**
- System-only program compiles correctly
- User-only program compiles correctly
- Both system and user (same program):
  - User options override system options
  - Generated config reflects merged options
  - Metadata shows override
- Empty programs section handled gracefully

**Acceptance:**
- Programs compile from system level
- Programs compile from user level
- Merging works (user overrides system)
- Compiled format includes scope metadata

---

### Task 5: Update Builtin Programs (0.5h)

**What:** Add scope field to all 3 builtin programs

**Where:** 
- `src/kod/registry/builtin/git.lua`
- `src/kod/registry/builtin/neovim.lua`
- `src/kod/registry/builtin/syncthing.lua`

**Changes:**

**git.lua:**
```lua
return {
    name = "git",
    scope = "user",  -- NEW: Only configurable at user level
    schema = {...},
    ...
}
```

**neovim.lua:**
```lua
return {
    name = "neovim",
    scope = "user",  -- NEW: Only configurable at user level
    schema = {...},
    ...
}
```

**syncthing.lua:**
```lua
return {
    name = "syncthing",
    scope = "both",  -- NEW: Configurable at system OR user level
    schema = {...},
    ...
}
```

**Also:**
- Update `docs/examples/custom_program.lua` to show scope field
- Add comments explaining scope

**Tests:**
- Each program loads with correct scope
- Scope value validated

**Acceptance:**
- All 3 builtin programs have scope field
- Scope values match design (git: user, neovim: user, syncthing: both)

---

### Task 6: Comprehensive Tests (1h)

**What:** Test all scope scenarios

**Where:** 
- `tests/registry/test_scope.py` (new)
- Updates to existing test files

**Tests to add:**

1. **Program class scope:**
   - test_program_scope_system
   - test_program_scope_user
   - test_program_scope_both
   - test_program_scope_default_is_user
   - test_program_scope_invalid_raises_error

2. **Validator scope enforcement:**
   - test_system_level_user_program_rejected
   - test_user_level_system_program_rejected
   - test_system_level_both_program_accepted
   - test_user_level_both_program_accepted
   - test_error_message_includes_available_programs

3. **Compiler scope handling:**
   - test_system_level_programs_compiled
   - test_user_level_programs_compiled
   - test_system_and_user_same_program_merged
   - test_user_overrides_system_options
   - test_compiled_metadata_includes_scope

4. **Integration:**
   - test_full_workflow_system_level_program
   - test_full_workflow_user_level_program
   - test_full_workflow_both_system_and_user
   - test_validation_prevents_scope_mismatch

5. **Builtin programs:**
   - test_git_scope_is_user
   - test_neovim_scope_is_user
   - test_syncthing_scope_is_both
   - test_git_rejected_at_system_level
   - test_syncthing_accepted_at_both_levels

**Acceptance:**
- All new tests pass
- All existing tests still pass
- 90%+ coverage of scope code
- Edge cases tested (merging, overrides, errors)

---

### Task 7: Documentation Updates (0.5h)

**What:** Update docs to explain system vs user programs

**Where:**
- `docs/INSTALLATION_GUIDE.md` (update)
- `docs/extending.md` (update)
- `README.md` (update section)

**Updates:**

1. **docs/INSTALLATION_GUIDE.md:**
   - Add section: "System-Level vs User-Level Programs"
   - Explain scope field and semantics
   - Show examples of each scope
   - Show merging (system + user)
   - Show scope in program info output

2. **docs/extending.md:**
   - Add `scope` field to program definition section
   - Explain when to use each scope
   - Examples: system-only, user-only, both

3. **README.md:**
   - Update Program Registry section
   - Mention both system and user level availability

4. **Create example config:**
   - Show system-level programs
   - Show user-level programs
   - Show both levels together
   - Show override behavior

**Acceptance:**
- Documentation is clear and comprehensive
- Examples work (can run them)
- All scopes explained with rationale

---

## Task Dependencies

```
Task 1 (Program class)
  ↓
Task 2 (PluginLoader) ← depends on Task 1
  ↓
Task 3 (Validator) ← depends on Task 2
  ↓
Task 4 (Compiler) ← depends on Task 3
  ↓
Task 5 (Builtin programs) ← depends on Tasks 1-4
  ├→ Task 6 (Tests) ← depends on all above
      ↓
Task 7 (Documentation) ← depends on all above
```

**Sequential requirement:** Must follow order (each task depends on previous)

---

## Success Criteria

✅ **Functionality:**
- [x] Programs declare scope: "system", "user", or "both"
- [x] Validator enforces scope correctly
- [x] Compiler handles system and user level
- [x] System and user configs can coexist
- [x] User config overrides system config
- [x] Builtin programs have correct scopes

✅ **Quality:**
- [x] All tests pass (new + existing)
- [x] 90%+ coverage of scope code
- [x] Clear error messages
- [x] No breaking changes

✅ **Documentation:**
- [x] System vs user programs explained
- [x] Examples provided
- [x] Scope field documented
- [x] Merging behavior explained

---

## Estimated Timeline

| Task | Hours | Status |
|------|-------|--------|
| 1. Program class | 0.5h | Pending |
| 2. PluginLoader | 0.5h | Pending |
| 3. Validator | 1.0h | Pending |
| 4. Compiler | 1.0h | Pending |
| 5. Builtin programs | 0.5h | Pending |
| 6. Tests | 1.0h | Pending |
| 7. Documentation | 0.5h | Pending |
| **Total** | **~5.5h** | Pending |

---

## Verification Steps

After implementation:

```bash
# 1. Test system-level program
kod config validate example/system_programs.lua

# 2. Test user-level program  
kod config validate example/user_programs.lua

# 3. Test both levels
kod config validate example/mixed_programs.lua

# 4. Check program info shows scope
kod registry info git
kod registry info syncthing

# 5. Run full test suite
pytest tests/registry/test_scope.py -v
pytest tests/ -v  # All tests
```

---

## Git Commit Plan

After all tasks:
```
git add -A
git commit -m "Phase 3 Enhancement: System & User-Level Programs

Add support for programs at system level and/or user level based on scope:

NEW FEATURES:
- Programs declare scope: 'system', 'user', or 'both'
- Validator enforces scope at both levels
- Compiler handles system and user programs
- User config overrides system config

UPDATED COMPONENTS:
- Program class: Added scope field with validation
- PluginLoader: Extracts scope from program definitions
- Validator: Enforces scope constraints
- Compiler: Compiles from system and user levels
- Builtin programs: Added scope field to git, neovim, syncthing

BACKWARD COMPATIBLE:
- Default scope is 'user' (existing behavior)
- Existing configs work unchanged
- All Phase 1-2 tests pass

NEW TESTS:
- 20+ scope-related tests
- 90%+ coverage

DOCUMENTATION:
- Updated installation guide
- Added system vs user program explanation
- Examples for all scopes
"
```

---
