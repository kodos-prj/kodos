-- Example: Mixed System and User-Level Programs in KodOS
-- File: mixed_level_programs.lua
--
-- This example demonstrates how to use programs at both system and user levels
-- in the same configuration. This is the most common and flexible approach.
--
-- Key concept: System-level config provides defaults, user-level config overrides.
--
-- Run: kod config validate mixed_level_programs.lua

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
        hostname = "mixed-programs-example",
        ipv6 = true,
    },

    -- ========================================================================
    -- SYSTEM-LEVEL PROGRAMS
    -- These provide defaults for ALL users
    -- ========================================================================
    programs = {
        -- Syncthing at system level: provides global defaults
        -- Scope: "both" - can be overridden at user level
        syncthing = {
            auto_start = true,
            listen_address = "127.0.0.1:8384"  -- Private by default
        }
    },

    users = {
        root = {
            password = "root",
            shell = "/bin/bash",
        },

        -- ====================================================================
        -- ALICE: Uses system defaults + adds user-level customization
        -- ====================================================================
        alice = {
            name = "Alice Developer",
            password = "alice",
            shell = "/bin/bash",
            extra_groups = { "wheel", "audio" },

            programs = {
                -- Git: User-level ONLY (scope="user")
                -- Must be configured at user level, not system level
                git = {
                    user_name = "Alice Developer",
                    email = "alice@example.com",
                    signing_key = "9A1B2C3D4E5F6A7B"
                },

                -- Neovim: User-level ONLY (scope="user")
                neovim = {
                    python_provider = true,
                    node_provider = true,
                    ruby_provider = false
                },

                -- Syncthing: User-level OVERRIDE (scope="both")
                -- This OVERRIDES the system-level syncthing config:
                -- - listen_address: OVERRIDDEN to 0.0.0.0:8384 (Alice wants it accessible)
                -- - auto_start: INHERITED from system (true)
                syncthing = {
                    listen_address = "0.0.0.0:8384"  -- Override: Alice needs remote access
                    -- auto_start inherited from system: true
                }
            }
        },

        -- ====================================================================
        -- BOB: Uses system defaults, no user-level overrides
        -- ====================================================================
        bob = {
            name = "Bob User",
            password = "bob",
            shell = "/bin/bash",
            extra_groups = { "wheel", "audio" },

            programs = {
                -- Git: User-level config (different identity from Alice)
                git = {
                    user_name = "Bob User",
                    email = "bob@company.com"
                    -- No signing key for Bob
                },

                -- Neovim: User-level config (different from Alice)
                neovim = {
                    python_provider = false,
                    node_provider = true,
                    ruby_provider = false
                },

                -- Syncthing: NO USER-LEVEL CONFIG
                -- Bob inherits system defaults:
                -- - auto_start: true (from system)
                -- - listen_address: 127.0.0.1:8384 (from system)
            }
        },

        -- ====================================================================
        -- CHARLIE: Minimal setup, uses system defaults where possible
        -- ====================================================================
        charlie = {
            name = "Charlie Minimal",
            password = "charlie",
            shell = "/bin/bash",
            extra_groups = { "wheel" },

            programs = {
                -- Charlie uses ONLY git and syncthing (no neovim)
                git = {
                    user_name = "Charlie Minimal",
                    email = "charlie@localhost"
                },

                -- Syncthing: Charlie inherits system defaults
                -- No override = default config
            }
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
-- Explanation: How System and User-Level Programs Work Together
-- ============================================================================
--
-- SYSTEM LEVEL (programs = {...})
-- Provides defaults that apply to ALL users
-- ├─ Syncthing: auto_start=true, listen_address=127.0.0.1:8384
--
-- USER LEVEL (users.<name>.programs = {...})
-- Configured per-user, can override system defaults
--
-- ALICE:
--   ├─ Git (scope="user"): Alice Developer <alice@example.com>
--   ├─ Neovim (scope="user"): Python + Node enabled
--   └─ Syncthing (scope="both"):
--       └─ OVERRIDES system listen_address to 0.0.0.0:8384
--       └─ INHERITS auto_start=true from system
--
-- BOB:
--   ├─ Git (scope="user"): Bob User <bob@company.com>
--   ├─ Neovim (scope="user"): Node enabled only
--   └─ Syncthing (scope="both"):
--       └─ USES system defaults (no override)
--       └─ auto_start=true, listen_address=127.0.0.1:8384
--
-- CHARLIE:
--   ├─ Git (scope="user"): Charlie Minimal <charlie@localhost>
--   └─ Syncthing (scope="both"):
--       └─ USES system defaults (no override)
--       └─ No neovim at all
--
-- ============================================================================
-- Key Takeaways
-- ============================================================================
--
-- 1. System programs (top-level) provide DEFAULTS
-- 2. User programs (per-user) can OVERRIDE those defaults
-- 3. User-only programs (scope="user") MUST be at user level
-- 4. System-only programs (scope="system") MUST be at top level
-- 5. Both-level programs (scope="both") can be at either or both levels
-- 6. User overrides are ADDITIVE: user options override system, others inherited
--
-- ============================================================================
