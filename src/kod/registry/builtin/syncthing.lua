return {
    name = "syncthing",
    scope = "both",  -- Can be system-level (global service) or user-level (per-user sync)
    package = "syncthing",
    
    service = {
        enable = true,
        service_name = "syncthing",
        socket_activation = true,
        user_service = true,
        restart_policy = "always",
        after = {"network.target"},
        wanted_by = {"multi-user.target"}
    },
    
    schema = {
        auto_start = {
            type = "boolean",
            default = true,
            description = "Auto-start syncthing service"
        },
        listen_address = {
            type = "string",
            default = "127.0.0.1:8384",
            description = "Listen address"
        }
    },
    
    default_config = {
        auto_start = true,
        listen_address = "127.0.0.1:8384"
    },
    
    generate_config = function(self, options)
        local config = "systemctl enable syncthing"
        
        if options.auto_start then
            config = config .. "\nsystemctl start syncthing"
        end
        
        return config
    end
}
