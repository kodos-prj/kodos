--- Unified Registry: Program discovery, loading, and inheritance
--
-- Consolidates loader.lua + inheritance.lua into single module
--
-- Responsibilities:
-- - Discover .lua files in builtin and user directories
-- - Load and parse .lua program definitions
-- - Resolve program inheritance chains (follow _extends field)
-- - Detect circular inheritance
-- - Merge builtin + user program definitions
-- - Manage caching to avoid reloading
--
-- All functions return (result, error_msg) tuples where:
--   - result: the actual value on success, nil on failure
--   - error_msg: nil on success, error string on failure
--
-- This module does NOT throw Lua exceptions; it returns error tuples

local lib = {}

-- Global caches (persistent across calls)
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
function lib.discover_builtin_files(dir)
    return _scan_directory(dir)
end

--- Discover user plugin .lua files
-- @param dir string - path to user plugins directory
-- @return table {name: path}, nil on success; nil, error_msg on failure
function lib.discover_user_files(dir)
    return _scan_directory(dir)
end

-- ============================================================================
-- File Loading & Parsing
-- ============================================================================

--- Load and parse a single .lua program definition file
-- Executes the .lua file (which should return a table) and returns it
-- @param file_path string - path to .lua file
-- @return table program_def, nil on success; nil, error_msg on failure
function lib.load_program_file(file_path)
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

function lib.get_merged_cache(name)
    return _merged_cache[name]
end

function lib.set_merged_cache(name, program_def)
    _merged_cache[name] = program_def
end

function lib.clear_cache()
    _merged_cache = {}
end

function lib.get_cache_info()
    return {
        merged = _merged_cache,
    }
end

-- Backward compatibility aliases for old two-tier cache interface
function lib.get_builtin_cache(name)
    return _merged_cache[name]
end

function lib.get_user_cache(name)
    return _merged_cache[name]
end

function lib.set_builtin_cache(name, program_def)
    _merged_cache[name] = program_def
end

function lib.set_user_cache(name, program_def)
    _merged_cache[name] = program_def
end

function lib.get_cached_names()
    local names = {}
    for name, _ in pairs(_merged_cache) do
        table.insert(names, name)
    end
    table.sort(names)
    return names
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
function lib._merge_defs(parent_def, child_def)
    -- Skip _extends marker
    local merged = {}
    for k, v in pairs(parent_def) do
        if k ~= "_extends" then
            merged[k] = v
        end
    end
    
    for k, v in pairs(child_def) do
        if k ~= "_extends" then
            if type(v) == "table" and type(merged[k]) == "table" then
                merged[k] = _deep_merge_tables(merged[k], v)
            else
                merged[k] = v
            end
        end
    end
    
    return merged
end

-- ============================================================================
-- Program Resolution & Loading (main entry point)
-- ============================================================================

--- Resolve a program's inheritance chain, loading parents as needed
-- Returns the fully merged program definition
--
-- @param program_name string - name of program to load (e.g., "git")
-- @param builtin_programs table - {name: path} dict of builtin programs
-- @param user_programs table - {name: path} dict of user programs
-- @param visited table - set of visited program names (for circular detection)
-- @return table merged_program_def, nil on success; nil, error_msg on failure
function lib.resolve_program(program_name, builtin_programs, user_programs, visited)
    if not visited then visited = {} end
    
    -- Check for circular inheritance
    local ok, err = _detect_circular(program_name, visited)
    if not ok then
        return nil, err
    end
    
    -- Check merged cache first (avoid reloading)
    local cached = lib.get_merged_cache(program_name)
    if cached then
        return cached, nil
    end
    
    -- Load builtin and user definitions
    local builtin_def = nil
    local user_def = nil
    
    if builtin_programs and builtin_programs[program_name] then
        builtin_def, err = lib.load_program_file(builtin_programs[program_name])
        if not builtin_def then
            return nil, err
        end
    end
    
    if user_programs and user_programs[program_name] then
        user_def, err = lib.load_program_file(user_programs[program_name])
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
        merged = lib._merge_defs(builtin_def, user_def)
        
    elseif user_def then
        -- Only user exists
        if user_def._extends then
            -- User extends something; load parent
            local parent_name = user_def._extends
            if parent_name == program_name then
                return nil, "Program '" .. program_name .. "' user tries to extend itself"
            end
            
            local parent_def, err2 = lib.resolve_program(parent_name, builtin_programs, user_programs, visited)
            if not parent_def then
                return nil, err2
            end
            -- Merge with parent
            merged = lib._merge_defs(parent_def, user_def)
        else
            -- User stands alone
            merged = user_def
        end
        
    elseif builtin_def then
        -- Only builtin exists
        if builtin_def._extends then
            -- Builtin extends something; load parent
            local parent_name = builtin_def._extends
            if parent_name == program_name then
                return nil, "Program '" .. program_name .. "' tries to extend itself"
            end
            
            local parent_def, err2 = lib.resolve_program(parent_name, builtin_programs, user_programs, visited)
            if not parent_def then
                return nil, err2
            end
            -- Merge with parent
            merged = lib._merge_defs(parent_def, builtin_def)
        else
            -- Builtin stands alone
            merged = builtin_def
        end
        
    else
        return nil, "Program '" .. program_name .. "' not found in builtin or user programs"
    end
    
    -- Cache and return
    lib.set_merged_cache(program_name, merged)
    return merged, nil
end

-- ============================================================================
-- Program Validation
-- ============================================================================

--- Validate program definition structure
-- @param program_def table - program definition to validate
-- @return nil, nil on success; nil, error_msg on failure
function lib.validate_program_def(program_def)
    if type(program_def) ~= "table" then
        return nil, "Program definition must be a table"
    end
    
    -- Basic structure validation
    if program_def.name and type(program_def.name) ~= "string" then
        return nil, "Program name must be a string"
    end
    
    if program_def.scope and type(program_def.scope) ~= "string" then
        return nil, "Program scope must be a string"
    end
    
    if program_def.scope and program_def.scope ~= "system" and 
       program_def.scope ~= "user" and program_def.scope ~= "both" then
        return nil, "Program scope must be 'system', 'user', or 'both'"
    end
    
    if program_def.schema and type(program_def.schema) ~= "table" then
        return nil, "Program schema must be a table"
    end
    
    return true, nil
end

return lib
