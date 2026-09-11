"""Top-level configuration schema (Phase 1).

Maps each valid top-level config option to its expected type.
"""

SCHEMA = {
    "base_distribution": str,
    "repos": dict,
    "devices": dict,
    "boot": dict,
    "hardware": dict,
    "locale": dict,
    "network": dict,
    "users": dict,
    "desktop": dict,
    "fonts": dict,
    "packages": list,
    "services": dict,
    "programs": dict,  # Phase 3: Program registry section (optional)
}

SECTION_HELP = {
    "base_distribution": {
        "description": "Base Linux distribution to install.",
        "type": "string",
        "required": True,
        "valid_values": ["arch", "debian"],
        "example": 'base_distribution = "arch"',
        "error_help": "Must be 'arch' or 'debian', e.g.: base_distribution = \"arch\"",
    },
    
    "boot": {
        "description": "Kernel and bootloader configuration.",
        "type": "dict",
        "required": False,
        "example": '''boot = {
    kernel = {
        package = "linux-lts",
        modules = {"xhci_pci", "virtio_blk"},
    },
    loader = {
        type = "systemd-boot",
        timeout = 10,
    },
}''',
        "fields": {
            "kernel": {
                "description": "Kernel package and loadable modules.",
                "type": "dict",
                "required": False,
                "fields": {
                    "package": {
                        "description": "Kernel package name (e.g., 'linux', 'linux-lts', 'linux-hardened').",
                        "type": "string",
                        "required": False,
                        "default": "linux",
                    },
                    "modules": {
                        "description": "List of kernel modules to load at boot (for initramfs).",
                        "type": "list",
                        "required": False,
                        "example": '{"xhci_pci", "virtio_blk", "ahci"}',
                    },
                },
            },
            "loader": {
                "description": "Bootloader configuration.",
                "type": "dict",
                "required": False,
                "fields": {
                    "type": {
                        "description": "Bootloader type.",
                        "type": "string",
                        "required": False,
                        "valid_values": ["systemd-boot", "grub"],
                        "default": "systemd-boot",
                    },
                    "timeout": {
                        "description": "Boot menu timeout in seconds.",
                        "type": "number",
                        "required": False,
                        "default": 10,
                    },
                },
            },
        },
    },
    
    "hardware": {
        "description": "Hardware features and configurations.",
        "type": "dict",
        "required": False,
        "example": '''hardware = {
    pipewire = {
        enable = true,
        extra_packages = {"pipewire-alsa", "pipewire-pulse"},
    },
}''',
        "fields": {
            "pipewire": {
                "description": "PipeWire audio system (replaces PulseAudio).",
                "type": "dict",
                "required": False,
                "fields": {
                    "enable": {
                        "description": "Enable PipeWire.",
                        "type": "boolean",
                        "required": False,
                        "default": False,
                    },
                    "extra_packages": {
                        "description": "Additional PipeWire packages (e.g., ALSA/PulseAudio compatibility).",
                        "type": "list",
                        "required": False,
                        "example": '{"pipewire-alsa", "pipewire-pulse"}',
                    },
                },
            },
        },
    },
    
    "locale": {
        "description": "Localization settings (language, timezone, environment variables).",
        "type": "dict",
        "required": False,
        "example": '''locale = {
    locale = {
        default = "en_US.UTF-8 UTF-8",
        extra_generate = {"en_GB.UTF-8 UTF-8"},
    },
    timezone = "America/New_York",
    keymap = "us",
}''',
        "fields": {
            "locale": {
                "description": "Locale settings.",
                "type": "dict",
                "required": False,
                "fields": {
                    "default": {
                        "description": "Default system locale (format: 'en_US.UTF-8 UTF-8').",
                        "type": "string",
                        "required": False,
                        "default": "en_US.UTF-8 UTF-8",
                    },
                    "extra_generate": {
                        "description": "Additional locales to generate.",
                        "type": "list",
                        "required": False,
                    },
                },
            },
            "timezone": {
                "description": "System timezone (IANA format: 'America/New_York', 'Europe/London').",
                "type": "string",
                "required": False,
                "example": '"America/New_York"',
            },
            "keymap": {
                "description": "Console keyboard layout.",
                "type": "string",
                "required": False,
                "default": "us",
            },
        },
    },
    
    "network": {
        "description": "Network configuration (hostname, IPv6).",
        "type": "dict",
        "required": False,
        "example": '''network = {
    hostname = "mycomputer",
    ipv6 = true,
}''',
        "fields": {
            "hostname": {
                "description": "System hostname (computer name on network).",
                "type": "string",
                "required": False,
            },
            "ipv6": {
                "description": "Enable IPv6 support.",
                "type": "boolean",
                "required": False,
                "default": True,
            },
        },
    },
    
    "users": {
        "description": "User accounts (login, shell, groups, home configuration).",
        "type": "dict",
        "required": False,
        "example": '''users = {
    alice = {
        shell = "/bin/bash",
        groups = {"wheel"},
        home_programs = {neovim = true},
    },
}''',
        "fields": {
            "USERNAME": {
                "description": "Username (key in users dict). Fields inside each user:",
                "type": "dict",
                "required": False,
                "fields": {
                    "shell": {
                        "description": "Login shell (e.g., '/bin/bash', '/bin/fish').",
                        "type": "string",
                        "required": False,
                        "default": "/bin/bash",
                    },
                    "groups": {
                        "description": "Groups to add user to (e.g., 'wheel', 'sudo').",
                        "type": "list",
                        "required": False,
                        "example": '{"wheel", "docker"}',
                    },
                    "home_programs": {
                        "description": "User-scoped programs to install (key = program name, value = config).",
                        "type": "dict",
                        "required": False,
                        "example": '{neovim = true, git = true}',
                    },
                },
            },
        },
    },
    
    "packages": {
        "description": "List of system packages to install (package manager names).",
        "type": "list",
        "required": False,
        "example": '''packages = {"vim", "tmux", "git", "htop", "neofetch"}''',
        "error_help": "Must be a list of strings (package names), not a dict.",
    },
    
    "services": {
        "description": "System services to enable/start (e.g., ssh, nginx, docker).",
        "type": "dict",
        "required": False,
        "example": '''services = {
    ssh = { enable = true },
    nginx = { enable = true, start = true },
}''',
        "fields": {
            "SERVICE_NAME": {
                "description": "Service name (key in services dict). Config options:",
                "type": "dict",
                "required": False,
                "fields": {
                    "enable": {
                        "description": "Enable service to start on boot.",
                        "type": "boolean",
                        "required": False,
                    },
                    "start": {
                        "description": "Start service immediately (after install).",
                        "type": "boolean",
                        "required": False,
                    },
                },
            },
        },
    },
    
    "repos": {
        "description": "Repository definitions (package sources).",
        "type": "dict",
        "required": False,
        "example": '''repos = {
    official = repos.arch_repo("https://mirror.example.com/archlinux"),
    aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay.git"),
}''',
        "fields": {
            "REPO_NAME": {
                "description": "Repository identifier (key). Use repo.* functions (arch_repo, aur_repo, flatpak_repo) as values.",
                "type": "dict or string",
                "required": False,
            },
        },
    },
    
    "devices": {
        "description": "Disk and partition definitions for system installation.",
        "type": "dict",
        "required": False,
        "example": '''devices = {
    disk0 = disk.disk_definition("/dev/sda", "50GB"),
}''',
        "fields": {
            "DISK_NAME": {
                "description": "Disk identifier (key). Use disk.disk_definition() to define.",
                "type": "result of disk.disk_definition()",
                "required": False,
            },
        },
    },
    
    "desktop": {
        "description": "Desktop environment selection (GNOME, KDE Plasma, XFCE, etc.).",
        "type": "dict",
        "required": False,
        "example": '''desktop = {
    environment = "plasma",
    enable = true,
}''',
        "fields": {
            "environment": {
                "description": "Desktop environment (e.g., 'gnome', 'plasma', 'xfce', 'cosmic').",
                "type": "string",
                "required": False,
            },
            "enable": {
                "description": "Enable desktop environment installation.",
                "type": "boolean",
                "required": False,
                "default": True,
            },
        },
    },
    
    "fonts": {
        "description": "Font packages to install (monospace, sans-serif, CJK, emoji).",
        "type": "dict",
        "required": False,
        "example": '''fonts = {
    monospace = {"noto-fonts-cjk"},
    enable = true,
}''',
        "fields": {
            "monospace": {
                "description": "Monospace font packages.",
                "type": "list",
                "required": False,
                "example": '{"noto-fonts-cjk", "liberation-fonts"}',
            },
            "sans_serif": {
                "description": "Sans-serif font packages.",
                "type": "list",
                "required": False,
            },
            "emoji": {
                "description": "Emoji font packages.",
                "type": "list",
                "required": False,
            },
            "enable": {
                "description": "Enable font installation.",
                "type": "boolean",
                "required": False,
                "default": True,
            },
        },
    },
    
    "programs": {
        "description": "Program configurations at system level (custom programs with install logic).",
        "type": "dict",
        "required": False,
        "example": '''programs = {
    neovim = { enable = true },
    git = { enable = true, config = {} },
}''',
        "fields": {
            "PROGRAM_NAME": {
                "description": "Program name (key). Value is program config (passed to program's schema).",
                "type": "dict",
                "required": False,
                "fields": {
                    "enable": {
                        "description": "Enable program installation.",
                        "type": "boolean",
                        "required": False,
                    },
                },
            },
        },
    },
}
