-- Hardware section module - configures hardware features like audio
-- Handles pipewire audio system installation and configuration

local Schema = require('kod.core.schema')
local Repos = require('kod.system.repos')

local module = {
    schema = Schema.hardware,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- PipeWire audio system
        if config.pipewire and config.pipewire.enable then
            local pipewire_packages = {"pipewire", "wireplumber"}
            
            -- Add extra packages if specified
            if config.pipewire.extra_packages then
                for _, pkg in ipairs(config.pipewire.extra_packages) do
                    table.insert(pipewire_packages, pkg)
                end
            end
            
            local pkg_list = table.concat(pipewire_packages, " ")
            
            local install_cmd = Repos.install_cmd(distro, pkg_list)
            if not install_cmd then
                return steps
            end
            
            table.insert(steps, {
                name = "hardware_pipewire_install",
                description = "Install PipeWire audio system",
                command = install_cmd,
                chroot = true,
                order = 350,
            })
            
            -- Enable pipewire service
            table.insert(steps, {
                name = "hardware_pipewire_enable",
                description = "Enable PipeWire service",
                command = "systemctl enable --global pipewire",
                chroot = true,
                order = 351,
                depends_on = {"hardware_pipewire_install"},
            })
        end
        
        -- SANE scanner support
        if config.sane and config.sane.enable then
            local sane_packages = {"sane"}
            
            -- Add extra packages if specified
            if config.sane.extra_packages then
                for _, pkg in ipairs(config.sane.extra_packages) do
                    table.insert(sane_packages, pkg)
                end
            end
            
            local pkg_list = table.concat(sane_packages, " ")
            
            local install_cmd = Repos.install_cmd(distro, pkg_list)
            if not install_cmd then
                return steps
            end
            
            table.insert(steps, {
                name = "hardware_sane_install",
                description = "Install SANE scanner support",
                command = install_cmd,
                chroot = true,
                order = 360,
            })
            
            -- Add extra packages step if any extra packages
            if config.sane.extra_packages and #config.sane.extra_packages > 0 then
                table.insert(steps, {
                    name = "hardware_sane_extra_packages",
                    description = "Install additional SANE packages: " .. table.concat(config.sane.extra_packages, ", "),
                    command = install_cmd,
                    chroot = true,
                    order = 361,
                    depends_on = {"hardware_sane_install"},
                })
            end
        end
        
        return steps
    end
}

return module
