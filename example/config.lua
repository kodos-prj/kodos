print("config.lua")
-- require("core.lua")
-- package.path = '../example/?.lua;' .. package.path


return {
    source = {
        url = "https://mirror.rackspace.com/archlinux",
        arch = "x86_64",
        repo = { "core", "extra" },
        type = "arch",
    },
    -- source = {
    --     -- url = "http://ftp.ca.debian.org/debian/dists/stable/main/binary-amd64/Packages.gz",
    --     url = "http://ftp.ca.debian.org/debian/dists/stable/",
    --     -- url2 = "https://mirror.rackspace.com/archlinux",
    --     arch = "amd64",
    --     -- repo = { "main", "contrib" },
    --     repo = {"main" },
    --     type = "deb",
    -- },

    devices = {
        disk0 = require "disk",
    },

    -- bootloader = {
    --     type = "systemd-boot",
    --     location = "/boot/efi"
    -- },

    boot = {
        initrd = {
            kernel_modules = {"xhci_pci", "ohci_pci", "ehci_pci", "virtio_pci", "ahci", "usbhid", "sr_mod", "virtio_blk"},
        },
        loader = {
            type = "systemd-boot",
            timeout = 10,
            include = { "memtest86+" },
        },
    },

    locale = {
        locale = {
            default = "en_US.UTF-8 UTF-8",
        },
        keymap = "us",
        timezone = "America/Edmonton"
    },

    network = {
        hostname = "kodos",
        ipv6 = false
    },

    users = {
        abuss = {
            name = "Antal Buss",
            password = "changeme",
            shell = "bash",

            packages = {
                "helix"
            },

            services = {
                "syncthing"
            }
        },
    },

    packages = {
        "base",
        -- "bash",
        -- "coreutils",
        "linux",
        -- "pacman",
        -- "mkinitcpio",
        -- "python",
        -- "poetry",
        -- "grep",
        -- "mc",
        -- "systemd",
        -- "git",
        -- "openssl",
        -- "neovim",
        -- "libvterm",
        -- "zlib",
        -- "lua51-lpeg",
        -- "ca-certificates-utils",
        -- "p11-kit",
        -- "libp11-kit"
        -- "curl",
        -- "btrfs-progs",
        -- "dracut",
        -- "grub",
        -- "grub-btrfs",
        -- "efibootmgr",
        -- "memtest86+-efi",
        "linux-firmware",
        -- "util-linux",
        -- "strace",
        -- "pacman",
        -- "libmnl",
        -- "openssh",
        -- "networkmanager",
        -- "iptables",
    },

    services = {
        "systemd"
    }
}
