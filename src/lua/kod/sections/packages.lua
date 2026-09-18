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
    
    -- Desktop environments and extra packages
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
-- STEP EMISSION
-- ============================================================================

local module = {
    schema = Schema.packages,
    
    -- Export aggregation function for Python to call
    aggregate_packages = aggregate_all_packages,
    
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
        })
        
        return steps
    end
}

return module
