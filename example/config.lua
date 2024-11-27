print("config.lua")
-- require("core.lua")
-- package.path = '../example/?.lua;' .. package.path

disk = require("disk")

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
                remove = "pacman -Rscn",
                update_db = "pacman -Sy",
            }
        },
        aur = {
            type = "aur",
            build = {
                name = "yay",
                url = "https://aur.archlinux.org/yay-bin.git",
                build_cmd = "makepkg -si --noconfirm",
            },
            commands = {
                install = "yay -S",
                update = "yay -Syu",
                remove = "yay -R",
                update_db = "yay -Sy",
                run_as_root = false,
            },
        },
    },

    devices = {
        -- disk0 = require "disk-btrfs",
        disk0 = disk.disk_definition("/dev/vda", "3GB"),
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

    hardware = {
        -- pulseaudio = { enable = false },

        sane = {
            enable = true,
            extra_packages = { "sane-airscan" },
        },
  
        -- https://wiki.archlinux.org/title/Bluetooth
        bluetooth = {
            enable = true,
            package = "bluez",
            -- settings = {
                -- General = {
                    -- Enable = "Source,Sink,Media,Socket",
                -- },
            -- },
        },

        pipewire = {
            enable = true,
            extra_packages = {
                "pipewire-alsa",
                "pipewire-pulse",
            },
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
                "gnome-extra",
                "gnome-themes-extra",
            },
        },

        plasma = {
            enable = false,
            display_manager = "sddm",
            -- exclude_packages = {
            --     "gnome-tour",
            -- }
            packages = {
                "kde-applications",
            },
        },
        cosmic = {
            enable = true,
            display_manager = "sddm",
            -- exclude_packages = {
            --     "gnome-tour",
            -- }
            -- packages = {
                -- "kde-applications",
            -- },
        },
    },

    packages = {
        "flatpak",
        -- "pipewire",
        -- "pipewire-pulse",
        "mc",
        "neovim",
        "htop",
        -- "cosmic",
        "python-invoke",
        -- "rustup",
        "git",
        "poetry",
        "blueman", -- TODO: Maybe a better location is required
        -- "aur:visual-studio-code-bin",
        -- "aur:floorp-bin",
        -- "aur:mission-center",
    },

    services = {
        -- Firmware update
        fwupd = { enable = true },
        
        -- TODO: Maybe move inside network
        networkmanager = {
            enable = true,
            service_name = "NetworkManager",
        },
        
        openssh = {
            enable = true,
            service_name = "sshd",
            settings = {
                PermitRootLogin = false,
            }
        },
    
        -- avahi = {
        --     enable = true,
        --     nssmdns = true,
        --     publish = {
        --         enable = true,
        --         domain = true,
        --         userServices = true
        --     },
        -- },
    
        cups = {
            enable = true,
            extra_packages = { "gutenprint" },
        },
    
    }
}
