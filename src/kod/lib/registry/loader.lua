-- Registry Loader: Program file discovery and loading
--
-- Responsibilities:
-- - Discover .lua files in builtin and user directories
-- - Load and parse .lua program definitions
-- - Manage caching to avoid reloading
-- - Handle errors gracefully (return tuples, not exceptions)
--
-- All functions return (result, error_msg) tuples where:
--   - result: the actual value on success, nil on failure
--   - error_msg: nil on success, error string on failure
--
-- This module does NOT handle inheritance/merging; that's in inheritance.lua
-- This module does NOT throw exceptions; it returns error tuples

local loader = {}

-- Global caches (persistent across calls)
local _builtin_cache = {}  -- {program_name: program_def}
local _user_cache = {}     -- {program_name: program_def}

-- ============================================================================
-- File Discovery
-- ============================================================================

--- Discover all .lua files in a directory
-- Returns {name: path} dict where name is filename without .lua extension
-- @param dir string - directory path to scan
-- @return table {name: path}, nil on success; nil, error_msg on failure
local function _scan_directory(dir)
    -- Try to load lfs (Lua File System) library
    -- If not available, return empty (will be handled by Python fallback)
    
    local result = {}
    local lfs = nil
    
    local ok, lfs_or_error = pcall(require, "lfs")
    if ok then
        lfs = lfs_or_error
    end
    
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
        -- Python will handle directory scanning as fallback
        return result, nil
    end
end

--- Discover builtin program .lua files
-- @param dir string - path to builtin directory (e.g., /path/to/src/kod/lib/registry/builtin)
-- @return table {name: path}, nil on success; nil, error_msg on failure
function loader.discover_builtin_files(dir)
    return _scan_directory(dir)
end

--- Discover user plugin .lua files
-- @param dir string - path to user plugins directory (e.g., ~/.kod/plugins/programs)
-- @return table {name: path}, nil on success; nil, error_msg on failure
function loader.discover_user_files(dir)
    return _scan_directory(dir)
end

-- ============================================================================
-- File Loading & Parsing
-- ============================================================================

--- Load and parse a single .lua program definition file
-- Executes the .lua file (which should return a table) and returns it
-- @param file_path string - path to .lua file
-- @return table program_def, nil on success; nil, error_msg on failure
function loader.load_program_file(file_path)
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

--- Get cached builtin program definition
-- @param name string - program name
-- @return table program_def, nil if not cached
function loader.get_builtin_cache(name)
    return _builtin_cache[name]
end

--- Get cached user program definition
-- @param name string - program name
-- @return table program_def, nil if not cached
function loader.get_user_cache(name)
    return _user_cache[name]
end

--- Set cached builtin program definition
-- @param name string - program name
-- @param program_def table - program definition
function loader.set_builtin_cache(name, program_def)
    _builtin_cache[name] = program_def
end

--- Set cached user program definition
-- @param name string - program name
-- @param program_def table - program definition
function loader.set_user_cache(name, program_def)
    _user_cache[name] = program_def
end

--- Clear all caches
function loader.clear_cache()
    _builtin_cache = {}
    _user_cache = {}
end

--- Get all cached program names (builtin + user)
-- @return table list of program names
function loader.get_cached_names()
    local names = {}
    for name, _ in pairs(_builtin_cache) do
        table.insert(names, name)
    end
    for name, _ in pairs(_user_cache) do
        if not _builtin_cache[name] then
            table.insert(names, name)
        end
    end
    table.sort(names)
    return names
end

return loader
