-- Packages section module - installs system packages
-- Emits steps to install each package from the packages list

local Schema = require('kod.lib.schema')
local Repos = require('kod.lib.repos')

local module = {
    schema = Schema.packages,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config or #config == 0 then
            return steps
        end
        
        -- Install all packages together in a single step
        local package_list = table.concat(config, " ")
        
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
