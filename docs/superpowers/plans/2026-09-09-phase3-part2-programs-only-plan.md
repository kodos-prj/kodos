# Phase 3 Part 2: Programs-Only Architecture - Implementation Plan

**Date:** 2026-09-09  
**Objective:** Unify services and programs into single section  
**Duration:** ~11 hours (can parallelize after Task 1)  
**Branch:** feat/architecture-redesign

---

## Task 1: Design & Finalize Structure ✅ DONE

**Objective:** Finalize Lua program + service structure

**Deliverable:** Specification document  
**Status:** Complete  
**File:** docs/superpowers/specs/2026-09-09-phase3-part2-programs-only-spec.md

---

## Task 2: Program Class Service Field (1h)

**Objective:** Add service field to Program class with validation

**Location:** `src/kod/registry/programs.py`

**What to implement:**

1. **Add service field to Program class:**
   ```python
   class Program:
       def __init__(self, name, lua_def, parent=None, scope=None):
           # ... existing code ...
           
           # NEW: Extract and validate service definition
           self.service = self._extract_service(lua_def)
   ```

2. **Method: `_extract_service(lua_def)`:**
   - Extract `lua_def.get("service")`
   - If service exists:
     - Validate service_name is non-empty string
     - Validate enable is boolean
     - Validate scope compatibility (not "user")
     - Extract service fields: enable, service_name, socket_activation, user_service, restart_policy, after, wanted_by, per_user
   - Return service dict or None
   - Raise SchemaError if validation fails

3. **Method: `get_service()`:**
   - Return self.service
   - Accessor for service definition

4. **Update `get_program_info()`:**
   - Include `"service": self.get_service()` in returned dict
   - Example: `{"name": "syncthing", "scope": "both", "service": {...}, ...}`

5. **Service validation rules:**
   - If service exists:
     - service.service_name required (non-empty string)
     - service.enable required (boolean)
     - service.socket_activation optional (boolean, default false)
     - service.user_service optional (boolean, default false)
     - service.restart_policy optional (string, default "always")
     - service.after optional (list)
     - service.wanted_by optional (list)
     - service.per_user optional (boolean, default false)
   - If scope = "user" and service exists: raise SchemaError
   - If scope = "both" and service.user_service = true: valid
   - If scope = "system" and service.user_service = true: valid (but per_user ignored)

6. **Update docstrings:**
   - Document service field and semantics
   - Explain when service field is allowed
   - Examples of programs with and without services

**Tests to pass:**
```bash
# Program with service
test_program_service_openssh
test_program_service_syncthing
test_program_service_validation

# Program without service
test_program_no_service_git
test_program_no_service_neovim

# Service validation
test_program_service_user_scope_invalid  # service + scope="user" should error
test_program_service_field_required
test_program_service_get_program_info_includes_service
```

**Success Criteria:**
- Program class extracts service definition
- Service validation enforces rules
- Service accessible via get_service()
- get_program_info() includes service
- Invalid service raises SchemaError
- Scope and service compatibility checked
- All new tests pass
- All existing tests still pass

---

## Task 3: Validator Service Handling (1.5h)

**Objective:** Validate service configuration in programs

**Location:** `src/kod/config/validator.py`

**What to implement:**

1. **Create `_validate_program_service(program, location)` helper:**
   - `program`: Program object with service field
   - `location`: "system" or "user.alice"
   - Returns: ValidationError or None

2. **Service validation logic:**
   ```python
   def _validate_program_service(program, location):
       """Validate service definition at given location."""
       
       service = program.get_service()
       if not service:
           return None  # No service, that's fine
       
       # Service only allowed at system/both scope
       if program.get_scope() not in ["system", "both"]:
           return ValidationError(
               f"Program '{program.name}' has service but scope='{program.get_scope()}'"
           )
       
       # Service only allowed at system level (not user level)
       if location.startswith("user."):
           return ValidationError(
               f"Service configuration for '{program.name}' not allowed at user level"
           )
       
       # Validate service fields
       required_fields = ["service_name", "enable"]
       for field in required_fields:
           if field not in service:
               return ValidationError(
                   f"Program '{program.name}' service missing '{field}' field"
               )
       
       # service_name must be non-empty
       if not service.get("service_name"):
           return ValidationError(
               f"Program '{program.name}' service_name cannot be empty"
           )
       
       return None
   ```

3. **Update `_validate_programs_section()`:**
   - Add service validation alongside program validation
   - Call helper for each program
   - Collect service validation errors with program errors

4. **Clear error messages:**
   - Show program name
   - Show what's wrong
   - Show how to fix
   - Example: "Service configuration for 'git' not allowed at user level. Remove service field or use system-level only."

5. **Validation call sites:**
   - System-level: `_validate_programs_section(config["programs"], "system")`
   - User-level: `_validate_programs_section(user_config["programs"], f"user.{user_name}")`

**Tests to pass:**
```bash
test_validator_service_system_level_valid
test_validator_service_user_level_invalid
test_validator_service_missing_service_name
test_validator_service_missing_enable
test_validator_service_with_user_scope_invalid
test_validator_service_error_message_clear
```

**Success Criteria:**
- Service fields validated correctly
- Service not allowed at user level (error message)
- Service required fields checked
- Clear error messages
- All validation tests pass
- All existing tests still pass

---

## Task 4: Compiler Service Integration (1.5h)

**Objective:** Compile service definitions in programs

**Location:** `src/kod/config/compiler.py`

**What to implement:**

1. **Extend `_compile_programs()` method:**
   - Extract service from program
   - Store service config in compiled output
   - Service config separate from program config

2. **System-level compilation:**
   ```python
   if "programs" in config:
       compiled["programs"] = {}
       for name, options in config["programs"].items():
           program = loader.load_program(name)
           
           # NEW: Extract service if present
           service = program.get_service()
           
           compiled["programs"][name] = {
               "program": program,
               "options": options,
               "config": program.generate_config(options),
               "scope": "system",
               # NEW: Include service
               "service": service if service else None
           }
   ```

3. **User-level compilation:**
   - User programs can override program config
   - User programs CANNOT override service
   - If same program at system + user level:
     - Merge program options
     - Keep system service definition
     - User inherits system service config

4. **Compiled format:**
   ```python
   # System program with service
   compiled["programs"]["openssh"] = {
       "program": <Program>,
       "options": {...},
       "config": "sshd_config",
       "scope": "system",
       "service": {
           "enable": True,
           "service_name": "sshd",
           "socket_activation": False,
           "user_service": False,
           "restart_policy": "always"
       }
   }
   
   # User program (no service)
   compiled["users"]["alice"]["programs"]["git"] = {
       "program": <Program>,
       "options": {...},
       "config": "git config",
       "scope": "user",
       # No service field
   }
   
   # User-level service (if program supports user_service)
   compiled["users"]["alice"]["programs"]["syncthing"] = {
       "program": <Program>,
       "options": {...},  # Merged with system
       "config": "syncthing config",
       "scope": "user",
       "overrides_system": True,
       "service": {  # Inherited from system or per-user instance
           "enable": True,
           "service_name": "syncthing",
           "user_service": True,
           "per_user": True
       }
   }
   ```

5. **Service compilation rules:**
   - Service only compiled if present in program definition
   - Service preserved at system level
   - User cannot override service fields
   - User can enable/disable if per_user = true
   - Service unit file paths generated (optional, for install workflow)

**Tests to pass:**
```bash
test_compiler_service_system_level
test_compiler_service_included_in_output
test_compiler_service_user_level_inherited
test_compiler_service_per_user_instance
test_compiler_multiple_services_compiled
```

**Success Criteria:**
- Service definitions compiled correctly
- Service preserved in compiled format
- User-level can't override service
- Per-user service handled correctly
- Compiled format includes service metadata
- All compilation tests pass
- All existing tests still pass

---

## Task 5: Builtin Service Programs (2h)

**Objective:** Create Lua definitions for service-based programs

**Location:** `src/kod/registry/builtin/`

**Programs to create:**

1. **syncthing.lua (UPGRADE)**
   - Add `service` field
   - Keep existing config fields
   - Service: enable, socket_activation, user_service

2. **openssh.lua (NEW - from services section)**
   - service: enable, service_name="sshd"
   - config: PermitRootLogin, etc.

3. **networkmanager.lua (NEW)**
   - service: enable, service_name="NetworkManager"

4. **cups.lua (NEW)**
   - service: enable, service_name="cupsd"

5. **bluetooth.lua (NEW)**
   - service: enable, service_name="bluetooth"

6. **fwupd.lua (NEW)**
   - service: enable, service_name="fwupd"

**Each program structure:**
```lua
return {
    name = "service_name",
    scope = "system",  -- or "both" for syncthing
    package = "package_name",
    
    service = {
        enable = true,
        service_name = "systemd_service_name",
        socket_activation = false,  -- optional
        user_service = false,       -- optional
        restart_policy = "always"   -- optional
    },
    
    schema = {
        type = "object",
        properties = {
            -- service-specific settings
        }
    },
    
    default_config = {
        -- defaults
    },
    
    generate_config = function(self, options)
        -- Generate service config (e.g., sshd_config)
    end
}
```

**syncthing.lua specifically:**
- scope = "both" (supports system and per-user)
- service.user_service = true
- schema includes user-specific options
- generate_config creates user-specific config

**Tests to pass:**
```bash
test_builtin_openssh_has_service
test_builtin_syncthing_has_service
test_builtin_syncthing_scope_both
test_builtin_cups_scope_system
test_builtin_networkmanager_service_name
```

**Success Criteria:**
- All 6 service programs created
- Service fields populated correctly
- Scopes appropriate for each program
- Programs load without errors
- All builtin program tests pass

---

## Task 6: Installation Workflow Integration (1h)

**Objective:** Run services during installation

**Location:** `src/kod/system/services.py` and install workflow

**What to implement:**

1. **Refactor service enablement:**
   - Old code: `enable_services(list_of_services)`
   - New code: Accept compiled program dict with service info

2. **Service execution order:**
   ```
   1. Install packages (all programs)
   2. Generate system configs (all programs)
   3. Enable system services (from compiled programs)
   4. Create users
   5. For each user:
       - Install user packages
       - Generate user configs
       - Enable user services (if per_user = true)
   6. Start/reload services
   ```

3. **New function: `enable_services_from_programs(compiled)`**
   - Extract programs with service definitions
   - Enable each service
   - Handle per-user services separately

4. **Service enablement logic:**
   - Only enable if service.enable = true
   - Use systemctl enable (or equivalent)
   - For per-user: systemctl --user enable

5. **No breaking changes:**
   - Existing service workflow still works
   - New program-based services integrated
   - Gradual transition possible

**Tests to pass:**
```bash
test_install_service_from_program
test_install_per_user_service
test_install_service_order
```

**Success Criteria:**
- Services enabled from compiled programs
- Per-user services handled
- Correct systemctl commands used
- Installation workflow tests pass

---

## Task 7: Comprehensive Tests (2h)

**Objective:** Test all service + program integration

**Location:** `tests/registry/test_service_programs.py` (new) and updates to existing tests

**Test categories:**

1. **Program class service field (8 tests):**
   - Service extraction and validation
   - Scope compatibility
   - Error handling

2. **Validator service (8 tests):**
   - System-level service validation
   - User-level service rejection
   - Field validation
   - Error messages

3. **Compiler service (8 tests):**
   - Service compilation
   - Merging behavior
   - Per-user services
   - Output format

4. **Builtin service programs (6 tests):**
   - Each program loads
   - Service fields correct
   - Scopes appropriate

5. **Integration workflows (6 tests):**
   - Full validation + compile + install
   - Service enablement
   - Per-user service handling
   - Backward compatibility

6. **Edge cases (6 tests):**
   - Empty service field
   - Service + no scope
   - User override of service (should fail)
   - Multiple services per program

**Coverage target:** 95%+ of service-related code

**Tests to run:**
```bash
pytest tests/registry/test_service_programs.py -v
pytest tests/registry/test_programs.py -v
pytest tests/config/test_validator.py -v
pytest tests/config/test_compiler.py -v
pytest tests/ -v  # All tests
```

**Success Criteria:**
- 42+ new service tests created
- 95%+ coverage of service code
- All tests pass
- All existing tests still pass
- No regressions

---

## Task 8: Documentation & Migration Guide (1.5h)

**Objective:** Document new architecture and migration path

**Files to create/update:**

1. **docs/INSTALLATION_GUIDE.md (UPDATE)**
   - Section: "Programs with Services"
   - Examples: openssh, syncthing, git
   - Explain service field
   - Show complete example

2. **docs/extending.md (UPDATE)**
   - Service field in program definitions
   - When to include service
   - Service field reference
   - Examples of programs with/without services

3. **docs/MIGRATION_GUIDE.md (NEW)**
   - How to migrate from services to programs
   - Old services section still works
   - Gradual migration possible
   - Examples: openssh, syncthing migration
   - Timeline for services deprecation

4. **README.md (UPDATE)**
   - Programs section now includes services
   - Single source of truth
   - Simplified architecture

5. **docs/examples/:**
   - `system_services_as_programs.lua` (NEW)
     - openssh, cups, networkmanager as programs
   - `mixed_programs_and_services.lua` (UPDATE)
     - Show service field in programs

**Migration guide structure:**
```
## Migrating from Services to Programs

### Old Config (Still Works)
services = { ... }
programs = { ... }

### New Config (Programs-Only)
programs = { ... (with services) ... }

### Step-by-Step Migration
1. Keep old config (backward compat)
2. Convert services to programs one-by-one
3. Test each conversion
4. Eventually remove services section

### Examples
- openssh: from services → programs
- syncthing: from services + programs → single program
- git: already in programs (no change)
```

**Success Criteria:**
- Migration guide clear and complete
- Examples runnable and tested
- Documentation consistent
- User can understand new architecture
- User can migrate existing configs

---

## Parallel Tasks

**After Task 1, can parallelize:**
- Tasks 2-4 (Program class, Validator, Compiler) - foundation
- Tasks 5-7 (Builtin programs, Tests, Docs) - depend on 2-4
- Task 6 can start during 2-4

**Recommended execution:**
1. Task 1 (1 session, ~30min)
2. Tasks 2-4 in parallel (~4 hours total)
3. Tasks 5-7 in parallel (~5.5 hours total)
4. Final verification and merge

---

## Verification Checklist

Before marking complete:

- [ ] All new tests pass
- [ ] All existing tests pass
- [ ] No regressions
- [ ] Service programs load correctly
- [ ] Backward compatibility verified
- [ ] Migration guide tested
- [ ] Documentation complete
- [ ] Examples work
- [ ] Compiler output correct
- [ ] Validator rejects invalid service
- [ ] Installation workflow handles services
- [ ] Code follows project conventions

---

## Success Criteria Summary

✅ Single source of truth (programs section)  
✅ No duplication (syncthing once, not twice)  
✅ Services are optional program sub-field  
✅ All scope semantics work (system/user/both)  
✅ Backward compatible with existing services  
✅ Clear migration path  
✅ Installation workflow runs services  
✅ Per-user services supported  
✅ 42+ tests pass with 95%+ coverage  
✅ Complete documentation  
✅ Production ready  

---

## Timeline

| Phase | Tasks | Duration | Parallel? |
|-------|-------|----------|-----------|
| A | 1 | 0.5h | - |
| B | 2-4 | 4h | ✅ Yes |
| C | 5-7 | 5.5h | ✅ Yes (after B) |
| D | Verify | 1h | - |
| **Total** | | **~11h** | Effective: ~6.5h |

---
