# Advanced User Configuration Guide

**Phase 5d introduces nested feature blocks for granular per-user configuration.**

This guide covers user-level identity, SSH keys, dotfiles, programs, and services.

---

## Overview: User Blocks in Phase 5d

Previous phases only supported basic user setup (shell, groups). Phase 5d adds five new nested blocks:

```lua
users = {
  username = {
    shell = "/bin/bash",              -- Existing: user shell
    
    -- NEW in Phase 5d:
    identity = { ... },               -- User name, password, groups
    ssh_keys = { ... },               -- SSH key setup
    dotfiles = { ... },               -- Dotfile deployment
    programs = { ... },               -- User-level programs
    services = { ... },               -- User-level services
    home_config = { ... },            -- Home directory config
  },
}
```

### Why Nested Blocks?

| Problem | Solution |
|---------|----------|
| Password setup scattered across configs | All identity info in one `identity` block |
| SSH key deployment manual | `ssh_keys` block automates it |
| Dotfile repos hard to track | `dotfiles` block centralizes management |
| User programs mixed with system | `programs` block keeps user customizations separate |
| User services not standardized | `services` block enables user-level systemd |

---

## User Identity Block

Configure user name, password, and group membership.

### Basic Example

```lua
users = {
  abuss = {
    identity = {
      name = "Antal Buss",
      hashed_password = "$6$MOkGLOzXlj0lIE2d$...",  -- mkpasswd generated
      groups = { "audio", "video", "wheel" },
    },
  },
}
```

### Password Hashing

Generate hashed passwords using `mkpasswd`:

```bash
# Arch Linux / most distros
mkpasswd -m sha-512

# Enter password: ***
# Hash: $6$MOkGLOzXlj0lIE2d$5sxAysiDyD/7ZfntgZaN3vJ48t.BMi2qwPxqjgVxGXKXrNlFxRvnO8uCvOlHaGW2pVDrjt0JLNR9GWH.2YT5j.
```

**Security:** Never commit plain-text passwords. Always use hashed passwords.

### User Groups

Common group membership:

| Group | Purpose |
|-------|---------|
| `audio` | Audio device access |
| `input` | Input device access (keyboard, mouse) |
| `video` | Video device access |
| `wheel` | Sudo access (on Arch) / admin group |
| `users` | Primary user group |
| `docker` | Docker access (if installed) |
| `libvirt` | Virtualization access |
| `scanner` | Scanner access |
| `lp` | Printer access |

### Root User Setup

```lua
users = {
  root = {
    shell = "/bin/bash",
    identity = {
      hashed_password = nil,  -- No password for root (only key access)
    },
  },
}
```

### Complete Example: eszkoz User

```lua
users = {
  root = {
    shell = "/bin/bash",
    identity = {
      hashed_password = nil,
    },
  },
  
  abuss = {
    shell = "/usr/bin/zsh",
    
    identity = {
      name = "Antal Buss",
      hashed_password = "$6$MOkGLOzXlj0lIE2d$5sxAysiDyD/7ZfntgZaN3vJ48t.BMi2qwPxqjgVxGXKXrNlFxRvnO8uCvOlHaGW2pVDrjt0JLNR9GWH.2YT5j.",
      groups = { "audio", "input", "users", "video", "wheel" },
    },
  },
}
```

---

## SSH Keys Block

Automate SSH key deployment.

### Basic Example

```lua
users = {
  abuss = {
    ssh_keys = {
      enabled = true,
      authorized = {
        "ssh-rsa AAAAB3NzaC1yc2EA...",
      },
    },
  },
}
```

### SSH Key Formats

kodos supports:

- `ssh-rsa` — RSA keys (2048-4096 bits)
- `ssh-ed25519` — EdDSA keys (recommended)
- `ecdsa-sha2-nistp256` — Elliptic Curve keys
- `ssh-dss` — DSA keys (deprecated)

### Generate SSH Keys

**Ed25519 (recommended):**

```bash
ssh-keygen -t ed25519 -C "antal.buss@gmail.com"
# Generates: ~/.ssh/id_ed25519.pub
# Starts with: ssh-ed25519 AAAA...
```

**RSA (legacy support):**

```bash
ssh-keygen -t rsa -b 4096 -C "antal.buss@gmail.com"
# Generates: ~/.ssh/id_rsa.pub
# Starts with: ssh-rsa AAAA...
```

### Multiple SSH Keys

Deploy multiple authorized keys:

```lua
ssh_keys = {
  enabled = true,
  authorized = {
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKz5...",  -- Laptop
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIQk9...",  -- Desktop
    "ssh-rsa AAAAB3NzaC1yc2EA...",                    -- Legacy RSA
  },
}
```

### Disable SSH

```lua
ssh_keys = {
  enabled = false,  -- Don't set up SSH keys
}
```

### Real-World Example: eszkoz

```lua
ssh_keys = {
  enabled = true,
  authorized = {
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDOA6V+TZJ+BmBAU4FB0nbhYQ9XOFZwCHdwXTuQkb77sPi6fVcbzso5AofUc+3DhfN56ATNOOslvjutSPE8kIp3Uv91/c7DE0RHoidNl3oLre8bau2FT+9AUTZnNEtWH/qXp5+fzvGk417mSL3M5jdoRwude+AzhPNXmbdAzn08TMGAkjGrMQejXItcG1OhXKUjqeLmB0A0l3Ac8DGQ6EcSRtgPCiej8Boabn21K2OBfq64KwW/MMh/FWTHndyBF/lhfEos7tGPvrDN+5G05oGjf0fnMOxsmAUdTDbtOTTeMTvDwjJdzsGUluEDbWBYPNlg5wacbimkv51/Bm4YwsGOkkUTy6eCCS3d5j8PrMbB2oNZfByga01FohhWSX9bv35KAP4nq7no9M6nXj8rQVsF0gPndPK/pgX46tpJG+pE1Ul6sSLR2jnrN6oBKzhdZJ54a2wwFSd207Zvahdx3m9JEVhccmDxWltxjKHz+zChAHsqWC9Zcqozt0mDRJNalW8fRXKcSWPGVy1rfbwltiQzij+ChCQQlUG78zW8lU7Bz6FuyDsEFpZSat7jtbdDBY0a4F0yb4lkNvu+5heg+dhlKCFj9YeRDrnvcz94OKvAZW1Gsjbs83n6wphBipxUWku7y86iYyAAYQGKs4jihhYWrFtfZhSf1m6EUKXoWX87KQ== antal.buss@gmail.com",
  },
}
```

---

## Dotfiles Block

Centralize dotfile management and deployment.

### Basic Example

```lua
users = {
  abuss = {
    dotfiles = {
      source_dir = "~/.dotfiles",
      repo_url = "http://git.homecloud.lan/abuss/dotconfig.git",
      deploy_tool = "stow",
    },
  },
}
```

### Understanding Dotfiles

**Dotfiles** are configuration files for terminal tools:

- `.bashrc`, `.zshrc` — Shell configuration
- `.config/helix/config.toml` — Editor configuration
- `.config/nvim/init.lua` — Neovim configuration
- `.gitconfig` — Git configuration
- `.ssh/config` — SSH client configuration

### Deployment Tools

**stow** (recommended):
- Simple symlink-based deployment
- Minimal dependencies
- Easy to customize per-tool

```lua
deploy_tool = "stow"
```

**chezmoi** (template support):
- Template-based configuration
- Supports conditional sections
- More powerful for complex setups

```lua
deploy_tool = "chezmoi"
```

**manual** (custom):
- Custom deployment script
- Full control over process

```lua
deploy_tool = "manual"
```

### Dotfile Repository Structure (stow)

Typical layout for stow:

```
~/.dotfiles/
├── zsh/
│   └── .zshrc
├── git/
│   └── .gitconfig
├── nvim/
│   └── .config/nvim/init.lua
├── helix/
│   └── .config/helix/config.toml
└── starship/
    └── .config/starship.toml
```

Deploy with:

```bash
cd ~/.dotfiles
stow zsh git nvim helix starship
```

Creates symlinks:
- `~/.zshrc` → `~/.dotfiles/zsh/.zshrc`
- `~/.gitconfig` → `~/.dotfiles/git/.gitconfig`
- etc.

### Clone Repository

The `dotfiles` block clones the repo:

```lua
dotfiles = {
  source_dir = "~/.dotfiles",              -- Where to clone
  repo_url = "http://git.../dotconfig.git",  -- Repository URL
  deploy_tool = "stow",
}
```

kodos will:
1. Clone `repo_url` to `source_dir`
2. Run deployment tool (stow, chezmoi, etc.)

### Real-World Example: eszkoz

```lua
dotfiles = {
  source_dir = "~/.dotfiles",
  repo_url = "http://git.homecloud.lan/abuss/dotconfig.git",
  deploy_tool = "stow",
}
```

kodos execution:
```bash
# 1. Clone repo
git clone http://git.homecloud.lan/abuss/dotconfig.git ~/.dotfiles

# 2. Deploy with stow
cd ~/.dotfiles
stow zsh git nvim helix emacs starship
```

---

## User Programs Block

Configure user-level programs with per-program customization.

### Basic Example

```lua
users = {
  abuss = {
    programs = {
      git = {
        enable = true,
      },
      
      zsh = {
        enable = true,
        deploy_config = true,  -- Deploy from dotfiles
      },
    },
  },
}
```

### Program Types

**Simple programs (package install):**

```lua
programs = {
  fish = {
    enable = true,  -- Install fish shell
  },
}
```

**Programs with configuration:**

```lua
programs = {
  git = {
    enable = true,
    config = configs.git({
      user_name = "Antal Buss",
      user_email = "antal.buss@gmail.com",
      core_editor = "helix",
    }),
  },
}
```

**Programs with dotfile deployment:**

```lua
programs = {
  neovim = {
    enable = true,
    deploy_config = true,  -- Deploy ~/.config/nvim/init.lua from dotfiles
  },
}
```

**Programs with extra packages:**

```lua
programs = {
  emacs = {
    enable = true,
    package = "emacs-wayland",  -- Override package name
    deploy_config = true,
    extra_packages = {
      "aspell",
      "aspell-en",
    },
  },
}
```

### Common User Programs

| Program | Purpose | Config |
|---------|---------|--------|
| `git` | Version control | `configs.git(options)` |
| `zsh` | Shell | Deploy from dotfiles |
| `fish` | Shell | Deploy from dotfiles |
| `bash` | Shell | Deploy from dotfiles |
| `neovim` | Editor | Deploy from dotfiles |
| `helix` | Editor | Deploy from dotfiles |
| `emacs` | Editor | Deploy from dotfiles + extra packages |
| `starship` | Shell prompt | Deploy from dotfiles |

### Real-World Example: eszkoz

```lua
programs = {
  git = {
    enable = true,
    config = configs.git({
      user_name = "Antal Buss",
      user_email = "antal.buss@gmail.com",
      core_editor = "helix",
    }),
  },
  
  starship = {
    enable = true,
    deploy_config = true,
  },
  
  fish = {
    enable = true,
  },
  
  zsh = {
    enable = true,
    deploy_config = true,
  },
  
  neovim = {
    enable = true,
    deploy_config = true,
  },
  
  helix = {
    enable = true,
    deploy_config = true,
  },
  
  emacs = {
    enable = true,
    package = "emacs-wayland",
    deploy_config = true,
    extra_packages = { "aspell", "aspell-en" },
  },
  
  dconf = {
    enable = true,  -- Gnome dconf
    config = configs.dconf(require("gnome")),
  },
}
```

---

## User Services Block

Configure user-level systemd services.

### Basic Example

```lua
users = {
  abuss = {
    services = {
      syncthing = {
        enable = false,
      },
    },
  },
}
```

### Service Configuration

**Enable a service:**

```lua
services = {
  syncthing = {
    enable = true,  -- Start syncthing
  },
}
```

**Custom service name:**

```lua
services = {
  syncthing = {
    enable = true,
    service_name = "syncthing@abuss",  -- Custom systemd unit
  },
}
```

**Service with configuration:**

```lua
services = {
  syncthing = {
    enable = true,
    config = configs.syncthing({
      service_name = "syncthing",
      options = "'--no-browser' '--no-restart' '--logflags=0'",
    }),
  },
}
```

### Real-World Example: eszkoz

```lua
services = {
  syncthing = {
    enable = false,  -- Disabled but configured
    config = configs.syncthing({
      service_name = "syncthing",
      options = "'--no-browser' '--no-restart' '--logflags=0' '--gui-address=0.0.0.0:8384'",
    }),
  },
}
```

---

## Home Config Block

Configure user home directory settings.

### Basic Example

```lua
users = {
  abuss = {
    home_config = {
      dotfiles_repos = {
        "http://git.homecloud.lan/abuss/dotconfig.git",
      },
    },
  },
}
```

### Available Options

| Field | Purpose |
|-------|---------|
| `dotfiles_repos` | List of dotfile repositories to manage |

---

## Complete Multi-User Example

Configure multiple users with different roles:

```lua
users = {
  root = {
    shell = "/bin/bash",
    identity = {
      hashed_password = nil,  -- No password
    },
  },
  
  abuss = {
    shell = "/usr/bin/zsh",
    
    identity = {
      name = "Antal Buss",
      hashed_password = "$6$MOkGLOzXlj0lIE2d$...",
      groups = { "audio", "input", "users", "video", "wheel" },
    },
    
    ssh_keys = {
      enabled = true,
      authorized = {
        "ssh-rsa AAAAB3NzaC1yc2EA...",
      },
    },
    
    dotfiles = {
      source_dir = "~/.dotfiles",
      repo_url = "http://git.homecloud.lan/abuss/dotconfig.git",
      deploy_tool = "stow",
    },
    
    programs = {
      git = {
        enable = true,
        config = configs.git({
          user_name = "Antal Buss",
          user_email = "antal.buss@gmail.com",
          core_editor = "helix",
        }),
      },
      
      zsh = {
        enable = true,
        deploy_config = true,
      },
      
      neovim = {
        enable = true,
        deploy_config = true,
      },
    },
    
    services = {
      syncthing = {
        enable = false,
      },
    },
  },
  
  guest = {
    shell = "/bin/bash",
    
    identity = {
      name = "Guest User",
      hashed_password = nil,
      groups = { "users" },
    },
    
    programs = {
      git = { enable = true },
      zsh = { enable = true },
    },
  },
}
```

---

## Validation & Errors

### Password Hash Validation

Invalid password hash:

```lua
identity = {
  name = "Antal Buss",
  hashed_password = "not-a-valid-hash",  -- ERROR
}
```

**Error:** `Invalid password hash format`

**Fix:** Use `mkpasswd` to generate proper hash

### SSH Key Validation

Invalid SSH key:

```lua
ssh_keys = {
  enabled = true,
  authorized = {
    "this is not a valid ssh key",  -- ERROR
  },
}
```

**Error:** `Invalid SSH key format`

**Fix:** Use valid SSH key starting with `ssh-rsa`, `ssh-ed25519`, etc.

### Group Name Validation

Invalid group name:

```lua
identity = {
  name = "User",
  groups = { "wheel", "invalid-group-name-with-dashes" },  -- ERROR
}
```

**Error:** `Invalid group name`

**Fix:** Use valid group names (alphanumeric, underscore)

---

## Migration from Phase 5c

### Before (Phase 5c)

```lua
users = {
  abuss = {
    shell = "/usr/bin/zsh",
  },
}
```

### After (Phase 5d)

```lua
users = {
  abuss = {
    shell = "/usr/bin/zsh",
    
    identity = {
      name = "Antal Buss",
      hashed_password = "$6$...",
      groups = { "audio", "wheel" },
    },
    
    ssh_keys = {
      enabled = true,
      authorized = { "ssh-rsa AAAA..." },
    },
    
    dotfiles = {
      source_dir = "~/.dotfiles",
      repo_url = "http://git.../dotconfig.git",
      deploy_tool = "stow",
    },
    
    programs = {
      git = { enable = true },
      zsh = { enable = true, deploy_config = true },
    },
  },
}
```

---

## Troubleshooting

### Issue: Password Not Accepted

**Symptom:** User can't log in with configured password

**Cause:** Invalid password hash or wrong algorithm

**Solution:**
```bash
# Regenerate with same algorithm
mkpasswd -m sha-512
# Copy new hash to config
```

### Issue: SSH Key Rejected

**Symptom:** SSH key in config but can't connect

**Cause:** Key format invalid or permissions wrong

**Solution:**
```bash
# Verify key format
ssh-keygen -l -f ~/.ssh/id_ed25519.pub

# Copy correct format to config
cat ~/.ssh/id_ed25519.pub  # Should start with ssh-ed25519
```

### Issue: Dotfiles Not Deployed

**Symptom:** Dotfiles repo cloned but config files not symlinked

**Cause:** Deployment tool not found or failed

**Solution:**
```bash
# Verify stow installed
which stow

# Test manual deployment
cd ~/.dotfiles
stow zsh git

# Check symlinks created
ls -la ~/
```

### Issue: User Programs Not Installed

**Symptom:** `enable = true` but program not installed

**Cause:** Package name not in distro repos

**Solution:**
```lua
programs = {
  emacs = {
    enable = true,
    package = "emacs-wayland",  -- Specify exact package name
  },
}
```

---

## Performance Considerations

### SSH Key Setup

Adding SSH keys adds minimal overhead (<100ms):

```lua
ssh_keys = {
  enabled = true,
  authorized = {
    -- Each key: ~1-2ms to append
  },
}
```

### Dotfile Deployment

Cloning and deploying dotfiles can be slow:

```lua
dotfiles = {
  source_dir = "~/.dotfiles",
  repo_url = "http://git.../dotconfig.git",  -- Network I/O
  deploy_tool = "stow",
}
```

**Time estimates:**
- Clone (small repo): 5-15s
- Stow deployment: 1-5s
- Total: 6-20s per user

### User Programs

Each program adds:

| Operation | Time |
|-----------|------|
| Package install | 2-30s (depends on size) |
| Dotfile deploy | 1-5s |
| Config generation | <100ms |

---

## Links & References

- [PHASE-5D-STRUCTURED-DESIGN.md](./PHASE-5D-STRUCTURED-DESIGN.md) — Full schema overview
- [eszkoz User Configuration](../tests/fixtures/eszkoz-config-5d.lua) — Real-world example
- [Dotfiles Guide](https://github.com/anishathalye/dotfiles) — External reference
- [systemd User Services](https://wiki.archlinux.org/title/Systemd/User) — External reference

---

## Summary

Phase 5d user blocks enable:

✅ Per-user identity, password, and group management  
✅ SSH key deployment automation  
✅ Dotfile repository integration  
✅ User-level program configuration  
✅ User-level systemd services  

All features are optional and Phase 5c compatible.
