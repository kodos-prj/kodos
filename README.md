<h1 align="center">
  <img src="docs/images/KodOS.svg" alt="KoDOS" width="100px">
  <br />
  <b>KodOS</b>
</h1>
  <h2 align="center">Kind of Distribution for linux</h2 >

# Introduction

KodOS is a tool for creating Linux installations based on declarative configuration, enabling reproducibility. Inspired by [Nix](https://nixos.org/) and [AshOS](https://github.com/ashos/ashos). KodOS rather than providing its own package ecosystem, it leverages packages from other Linux distributions (currently Arch Linux), much like AshOS. KodOS uses [Lua](https://www.lua.org/) as its configuration language and uses the concept of "generations," from Nix allowing users to boot previous versions of the system. Btrfs snapshots are used to manage these generations, providing an efficient way to handle system rollbacks and upgrades.

# Installation

To install the tools, clone the repository to your machine with the following command:

```bash
git clone https://github.com/kodos-prj/kodos.git
```

To use KodOS, run the command `uv run kod`:

```bash
Usage: kod [OPTIONS] COMMAND [ARGS]...

Options:
  -d, --debug
  --help       Show this message and exit.

Commands:
  install       Install KodOS in /mnt
  rebuild       Rebuild KodOS installation based on configuration file
  rebuild-user  Rebuild the user based on configuration file
```

## [Configuration file](#configuration)
The configuration file is a lua file that contains defferent sections to configure the different aspects of the system. An example of a basic configuration file is the following:

```lua
disk = require("disk")
repos = require("repos")
dotmgr = require("dotfile_manager")
configs = require("configs")

return {
    repos = {
        official = repos.arch_repo("https://mirror.rackspace.com/archlinux");
        -- Uses yay as package manager for AUR
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git");
        flatpak = repos.flatpak_repo("flathub");
    },

    devices = {
        -- Defines partition layout for the /dev/vda device using 3GB of swap
        disk0 = disk.disk_definition("/dev/vda", "3GB");
    };

    boot = {
        loader = {
            type = "systemd-boot";
            timeout = 10;
            include = { "memtest86+" };
        };
    };

    hardware = {
        bluetooth = {
            enable = true,
            package = "bluez",
        };

        pipewire = {
            enable = true,
            extra_packages = {
                "pipewire-alsa",
                "pipewire-pulse",
            },
        },
    };

    locale = {
        locale = {
            default = "en_US.UTF-8 UTF-8\nen_CA.UTF-8 UTF-8";
        },
        keymap = "us";
        timezone = "America/Edmonton"
    };

    network = {
        hostname = "testvm",
        ipv6 = false
    };

    users = {
        root = {
            no_password = true,
            shell = "/bin/bash",
        };
        abuss = {
            name = "Demo User",
            hashed_password = "$6$q5r7h6qJ8nRats.X$twRR8mUf5y/oKae4doeb6.aXhPhh4Z1ZcAz5RJG38MtPRpyFjuN8eCt9GW.a20yZK1O8OvVPtJusVHZ9I8Nk/.",
            shell = "/bin/zsh",

            dotfile_manager = dotmgr.stow({
                    source_dir = "~/.dotfiles",
                    target_dir = "~/",
                    repo_url = "http://git.homecloud.lan/demouser/dotconfig.git",
                });

            programs = {
                git = {
                    enable = true,
                    config = configs.git({
                        user_name = "Demo User",
                        user_email = "demo.user@gmail.com",
                    })
                };

                zsh = {
                    enable = true,
                    deploy_config = true,
                    extra_packages = {
                        "zsh-autosuggestions",
                        "zsh-completions",
                    }
                };

                neovim = {
                    enable = true,
                    deploy_config = true,
                };
            };

            -- Configuration to deploy using the defined dotfile manager
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
                }
            }
        },
    };

    desktop = {
        display_manager = "gdm";

        desktop_manager = {
            gnome = {
                enable = true,
                exclude_packages = {
                    "gnome-tour", "yelp"
                },
                extra_packages = {
                    "gnome-tweaks",
                    "gnome-shell-extension-appindicator",
                    "aur:gnome-shell-extension-dash-to-dock"
                },
            };
    
            plasma = {
                enable = false,
                extra_packages = {
                    "kde-applications",
                },
            };

            cosmic = {
                enable = false,
                display_manager = "cosmic-greeter",
            },
        }
    },

    fonts = {
        font_dir = true,
        packages = {
            "ttf-firacode-nerd",
            "ttf-nerd-fonts-symbols",
            "ttf-nerd-fonts-symbols-common",
            "ttf-sourcecodepro-nerd",
            "ttf-fira-sans",
            "ttf-fira-code",
            "ttf-liberation",
            "noto-fonts-emoji",
            "adobe-source-serif-fonts",
            "ttf-ubuntu-font-family",
            "aur:ttf-work-sans",
        },
    };

    packages = {
        "neovim",
        "htop",
        "uv",
        "git",
        "neofetch",
        -- AUR packages,
        "aur:floorp-bin",
        -- Flatpak packages
        "flatpak:com.visualstudio.code",
    };

    services = {
        -- Firmware update
        fwupd = { enable = true },
        
        networkmanager = {
            enable = true,
            service_name = "NetworkManager",
        };
        
        openssh = {
            enable = true,
            service_name = "sshd",
            settings = {
                PermitRootLogin = false,
            }
        }; 
        cups = {
            enable = true,
            extra_packages = { "gutenprint" },
        };
    }
}
```