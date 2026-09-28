-- Desktop section module - desktop environment installation and configuration
-- Handles DE selection and installation (GNOME, KDE Plasma, XFCE, Cosmic, etc.)

local Schema = require('kod.core.schema')
local Repos = require('kod.system.repos')

local module = {
    schema = Schema.desktop,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end

        -- Planner passes the full config (flatpak aggregation needs it); DE/DM
        -- settings live under .desktop. Tolerate a bare section table too.
        local d = (type(config.desktop) == "table") and config.desktop or config
        if d.enable == false then
            return steps
        end
        
        -- Desktop environment installation
        if d.environment then
            local de_packages = {}
            local de_name = d.environment:lower()
            
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
                description = "Install " .. d.environment .. " desktop environment",
                command = install_cmd,
                chroot = true,
                order = 450,
                timeout_s = 3600,  -- DE installs are large downloads
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
                kind = "service",
                name = dm_service,
                description = "Enable display manager " .. dm_service,
                command = "systemctl enable " .. dm_service,
                chroot = true,
                order = 451,
                depends_on = {"desktop_install_" .. de_name},
            })
        end
        
        -- Multi-environment configuration (desktop.environments block)
          if d.environments and type(d.environments) == "table" then
              local de_order = 460
              
              -- Handle each environment configuration
              for env_name, env_config in pairs(d.environments) do
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
                          timeout_s = 3600,  -- DE installs are large downloads
                      })
                     
                     de_order = de_order + 1
                     
                     ::continue_env::
                 end
             end
         end
        
        -- Display manager configuration (if specified separately).
        -- Only install when at least one environment is enabled; a display
        -- manager with no desktop to greet is useless.
        local any_env_enabled = false
        if d.environments and type(d.environments) == "table" then
            for _, env_config in pairs(d.environments) do
                if type(env_config) == "table" and env_config.enable ~= false then
                    any_env_enabled = true
                    break
                end
            end
        end

         if d.display_manager and any_env_enabled then
             local dm_service = d.display_manager:lower()
             
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
                  description = "Install display manager: " .. d.display_manager,
                  command = install_cmd,
                  chroot = true,
                  order = 455,
                  timeout_s = 1800,
              })
             
              table.insert(steps, {
                  kind = "service",
                  name = dm_service,
                  description = "Enable display manager " .. dm_service,
                  command = "systemctl enable " .. dm_service,
                  chroot = true,
                  order = 456,
                  depends_on = {"desktop_display_manager_install"},
              })

              -- The DM unit (e.g. cosmic-greeter) only aliases display-manager.service;
              -- nothing pulls it in unless the default target is graphical.target
              -- (fresh installs default to multi-user.target). gdm/sddm do this in
              -- their post-install hooks; cosmic-greeter doesn't.
              table.insert(steps, {
                  name = "desktop_default_target_graphical",
                  description = "Boot to graphical.target so display manager starts",
                  command = "systemctl set-default graphical.target",
                  chroot = true,
                  order = 457,
                  depends_on = {dm_service},
              })
          end
         
            -- Flatpak apps are installed system-wide on first boot by a systemd
            -- service. Not during chroot (flatpak needs a running system), and no
            -- daemon gating: root system installs use /var/lib/flatpak directly,
            -- not the user-level flatpak daemon.
             local packages_module = require('kod.sections.packages')
            local all_packages = packages_module.aggregate_packages(config)
            local flatpak_apps = packages_module.extract_flatpak_apps(all_packages.packages)
          
           for _, s in ipairs(packages_module.emit_flatpak_setup_steps(flatpak_apps)) do
               table.insert(steps, s)
           end
         
         return steps
    end
}

return module
