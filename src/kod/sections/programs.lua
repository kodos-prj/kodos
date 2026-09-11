-- Programs section module - program installation and configuration
-- Handles custom program install logic defined via DSL

local Schema = require('kod.lib.schema')

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
                
                -- Look for program-specific install function
                if program_config.install and type(program_config.install) == "function" then
                    -- Call the program's install function to get steps
                    local install_steps = program_config.install(program_config, distro)
                    
                    if install_steps and type(install_steps) == "table" then
                        for _, step in ipairs(install_steps) do
                            table.insert(steps, step)
                        end
                    end
                else
                    -- Fallback: generate generic install step if package name is provided
                    if program_config.package then
                        local pkg_name = program_config.package
                        
                        local install_cmd
                        if distro == "arch" then
                            install_cmd = "pacman -S --noconfirm " .. pkg_name
                        elseif distro == "debian" then
                            install_cmd = "apt-get install -y " .. pkg_name
                        else
                            goto continue
                        end
                        
                        table.insert(steps, {
                            name = "programs_install_" .. program_name,
                            description = "Install program: " .. program_name,
                            command = install_cmd,
                            order = 800,
                        })
                    end
                end
                
                ::continue::
            end
        end
        
        return steps
    end
}

return module
