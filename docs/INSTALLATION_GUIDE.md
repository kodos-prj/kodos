# Real Installation Guide: Using Kodos to Install Systems

**Status:** Phase 3 (Program Registry) is complete. Real installations are ready to begin!

**Current Phases Complete:**
- ✅ Phase 1: Configuration System (config validation, compilation, CLI)
- ✅ Phase 2: Modular Architecture (filesystem, users, packages, services, boot)
- ✅ Phase 3: Program Registry (builtin programs, user plugins, CLI commands)

---

## Quick Start: What Changed in configuration.lua?

### Summary
The **good news:** Your existing `configuration.lua` files will continue to work as-is. The **new capability:** You can now use the **programs section** to configure applications like git, neovim, and syncthing.

### Before (Still Works)
```lua
return {
    locale = {...},
    network = {...},
    users = {...},
    -- ... everything else
}
```

### After (New Capability)
```lua
return {
    locale = {...},
    network = {...},
    users = {
        alice = {
            -- ... user config ...
            
            -- NEW: Programs section!
            -- This is where you configure applications
            programs = {
                git = {
                    user_name = "Alice",
                    email = "alice@example.com",
                    signing_key = "ABC123DEF456"  -- optional
                },
                neovim = {
                    python_provider = true,
                    node_provider = true
                },
                syncthing = {
                    auto_start = true,
                    listen_address = "127.0.0.1:8384"
                }
            }
        }
    },
    -- ... everything else
}
```

---

## Available Builtin Programs

### 1. Git

Configure git with user name, email, and optional signing key.

**Schema:**
```lua
git = {
    user_name = "Alice",           -- required: string
    email = "alice@example.com",   -- required: email format
    signing_key = "ABC123DEF456"   -- optional: GPG key ID
}
```

**What it does:**
- Runs: `git config --global user.name 'Alice'`
- Runs: `git config --global user.email 'alice@example.com'`
- If signing_key provided: `git config --global user.signingkey 'ABC123DEF456'`

**Example:**
```lua
programs = {
    git = {
        user_name = "Antal Buss",
        email = "antal.buss@gmail.com",
        signing_key = "9A1B2C3D4E5F6A7B"  -- optional
    }
}
```

---

### 2. Neovim

Install Neovim with optional language providers.

**Schema:**
```lua
neovim = {
    python_provider = false,  -- optional: Install Python provider (default: false)
    ruby_provider = false,    -- optional: Install Ruby provider (default: false)
    node_provider = true      -- optional: Install Node.js provider (default: true)
}
```

**What it does:**
- Installs `neovim` package
- If `python_provider=true`: Installs `python-pynvim`
- If `ruby_provider=true`: Installs `ruby-neovim`
- If `node_provider=true`: Installs `nodejs-neovim`

**Example:**
```lua
programs = {
    neovim = {
        python_provider = true,
        node_provider = true,
        ruby_provider = false
    }
}
```

---

### 3. Syncthing

Enable and configure the Syncthing service.

**Schema:**
```lua
syncthing = {
    auto_start = true,                      -- optional: Auto-start on boot (default: true)
    listen_address = "127.0.0.1:8384"       -- optional: GUI listen address (default: 127.0.0.1:8384)
}
```

**What it does:**
- Runs: `systemctl enable syncthing`
- If `auto_start=true`: Runs: `systemctl start syncthing`

**Example:**
```lua
programs = {
    syncthing = {
        auto_start = true,
        listen_address = "0.0.0.0:8384"  -- Listen on all interfaces
    }
}
```

---

## Program Scope: System vs User Level

Each program declares a **scope** that determines where it can be configured:

| Scope | Location | Use Case |
|-------|----------|----------|
| `"user"` | User-level only (`users.alice.programs`) | Per-user configuration (git, neovim) |
| `"system"` | System-level only (top-level `programs`) | System-wide services or defaults |
| `"both"` | Either or both levels | Works at system or user level (syncthing) |

### What's the Difference?

**User-Level Programs** (scope: `"user"`):
- Configured for each user separately
- Each user can have different settings
- Examples: git (user name/email), neovim (user preferences)
- Location: Inside `users.<username>.programs`

```lua
users = {
    alice = {
        programs = {
            git = {
                user_name = "Alice",
                email = "alice@example.com"
            }
        }
    },
    bob = {
        programs = {
            git = {
                user_name = "Bob",
                email = "bob@example.com"  -- Different identity
            }
        }
    }
}
```

**System-Level Programs** (scope: `"system"`):
- Configured once for the entire system
- Applied globally to all users
- Examples: firewall rules, system services
- Location: Top-level `programs` section

```lua
-- System-level configuration
programs = {
    firewall = {
        enabled = true,
        rules = {...}
    }
}
```

**Both-Level Programs** (scope: `"both"`):
- Can be configured at system level AND/OR user level
- System config provides defaults
- User config can override system defaults
- Example: syncthing can be a system service (global) or per-user (user-specific folders)

### Example: Git at Both Levels

Git is a "user" scope program, but you can see how Syncthing (scope: "both") works:

```lua
-- Syncthing: System level (global defaults)
programs = {
    syncthing = {
        auto_start = true,
        listen_address = "127.0.0.1:8384"
    }
}

users = {
    alice = {
        programs = {
            -- Alice overrides system defaults for her user
            syncthing = {
                listen_address = "0.0.0.0:8384"  -- Overrides system setting
            }
            -- auto_start inherited from system config: true
        }
    },
    bob = {
        programs = {
            -- Bob uses system defaults (no override needed)
            -- He gets: auto_start=true, listen_address=127.0.0.1:8384
        }
    }
}
```

In this example:
- System sets syncthing defaults for all users
- Alice overrides `listen_address` for her user (system setting ignored)
- Bob uses the system defaults unchanged

### Builtin Programs and Their Scopes

| Program | Scope | Location | Notes |
|---------|-------|----------|-------|
| **git** | `"user"` | Users only | Each user has own identity |
| **neovim** | `"user"` | Users only | Each user has own config |
| **syncthing** | `"both"` | System + Users | Global service or per-user sync |

### Validation Errors

If you try to use a program at the wrong scope level, KodOS will show a clear error:

```
✗ Validation Error
Program 'git' (scope: user) cannot be used at system level.
Fix: Move 'programs.git' to 'users.alice.programs.git'

Available system-level programs: syncthing
```

To check a program's scope, use:
```bash
kod registry info git
```

This will show the program's scope and schema.

---

## Configuration Location

Where to add the `programs` section in your `configuration.lua`:

```lua
return {
    repos = {...},
    devices = {...},
    boot = {...},
    hardware = {...},
    locale = {...},
    network = {...},
    
    users = {
        root = {
            password = "...",
            shell = "/bin/bash"
            -- programs section goes here for root user
        },
        
        alice = {
            name = "Alice",
            password = "...",
            shell = "/bin/bash",
            extra_groups = {...},
            
            -- ADD PROGRAMS HERE:
            programs = {
                git = {...},
                neovim = {...},
                syncthing = {...}
            }
        }
    },
    
    packages = {...},
    services = {...},
    desktop = {...}
}
```

---

## Complete Example

Here's a complete, working example configuration:

```lua
local disk = require("disk")
local repos = require("repos")

return {
    repos = {
        official = repos.arch_repo("http://mirror.cpsc.ucalgary.ca/mirror/archlinux.org"),
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git"),
    },

    devices = {
        disk0 = disk.disk_definition("/dev/vda", "30GB"),
    },

    boot = {
        kernel = {
            package = "linux-lts",
            modules = { "virtio_pci", "ahci", "virtio_blk" },
        },
        loader = {
            type = "systemd-boot",
            timeout = 10,
        },
    },

    locale = {
        locale = {
            default = "en_US.UTF-8 UTF-8",
        },
        keymap = "us",
        timezone = "UTC",
    },

    network = {
        hostname = "kodosvm",
        ipv6 = true,
    },

    users = {
        root = {
            password = "root",
            shell = "/bin/bash",
        },
        
        alice = {
            name = "Alice Developer",
            password = "alice",
            shell = "/bin/bash",
            extra_groups = { "audio", "input", "network", "users", "video", "wheel" },
            
            -- PROGRAMS SECTION - Configure applications for this user
            programs = {
                git = {
                    user_name = "Alice Developer",
                    email = "alice@example.com",
                    signing_key = "9A1B2C3D4E5F6A7B"
                },
                
                neovim = {
                    python_provider = true,
                    node_provider = true
                },
                
                syncthing = {
                    auto_start = true,
                    listen_address = "127.0.0.1:8384"
                }
            }
        }
    },

    packages = {
        "git",
        "htop",
        "tmux",
        "bash-completion"
    },

    services = {
        networkmanager = {
            enable = true,
            service_name = "NetworkManager",
        },
        openssh = {
            enable = true,
            service_name = "sshd",
        },
    }
}
```

---

## Validating Your Configuration

Before running a real installation, validate your config:

```bash
# Validate config (dry-run, doesn't modify system)
kod config validate path/to/configuration.lua

# This will:
# 1. Load your Lua configuration
# 2. Check all sections are valid
# 3. Validate programs section if present
# 4. Report any errors clearly
```

**Example validation output (success):**
```
✓ Configuration valid
✓ Programs section valid
  - git: Valid (user_name, email, signing_key)
  - neovim: Valid (python_provider, node_provider)
  - syncthing: Valid (auto_start, listen_address)
```

**Example validation output (error):**
```
✗ Configuration invalid

Error in programs.git:
  Missing required field 'email'
  
  Available programs: git, neovim, syncthing

Hint: Run 'kod registry info git' to see program schema
```

---

## No Changes Required: Backward Compatibility

If your existing `configuration.lua` files don't have a `programs` section:
- ✅ They still work exactly as before
- ✅ All existing configs remain valid
- ✅ Phase 1-2 functionality unchanged
- ✅ Programs section is completely optional

---

## Next Steps: Custom Programs

Once you have your system running, you can extend it with custom programs. See:
- `docs/extending.md` — How to write custom programs
- `docs/examples/custom_program.lua` — Full example (Redis program)

Custom programs go in: `~/.kod/plugins/programs/`

---

## CLI Commands for Exploring Programs

Before writing your config, explore available programs:

```bash
# List all available programs (builtin + user plugins)
kod registry list

# Show detailed info about a program
kod registry info git
kod registry info neovim
kod registry info syncthing

# View the JSON schema for a program
kod registry schema git

# Dry-run: Generate config without installing
kod registry generate git --user-name "Alice" --email "alice@example.com"
```

---

## Installation Workflow

Once your `configuration.lua` is ready:

```bash
# 1. Validate (dry-run, no changes)
kod config validate path/to/configuration.lua

# 2. Install (actually modifies system)
kod install path/to/configuration.lua /path/to/mount/point

# This will:
# - Create filesystems
# - Install packages (including ones from programs)
# - Configure all programs (git, neovim, syncthing, etc.)
# - Setup users and services
# - Configure bootloader
```

---

## Troubleshooting

### "Unknown program 'foo'"
The program doesn't exist. Check available programs:
```bash
kod registry list
```

### "Missing required field 'email' in program 'git'"
The git program requires email. Add it to your config:
```lua
programs = {
    git = {
        user_name = "Alice",
        email = "alice@example.com"  -- Add this
    }
}
```

### "Invalid email format"
Git requires a valid email. Examples that work:
- `alice@example.com`
- `alice.smith@company.org`
- `user+tag@domain.co.uk`

### Programs section ignored
Make sure it's in the right place in the users section:
```lua
users = {
    alice = {
        name = "Alice",
        password = "...",
        programs = {  -- ← RIGHT: Inside user definition
            git = {...}
        }
    }
}

-- NOT here:
programs = {      -- ← WRONG: At top level
    git = {...}
}
```

---

## What Gets Installed?

When you include a program in your config, here's what happens:

### Git Program
**Packages installed:** None (git config only)
**Files modified:**
- `~/.gitconfig` (user's git config file)

### Neovim Program  
**Packages installed:**
- `neovim`
- `python-pynvim` (if python_provider=true)
- `nodejs-neovim` (if node_provider=true)
- `ruby-neovim` (if ruby_provider=true)

### Syncthing Program
**Packages installed:**
- `syncthing`

**Services enabled:**
- `syncthing` (systemd service)

---

## Ready to Install?

Your configuration.lua can now include:

✅ **Locale & Network** (Phase 1-2)  
✅ **Users & Packages** (Phase 1-2)  
✅ **Services & Boot** (Phase 1-2)  
✅ **Programs** (Phase 3 - NEW!)  

Everything is integrated and ready for real installations!

---

## Questions or Issues?

- Check program schemas: `kod registry info <program_name>`
- Validate config first: `kod config validate path/to/configuration.lua`
- See extending guide for custom programs: `docs/extending.md`
