print("config.lua")
-- require("core.lua")

return {
    source = {
        url = "https://mirror.rackspace.com/archlinux",
        arch = "x86_64",
        repo = { "core", "extra" },
        -- repo = {"core" },
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
        disk0 = {
            device = "/dev/vda",
            efi = true,
            efi_size = 1024,
            type = "gpt",
            filesystem = "ext4",
            partitions = {
                {
                    name = "System",
                    size = "1M",
                    type = "vfat",
                    mountpoint = "/boot",
                },
                {
                    name = "Swap",
                    size = "2G",
                    type = "swap",
                    resumeDevice = true,
                },
                {
                    name = "Root",
                    size = "30G",
                    type = "ext4",
                    mountpoint = "/",
                },
                {
                    name = "Home",
                    size = "100%",
                    type = "ext4",
                    mountpoint = "/home",
                }
            },
        },
    },

    bootloader = {
        type = "systemd-boot",
        location = "/boot/efi"
    },

    locale = {
        locale = {
            "en_US.UTF-8 UTF-8"
        },
        keymap = "us",
        timezone = "GMT-7"
    },

    network = {
        hostname = "kodos",
        ipv6 = false
    },

    users = {
        {
            name = "user",
            password = "SOME_PLAINTEXT_PASSWORD",
            shell = "bash"
        },
    },

    packages = {
        -- "base",
        "bash",
        -- "linux",
        -- "python",
        -- "python-pip",
        -- "python-virtualenv",
        -- "python-hatch",
        -- "python-lupa",
        -- "python-requests",
        -- "python-click",
        -- "python-pyzstd",
        -- "grep",
        -- "mc",
        -- "systemd",
        -- "openssl",
        -- "neovim",
        -- "libvterm",
        -- "lua51-lpeg",
        -- "ca-certificates-utils",
        -- "p11-kit",
        -- "libp11-kit"
    },

    services = {
        "systemd"
    }
}
