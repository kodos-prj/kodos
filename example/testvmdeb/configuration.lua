print("Demo configuration")

local disk = require("disk")
local repos = require("repos")
local configs = require("configs")

-- Extra packages
local cli = require("cli")
local development = require("development")

local use_gnome = false
local use_plasma = false
local use_cosmic = false
local use_pantheon = false

return {
    base_distribution = "debian",
    repos = {
        official = repos.deb_repo("http://ftp.ca.debian.org/debian bookworm main"),
        -- aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git"),
        flatpak = repos.flatpak_repo("flathub"),
    },

    devices = {
        disk0 = disk.disk_definition("/dev/vda", "3GB"),
    },

    boot = {
        kernel = {
            package = "linux-image-amd64",
            modules = { "xhci_pci", "ohci_pci", "ehci_pci", "virtio_pci", "ahci", "usbhid", "sr_mod", "virtio_blk" },
        },
        loader = {
            type = "systemd-boot",
            -- type = "grub",
            timeout = 10,
            include = { "memtest86+" },
        },
    },

    hardware = {
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
            default = "en_CA.UTF-8 UTF-8",
            extra_generate = {
                "en_US.UTF-8 UTF-8", "en_GB.UTF-8 UTF-8"
            },
            extra_settings = {
                LC_ADDRESS = "en_CA.UTF-8",
                LC_IDENTIFICATION = "en_CA.UTF-8",
                LC_MEASUREMENT = "en_CA.UTF-8",
                LC_MONETARY = "en_CA.UTF-8",
                LC_NAME = "en_CA.UTF-8",
                LC_NUMERIC = "en_CA.UTF-8",
                LC_PAPER = "en_CA.UTF-8",
                LC_TELEPHONE = "en_CA.UTF-8",
                LC_TIME = "en_CA.UTF-8",
            },
        },
        keymap = "us",
        timezone = "America/Edmonton",
    },

    network = {
        hostname = "testvm",
        ipv6 = true,
    },

    users = {
        root = {
            no_password = true,
            shell = "/bin/bash",
        },
        abuss = {
            name = "Antal Buss",
            -- password = "changeme",
            hashed_password =
            "$6$q5r7h6qJ8nRats.X$twRR8mUf5y/oKae4doeb6.aXhPhh4Z1ZcAz5RJG38MtPRpyFjuN8eCt9GW.a20yZK1O8OvVPtJusVHZ9I8Nk/.",
            shell = "/bin/bash",
            extra_groups = map({ "audio", "input", "networkmanager", "users", "video", "wheel", "sudo" }), -- .. if_true(use_virtualization, { "docker", "podman", "libvirt" });

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

                fish = {
                    enable = true,
                },

                neovim = {
                    enable = true,
                    deploy_config = true,
                },

                emacs = {
                    enable = true,
                    -- package = "emacs-wayland",
                    deploy_config = true,
                },

                -- Gnome dconf configuration
                dconf = {
                    enable = use_gnome,
                    config = configs.dconf(require("gnome")),
                },
            },

            deploy_configs = {
                "home", -- General config for home directory (face, background, etc.)
                "gtk",  -- GTK themes
            },

            services = {
                syncthing = {
                    enable = true,
                    config = configs.syncthing({
                        service_name = "syncthing",
                        options =
                        "'--no-browser' '--no-restart' '--logflags=0' '--gui-address=0.0.0.0:8384' '--no-default-folder'",
                    }),
                    -- extra_packages = { "aur:syncthing-gtk" },
                }
            },

        },
    },

    desktop = {
        -- display_manager = "gdm",
        -- display_manager = "sddm",
        -- display_manager = "lightdm",
        desktop_manager = {
            gnome = {
                enable = use_gnome,
                display_manager = "gdm",
                exclude_packages = {
                    "gnome-tour", "yelp"
                },
                extra_packages = {
                    "gnome-tweaks",
                    -- "gnome-extra",
                    -- "gnome-themes-extra",
                    -- "gnome-shell-extension-appindicator",
                    -- "aur:gnome-shell-extension-dash-to-dock",
                    -- "aur:gnome-shell-extension-blur-my-shell",
                    -- "aur:gnome-shell-extension-arc-menu-git",
                    -- "aur:gnome-shell-extension-gsconnect",
                    -- "aur:nordic-theme",
                    -- "aur:whitesur-gtk-theme-git",
                    -- "aur:whitesur-icon-theme-git",
                    "flatpak:com.mattjakeman.ExtensionManager"
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

            pantheon = {
                enable = use_pantheon,
                display_manager = "lightdm",
            },
        }
    },

    fonts = {
        font_dir = true,
        packages = {
            -- "ttf-firacode-nerd",
            -- "ttf-nerd-fonts-symbols",
            -- "ttf-nerd-fonts-symbols-common",
            -- "ttf-sourcecodepro-nerd",
            -- "ttf-fira-sans",
            -- "ttf-fira-code",
            -- "ttf-liberation",
            -- "noto-fonts-emoji",
            -- "adobe-source-serif-fonts",
            -- "ttf-ubuntu-font-family",
            -- "aur:ttf-work-sans",
        },
    },

    packages = list({
        "iw",
        "stow",
        "mc",
        "less",
        "neovim",
        "htop",
        -- "libgtop",
        -- "uv",
        -- "python-invoke",
        "git",
        -- "poetry",
        "neofetch",
        -- "helix",
        -- "ghostty",
        -- AUR packages
        -- "aur:visual-studio-code-bin",
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
        -- "vulkan-virtio",
        -- "zed",
    }),
    -- ..
    -- cli, -- CLI tools
    -- ..
    -- development, -- Development tools

    services = {
        -- Firmware update
        fwupd = { enable = true },

        -- TODO: Maybe move inside network
        networkmanager = {
            enable = true,
            service_name = "NetworkManager",
            package = "network-manager",
        },

        openssh = {
            enable = true,
            service_name = "sshd",
            package = "openssh-server",
            settings = {
                PermitRootLogin = false,
            }
        },

        cups = {
            enable = true,
            -- extra_packages = { "gutenprint", "aur:brother-dcp-l2550dw" },
        },

        -- https://wiki.archlinux.org/title/Bluetooth
        bluetooth = {
            enable = true,
            service_name = "bluetooth",
            package = "bluez",
        },

        systemd_mount = {
            services = {
                data = configs.mount({
                    enable = true,
                    name = "mnt-data",
                    type = "cifs",
                    what = "//mmserver.lan/NAS1",
                    where = "/mnt/data",
                    description = "MMserverNAS1",
                    options =
                    "vers=2.1,credentials=/etc/samba/mmserver-cred,iocharset=utf8,rw,x-systemd.automount,uid=1000",
                    after = "network.target",
                    wanted_by = "multi-user.target",
                    automount = true,
                    automount_config = "TimeoutIdleSec=0",
                }),

                library = configs.mount({
                    enable = true,
                    name = "mnt-library",
                    type = "nfs",
                    what = "homenas2.lan:/data/Documents",
                    where = "/mnt/library/",
                    description = "Document library",
                    options = "noatime,x-systemd.automount,noauto",
                    after = "network.target",
                    wanted_by = "multi-user.target",
                    automount = true,
                    automount_config = "TimeoutIdleSec=600",
                })
            }
        },
    }
}
