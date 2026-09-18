-- Repos section module - package repository configuration
-- Handles addition and configuration of package repositories

local Schema = require('kod.core.schema')

local module = {
    schema = Schema.repos,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Iterate over each repository defined in config
        for repo_name, repo_config in pairs(config) do
            if type(repo_config) == "table" then
                -- Each repo_config should have distro-specific add functions
                -- Check if there's an add function for this distro
                local add_func_name = "add_" .. distro
                
                if repo_config[add_func_name] and type(repo_config[add_func_name]) == "function" then
                    -- Call the distro-specific add function
                    local repo_steps = repo_config[add_func_name](repo_config)
                    
                    -- Collect steps from repo configuration
                    if repo_steps and type(repo_steps) == "table" then
                        for _, step in ipairs(repo_steps) do
                            table.insert(steps, step)
                        end
                    end
                else
                    -- Fallback: try generic approach based on repo properties
                     if repo_config.url then
                         if distro == "arch" then
                             -- For Arch, add repository to pacman.conf
                             table.insert(steps, {
                                 name = "repos_add_" .. repo_name .. "_arch",
                                 description = "Add repository: " .. repo_name,
                                 command = "echo \"[" .. repo_name .. "]\" >> /etc/pacman.conf && echo \"Server = " .. repo_config.url .. "\" >> /etc/pacman.conf",
                                 order = 50,
                             })
                         elseif distro == "debian" then
                             -- For Debian, add PPA or repository
                             if repo_config.ppa then
                                 table.insert(steps, {
                                     name = "repos_add_" .. repo_name .. "_debian",
                                     description = "Add PPA: " .. repo_config.ppa,
                                     command = "add-apt-repository -y " .. repo_config.ppa .. " && apt-get update",
                                     order = 50,
                                 })
                             else
                                 table.insert(steps, {
                                     name = "repos_add_" .. repo_name .. "_debian",
                                     description = "Add repository: " .. repo_name,
                                     command = "echo \"deb " .. repo_config.url .. "\" | tee /etc/apt/sources.list.d/" .. repo_name .. ".list && apt-get update",
                                     order = 50,
                                 })
                             end
                        end
                    end
                end
            end
        end
        
        return steps
    end
}

return module
