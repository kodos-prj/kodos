print("Demo minimal configuration")

local disk = require("disk")
local repos = require("repos")
local configs = require("configs")

-- Extra packages
-- local cli = require("cli")
-- local development = require("development")

-- local use_gnome = false
-- local use_plasma = false
-- local use_cosmic = false
-- local use_pantheon = false

return {
    -- base_distribution = "pistacho", 

    repos = {
        -- official = repos.arch_repo("https://mirror.rackspace.com/archlinux"),
        official = repos.arch_repo("http://mirror.cpsc.ucalgary.ca/mirror/archlinux.org"),
        -- pith resolves AUR packages natively
        -- aur = repos.aur_repo("pith"),
        flatpak = repos.flatpak_repo("flathub"),
    },

    devices = {
        disk0 = disk.disk_definition("/dev/vda", "3GB"),
    },

    boot = {
        kernel = {
            package = "linux",
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
            -- no_password = true,
            password = "root",
            shell = "/bin/bash",
        },
        abuss = {
            name = "Antal Buss",
            password = "abuss",
            -- hashed_password = "$6$q5r7h6qJ8nRats.X$twRR8mUf5y/oKae4doeb6.aXhPhh4Z1ZcAz5RJG38MtPRpyFjuN8eCt9GW.a20yZK1O8OvVPtJusVHZ9I8Nk/.",
            shell = "/usr/bin/fish",
            extra_groups = list({ "audio", "input", "network", "users", "video", "wheel" }), -- .. if_true(use_virtualization, { "docker", "podman", "libvirt" });

            dotfile_manager = configs.stow({
                source_dir = "~/.dotfiles",
                target_dir = "~/",
                repo_url = "https://github.com/abuss/dotconfig.git",
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
                    enable = false,
                    deploy_config = true,
                },

                fish = {
                    enable = false,
                },

                neovim = {
                    enable = false,
                    deploy_config = true,
                },

                helix = {
                    enable = false,
                    deploy_config = true,
                },

                -- emacs = {
                --     enable = true,
                --     package = "emacs-wayland",
                --     deploy_config = true,
                -- },

                -- Gnome dconf configuration
                -- dconf = {
                --     enable = use_gnome,
                --     config = configs.dconf(require("gnome")),
                -- },
            },

            deploy_configs = {
                "home", -- General config for home directory (face, background, etc.)
                "gtk",  -- GTK themes
            },

            services = {
                syncthing = {
                    enable = false,
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

        cups = {
            enable = false,
            extra_packages = { "gutenprint", "brother-dcp-l2550dw" }, -- AUR
        },

        -- https://wiki.archlinux.org/title/Bluetooth
        bluetooth = {
            enable = false,
            service_name = "bluetooth",
            package = "bluez",
        },

    }
}
