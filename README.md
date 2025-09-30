<h1 align="center">
  <img src="docs/images/KoDOS.svg" alt="KoDOS" width="100px">
  <br />
  <b>KodOS</b>
</h1>
  <h2 align="center">Kind of Distribution for linux</h2 >

# Introduction

KodOS is a tool for installing and managing packages in a Linux distribution. It uses [Lua](https://www.lua.org/) as a declarative language for configurations, enabling reproducibility. KodOS follows many concepts from [NixOS](https://nixos.org/). Rather than providing its own package ecosystem, KodOS leverages packages from other Linux distributions (currently Arch Linux), similar to [AshOS](https://github.com/ashos/ashos).

KodOS employs Btrfs snapshots to provide "generations," allowing users to boot into previous versions of the system. This feature enables efficient handling of system atomic rollbacks and upgrades.

KodOS is still a work-in-progress but supports system installation, generation management (updates and rollbacks), and minimal package configuration support. New package configurations can be added using Lua.

# Features

- **Generation support** via Btrfs snapshots.
- **Declarative system configuration** using Lua.
- **Multiple package sources** are supported, including Arch repositories (core, extra), AUR, and Flatpak. New sources can be added using Lua.
- **Partial support for `kod shell`** (similar to `nix shell`).
- **Extensible** to work with other distributions. (Currently, only Arch Linux is supported, with Debian planned for the future).

KodOS is still under development and not yet ready for production, although I personally use it on both my laptop and desktop. The currently implemented features are based on my personal requirements, but I'm open to adding new functionality. I will continue to work on it during my spare time, with plans to introduce more features and expand support for other distributions.

If you're interested in trying it out, I recommend starting with a virtual machine to familiarize yourself with the system and its configuration file.


# Installation and usage

KodOS requires an official live ISO of the target distribution (currently [Arch](https://archlinux.org/download/))

### 1. Boot with the Live ISO

After booting the live ISO, install the required packages for installation:

```bash
pacman -Syy
pacman -S git uv
```

### 2. Install KodOS (`kod` CLI tool)

Clone the repository:

```bash
git clone https://github.com/kodos-prj/kodos.git
```
Navigate to the kodos directory and run:

```bash
uv run kod
```

This will download the required dependencies and display the help message:

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

### 3. Example Installation

To install the system, you need a configuration file that describes the target system. An example configuration for a virtual machine can be found at [`example/testvm/configuration.lua`](https://github.com/kodos-prj/kodos/blob/main/example/testvm/configuration.lua).

Use the example configuration with the following command to start the installation:

```bash
uv run kod rebuild-user -c example/testvm
```

By default, `kod` will look for a file called `configuration.lua` in the specified directory path, unless a particular configuration file path is provided.

The previous command will wipe the virtual disk and create three partitions: _boot_, _swap_ (optional), and _rootfs_ (using Btrfs). The first generation will be created, and the specified packages, services, and users will be installed.

After installation, reboot the system to boot into the newly installed system. KodOS is copied to `/root/kodos` for future use.

### 4. Rebuilding User Configuration

After logging in as a normal user, you can run the following to rebuild the user configuration:

```bash
uv run kod rebuild-user -c example/testvm
```

This will process all the configurations defined for the current user, such as dotfile managers or package-specific configurations (e.g., `.gitconfig` generation).

### 5. Adding/Removing Packages or Services

To modify the system configuration, edit the configuration file and run:

```bash
uv run kod rebuild -n -c example/testvm
```
This will create a new generation (`-n`), adding an entry to the boot loader (`system-boot`). To use the new generation, reboot the system and select the desired one. If the `-n` flag is not used, the changes will take effect immediately without rebooting. However, changes like display manager updates may cause issues in this case.

### 6. Temporary Package Installation with kod shell

KodOS supports temporarily installing packages using `kod shell`, which works similarly to `nix shell`. This feature uses [schroot](https://man.archlinux.org/man/schroot.1) and overlayfs to create a temporary environment.

For example, to install `smem` from AUR and `neofetch` from Arch extra in a temporary shell, run:

```bash
uv run kod shell -p aur:smem -p neofetch
```

When the shell is closed, the installed packages will be removed (the overlay is destroyed). Note that some programs may have issues running in this environment, especially with Wayland/X11 permissions or chroot detection.

### 7. Running Unit Tests

To run the comprehensive unit test suite for KodOS:

```bash
# Install development dependencies (includes pytest)
uv sync --dev

# Run all tests with verbose output
uv run pytest tests/test_common.py -v

# Run tests without verbose output
uv run pytest tests/test_common.py
```

The test suite includes 25 tests covering:
- Core `exec()` function functionality and error handling
- Command safety validation and timeout handling  
- Error handling abstractions (`exec_critical`, `exec_warn`, etc.)
- Custom exception classes and their properties

All tests should pass for a healthy codebase.

----

## [Configuration file](#configuration)

The configuration file is written in Lua and defines various sections for configuring the system. Here’s a basic example of a configuration file:

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
        kernel = {
            package = "linux-lts",
            modules = { "xhci_pci", "ohci_pci", "ehci_pci", "virtio_pci", "ahci", "usbhid", "sr_mod", "virtio_blk" },
        },
        loader = {
            type = "systemd-boot",
            timeout = 10,
            include = { "memtest86+" },
        },
    },


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

