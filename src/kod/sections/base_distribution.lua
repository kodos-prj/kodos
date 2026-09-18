-- Base distribution section module - validates distribution choice
-- No steps generated, only validation and storage of distro choice

local Schema = require('kod.core.schema')

local module = {
    schema = Schema.base_distribution,
    
    emit_steps = function(config, distro)
        -- No steps generated for base_distribution
        -- This section only stores the distro choice for use by other sections
        return {}
    end
}

return module
