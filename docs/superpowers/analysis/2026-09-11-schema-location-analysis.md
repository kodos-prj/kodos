# Schema Location Analysis: Python vs Lua

## Current State (Phase 5b)

**Schema in Python:**
- `SCHEMA` dict (types only)
- `SECTION_HELP` dict (descriptions, examples, validation rules)
- Validator uses these to check configs
- CLI commands export as JSON

**Problem you've identified:**
Lua programs (bootstrap modules, custom programs) don't have access to schema. They generate steps without knowing:
- What fields are optional vs required
- What types are expected
- Default values
- Field descriptions

This means each Lua module duplicates validation logic or skips it entirely.

---

## Option 1: Python Schema Only (Current Phase 5b)

**Pros:**
- Single source of truth
- Easier to keep in sync
- CLI can validate before sending to Lua
- Validation happens early in Python

**Cons:**
- Lua modules can't emit conditional steps based on schema
- Lua modules can't validate their own config against schema
- No way for Lua to know "this field is optional" without hardcoding
- Custom Lua programs need to re-document schema

**Example problem:**
```lua
-- bootstrap.lua has no way to know if boot.kernel is optional
-- So it blindly accesses it, or checks existence manually
if config.boot and config.boot.kernel then
  -- emit kernel steps
end
```

---

## Option 2: Schema in Lua Only

**Pros:**
- Lua can emit steps based on schema
- Bootstrap modules can validate their config
- Custom programs can check schema for their fields
- Single source of truth (Lua)

**Cons:**
- Python CLI can't validate without calling Lua
- Slower validation (Lua interpreter startup cost)
- Harder to integrate with Click for error messages
- Schema becomes executable code (less declarative)

**Example:**
```lua
-- schema.lua (Lua)
local SCHEMA = {
  boot = {
    type = "dict",
    fields = {
      kernel = { type = "dict", required = false },
      loader = { type = "dict", required = false }
    }
  }
}
```

---

## Option 3: Dual Schema (Split)

**Best of both worlds:**

### Python Schema (Declarative)
```python
# src/kod/config/schema.py
SECTION_HELP = {
    "boot": {
        "description": "...",
        "type": "dict",
        "fields": {
            "kernel": {
                "type": "dict",
                "required": False,
                "fields": {...}
            }
        }
    }
}
```

### Lua Schema (Executable)
```lua
-- src/kod/lib/schema.lua (generated from Python or hand-mirrored)
local SCHEMA = {
  boot = {
    type = "dict",
    optional = true,
    fields = {
      kernel = { type = "dict", optional = true },
      loader = { type = "dict", optional = true }
    }
  }
}

function validate_field(section, field_path, value)
  -- Lua can validate during step emission
end

return { SCHEMA = SCHEMA, validate_field = validate_field }
```

**Implementation:**
1. Define schema in Python (single declarative source)
2. Generate Lua schema from Python at build time or runtime
3. Python uses Python schema for CLI validation
4. Lua loads schema and uses it for step emission

---

## Where Schema Should Live (Recommendation)

### For **Validation & CLI** → Python
- `kod config validate` runs Python validation
- `kod config schema` displays from Python
- Early error feedback before Lua

### For **Step Emission** → Lua
- Bootstrap modules know what fields are optional
- Custom programs can access schema
- Conditional step generation based on config structure

### Implementation Strategy

```
┌─────────────────────────────────────────────────────┐
│ Python: SECTION_HELP (source of truth)              │
│ - Descriptions, examples, validation rules          │
│ - Used by CLI and validator                         │
└─────────────────────────────────────────────────────┘
                        │
                        ↓ (generate or load at runtime)
┌─────────────────────────────────────────────────────┐
│ Lua: schema.lua (generated or mirrored)             │
│ - Type info, required/optional flags                │
│ - Used by bootstrap, programs for step emission     │
│ - Can call validation functions during emission     │
└─────────────────────────────────────────────────────┘
```

---

## Specific Question: Should Bootstrap Know Schema?

**Current bootstrap.py (Python):**
```python
def emit_bootstrap_steps(config, distro):
    kernel_steps = []
    if config.get("boot") and config["boot"].get("kernel"):
        # emit kernel steps
    return kernel_steps
```

**Proposed (with Lua schema access):**
```lua
-- bootstrap-arch.lua
local schema = require("schema")

function emit_bootstrap_steps(config)
    local steps = {}
    
    -- Schema tells us boot.kernel is optional
    if config.boot and config.boot.kernel then
        -- Safe to access because schema says it's optional
        table.insert(steps, emit_kernel_steps(config.boot.kernel))
    end
    
    return steps
end
```

**Or even better:**
```lua
-- bootstrap-arch.lua
local schema = require("schema")

function emit_bootstrap_steps(config)
    local steps = {}
    
    -- Schema knows boot.kernel is optional
    local boot_schema = schema.SCHEMA.boot
    if boot_schema.fields.kernel and config.boot and config.boot.kernel then
        table.insert(steps, emit_kernel_steps(config.boot.kernel))
    end
    
    return steps
end
```

This way:
- If schema changes (boot.kernel becomes required), bootstrap adapts
- No magic strings or hardcoded assumptions
- Schema is the source of truth for both Python and Lua

---

## Proposal: Hybrid Approach (Recommended)

### Phase 5b (Already Done)
- Schema in Python `SECTION_HELP` ✅
- Python validation works ✅
- CLI commands work ✅

### Phase 5c (New)
- **Generate or load Lua schema** at runtime
  ```python
  def load_lua_schema():
      """Convert Python SECTION_HELP to Lua table and load into runtime."""
      lua_schema = convert_section_help_to_lua(SECTION_HELP)
      lua_runtime.execute(f"SCHEMA = {lua_schema}")
  ```
  
- **Update bootstrap.py** to use Lua schema
  ```python
  def emit_bootstrap_steps(config, distro):
      """Call bootstrap module, which can now use schema."""
      lua_runtime.execute("""
          local bootstrap = require('bootstrap-{distro}')
          return bootstrap.emit_bootstrap_steps(config)
      """)
  ```

- **Update bootstrap modules** to reference schema
  ```lua
  -- bootstrap-arch.lua
  local schema = require("schema")
  
  function emit_bootstrap_steps(config)
      local steps = {}
      if schema.has_field(config, "boot.kernel") then
          -- Safe to emit kernel steps
      end
      return steps
  end
  ```

---

## Benefits of Hybrid Approach

1. **Single source of truth** — Python SECTION_HELP is the canonical schema
2. **Python gets fast validation** — No Lua interpreter overhead
3. **Lua gets schema awareness** — Can emit smarter, safer steps
4. **Maintainability** — One schema definition, two implementations
5. **Extensibility** — Custom Lua programs can access schema
6. **Backward compatible** — No changes to Phase 5b, additive only

---

## Action Items

### Current (Phase 5b Complete)
- ✅ Python schema in place
- ✅ Python validation working
- ✅ CLI commands working

### Next (Phase 5c: Schema-Aware Step Emission)
- [ ] Create `src/kod/lib/schema.lua` (generated from Python)
- [ ] Add function to load schema into Lua runtime
- [ ] Update `bootstrap.py` to load schema before calling Lua
- [ ] Update bootstrap modules to use schema
- [ ] Update planner to call bootstrap with schema available
- [ ] Tests to verify schema is accessible in Lua

### Benefit
Bootstrap modules can then:
- Know which fields are optional without hardcoding
- Validate field types before emitting steps
- Emit conditional steps based on schema
- Support schema changes without code changes

---

## Decision

**Should schema be in Lua?** 

Yes, but **not instead of Python**—**in addition to Python**.

- **Python schema** = declarative source of truth
- **Lua schema** = executable version for step emission

This way:
- Config validation is fast (Python)
- Step emission is smart (Lua with schema awareness)
- Schema is maintained once, used everywhere
- Lua programs are self-documenting ("this field is optional per schema")
