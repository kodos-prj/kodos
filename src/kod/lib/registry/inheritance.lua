-- Registry Inheritance: Program merging and inheritance logic
--
-- Responsibilities:
-- - Resolve program inheritance chains (follow _extends field)
-- - Detect circular inheritance
-- - Merge builtin + user program definitions
-- - Validate program schemas
-- - Load programs from registry.loader
--
-- All functions return (result, error_msg) tuples where:
--   - result: the actual value on success, nil on failure
--   - error_msg: nil on success, error string on failure

local inheritance = {}

-- Load the loader module (assumes it's at same level)
local loader = require("lib.registry.loader")

-- ============================================================================
-- Circular Inheritance Detection
-- ============================================================================

--- Check if program name is in visited set
-- @param name string - program name
-- @param visited table - set of visited program names {name: true}
-- @return boolean true if already visited
local function _is_visited(name, visited)
    if not visited then return false end
    return visited[name] == true
end

--- Detect circular inheritance in a single program's _extends chain
-- @param program_name string - program to check
-- @param visited table - set of visited names {name: true}
-- @return boolean, nil on success; nil, error_msg if circular
local function _detect_circular(program_name, visited)
    if not visited then visited = {} end
    
    if _is_visited(program_name, visited) then
        return nil, "Circular inheritance detected: " .. program_name .. " extends itself"
    end
    
    visited[program_name] = true
    return true, nil
end

-- ============================================================================
-- Program Resolution
-- ============================================================================

--- Resolve a program's inheritance chain, loading parents as needed
-- Returns the fully merged program definition
-- This is the main entry point for loading a program
--
-- @param program_name string - name of program to load (e.g., "git")
-- @param builtin_programs table - {name: path} dict of builtin programs
-- @param user_programs table - {name: path} dict of user programs
-- @param visited table - set of visited program names (for circular detection)
-- @return table merged_program_def, nil on success; nil, error_msg on failure
function inheritance.resolve_program(program_name, builtin_programs, user_programs, visited)
    if not visited then visited = {} end
    
    -- Check for circular inheritance
    local ok, err = _detect_circular(program_name, visited)
    if not ok then
        return nil, err
    end
    
    -- Check caches first (avoid reloading)
    local cached_user = loader.get_user_cache(program_name)
    if cached_user then
        return cached_user, nil
    end
    
    local cached_builtin = loader.get_builtin_cache(program_name)
    if cached_builtin then
        return cached_builtin, nil
    end
    
    -- Load builtin and user definitions
    local builtin_def = nil
    local user_def = nil
    
    if builtin_programs[program_name] then
        builtin_def, err = loader.load_program_file(builtin_programs[program_name])
        if not builtin_def then
            return nil, err
        end
        loader.set_builtin_cache(program_name, builtin_def)
    end
    
    if user_programs[program_name] then
        user_def, err = loader.load_program_file(user_programs[program_name])
        if not user_def then
            return nil, err
        end
    end
    
    -- Handle different combinations
    if builtin_def and user_def then
        -- Both exist: user must extend builtin
        if not user_def._extends then
            return nil, "Program '" .. program_name .. "' has both builtin and user definitions, " ..
                        "but user doesn't extend builtin. Add '_extends: \"" .. program_name .. "\"' to user."
        end
        
        if user_def._extends ~= program_name then
            return nil, "Program '" .. program_name .. "' user extends '" .. user_def._extends ..
                        "', not itself."
        end
        
        -- Merge: start with builtin, apply user overrides
        local merged = inheritance._merge_defs(builtin_def, user_def)
        loader.set_user_cache(program_name, merged)
        return merged, nil
        
    elseif user_def then
        -- Only user exists
        if user_def._extends then
            -- User extends something; load parent
            local parent_name = user_def._extends
            if parent_name == program_name then
                return nil, "Program '" .. program_name .. "' user tries to extend itself"
            end
            
            local parent_def, err = inheritance.resolve_program(parent_name, builtin_programs, user_programs, visited)
            if not parent_def then
                return nil, err
            end
            
            local merged = inheritance._merge_defs(parent_def, user_def)
            loader.set_user_cache(program_name, merged)
            return merged, nil
        else
            -- Standalone user program
            loader.set_user_cache(program_name, user_def)
            return user_def, nil
        end
        
    elseif builtin_def then
        -- Only builtin exists
        if builtin_def._extends then
            -- Builtin extends something; load parent
            local parent_name = builtin_def._extends
            if parent_name == program_name then
                return nil, "Program '" .. program_name .. "' tries to extend itself"
            end
            
            local parent_def, err = inheritance.resolve_program(parent_name, builtin_programs, user_programs, visited)
            if not parent_def then
                return nil, err
            end
            
            local merged = inheritance._merge_defs(parent_def, builtin_def)
            return merged, nil
        else
            -- Standalone builtin program
            return builtin_def, nil
        end
        
    else
        -- Neither builtin nor user exists
        return nil, "Program '" .. program_name .. "' not found in builtin or user plugins"
    end
end

-- ============================================================================
-- Program Merging
-- ============================================================================

--- Merge two program definitions (parent + child)
-- Child fields override parent fields
-- Sensitive merging for special fields (scope, services, etc.)
--
-- @param parent_def table - parent program definition
-- @param child_def table - child program definition (overrides parent)
-- @return table merged definition
--- Recursively merge two tables (child overrides parent)
local function _deep_merge_tables(parent, child)
    local result = {}
    
    -- Copy parent
    for k, v in pairs(parent) do
        if type(v) == "table" then
            result[k] = {}
            for pk, pv in pairs(v) do
                result[k][pk] = pv
            end
        else
            result[k] = v
        end
    end
    
    -- Merge child
    for k, v in pairs(child) do
        if type(v) == "table" and type(result[k]) == "table" then
            -- Recursively merge nested tables
            result[k] = _deep_merge_tables(result[k], v)
        else
            result[k] = v
        end
    end
    
    return result
end

function inheritance._merge_defs(parent_def, child_def)
    -- Start with parent copy
    local merged = {}
    for k, v in pairs(parent_def) do
        if k ~= "_extends" then  -- Skip _extends marker
            merged[k] = v
        end
    end
    
    -- Override with child fields
    for k, v in pairs(child_def) do
        if k ~= "_extends" then  -- Skip _extends marker
            if type(v) == "table" and type(merged[k]) == "table" then
                -- Deep merge for tables (child overrides parent)
                merged[k] = _deep_merge_tables(merged[k], v)
            else
                -- Scalar fields: child completely overrides parent
                merged[k] = v
            end
        end
    end
    
    return merged
end

--- Validate that a program definition is well-formed
-- @param program_def table - program definition to validate
-- @return boolean, nil on success; nil, error_msg on failure
function inheritance.validate_program_def(program_def)
    if type(program_def) ~= "table" then
        return nil, "Program definition must be a table"
    end
    
    -- Required fields: scope, schema
    if not program_def.scope then
        return nil, "Program definition missing required field: scope"
    end
    
    if program_def.scope ~= "system" and program_def.scope ~= "user" and program_def.scope ~= "both" then
        return nil, "Program scope must be 'system', 'user', or 'both', got: " .. program_def.scope
    end
    
    if not program_def.schema or type(program_def.schema) ~= "table" then
        return nil, "Program definition missing required field: schema (must be a table)"
    end
    
    -- Optional field: service (if present, scope must allow it)
    if program_def.service then
        if program_def.scope == "user" then
            return nil, "Program with scope 'user' cannot have a service definition"
        end
        
        if type(program_def.service) ~= "table" then
            return nil, "Service definition must be a table"
        end
        
        if not program_def.service.name then
            return nil, "Service definition missing required field: name"
        end
    end
    
    return true, nil
end

return inheritance
