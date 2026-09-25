-- Services section module - aggregates and enables system services
-- Emits steps to enable services and configure service-related packages

local Schema = require('kod.core.schema')
local Repos = require('kod.system.repos')

-- ============================================================================
-- AGGREGATION: Collect services from config sections
-- ============================================================================

local function aggregate_desktop_services(config)
    local services = {}
    
    if not config.desktop then
        return services
    end
    
    local desktop = config.desktop
    
    -- Display manager service (top-level, can be directly specified)
    if desktop.display_manager then
        table.insert(services, desktop.display_manager)
    end
    
    -- Note: Desktop environments (gnome, plasma, cosmic, etc.) don't currently
    -- specify their own display managers in the schema. The display_manager is
    -- set at the desktop section level and applies to the enabled environment.
    -- If per-environment display manager support is added later, iterate here.
    
    return services
end

local function aggregate_system_services(config)
    local services = {}
    
    if not config.services then
        return services
    end
    
    -- System services with enable=true
    for service_name, service_conf in pairs(config.services) do
        if service_conf.enable then
            table.insert(services, service_name)
        end
    end
    
    return services
end

local function aggregate_user_services(config)
    local services = {}
    
    if not config.users then
        return services
    end
    
    -- User services
    for user_name, user_conf in pairs(config.users) do
        if user_conf.services then
            for service_name, service_conf in pairs(user_conf.services) do
                if service_conf.enable then
                    table.insert(services, service_name)
                end
            end
        end
    end
    
    return services
end

local function deduplicate_services(services)
    local seen = {}
    local unique = {}
    
    for _, svc in ipairs(services) do
        if not seen[svc] then
            seen[svc] = true
            table.insert(unique, svc)
        end
    end
    
    return unique
end

local function aggregate_all_services(config)
    local services = {}
    
    -- Collect from all sources
    local sources = {
        aggregate_desktop_services(config),
        aggregate_system_services(config),
        aggregate_user_services(config),
    }
    
    -- Flatten
    for _, source_services in ipairs(sources) do
        for _, svc in ipairs(source_services) do
            table.insert(services, svc)
        end
    end
    
    -- Remove duplicates while preserving order
    return deduplicate_services(services)
end

-- ============================================================================
-- STEP EMISSION
-- ============================================================================

local module = {
    schema = Schema.services,
    
    -- Export aggregation function for Python to call
    aggregate_services = aggregate_all_services,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Aggregate services from all config sections
        local services = aggregate_all_services(config)
        
        -- Emit enable steps for each service
        for _, service_name in ipairs(services) do
            table.insert(steps, {
                kind = "service",
                name = service_name,
                description = "Enable service on boot: " .. service_name,
                command = "systemctl enable " .. service_name,
                chroot = true,
                order = 700,
            })
        end
        
        -- Service config block (Task 9 extension)
        if config.config and type(config.config) == "table" then
            local svc_config = config.config
            
            -- Install service packages
            if svc_config.packages then
                local main_pkg = svc_config.packages.main
                if main_pkg then
                    local install_cmd = Repos.install_cmd(distro, main_pkg)
                    if not install_cmd then
                        main_pkg = nil
                    end
                    
                    if main_pkg then
                        table.insert(steps, {
                            name = "services_config_install_main",
                            description = "Install main service package: " .. main_pkg,
                            command = install_cmd,
                            chroot = true,
                            order = 710,
                        })
                    end
                end
                
                -- Install extra packages
                if svc_config.packages.extra and #svc_config.packages.extra > 0 then
                    local extra_list = table.concat(svc_config.packages.extra, " ")
                    local install_cmd = Repos.install_cmd(distro, extra_list)
                    if not install_cmd then
                        install_cmd = nil
                    end
                    
                    if install_cmd then
                        table.insert(steps, {
                            name = "services_config_install_extra",
                            description = "Install extra service packages: " .. extra_list,
                            command = install_cmd,
                            chroot = true,
                            order = 711,
                        })
                    end
                end
            end
            
             -- Apply service settings
             if svc_config.settings and type(svc_config.settings) == "table" then
                 local settings_order = 720
                 for setting_key, setting_value in pairs(svc_config.settings) do
                     table.insert(steps, {
                         name = "services_config_setting_" .. setting_key,
                         description = "Configure service setting: " .. setting_key .. " = " .. tostring(setting_value),
                         command = "echo \"Setting " .. setting_key .. "=" .. tostring(setting_value) .. "\" # Placeholder for service config",
                         chroot = true,
                         order = settings_order,
                     })
                     settings_order = settings_order + 1
                 end
             end
         end
         
         -- Systemd configuration block (Task 9 extension)
         if config.systemd and type(config.systemd) == "table" then
             -- Handle systemd mounts
             if config.systemd.mounts and type(config.systemd.mounts) == "table" then
                 local mount_order = 730
                 for mount_name, mount_config in pairs(config.systemd.mounts) do
                     if type(mount_config) == "table" then
                         table.insert(steps, {
                             name = "services_systemd_mount_" .. mount_name,
                             description = "Configure systemd mount: " .. mount_name,
                             command = "mkdir -p /etc/systemd/system/ && echo \"[Mount]\" > /etc/systemd/system/" .. mount_name .. ".mount",
                             chroot = true,
                             order = mount_order,
                         })
                         mount_order = mount_order + 1
                     end
                 end
             end
             
             -- Handle systemd units
             if config.systemd.units and type(config.systemd.units) == "table" then
                 local unit_order = 740
                 for unit_name, unit_config in pairs(config.systemd.units) do
                     if type(unit_config) == "table" then
                         table.insert(steps, {
                             name = "services_systemd_unit_" .. unit_name,
                             description = "Configure systemd unit: " .. unit_name,
                             command = "mkdir -p /etc/systemd/system/ && echo \"[Unit]\" > /etc/systemd/system/" .. unit_name .. ".service",
                             chroot = true,
                             order = unit_order,
                         })
                         unit_order = unit_order + 1
                     end
                 end
             end
         end
        
        return steps
    end
}

return module
