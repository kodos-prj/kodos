-- System Services as Programs Example
-- File: docs/examples/system_services_as_programs.lua
--
-- This example demonstrates configuring system-level services as programs.
-- These services are configured once for the entire system and apply to all users.
--
-- Services shown:
-- 1. OpenSSH - Secure Shell Server
-- 2. CUPS - Common Unix Printing System  
-- 3. NetworkManager - Network management service

local repos = require("repos")
local disk = require("disk")

return {
    repos = {
        arch = repos.arch_repo("https://mirror.rackspace.com/archlinux"),
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git"),
    },

    devices = {
        disk0 = disk.disk_definition("/dev/vda", "20GB"),
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
        hostname = "kodos-services",
        ipv6 = true,
    },

    users = {
        root = {
            password = "root",
            shell = "/bin/bash",
        },
    },

    packages = {
        "base",
        "linux-firmware",
        "htop",
        "neofetch",
    },

    -- ============================================================================
    -- SYSTEM-LEVEL SERVICES AS PROGRAMS
    -- ============================================================================
    -- These programs are configured at the system level (top-level 'programs'
    -- section). Each service is configured once and applies to the entire system.
    --
    -- Key aspects:
    -- 1. Located at top-level 'programs' section (not inside users)
    -- 2. scope = "system" means they can only be used at system level
    -- 3. service field declares the systemd service name
    -- 4. Configuration and service management are unified
    -- ============================================================================

    programs = {
        -- ====================================================================
        -- OpenSSH: Secure Shell Server
        -- ====================================================================
        -- Provides remote access to the system via SSH.
        --
        -- What this program does:
        -- - Installs openssh package
        -- - Enables and starts sshd service
        -- - Applies SSH server configuration
        --
        -- Configuration applied by this:
        -- - SSH server listens on port 2222 (non-standard for security)
        -- - Root login disabled (security best practice)
        -- - Password authentication disabled (use keys only)
        -- - Public key authentication enabled
        --
        -- After installation, connect with:
        --   ssh -p 2222 -i /path/to/private/key user@hostname
        -- ====================================================================
        openssh = {
            enable = true,
            
            -- Service configuration
            service = {
                enable = true,
                service_name = "sshd"
            },
            
            -- SSH server settings
            settings = {
                Port = 2222,                          -- Custom port
                PermitRootLogin = false,              -- Root login disabled
                PasswordAuthentication = false,       -- Only key-based auth
                PubkeyAuthentication = true,          -- Enable key auth
                X11Forwarding = false,                -- Disable X11 forwarding
                PrintMotd = true,                     -- Show MOTD on login
                UsePAM = true,                        -- Use PAM for auth
            }
        },

        -- ====================================================================
        -- CUPS: Common Unix Printing System
        -- ====================================================================
        -- Manages network printing and local printer access.
        --
        -- What this program does:
        -- - Installs cups and gutenprint packages
        -- - Enables and starts cupsd service
        -- - Makes printers available on the network
        --
        -- Configuration applied by this:
        -- - Print server accessible via cupsd daemon
        -- - Gutenprint driver for enhanced printer support
        -- - Foomatic database for additional printer drivers
        --
        -- After installation, access with:
        --   http://localhost:631 (CUPS web interface)
        --   lpstat -p -d (check connected printers)
        --   lpadmin -p printername -E -v device -m ppd-file
        -- ====================================================================
        cups = {
            enable = true,
            
            -- Service configuration
            service = {
                enable = true,
                service_name = "cupsd"
            },
            
            -- Additional printer drivers and utilities
            extra_packages = {
                "gutenprint",           -- High-quality printer drivers
                "foomatic-db",          -- Printer database
                "foomatic-db-engine",   -- Printer description engine
            }
        },

        -- ====================================================================
        -- NetworkManager: Network Management Service
        -- ====================================================================
        -- Provides automatic network configuration and management.
        --
        -- What this program does:
        -- - Installs networkmanager package
        -- - Enables and starts NetworkManager service
        -- - Manages network interfaces (ethernet, WiFi, VPN)
        --
        -- Configuration applied by this:
        -- - Automatic IP configuration (DHCP)
        -- - WiFi network management
        -- - VPN support
        --
        -- After installation, manage network with:
        --   nmcli device              (list devices)
        --   nmcli connection show     (show connections)
        --   nmcli radio wifi on/off   (control WiFi)
        --   nmtui                     (text user interface)
        -- ====================================================================
        networkmanager = {
            enable = true,
            
            -- Service configuration
            service = {
                enable = true,
                service_name = "NetworkManager"
            },
            
            -- Optional: Wi-Fi and Bluetooth support
            extra_packages = {
                "nm-connection-editor",  -- GUI for network settings
                "networkmanager-openvpn" -- VPN support
            }
        },
    },
}
