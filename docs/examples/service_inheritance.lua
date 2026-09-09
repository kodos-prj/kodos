-- Service Inheritance Example: System and User-Level Programs
-- File: docs/examples/service_inheritance.lua
--
-- This example demonstrates how programs work at both system and user levels,
-- with user-level configuration inheriting from and overriding system defaults.
--
-- Key concepts shown:
-- 1. System-level services apply to all users
-- 2. User-level services override system defaults
-- 3. Service names can be user-specific (e.g., syncthing@username)
-- 4. Programs with scope="both" support both patterns

local repos = require("repos")
local disk = require("disk")
local configs = require("configs")

return {
    repos = {
        arch = repos.arch_repo("https://mirror.rackspace.com/archlinux"),
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git"),
    },

    devices = {
        disk0 = disk.disk_definition("/dev/vda", "25GB"),
    },

    boot = {
        kernel = {
            package = "linux",
            modules = { "virtio_pci", "ahci", "virtio_blk" },
        },
        loader = {
            type = "systemd-boot",
            timeout = 10,
        },
    },

    locale = {
        locale = {
            default = "en_US.UTF-8 UTF-8",
        },
        keymap = "us",
        timezone = "UTC",
    },

    network = {
        hostname = "kodos-inheritance",
        ipv6 = true,
    },

    packages = {
        "base",
        "linux-firmware",
        "htop",
        "neofetch",
    },

    -- ============================================================================
    -- SYSTEM-LEVEL PROGRAMS
    -- ============================================================================
    -- These are configured once at the system level and provide defaults for
    -- all users. Users can override these settings in their own configuration.
    -- ============================================================================

    programs = {
        -- System-level Syncthing provides a global file sync service
        -- All users can optionally override the listen address and auto_start
        syncthing = {
            enable = true,
            
            -- System-level service runs as root/system
            service = {
                enable = true,
                service_name = "syncthing"  -- System-level service name
            },
            
            -- Default configuration for all users
            listen_address = "127.0.0.1:8384",  -- Localhost only (safe default)
            auto_start = true,                   -- Auto-start on boot
        }
    },

    -- ============================================================================
    -- USER-LEVEL CONFIGURATION WITH SERVICE INHERITANCE
    -- ============================================================================
    -- Each user can:
    -- 1. Inherit system-level program settings (if not overridden)
    -- 2. Override system settings with their own values
    -- 3. Have their own user-level services (e.g., syncthing@alice)
    -- ============================================================================

    users = {
        root = {
            password = "root",
            shell = "/bin/bash",
        },

        -- ====================================================================
        -- Alice: Developer who uses system defaults
        -- ====================================================================
        -- Alice doesn't configure syncthing at user level, so she inherits
        -- the system defaults:
        -- - listen_address = 127.0.0.1:8384 (inherited from system)
        -- - auto_start = true (inherited from system)
        -- - service_name = syncthing (system service, not user-specific)
        --
        -- Her syncthing runs as part of the system service, not per-user.
        -- ====================================================================
        alice = {
            name = "Alice Developer",
            password = "alice",
            shell = "/bin/bash",
            extra_groups = { "audio", "video", "wheel" },
            
            -- Alice uses system-level syncthing, no per-user override
            programs = {
                git = {
                    user_name = "Alice Developer",
                    email = "alice@example.com"
                },
                
                neovim = {
                    python_provider = true,
                    node_provider = true
                }
                
                -- No syncthing override here - uses system settings
            }
        },

        -- ====================================================================
        -- Bob: System Administrator with per-user service
        -- ====================================================================
        -- Bob wants his own syncthing service running at user level with
        -- different settings from the system default:
        -- - His service listens on all interfaces (0.0.0.0:8384)
        -- - His service is user-scoped (syncthing@bob, not system syncthing)
        -- - His service runs as his user, not as root
        --
        -- Inheritance at work:
        -- - System level: syncthing enabled, generic configuration
        -- - User level: Bob overrides listen_address and gets user service
        -- ====================================================================
        bob = {
            name = "Bob Admin",
            password = "bob",
            shell = "/bin/bash",
            extra_groups = { "audio", "video", "wheel" },
            
            programs = {
                git = {
                    user_name = "Bob Admin",
                    email = "bob@example.com",
                    signing_key = "9A1B2C3D4E5F6A7B"
                },
                
                neovim = {
                    python_provider = true
                },
                
                -- Bob overrides syncthing configuration at user level
                syncthing = {
                    -- These settings override the system defaults:
                    listen_address = "0.0.0.0:8384",  -- Listen on all interfaces
                    auto_start = true,                 -- Still auto-start
                    
                    -- User-level service (syncthing@bob, not system syncthing)
                    service = {
                        enable = true,
                        service_name = "syncthing@bob"  -- User-specific service!
                    }
                }
                -- Note: Only listen_address is overridden
                -- auto_start inherited from system: true
            }
        },

        -- ====================================================================
        -- Carol: Team Lead with service disabled for manual control
        -- ====================================================================
        -- Carol wants syncthing installed but not running automatically.
        -- She manually starts/stops it as needed during her workday.
        --
        -- Configuration pattern:
        -- - Program enabled (config exists)
        -- - Service disabled (systemctl start required)
        -- - Settings override for her needs
        -- ====================================================================
        carol = {
            name = "Carol Team Lead",
            password = "carol",
            shell = "/bin/bash",
            extra_groups = { "audio", "video", "wheel", "networkmanager" },
            
            programs = {
                git = {
                    user_name = "Carol Team Lead",
                    email = "carol@example.com"
                },
                
                neovim = {
                    python_provider = true,
                    node_provider = true,
                    ruby_provider = true
                },
                
                -- Carol configures syncthing but doesn't auto-start it
                syncthing = {
                    -- Override from system defaults
                    listen_address = "127.0.0.1:8384",  -- Localhost only
                    
                    -- Service NOT auto-starting
                    service = {
                        enable = false  -- Carol manually starts/stops when needed
                    }
                }
            }
        },

        -- ====================================================================
        -- David: Minimal User (no syncthing)
        -- ====================================================================
        -- David just uses system-level syncthing without any user override.
        -- Since he doesn't declare syncthing in his programs section,
        -- he gets the system defaults automatically.
        -- ====================================================================
        david = {
            name = "David User",
            password = "david",
            shell = "/bin/bash",
            
            programs = {
                git = {
                    user_name = "David User",
                    email = "david@example.com"
                }
                
                -- No syncthing config - uses system defaults
                -- His system-level syncthing handles file sync for everyone
            }
        },

        -- ====================================================================
        -- Eve: Power User with service isolation
        -- ====================================================================
        -- Eve wants completely separate syncthing from the system service:
        -- - System service runs at default settings
        -- - Eve's service runs at user level on different port
        -- - Both services coexist without conflict
        -- ====================================================================
        eve = {
            name = "Eve Power User",
            password = "eve",
            shell = "/bin/bash",
            extra_groups = { "audio", "video", "wheel" },
            
            programs = {
                git = {
                    user_name = "Eve Power User",
                    email = "eve@example.com",
                    signing_key = "1A2B3C4D5E6F7G8H"
                },
                
                neovim = {
                    python_provider = true,
                    node_provider = true,
                    ruby_provider = true
                },
                
                -- Eve runs her own syncthing instance alongside the system one
                syncthing = {
                    enable = true,
                    listen_address = "0.0.0.0:8385",  -- Different port!
                    auto_start = true,
                    
                    -- Her own user-scoped service
                    service = {
                        enable = true,
                        service_name = "syncthing@eve"  -- Separate from system
                    }
                }
            }
        },
    },
}
