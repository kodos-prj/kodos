-- Desktop section module - desktop environment installation and configuration
-- Handles DE selection and installation (GNOME, KDE Plasma, XFCE, Cosmic, etc.)

local Schema = require('kod.core.schema')
local Repos = require('kod.system.repos')

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
        
        -- Display manager configuration (if specified separately).
        -- Only install when at least one environment is enabled; a display
        -- manager with no desktop to greet is useless.
        local any_env_enabled = false
        if config.environments and type(config.environments) == "table" then
            for _, env_config in pairs(config.environments) do
                if type(env_config) == "table" and env_config.enable ~= false then
                    any_env_enabled = true
                    break
                end
            end
        end

         if config.display_manager and any_env_enabled then
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
                 kind = "service",
                 name = dm_service,
                 description = "Enable display manager " .. dm_service,
                 command = "systemctl enable " .. dm_service,
                 chroot = true,
                 order = 456,
                 depends_on = {"desktop_display_manager_install"},
             })
         end
         
         -- Flatpak apps installation (post-boot via systemd service)
           -- Extract flatpak apps from all enabled sections and defer to first-boot service
           local packages_module = require('kod.sections.packages')
           local flatpak_apps = packages_module.aggregate_flatpak_apps(config)
          
           if #flatpak_apps > 0 then
               -- Write flatpak apps list to config file
               -- Build command using printf %s\n with each app as separate arg
               local apps_args = ""
               for _, app in ipairs(flatpak_apps) do
                   -- Escape single quotes in app names
                   local escaped_app = app:gsub("'", "'\\''")
                   apps_args = apps_args .. " '" .. escaped_app .. "'"
               end
               local write_config_cmd = "mkdir -p /etc/kod && printf '%s\\n'" .. apps_args .. " > /etc/kod/flatpak-apps.txt"
              
              table.insert(steps, {
                  name = "flatpak_config_write",
                  description = "Write flatpak apps config",
                  command = write_config_cmd,
                  chroot = true,
                  order = 470,
              })
              
              -- Write install script (uses printf to avoid shell variable interpolation issues)
              -- Store script as base64 to avoid escaping nightmares
              local install_script_content = [[#!/bin/bash
# kod-install-flatpak-apps - Install flatpak applications on first boot
set -e
FLATPAK_APPS_CONFIG="/etc/kod/flatpak-apps.txt"
INSTALLED_FLAG="/var/lib/kod/flatpak-apps-installed"
if [ ! -f "$FLATPAK_APPS_CONFIG" ]; then
    echo "No flatpak apps configured in $FLATPAK_APPS_CONFIG"
    exit 0
fi
mapfile -t APPS < "$FLATPAK_APPS_CONFIG"
if [ ${#APPS[@]} -eq 0 ]; then
    echo "No flatpak apps to install"
    mkdir -p "$(dirname "$INSTALLED_FLAG")"
    touch "$INSTALLED_FLAG"
    exit 0
fi
echo "Installing flatpak applications"
if ! flatpak remote-list | grep -q flathub; then
    flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
fi
flatpak install -y flathub "${APPS[@]}"
mkdir -p "$(dirname "$INSTALLED_FLAG")"
touch "$INSTALLED_FLAG"
echo "Flatpak apps installation complete"
]]
              
              -- Escape single quotes for shell
              local script_escaped = install_script_content:gsub("'", "'\\''")
              local write_script_cmd = "mkdir -p /usr/local/bin && echo '" .. script_escaped .. "' > /usr/local/bin/kod-install-flatpak-apps && chmod +x /usr/local/bin/kod-install-flatpak-apps"
              
              table.insert(steps, {
                  name = "flatpak_install_script_write",
                  description = "Write flatpak install script",
                  command = write_script_cmd,
                  chroot = true,
                  order = 471,
                  depends_on = {"flatpak_config_write"},
              })
              
              -- Write systemd service
              local systemd_service = [[
[Unit]
Description=KodOS Flatpak Apps Installer
After=multi-user.target
ConditionPathExists=/etc/kod/flatpak-apps.txt

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/kod-install-flatpak-apps
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
]]
              
              local service_escaped = systemd_service:gsub("'", "'\\''")
              local write_service_cmd = "mkdir -p /etc/systemd/system && echo '" .. service_escaped .. "' > /etc/systemd/system/kod-flatpak-install.service"
              
              table.insert(steps, {
                  name = "flatpak_systemd_service_write",
                  description = "Write flatpak installer systemd service",
                  command = write_service_cmd,
                  chroot = true,
                  order = 472,
                  depends_on = {"flatpak_install_script_write"},
              })
              
              -- Enable the service to run on first boot
              table.insert(steps, {
                  kind = "service",
                  name = "kod-flatpak-install",
                  description = "Enable flatpak installer service for first boot",
                  command = "systemctl enable kod-flatpak-install",
                  chroot = true,
                  order = 473,
                  depends_on = {"flatpak_systemd_service_write"},
              })
          end
         
         return steps
    end
}

return module
