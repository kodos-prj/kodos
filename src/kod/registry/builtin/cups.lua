return {
    name = "cups",
    scope = "system",
    package = "cups",
    
    service = {
        enable = true,
        service_name = "cupsd",
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
