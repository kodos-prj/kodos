# Task 3: Refactor Planner to Schema-Driven Composition

## Requirement

Refactor the planner from nested-conditional orchestrator to a simple schema-driven composer that:
1. Loads all 13 section modules
2. Iterates through configuration sections
3. Calls each section's `emit_steps(config[section], distro)` function
4. Collects and orders all steps

## Current State

The planner currently lives in `src/kod/lib/planner.lua` (or similar) and has ~600+ lines of hardcoded conditional logic for each section:

```lua
-- OLD: Nested conditionals for each section
if config.boot then
    if config.boot.kernel then
        -- emit kernel steps
    end
    if config.boot.loader then
        -- emit bootloader steps
    end
end

if config.hardware then
    if config.hardware.pipewire then
        -- emit pipewire steps
    end
end

-- ... 20+ more sections with similar nesting
```

## Target Implementation

```lua
-- NEW: Simple composer
local Planner = {}

function Planner:compose(config, distro)
    local sections = {
        'base_distribution', 'repos', 'devices', 'boot', 'hardware',
        'locale', 'network', 'users', 'desktop', 'fonts',
        'packages', 'services', 'programs'
    }
    
    local steps = {}
    
    for _, section_name in ipairs(sections) do
        if config[section_name] then
            local section = require('kod.sections.' .. section_name)
            local section_steps = section.emit_steps(config[section_name], distro)
            for _, step in ipairs(section_steps) do
                table.insert(steps, step)
            end
        end
    end
    
    -- Sort by order field (if present)
    table.sort(steps, function(a, b)
        return (a.order or 0) < (b.order or 0)
    end)
    
    return steps
end

return Planner
```

**Lines reduced:** 600+ → ~50 lines (90% reduction!)

## File to Refactor

**`src/kod/lib/planner.lua`** (REFACTOR or CREATE if new)

If the planner doesn't exist yet, create it. If it exists, replace the old logic with the new compose() function.

## Implementation Details

### 1. Module Loading
- Lazy-load each section module as needed
- Cache loaded modules to avoid repeated requires
- Handle missing modules gracefully

### 2. Step Ordering
- Collect all steps from all sections
- Sort by `order` field (default 0)
- Respect dependency ordering (if Step has `depends_on`, ensure dependencies come first)

### 3. Distro Awareness
- Pass distro to each section's emit_steps()
- Sections handle distro-specific logic internally
- Planner doesn't need to know distro-specific details

### 4. Configuration Validation
- Accept config table from bootstrap
- Validate required fields (at least base_distribution) before composing
- Return error if validation fails

### 5. Error Handling
- Handle missing section modules gracefully
- Handle nil/empty config sections
- Return meaningful error messages for debugging

## Public API

```lua
local Planner = require('kod.lib.planner')

-- Main entry point: compose a list of steps
-- @param config Table with configuration
-- @param distro String 'arch' or 'debian'
-- @return Table array of Step objects
-- @return String error message if failed
local steps, err = Planner:compose(config, distro)
if err then
    print("Error: " .. err)
    return
end

print("Generated " .. #steps .. " steps")
for i, step in ipairs(steps) do
    print(i .. ": " .. step.name .. " - " .. step.description)
end
```

## Step Object Format (Reference)

```lua
{
    name = "step_id",
    description = "Human readable",
    command = "shell command or lua code",
    on_distro = "arch" or "debian" or nil,  -- if nil, applies to both
    order = 100,                            -- sort order
    depends_on = {"other_step"},            -- optional dependencies
}
```

## Testing

Add tests in `tests/lua/test_planner.lua`:

```lua
-- Test planner loads all section modules
-- Test compose() returns step array
-- Test step ordering works
-- Test distro-aware composition (arch vs debian)
-- Test missing config sections are skipped
-- Test required fields validation
-- Test error handling for invalid config
-- Test compose with empty config (only base_distribution)
-- Test compose with full config
```

Also ensure Python integration tests pass:
- `tests/test_bootstrap.py` — planner is called from bootstrap

## Success Criteria

✅ Old nested-conditional logic removed  
✅ New composer loads all 13 section modules  
✅ All steps collected and sorted correctly  
✅ Distro-aware (arch vs debian)  
✅ Planner interface clean and simple  
✅ All 541+ existing tests pass  
✅ 20+ new planner tests pass  
✅ 90% code reduction (600+ lines → ~100 lines)  
✅ Error handling works  
✅ Planner can be tested independently  

## Integration Points

- **Input:** Config table from bootstrap (Python)
- **Output:** Array of Step objects
- **Usage:** Bootstrap calls `Planner:compose(config, distro)` to get steps
- **Sections:** Loads all 13 section modules (Task 2, completed)
- **Next:** Bootstrap integration (Task 4) will use this planner

## File Size Expectation

**~100-150 lines** of clean, readable Lua code (down from 600+).

## Notes

- **This is the core of Phase 5c:** transforming nested conditionals into compositional design
- Keep it simple and readable
- Don't add unnecessary abstractions
- Sections handle all the complexity; planner is just a simple iterator
- The planner should be testable without needing the full bootstrap
- Consider caching section modules (avoid repeated requires)
- Make sure step ordering is predictable (tie-breaking for same order values)

## Example Walkthrough

```lua
local config = {
    base_distribution = "arch",
    packages = {"git", "vim"},
    boot = {
        kernel = {package = "linux"}
    }
}

local steps = Planner:compose(config, "arch")

-- Expected: steps from:
-- 1. base_distribution section (none)
-- 2. packages section (install git, vim)
-- 3. boot section (install linux kernel)
-- Total: 2-3 steps in predictable order
```

## Related

- Schema: `src/kod/lib/schema.lua` (Task 1, completed)
- Section modules: `src/kod/sections/*.lua` (Task 2, completed)
- Bootstrap: `src/kod/bootstrap.py` (Task 4, upcoming — will call planner)
