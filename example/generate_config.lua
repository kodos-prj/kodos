-- Program Configuration generation

function config_git(config)
    user_name = config.user_name
    user_email = config.user_email
    return { 
        command = "git config --global user.name \"" .. user_name .. "\" && git config --global user.email \"" .. user_email .. "\""
    }
end

return {
    config_git = config_git
}