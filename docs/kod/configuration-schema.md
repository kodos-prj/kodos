# KodOS Configuration Schema Reference

**Last Updated:** September 11, 2026  
**Status:** Complete (Phase 5b)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Configuration Sections](#configuration-sections)
   - [base_distribution](#base_distribution)
   - [repos](#repos)
   - [devices](#devices)
   - [boot](#boot)
   - [hardware](#hardware)
   - [locale](#locale)
   - [network](#network)
   - [users](#users)
   - [desktop](#desktop)
   - [fonts](#fonts)
   - [packages](#packages)
   - [services](#services)
   - [programs](#programs)
4. [Common Errors & Solutions](#common-errors--solutions)
5. [Advanced Topics](#advanced-topics)
6. [Complete Examples](#complete-examples)
7. [Command Reference](#command-reference)

---

## Introduction

### What is KodOS Configuration?

KodOS uses **Lua configuration files** to describe your desired system state, including:

- **Base distribution** — Linux distribution (Arch, Debian)
- **Repositories** — Package sources (official, AUR, Flatpak, APT)
- **Hardware** — Disk layout, boot settings, audio configuration
- **Localization** — Timezone, locale, keyboard layout
- **Network** — Hostname, IPv6
- **Users** — User accounts, groups, shells, programs
- **Desktop** — Desktop environment (GNOME, KDE Plasma, XFCE, Cosmic, etc.)
- **Fonts** — Font packages (monospace, sans-serif, emoji)
- **Packages** — System packages to install
- **Services** — System services to enable/start (SSH, nginx, etc.)
- **Programs** — High-level program configurations with installation logic

Configuration files are **pure Lua**, executed in a sandboxed environment. KodOS
validates, plans, and executes configurations in order, generating a
reproducible list of installation steps.

### File Location & Format

Configuration files are plain-text Lua files:

```
~/.kod/config.lua              # User's default config (searched by 'kod install')
/etc/kod/config.lua            # System-wide default
example/testvm/configuration.lua   # Example config in repo
```

Each config file returns a single Lua table with top-level sections:

```lua
return {
    base_distribution = "arch",
    repos = { ... },
    devices = { ... },
    -- ... etc
}
```

### Quick Start

1. **Generate a template:**
   ```bash
   kod config init --distro arch
   ```

2. **Edit the generated config** `~/.kod/config.lua` with your settings

3. **Preview the installation plan** without changes:
   ```bash
   kod plan --config ~/.kod/config.lua
   ```

4. **Apply the configuration:**
   ```bash
   kod install --config ~/.kod/config.lua
   ```

### Getting Help

- **View schema for a section:**
  ```bash
  kod config schema --section users
  ```

- **View all sections:**
  ```bash
  kod config schema
  ```

- **Validate a configuration:**
  ```bash
  kod config validate --config ~/.kod/config.lua
  ```

---

## Getting Started

### Generating a Starter Template

Use `kod config init` to create a template configuration:

```bash
# Generate Arch config template
kod config init --distro arch --output my-config.lua

# Generate Debian config template  
kod config init --distro debian --output my-config.lua
```

The template contains all 13 sections with example values and comments
explaining each field.

### Understanding the Template Structure

The generated template looks like:

```lua
-- KodOS Configuration Template
-- Distribution: arch
--
-- See 'kod config schema' for full documentation.
-- Uncomment sections below and customize as needed.
--

return {

    -- BASE_DISTRIBUTION
    -- Base Linux distribution to install.
    -- Required: Yes
    --
    -- Example:
    -- base_distribution = "arch"

    -- BOOT
    -- Kernel and bootloader configuration.
    -- 
    -- Example:
    -- boot = {
    --     kernel = {
    --         package = "linux-lts",
    --         modules = {"xhci_pci", "virtio_blk"},
    --     },
    --     loader = {
    --         type = "systemd-boot",
    --         timeout = 10,
    --     },
    -- }

    -- ... more sections ...

}
```

Start by uncommenting sections you need and customizing values.

### Running a Plan (Dry-Run)

Preview changes without applying them:

```bash
kod plan --config ~/.kod/config.lua
```

Output shows:
- List of steps that will execute
- Disk operations (partitioning, formatting)
- Package installation commands
- Service management
- User creation

### Running an Installation

Apply the configuration:

```bash
kod install --config ~/.kod/config.lua
```

**On an existing system:** Updates packages, services, users, and programs.

**On a new system:** Partitions disks, installs base OS, then applies
configuration.

---

## Configuration Sections

### base_distribution

**Base Linux distribution to install.**

**Type:** string  
**Required:** Yes  
**Valid values:** `"arch"`, `"debian"`

The distribution determines:
- Default package manager (pacman vs apt)
- Bootstrap packages (base vs base-files)
- Repository functions available
- Systemd/init compatibility
- Package names for common software

#### Example

```lua
base_distribution = "arch"
```

or

```lua
base_distribution = "debian"
```

#### Notes

- **Required** — Configuration will fail if missing
- **Distro-specific:** Boot, packages, and services vary between Arch and Debian
- See sections below for distro-specific examples

---

### repos

**Repository definitions (package sources).**

**Type:** dict  
**Required:** No (uses distro defaults if omitted)

Repositories are named package sources. KodOS provides functions to define
them:

- **Arch-specific:**
  - `repos.arch_repo(url)` — Official Arch repository mirror
  - `repos.aur_repo(helper, url)` — AUR (Arch User Repository)
  - `repos.flatpak_repo(name)` — Flatpak repository

- **Debian-specific:**
  - `repos.apt_repo(url)` — APT repository
  - `repos.ppa_repo(ppa)` — Personal Package Archive

#### Example: Arch

```lua
repos = {
    official = repos.arch_repo(
        "https://mirror.cpsc.ucalgary.ca/mirror/archlinux.org"
    ),
    aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay.git"),
    flatpak = repos.flatpak_repo("flathub"),
}
```

#### Example: Debian

```lua
repos = {
    official = repos.apt_repo(
        "deb https://deb.debian.org/debian bookworm main"
    ),
    backports = repos.apt_repo(
        "deb https://deb.debian.org/debian bookworm-backports main"
    ),
}
```

#### Common Mistakes

**Problem:** Using wrong function for distro
```lua
-- Wrong on Debian:
repos = {
    aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay.git"),
}
```

**Solution:** Use distro-specific functions
```lua
-- Correct for Debian:
repos = {
    official = repos.apt_repo("deb https://deb.debian.org/debian bookworm main"),
}
```

---

### devices

**Disk and partition definitions for system installation.**

**Type:** dict  
**Required:** No (use if installing on new system)

Define disks and their partitions using the `disk` module:

```lua
local disk = require("disk")

devices = {
    disk0 = disk.disk_definition("/dev/sda", "50GB"),
}
```

#### Nested Fields

**disk.disk_definition(device_path, size)**

Create a disk definition:
- `device_path` — Linux device path (`/dev/sda`, `/dev/nvme0n1`)
- `size` — Total disk size (`"50GB"`, `"1TB"`)

**Returns:** A disk object with methods for adding partitions

#### Partition Scheme Example

```lua
devices = {
    disk0 = disk.disk_definition("/dev/sda", "100GB")
        :partition("boot", "512M", "vfat", "/boot")
        :partition("root", "100%", "ext4", "/"),
}
```

This creates:
- `/dev/sda1` — 512M EFI boot partition (vfat, mounted at /boot)
- `/dev/sda2` — Remaining space root partition (ext4, mounted at /)

#### Common Mistakes

**Problem:** Partition sizes exceed disk size
```lua
devices = {
    disk0 = disk.disk_definition("/dev/sda", "50GB")
        :partition("boot", "20GB", "vfat", "/boot")
        :partition("root", "40GB", "ext4", "/"),  -- Only 30GB left!
}
```

**Solution:** Use percentages or ensure sizes sum correctly
```lua
devices = {
    disk0 = disk.disk_definition("/dev/sda", "50GB")
        :partition("boot", "512M", "vfat", "/boot")
        :partition("root", "100%", "ext4", "/"),
}
```

---

### boot

**Kernel and bootloader configuration.**

**Type:** dict  
**Required:** No

Define which kernel to install and how to boot the system.

#### Nested Fields

##### kernel

Kernel package and loadable modules:

```lua
boot = {
    kernel = {
        package = "linux-lts",
        modules = {"xhci_pci", "virtio_blk", "ahci"},
    },
}
```

**Fields:**
- `package` — Kernel package name
  - **Arch:** `"linux"` (default), `"linux-lts"`, `"linux-hardened"`
  - **Debian:** `"linux-image-amd64"` (default)
  
- `modules` — Kernel modules to load at boot (initramfs inclusion)
  - Common: `"xhci_pci"`, `"virtio_blk"`, `"ahci"`, `"usbhid"`, `"sr_mod"`
  - Use for VM drivers, SATA, USB compatibility

##### loader

Bootloader configuration:

```lua
boot = {
    loader = {
        type = "systemd-boot",  -- or "grub"
        timeout = 10,
    },
}
```

**Fields:**
- `type` — Bootloader type
  - `"systemd-boot"` (default, EFI only) — Modern, lightweight
  - `"grub"` — Legacy BIOS and EFI support
  
- `timeout` — Boot menu timeout in seconds (default: 10)

#### Complete Example

```lua
boot = {
    kernel = {
        package = "linux-lts",
        modules = {"xhci_pci", "ohci_pci", "ehci_pci", "virtio_pci",
                   "ahci", "usbhid", "sr_mod", "virtio_blk"},
    },
    loader = {
        type = "systemd-boot",
        timeout = 10,
    },
}
```

#### Common Mistakes

**Problem:** Missing kernel modules for hardware
```lua
boot = {
    kernel = {
        package = "linux",
        -- modules not specified, may fail on some hardware
    },
}
```

**Solution:** Include essential hardware drivers
```lua
boot = {
    kernel = {
        package = "linux",
        modules = {"virtio_blk", "virtio_pci", "ahci"},  -- VM + SATA
    },
}
```

---

### hardware

**Hardware features and configurations.**

**Type:** dict  
**Required:** No

Configure audio, graphics, and other hardware support.

#### Nested Fields

##### pipewire

PipeWire audio system (replaces PulseAudio):

```lua
hardware = {
    pipewire = {
        enable = true,
        extra_packages = {"pipewire-alsa", "pipewire-pulse"},
    },
}
```

**Fields:**
- `enable` — Enable PipeWire (boolean, default: false)
- `extra_packages` — Additional packages for compatibility
  - `"pipewire-alsa"` — ALSA compatibility layer
  - `"pipewire-pulse"` — PulseAudio compatibility
  - `"pipewire-jack"` — JACK compatibility

#### Example: Desktop with Audio

```lua
hardware = {
    pipewire = {
        enable = true,
        extra_packages = {
            "pipewire-alsa",
            "pipewire-pulse",
            "wireplumber",
        },
    },
}
```

#### Example: Server (No Audio)

```lua
hardware = {
    -- Omit pipewire for headless systems
}
```

---

### locale

**Localization settings (language, timezone, keyboard, environment).**

**Type:** dict  
**Required:** No

Configure system language, timezone, and keyboard layout.

#### Nested Fields

##### locale

Locale and language settings:

```lua
locale = {
    locale = {
        default = "en_US.UTF-8 UTF-8",
        extra_generate = {"en_GB.UTF-8 UTF-8", "en_CA.UTF-8 UTF-8"},
    },
}
```

**Fields:**
- `default` — Default system locale (format: `LANG.ENCODING ENCODING`)
  - Examples: `"en_US.UTF-8 UTF-8"`, `"de_DE.UTF-8 UTF-8"`, `"fr_FR.UTF-8 UTF-8"`
  - Sets `LANG`, `LC_ALL` environment variables
  
- `extra_generate` — Additional locales to generate on system
  - Allows easy switching between locales
  - Common: English (US, GB, CA), German, French, etc.

##### timezone

System timezone (IANA format):

```lua
locale = {
    timezone = "America/New_York",
}
```

**Format:** `"Continent/City"` (IANA tz database)

**Examples:**
- `"America/New_York"` — Eastern (US)
- `"America/Los_Angeles"` — Pacific (US)
- `"Europe/London"` — UK
- `"Europe/Berlin"` — Germany
- `"Asia/Tokyo"` — Japan
- `"Australia/Sydney"` — Australia
- `"UTC"` — Coordinated Universal Time

##### keymap

Console keyboard layout:

```lua
locale = {
    keymap = "us",
}
```

**Common layouts:**
- `"us"` — US English
- `"de"` — German
- `"fr"` — French
- `"gb"` — British
- `"colemak"` — Colemak layout
- `"dvorak"` — Dvorak layout

#### Complete Example

```lua
locale = {
    locale = {
        default = "en_CA.UTF-8 UTF-8",
        extra_generate = {
            "en_US.UTF-8 UTF-8",
            "en_GB.UTF-8 UTF-8",
            "fr_CA.UTF-8 UTF-8",
        },
    },
    timezone = "America/Edmonton",
    keymap = "us",
}
```

#### Common Mistakes

**Problem:** Invalid timezone
```lua
locale = {
    timezone = "Canada/Mountain",  -- Wrong format
}
```

**Solution:** Use IANA format (Continent/City)
```lua
locale = {
    timezone = "America/Edmonton",  -- Correct
}
```

**Problem:** Invalid locale format
```lua
locale = {
    locale = {
        default = "en_US",  -- Missing encoding
    },
}
```

**Solution:** Include encoding
```lua
locale = {
    locale = {
        default = "en_US.UTF-8 UTF-8",
    },
}
```

---

### network

**Network configuration (hostname, IPv6).**

**Type:** dict  
**Required:** No

Configure network settings and hostname.

#### Fields

##### hostname

System hostname (computer name on network):

```lua
network = {
    hostname = "mycomputer",
}
```

**Notes:**
- Used in `/etc/hostname`
- Visible on network and in terminal prompt
- Common pattern: `firstname-machine` (e.g., `alice-desktop`)

##### ipv6

Enable IPv6 support:

```lua
network = {
    ipv6 = true,  -- or false to disable
}
```

**Default:** true  
**Options:**
- `true` — Enable IPv6 (default)
- `false` — Disable IPv6 (IPv4-only)

#### Complete Example

```lua
network = {
    hostname = "workstation",
    ipv6 = true,
}
```

#### Common Mistakes

**Problem:** Using spaces or invalid characters in hostname
```lua
network = {
    hostname = "My Computer",  -- Invalid (spaces)
}
```

**Solution:** Use lowercase alphanumerics and hyphens
```lua
network = {
    hostname = "my-computer",  -- Valid
}
```

---

### users

**User accounts (login, shell, groups, home configuration).**

**Type:** dict  
**Required:** No

Define user accounts and their properties.

#### Fields

Each key in `users` is a username. Inside each user, configure:

```lua
users = {
    alice = {
        shell = "/bin/bash",
        groups = {"wheel", "docker"},
        home_programs = {neovim = true, git = true},
    },
}
```

##### shell

Default login shell:

```lua
users = {
    alice = {
        shell = "/bin/bash",
    },
}
```

**Common shells:**
- `/bin/bash` — Bash (default, widely compatible)
- `/bin/zsh` — Zsh (modern, extensible)
- `/bin/fish` — Fish (user-friendly, less POSIX-compatible)
- `/bin/sh` — POSIX shell (minimal)

**Note:** Shell binary must be installed in packages first

##### groups

Unix groups to add user to:

```lua
users = {
    alice = {
        groups = {"wheel", "docker", "audio", "video"},
    },
}
```

**Common groups:**
- `"wheel"` (Arch) / `"sudo"` (Debian) — Administrative access (sudo)
- `"docker"` — Docker container access
- `"audio"` — Audio device access
- `"video"` — GPU/graphics access
- `"input"` — Input device access (keyboard, mouse)
- `"network"` — Network access
- `"users"` — Standard user group

**Important:** Distro-specific sudo group
- **Arch:** Use `"wheel"` for sudo access
- **Debian:** Use `"sudo"` for sudo access

##### home_programs

User-scoped programs (installed in home directory):

```lua
users = {
    alice = {
        home_programs = {
            neovim = true,
            git = {enable = true, config = {...}},
        },
    },
}
```

Programs can be:
- `true` — Install with default configuration
- `{enable = true, ...}` — Install with custom configuration

#### Complete Example

```lua
users = {
    root = {
        shell = "/bin/bash",
    },
    alice = {
        shell = "/usr/bin/fish",
        groups = {"wheel", "docker", "audio", "video"},
        home_programs = {
            git = {
                enable = true,
                config = {
                    user_name = "Alice Smith",
                    user_email = "alice@example.com",
                },
            },
            neovim = {enable = true},
        },
    },
    bob = {
        shell = "/bin/bash",
        groups = {"audio", "video"},
    },
}
```

#### Common Mistakes

**Problem:** Wrong sudo group for distro
```lua
-- Wrong on Debian:
users = {
    alice = {
        groups = {"wheel"},  -- Debian doesn't have 'wheel'
    },
}
```

**Solution:** Use distro-specific group
```lua
-- Correct for Debian:
users = {
    alice = {
        groups = {"sudo"},  -- Use 'sudo' on Debian
    },
}
```

**Problem:** Using unavailable shell
```lua
users = {
    alice = {
        shell = "/bin/fish",
        -- But 'fish' is not in packages!
    },
}
```

**Solution:** Include shell in packages
```lua
packages = {"fish", "git", "neovim"},

users = {
    alice = {
        shell = "/bin/fish",
    },
}
```

---

### desktop

**Desktop environment selection and configuration.**

**Type:** dict  
**Required:** No

Choose and configure a graphical desktop environment.

#### Fields

##### environment

Desktop environment to install:

```lua
desktop = {
    environment = "gnome",  -- or "plasma", "xfce", "cosmic"
}
```

**Available environments:**
- `"gnome"` — GNOME 3/4 (modern, Wayland-ready)
- `"plasma"` — KDE Plasma 5/6 (feature-rich, customizable)
- `"xfce"` — XFCE (lightweight, fast)
- `"cosmic"` — COSMIC (new Rust-based DE)
- `"cinnamon"` — Cinnamon (Mint-style)
- `"mate"` — MATE (lightweight, traditional)
- `"lxde"` / `"lxqt"` — Minimalist

##### enable

Enable desktop environment installation:

```lua
desktop = {
    enable = true,  -- Install and set up desktop (default)
}
```

**Options:**
- `true` — Install desktop packages and display manager
- `false` — Skip desktop (headless server)

#### Complete Example: GNOME

```lua
desktop = {
    environment = "gnome",
    enable = true,
    extra_packages = {
        "gnome-tweaks",
        "gnome-shell-extensions",
    },
}
```

#### Complete Example: KDE Plasma

```lua
desktop = {
    environment = "plasma",
    enable = true,
    extra_packages = {
        "kde-applications",
    },
}
```

#### Common Mistakes

**Problem:** Typo in environment name
```lua
desktop = {
    environment = "gnome-desktop",  -- Wrong
}
```

**Solution:** Use exact environment name
```lua
desktop = {
    environment = "gnome",  -- Correct
}
```

---

### fonts

**Font packages to install (monospace, sans-serif, emoji).**

**Type:** dict  
**Required:** No

Install fonts for different purposes.

#### Fields

##### monospace

Monospace font packages (for terminal, code editors):

```lua
fonts = {
    monospace = {"ttf-firacode-nerd", "ttf-sourcecodepro-nerd"},
}
```

**Common monospace fonts:**
- `"ttf-firacode-nerd"` — Fira Code (ligatures, Nerd icons)
- `"ttf-sourcecodepro-nerd"` — Source Code Pro (clean)
- `"ttf-inconsolata-nerd"` — Inconsolata (minimal)
- `"noto-fonts-cjk"` — CJK characters (Chinese/Japanese/Korean)

##### sans_serif

Sans-serif font packages (UI, documents):

```lua
fonts = {
    sans_serif = {"ttf-fira-sans", "noto-fonts"},
}
```

**Common sans-serif fonts:**
- `"ttf-fira-sans"` — Fira Sans (modern)
- `"ttf-dejavu"` — DejaVu (safe, widely available)
- `"noto-fonts"` — Google Noto (comprehensive)

##### emoji

Emoji font packages:

```lua
fonts = {
    emoji = {"noto-fonts-emoji", "ttf-nerd-fonts-symbols"},
}
```

**Common emoji fonts:**
- `"noto-fonts-emoji"` — Google Noto Emoji
- `"ttf-nerd-fonts-symbols"` — Nerd Fonts symbols

#### Complete Example

```lua
fonts = {
    monospace = {
        "ttf-firacode-nerd",
        "ttf-sourcecodepro-nerd",
        "noto-fonts-cjk",
    },
    sans_serif = {
        "ttf-fira-sans",
        "noto-fonts",
    },
    emoji = {
        "noto-fonts-emoji",
        "ttf-nerd-fonts-symbols-common",
    },
}
```

---

### packages

**List of system packages to install.**

**Type:** list  
**Required:** No

Install additional system packages from configured repositories.

#### Format

```lua
packages = {"package1", "package2", "package3"}
```

Each element is a package name (distro-specific):

- **Arch:** `pacman` name (e.g., `"vim"`, `"git"`, `"htop"`)
- **Debian:** `apt` name (e.g., `"vim"`, `"git"`, `"htop"`)

#### Finding Packages

**Arch:**
```bash
pacman -Ss package_name    # Search in repos
yay -Ss package_name       # Search including AUR
```

**Debian:**
```bash
apt search package_name    # Search
```

#### Common Packages

**Essentials:**
- `"git"` — Version control
- `"vim"` or `"neovim"` — Text editor
- `"tmux"` or `"screen"` — Terminal multiplexer
- `"htop"` — Process monitor
- `"curl"` or `"wget"` — Download tools

**Development:**
- `"build-essential"` (Debian) / `"base-devel"` (Arch) — C/C++ compiler
- `"python"` — Python 3 interpreter
- `"nodejs"` — Node.js runtime
- `"rustup"` — Rust toolchain

**Utilities:**
- `"ripgrep"` (`"rg"`) — Fast search
- `"bat"` — Cat with syntax highlighting
- `"fzf"` — Fuzzy finder
- `"jq"` — JSON processor
- `"imagemagick"` — Image manipulation

#### Example

```lua
packages = {
    -- Core utilities
    "git",
    "vim",
    "tmux",
    "htop",
    
    -- Development
    "base-devel",      -- Arch
    "python",
    "nodejs",
    
    -- Tools
    "ripgrep",
    "fzf",
    "bat",
}
```

#### Common Mistakes

**Problem:** Package list as dict instead of list
```lua
-- Wrong:
packages = {
    git = true,
    vim = true,
}
```

**Solution:** Use list syntax
```lua
-- Correct:
packages = {
    "git",
    "vim",
}
```

**Problem:** Using package names from wrong distro
```lua
-- Wrong on Debian (Arch package name):
packages = {
    "base-devel",  -- This is Arch-specific
}
```

**Solution:** Use distro-specific package name
```lua
-- Correct for Debian:
packages = {
    "build-essential",  -- Debian equivalent
}
```

---

### services

**System services to enable/start (ssh, nginx, docker, etc.).**

**Type:** dict  
**Required:** No

Configure systemd services for automatic start/enable.

#### Format

```lua
services = {
    ssh = {enable = true},
    nginx = {enable = true, start = true},
}
```

Each key is a service name; value is configuration dict.

#### Fields

##### enable

Enable service to start on boot:

```lua
services = {
    ssh = {enable = true},  -- Starts automatically on boot
}
```

**Options:**
- `true` — Enable service at boot
- `false` or omitted — Don't enable

##### start

Start service immediately (after install):

```lua
services = {
    nginx = {start = true},  -- Start now, don't wait for reboot
}
```

**Options:**
- `true` — Start immediately (on same system)
- `false` or omitted — Don't start (wait for boot)

#### Common Services

**Networking:**
- `"ssh"` / `"sshd"` — Secure shell server
- `"networkmanager"` — Network management daemon
- `"systemd-resolved"` — DNS resolver

**Web:**
- `"nginx"` — Lightweight web server
- `"apache2"` (Debian) / `"httpd"` (Arch) — Apache web server

**Containers:**
- `"docker"` — Docker daemon (containerization)
- `"podman"` — Podman daemon (rootless containers)

**Database:**
- `"mysql"` / `"mariadb"` — MySQL/MariaDB
- `"postgresql"` — PostgreSQL

**Media:**
- `"mpd"` — Music Player Daemon
- `"pulseaudio"` — PulseAudio daemon

#### Example: Web Server

```lua
services = {
    nginx = {
        enable = true,   -- Start on boot
        start = true,    -- Start now
    },
}
```

#### Example: SSH Server

```lua
services = {
    ssh = {
        enable = true,   -- Start on boot
    },
}
```

#### Example: Development Stack

```lua
services = {
    ssh = {enable = true},
    nginx = {enable = true, start = true},
    docker = {enable = true},
    postgresql = {enable = true, start = true},
}
```

#### Common Mistakes

**Problem:** Service name inconsistency across distros
```lua
services = {
    sshd = {enable = true},  -- Wrong name, should be 'ssh'
}
```

**Solution:** Use correct systemd service name
```bash
systemctl list-unit-files | grep ssh  # Find exact name
```

```lua
services = {
    ssh = {enable = true},  -- Correct (alias for sshd)
}
```

---

### programs

**Program configurations at system level (custom programs with logic).**

**Type:** dict  
**Required:** No

Configure system-level programs with installation logic, not just package
names. Programs have custom schemas and may include services, config files,
extra packages, etc.

#### Format

```lua
programs = {
    neovim = {enable = true},
    openssh = {
        enable = true,
        service = {enable = true, service_name = "sshd"},
    },
}
```

Each key is a program name; value is program-specific configuration.

#### Program Definition

Programs are registered in KodOS's program registry and can include:
- Package installation logic
- Configuration file generation
- Service management
- Extra packages for compatibility
- User-level installation

#### System-Level Programs

System-level programs (top-level `programs` section):

```lua
programs = {
    -- Network management
    networkmanager = {
        enable = true,
        service = {
            enable = true,
            service_name = "NetworkManager",
        },
    },
    
    -- SSH server
    openssh = {
        enable = true,
        service = {
            enable = true,
            service_name = "sshd",
        },
    },
    
    -- Firmware updates
    fwupd = {
        enable = true,
        service = {enable = true, service_name = "fwupd"},
    },
    
    -- Docker
    docker = {
        enable = true,
        service = {enable = true, service_name = "docker"},
    },
}
```

#### User-Level Programs

User-level programs (inside `users.<username>.home_programs`):

```lua
users = {
    alice = {
        home_programs = {
            git = {
                enable = true,
                config = {
                    user_name = "Alice",
                    user_email = "alice@example.com",
                },
            },
            neovim = {enable = true},
        },
    },
}
```

#### Common Programs

**System-level:**
- `openssh` — SSH server
- `docker` — Docker daemon
- `postgresql` — PostgreSQL database
- `nginx` — Web server
- `networkmanager` — Network manager
- `fwupd` — Firmware updater

**User-level:**
- `git` — Version control
- `neovim` — Terminal editor
- `fish` — Shell
- `starship` — Shell prompt
- `helix` — Modal editor

#### Example: Development System

```lua
programs = {
    -- System services
    openssh = {
        enable = true,
        service = {enable = true, service_name = "sshd"},
    },
    docker = {
        enable = true,
        service = {enable = true, service_name = "docker"},
    },
}

users = {
    alice = {
        programs = {
            git = {
                enable = true,
                config = {
                    user_name = "Alice",
                    user_email = "alice@example.com",
                },
            },
            neovim = {enable = true},
        },
    },
}
```

#### Common Mistakes

**Problem:** Confusing `programs` (high-level) with `packages` (low-level)
```lua
programs = {
    "git",  -- Wrong: packages go in 'packages' list
    "vim",
}
```

**Solution:** Use `packages` for package names, `programs` for configs
```lua
packages = {"git", "vim"},

programs = {
    git = {enable = true, config = {...}},
}
```

---

## Common Errors & Solutions

### 1. Unknown Configuration Section

**Problem:**
```
Error: Unknown configuration section 'base_destribution'
```

**Cause:** Typo in section name (here: `destribution` instead of `distribution`)

**Solution:** Check spelling against valid sections:
- `base_distribution` ✓
- `repos`
- `devices`
- `boot`
- `hardware`
- `locale`
- `network`
- `users`
- `desktop`
- `fonts`
- `packages`
- `services`
- `programs`

**Example:**
```lua
-- Wrong:
base_destribution = "arch"  -- Typo

-- Correct:
base_distribution = "arch"
```

---

### 2. Type Errors

**Problem:**
```
Error: Expected dict for 'boot', got list
```

**Cause:** Wrong data type (using list `{...}` instead of dict `{key = value}`)

**Solution:** Use correct type for each section:
- `base_distribution` — string (`"arch"`)
- `repos` — dict (`{arch_repo = ...}`)
- `devices` — dict (`{disk0 = ...}`)
- `boot` — dict (`{kernel = {...}}`)
- `packages` — list (`{"git", "vim"}`)
- `services` — dict (`{ssh = {enable = true}}`)
- `users` — dict (`{alice = {...}}`)

**Example:**
```lua
-- Wrong: packages as dict
packages = {
    git = true,
    vim = true,
}

-- Correct: packages as list
packages = {
    "git",
    "vim",
}
```

---

### 3. Invalid Enumeration Values

**Problem:**
```
Error: Invalid value 'gnome-desktop' for boot.loader.type
Valid values: 'systemd-boot', 'grub'
```

**Cause:** Using value not in allowed list

**Solution:** Use only valid values:
- `boot.loader.type` → `"systemd-boot"` or `"grub"`
- `base_distribution` → `"arch"` or `"debian"`
- `desktop.environment` → `"gnome"`, `"plasma"`, `"xfce"`, etc.

**Example:**
```lua
-- Wrong:
boot = {
    loader = {type = "lilo"},  -- Lilo not supported
}

-- Correct:
boot = {
    loader = {type = "systemd-boot"},
}
```

---

### 4. Missing Required Fields

**Problem:**
```
Error: Missing required field 'base_distribution'
```

**Cause:** Omitted a required section

**Solution:** Add required section:
- `base_distribution` — **Required** (must be "arch" or "debian")

All other sections are optional.

**Example:**
```lua
-- Wrong: missing base_distribution
return {
    repos = {...},
    packages = {"git"},
}

-- Correct: include base_distribution
return {
    base_distribution = "arch",
    repos = {...},
    packages = {"git"},
}
```

---

### 5. Invalid Repository URLs

**Problem:**
```
Error: Invalid repository URL 'htp://example.com'
```

**Cause:** Typo in URL or missing scheme (http/https)

**Solution:** Check URL syntax:
- Must start with `http://` or `https://`
- Must be reachable

**Example:**
```lua
-- Wrong:
repos = {
    official = repos.arch_repo("htp://mirror.example.com"),  -- Typo
}

-- Correct:
repos = {
    official = repos.arch_repo("https://mirror.example.com"),
}
```

---

### 6. Partition Scheme Errors

**Problem:**
```
Error: Partition sizes exceed disk capacity (need 150GB, have 100GB)
```

**Cause:** Partition sizes don't fit on disk

**Solution:** Ensure partitions sum to disk size:
- Use percentages (`"100%"`) for last partition
- Or calculate exact sizes
- Leave room for partition table/alignment

**Example:**
```lua
-- Wrong: exceeds disk
devices = {
    disk0 = disk.disk_definition("/dev/sda", "50GB")
        :partition("boot", "30GB", "vfat", "/boot")
        :partition("root", "30GB", "ext4", "/"),  -- Total 60GB > 50GB!
}

-- Correct: uses percentage
devices = {
    disk0 = disk.disk_definition("/dev/sda", "50GB")
        :partition("boot", "512M", "vfat", "/boot")
        :partition("root", "100%", "ext4", "/"),
}
```

---

### 7. Timezone Not Found

**Problem:**
```
Error: Unknown timezone 'Canada/Mountain'
```

**Cause:** Invalid timezone name (not in IANA database)

**Solution:** Use IANA timezone format: `Continent/City`

**Valid timezones:**
```
America/New_York
America/Toronto
America/Denver
America/Los_Angeles
Europe/London
Europe/Paris
Europe/Berlin
Asia/Tokyo
Australia/Sydney
UTC
```

Find all timezones: `timedatectl list-timezones`

**Example:**
```lua
-- Wrong:
locale = {
    timezone = "Canada/Mountain",  -- Not in IANA database
}

-- Correct:
locale = {
    timezone = "America/Denver",   -- Use Continent/City format
}
```

---

### 8. Invalid Shell Path

**Problem:**
```
Error: Shell '/bin/bash' not available (not in packages)
```

**Cause:** Shell specified but not installed

**Solution:** Add shell to packages first, then reference in users:

**Example:**
```lua
-- Wrong: fish shell not installed
packages = {"git"}
users = {
    alice = {shell = "/bin/fish"},  -- Error!
}

-- Correct: add fish to packages
packages = {"git", "fish"}
users = {
    alice = {shell = "/bin/fish"},  -- Now OK
}
```

---

### 9. Desktop Environment Not Available

**Problem:**
```
Error: Unknown desktop environment 'kde'
```

**Cause:** Typo or unsupported environment name

**Solution:** Use exact desktop name:
- `"gnome"` (not gnome-desktop)
- `"plasma"` (not kde)
- `"xfce"` ✓
- `"cosmic"` ✓

**Example:**
```lua
-- Wrong:
desktop = {
    environment = "kde",  -- Should be 'plasma'
}

-- Correct:
desktop = {
    environment = "plasma",
}
```

---

### 10. Invalid User Group for Distro

**Problem:**
```
Error: Group 'wheel' does not exist on Debian
(use 'sudo' for administrative access)
```

**Cause:** Using distro-specific group name on wrong distro

**Solution:** Use correct group per distro:
- **Arch:** `"wheel"` for sudo access
- **Debian:** `"sudo"` for sudo access

**Example:**
```lua
-- Wrong on Debian:
users = {
    alice = {
        groups = {"wheel"},  -- Doesn't exist on Debian
    },
}

-- Correct for Debian:
users = {
    alice = {
        groups = {"sudo"},   -- Correct for Debian
    },
}

-- Correct for Arch:
users = {
    alice = {
        groups = {"wheel"},  -- Correct for Arch
    },
}
```

---

## Advanced Topics

### Custom Programs and Modules

KodOS programs are registered in the program registry and can be extended.
Each program has:

- **Installation logic** — How to install the program
- **Configuration schema** — What config options it accepts
- **Service hooks** — Optional systemd service management
- **User scope** — System-level or user-level

See [ARCHITECTURE.md](../ARCHITECTURE.md) for program registry details.

### Lua Functions and Macros

KodOS provides Lua modules for dynamic configuration:

#### disk Module

Define disk partitions:

```lua
local disk = require("disk")

devices = {
    disk0 = disk.disk_definition("/dev/sda", "100GB")
        :partition("boot", "512M", "vfat", "/boot")
        :partition("root", "100%", "ext4", "/"),
}
```

#### repos Module

Define package repositories:

```lua
local repos = require("repos")

repos = {
    official = repos.arch_repo("https://mirror.example.com"),
    aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay.git"),
}
```

#### Conditional Configuration

Use Lua conditionals for environment-specific settings:

```lua
local use_laptop = true
local use_docker = true

return {
    packages = {
        "git",
        "vim",
        (use_docker and "docker" or nil),
        (use_laptop and "tlp" or nil),  -- Power management
    },
    
    services = (use_docker and {
        docker = {enable = true},
    } or {}),
}
```

Or use a helper function:

```lua
local function list_concat(...)
    local result = {}
    for _, list in ipairs({...}) do
        for _, item in ipairs(list) do
            if item then table.insert(result, item) end
        end
    end
    return result
end

packages = list_concat(
    {"git", "vim"},
    use_docker and {"docker"} or {},
    use_laptop and {"tlp"} or {}
)
```

### Reusing Configuration Across Machines

Define a base configuration and customize per machine:

**`~/.kod/base.lua`:**
```lua
return {
    base_distribution = "arch",
    locale = {
        timezone = "America/Denver",
        keymap = "us",
    },
    packages = {"git", "vim", "tmux"},
}
```

**`~/.kod/laptop.lua`:**
```lua
local base = require("base")

return {
    -- Inherit from base
    base_distribution = base.base_distribution,
    locale = base.locale,
    packages = base.packages .. {"tlp", "powertop"},
    
    -- Laptop-specific
    network = {hostname = "alice-laptop"},
    desktop = {environment = "gnome"},
}
```

**`~/.kod/server.lua`:**
```lua
local base = require("base")

return {
    -- Inherit from base
    base_distribution = base.base_distribution,
    locale = base.locale,
    packages = base.packages .. {"nginx", "postgresql"},
    
    -- Server-specific (no desktop)
    network = {hostname = "alice-server"},
    services = {
        nginx = {enable = true},
        postgresql = {enable = true},
    },
}
```

Then install each config:

```bash
kod install --config ~/.kod/laptop.lua
kod install --config ~/.kod/server.lua
```

### Managing Multiple System Configs

Store configs in version control:

```
configs/
  ├── arch-laptop.lua
  ├── debian-server.lua
  ├── arch-desktop.lua
  └── README.md
```

With descriptions:

```lua
-- arch-laptop.lua
-- Machine: Alice's Dell XPS
-- Purpose: Development laptop
-- Distro: Arch Linux

return {
    -- configuration here
}
```

Use a Makefile for convenience:

```makefile
.PHONY: plan-laptop install-laptop plan-server install-server

plan-laptop:
	kod plan --config configs/arch-laptop.lua

install-laptop:
	kod install --config configs/arch-laptop.lua

plan-server:
	kod plan --config configs/debian-server.lua

install-server:
	kod install --config configs/debian-server.lua
```

### Configuration Validation and Testing

Validate a config before applying:

```bash
# Check for schema errors
kod config validate --config ~/.kod/config.lua

# Preview changes without applying
kod plan --config ~/.kod/config.lua

# Check only one section
kod config schema --section users
```

---

## Complete Examples

### Example 1: Minimal Arch Install

A bare-minimum Arch system with just base packages:

```lua
-- minimal-arch.lua
-- Minimal Arch Linux installation

return {
    base_distribution = "arch",
    
    -- Minimal packages
    packages = {
        "git",
        "vim",
        "htop",
    },
}
```

**What it does:**
- Installs Arch Linux base system
- Installs git, vim, htop
- No desktop, no desktop environment
- No extra services
- Minimal configuration

---

### Example 2: Desktop GNOME (Arch)

Full desktop setup with GNOME on Arch:

```lua
-- desktop-gnome-arch.lua
-- GNOME desktop workstation on Arch Linux

return {
    base_distribution = "arch",
    
    boot = {
        kernel = {
            package = "linux",
            modules = {"xhci_pci", "virtio_pci", "ahci"},
        },
        loader = {
            type = "systemd-boot",
            timeout = 10,
        },
    },
    
    locale = {
        locale = {
            default = "en_US.UTF-8 UTF-8",
            extra_generate = {"en_GB.UTF-8 UTF-8"},
        },
        timezone = "America/New_York",
        keymap = "us",
    },
    
    network = {
        hostname = "workstation",
        ipv6 = true,
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
    
    desktop = {
        environment = "gnome",
        enable = true,
    },
    
    fonts = {
        monospace = {"ttf-firacode-nerd"},
        sans_serif = {"noto-fonts"},
        emoji = {"noto-fonts-emoji"},
    },
    
    users = {
        alice = {
            shell = "/bin/bash",
            groups = {"wheel", "audio", "video"},
        },
    },
    
    packages = {
        "git",
        "vim",
        "tmux",
        "htop",
        "firefox",
        "discord",
    },
    
    programs = {
        networkmanager = {
            enable = true,
            service = {
                enable = true,
                service_name = "NetworkManager",
            },
        },
    },
}
```

**What it does:**
- Arch Linux with GNOME desktop
- PipeWire audio system
- Standard fonts (monospace, sans-serif, emoji)
- User account with wheel access
- Development tools (git, vim, tmux)
- Firefox and Discord
- NetworkManager for networking

---

### Example 3: Server (Debian)

Headless server setup on Debian:

```lua
-- server-debian.lua
-- Debian server: web, database, SSH

return {
    base_distribution = "debian",
    
    boot = {
        kernel = {package = "linux-image-amd64"},
        loader = {type = "grub"},
    },
    
    locale = {
        locale = {
            default = "en_US.UTF-8 UTF-8",
        },
        timezone = "UTC",
        keymap = "us",
    },
    
    network = {
        hostname = "production-server",
        ipv6 = true,
    },
    
    users = {
        root = {shell = "/bin/bash"},
        deploy = {
            shell = "/bin/bash",
            groups = {"sudo"},  -- sudo on Debian
        },
    },
    
    packages = {
        "git",
        "vim",
        "curl",
        "build-essential",
        "htop",
        "nginx",
        "postgresql",
    },
    
    services = {
        ssh = {enable = true},
        nginx = {enable = true, start = true},
        postgresql = {enable = true, start = true},
    },
    
    programs = {
        openssh = {
            enable = true,
            service = {
                enable = true,
                service_name = "sshd",
            },
        },
    },
}
```

**What it does:**
- Debian Linux server
- SSH, nginx, PostgreSQL enabled
- Standard development tools
- No desktop environment (headless)
- Time synchronized to UTC
- `deploy` user for deployments

---

### Example 4: Development Workstation (Arch)

Full development setup with multiple tools:

```lua
-- development-workstation.lua
-- Full development workstation on Arch Linux

local repos = require("repos")

return {
    base_distribution = "arch",
    
    repos = {
        official = repos.arch_repo(
            "https://mirror.cpsc.ucalgary.ca/mirror/archlinux.org"
        ),
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay.git"),
        flatpak = repos.flatpak_repo("flathub"),
    },
    
    boot = {
        kernel = {
            package = "linux",
            modules = {
                "xhci_pci", "ohci_pci", "ehci_pci", "virtio_pci",
                "ahci", "usbhid", "sr_mod", "virtio_blk",
            },
        },
        loader = {type = "systemd-boot", timeout = 10},
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
            default = "en_US.UTF-8 UTF-8",
            extra_generate = {"en_CA.UTF-8 UTF-8"},
        },
        timezone = "America/Denver",
        keymap = "us",
    },
    
    network = {
        hostname = "dev-workstation",
        ipv6 = true,
    },
    
    desktop = {
        environment = "plasma",
        enable = true,
    },
    
    fonts = {
        monospace = {
            "ttf-firacode-nerd",
            "ttf-sourcecodepro-nerd",
            "noto-fonts-cjk",
        },
        sans_serif = {"ttf-fira-sans", "noto-fonts"},
        emoji = {"noto-fonts-emoji"},
    },
    
    users = {
        alice = {
            shell = "/usr/bin/fish",
            groups = {"wheel", "docker", "audio", "video"},
            home_programs = {
                git = {
                    enable = true,
                    config = {
                        user_name = "Alice Smith",
                        user_email = "alice@example.com",
                    },
                },
                neovim = {enable = true},
            },
        },
    },
    
    packages = {
        -- Core utilities
        "git",
        "tmux",
        "htop",
        "ripgrep",
        "fzf",
        "bat",
        
        -- Development
        "base-devel",
        "cmake",
        "python",
        "nodejs",
        "rustup",
        
        -- Editors
        "neovim",
        "helix",
        
        -- Containers
        "docker",
        "docker-compose",
        
        -- Other tools
        "firefox",
        "vscode-bin",
        "postman",
        "vlc",
    },
    
    services = {
        ssh = {enable = true},
        docker = {enable = true, start = true},
    },
    
    programs = {
        openssh = {
            enable = true,
            service = {
                enable = true,
                service_name = "sshd",
            },
        },
        docker = {
            enable = true,
            service = {
                enable = true,
                service_name = "docker",
            },
        },
    },
}
```

**What it does:**
- Arch Linux with KDE Plasma desktop
- Complete development environment (C/C++, Python, Node.js, Rust)
- Git, tmux, fish shell
- Editors: Neovim, Helix
- Docker containerization
- SSH server enabled
- Development tools and utilities
- AUR and Flatpak support

---

## Command Reference

### kod config init

Generate a starter configuration template.

**Syntax:**
```bash
kod config init [--distro {arch,debian}] [--output FILE]
```

**Options:**
- `--distro {arch,debian}` — Target distribution (default: arch)
- `--output FILE` — Output file (default: ~/.kod/config.lua)

**Examples:**
```bash
# Generate Arch config to ~/.kod/config.lua
kod config init

# Generate Debian config to custom file
kod config init --distro debian --output my-debian-config.lua

# Generate and print to stdout
kod config init --distro arch --output /dev/stdout
```

---

### kod config schema

Display configuration schema documentation.

**Syntax:**
```bash
kod config schema [--section SECTION] [--format {text,json}]
```

**Options:**
- `--section SECTION` — Show only one section (default: all)
- `--format {text,json}` — Output format (default: text)

**Examples:**
```bash
# View all sections
kod config schema

# View only 'users' section
kod config schema --section users

# View 'boot' section as JSON
kod config schema --section boot --format json
```

---

### kod config validate

Validate a configuration file.

**Syntax:**
```bash
kod config validate --config FILE
```

**Options:**
- `--config FILE` — Configuration file to validate

**Examples:**
```bash
# Validate default config
kod config validate --config ~/.kod/config.lua

# Validate custom config
kod config validate --config configs/arch-laptop.lua
```

---

### kod plan

Preview installation plan without applying changes.

**Syntax:**
```bash
kod plan [--config FILE] [--baseline FILE]
```

**Options:**
- `--config FILE` — Configuration file (default: ~/.kod/config.lua)
- `--baseline FILE` — Baseline/previous plan (for updates)

**Examples:**
```bash
# Preview installation plan
kod plan --config ~/.kod/config.lua

# Preview update on existing system
kod plan --config ~/.kod/config.lua --baseline /var/lib/kod/plan.json
```

**Output includes:**
- List of steps that will execute
- Disk operations
- Package installations
- Service management
- User creation

---

### kod install

Apply configuration and install system.

**Syntax:**
```bash
kod install [--config FILE]
```

**Options:**
- `--config FILE` — Configuration file (default: ~/.kod/config.lua)

**Examples:**
```bash
# Install from default config
kod install

# Install from custom config
kod install --config ~/.kod/config.lua

# Install specific config
kod install --config configs/arch-laptop.lua
```

**On new system:**
- Partitions and formats disks
- Installs base OS
- Configures packages, users, services

**On existing system:**
- Updates packages
- Adds/updates users
- Enables/starts services
- Installs programs

---

## See Also

- [ARCHITECTURE.md](../ARCHITECTURE.md) — System design and internals
- [INSTALLATION_GUIDE.md](../INSTALLATION_GUIDE.md) — Installation instructions
- [cli-architecture.md](../cli-architecture.md) — CLI command structure
- [extending.md](../extending.md) — Extending with custom programs

