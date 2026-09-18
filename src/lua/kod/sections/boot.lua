-- Boot section module - kernel and bootloader configuration
-- Handles kernel package, modules, and bootloader setup

local Schema = require('kod.core.schema')
local Repos = require('kod.system.repos')

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
            
            -- Pin initramfs modules via dracut conf BEFORE kernel install
            -- This must run before boot_kernel_install (order 200) so that the kernel's
            -- post-install hook can use this config when it runs dracut automatically
            -- KodOS root is btrfs, so btrfs is always pinned: without it the kernel hangs
            -- on /dev/disk/by-uuid at boot.
            local modules = { "btrfs" }
            for _, m in ipairs(config.kernel.modules or {}) do
                if m ~= "btrfs" then
                    table.insert(modules, m)
                end
            end
            local add_lines = {}
            for _, m in ipairs(modules) do
                table.insert(add_lines, "add_drivers+=" .. m)
            end

            table.insert(steps, {
               name = "boot_kernel_modules_config",
               description = "Configure initramfs modules: " .. table.concat(modules, " "),
               command = "mkdir -p /etc/dracut.conf.d && printf \"" .. table.concat(add_lines, "\\n") .. "\" > /etc/dracut.conf.d/kodos.conf",
               chroot = true,
               order = 199,
            })
            
            table.insert(steps, {
                name = "boot_kernel_install",
                description = "Install kernel: " .. kernel_pkg,
                command = install_cmd,
                chroot = true,
                order = 200,
            })
           
            -- Kernel/initramfs updates are dispatched system steps: the executor calls
            -- env["kernel-update"] / env["initramfs-update"], which copy vmlinuz-<kver>
            -- into /boot and generate initramfs-linux-<kver>.img.
            table.insert(steps, {
                name = "kernel-update",
                description = "Update kernel files in /boot: " .. kernel_pkg,
                command = "",
                meta = { kernel = kernel_pkg },
                order = 202,
            })
            
            table.insert(steps, {
                name = "initramfs-update",
                description = "Generate initramfs for " .. kernel_pkg,
                command = "",
                meta = { kernel = kernel_pkg },
                order = 203,
            })
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
                 
                 -- The boot entry (.conf + loader.conf) is written by the dispatched
                 -- boot-entry system step: kver comes from the installed kernel and the
                 -- root UUID from the generated fstab (single source of truth).
                 if config.kernel then
                     local kernel_pkg = config.kernel.package or "linux"
                     table.insert(steps, {
                         name = "boot-entry",
                         description = "Create systemd-boot entry for Generation 0",
                         command = "",
                         meta = { kernel = kernel_pkg },
                         order = 212,
                         on_distro = "arch",
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
                      })
                 end
             end
         end
        
        return steps
    end
}

return module
