return {
    name = "bluetooth",
    scope = "system",
    package = "bluez",
    
    service = {
        enable = true,
        service_name = "bluetooth",
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
