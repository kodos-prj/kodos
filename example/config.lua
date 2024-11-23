print("config.lua")
-- require("core.lua")
-- package.path = '../example/?.lua;' .. package.path

local function aur_helper(dry_run)
    run("yay -S --noconfirm", dry_run)
end

return {
    repos = {
        official = {
            mirror = "https://mirror.rackspace.com/archlinux",
            -- arch = "x86_64",
            repo = { "core", "extra" },
            type = "arch",
            commands = {
                install = "pacman -S",
                update = "pacman -Syu",
                remove = "pacman -R",
                update_db = "pacman -Sy",
            }
        },
        aur = {
            type = "aur",
            -- build = {
            --     name = "yay",
            --     url = "https://aur.archlinux.org/yay.git",
            --     build_cmd = "makepkg -si --noconfirm",
            -- },
            build = {
                name = "paru",
                url = "https://aur.archlinux.org/paru.git",
                build_cmd = "makepkg -si --noconfirm",
            },
            commands = {
                install = "paru -S",
                update = "paru -Syu",
                remove = "paru -R",
                update_db = "paru -Sy",
            },
        }
    },

    -- source = {
    --     url = "https://mirror.rackspace.com/archlinux",
    --     arch = "x86_64",
    --     repo = { "core", "extra" },
    --     type = "arch",
    -- },
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
        disk0 = require "disk-btrfs",
    },

    -- bootloader = {
    --     type = "systemd-boot",
    --     location = "/boot/efi"
    -- },

    boot = {
        -- initrd = {
        --     kernel_modules = {"xhci_pci", "ohci_pci", "ehci_pci", "virtio_pci", "ahci", "usbhid", "sr_mod", "virtio_blk"},
        -- },
        loader = {
            -- type = "systemd-boot",
            type = "grub",
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

    desktop_manager = {
        gnome = {
            enable = false,
            display_manager = "gdm",
            exclude_packages = {
                "gnome-tour", "yelp"
            },
            packages = {
                "gnome-tweaks",
            },
        },

        plasma = {
            enable = true,
            display_manager = "sddm",
            -- exclude_packages = {
            --     "gnome-tour",
            -- }
            packages = {
                "kde-applications",
            },
        },
    },

    packages = {
        "flatpak",
        -- "gnome",
        -- "gnome-extra",
        -- "gnome-themes-extra",
        -- "gdm",
        -- "sddm",
        -- "plasma",
        -- "kde-applications",
        "pipewire",
        "pipewire-pulse",
        -- "gnome-tweaks",
        "mc",
        "neovim",
        -- "cosmic",
        "python-invoke",
        "rustup",
        "git",
        "poetry",
        "aur:visual-studio-code-bin",
        "aur:floorp-bin",
    },

    services = {
        "systemd"
    }
}
