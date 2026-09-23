-- Packages section module - aggregates and installs system packages
-- Emits steps to install packages from aggregated config sections

local Schema = require('kod.core.schema')
local Repos = require('kod.system.repos')

-- ============================================================================
-- AGGREGATION: Collect packages from all config sections
-- ============================================================================

local function aggregate_base_packages(config)
    local packages = {}
    
    -- Base packages come from distro defaults (e.g., base, linux, grub)
    -- These are typically set in the distro schema, not user config
    -- For now, rely on packages section to be explicit
    
    return packages
end

local function aggregate_desktop_packages(config)
    local packages = {}
    
    if not config.desktop then
        return packages
    end
    
    local desktop = config.desktop
    
    -- Display manager
    if desktop.display_manager then
        table.insert(packages, desktop.display_manager)
    end
    
    -- Desktop environments and extra packages (legacy desktop_manager structure)
    if desktop.desktop_manager then
        for dm_name, dm_conf in pairs(desktop.desktop_manager) do
            if dm_conf.enable then
                table.insert(packages, dm_name)
                
                -- Extra packages for this desktop
                if dm_conf.extra_packages then
                    for _, pkg in pairs(dm_conf.extra_packages) do
                        table.insert(packages, pkg)
                    end
                end
            end
        end
    end
    
    -- Modern desktop environments structure
    if desktop.environments then
        for env_name, env_conf in pairs(desktop.environments) do
            if env_conf.enable then
                -- Main environment package (e.g., 'gnome', 'plasma', 'cosmic')
                table.insert(packages, env_name)
                
                -- Extra packages for this environment
                if env_conf.extra_packages then
                    for _, pkg in pairs(env_conf.extra_packages) do
                        table.insert(packages, pkg)
                    end
                end
            end
        end
    end
    
    return packages
end

local function aggregate_hardware_packages(config)
    local packages = {}
    
    if not config.hardware then
        return packages
    end
    
    for hw_name, hw_conf in pairs(config.hardware) do
        if hw_conf.enable then
            -- Use custom package name if specified, otherwise hw name
            local pkg_name = hw_conf.package or hw_name
            table.insert(packages, pkg_name)
            
            -- Extra packages for this hardware
            if hw_conf.extra_packages then
                for _, pkg in pairs(hw_conf.extra_packages) do
                    table.insert(packages, pkg)
                end
            end
        end
    end
    
    return packages
end

local function aggregate_system_packages(config)
    local packages = {}
    
    if not config.packages then
        return packages
    end
    
    -- User-specified system packages
    for _, pkg in pairs(config.packages) do
        table.insert(packages, pkg)
    end
    
    return packages
end

local function aggregate_font_packages(config)
    local packages = {}
    
    if not config.fonts then
        return packages
    end
    
    if config.fonts.packages then
        for _, pkg in pairs(config.fonts.packages) do
            table.insert(packages, pkg)
        end
    end
    
    return packages
end

local function aggregate_user_program_packages(config)
    local packages = {}
    
    if not config.users then
        return packages
    end
    
    for user_name, user_conf in pairs(config.users) do
        -- User programs
        if user_conf.programs then
            for prog_name, prog_conf in pairs(user_conf.programs) do
                if prog_conf.enable then
                    -- Use custom package name if specified, otherwise prog name
                    local pkg_name = prog_conf.package or prog_name
                    table.insert(packages, pkg_name)
                    
                    -- Extra packages for this program
                    if prog_conf.extra_packages then
                        for _, pkg in pairs(prog_conf.extra_packages) do
                            table.insert(packages, pkg)
                        end
                    end
                end
            end
        end
        
        -- User services
        if user_conf.services then
            for service_name, service_conf in pairs(user_conf.services) do
                if service_conf.enable then
                    -- Use custom package name if specified, otherwise service name
                    local pkg_name = service_conf.package or service_name
                    table.insert(packages, pkg_name)
                    
                    -- Extra packages for this service
                    if service_conf.extra_packages then
                        for _, pkg in pairs(service_conf.extra_packages) do
                            table.insert(packages, pkg)
                        end
                    end
                end
            end
        end
    end
    
    return packages
end

local function deduplicate_packages(packages)
    local seen = {}
    local unique = {}
    
    for _, pkg in ipairs(packages) do
        if not seen[pkg] then
            seen[pkg] = true
            table.insert(unique, pkg)
        end
    end
    
    return unique
end

local function aggregate_all_packages(config)
    local packages = {}
    
    -- Collect from all sources
    local sources = {
        aggregate_base_packages(config),
        aggregate_desktop_packages(config),
        aggregate_hardware_packages(config),
        aggregate_system_packages(config),
        aggregate_font_packages(config),
        aggregate_user_program_packages(config),
    }
    
    -- Flatten
    for _, source_packages in ipairs(sources) do
        for _, pkg in ipairs(source_packages) do
            table.insert(packages, pkg)
        end
    end
    
    -- Remove duplicates while preserving order
    return deduplicate_packages(packages)
end

-- ============================================================================
-- FLATPAK APPS EXTRACTION
-- ============================================================================
-- Extract flatpak: prefixed packages from all enabled sections
-- Mirrors aggregate_all_packages pattern to ensure consistency

local function extract_flatpak_apps_from_packages(packages)
    -- Extract flatpak app names from package list, removing 'flatpak:' prefix
    local apps = {}
    for _, pkg in ipairs(packages) do
        if type(pkg) == "string" and pkg:find("^flatpak:") then
            local app_name = pkg:sub(10)  -- Remove "flatpak:" prefix
            table.insert(apps, app_name)
        end
    end
    return apps
end

local function aggregate_flatpak_apps(config)
    -- Aggregate flatpak apps from all config sections, respecting enable checks
    local flatpak_apps = {}
    
    -- Desktop environments (with enable check)
    if config.desktop and config.desktop.environments then
        for env_name, env_conf in pairs(config.desktop.environments) do
            if type(env_conf) == "table" and env_conf.enable ~= false then
                if env_conf.extra_packages then
                    for _, pkg in ipairs(env_conf.extra_packages) do
                        if type(pkg) == "string" and pkg:find("^flatpak:") then
                            local app_name = pkg:sub(10)  -- Remove "flatpak:" prefix
                            table.insert(flatpak_apps, app_name)
                        end
                    end
                end
            end
        end
    end
    
    -- Hardware packages (with enable check)
    if config.hardware then
        for hw_name, hw_conf in pairs(config.hardware) do
            if type(hw_conf) == "table" and hw_conf.enable then
                if hw_conf.extra_packages then
                    for _, pkg in ipairs(hw_conf.extra_packages) do
                        if type(pkg) == "string" and pkg:find("^flatpak:") then
                            local app_name = pkg:sub(10)  -- Remove "flatpak:" prefix
                            table.insert(flatpak_apps, app_name)
                        end
                    end
                end
            end
        end
    end
    
    -- Font packages (from global config.fonts.packages)
    if config.fonts and config.fonts.packages then
        for _, pkg in ipairs(config.fonts.packages) do
            if type(pkg) == "string" and pkg:find("^flatpak:") then
                local app_name = pkg:sub(10)  -- Remove "flatpak:" prefix
                table.insert(flatpak_apps, app_name)
            end
        end
    end
    
    -- System packages (from global config.packages)
    if config.packages then
        for _, pkg in ipairs(config.packages) do
            if type(pkg) == "string" and pkg:find("^flatpak:") then
                local app_name = pkg:sub(10)  -- Remove "flatpak:" prefix
                table.insert(flatpak_apps, app_name)
            end
        end
    end
    
    -- User programs (with enable check)
    if config.users then
        for user_name, user_conf in pairs(config.users) do
            if type(user_conf) == "table" and user_conf.programs then
                for prog_name, prog_conf in pairs(user_conf.programs) do
                    if type(prog_conf) == "table" and prog_conf.enable then
                        if prog_conf.extra_packages then
                            for _, pkg in ipairs(prog_conf.extra_packages) do
                                if type(pkg) == "string" and pkg:find("^flatpak:") then
                                    local app_name = pkg:sub(10)  -- Remove "flatpak:" prefix
                                    table.insert(flatpak_apps, app_name)
                                end
                            end
                        end
                    end
                end
            end
            
            -- User services (with enable check)
            if type(user_conf) == "table" and user_conf.services then
                for service_name, service_conf in pairs(user_conf.services) do
                    if type(service_conf) == "table" and service_conf.enable then
                        if service_conf.extra_packages then
                            for _, pkg in ipairs(service_conf.extra_packages) do
                                if type(pkg) == "string" and pkg:find("^flatpak:") then
                                    local app_name = pkg:sub(10)  -- Remove "flatpak:" prefix
                                    table.insert(flatpak_apps, app_name)
                                end
                            end
                        end
                    end
                end
            end
        end
    end
    
    -- Remove duplicates while preserving order
    return deduplicate_packages(flatpak_apps)
end

-- ============================================================================
-- STEP EMISSION
-- ============================================================================

local module = {
    schema = Schema.packages,
    
    -- Export aggregation functions for Python to call
    aggregate_packages = aggregate_all_packages,
    aggregate_flatpak_apps = aggregate_flatpak_apps,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Aggregate packages from all config sections
        local packages = aggregate_all_packages(config)
        
        if #packages == 0 then
            return steps
        end
        
        -- Install all packages together in a single step
        local package_list = table.concat(packages, " ")
        
        local install_cmd = Repos.install_cmd(distro, package_list)
        if not install_cmd then
            return steps
        end
        
         table.insert(steps, {
             name = "packages_install_all",
             description = "Install system packages: " .. package_list,
             command = install_cmd,
             chroot = true,
             order = 500,
             timeout_s = 600,  -- 10 minutes for large package installation
         })
        
        return steps
    end
}

return module
