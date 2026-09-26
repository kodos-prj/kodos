-- Programs section module - program installation and configuration
-- Handles custom program install logic defined via DSL

local Schema = require('kod.core.schema')

local module = {
    schema = Schema.programs,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Iterate over each program
        for program_name, program_config in pairs(config) do
            if type(program_config) == "table" then
                -- Check if program is enabled
                if program_config.enable == false then
                    goto continue
                end
                
                -- Custom install functions emit their own steps. Plain package
                -- fields need no step here: packages.lua aggregates them into
                -- the bulk install (packages_install_normal_and_base).
                if program_config.install and type(program_config.install) == "function" then
                    local install_steps = program_config.install(program_config, distro)

                    if install_steps and type(install_steps) == "table" then
                        for _, step in ipairs(install_steps) do
                            table.insert(steps, step)
                        end
                    end
                end

                    -- Enable the program's service if configured (service.enable).
                    -- per_user services are skipped: user units can't be enabled from a
                    -- chroot, and the system unit may not exist (e.g. syncthing).
                    -- The unit name defaults to the program name (original Python
                    -- behavior); service_name overrides it when the unit differs
                    -- (e.g. openssh -> sshd).
                    local svc = program_config.service
                    if type(svc) == "table" and svc.enable == true and svc.per_user ~= true then
                        -- No depends_on: the bulk package install (order 490)
                        -- always precedes this step (order 810).
                        local unit = svc.service_name or program_name
                        table.insert(steps, {
                            kind = "service",
                            name = unit,
                            description = "Enable service for program " .. program_name .. ": " .. unit,
                            command = "systemctl enable " .. unit,
                            chroot = true,
                            order = 810,
                        })
                    end

                    ::continue::
            end
        end
        
        return steps
    end
}

return module
