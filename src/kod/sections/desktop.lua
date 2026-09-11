-- Desktop section module - desktop environment installation and configuration
-- Handles DE selection and installation (GNOME, KDE Plasma, XFCE, Cosmic, etc.)

local Schema = require('kod.lib.schema')
local Repos = require('kod.lib.repos')

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
             
             local install_cmd = Repos.install_cmd(distro, pkg_list)
             if not install_cmd then
                 return steps
             end
            
            table.insert(steps, {
                name = "desktop_install_" .. de_name,
                description = "Install " .. config.environment .. " desktop environment",
                command = install_cmd,
                chroot = true,
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
                chroot = true,
                order = 451,
                depends_on = {"desktop_install_" .. de_name},
            })
        end
        
        -- Multi-environment configuration (desktop.environments block)
         if config.environments and type(config.environments) == "table" then
             local de_order = 460
             
             -- Handle each environment configuration
             for env_name, env_config in pairs(config.environments) do
                 if type(env_config) == "table" and env_config.enable ~= false then
                     -- Map environment names to DE packages
                     local de_map = {
                         gnome = {"gnome", "gnome-extra"},
                         plasma = {"plasma-meta", "kde-applications"},
                         cosmic = {"cosmic"},
                         budgie = {"budgie-desktop"},
                         pantheon = {"elementary-os"},
                     }
                     
                      local de_packages = de_map[env_name] or {env_name}
                      local pkg_list = table.concat(de_packages, " ")
                      
                      local install_cmd = Repos.install_cmd(distro, pkg_list)
                      if not install_cmd then
                          goto continue_env
                      end
                     
                      -- Install environment
                      table.insert(steps, {
                          name = "desktop_environments_install_" .. env_name,
                          description = "Install " .. env_name .. " desktop environment",
                          command = install_cmd,
                          chroot = true,
                          order = de_order,
                      })
                     
                     de_order = de_order + 1
                     
                     ::continue_env::
                 end
             end
         end
        
        -- Display manager configuration (if specified separately)
        if config.display_manager then
            local dm_service = config.display_manager:lower()
            
            -- Install display manager packages if needed
            local dm_packages = {
                gdm = "gdm",
                sddm = "sddm",
                lightdm = "lightdm",
                ["cosmic-session"] = "cosmic-session",
            }
            
             local dm_pkg = dm_packages[dm_service] or dm_service
             
             local install_cmd = Repos.install_cmd(distro, dm_pkg)
             if not install_cmd then
                 return steps
             end
            
            table.insert(steps, {
                name = "desktop_display_manager_install",
                description = "Install display manager: " .. config.display_manager,
                command = install_cmd,
                chroot = true,
                order = 455,
            })
            
            table.insert(steps, {
                name = "desktop_display_manager_enable",
                description = "Enable display manager " .. dm_service,
                command = "systemctl enable " .. dm_service,
                chroot = true,
                order = 456,
                depends_on = {"desktop_display_manager_install"},
            })
        end
        
        return steps
    end
}

return module
