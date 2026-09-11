# Task 2: Create Lua Section Modules (13 Modules)

## Requirement

Create 13 Lua section modules in `src/kod/sections/` that implement schema-driven step emission. Each module owns its section of the configuration schema and generates boot steps.

## File to Create

Create one file per section:
- `src/kod/sections/base_distribution.lua`
- `src/kod/sections/repos.lua`
- `src/kod/sections/devices.lua`
- `src/kod/sections/boot.lua`
- `src/kod/sections/hardware.lua`
- `src/kod/sections/locale.lua`
- `src/kod/sections/network.lua`
- `src/kod/sections/users.lua`
- `src/kod/sections/desktop.lua`
- `src/kod/sections/fonts.lua`
- `src/kod/sections/packages.lua`
- `src/kod/sections/services.lua`
- `src/kod/sections/programs.lua`

**Directory:** Create `src/kod/sections/` if it doesn't exist.

## Module Structure

Each section module must follow this pattern:

```lua
local Schema = require('kod.lib.schema')

local module = {
    -- Reference to this section's schema
    schema = Schema.SECTION_NAME,
    
    -- Generate boot steps from config
    -- @param config Table with this section's configuration (may be nil)
    -- @param distro String base distribution ('arch' or 'debian')
    -- @return Table of Step objects (see below)
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Generate steps based on config and distro
        -- Each step: {name = "...", description = "...", command = "...", ...}
        
        return steps
    end
}

return module
```

## Step Object Format

Each step returned by emit_steps() should have:

```lua
{
    name = "step_identifier",           -- unique ID (e.g., "boot_kernel_install")
    description = "Human readable description",
    command = "shell command or lua code",
    on_distro = "arch" or "debian" or nil,  -- nil = both
    order = 100,                        -- sort order (optional)
    depends_on = {"other_step"},        -- dependencies (optional)
}
```

## Implementation Details

### 1. base_distribution (SIMPLE)
- Validate and store distribution choice (arch/debian)
- No steps generated (validation only)
- Used by other sections to decide distro-specific behavior

### 2. repos (DYNAMIC)
- Iterate config.repos (dynamic keys per distro)
- Call repos.add_DISTRO() for each repo
- Generate appropriate package manager commands

### 3. devices (DYNAMIC)
- Iterate config.devices (disk definitions)
- Call device.DISK_NAME() functions
- Generate partition/mount steps

### 4. boot (CONDITIONAL)
- Check config.boot.kernel (kernel package, modules)
- Check config.boot.loader (bootloader type, timeout)
- Generate install/config steps

### 5. hardware (CONDITIONAL)
- Check config.hardware.pipewire.enable
- Generate pipewire install + config steps

### 6. locale (CONDITIONAL)
- Check config.locale.locale (default, extra)
- Check config.locale.timezone
- Check config.locale.keymap
- Generate locale-gen, timezone symlink, keymap steps

### 7. network (CONDITIONAL)
- Check config.network.hostname
- Check config.network.ipv6
- Generate hostname + network config steps

### 8. users (DYNAMIC)
- Iterate config.users (USERNAME is dynamic key)
- For each user: shell, groups, home_programs
- Generate useradd, usermod, home setup steps

### 9. desktop (CONDITIONAL)
- Check config.desktop.environment
- Check config.desktop.enable
- Generate DE install + default packages steps

### 10. fonts (CONDITIONAL)
- Check config.fonts.monospace/sans_serif/emoji lists
- Check config.fonts.enable
- Generate font package install steps

### 11. packages (SIMPLE LIST)
- Iterate config.packages (list of package names)
- Generate install step for all packages

### 12. services (DYNAMIC)
- Iterate config.services (SERVICE_NAME is dynamic key)
- For each service: enable, start booleans
- Generate systemctl enable/start steps

### 13. programs (DYNAMIC)
- Iterate config.programs (PROGRAM_NAME is dynamic key)
- Call programs.PROGRAM_NAME.install(config) if defined
- Generate custom program install steps

## Success Criteria

✅ All 13 modules created  
✅ Each module has schema reference  
✅ Each module has emit_steps() function  
✅ emit_steps() returns Step array  
✅ Handles missing config gracefully (returns empty steps)  
✅ All modules can be loaded (no syntax errors)  
✅ No hardcoded planner logic (each section is independent)  
✅ Distro-aware step generation (arch vs debian)  
✅ All 541+ tests still pass  

## File Size Expectation

- Simple modules (base_distribution, packages): 30-50 lines each
- Conditional modules (boot, hardware, locale, network, desktop, fonts): 80-150 lines each
- Dynamic modules (repos, devices, users, services, programs): 100-200 lines each
- **Total: ~1,200-1,500 lines across 13 files**

## Notes

- These modules are **completely independent** — no module calls another
- The **planner** (Task 3) just iterates sections and calls emit_steps()
- Step generation follows the flow from current Python planner
- Use distro to decide arch vs debian specific commands
- Dynamic sections (repos, devices, users, services, programs) need helper functions in the config itself (those are created by DSL, not by these modules)
- Import Schema to reference section definitions for validation
- Keep each module under 200 lines (split if needed)

## Testing

Add tests in `tests/lua/test_sections.lua`:

```lua
-- Test each section loads
-- Test emit_steps() works with valid config
-- Test emit_steps() works with nil config
-- Test step format is valid
-- Test distro-specific steps
-- Test dynamic key handling (users, services, programs)
```

Also add integration test in `tests/lua/test_composition.lua`:

```lua
-- Load all 13 sections
-- Call all emit_steps() in sequence
-- Verify total step count is reasonable
-- Verify no duplicate step names
-- Verify dependencies make sense
```

## Related

- Schema: `src/kod/lib/schema.lua` (Task 1, completed)
- Planner: `src/kod/lib/planner.lua` (Task 3, upcoming — will iterate these modules)
- Bootstrap: `src/kod/bootstrap.py` (Task 4, upcoming — will use planner)
