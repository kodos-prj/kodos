-- Example: System-Level Programs in KodOS
-- File: system_level_programs.lua
--
-- This example demonstrates how to use system-level programs.
-- System-level programs are configured once for the entire system
-- and apply globally to all users.
--
-- Run: kod config validate system_level_programs.lua

local disk = require("disk")
local repos = require("repos")

return {
    repos = {
        official = repos.arch_repo("http://mirror.cpsc.ucalgary.ca/mirror/archlinux.org"),
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git"),
    },

    devices = {
        disk0 = disk.disk_definition("/dev/vda", "30GB"),
    },

    boot = {
        kernel = {
            package = "linux-lts",
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
        hostname = "system-programs-example",
        ipv6 = true,
    },

    -- SYSTEM-LEVEL PROGRAMS
    -- These programs are configured once for the entire system
    -- and apply to all users unless overridden at user level.
    programs = {
        -- Syncthing can be configured at system level to provide
        -- a global file synchronization service
        syncthing = {
            auto_start = true,
            listen_address = "127.0.0.1:8384"
        }
        
        -- Example: If you had a firewall program, it would go here:
        -- firewall = {
        --     enabled = true,
        --     default_policy = "drop",
        --     rules = { ... }
        -- }
    },

    users = {
        root = {
            password = "root",
            shell = "/bin/bash",
        },

        alice = {
            name = "Alice Developer",
            password = "alice",
            shell = "/bin/bash",
            extra_groups = { "wheel", "audio" },
            
            -- This user does NOT override syncthing settings,
            -- so she inherits the system defaults:
            -- - auto_start = true
            -- - listen_address = "127.0.0.1:8384"
        },

        bob = {
            name = "Bob User",
            password = "bob",
            shell = "/bin/bash",
            extra_groups = { "wheel", "audio" },
            
            -- This user also inherits the system syncthing defaults
        }
    },

    packages = {
        "git",
        "htop",
        "tmux"
    },

    services = {
        networkmanager = {
            enable = true,
            service_name = "NetworkManager",
        },
    }
}

-- ============================================================================
-- Key Points: System-Level Programs
-- ============================================================================
--
-- 1. System-level programs are configured in the top-level `programs` section
--
-- 2. They apply to ALL users (unless a user overrides them)
--
-- 3. Use system-level programs for:
--    - Global defaults (Syncthing listen address)
--    - System services (Syncthing as a system service)
--    - Global policies (firewall rules)
--
-- 4. To override a system program at user level:
--    Add it to: users.<username>.programs
--
--    users = {
--        alice = {
--            programs = {
--                syncthing = {
--                    listen_address = "0.0.0.0:8384"  -- Overrides system default
--                }
--            }
--        }
--    }
--
-- ============================================================================
