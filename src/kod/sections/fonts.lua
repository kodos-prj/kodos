-- Fonts section module - system font installation
-- Handles installation of monospace, sans-serif, and emoji fonts

local Schema = require('kod.lib.schema')
local Repos = require('kod.lib.repos')

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
            
            local install_cmd = Repos.install_cmd(distro, pkg_list)
            if not install_cmd then
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
        
        -- Additional font packages (Task 8 extension)
        if config.packages and #config.packages > 0 then
            local pkg_list = table.concat(config.packages, " ")
            
            local install_cmd = Repos.install_cmd(distro, pkg_list)
            if not install_cmd then
                return steps
            end
            
            table.insert(steps, {
                name = "fonts_packages_install",
                description = "Install additional font packages: " .. pkg_list,
                command = install_cmd,
                order = 402,
            })
        end
        
        -- Custom font directory setup
        if config.font_dir then
            table.insert(steps, {
                name = "fonts_font_dir_create",
                description = "Create custom font directory: " .. config.font_dir,
                command = "mkdir -p " .. config.font_dir .. " && chmod 755 " .. config.font_dir,
                order = 403,
            })
            
            -- Copy system fonts to custom directory (optional)
            table.insert(steps, {
                name = "fonts_font_dir_refresh",
                description = "Refresh font cache for custom directory: " .. config.font_dir,
                command = "fc-cache -fv " .. config.font_dir,
                order = 404,
                depends_on = {"fonts_font_dir_create"},
            })
        end
        
        return steps
    end
}

return module
