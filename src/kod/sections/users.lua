-- Users section module - user account configuration
-- Handles user creation, shell setup, groups, and home configuration

local Schema = require('kod.lib.schema')

local module = {
    schema = Schema.users,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Iterate over each user account
        for username, user_config in pairs(config) do
            if type(user_config) == "table" then
                local shell = user_config.shell or "/bin/bash"
                local groups = user_config.groups or {}
                
                -- Create user
                local useradd_cmd = "useradd -m -s " .. shell .. " " .. username
                
                table.insert(steps, {
                    name = "users_create_" .. username,
                    description = "Create user account: " .. username,
                    command = useradd_cmd,
                    order = 600 + (tonumber(username:match("%d+")) or 0),
                })
                
                -- Add user to groups
                if #groups > 0 then
                    local groups_str = table.concat(groups, ",")
                    
                    table.insert(steps, {
                        name = "users_groups_" .. username,
                        description = "Add user " .. username .. " to groups: " .. groups_str,
                        command = "usermod -aG " .. groups_str .. " " .. username,
                        order = 601 + (tonumber(username:match("%d+")) or 0),
                        depends_on = {"users_create_" .. username},
                    })
                end
                
                -- Configure home directory (home_programs)
                if user_config.home_programs and type(user_config.home_programs) == "table" then
                    for program_name, program_config in pairs(user_config.home_programs) do
                        if type(program_config) == "table" then
                            -- Create home program config directory
                            local config_dir = "/home/" .. username .. "/.config/" .. program_name
                            
                            table.insert(steps, {
                                name = "users_home_config_" .. username .. "_" .. program_name,
                                description = "Create config directory for " .. program_name .. " in " .. username .. "'s home",
                                command = "mkdir -p " .. config_dir .. " && chown " .. username .. ":" .. username .. " " .. config_dir,
                                order = 610 + (tonumber(username:match("%d+")) or 0),
                                depends_on = {"users_create_" .. username},
                            })
                        end
                    end
                end
            end
        end
        
        return steps
    end
}

return module
