<h1 align="center">
  <img src="docs/images/KoDOS.svg" alt="KoDOS" width="100px">
  <br />
  <b>KodOS</b>
</h1>
  <h2 align="center">Kind of Distribution for linux</h2 >

# Introduction

KodOS is a tool for installation and package management of a Linux distribution. It uses [Lua](https://www.lua.org/) as a declarative languge for configurations to enable reproducibility. KodOS follow some of the ideas of [NixOS](https://nixos.org/). KodOS rather than providing its own package ecosystem, it leverages packages from other Linux distributions (currently Arch Linux), simillar to and [AshOS](https://github.com/ashos/ashos). KodOS uses Btrfs snapshots to provide the concept of "generations," allowing users to boot previous versions of the system. This provides an efficient way to handle system rollbacks and upgrades.

KodOS is still in a Work-in-progress state, allowing install a system, manage generations (updates and rollback), as well a minimal support for package configurations. New package configurations can be added using Lua. 

# Features
- Support for generations through Btrfs snapshots.
- Declarative configuration of the system using Lua to decribe the configuration.
- Different package sources can be used and new ones can be added using Lua. Current Arch repos (core and extra), AUR and flatpak are supported.
- New package configurations can be added using Lua.
- Partial support for `kod shell -p` (simillar to `nix shell -p`). Currently some GUI applications are not working, but so far, CLI apps work fine.
- The tool can be extended to work with different distributions. (Currently only Arch is supported, but Debian is in the future plans).

KodOS is in development and it is not ready for production (however, I'm using it on my personal laptop and desktop). 

# Installation and usage

KodOS currently uses an official live iso for the target distribution, currently [Arch](https://archlinux.org/download/)

After booting with the live iso, you need to install the required packages for installation:
```bash
pacman -Syy
pacman -S git uv
```

To install the KodOS (`kod` cli tool), clone the repository:

```bash
git clone https://github.com/kodos-prj/kodos.git
```

Then, enter to the `kodos` directory and run `uv run kod`. This will download the library dependencies and run the `kod` command to show the help:

```bash
Usage: kod [OPTIONS] COMMAND [ARGS]...

Options:
  -d, --debug
  --help       Show this message and exit.

Commands:
  install       Install KodOS based on the given configuration
  rebuild       Rebuild KodOS system installation
  rebuild-user  Rebuild user configuration
  shell         Run shell
```

Installing a system requires a configuration that describe the target system. An example of a simple configuration to be used to install over a virtual machine is [`example/testvm/configuration.lua`](https://github.com/kodos-prj/kodos/blob/main/example/testvm/configuration.lua).

Using the example configuration, running `uv run kod install -c example/testvm` will start the installation. The example configuration witll wipe the virtual disk and create 3 partions (`boot`, `swap` (optional), and `rootfs` (_btrfs_)). The first generation is created and the specified packages and services are installed, as well as the specified users. After finishing the installation, the system can be rebooted to boot to the new installed system. KodOS is automatically copied into the `/root/kodos` for future use.

After loging as a normal user, we can run the configuration set for each user running 
```bash
uv run kod rebuild-user -c example/testvm
```
This command will process all the configurations defined for the current user. For example, if a dotfile manager program has been specified, or Lua functions has been used to configure a package, like generation of `.gitconfig` file.

To add/remove packages or service, edit your configuration file and run:
```bash
uv run kod rebuild -n -c example/testvm
```
The previous command will recreate the given configuration in a new generation (`-n`), creating a new entry in the boot loader (`system-boot`). To use the new created generation, the system need to be rebooted to choose the desired generation to boot. If the option `-n` is not used, a new generation is created and but the changes introduced are inmediatly available without reboot. This on-site generetaion could have issues with programs that replaces actual functionality (e.g. changing the display manager). 

KodOS provides a functionality to temporary install a package(s), similar to the functionality provide by `nix shell`. The implementation of `kod shell` uses [pchroot](https://man.archlinux.org/man/schroot.1) and ovelayfs to create a temporary enviroment to install packages. For example, the following command will create a temporary shell where `smem` from AUR and `neofetch` from Arch extra are installed, and the programs are accesable inside the created shell. When the shell is closed, all the installed packages are removed (overlay is destroyed).

```bash
uv run kod shell -p aur:smem -p neofetch
```

Currently, not all the programs work using `kod shell`. Some of the problems are related to permissions to access the current display (Wayland or X11), the program detects that is running in a chroot environment, or other issues.

## [Configuration file](#configuration)
The configuration file is a Lua file that contains defferent sections to configure the different aspects of the system. An example of a basic configuration file is the following:

```lua
-- Helper scripts 
disk = require("disk") 
repos = require("repos")
dotmgr = require("dotfile_manager")
configs = require("configs")

return {
    repos = {
        -- The following package sources are defined by script functions freom repo 
        arch = repos.arch_repo("https://mirror.rackspace.com/archlinux");
        -- Uses yay as package manager for AUR
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git");
        flatpak = repos.flatpak_repo("flathub");
    },

    devices = {
        -- disk0 is a disk partition layout (boot, swap (optional), and rootfs) over the /dev/vda device, created using a script function 
        -- The swap size (3GB in this case) is optional
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
            default = "en_CA.UTF-8 UTF-8";
            extra_generate = {
                "en_US.UTF-8 UTF-8", "en_GB.UTF-8 UTF-8"
            };
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
        };
        keymap = "us";
        timezone = "America/Edmonton";
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
        demo-user = {
            name = "Demo User";
            password = "changme";
            -- or use a hash version of the passward 
            -- hashed_password = "$6$q5r7h6qJ8nRats.X$twRR8mUf5y/oKae4doeb6.aXhPhh4Z1ZcAz5RJG38MtPRpyFjuN8eCt9GW.a20yZK1O8OvVPtJusVHZ9I8Nk/.",
            shell = "/bin/zsh",

            -- Specify if a program to hadle dotfiles is used. In this case stow
            dotfile_manager = dotmgr.stow({
                    source_dir = "~/.dotfiles",
                    target_dir = "~/",
                    repo_url = "http://git.homecloud.lan/demouser/dotconfig.git",
                });

            -- Programs used for the user. This programs aree installed at the system level and are available for all the users
            programs = {
                git = {
                    enable = true,
                    -- Uses a script function to configure .gitconfig
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
                    -- This option instruct the dotfile manager to deply the configuration for neovim
                    deploy_config = true,
                };
            };

            -- Configuration to deploy using the defined dotfile manager not associated to any program in particular
            deploy_configs = {
                "home", -- General config for home directory (face, background, etc.)
                "gtk", -- GTK themes
            },

            -- Services enabled at the user level
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
        -- General display manager to use. Use this option if multiple desktop managers wants to be  installed.
        -- IF it is not used, each desktop manager could define it own display manager. 
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

    -- System packages to install
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

    -- System services
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
