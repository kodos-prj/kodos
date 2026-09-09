return {
    name = "networkmanager",
    scope = "system",
    package = "networkmanager",
    
    service = {
        enable = true,
        service_name = "NetworkManager",
        restart_policy = "always"
    },
    
    schema = {
        type = "object",
        properties = {}
    },
    
    default_config = {},
    
    generate_config = function(self, options)
        return ""
    end
}
