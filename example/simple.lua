print("config.lua")
-- require("core.lua")
-- package.path = '../example/?.lua;' .. package.path

disk = require("disk")
repos = require("repos")
dotmgr = require("dotfile_manager")
configs = require("configs")

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
                    config = configs.git({
                        user_name = "Antal Buss",
                        user_email = "antal.buss@gmail.com",
                    })
                },

                starship = { 
                    enable = true,
                    deploy_config = true,
                },

                zsh = {
                    enable = true,
                    deploy_config = true,
                    extra_packages = {
                        -- "zsh-syntax-highlighting",
                        "zsh-autosuggestions",
                        "zsh-completions",
                        -- "zsh-history-substring-search",
                    }
                    -- autosuggestion = true,
                    -- enable_vfe_integration = true,
                    -- default_keymap = "emacs",

                    -- oh_my_zsh = {
                    --     enable = true,
                    --     plugins = {"sudo"},
                    --     theme = "lukerandall"
                    -- }
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
                syncthing = {
                    enable = false,
                    config = configs.syncthing({
                        service_name = "syncthing",
                        options = "'--no-browser' '--no-restart' '--logflags=0' '--gui-address=0.0.0.0:8384' '--no-default-folder'",
                    }),
                    -- extra_packages = { "aur:syncthing-gtk" },
                }
            }
        },
    },

    desktop = {
        -- display_manager = "gdm",
        -- display_manager = "sddm",
        -- display_manager = "lightdm",
        desktop_manager = {
            gnome = {
                enable = false,
                exclude_packages = {
                    "gnome-tour", "yelp"
                },
                extra_packages = {
                    "gnome-tweaks",
                    -- "gnome-extra",
                    -- "gnome-themes-extra",
                    "gnome-shell-extension-appindicator",
                    "aur:gnome-shell-extension-dash-to-dock"
                },
            },
    
            plasma = {
                enable = false,
                extra_packages = {
                    "kde-applications",
                },
            },
            cosmic = {
                enable = false,
                display_manager = "cosmic-greeter",
            },
        }
    },

    fonts = {
        font_dir = true,
        packages = {
            -- -- (nerdfonts.override { fonts = [ "FiraCode" "SourceCodePro" "UbuntuMono" ]; })
            -- "ttf-firacode-nerd",
            -- "ttf-nerd-fonts-symbols",
            -- "ttf-nerd-fonts-symbols-common",
            -- "ttf-sourcecodepro-nerd",
            -- "ttf-fira-sans",
            -- "ttf-fira-code",
            -- -- "fira-code-symbols",
            -- "ttf-liberation",
            -- "noto-fonts-emoji",
            -- "adobe-source-serif-fonts",
            -- -- "source-serif",
            -- "ttf-ubuntu-font-family",
            -- "aur:ttf-work-sans",
        },
    },

    packages = {
        "stow",
        "mc",
        "less",
        "neovim",
        "htop",
        "uv",
        "python-invoke",
        "git",
        -- "poetry",
        "neofetch",
        "helix",
        -- "blueman", -- TODO: Maybe a better location is required
        -- AUR packages
        -- "aur:visual-studio-code-bin",
        -- "aur:floorp-bin",
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
    
        cups = {
            enable = false,
            extra_packages = { "gutenprint" },
        },
    
    }
}
