-- Example: User-Level Programs in KodOS
-- File: user_level_programs.lua
--
-- This example demonstrates how to use user-level programs.
-- User-level programs are configured for each user separately,
-- allowing per-user customization.
--
-- Run: kod config validate user_level_programs.lua

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
        hostname = "user-programs-example",
        ipv6 = true,
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

            -- USER-LEVEL PROGRAMS FOR ALICE
            -- These programs are configured specifically for this user
            programs = {
                -- Git: Configure with Alice's identity
                git = {
                    user_name = "Alice Developer",
                    email = "alice@example.com",
                    signing_key = "9A1B2C3D4E5F6A7B"
                },

                -- Neovim: Configure for Alice's preferences
                neovim = {
                    python_provider = true,
                    node_provider = true,
                    ruby_provider = false
                }
            }
        },

        bob = {
            name = "Bob User",
            password = "bob",
            shell = "/bin/bash",
            extra_groups = { "wheel", "audio" },

            -- USER-LEVEL PROGRAMS FOR BOB
            -- These are different from Alice's programs
            programs = {
                -- Git: Configure with Bob's identity (different from Alice)
                git = {
                    user_name = "Bob User",
                    email = "bob@company.com",
                    signing_key = "1A2B3C4D5E6F7A8B"  -- Different key
                },

                -- Neovim: Configure for Bob's preferences (different from Alice)
                neovim = {
                    python_provider = false,  -- Bob doesn't need Python
                    node_provider = true,
                    ruby_provider = true      -- Bob needs Ruby
                }
            }
        },

        charlie = {
            name = "Charlie Minimal",
            password = "charlie",
            shell = "/bin/bash",
            extra_groups = { "wheel" },

            -- Charlie uses ONLY git, not neovim
            programs = {
                git = {
                    user_name = "Charlie Minimal",
                    email = "charlie@localhost"
                }
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
-- Key Points: User-Level Programs
-- ============================================================================
--
-- 1. User-level programs are configured in: users.<username>.programs
--
-- 2. Each user can have DIFFERENT configuration for the same program
--
-- 3. Use user-level programs for:
--    - Per-user identity (git with unique name/email)
--    - Per-user preferences (neovim configuration)
--    - Per-user services (if scope="both")
--
-- 4. Programs like git (scope="user") MUST be configured at user level:
--    ✓ Correct:   users.alice.programs.git = {...}
--    ✗ Incorrect: programs.git = {...}  -- Not allowed for user-only programs
--
-- 5. Each user can customize independently:
--    - Alice: Python + Node providers
--    - Bob: Node + Ruby providers
--    - Charlie: No neovim at all
--
-- ============================================================================
