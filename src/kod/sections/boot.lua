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
                       on_error = "warn",  -- mkinitcpio warns about missing vconsole.conf and fsck helpers (non-fatal)
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
                       on_error = "warn",  -- dracut may warn about missing configuration (non-fatal)
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
                 
                 -- Configure timeout and default entry
                 -- Writes loader.conf with default entry and timeout (console-mode keep)
                 local entry_file = "kodos-0.conf"
                 table.insert(steps, {
                     name = "boot_loader_timeout",
                     description = "Set boot timeout to " .. timeout .. " seconds",
                     command = "echo \"default " .. entry_file .. "\" > /boot/loader/loader.conf && echo \"timeout " .. timeout .. "\" >> /boot/loader/loader.conf && echo \"console-mode keep\" >> /boot/loader/loader.conf",
                     chroot = true,
                     order = 211,
                     on_distro = "arch",
                     depends_on = {"boot_loader_install_systemd"},
                 })
                 
                 -- Create main boot entry for current generation
                 -- systemd-boot looks for .conf files in /boot/loader/entries/
                 -- IMPORTANT: Use double quotes only - executor wraps chroot commands
                 -- in single quotes (chroot /mnt sh -c '...'), so internal single
                 -- quotes would break the shell command.
                 if config.kernel then
                     local kernel_pkg = config.kernel.package or "linux"
                     -- mkinitcpio names initramfs by kernel package: linux-lts → initramfs-linux-lts.img
                     local kernel_suffix = kernel_pkg:match("^linux(.*)") or ""
                     local initramfs_name = "initramfs-linux" .. kernel_suffix .. ".img"
                     local vmlinuz_name = "vmlinuz-linux" .. kernel_suffix
                     
                     -- Write entry with multiple echo commands (avoids single quotes)
                     -- Uses UUID lookup for root device (matches fstab, robust across device reordering)
                     -- title Kodos (Generation 0)
                     -- linux /vmlinuz-linux-lts
                     -- initrd /initramfs-linux-lts.img
                     -- options root=UUID=... rw rootflags=subvol=generations/0/rootfs
                     local boot_entry_cmd = "mkdir -p /boot/loader/entries && " ..
                                            "echo \"title Kodos (Generation 0)\" > /boot/loader/entries/" .. entry_file .. " && " ..
                                            "echo \"linux /" .. vmlinuz_name .. "\" >> /boot/loader/entries/" .. entry_file .. " && " ..
                                            "echo \"initrd /" .. initramfs_name .. "\" >> /boot/loader/entries/" .. entry_file .. " && " ..
                                            "ROOT_UUID=$(lsblk -no UUID /dev/vda3) && " ..
                                            "echo \"options root=UUID=$ROOT_UUID rw rootflags=subvol=generations/0/rootfs\" >> /boot/loader/entries/" .. entry_file
                     
                     table.insert(steps, {
                         name = "boot_loader_create_entry_generation_0",
                         description = "Create systemd-boot entry for Generation 0",
                         command = boot_entry_cmd,
                         chroot = true,
                         order = 212,
                         on_distro = "arch",
                         depends_on = {"boot_loader_timeout"},
                     })
                 end
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
                          order = 213 + i,
                          depends_on = {"boot_loader_timeout"} or {"boot_loader_grub_timeout"},
                      })
                  end
              end
         end
        
        return steps
    end
}

return module
