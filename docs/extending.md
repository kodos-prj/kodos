# Extending KodOS

This guide covers how to extend KodOS with custom programs, package sources, and configuration helpers. KodOS is designed to be flexible and extensible without modifying the core codebase.

## Table of Contents

1. [Creating Custom Programs](#creating-custom-programs)
2. [Program Schema and Validation](#program-schema-and-validation)
3. [Program Installation Functions](#program-installation-functions)
4. [Using Custom Programs](#using-custom-programs)
5. [Creating Configuration Helpers](#creating-configuration-helpers)
6. [Plugin Discovery](#plugin-discovery)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Creating Custom Programs

Custom programs in KodOS are Lua modules that extend the builtin program registry. They allow you to define new system components without modifying the core KodOS code.

### Directory Structure

Place your custom programs in:
```
~/.kod/plugins/programs/
├── my_app.lua
├── another_program.lua
└── utilities/
    └── helper_lib.lua
```

### Basic Program Template

Here's a minimal program definition:

```lua
-- ~/.kod/plugins/programs/my_app.lua
return {
    name = "my_app",
    description = "My custom application",
    schema = {
        enable = {
            type = "boolean",
            default = false,
            description = "Enable my_app"
        },
        version = {
            type = "string",
            default = "latest",
            description = "Version to install"
        },
    },
    install = function(config, exec_fn)
        if not config.enable then
            return
        end
        -- Installation logic here
        exec_fn("pacman -S my_app")
    end,
    validate = function(config)
        if config.version and config.version ~= "latest" then
            if not config.version:match("^%d+%.%d+%.%d+$") then
                return false, "Invalid version format"
            end
        end
        return true
    end,
}
```

## Program Schema and Validation

Each program defines a schema that describes its configuration options. The schema is used for:
- Type checking
- Default value provision
- Documentation generation
- Configuration validation

### Schema Field Types

```lua
schema = {
    -- Boolean option
    enable = {
        type = "boolean",
        default = false,
        description = "Enable this program"
    },
    
    -- String option
    version = {
        type = "string",
        default = "stable",
        description = "Version to install"
    },
    
    -- Number option
    workers = {
        type = "number",
        default = 4,
        description = "Number of worker threads"
    },
    
    -- Array/List option
    packages = {
        type = "array",
        default = {},
        description = "Additional packages"
    },
    
    -- Table/Object option
    config = {
        type = "table",
        default = {},
        description = "Application configuration"
    },
}
```

### Adding Validation Rules

The `validate` function checks configuration validity:

```lua
validate = function(config)
    -- Check required fields
    if config.enable and not config.package_name then
        return false, "package_name is required when enable=true"
    end
    
    -- Validate enumerated values
    if config.log_level and not ({ 
        debug=1, info=1, warn=1, error=1 
    })[config.log_level] then
        return false, "log_level must be one of: debug, info, warn, error"
    end
    
    -- Validate numeric ranges
    if config.max_connections and (config.max_connections < 1 or config.max_connections > 1000) then
        return false, "max_connections must be between 1 and 1000"
    end
    
    -- Validate format
    if config.port and not config.port:match("^%d+$") then
        return false, "port must be a number"
    end
    
    return true
end
```

## Program Installation Functions

The `install` function performs the actual installation. It receives the validated configuration and an execution function.

### Function Signature

```lua
install = function(config, exec_fn)
    -- config: the validated configuration table
    -- exec_fn: function to execute shell commands
end
```

### Using exec_fn

The `exec_fn` parameter is a wrapper around shell execution that provides error handling and logging:

```lua
install = function(config, exec_fn)
    if not config.enable then
        return
    end
    
    -- Execute a simple command
    exec_fn("pacman -S myapp")
    
    -- With options (output to user, fail on error, etc.)
    local result = exec_fn("systemctl enable myapp")
    
    -- For critical operations that should not continue on failure
    exec_fn("mkdir -p /opt/myapp")
end
```

### Complete Example: PostgreSQL Program

```lua
return {
    name = "postgresql",
    description = "PostgreSQL database server",
    schema = {
        enable = {
            type = "boolean",
            default = false,
            description = "Enable PostgreSQL"
        },
        version = {
            type = "string",
            default = "15",
            description = "PostgreSQL version"
        },
        superuser = {
            type = "string",
            default = "postgres",
            description = "Superuser name"
        },
        data_dir = {
            type = "string",
            default = "/var/lib/postgres/data",
            description = "Data directory"
        },
    },
    
    install = function(config, exec_fn)
        if not config.enable then
            return
        end
        
        -- Install PostgreSQL package
        local pkg = "postgresql-" .. config.version
        exec_fn("pacman -S " .. pkg)
        
        -- Initialize database cluster
        exec_fn("mkdir -p " .. config.data_dir)
        exec_fn("chown " .. config.superuser .. ":" .. config.superuser .. " " .. config.data_dir)
        
        -- Initialize the database
        exec_fn("sudo -u " .. config.superuser .. " initdb -D " .. config.data_dir)
        
        -- Enable and start service
        exec_fn("systemctl enable postgresql")
        exec_fn("systemctl start postgresql")
    end,
    
    validate = function(config)
        if config.enable then
            if not config.version:match("^%d+$") then
                return false, "version must be a number (e.g., '15', '16')"
            end
            if not config.superuser:match("^[a-z_][a-z0-9_]*$") then
                return false, "superuser must be a valid Linux username"
            end
        end
        return true
    end,
}
```

## Using Custom Programs

Once you've created a custom program, use it in your configuration like any builtin program:

```lua
return {
    users = {
        myuser = {
            programs = {
                -- Builtin program
                git = {
                    enable = true,
                    config = configs.git({
                        user_name = "My Name",
                        user_email = "me@example.com",
                    })
                },
                
                -- Custom program from ~/.kod/plugins/programs/my_app.lua
                my_app = {
                    enable = true,
                    version = "1.2.3",
                    config = {
                        debug = true,
                        output_dir = "~/my_app_data"
                    }
                },
                
                -- Another custom program
                postgresql = {
                    enable = true,
                    version = "15",
                    superuser = "postgres",
                    data_dir = "/var/lib/postgres/data"
                }
            }
        }
    }
}
```

## Creating Configuration Helpers

Configuration helpers are Lua modules that provide utility functions for common configuration patterns. They're similar to NixOS option builders.

### Helper Module Structure

```lua
-- ~/.kod/plugins/configs/helpers/web_server.lua
local M = {}

M.nginx = function(options)
    return {
        enable = true,
        package = "nginx",
        config = {
            port = options.port or 80,
            server_name = options.domain or "localhost",
            root = options.document_root or "/var/www/html",
            ssl = options.ssl or false,
            ssl_cert = options.ssl_cert,
            ssl_key = options.ssl_key,
        }
    }
end

M.caddy = function(options)
    return {
        enable = true,
        package = "caddy",
        config = {
            domain = options.domain or "localhost",
            upstream = options.upstream or "127.0.0.1:8080",
            auto_https = options.auto_https ~= false,
        }
    }
end

return M
```

### Using Configuration Helpers

```lua
-- ~/.kod/configuration.lua
local webservers = require("web_server")

return {
    programs = {
        web = webservers.nginx({
            port = 8080,
            domain = "example.com",
            document_root = "/srv/www",
            ssl = true,
            ssl_cert = "/etc/ssl/certs/example.com.crt",
            ssl_key = "/etc/ssl/private/example.com.key",
        })
    }
}
```

## Plugin Discovery

KodOS automatically discovers and loads plugins from the following locations:

```
~/.kod/plugins/
├── programs/        # Custom program definitions
│   ├── *.lua       # Program modules
│   └── [dir]/      # Subdirectories allowed
├── configs/        # Configuration helpers
│   ├── *.lua
│   └── [dir]/
└── build_templates/ # Custom package build templates (Phase 5)
    ├── *.lua
    └── [dir]/
```

### Discovery Process

1. KodOS scans `~/.kod/plugins/` on startup
2. Each `.lua` file is validated for correct structure
3. Programs are added to the registry with their filenames as identifiers
4. Invalid plugins generate warnings but don't block initialization
5. Name conflicts (plugin vs. builtin) favor builtins (override-safe)

## Best Practices

### 1. Error Handling

Always validate inputs and handle errors gracefully:

```lua
install = function(config, exec_fn)
    if not config.enable then
        return
    end
    
    -- Validate required fields before using them
    if not config.username or config.username == "" then
        error("username is required")
    end
    
    -- Check dependencies
    local ok, err = exec_fn("which systemctl")
    if not ok then
        error("systemd is required but not available")
    end
end
```

### 2. Documentation

Provide clear descriptions for all schema fields:

```lua
schema = {
    enable = {
        type = "boolean",
        default = false,
        description = "Enable this program",
        longdesc = "When enabled, this program will be installed and configured. "
                  .. "It requires systemd and at least 2GB of disk space.",
    },
    -- ... more fields
}
```

### 3. Conditional Execution

Use early returns to avoid unnecessary work:

```lua
install = function(config, exec_fn)
    if not config.enable then
        return
    end
    
    -- Only reach here if enabled
    exec_fn("pacman -S myapp")
end
```

### 4. Modularity

Break large programs into separate files:

```lua
-- ~/.kod/plugins/programs/complex_app.lua
local db = require("complex_app.database")
local web = require("complex_app.webserver")
local cache = require("complex_app.cache")

return {
    name = "complex_app",
    schema = { /* ... */ },
    install = function(config, exec_fn)
        db.install(config, exec_fn)
        web.install(config, exec_fn)
        cache.install(config, exec_fn)
    end,
}
```

### 5. Version Compatibility

Be aware of KodOS version requirements:

```lua
return {
    name = "my_program",
    
    -- Optional: specify minimum KodOS version
    requires_kodos_version = "0.2.0",
    
    schema = { /* ... */ },
    install = function(config, exec_fn)
        -- Implementation
    end,
}
```

## Troubleshooting

### Plugin Not Loading

**Problem:** Your plugin doesn't appear in `kod registry list`

**Solutions:**
1. Check file location: `~/.kod/plugins/programs/yourprogram.lua`
2. Verify Lua syntax: `luac -p yourprogram.lua`
3. Check plugin logs: `kod registry list --debug`
4. Ensure return statement: plugins must return a table

### Validation Errors

**Problem:** `kod config validate` reports schema errors

**Solutions:**
1. Verify schema field names match config usage
2. Check type declarations: "string", "number", "boolean", "table", "array"
3. Test validation function independently
4. Use `kod config --schema` to inspect available options

### Installation Failures

**Problem:** Installation stops with an error

**Solutions:**
1. Add `--debug` to see full command output
2. Test `exec_fn` calls manually
3. Check for missing dependencies in your program
4. Verify execute permissions on scripts
5. Use `systemctl status` to check service status

### Permission Issues

**Problem:** "Permission denied" errors during installation

**Solutions:**
1. Run `kod` with appropriate privileges (usually `sudo`)
2. Use `exec_fn` for operations that need elevation
3. Create directories with correct ownership
4. Check file permissions after installation

## Examples

For complete working examples, see:
- [`docs/examples/custom_program.lua`](examples/custom_program.lua) - Simple program definition
- [`example/testvm/configuration.lua`](../example/testvm/configuration.lua) - Configuration using builtin and custom programs
- [`src/kod/registry/programs.py`](../src/kod/registry/programs.py) - Builtin program definitions (reference)

## See Also

- [KodOS Architecture Overview](../ARCHITECTURE_OVERVIEW.txt)
- [Program Registry Design](phase3-plugins.md)
- [Configuration System Documentation](cli-architecture.md)
