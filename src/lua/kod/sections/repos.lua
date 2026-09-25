-- Repos section module - package repository configuration
-- Handles addition and configuration of package repositories

local Schema = require('kod.core.schema')
local Repos = require('kod.system.repos')

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
                -- Use emit_repo_steps to generate setup steps for this repo
                local repo_steps = Repos.emit_repo_steps(repo_name, repo_config, distro)
                if repo_steps and type(repo_steps) == "table" then
                    for _, step in ipairs(repo_steps) do
                        table.insert(steps, step)
                    end
                end
            end
        end
        
        return steps
    end
}

return module
