-- Dotfiles section module - dotfile repository deployment
-- Handles cloning and deployment of dotfiles repositories

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
            if type(user_config) == "table" and user_config.dotfiles then
                local dotfiles = user_config.dotfiles
                
                if dotfiles.repo_url then
                    local deploy_tool = dotfiles.deploy_tool or "cp"
                    local source_dir = dotfiles.source_dir or "."
                    local repo_dir = "/tmp/dotfiles_" .. username
                    
                    -- Clone dotfiles repository
                    table.insert(steps, {
                        name = "dotfiles_" .. username .. "_clone",
                        description = "Clone dotfiles repository for user " .. username .. " from " .. dotfiles.repo_url,
                        command = "git clone " .. dotfiles.repo_url .. " " .. repo_dir,
                        order = 500 + (tonumber(username:match("%d+")) or 0),
                    })
                    
                    -- Deploy dotfiles using specified tool
                    local deploy_cmd
                    if deploy_tool == "stow" then
                        deploy_cmd = "cd " .. repo_dir .. "/" .. source_dir .. " && stow -t /home/" .. username .. " ."
                    elseif deploy_tool == "symlink" then
                        deploy_cmd = "for file in $(find " .. repo_dir .. "/" .. source_dir .. " -type f); do ln -sf $file /home/" .. username .. "/$(basename $file); done"
                    elseif deploy_tool == "chezmoi" then
                        deploy_cmd = "chezmoi -S " .. repo_dir .. " apply"
                    elseif deploy_tool == "yadm" then
                        deploy_cmd = "yadm clone " .. dotfiles.repo_url .. " --bootstrap"
                    else
                        -- Default to cp
                        deploy_cmd = "cp -r " .. repo_dir .. "/" .. source_dir .. "/* /home/" .. username .. "/ 2>/dev/null || true"
                    end
                    
                    table.insert(steps, {
                        name = "dotfiles_" .. username .. "_deploy",
                        description = "Deploy dotfiles for user " .. username .. " using " .. deploy_tool,
                        command = deploy_cmd,
                        order = 501 + (tonumber(username:match("%d+")) or 0),
                        depends_on = {"dotfiles_" .. username .. "_clone"},
                    })
                    
                    -- Fix ownership
                    table.insert(steps, {
                        name = "dotfiles_" .. username .. "_ownership",
                        description = "Fix dotfiles ownership for user " .. username,
                        command = "chown -R " .. username .. ":" .. username .. " /home/" .. username,
                        order = 502 + (tonumber(username:match("%d+")) or 0),
                        depends_on = {"dotfiles_" .. username .. "_deploy"},
                    })
                end
            end
        end
        
        return steps
    end
}

return module
