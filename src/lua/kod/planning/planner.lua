-- Schema-driven Planner for KodOS
-- Loads all section modules and composes installation/configuration steps
-- Replaces 600+ lines of nested conditionals with simple composition

local Planner = {}

-- List of all 13 section modules (order of iteration only, not execution order)
Planner.sections = {
    'base_distribution', 'repos', 'devices', 'boot', 'hardware',
    'locale', 'network', 'users', 'desktop', 'fonts',
    'packages', 'services', 'programs'
}

-- Cache for loaded section modules to avoid repeated requires
Planner._section_cache = {}

-- Load a section module, with caching
local function load_section(section_name)
    if Planner._section_cache[section_name] then
        return Planner._section_cache[section_name]
    end
    
    local success, section = pcall(require, 'kod.sections.' .. section_name)
    if not success then
        error("Failed to load section module '" .. section_name .. "': " .. tostring(section))
    end
    
    if not section.emit_steps then
        error("Section module '" .. section_name .. "' does not have emit_steps function")
    end
    
    Planner._section_cache[section_name] = section
    return section
end

-- Sort steps by order field, with stable sort for same-order steps
-- If steps have depends_on, ensure dependencies come before dependents
local function sort_steps(steps)
    -- First pass: sort by order field, tie-break by name.
    -- Lua table.sort is NOT stable, so equal-order steps need a total order
    -- or plan output is nondeterministic (flaky golden tests, unreproducible plans).
    table.sort(steps, function(a, b)
        local order_a = a.order or 0
        local order_b = b.order or 0
        if order_a ~= order_b then
            return order_a < order_b
        end
        return (a.name or "") < (b.name or "")
    end)
    
    -- Second pass: handle dependencies (simple topological sort)
    -- Only do 1 pass - assumes dependencies are already well-ordered by order field
    local result = {}
    local added = {}
    
    for _, step in ipairs(steps) do
        if step.depends_on and #step.depends_on > 0 then
            -- Try to find and add dependencies first
            for _, dep_name in ipairs(step.depends_on) do
                if not added[dep_name] then
                    -- Find dependency in original steps
                    for _, candidate in ipairs(steps) do
                        if candidate.name == dep_name and not added[candidate.name] then
                            table.insert(result, candidate)
                            added[candidate.name] = true
                            break
                        end
                    end
                end
            end
        end
        
        if not added[step.name] then
            table.insert(result, step)
            added[step.name] = true
        end
    end
    
    return result
end

-- Validate that config has required base_distribution
local function validate_config(config)
    if not config then
        return false, "config is nil"
    end
    
    if not config.base_distribution then
        return false, "config must have base_distribution (required field)"
    end
    
    if config.base_distribution ~= "arch" and config.base_distribution ~= "debian" then
        return false, "base_distribution must be 'arch' or 'debian', got: " .. tostring(config.base_distribution)
    end
    
    return true, nil
end

-- Merge user-level programs and services into global collections
-- Order: global first (lower order), then user (higher order)
-- No duplicates: if a program/service exists in both, global is kept
local function merge_user_programs_services(config)
    if not config.users then
        return
    end
    
    -- Iterate through users and merge their programs and services into global
    for username, user_config in pairs(config.users) do
        if type(user_config) == "table" then
            -- Merge user-level programs into global programs
            if user_config.programs and type(user_config.programs) == "table" then
                if not config.programs then
                    config.programs = {}
                end
                for program_name, program_config in pairs(user_config.programs) do
                    -- Only add if not already in global (global takes precedence)
                    if not config.programs[program_name] then
                        config.programs[program_name] = program_config
                    end
                end
            end
            
            -- Merge user-level services into global services
            if user_config.services and type(user_config.services) == "table" then
                if not config.services then
                    config.services = {}
                end
                for service_name, service_config in pairs(user_config.services) do
                    -- Only add if not already in global (global takes precedence)
                    if not config.services[service_name] then
                        config.services[service_name] = service_config
                    end
                end
            end
        end
    end
end

-- Main composition function: load all sections, call emit_steps, collect and sort results
---Compose installation/rebuild plan from configuration.
---
---Loads all enabled configuration sections, calls their emit_steps() methods,
---merges the resulting steps, sorts them by order field, and returns the
---complete execution plan.
---
---Entry point for Python planner (src/kod/planner.py:compose_steps_lua).
---
---Process:
---  1. Validate config and distro parameters
---  2. Set config.base_distribution if not already set
---  3. Merge user-level programs/services into global collections (Task 10)
---  4. For each enabled section (in order):
---     - Load section module (with caching)
---     - Call section.emit_steps(section_config, distro)
---     - Collect all returned steps
---  5. Sort all steps by order field (and handle dependencies via sort_steps)
---  6. Return (steps, error_msg) or (nil, error) on validation failure
---
---Special handling:
---  - packages section receives full config (needs to aggregate from all sections)
---  - All other sections receive their section-specific config (config[section_name])
---  - Errors in individual sections are collected but don't stop composition
---  - Returns both steps and error messages (partial success case)
---
---@param config table|LuaTable Configuration table (from load_config or Python dict)
---@param distro string Distribution name: "arch" or "debian"
---
---@return table|nil all_steps Ordered list of Step tables, or nil on validation failure
---@return string|nil error_msg Concatenated error messages from sections, or nil if no errors
---
---@raise Returns (nil, error_msg) instead of raising on validation failure
---
---Example:
---  local planner = require('kod.planning.planner')
---  local config = require('kod.lib.configs').load('example/testvm/configuration.lua')
---  local steps, errors = planner:compose(config, 'arch')
---  if not steps then
---    print('Failed to compose plan:', errors)
---    return
---  end
---  if errors then
---    print('Warnings during composition:', errors)
---  end
---  for i, step in ipairs(steps) do
---    print(i, step.name, step.order)
---  end
function Planner:compose(config, distro)
    -- Validate inputs
    local valid, err = validate_config(config)
    if not valid then
        return nil, err
    end
    
    if not distro or (distro ~= "arch" and distro ~= "debian") then
        return nil, "distro must be 'arch' or 'debian', got: " .. tostring(distro)
    end
    
    -- If distro not specified in config, use the passed distro parameter
    if not config.base_distribution then
        config.base_distribution = distro
    end
    
    -- Merge user-level programs and services into global collections (Task 10)
    merge_user_programs_services(config)
    
    local all_steps = {}
    local errors = {}
    
    -- Iterate through all sections (in order)
    for _, section_name in ipairs(Planner.sections) do
        -- Skip sections that aren't in config
        if config[section_name] then
            -- Try to load and call section
            local success, section_or_error = pcall(load_section, section_name)
            if not success then
                table.insert(errors, section_or_error)
                goto continue
            end
            
            local section = section_or_error
            
            -- Call emit_steps to get steps from this section
            local ok, err = pcall(function()
                -- Special case: packages section needs full config to aggregate from all sections
                -- All other sections receive their section-specific config
                local section_config = (section_name == 'packages') and config or config[section_name]
                local section_steps = section.emit_steps(section_config, distro)
                if section_steps and type(section_steps) == "table" then
                    for _, step in ipairs(section_steps) do
                        table.insert(all_steps, step)
                    end
                end
            end)

            if not ok then
                table.insert(errors, "Section '" .. section_name .. "' emit_steps failed: " .. tostring(err))
            end
        end
        
        ::continue::
    end
    
    -- Sort all collected steps by order field (and handle dependencies)
    all_steps = sort_steps(all_steps)
    
    -- If there were errors, return them (but also return the steps we got)
    local error_msg = nil
    if #errors > 0 then
        error_msg = table.concat(errors, "; ")
    end
    
    return all_steps, error_msg
end

-- Clear the cache (useful for testing)
function Planner:clear_cache()
    self._section_cache = {}
end

return Planner
