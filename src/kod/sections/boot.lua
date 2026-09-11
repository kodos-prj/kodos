-- Boot section module - kernel and bootloader configuration
-- Handles kernel package, modules, and bootloader setup

local Schema = require('kod.lib.schema')

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
            local install_cmd
            if distro == "arch" then
                install_cmd = "pacman -S --noconfirm " .. kernel_pkg
            elseif distro == "debian" then
                install_cmd = "apt-get install -y " .. kernel_pkg
            else
                return steps
            end
            
            table.insert(steps, {
                name = "boot_kernel_install",
                description = "Install kernel: " .. kernel_pkg,
                command = install_cmd,
                order = 200,
            })
            
            -- Configure kernel modules in initramfs
            if config.kernel.modules and #config.kernel.modules > 0 then
                local modules_str = table.concat(config.kernel.modules, " ")
                
                table.insert(steps, {
                    name = "boot_kernel_modules_config",
                    description = "Configure kernel modules in initramfs: " .. modules_str,
                    command = "echo 'MODULES=(" .. modules_str .. ")' > /etc/mkinitcpio.conf.d/modules.conf",
                    order = 201,
                    on_distro = "arch",
                    depends_on = {"boot_kernel_install"},
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
                    order = 210,
                    on_distro = "arch",
                })
                
                -- Configure timeout
                table.insert(steps, {
                    name = "boot_loader_timeout",
                    description = "Set boot timeout to " .. timeout .. " seconds",
                    command = "echo 'timeout " .. timeout .. "' > /boot/loader/loader.conf",
                    order = 211,
                    on_distro = "arch",
                    depends_on = {"boot_loader_install_systemd"},
                })
            elseif loader_type == "grub" then
                -- Install GRUB
                local grub_pkg = "grub"
                if distro == "arch" then
                    grub_pkg = "grub"
                elseif distro == "debian" then
                    grub_pkg = "grub-pc"
                end
                
                table.insert(steps, {
                    name = "boot_loader_install_grub",
                    description = "Install GRUB bootloader",
                    command = (distro == "arch" and "pacman -S --noconfirm " or "apt-get install -y ") .. grub_pkg,
                    order = 210,
                })
                
                -- Configure GRUB timeout
                table.insert(steps, {
                    name = "boot_loader_grub_timeout",
                    description = "Set GRUB timeout to " .. timeout .. " seconds",
                    command = "sed -i 's/GRUB_TIMEOUT=.*/GRUB_TIMEOUT=" .. timeout .. "/' /etc/default/grub",
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
                        command = "echo 'include " .. include_entry .. "' >> /boot/loader/loader.conf",
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
