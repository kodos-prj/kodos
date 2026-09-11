-- Packages section module - installs system packages
-- Emits steps to install each package from the packages list

local Schema = require('kod.lib.schema')

local module = {
    schema = Schema.packages,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config or #config == 0 then
            return steps
        end
        
        -- Install all packages together in a single step
        local package_list = table.concat(config, " ")
        
        local install_cmd
        if distro == "arch" then
            install_cmd = "pacman -S --noconfirm " .. package_list
        elseif distro == "debian" then
            install_cmd = "apt-get install -y " .. package_list
        else
            return steps
        end
        
        table.insert(steps, {
            name = "packages_install_all",
            description = "Install system packages: " .. package_list,
            command = install_cmd,
            order = 500,
        })
        
        return steps
    end
}

return module
