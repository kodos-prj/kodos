print("Eszkoz configuration")
-- require("core.lua")
-- package.path = '../example/?.lua;' .. package.path

disk = require("disk")
repos = require("repos")
configs = require("configs")

-- Extra packages
cli = require("cli")
development = require("development")

local use_gnome = true
local use_plasma = false
local use_cosmic = false

return {
    repos = {
        official = repos.arch_repo("https://mirror.rackspace.com/archlinux"),
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git"),
        flatpak = repos.flatpak_repo("flathub"),
    },

    devices = {
        -- disk0 = disk.disk_definition("/dev/nvme0n1", "34GB"),
        disk0 = disk.disk_definition("/dev/vda", "3GB"),
    },

    -- bootloader = {
    --     type = "systemd-boot",
    --     location = "/boot/efi"
    -- },

    boot = {
        kernel = {
            package = "linux-lts";
            modules = { "xhci_pci", "ohci_pci", "ehci_pci", "virtio_pci", "ahci", "usbhid", "sr_mod", "virtio_blk"};
        };
        loader = {
            type = "systemd-boot";
            -- type = "grub",
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
            default = "en_CA.UTF-8 UTF-8";
            extra_generate = {
                "en_US.UTF-8 UTF-8", "en_GB.UTF-8 UTF-8"
            };
            extra_settings = {
                    LC_ADDRESS = "en_CA.UTF-8";
                    LC_IDENTIFICATION = "en_CA.UTF-8";
                    LC_MEASUREMENT = "en_CA.UTF-8";
                    LC_MONETARY = "en_CA.UTF-8";
                    LC_NAME = "en_CA.UTF-8";
                    LC_NUMERIC = "en_CA.UTF-8";
                    LC_PAPER = "en_CA.UTF-8";
                    LC_TELEPHONE = "en_CA.UTF-8";
                    LC_TIME = "en_CA.UTF-8";
            };
        };
        keymap = "us";
        timezone = "America/Edmonton";
    };

    network = {
        hostname = "testvm";
        ipv6 = true;
    };

    users = {
        root = {
            no_password = true,
            shell = "/bin/bash",
        },
        abuss = {
            name = "Antal Buss",
            hashed_password = "$6$q5r7h6qJ8nRats.X$twRR8mUf5y/oKae4doeb6.aXhPhh4Z1ZcAz5RJG38MtPRpyFjuN8eCt9GW.a20yZK1O8OvVPtJusVHZ9I8Nk/.",
            shell = "/usr/bin/fish",
            extra_groups = map({ "audio", "input", "networkmanager", "users", "video", "wheel" }); -- .. if_true(use_virtualization, { "docker", "podman", "libvirt" }); 
            openssh_authorized = {
                keys = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDOA6V+TZJ+BmBAU4FB0nbhYQ9XOFZwCHdwXTuQkb77sPi6fVcbzso5AofUc+3DhfN56ATNOOslvjutSPE8kIp3Uv91/c7DE0RHoidNl3oLre8bau2FT+9AUTZnNEtWH/qXp5+fzvGk417mSL3M5jdoRwude+AzhPNXmbdAzn08TMGAkjGrMQejXItcG1OhXKUjqeLmB0A0l3Ac8DGQ6EcSRtgPCiej8Boabn21K2OBfq64KwW/MMh/FWTHndyBF/lhfEos7tGPvrDN+5G05oGjf0fnMOxsmAUdTDbtOTTeMTvDwjJdzsGUluEDbWBYPNlg5wacbimkv51/Bm4YwsGOkkUTy6eCCS3d5j8PrMbB2oNZfByga01FohhWSX9bv35KAP4nq7no9M6nXj8rQVsF0gPndPK/pgX46tpJG+pE1Ul6sSLR2jnrN6oBKzhdZJ54a2wwFSd207Zvahdx3m9JEVhccmDxWltxjKHz+zChAHsqWC9Zcqozt0mDRJNalW8fRXKcSWPGVy1rfbwltiQzij+ChCQQlUG78zW8lU7Bz6FuyDsEFpZSat7jtbdDBY0a4F0yb4lkNvu+5heg+dhlKCFj9YeRDrnvcz94OKvAZW1Gsjbs83n6wphBipxUWku7y86iYyAAYQGKs4jihhYWrFtfZhSf1m6EUKXoWX87KQ== antal.buss@gmail.com"
            };
            
            dotfile_manager = configs.stow({
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

                fish = {
                    enable = true,
                };

                neovim = {
                    enable = true,
                    deploy_config = true,
                },

                emacs = {
                    enable = true,
                    package = "emacs-wayland",
                    deploy_config = true,
                },

                -- Gnome dconf configuration
                dconf = {
                    enable = use_gnome;
                    config = configs.dconf(require("gnome"));
                };
            };

            deploy_configs = {
                "home", -- General config for home directory (face, background, etc.)
                "gtk", -- GTK themes
            },

            services = {
                syncthing = {
                    enable = true;
                    config = configs.syncthing({
                        service_name = "syncthing",
                        options = "'--no-browser' '--no-restart' '--logflags=0' '--gui-address=0.0.0.0:8384' '--no-default-folder'",
                    }),
                    -- extra_packages = { "aur:syncthing-gtk" },
                }
            },

            home = map({
                -- file("face.jpg", "/home/abuss/.face");
                -- file("/home/abuss/.face"):copy("face.jpg");
                [".config/background"] = copy_file("background"),
                [".face"] = copy_file("face.jpg"),

            })
        },
    },

    desktop = {
        -- display_manager = "gdm",
        -- display_manager = "sddm",
        -- display_manager = "lightdm",
        desktop_manager = {
            gnome = {
                enable = use_gnome;
                display_manager = "gdm",
                exclude_packages = {
                    "gnome-tour", "yelp"
                },
                extra_packages = {
                    "gnome-tweaks",
                    -- "gnome-extra",
                    -- "gnome-themes-extra",
                    "gnome-shell-extension-appindicator",
                    "aur:gnome-shell-extension-dash-to-dock",
                    "aur:gnome-shell-extension-blur-my-shell",
                    "aur:gnome-shell-extension-arc-menu-git",
                    "aur:gnome-shell-extension-gsconnect",
                    "aur:nordic-theme",
                    -- "aur:whitesur-gtk-theme-git",
                    "aur:whitesur-icon-theme-git",
                },
            },
    
            plasma = {
                enable = use_plasma,
                display_manager = "sddm",
                extra_packages = {
                    "kde-applications",
                    -- "aur:plasma5-themes-whitesur-git",
                },
            },
            cosmic = {
                enable = use_cosmic,
                display_manager = "cosmic-greeter",
            },
        }
    },

    fonts = {
        font_dir = true,
        packages = {
            -- (nerdfonts.override { fonts = [ "FiraCode" "SourceCodePro" "UbuntuMono" ]; })
            "ttf-firacode-nerd",
            "ttf-nerd-fonts-symbols",
            "ttf-nerd-fonts-symbols-common",
            "ttf-sourcecodepro-nerd",
            "ttf-fira-sans",
            "ttf-fira-code",
            -- "fira-code-symbols",
            "ttf-liberation",
            "noto-fonts-emoji",
            "adobe-source-serif-fonts",
            -- "source-serif",
            "ttf-ubuntu-font-family",
            "aur:ttf-work-sans",
        },
    },

    packages = list({
        "iw",
        "stow",
        "mc",
        "less",
        "neovim",
        "htop",
        "libgtop",
        "uv",
        "python-invoke",
        "git",
        -- "poetry",
        "neofetch",
        "helix",
        "ghostty",
        -- "blueman", -- TODO: Maybe a better location is required
        -- AUR packages
        "aur:visual-studio-code-bin",
        -- "aur:floorp-bin",
        -- "aur:mission-center",
        -- Flatpak packages
        -- "flatpak:com.mattjakeman.ExtensionManager",
        -- "flatpak:com.visualstudio.code",
        -- "distrobox",
        -- "aur:quickemu",
        -- "aur:uxplay",
        -- "aur:megasync",

        "firefox",
        -- "aur:brave-bin",
        "vulkan-virtio",
        "zed",
    });
    -- ..
    -- cli -- CLI tools
    -- ..
    -- development, -- Development tools

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
            extra_packages = { "gutenprint", "aur:brother-dcp-l2550dw" },
        },
    
        -- https://wiki.archlinux.org/title/Bluetooth
        bluetooth = {
            enable = true,
            service_name = "bluetooth",
            package = "bluez",
            -- settings = {
                -- General = {
                    -- Enable = "Source,Sink,Media,Socket",
                -- },
            -- },
        },
    }
}
