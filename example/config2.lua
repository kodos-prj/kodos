print("config.lua")
-- require("core.lua")
-- package.path = '../example/?.lua;' .. package.path

disk = require("disk-new")
repos = require("repos")

return {
    repos = {
        official = repos.arch_repo("https://mirror.rackspace.com/archlinux"), 
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git"),
        flatpak = repos.flatpak_repo("flathub"),
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

    desktop = {
        display_manager = "sddm",
        desktop_manager = {
            cosmic = {
                enable = true,
                display_manager = "sddm",
            },
        }
    },

    packages = {
        -- "bubblewrap-suid",
        -- "aur:proot",
        -- "flatpak",
        "mc",
        "less",
        "neovim",
        "htop",
        "python-invoke",
        "git",
        "poetry",
        -- "blueman", -- TODO: Maybe a better location is required
        -- AUR packages
        "aur:visual-studio-code-bin",
        "aur:floorp-bin",
        -- "aur:mission-center",
        -- Flatpak packages
        -- "flatpak:com.visualstudio.code",
    },

    services = {
        -- Firmware update
        -- fwupd = { enable = true },
        
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
    
        -- cups = {
        --     enable = true,
        --     extra_packages = { "gutenprint" },
        -- },
    
    }
}
