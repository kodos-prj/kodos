-- Desktop section module - desktop environment installation and configuration
-- Handles DE selection and installation (GNOME, KDE Plasma, XFCE, Cosmic, etc.)

local Schema = require('kod.lib.schema')

local module = {
    schema = Schema.desktop,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config or (config.enable == false) then
            return steps
        end
        
        -- Desktop environment installation
        if config.environment then
            local de_packages = {}
            local de_name = config.environment:lower()
            
            -- Map DE names to package lists
            local de_map = {
                gnome = {"gnome", "gnome-extra"},
                kde = {"plasma-meta", "kde-applications"},
                plasma = {"plasma-meta", "kde-applications"},
                xfce = {"xfce4", "xfce4-goodies"},
                cosmic = {"cosmic"},
                cinnamon = {"cinnamon"},
                mate = {"mate", "mate-extra"},
                lxde = {"lxde"},
            }
            
            de_packages = de_map[de_name] or {de_name}
            
            local pkg_list = table.concat(de_packages, " ")
            
            local install_cmd
            if distro == "arch" then
                install_cmd = "pacman -S --noconfirm " .. pkg_list
            elseif distro == "debian" then
                install_cmd = "apt-get install -y " .. pkg_list
            else
                return steps
            end
            
            table.insert(steps, {
                name = "desktop_install_" .. de_name,
                description = "Install " .. config.environment .. " desktop environment",
                command = install_cmd,
                order = 450,
            })
            
            -- Enable display manager (depends on DE)
            local dm_service
            if de_name == "gnome" then
                dm_service = "gdm"
            elseif de_name == "kde" or de_name == "plasma" then
                dm_service = "sddm"
            elseif de_name == "xfce" or de_name == "cinnamon" or de_name == "mate" then
                dm_service = "lightdm"
            elseif de_name == "cosmic" then
                dm_service = "cosmic-session"
            else
                dm_service = "lightdm"  -- fallback
            end
            
            table.insert(steps, {
                name = "desktop_dm_enable",
                description = "Enable display manager " .. dm_service,
                command = "systemctl enable " .. dm_service,
                order = 451,
                depends_on = {"desktop_install_" .. de_name},
            })
        end
        
        return steps
    end
}

return module
