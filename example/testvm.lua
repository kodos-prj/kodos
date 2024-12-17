print("config.lua")
-- require("core.lua")
-- package.path = '../example/?.lua;' .. package.path

disk = require("disk")
repos = require("repos")
dotmgr = require("dotfile_manager")

return {
    repos = {
        official = repos.arch_repo("https://mirror.rackspace.com/archlinux"), 
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git"),
        flatpak = repos.flatpak_repo("flathub"),
    },

    devices = {
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
        hostname = "testvm",
        ipv6 = false
    },

    users = {
        root = {
            no_password = true,
            shell = "/bin/bash",
        },
        abuss = {
            name = "Antal Buss",
            hashed_password = "$6$q5r7h6qJ8nRats.X$twRR8mUf5y/oKae4doeb6.aXhPhh4Z1ZcAz5RJG38MtPRpyFjuN8eCt9GW.a20yZK1O8OvVPtJusVHZ9I8Nk/.",
            shell = "/bin/zsh",

            dotfile_manager = dotmgr.stow({
                    source_dir = "~/.dotfiles",
                    target_dir = "~/",
                    repo_url = "http://git.homecloud.lan/abuss/dotconfig.git",
                }),

            programs = {
                git = {
                    enable = true,
                    user_email = "antal.buss@gmail.com",
                    user_name = "Antal Buss"
                },

                starship = { 
                    enable = true,
                    deploy_config = true,
                },

                zsh = {
                    enable = true,
                    autosuggestion = true,
                    enable_vfe_integration = true,
                    default_keymap = "emacs",

                    oh_my_zsh = {
                        enable = true,
                        plugins = {"sudo"},
                        theme = "lukerandall"
                    }
                },

                neovim = {
                    enable = true,
                    deploy_config = true,
                },
            },

            deploy_configs = {
                "home", -- General config for home directory (face, background, etc.)
                "gtk", -- GTK themes
            },

            services = {
                "syncthing"
            }
        },
    },

    desktop = {
        display_manager = "gdm",
        -- display_manager = "sddm",
        -- display_manager = "lightdm",
        desktop_manager = {
            gnome = {
                enable = true,
                exclude_packages = {
                    "gnome-tour", "yelp"
                },
                packages = {
                    "gnome-tweaks",
                    "gnome-extra",
                    "gnome-themes-extra",
                    "gnome-shell-extension-appindicator",
                    -- "gnome-shell-extension-dash-to-panel",
                    "aur:gnome-shell-extension-dash-to-dock"
                },
            },
    
            plasma = {
                enable = false,
                packages = {
                    "kde-applications",
                },
            },
            cosmic = {
                enable = false,
                display_manager = "sddm",
            },
        }
    },

    packages = {
        -- "bubblewrap-suid",
        -- "aur:proot",
        -- "flatpak",
        "starship",
        "zsh",
        "stow",
        "mc",
        "less",
        "neovim",
        "htop",
        "python-invoke",
        "git",
        "poetry",
        "neofetch",
        "helix",
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