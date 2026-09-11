-- Boot section module - kernel and bootloader configuration
-- Handles kernel package, modules, and bootloader setup

local Schema = require('kod.lib.schema')
local Repos = require('kod.lib.repos')

local module = {
    schema = Schema.boot,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Kernel configuration
         if config.kernel then
             local kernel_pkg = config.kernel.package or "linux"
             
             -- Install kernel package
             local install_cmd = Repos.install_cmd(distro, kernel_pkg)
             if not install_cmd then
                 return steps
             end
            
            table.insert(steps, {
                name = "boot_kernel_install",
                description = "Install kernel: " .. kernel_pkg,
                command = install_cmd,
                chroot = true,
                order = 200,
            })
            
              -- Configure kernel modules in initramfs
               if config.kernel.modules and #config.kernel.modules > 0 then
                   local modules_str = table.concat(config.kernel.modules, " ")
                   
                   table.insert(steps, {
                       name = "boot_kernel_modules_config",
                       description = "Configure kernel modules in initramfs: " .. modules_str,
                       command = "mkdir -p /etc/mkinitcpio.conf.d && echo \"MODULES=(" .. modules_str .. ")\" > /etc/mkinitcpio.conf.d/modules.conf",
                       chroot = true,
                       order = 201,
                       on_distro = "arch",
                       depends_on = {"boot_kernel_install"},
                   })
               end
              
              -- Regenerate initramfs after kernel install and module configuration
              -- Use distribution-specific tool:
              -- - Arch Linux: mkinitcpio
              -- - Debian/Ubuntu: dracut
              if distro == "arch" then
                  table.insert(steps, {
                      name = "boot_kernel_initramfs_regenerate",
                      description = "Regenerate initramfs with mkinitcpio",
                      command = "mkinitcpio -p " .. kernel_pkg,
                      chroot = true,
                      order = 202,
                      on_distro = "arch",
                      depends_on = (config.kernel.modules and #config.kernel.modules > 0) and {"boot_kernel_modules_config"} or {"boot_kernel_install"},
                  })
              elseif distro == "debian" then
                  table.insert(steps, {
                      name = "boot_kernel_initramfs_regenerate",
                      description = "Regenerate initramfs with dracut",
                      command = "dracut -f",
                      chroot = true,
                      order = 202,
                      on_distro = "debian",
                      depends_on = (config.kernel.modules and #config.kernel.modules > 0) and {"boot_kernel_modules_config"} or {"boot_kernel_install"},
                  })
              end
        end
        
        -- Bootloader configuration
        if config.loader then
            local loader_type = config.loader.type or "systemd-boot"
            local timeout = config.loader.timeout or 10
            
            if loader_type == "systemd-boot" then
                -- Install systemd-boot
                table.insert(steps, {
                    name = "boot_loader_install_systemd",
                    description = "Install systemd-boot bootloader",
                    command = "bootctl install",
                    chroot = true,
                    order = 210,
                    on_distro = "arch",
                })
                
                -- Configure timeout
                table.insert(steps, {
                    name = "boot_loader_timeout",
                    description = "Set boot timeout to " .. timeout .. " seconds",
                    command = "echo \"timeout " .. timeout .. "\" > /boot/loader/loader.conf",
                    chroot = true,
                    order = 211,
                    on_distro = "arch",
                    depends_on = {"boot_loader_install_systemd"},
                })
            elseif loader_type == "grub" then
                  -- Install GRUB
                  local grub_pkg = distro == "arch" and "grub" or "grub-pc"
                  local grub_install = Repos.install_cmd(distro, grub_pkg)
                  
                  table.insert(steps, {
                      name = "boot_loader_install_grub",
                      description = "Install GRUB bootloader",
                      command = grub_install,
                      chroot = true,
                      order = 210,
                  })
                
                -- Configure GRUB timeout
                table.insert(steps, {
                    name = "boot_loader_grub_timeout",
                    description = "Set GRUB timeout to " .. timeout .. " seconds",
                    command = "sed -i 's/GRUB_TIMEOUT=.*/GRUB_TIMEOUT=" .. timeout .. "/' /etc/default/grub",
                    chroot = true,
                    order = 211,
                    depends_on = {"boot_loader_install_grub"},
                })
            end
            
            -- Loader include files
            if config.loader.include and #config.loader.include > 0 then
                for i, include_entry in ipairs(config.loader.include) do
                     -- Clean entry name for step naming (remove .conf extension if present)
                     local entry_name = include_entry:gsub("%.conf$", ""):gsub("[/-]", "_")
                     
                     table.insert(steps, {
                         name = "boot_loader_include_" .. entry_name,
                         description = "Add loader include: " .. include_entry,
                         command = "echo \"include " .. include_entry .. "\" >> /boot/loader/loader.conf",
                         chroot = true,
                         order = 212 + i,
                         depends_on = {"boot_loader_timeout"} or {"boot_loader_grub_timeout"},
                     })
                 end
             end
         end
        
        return steps
    end
}

return module
