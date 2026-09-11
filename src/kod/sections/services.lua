-- Services section module - system service enablement and startup
-- Handles systemctl enable/start for various services

local Schema = require('kod.lib.schema')

local module = {
    schema = Schema.services,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Iterate over each service
        for service_name, service_config in pairs(config) do
            if type(service_config) == "table" then
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
        
        return steps
    end
}

return module
