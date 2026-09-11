-- KodOS Configuration Schema (Lua)
-- Single source of truth for all configuration sections
-- Used by: planner, section modules, validator, CLI

local Schema = {}

-- ============================================================================
-- BASE_DISTRIBUTION
-- ============================================================================
Schema.base_distribution = {
    type = "string",
    required = true,
    description = "Base Linux distribution to install.",
    enum = {"arch", "debian"},
}

-- ============================================================================
-- REPOS
-- ============================================================================
Schema.repos = {
    type = "dict",
    required = false,
    description = "Repository definitions (package sources).",
    fields = {
        -- REPO_NAME is a dynamic key, each value is created by repos.* functions
        -- This is a placeholder showing the structure
    }
}

-- ============================================================================
-- DEVICES
-- ============================================================================
Schema.devices = {
    type = "dict",
    required = false,
    description = "Disk and partition definitions for system installation.",
    fields = {
        -- DISK_NAME is a dynamic key, each value is created by disk.disk_definition()
        -- This is a placeholder showing the structure
    }
}

-- ============================================================================
-- BOOT
-- ============================================================================
Schema.boot = {
    type = "dict",
    required = false,
    description = "Kernel and bootloader configuration.",
    
    fields = {
        kernel = {
            type = "dict",
            required = false,
            description = "Kernel package and loadable modules.",
            
            fields = {
                package = {
                    type = "string",
                    required = false,
                    default = "linux",
                    description = "Kernel package name (e.g., 'linux', 'linux-lts', 'linux-hardened').",
                },
                modules = {
                    type = "list",
                    required = false,
                    description = "List of kernel modules to load at boot (for initramfs).",
                }
            }
        },
        
        loader = {
            type = "dict",
            required = false,
            description = "Bootloader configuration.",
            
            fields = {
                type = {
                    type = "string",
                    required = false,
                    default = "systemd-boot",
                    enum = {"systemd-boot", "grub"},
                    description = "Bootloader type.",
                },
                timeout = {
                    type = "number",
                    required = false,
                    default = 10,
                    description = "Boot menu timeout in seconds.",
                },
                include = {
                    type = "list",
                    required = false,
                    description = "Additional loader configuration files to include.",
                }
            }
        }
    }
}

-- ============================================================================
-- HARDWARE
-- ============================================================================
Schema.hardware = {
    type = "dict",
    required = false,
    description = "Hardware features and configurations.",
    
    fields = {
        pipewire = {
            type = "dict",
            required = false,
            description = "PipeWire audio system (replaces PulseAudio).",
            
            fields = {
                enable = {
                    type = "boolean",
                    required = false,
                    default = false,
                    description = "Enable PipeWire.",
                },
                extra_packages = {
                    type = "list",
                    required = false,
                    description = "Additional PipeWire packages (e.g., ALSA/PulseAudio compatibility).",
                }
            }
        },
        
        sane = {
            type = "dict",
            required = false,
            description = "SANE scanner support (Scanner Access Now Easy).",
            
            fields = {
                enable = {
                    type = "boolean",
                    required = false,
                    default = false,
                    description = "Enable SANE scanner support.",
                },
                extra_packages = {
                    type = "list",
                    required = false,
                    description = "Additional SANE packages and scanner backends.",
                }
            }
        }
    }
}

-- ============================================================================
-- LOCALE
-- ============================================================================
Schema.locale = {
    type = "dict",
    required = false,
    description = "Localization settings (language, timezone, environment variables).",
    
    fields = {
        locale = {
            type = "dict",
            required = false,
            description = "Locale settings.",
            
            fields = {
                default = {
                    type = "string",
                    required = false,
                    default = "en_US.UTF-8 UTF-8",
                    description = "Default system locale (format: 'en_US.UTF-8 UTF-8').",
                },
                extra_generate = {
                    type = "list",
                    required = false,
                    description = "Additional locales to generate.",
                },
                extra_settings = {
                    type = "dict",
                    required = false,
                    description = "Additional locale environment variable settings.",
                }
            }
        },
        
        timezone = {
            type = "string",
            required = false,
            description = "System timezone (IANA format: 'America/New_York', 'Europe/London').",
        },
        
        keymap = {
            type = "string",
            required = false,
            default = "us",
            description = "Console keyboard layout.",
        }
    }
}

-- ============================================================================
-- NETWORK
-- ============================================================================
Schema.network = {
    type = "dict",
    required = false,
    description = "Network configuration (hostname, IPv6).",
    
    fields = {
        hostname = {
            type = "string",
            required = false,
            description = "System hostname (computer name on network).",
        },
        
        ipv6 = {
            type = "boolean",
            required = false,
            default = true,
            description = "Enable IPv6 support.",
        }
    }
}

-- ============================================================================
-- USERS
-- ============================================================================
Schema.users = {
    type = "dict",
    required = false,
    description = "User accounts (login, shell, groups, home configuration).",
    
    fields = {
        -- USERNAME is dynamic key; inside each user config are optional nested blocks:
        identity = {
            type = "dict",
            required = false,
            description = "User identity information (name, password, groups).",
            
            fields = {
                name = {
                    type = "string",
                    required = false,
                    description = "User's full name (GECOS field).",
                },
                hashed_password = {
                    type = "string",
                    required = false,
                    description = "User's password hash (bcrypt, argon2, or sha512).",
                },
                groups = {
                    type = "list",
                    required = false,
                    description = "List of groups the user belongs to.",
                }
            }
        },
        
        ssh_keys = {
            type = "dict",
            required = false,
            description = "SSH key configuration for the user.",
            
            fields = {
                enabled = {
                    type = "boolean",
                    required = false,
                    default = false,
                    description = "Enable SSH key authentication.",
                },
                authorized = {
                    type = "list",
                    required = false,
                    description = "List of authorized public SSH keys.",
                }
            }
        },
        
        dotfiles = {
            type = "dict",
            required = false,
            description = "Dotfiles repository configuration.",
            
            fields = {
                repo_url = {
                    type = "string",
                    required = false,
                    description = "Git repository URL for dotfiles.",
                },
                source_dir = {
                    type = "string",
                    required = false,
                    description = "Directory within repo containing dotfiles.",
                },
                deploy_tool = {
                    type = "string",
                    required = false,
                    description = "Deployment tool (e.g., 'stow', 'yadm', 'chezmoi').",
                }
            }
        },
        
        programs = {
            type = "dict",
            required = false,
            description = "User-specific program configurations (nested program configs).",
        },
        
        services = {
            type = "dict",
            required = false,
            description = "User-specific service configurations (nested service configs).",
        },
        
        home_config = {
            type = "dict",
            required = false,
            description = "Home directory configuration (dotfiles repositories, etc).",
            
            fields = {
                dotfiles_repos = {
                    type = "list",
                    required = false,
                    description = "List of dotfiles repository URLs for the user's home.",
                }
            }
        }
    }
}

-- ============================================================================
-- DESKTOP
-- ============================================================================
Schema.desktop = {
    type = "dict",
    required = false,
    description = "Desktop environment selection (GNOME, KDE Plasma, XFCE, etc.).",
    
    fields = {
        environment = {
            type = "string",
            required = false,
            description = "Desktop environment (e.g., 'gnome', 'plasma', 'xfce', 'cosmic').",
        },
        
        enable = {
            type = "boolean",
            required = false,
            default = true,
            description = "Enable desktop environment installation.",
        },
        
        display_manager = {
            type = "string",
            required = false,
            description = "Display manager (login screen) - e.g., 'gdm', 'sddm', 'lightdm'.",
        },
        
        environments = {
            type = "dict",
            required = false,
            description = "Desktop environment configurations for specific DE types.",
            
            fields = {
                gnome = {
                    type = "dict",
                    required = false,
                    description = "GNOME-specific configuration.",
                },
                
                plasma = {
                    type = "dict",
                    required = false,
                    description = "KDE Plasma-specific configuration.",
                },
                
                cosmic = {
                    type = "dict",
                    required = false,
                    description = "COSMIC-specific configuration.",
                },
                
                budgie = {
                    type = "dict",
                    required = false,
                    description = "Budgie-specific configuration.",
                },
                
                pantheon = {
                    type = "dict",
                    required = false,
                    description = "Pantheon (Elementary OS)-specific configuration.",
                }
            }
        }
    }
}

-- ============================================================================
-- FONTS
-- ============================================================================
Schema.fonts = {
    type = "dict",
    required = false,
    description = "Font packages to install (monospace, sans-serif, CJK, emoji).",
    
    fields = {
        monospace = {
            type = "list",
            required = false,
            description = "Monospace font packages.",
        },
        
        sans_serif = {
            type = "list",
            required = false,
            description = "Sans-serif font packages.",
        },
        
        emoji = {
            type = "list",
            required = false,
            description = "Emoji font packages.",
        },
        
        enable = {
            type = "boolean",
            required = false,
            default = true,
            description = "Enable font installation.",
        },
        
        font_dir = {
            type = "string",
            required = false,
            description = "Custom font directory path for user-installed fonts.",
        },
        
        packages = {
            type = "list",
            required = false,
            description = "Additional font packages to install.",
        }
    }
}

-- ============================================================================
-- PACKAGES
-- ============================================================================
Schema.packages = {
    type = "list",
    required = false,
    description = "List of system packages to install (package manager names).",
}

-- ============================================================================
-- SERVICES
-- ============================================================================
Schema.services = {
    type = "dict",
    required = false,
    description = "System services to enable/start (e.g., ssh, nginx, docker).",
    
    fields = {
        -- SERVICE_NAME is dynamic key; inside each service config:
        --   enable: boolean (optional, enable on boot)
        --   start: boolean (optional, start immediately)
        --   config: service configuration block with service_name, packages, settings
        
        config = {
            type = "dict",
            required = false,
            description = "Service configuration block (service_name, packages, settings).",
            
            fields = {
                service_name = {
                    type = "string",
                    required = false,
                    description = "Override systemd service name (if different from config key).",
                },
                
                packages = {
                    type = "dict",
                    required = false,
                    description = "Service packages configuration (main and extra packages).",
                    
                    fields = {
                        main = {
                            type = "string",
                            required = false,
                            description = "Main package providing the service.",
                        },
                        
                        extra = {
                            type = "list",
                            required = false,
                            description = "List of additional packages for the service.",
                        }
                    }
                },
                
                settings = {
                    type = "dict",
                    required = false,
                    description = "Service-specific settings (untyped dict for flexibility).",
                }
            }
        },
        
        systemd = {
            type = "dict",
            required = false,
            description = "Systemd-specific configuration (mounts, units).",
            
            fields = {
                mounts = {
                    type = "dict",
                    required = false,
                    description = "Systemd mount definitions.",
                },
                
                units = {
                    type = "dict",
                    required = false,
                    description = "Systemd unit definitions.",
                }
            }
        }
    }
}

-- ============================================================================
-- PROGRAMS
-- ============================================================================
Schema.programs = {
    type = "dict",
    required = false,
    description = "Program configurations at system level (custom programs with install logic).",
    
    fields = {
        -- PROGRAM_NAME is dynamic key; inside each program config:
        -- enable: boolean (optional)
        -- Other fields depend on program's own schema
    }
}

-- ============================================================================
-- VALIDATION FUNCTIONS
-- ============================================================================

--- Validate a value against a schema definition
-- @param schema_def Table with type, required, enum, default, fields
-- @param value The value to validate
-- @return Boolean true if valid, false otherwise
-- @return String error message if invalid
function Schema:validate_field(schema_def, value)
    if not schema_def then
        return true
    end
    
    -- Required field check
    if schema_def.required and value == nil then
        return false, "Required field is missing"
    end
    
    -- Optional field - nil is OK
    if value == nil then
        return true
    end
    
    -- Type validation
    local lua_type = type(value)
    
    if schema_def.type == "string" then
        if lua_type ~= "string" then
            return false, "Expected string, got " .. lua_type
        end
    elseif schema_def.type == "number" then
        if lua_type ~= "number" then
            return false, "Expected number, got " .. lua_type
        end
    elseif schema_def.type == "boolean" then
        if lua_type ~= "boolean" then
            return false, "Expected boolean, got " .. lua_type
        end
    elseif schema_def.type == "list" then
        if lua_type ~= "table" then
            return false, "Expected list, got " .. lua_type
        end
    elseif schema_def.type == "dict" then
        if lua_type ~= "table" then
            return false, "Expected dict, got " .. lua_type
        end
    end
    
    -- Enum validation
    if schema_def.enum then
        local is_valid = false
        for _, enum_val in ipairs(schema_def.enum) do
            if value == enum_val then
                is_valid = true
                break
            end
        end
        if not is_valid then
            return false, "Value must be one of: " .. table.concat(schema_def.enum, ", ")
        end
    end
    
    -- Nested field validation
    if schema_def.fields and lua_type == "table" then
        for field_name, field_schema in pairs(schema_def.fields) do
            if value[field_name] then
                local ok, err = self:validate_field(field_schema, value[field_name])
                if not ok then
                    return false, field_name .. ": " .. err
                end
            elseif field_schema.required then
                return false, "Required field '" .. field_name .. "' is missing"
            end
        end
    end
    
    return true
end

--- Get default value for a schema field
-- @param schema_def Table with type, required, default
-- @return The default value, or nil if none specified
function Schema:get_default(schema_def)
    if schema_def.default ~= nil then
        return schema_def.default
    end
    
    -- Return empty container for dicts/lists
    if schema_def.type == "dict" then
        return {}
    end
    if schema_def.type == "list" then
        return {}
    end
    
    return nil
end

--- Check if a field exists at a given path (e.g., "boot.kernel.package")
-- @param config Table with configuration
-- @param path String path like "boot.kernel.package" or table path {"boot", "kernel", "package"}
-- @return Boolean true if field exists and has a schema definition
function Schema:has_field(config, path)
    local path_parts
    if type(path) == "string" then
        path_parts = {}
        for part in path:gmatch("[^.]+") do
            table.insert(path_parts, part)
        end
    else
        path_parts = path
    end
    
    if #path_parts == 0 then
        return false
    end
    
    -- Get the top-level section
    local section_name = path_parts[1]
    local section_schema = self[section_name]
    if not section_schema then
        return false
    end
    
    -- Traverse nested fields
    local current_schema = section_schema
    for i = 2, #path_parts do
        if not current_schema.fields then
            return false
        end
        current_schema = current_schema.fields[path_parts[i]]
        if not current_schema then
            return false
        end
    end
    
    return true
end

--- Get schema definition for a field at a given path
-- @param path String path like "boot.kernel.package" or table {"boot", "kernel", "package"}
-- @return Table schema definition, or nil if not found
function Schema:get_field_schema(path)
    local path_parts
    if type(path) == "string" then
        path_parts = {}
        for part in path:gmatch("[^.]+") do
            table.insert(path_parts, part)
        end
    else
        path_parts = path
    end
    
    if #path_parts == 0 then
        return nil
    end
    
    -- Get the top-level section
    local section_name = path_parts[1]
    local current_schema = self[section_name]
    if not current_schema then
        return nil
    end
    
    -- Traverse nested fields
    for i = 2, #path_parts do
        if not current_schema.fields then
            return nil
        end
        current_schema = current_schema.fields[path_parts[i]]
        if not current_schema then
            return nil
        end
    end
    
    return current_schema
end

return Schema
