-- Services section module - system service enablement and startup
-- Handles systemctl enable/start for various services, config blocks, and systemd units

local Schema = require('kod.lib.schema')
local Repos = require('kod.lib.repos')

local module = {
    schema = Schema.services,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Iterate over each service
        for service_name, service_config in pairs(config) do
            if type(service_config) == "table" and service_name ~= "config" and service_name ~= "systemd" then
                local enable = service_config.enable
                local start = service_config.start
                
                -- Enable service on boot
                if enable == true then
                    table.insert(steps, {
                        name = "services_enable_" .. service_name,
                        description = "Enable service on boot: " .. service_name,
                        command = "systemctl enable " .. service_name,
                        order = 700,
                    })
                end
                
                -- Start service immediately
                if start == true then
                    local depend_on = enable == true and {"services_enable_" .. service_name} or nil
                    
                    table.insert(steps, {
                        name = "services_start_" .. service_name,
                        description = "Start service: " .. service_name,
                        command = "systemctl start " .. service_name,
                        order = 701,
                        depends_on = depend_on,
                    })
                end
            end
        end
        
        -- Service config block (Task 9 extension)
        if config.config and type(config.config) == "table" then
            local svc_config = config.config
            local svc_name = svc_config.service_name or "custom-service"
            
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
                        command = "echo 'Setting " .. setting_key .. "=" .. tostring(setting_value) .. "' # Placeholder for service config",
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
                            command = "mkdir -p /etc/systemd/system/ && echo '[Mount]' > /etc/systemd/system/" .. mount_name .. ".mount",
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
                            command = "mkdir -p /etc/systemd/system/ && echo '[Unit]' > /etc/systemd/system/" .. unit_name .. ".service",
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

