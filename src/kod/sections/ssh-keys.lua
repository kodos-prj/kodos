-- SSH Keys section module - SSH key management
-- Handles authorized SSH keys setup for users

local Schema = require('kod.core.schema')

local module = {
    schema = Schema.users,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Iterate over each user account
        for username, user_config in pairs(config) do
            if type(user_config) == "table" and user_config.ssh_keys then
                local ssh_keys = user_config.ssh_keys
                
                if ssh_keys.enabled then
                    -- Create .ssh directory and set permissions
                    table.insert(steps, {
                        name = "ssh_keys_" .. username .. "_init",
                        description = "Initialize SSH directory for user " .. username,
                        command = "mkdir -p /home/" .. username .. "/.ssh && chmod 700 /home/" .. username .. "/.ssh && chown " .. username .. ":" .. username .. " /home/" .. username .. "/.ssh",
                        order = 480 + (tonumber(username:match("%d+")) or 0),
                    })
                    
                    -- Add each authorized SSH key
                     if ssh_keys.authorized and #ssh_keys.authorized > 0 then
                         for i, key in ipairs(ssh_keys.authorized) do
                             table.insert(steps, {
                                 name = "ssh_keys_" .. username .. "_authorize_" .. i,
                                 description = "Add authorized SSH key " .. i .. " for user " .. username,
                                 command = "echo \"" .. key .. "\" >> /home/" .. username .. "/.ssh/authorized_keys",
                                 order = 481 + i + (tonumber(username:match("%d+")) or 0),
                                 depends_on = {"ssh_keys_" .. username .. "_init"},
                             })
                         end
                        
                        -- Set proper permissions on authorized_keys file
                        table.insert(steps, {
                            name = "ssh_keys_" .. username .. "_permissions",
                            description = "Set permissions on authorized_keys for user " .. username,
                            command = "chmod 600 /home/" .. username .. "/.ssh/authorized_keys && chown " .. username .. ":" .. username .. " /home/" .. username .. "/.ssh/authorized_keys",
                            order = 485 + (tonumber(username:match("%d+")) or 0),
                        })
                    end
                end
            end
        end
        
        return steps
    end
}

return module
