return {
    name = "openssh",
    scope = "system",
    package = "openssh",
    
    service = {
        enable = true,
        service_name = "sshd",
        socket_activation = false,
        user_service = false,
        restart_policy = "always",
        after = {"network.target"},
        wanted_by = {"multi-user.target"}
    },
    
    schema = {
        type = "object",
        properties = {
            PermitRootLogin = {
                type = "boolean",
                description = "Permit root login"
            },
            PasswordAuthentication = {
                type = "boolean",
                description = "Enable password authentication"
            },
            PubkeyAuthentication = {
                type = "boolean",
                description = "Enable public key authentication"
            }
        }
    },
    
    default_config = {
        PermitRootLogin = false,
        PasswordAuthentication = true,
        PubkeyAuthentication = true
    },
    
    generate_config = function(self, options)
        local config = ""
        
        if options.PermitRootLogin ~= nil then
            config = config .. string.format("PermitRootLogin %s\n", 
                options.PermitRootLogin and "yes" or "no")
        end
        
        if options.PasswordAuthentication ~= nil then
            config = config .. string.format("PasswordAuthentication %s\n", 
                options.PasswordAuthentication and "yes" or "no")
        end
        
        if options.PubkeyAuthentication ~= nil then
            config = config .. string.format("PubkeyAuthentication %s\n", 
                options.PubkeyAuthentication and "yes" or "no")
        end
        
        return config
    end
}
