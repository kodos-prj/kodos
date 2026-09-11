-- Fonts section module - system font installation
-- Handles installation of monospace, sans-serif, and emoji fonts

local Schema = require('kod.lib.schema')

local module = {
    schema = Schema.fonts,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config or (config.enable == false) then
            return steps
        end
        
        local font_packages = {}
        
        -- Collect all font packages
        if config.monospace then
            for _, font in ipairs(config.monospace) do
                table.insert(font_packages, font)
            end
        end
        
        if config.sans_serif then
            for _, font in ipairs(config.sans_serif) do
                table.insert(font_packages, font)
            end
        end
        
        if config.emoji then
            for _, font in ipairs(config.emoji) do
                table.insert(font_packages, font)
            end
        end
        
        -- Install fonts if any are specified
        if #font_packages > 0 then
            local pkg_list = table.concat(font_packages, " ")
            
            local install_cmd
            if distro == "arch" then
                install_cmd = "pacman -S --noconfirm " .. pkg_list
            elseif distro == "debian" then
                install_cmd = "apt-get install -y " .. pkg_list
            else
                return steps
            end
            
            table.insert(steps, {
                name = "fonts_install_all",
                description = "Install system fonts: " .. pkg_list,
                command = install_cmd,
                order = 400,
            })
            
            -- Update font cache
            table.insert(steps, {
                name = "fonts_cache_update",
                description = "Update system font cache",
                command = "fc-cache -fv",
                order = 401,
                depends_on = {"fonts_install_all"},
            })
        end
        
        return steps
    end
}

return module
