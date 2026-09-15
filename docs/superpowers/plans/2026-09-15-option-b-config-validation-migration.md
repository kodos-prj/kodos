# Option B Migration — Config Validation to Lua Schema

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move config validation from Python (591 lines) to Lua schema-driven validation, reducing Python to pure orchestration/execution layer.

**Architecture:** 
Replace `src/kod/config/validator.py` with Lua schema-driven validation. The Lua schema (`lib/schema.lua`) already exists and drives the step emission; validation should be co-located. Move Python validation logic into schema-based checks in Lua, keeping Python as a simple validation orchestrator that calls into Lua.

**Tech Stack:** Python 3.11+, Lua 5.1+, lupa runtime, pytest

**Spec:** 
- `docs/superpowers/specs/2026-09-13-option-b-fat-lua-design.md` — Option B vision (remove command verbs from Python)
- This plan focuses on validation consolidation as a stepping stone to full Option B

---

## Global Constraints

- **Minimum test pass rate:** 700+ (current baseline)
- **No behavioral changes:** Validation logic moves, not changes
- **No new dependencies:** Lua already available via lupa
- **Python only orchestrates:** validator.py becomes thin wrapper calling Lua validation
- **Git discipline:** One focused commit per task

---

## File Structure

### Current Layout (Validation in Python)
```
src/kod/
├── config/
│   ├── validator.py          # 591 lines — validation logic (to move)
│   ├── loader.py             # 341 lines — loads config from Lua
│   └── compiler.py           # 260 lines — compiles steps
├── lib/
│   └── schema.lua            # 806 lines — schema + validation rules (to extend)
└── bootstrap.py              # calls validator.py
```

### After Migration (Validation in Lua)
```
src/kod/
├── config/
│   ├── validator.py          # ~50 lines — thin orchestrator (calls Lua)
│   ├── loader.py             # 341 lines — unchanged
│   └── compiler.py           # 260 lines — unchanged
├── lib/
│   ├── schema.lua            # ~1200 lines — schema + validation (consolidated)
│   └── validation.lua        # ~300 lines — validation helper functions
└── bootstrap.py              # calls validator.py (unchanged)
```

---

## Task Breakdown

### Task 1: Audit Current Validation Logic in validator.py

**Files:**
- Read: `src/kod/config/validator.py` (591 lines)
- Read: `src/kod/lib/schema.lua` (806 lines)
- Read: `tests/config/test_validator.py` (existing tests)

**Interfaces:**
- Consumes: Nothing (setup only)
- Produces: Mapping of validation rules to Lua schema equivalents

**Steps:**

- [ ] **Step 1: Read validator.py and categorize validations**

Scan `src/kod/config/validator.py` and list:
1. Block-level validations (e.g., "boot block must have device")
2. Field-level validations (e.g., "service.enable must be boolean")
3. Cross-field validations (e.g., "if desktop, then display_manager required")
4. Distro-specific validations (e.g., "arch uses pacman")
5. Type validations (already in schema.lua)

Create a checklist document.

- [ ] **Step 2: Read schema.lua to see what validation already exists**

Review `src/kod/lib/schema.lua` and note:
- Which validations are already schema-based (type, format, required)
- Which validations are missing (cross-field, conditional)
- Patterns used for validation (e.g., assertions, error functions)

- [ ] **Step 3: Map validator.py logic to schema.lua equivalents**

For each validation in validator.py, determine:
- Is it already in schema.lua? (no work needed)
- Can it move to schema as a constraint? (relatively easy)
- Does it need Lua validation helper? (requires new code)

Document this mapping as the basis for Task 2.

---

### Task 2: Extend schema.lua with Validation Rules

**Files:**
- Modify: `src/kod/lib/schema.lua`
- Create: `src/kod/lib/validation.lua` (new)
- Test: `tests/test_lua_schema.lua` (existing, may extend)

**Interfaces:**
- Consumes: Mapping from Task 1
- Produces: `validate_config(config, schema) → (bool, errors[])`

**Steps:**

- [ ] **Step 1: Create validation.lua helper functions**

Create `src/kod/lib/validation.lua`:

```lua
-- Validation helper functions for schema-based checks

local validation = {}

-- Check that a required field exists in a block
function validation.require_field(config_block, field_name, block_type)
    if not config_block[field_name] then
        error(string.format(
            "Block '%s' missing required field '%s'",
            block_type, field_name
        ))
    end
end

-- Check that a field is one of allowed values
function validation.enum_field(value, allowed_values, field_name)
    for _, allowed in ipairs(allowed_values) do
        if value == allowed then
            return true
        end
    end
    error(string.format(
        "Field '%s' = '%s' not in allowed values: %s",
        field_name, value, table.concat(allowed_values, ", ")
    ))
end

-- Check cross-field constraint (if X then Y required)
function validation.conditional_require(config_block, condition_field, required_field, block_type)
    if config_block[condition_field] and not config_block[required_field] then
        error(string.format(
            "Block '%s': if %s is set, %s is required",
            block_type, condition_field, required_field
        ))
    end
end

-- Add more helpers as needed per Task 1 mapping

return validation
```

- [ ] **Step 2: Extend schema.lua with validation rules**

In `src/kod/lib/schema.lua`, add validation rules for each block type:

```lua
-- At module level in schema.lua, add validators
local validation = require("validation")

-- Boot block validation
function schema.validate_boot(boot_block)
    if boot_block then
        validation.require_field(boot_block, "device", "boot")
        -- ... other rules
    end
end

-- Users block validation
function schema.validate_users(users_table)
    if users_table then
        for user_name, user_config in pairs(users_table) do
            if user_config.enable then
                -- conditional rules for enabled users
            end
        end
    end
end

-- Add validators for all block types
```

- [ ] **Step 3: Create master validator function in schema.lua**

```lua
-- Master validation function
function schema.validate_all(config)
    local errors = {}
    
    pcall(function() schema.validate_boot(config.boot) end, 
        function(err) table.insert(errors, err) end)
    pcall(function() schema.validate_users(config.users) end,
        function(err) table.insert(errors, err) end)
    -- ... call validators for all blocks
    
    if #errors > 0 then
        return false, errors
    end
    return true, {}
end
```

- [ ] **Step 4: Run existing tests to ensure no regression**

```bash
cd /home/abuss/Work/devel/analysis/kodos
PYTHONPATH=src python -m pytest tests/config/test_validator.py -xvs
```

Expected: All tests pass (no behavior change yet)

---

### Task 3: Create Thin Python Validator Orchestrator

**Files:**
- Modify: `src/kod/config/validator.py` (reduce from 591 to ~50 lines)
- Test: `tests/config/test_validator.py` (update imports, same tests)

**Interfaces:**
- Consumes: Lua schema validation from Task 2
- Produces: Same `validate_config(config)` function signature

**Steps:**

- [ ] **Step 1: Understand current validator.py interface**

Read the public API of validator.py:
- What functions are called from outside? (grep: `from kod.config.validator import`)
- What is the function signature of validate? (return type, exceptions)
- What do callers expect? (list of errors, exception on fail, return bool)

Example expected signatures:
```python
def validate_config(config: dict) -> bool:
    """Returns True if valid, raises ConfigError if not."""
    
def validate_config_with_errors(config: dict) -> tuple[bool, list[str]]:
    """Returns (bool, list of error strings)."""
```

- [ ] **Step 2: Create new thin validator that calls Lua**

Replace most of validator.py with:

```python
"""Config validation orchestrator.

Validation logic has moved to Lua schema (src/kod/lib/schema.lua).
This module is a thin wrapper that calls Lua validation.
"""

from typing import Dict, List, Any

def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration against Lua schema.
    
    Args:
        config: The configuration dict (loaded from Lua)
        
    Returns:
        True if valid
        
    Raises:
        ConfigError: If validation fails
    """
    from kod.lua_runtime import get_lua_runtime
    
    luart = get_lua_runtime()
    
    # Call Lua validation
    schema = luart.eval("require('schema')")
    success, errors = schema.validate_all(config)
    
    if not success:
        error_msg = "\n".join(errors)
        raise ConfigError(f"Config validation failed:\n{error_msg}")
    
    return True


class ConfigError(Exception):
    """Configuration validation error."""
    pass
```

- [ ] **Step 3: Delete old Python validation logic**

Remove from validator.py:
- All block-specific validation functions (already in Lua now)
- Helper functions for validation (moved to validation.lua)
- Type checking (schema.lua handles via schema)

Keep only:
- Public API (`validate_config`)
- Error classes
- Comments documenting the Lua delegation

- [ ] **Step 4: Update imports in bootstrap.py**

If bootstrap.py imports specific validators, update to just use `validate_config`:

```python
# Old
from kod.config.validator import validate_boot, validate_users, validate_config

# New
from kod.config.validator import validate_config
```

- [ ] **Step 5: Run tests to verify**

```bash
cd /home/abuss/Work/devel/analysis/kodos
PYTHONPATH=src python -m pytest tests/config/test_validator.py -xvs
```

Expected: All tests pass (same validation, different location)

- [ ] **Step 6: Run full test suite**

```bash
PYTHONPATH=src python -m pytest tests/ -q
```

Expected: 700+ passing (no regressions)

- [ ] **Step 7: Commit**

```bash
git add src/kod/config/validator.py src/kod/lib/schema.lua src/kod/lib/validation.lua
git commit -m "refactor(config): move validation from Python to Lua schema

- Move 550+ lines of validation logic from validator.py to Lua
- Create validation.lua with helper functions for schema checks
- Extend schema.lua with block-level and cross-field validators
- Replace validator.py with thin orchestrator calling Lua
- No behavior change, all 700+ tests pass"
```

---

## Verification Checklist

After all tasks:

- [ ] Run full test suite: `pytest tests/ -q` (expect 700+ pass)
- [ ] Verify validator.py is ~50 lines (from 591)
- [ ] Check schema.lua now has validation rules
- [ ] Confirm validation.lua exists with helper functions
- [ ] Spot check: Edit a config field, verify validation still catches errors

---

## Rollback Plan

If validation breaks:
1. `git revert` the commit
2. Validator.py returns to 591 lines
3. All Lua changes are rolled back
4. Tests revert to passing state

---

## Success Criteria

✅ **Code Migration:**
- validator.py reduces from 591 → 50 lines (88% reduction)
- Lua validation rules consolidated in schema.lua + validation.lua
- No behavioral changes (same validation, different place)

✅ **Testing:**
- 700+ tests still passing
- No regressions in config validation tests
- All edge cases handled by Lua schema validators

✅ **Architecture Improvement:**
- Python now only orchestrates
- Lua owns all config knowledge and rules
- Clear boundary: Python executes, Lua plans + validates

---

## Plan Completion & Execution

This plan is ready for execution. 

**Next steps after approval:**

1. **Execute inline** (all 3 tasks in this session)
   - Task 1: Audit & categorize (~15 min)
   - Task 2: Extend Lua schema (~45 min)
   - Task 3: Thin Python wrapper (~30 min)
   - Total: ~90 min

2. **Or delegate to subagent** for careful execution with review checkpoints

**Recommendation:** Inline execution (it's straightforward, spec is clear, low risk).
