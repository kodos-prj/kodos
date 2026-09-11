# Phase 5c Plan: Schema-Driven Step Emission Refactor

**Objective:** Refactor planner and section modules to use schema-driven composition, enabling configuration to define step generation entirely through Lua schemas and section modules.

**Key Outcome:** Planner becomes a simple iterator that composes steps from section modules, each self-contained with its own schema and step generation logic.

---

## Overview

### Current Architecture (Phase 5b)
```
Python SECTION_HELP (schema)
    ↓
Python validator (type checking)
    ↓
Python planner (nested conditionals for each section)
    ↓
Bootstrap.py (calls Lua bootstrap modules)
    ↓
Executor (runs steps)
```

### Proposed Architecture (Phase 5c)
```
Lua schema.lua (source of truth)
    ↓
Lua section modules (boot.lua, hardware.lua, locale.lua, etc.)
    ├─ Each has: schema + emit_steps() function
    ├─ Self-contained, no planner logic
    └─ Composable
    ↓
Lua planner.lua (simple composer)
    └─ for each section: call emit_steps(), collect results
    ↓
Python reads Lua schema for validation (optional, for CLI)
    ↓
Executor (runs steps)
```

---

## Tasks

### Task 1: Define Schema in Lua

**File:** `src/kod/lib/schema.lua` (NEW)

Define complete configuration schema in Lua:
- All 13 sections
- Nested field definitions
- Types, enums, defaults, descriptions
- Validation functions

```lua
local Schema = {}

Schema.base_distribution = {
    type = "string",
    enum = {"arch", "debian"},
    required = true,
    description = "Base Linux distribution"
}

Schema.boot = {
    type = "dict",
    required = false,
    description = "Kernel and bootloader configuration",
    fields = {
        kernel = {...},
        loader = {...}
    }
}

-- ... all 13 sections ...

-- Validation functions
function Schema:validate(section_name, config)
    local section_schema = self[section_name]
    if not section_schema then return false end
    -- Type checking, enum validation, required field validation
    return true
end

return Schema
```

**Testing:**
- Unit tests verify all 13 sections defined
- Type validation works correctly
- Enum validation works
- Required field checking works

---

### Task 2: Create Lua Section Modules

**Files:** `src/kod/sections/*.lua` (NEW)

Create a module for each configuration section:
- `boot.lua` — Kernel and bootloader
- `hardware.lua` — Hardware features (pipewire, etc.)
- `locale.lua` — Localization
- `network.lua` — Network config
- `users.lua` — User accounts
- `packages.lua` — Package lists
- `services.lua` — System services
- `desktop.lua` — Desktop environment
- `fonts.lua` — Font packages
- `repos.lua` — Repositories
- `devices.lua` — Disk configuration
- `programs.lua` — Program definitions
- `base_distribution.lua` — Base distro selection

**Module structure:**

```lua
-- src/kod/sections/boot.lua
local Schema = require("schema")

local boot = {
    schema = Schema.boot,
    
    emit_steps = function(config, distro)
        -- Validate config against schema
        if not boot.schema:validate(config) then
            error("Invalid boot config")
        end
        
        local steps = {}
        
        -- Emit steps based on config and schema defaults
        if config.kernel then
            -- Emit kernel steps
        end
        
        if config.loader then
            -- Emit bootloader steps
        end
        
        return steps
    end
}

return boot
```

**Each module should:**
- Have a `schema` field pointing to its schema
- Implement `emit_steps(config, distro)` function
- Validate config against schema before emitting
- Handle defaults from schema
- Return list of steps

**Testing:**
- Test each module's emit_steps independently
- Test validation against schema
- Test default value application
- Integration tests with planner

---

### Task 3: Refactor Planner to Use Schema-Driven Composition

**File:** `src/kod/lib/planner.lua` (MODIFY)

Rewrite planner to be a simple composer:

```lua
-- src/kod/lib/planner.lua
local Schema = require("schema")
local sections = {
    base_distribution = require("sections/base_distribution"),
    repos = require("sections/repos"),
    devices = require("sections/devices"),
    boot = require("sections/boot"),
    hardware = require("sections/hardware"),
    locale = require("sections/locale"),
    network = require("sections/network"),
    users = require("sections/users"),
    desktop = require("sections/desktop"),
    fonts = require("sections/fonts"),
    packages = require("sections/packages"),
    services = require("sections/services"),
    programs = require("sections/programs"),
}

function plan_install(config, distro)
    local plan = {
        metadata = {
            distro = distro,
            mode = "install"
        },
        steps = {}
    }
    
    -- Validate complete config against schema
    for section_name in pairs(sections) do
        if config[section_name] then
            if not sections[section_name].schema:validate(config[section_name]) then
                error(string.format("Invalid %s config", section_name))
            end
        end
    end
    
    -- Compose steps from all sections
    for section_name, section_module in pairs(sections) do
        if config[section_name] then
            local section_steps = section_module.emit_steps(
                config[section_name],
                distro
            )
            if section_steps then
                for _, step in ipairs(section_steps) do
                    table.insert(plan.steps, step)
                end
            end
        end
    end
    
    return plan
end

return {
    plan_install = plan_install,
    plan_rebuild = plan_rebuild,  -- Similar for rebuild
    sections = sections,
    schema = Schema
}
```

**Changes:**
- Remove all nested conditionals for sections
- Remove section-specific logic from planner
- Planner just iterates sections and calls emit_steps()
- Each section is self-contained
- Planner is now ~50 lines instead of 600+

**Testing:**
- Test planner with all sections
- Test planner with missing sections (should work)
- Test planner with invalid config (should error with clear message)
- Test step ordering
- Test dry-run accuracy

---

### Task 4: Update Bootstrap Integration

**File:** `src/kod/bootstrap.py` (MODIFY)

Update bootstrap bridge to use schema-aware Lua:

```python
def emit_bootstrap_steps(config, distro):
    """Emit bootstrap steps using Lua section modules."""
    lua = get_lua_runtime()
    
    # Lua already has schema and section modules loaded
    # Just call planner
    steps = lua.eval("""
        local planner = require("planner")
        return planner.plan_install(%s, "%s")
    """ % (lua_table(config), distro))
    
    return steps
```

**Benefits:**
- No more Python-Lua schema mismatch
- Bootstrap uses schema-aware section modules
- Step generation is entirely in Lua

---

### Task 5: Python Validator Reads Lua Schema

**File:** `src/kod/config/validator.py` (MODIFY)

Update validator to read schema from Lua:

```python
def load_schema_from_lua():
    """Load configuration schema from Lua."""
    lua = get_lua_runtime()
    schema = lua.eval("return require('schema')")
    # Convert Lua table to Python dict
    return lua.table_to_dict(schema)

def validate_config(config: dict) -> List[ValidationError]:
    """Validate config against Lua-defined schema."""
    schema = load_schema_from_lua()
    
    errors = []
    
    # Validate each section
    for section_name, section_config in config.items():
        if section_name not in schema:
            errors.append(ValidationError(f"Unknown section: {section_name}"))
            continue
        
        section_schema = schema[section_name]
        
        # Type validation
        expected_type = section_schema.get('type')
        if expected_type and not _type_ok(section_config, expected_type):
            errors.append(ValidationError(
                f"Invalid type for '{section_name}': expected {expected_type}, got {type(section_config).__name__}"
            ))
        
        # Nested field validation
        if 'fields' in section_schema and isinstance(section_config, dict):
            _validate_nested_fields(
                section_name,
                section_config,
                section_schema['fields'],
                errors
            )
    
    return errors
```

**Benefits:**
- Single source of truth (Lua schema)
- Python validator stays in sync automatically
- Less Python code (no hardcoded SECTION_HELP)

---

### Task 6: Tests and Verification

**Test Files:**
- `tests/lua/test_schema.lua` — Lua schema validation
- `tests/lua/test_sections/` — Each section module
- `tests/test_planner.lua` — Planner composition
- `tests/test_validator.py` — Python validator reading Lua schema
- `tests/integration/test_end_to_end.py` — Full pipeline

**Test Coverage:**
- Each section module emits correct steps
- Schema validation works in Lua
- Planner correctly composes all sections
- Python validator reads schema correctly
- End-to-end: config → plan → executor works

---

## Metrics

### Code Reduction
- Python planner: 600+ lines → ~100 lines (in bootstrap.py caller)
- Replaces Python SECTION_HELP (361 lines) with Lua schema.lua (~300 lines, more executable)
- Section-specific logic moves to Lua section modules (cleaner separation)

### Maintainability
- Schema defined once (in Lua)
- Each section is self-contained
- Adding new section = new module, no planner changes
- Easier to understand (no nested conditionals)

### Extensibility
- Custom sections can be added without modifying core code
- Each section can evolve independently
- Schema can be extended per-section

---

## Rollout

### Phase 5c Sprint 1: Foundation
- Task 1: Lua schema definition ✓
- Task 2: Basic section modules ✓
- Tests: Schema validation ✓

### Phase 5c Sprint 2: Integration
- Task 3: Refactor planner ✓
- Task 4: Update bootstrap ✓
- Tests: Planner composition ✓

### Phase 5c Sprint 3: Alignment
- Task 5: Python validator reads Lua ✓
- Task 6: End-to-end verification ✓
- All tests pass ✓

---

## Success Criteria

✅ Schema is defined in Lua (source of truth)  
✅ All 13 sections have Lua modules  
✅ Each module has schema + emit_steps()  
✅ Planner uses schema-driven composition  
✅ No nested conditionals for sections in planner  
✅ Python validator reads Lua schema  
✅ All tests pass (no regressions)  
✅ Dry-run accuracy maintained  
✅ Both Arch and Debian work correctly  

---

## Benefits Summary

1. **Composable** — Planner is a simple composer, not orchestrator
2. **Schema-driven** — Steps generated based on schema, not hardcoded logic
3. **Self-contained** — Each section module is independent
4. **Maintainable** — Adding sections doesn't require planner changes
5. **Extensible** — Custom sections can be added easily
6. **Future-proof** — Can replace Python with compiled language later
7. **Type-safe** — Schema validation throughout
8. **Clearer** — No magic, no nested conditionals

---

## Next Phase After 5c

**Phase 5d:** Custom Program Schemas
- User-defined programs have their own schema
- Program schema integrated into main schema
- Program modules follow same section module pattern
- Step generation for user programs is schema-driven

**Phase 6:** Compiled Language Migration (Optional)
- Lua schema and section modules unchanged
- Replace Python with Go/Rust/C
- Compiled code reads Lua schema and composes sections
- All business logic stays in Lua
