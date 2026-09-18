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
    example = 'base_distribution = "arch"',
}

-- ============================================================================
-- REPOS
-- ============================================================================
Schema.repos = {
    type = "dict",
    required = false,
    description = "Repository definitions (package sources).",
    example = [[repos = {
    official = repos.arch_repo("https://mirror.example.com/archlinux"),
    aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay.git"),
}]],
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
    example = [[devices = {
    disk0 = disk.disk_definition("/dev/sda", "50GB"),
}]],
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
    example = [[boot = {
    kernel = {
        package = "linux-lts",
        modules = {"xhci_pci", "virtio_blk"},
    },
    loader = {
        type = "systemd-boot",
        timeout = 10,
    },
}]],

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
                    example = '{"xhci_pci", "virtio_blk", "ahci"}',
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
    example = [[hardware = {
    pipewire = {
        enable = true,
        extra_packages = {"pipewire-alsa", "pipewire-pulse"},
    },
}]],

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
                    example = '{"pipewire-alsa", "pipewire-pulse"}',
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
    example = [[locale = {
    locale = {
        default = "en_US.UTF-8 UTF-8",
        extra_generate = {"en_GB.UTF-8 UTF-8"},
    },
    timezone = "America/New_York",
    keymap = "us",
}]],

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
                    example = '"America/New_York"',
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
    example = [[network = {
    hostname = "mycomputer",
    ipv6 = true,
}]],

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
    example = [[users = {
    alice = {
        identity = {
            name = "Alice",
            password = "secret",  -- or hashed_password
            shell = "/bin/bash",
            groups = {"wheel"},
        },
        home_programs = {neovim = true},
    },
}]],

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
                password = {
                    type = "string",
                    required = false,
                    description = "User's plaintext password.",
                },
                hashed_password = {
                    type = "string",
                    required = false,
                    description = "User's password hash (bcrypt, argon2, or sha512).",
                },
                shell = {
                    type = "string",
                    required = false,
                    default = "/bin/bash",
                    description = "Login shell (e.g., '/bin/bash', '/bin/fish').",
                },
                groups = {
                    type = "list",
                    required = false,
                    description = "List of groups the user belongs to.",
                    example = '{"wheel", "docker"}',
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
    example = [[desktop = {
    environment = "plasma",
    enable = true,
}]],

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
    example = [[fonts = {
    monospace = {"noto-fonts-cjk"},
    enable = true,
}]],

    fields = {
        monospace = {
            type = "list",
            required = false,
            description = "Monospace font packages.",
            example = '{"noto-fonts-cjk", "liberation-fonts"}',
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
    example = 'packages = {"vim", "tmux", "git", "htop", "neofetch"}',
}

-- ============================================================================
-- SERVICES
-- ============================================================================
Schema.services = {
    type = "dict",
    required = false,
    description = "System services to enable/start (e.g., ssh, nginx, docker).",
    example = [[services = {
    ssh = { enable = true },
    nginx = { enable = true, start = true },
}]],

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
    example = [[programs = {
    neovim = { enable = true },
    git = { enable = true, config = {} },
}]],

    fields = {
        -- PROGRAM_NAME is dynamic key; inside each program config:
        -- enable: boolean (optional)
        -- Other fields depend on program's own schema
    }
}


return Schema
