return {
    name = "fwupd",
    scope = "system",
    package = "fwupd",
    
    service = {
        enable = true,
        service_name = "fwupd",
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
