return {
    name = "git",
    
    schema = {
        user_name = {
            type = "string",
            required = true,
            description = "Git committer name"
        },
        email = {
            type = "string",
            format = "email",
            required = true,
            description = "Git committer email"
        },
        signing_key = {
            type = "string",
            required = false,
            description = "GPG key ID for signing commits"
        }
    },
    
    default_config = {
        user_name = "Default User",
        email = "user@localhost",
        signing_key = nil
    },
    
    generate_config = function(self, options)
        local config = string.format(
            "git config --global user.name '%s'\n" ..
            "git config --global user.email '%s'",
            options.user_name,
            options.email
        )
        
        -- Safely access signing_key (may not be in options dict)
        -- Use pcall to handle KeyError from lupa
        local success, signing_key = pcall(function()
            return options.signing_key
        end)
        
        if success and signing_key ~= nil then
            config = config .. "\n" ..
                string.format("git config --global user.signingkey '%s'",
                    signing_key)
        end
        
        return config
    end
}
