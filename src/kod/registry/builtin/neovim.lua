return {
    name = "neovim",
    
    schema = {
        python_provider = {
            type = "boolean",
            default = false,
            description = "Install Python provider"
        },
        ruby_provider = {
            type = "boolean",
            default = false,
            description = "Install Ruby provider"
        },
        node_provider = {
            type = "boolean",
            default = true,
            description = "Install Node.js provider"
        }
    },
    
    default_config = {
        python_provider = false,
        ruby_provider = false,
        node_provider = true
    },
    
    generate_config = function(self, options)
        local packages = {"neovim"}
        
        -- Helper function to safely get option value
        local function get_option(key)
            local success, value = pcall(function() return options[key] end)
            return success and value or false
        end
        
        if get_option("python_provider") then
            table.insert(packages, "python-pynvim")
        end
        if get_option("ruby_provider") then
            table.insert(packages, "ruby-neovim")
        end
        if get_option("node_provider") then
            table.insert(packages, "nodejs-neovim")
        end
        
        return "pacman -S " .. table.concat(packages, " ")
    end
}
