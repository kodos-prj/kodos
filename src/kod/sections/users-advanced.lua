-- Users Advanced section module - advanced user account features
-- Handles user identity, SSH keys, and dotfiles configuration

local Schema = require('kod.lib.core.schema')

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
                -- Process identity block (name, password, groups)
                if user_config.identity then
                    local identity = user_config.identity
                    
                    -- Set user's full name (GECOS field)
                     if identity.name then
                         table.insert(steps, {
                             name = "users_" .. username .. "_identity_name",
                             description = "Set user " .. username .. " full name: " .. identity.name,
                             command = "usermod -c \"" .. identity.name .. "\" " .. username,
                             chroot = true,
                             order = 620 + (tonumber(username:match("%d+")) or 0),
                         })
                     end
                     
                     -- Set user password hash
                     if identity.hashed_password then
                         table.insert(steps, {
                             name = "users_" .. username .. "_identity_password",
                             description = "Set user " .. username .. " password hash",
                             command = "echo \"" .. username .. ":" .. identity.hashed_password .. "\" | chpasswd -e",
                             chroot = true,
                             order = 621 + (tonumber(username:match("%d+")) or 0),
                         })
                     end
                    
                    -- Add groups from identity (if not handled by base users module)
                    if identity.groups and #identity.groups > 0 then
                        local groups_str = table.concat(identity.groups, ",")
                        
                        table.insert(steps, {
                            name = "users_" .. username .. "_identity_groups",
                            description = "Add user " .. username .. " to groups: " .. groups_str,
                            command = "usermod -aG " .. groups_str .. " " .. username,
                            chroot = true,
                            order = 622 + (tonumber(username:match("%d+")) or 0),
                        })
                    end
                end
                
                -- Process SSH keys block
                if user_config.ssh_keys then
                    local ssh_keys = user_config.ssh_keys
                    
                    if ssh_keys.enabled then
                        -- Create .ssh directory
                        table.insert(steps, {
                            name = "users_" .. username .. "_ssh_keys_init",
                            description = "Initialize SSH directory for user " .. username,
                            command = "mkdir -p /home/" .. username .. "/.ssh && chmod 700 /home/" .. username .. "/.ssh && chown " .. username .. ":" .. username .. " /home/" .. username .. "/.ssh",
                            chroot = true,
                            order = 630 + (tonumber(username:match("%d+")) or 0),
                        })
                        
                         -- Add authorized SSH keys
                         if ssh_keys.authorized and #ssh_keys.authorized > 0 then
                             for i, key in ipairs(ssh_keys.authorized) do
                                 table.insert(steps, {
                                     name = "users_" .. username .. "_ssh_keys_add_" .. i,
                                     description = "Add authorized SSH key " .. i .. " for user " .. username,
                                     command = "echo \"" .. key .. "\" >> /home/" .. username .. "/.ssh/authorized_keys",
                                     chroot = true,
                                     order = 631 + i + (tonumber(username:match("%d+")) or 0),
                                     depends_on = {"users_" .. username .. "_ssh_keys_init"},
                                 })
                             end
                            
                            -- Set proper permissions on authorized_keys
                            table.insert(steps, {
                                name = "users_" .. username .. "_ssh_keys_perms",
                                description = "Set authorized_keys permissions for user " .. username,
                                command = "chmod 600 /home/" .. username .. "/.ssh/authorized_keys && chown " .. username .. ":" .. username .. " /home/" .. username .. "/.ssh/authorized_keys",
                                chroot = true,
                                order = 635 + (tonumber(username:match("%d+")) or 0),
                            })
                        end
                    end
                end
                
                -- Process dotfiles block
                if user_config.dotfiles then
                    local dotfiles = user_config.dotfiles
                    
                    if dotfiles.repo_url then
                        local deploy_tool = dotfiles.deploy_tool or "cp"
                        local source_dir = dotfiles.source_dir or "."
                        local repo_dir = "/tmp/dotfiles_" .. username
                        
                        -- Clone dotfiles repository
                        table.insert(steps, {
                            name = "users_" .. username .. "_dotfiles_clone",
                            description = "Clone dotfiles repository for user " .. username,
                            command = "git clone " .. dotfiles.repo_url .. " " .. repo_dir,
                            chroot = true,
                            order = 640 + (tonumber(username:match("%d+")) or 0),
                        })
                        
                        -- Deploy dotfiles
                        local deploy_cmd
                        if deploy_tool == "stow" then
                            deploy_cmd = "cd " .. repo_dir .. "/" .. source_dir .. " && stow -t /home/" .. username .. " ."
                        elseif deploy_tool == "symlink" then
                            deploy_cmd = "cd " .. repo_dir .. "/" .. source_dir .. " && find . -type f -exec ln -sf $(pwd)/{} /home/" .. username .. "/{}  \\;"
                        else
                            -- Default to cp
                            deploy_cmd = "cp -r " .. repo_dir .. "/" .. source_dir .. "/* /home/" .. username .. "/"
                        end
                        
                        table.insert(steps, {
                            name = "users_" .. username .. "_dotfiles_deploy_" .. deploy_tool,
                            description = "Deploy dotfiles for user " .. username .. " using " .. deploy_tool,
                            command = deploy_cmd,
                            chroot = true,
                            order = 641 + (tonumber(username:match("%d+")) or 0),
                            depends_on = {"users_" .. username .. "_dotfiles_clone"},
                        })
                        
                        -- Fix ownership
                        table.insert(steps, {
                            name = "users_" .. username .. "_dotfiles_ownership",
                            description = "Fix dotfiles ownership for user " .. username,
                            command = "chown -R " .. username .. ":" .. username .. " /home/" .. username,
                            chroot = true,
                            order = 642 + (tonumber(username:match("%d+")) or 0),
                            depends_on = {"users_" .. username .. "_dotfiles_deploy_" .. deploy_tool},
                        })
                    end
                end
            end
        end
        
        return steps
    end
}

return module
