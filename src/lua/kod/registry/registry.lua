-- Unified Registry Module: Program discovery, loading, validation, generation
--
-- Consolidates loader.lua + inheritance.lua + new functions into single module
--
-- Responsibilities:
-- - Discover .lua files in builtin and user directories
-- - Load and parse .lua program definitions
-- - Resolve program inheritance chains (follow _extends field)
-- - Detect circular inheritance
-- - Merge builtin + user program definitions
-- - Validate program schemas and configs
-- - Generate config from programs
-- - Execute program hooks
-- - Extract service definitions
-- - Manage caching to avoid reloading
--
-- All functions return (result, error_msg) tuples where:
--   - result: the actual value on success, nil on failure
--   - error_msg: nil on success, error string on failure
--
-- This module does NOT throw Lua exceptions; it returns error tuples

local registry = {}

-- ============================================================================
-- File Discovery
-- ============================================================================

local _merged_cache = {}   -- {program_name: merged_program_def}

-- ============================================================================
-- File Discovery
-- ============================================================================

--- Discover all .lua files in a directory
-- Returns {name: path} dict where name is filename without .lua extension
-- @param dir string - directory path to scan
-- @return table {name: path}, nil on success; nil, error_msg on failure
local function _scan_directory(dir)
    local result = {}
    
    -- Try to load lfs (Lua File System) library
    local ok, lfs_or_error = pcall(require, "lfs")
    local lfs = ok and lfs_or_error or nil
    
    if lfs then
        -- Use lfs if available (more robust)
        for file in lfs.dir(dir) do
            if file ~= "." and file ~= ".." and file:match("%.lua$") then
                local name = file:sub(1, -5)  -- Remove .lua extension
                result[name] = dir .. "/" .. file
            end
        end
        return result, nil
    else
        -- lfs not available; return empty
        -- Python fallback will handle directory scanning
        return result, nil
    end
end

--- Discover builtin program .lua files
-- @param dir string - path to builtin directory
-- @return table {name: path}, nil on success; nil, error_msg on failure
function registry.discover_builtin(dir)
    return _scan_directory(dir)
end

--- Discover user plugin .lua files
-- @param dir string - path to user plugins directory
-- @return table {name: path}, nil on success; nil, error_msg on failure
function registry.discover_user_files(dir)
    return _scan_directory(dir)
end

-- ============================================================================
-- File Loading & Parsing
-- ============================================================================

--- Load and parse a single .lua program definition file
-- Executes the .lua file (which should return a table) and returns it
-- @param file_path string - path to .lua file
-- @return table program_def, nil on success; nil, error_msg on failure
function registry.load_program_file(file_path)
    -- Verify file exists
    local handle = io.open(file_path, "r")
    if not handle then
        return nil, "File not found: " .. file_path
    end
    handle:close()
    
    -- Try to load and execute the file
    local ok, result = pcall(function()
        return dofile(file_path)
    end)
    
    if not ok then
        -- Lua error occurred
        local error_msg = tostring(result)
        return nil, "Lua syntax error in " .. file_path .. ": " .. error_msg
    end
    
    if result == nil then
        return nil, "Program file " .. file_path .. " must return a table (got nil)"
    end
    
    if type(result) ~= "table" then
        return nil, "Program file " .. file_path .. " must return a table (got " .. type(result) .. ")"
    end
    
    return result, nil
end

-- ============================================================================
-- Caching
-- ============================================================================

function registry.get_merged_cache(name)
    return _merged_cache[name]
end

function registry.set_merged_cache(name, program_def)
    _merged_cache[name] = program_def
end

function registry.clear_cache()
    _merged_cache = {}
end

function registry.get_cache_info()
    return {
        merged = _merged_cache,
    }
end

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

--- Detect circular inheritance in a program's _extends chain
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
-- Table Merging & Deep Merge
-- ============================================================================

--- Deep merge two tables (parent into child)
-- Child values override parent values
-- @param parent table - parent definition
-- @param child table - child/override definition
-- @return table merged definition
local function _deep_merge_tables(parent, child)
    if type(parent) ~= "table" or type(child) ~= "table" then
        return child  -- Child overrides parent
    end
    
    local result = {}
    
    -- Copy all parent keys
    for k, v in pairs(parent) do
        result[k] = v
    end
    
    -- Override/add all child keys
    for k, v in pairs(child) do
        if type(result[k]) == "table" and type(v) == "table" then
            -- Recursively merge nested tables
            result[k] = _deep_merge_tables(result[k], v)
        else
            -- Child overrides parent
            result[k] = v
        end
    end
    
    return result
end

--- Merge two program definitions (builtin + user)
-- @param parent_def table - parent/builtin program definition
-- @param child_def table - child/user program definition
-- @return table merged definition
function registry._merge_defs(parent_def, child_def)
    return _deep_merge_tables(parent_def, child_def)
end

-- ============================================================================
-- Schema Merging (for inheritance)
-- ============================================================================

--- Merge two schemas using allOf pattern
-- @param parent_schema table - parent schema
-- @param child_schema table - child schema override
-- @return table merged schema with allOf
function registry.merge_schemas(parent_schema, child_schema)
    if not parent_schema then
        return child_schema
    end
    if not child_schema then
        return parent_schema
    end
    
    return {
        allOf = {parent_schema, child_schema}
    }
end

-- ============================================================================
-- Program Resolution & Loading
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
function registry.resolve_program(program_name, builtin_programs, user_programs, visited)
    if not visited then visited = {} end
    
    -- Check for circular inheritance
    local ok, err = _detect_circular(program_name, visited)
    if not ok then
        return nil, err
    end
    
    -- Check merged cache first (avoid reloading)
    local cached = registry.get_merged_cache(program_name)
    if cached then
        return cached, nil
    end
    
     -- Load builtin and user definitions
    local builtin_def = nil
    local user_def = nil
    
    if builtin_programs and builtin_programs[program_name] then
        local builtin_path = builtin_programs[program_name]
        builtin_def, err = registry.load_program_file(builtin_path)
        if not builtin_def then
            return nil, err
        end
    end
    
    if user_programs and user_programs[program_name] then
        local user_path = user_programs[program_name]
        user_def, err = registry.load_program_file(user_path)
        if not user_def then
            return nil, err
        end
    end
    
    -- Handle different combinations
    local merged = nil
    
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
        merged = registry._merge_defs(builtin_def, user_def)
        
    elseif user_def then
        -- Only user exists
        if user_def._extends then
            -- User extends something; load parent
            local parent_name = user_def._extends
            local parent_def, err2 = registry.resolve_program(parent_name, builtin_programs, user_programs, visited)
            if not parent_def then
                return nil, err2
            end
            -- Merge with parent
            merged = registry._merge_defs(parent_def, user_def)
        else
            -- User stands alone
            merged = user_def
        end
        
    elseif builtin_def then
        -- Only builtin exists
        if builtin_def._extends then
            -- Builtin extends something; load parent
            local parent_name = builtin_def._extends
            local parent_def, err2 = registry.resolve_program(parent_name, builtin_programs, user_programs, visited)
            if not parent_def then
                return nil, err2
            end
            -- Merge with parent
            merged = registry._merge_defs(parent_def, builtin_def)
        else
            -- Builtin stands alone
            merged = builtin_def
        end
        
    else
        return nil, "Program '" .. program_name .. "' not found in builtin or user programs"
    end
    
    -- Cache and return
    registry.set_merged_cache(program_name, merged)
    return merged, nil
end

-- ============================================================================
-- Config Generation
-- ============================================================================

--- Generate config from a program
-- @param program_def table - program definition
-- @param options table - user-provided config options
-- @return string generated config, nil on success; nil, error_msg on failure
function registry.generate_config(program_def, options)
    if not program_def.generate_config then
        return nil, "Program missing generate_config function"
    end
    
    if type(program_def.generate_config) ~= "function" then
        return nil, "Program.generate_config must be a function"
    end
    
    local ok, result = pcall(program_def.generate_config, program_def, options)
    if not ok then
        return nil, "Config generation failed: " .. tostring(result)
    end
    
    return result or "", nil
end

-- ============================================================================
-- Hook Execution
-- ============================================================================

--- Execute a program hook (validate, post_install, pre_uninstall, etc.)
-- @param program_def table - program definition
-- @param hook_name string - name of hook (validate, post_install, pre_uninstall)
-- @param ... any - arguments to pass to hook
-- @return any hook result, nil on success; nil, error_msg on failure
function registry.run_hook(program_def, hook_name, ...)
    local hook_func = program_def[hook_name]
    
    if not hook_func then
        return nil, nil  -- Hook doesn't exist, that's OK
    end
    
    if type(hook_func) ~= "function" then
        return nil, "Hook '" .. hook_name .. "' must be a function"
    end
    
    local ok, result = pcall(hook_func, program_def, ...)
    if not ok then
        return nil, "Hook '" .. hook_name .. "' failed: " .. tostring(result)
    end
    
    return result, nil
end

-- ============================================================================
-- Service Extraction
-- ============================================================================

--- Extract systemd service definition from program
-- @param program_def table - program definition
-- @return table service definition, nil on success; nil, error_msg on failure
function registry.get_service(program_def)
    local service_spec = program_def.service
    if not service_spec then
        return nil, nil  -- No service defined, that's OK
    end
    
    if type(service_spec) ~= "table" then
        return nil, "Service spec must be a table"
    end
    
    return service_spec, nil
end

-- ============================================================================
-- Info & Listing
-- ============================================================================

--- Get information about a program
-- @param program_def table - program definition
-- @return table program info
function registry.get_program_info(program_def)
    return {
        name = program_def.name or "unknown",
        scope = program_def.scope or "user",
        schema = program_def.schema or {},
        service = program_def.service or nil,
        description = program_def.description or "",
    }
end

-- ============================================================================
-- Main API for Python wrapper
-- ============================================================================

--- Load a program by name (full resolution with inheritance)
-- @param name string - program name
-- @param config_home string - path to config home (~/.kod)
-- @return table program_def, nil on success; nil, error_msg on failure
function registry.load_program(name, config_home)
    if not config_home then
        config_home = os.getenv("HOME") .. "/.kod"
    end
    
    local builtin_dir = config_home .. "/../lib/registry/builtin"
    local user_dir = config_home .. "/plugins/programs"
    
    -- Discover programs
    local builtin_programs, err1 = registry.discover_builtin(builtin_dir)
    if not builtin_programs then
        return nil, err1
    end
    
    local user_programs, err2 = registry.discover_user_files(user_dir)
    if not user_programs then
        return nil, err2
    end
    
    -- Resolve and merge
    return registry.resolve_program(name, builtin_programs, user_programs)
end

--- List all available programs
-- @param config_home string - path to config home (~/.kod)
-- @return table list of program names, nil on success; nil, error_msg on failure
function registry.list_programs(config_home)
    if not config_home then
        config_home = os.getenv("HOME") .. "/.kod"
    end
    
    local builtin_dir = config_home .. "/../lib/registry/builtin"
    local user_dir = config_home .. "/plugins/programs"
    
    -- Discover programs
    local builtin_programs, err1 = registry.discover_builtin(builtin_dir)
    if not builtin_programs then
        return nil, err1
    end
    
    local user_programs, err2 = registry.discover_user_files(user_dir)
    if not user_programs then
        return nil, err2
    end
    
    -- Collect unique names
    local names = {}
    local seen = {}
    
    for name, _ in pairs(builtin_programs) do
        if not seen[name] then
            table.insert(names, name)
            seen[name] = true
        end
    end
    
    for name, _ in pairs(user_programs) do
        if not seen[name] then
            table.insert(names, name)
            seen[name] = true
        end
    end
    
    table.sort(names)
    return names, nil
end

return registry
