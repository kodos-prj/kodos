-- Hardware section module - configures hardware features like audio
-- Handles pipewire audio system installation and configuration

local Schema = require('kod.lib.schema')

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
            
            local install_cmd
            if distro == "arch" then
                install_cmd = "pacman -S --noconfirm " .. pkg_list
            elseif distro == "debian" then
                install_cmd = "apt-get install -y " .. pkg_list
            else
                return steps
            end
            
            table.insert(steps, {
                name = "hardware_pipewire_install",
                description = "Install PipeWire audio system",
                command = install_cmd,
                order = 350,
            })
            
            -- Enable pipewire service
            table.insert(steps, {
                name = "hardware_pipewire_enable",
                description = "Enable PipeWire service",
                command = "systemctl enable --global pipewire",
                order = 351,
                depends_on = {"hardware_pipewire_install"},
            })
        end
        
        return steps
    end
}

return module
