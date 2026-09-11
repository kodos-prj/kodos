-- Network section module - hostname and IPv6 configuration
-- Handles hostname setup and IPv6 enable/disable

local Schema = require('kod.lib.schema')

local module = {
    schema = Schema.network,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Hostname configuration
        if config.hostname then
            table.insert(steps, {
                name = "network_hostname_set",
                description = "Set system hostname to " .. config.hostname,
                command = "echo '" .. config.hostname .. "' > /etc/hostname",
                chroot = true,
                order = 120,
            })
            
            -- Add hostname to /etc/hosts
            table.insert(steps, {
                name = "network_hosts_file_update",
                description = "Add hostname to /etc/hosts",
                command = "echo '127.0.0.1 " .. config.hostname .. "' >> /etc/hosts",
                chroot = true,
                order = 121,
                depends_on = {"network_hostname_set"},
            })
        end
        
        -- IPv6 configuration
        if config.ipv6 == false then
            -- Disable IPv6
            table.insert(steps, {
                name = "network_ipv6_disable",
                description = "Disable IPv6 support",
                command = "echo 'net.ipv6.conf.all.disable_ipv6 = 1' >> /etc/sysctl.d/99-disable-ipv6.conf",
                chroot = true,
                order = 130,
            })
        elseif config.ipv6 == true then
            -- Enable IPv6 (may already be enabled, but ensure it)
            table.insert(steps, {
                name = "network_ipv6_enable",
                description = "Enable IPv6 support",
                command = "echo 'net.ipv6.conf.all.disable_ipv6 = 0' >> /etc/sysctl.d/99-enable-ipv6.conf",
                chroot = true,
                order = 130,
            })
        end
        
        return steps
    end
}

return module
