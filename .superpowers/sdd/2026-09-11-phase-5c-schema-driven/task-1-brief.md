# Task 1: Define Configuration Schema in Lua

## Requirement

Create `src/kod/lib/schema.lua` — a complete Lua-based configuration schema that serves as the single source of truth for all configuration sections, replacing the Python SECTION_HELP dict.

## File to Create

**`src/kod/lib/schema.lua`** (NEW)

This is the canonical schema definition. All sections will reference it.

## Schema Structure

```lua
local Schema = {}

-- Each section definition follows this pattern:
-- {
--     type = "string" | "dict" | "list" | "number" | "boolean",
--     required = true | false,
--     description = "...",
--     enum = {...},           -- optional, for string types
--     default = ...,          -- optional, default value
--     fields = {              -- optional, for dict sections
--         field_name = {
--             type = "...",
--             required = false,
--             description = "...",
--             default = ...,
--             fields = {...}  -- optional, nested fields (max 3 levels)
--         }
--     }
-- }
```

## All 13 Sections to Define

1. **base_distribution** (string, required, enum: arch/debian)
2. **repos** (dict, optional, nested: repo identifiers)
3. **devices** (dict, optional, nested: disk identifiers)
4. **boot** (dict, optional, nested: kernel, loader with subfields)
5. **hardware** (dict, optional, nested: pipewire with enable/extra_packages)
6. **locale** (dict, optional, nested: locale/timezone/keymap)
7. **network** (dict, optional, nested: hostname, ipv6)
8. **users** (dict, optional, nested: USERNAME with shell/groups/home_programs)
9. **desktop** (dict, optional, nested: environment, enable)
10. **fonts** (dict, optional, nested: monospace/sans_serif/emoji/enable)
11. **packages** (list, optional, simple list of strings)
12. **services** (dict, optional, nested: SERVICE_NAME with enable/start)
13. **programs** (dict, optional, nested: PROGRAM_NAME with enable)

## Example: Complete boot Section

```lua
Schema.boot = {
    type = "dict",
    required = false,
    description = "Kernel and bootloader configuration (kernel version, modules, boot timeout)",
    
    fields = {
        kernel = {
            type = "dict",
            required = false,
            description = "Kernel package and loadable modules",
            
            fields = {
                package = {
                    type = "string",
                    required = false,
                    default = "linux",
                    description = "Kernel package name (e.g., 'linux', 'linux-lts', 'linux-hardened')"
                },
                modules = {
                    type = "list",
                    required = false,
                    description = "List of kernel modules to load at boot (for initramfs)"
                }
            }
        },
        
        loader = {
            type = "dict",
            required = false,
            description = "Bootloader configuration",
            
            fields = {
                type = {
                    type = "string",
                    required = false,
                    default = "systemd-boot",
                    enum = {"systemd-boot", "grub"},
                    description = "Bootloader type"
                },
                timeout = {
                    type = "number",
                    required = false,
                    default = 10,
                    description = "Boot menu timeout in seconds"
                }
            }
        }
    }
}
```

## Validation Functions

Add helper functions to schema.lua:

```lua
-- Validate field value against schema
function Schema:validate_field(schema_def, value)
    if not schema_def or not value then
        return true  -- Optional fields can be nil
    end
    
    -- Type check
    local lua_type = type(value)
    if schema_def.type == "dict" and lua_type ~= "table" then
        return false
    end
    if schema_def.type == "list" and lua_type ~= "table" then
        return false
    end
    if schema_def.type == "string" and lua_type ~= "string" then
        return false
    end
    if schema_def.type == "number" and lua_type ~= "number" then
        return false
    end
    if schema_def.type == "boolean" and lua_type ~= "boolean" then
        return false
    end
    
    -- Enum check
    if schema_def.enum then
        local valid = false
        for _, enum_val in ipairs(schema_def.enum) do
            if value == enum_val then
                valid = true
                break
            end
        end
        if not valid then return false end
    end
    
    -- Nested field validation
    if schema_def.fields and lua_type == "table" then
        for field_name, field_schema in pairs(schema_def.fields) do
            if field_schema.required and not value[field_name] then
                return false
            end
            if value[field_name] then
                if not self:validate_field(field_schema, value[field_name]) then
                    return false
                end
            end
        end
    end
    
    return true
end

-- Get default value for a field
function Schema:get_default(schema_def)
    if schema_def.default then
        return schema_def.default
    end
    if schema_def.type == "dict" then
        return {}
    end
    if schema_def.type == "list" then
        return {}
    end
    return nil
end
```

## Testing

Add tests in `tests/lua/test_schema.lua`:

```lua
-- Test that all 13 sections are defined
-- Test type validation works
-- Test enum validation works
-- Test nested field access works
-- Test required field checking
-- Test default value retrieval
```

Also add Python tests in `tests/test_lua_schema.py`:

```python
# Test schema can be loaded from Lua
# Test schema structure is valid
# Test all sections present
# Test validation functions callable
```

## Success Criteria

✅ All 13 sections defined in Lua  
✅ Each section has: type, required, description  
✅ Nested fields documented (3 levels max)  
✅ Examples/defaults provided where applicable  
✅ Validation functions work (type, enum, required)  
✅ Schema can be loaded from Python or Lua  
✅ All unit tests pass  
✅ No syntax errors in Lua  

## Notes

- This is the **single source of truth** for configuration schema
- All section modules (Task 2) will reference this schema
- Python validator (Task 5) will load this schema
- Keep descriptions clear and concise (single sentence or two)
- Use same descriptions as Phase 5b SECTION_HELP for consistency
- Enums should be arrays for easy iteration in validation
- Defaults should be reasonable (e.g., kernel="linux", timeout=10)

## File Size Expectation

Estimated 400-500 lines of well-commented Lua code.
