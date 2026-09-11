# Phase 5d: Structured Schema Design

> **Design Status:** Approved for implementation planning

**Goal:** Extend Phase 5c schema with nested feature blocks for users, restructured desktop config, and namespaced service customization — maintaining backward compatibility while enabling real-world production systems like eszkoz.

**Architecture:** Phase 5d uses nested feature blocks to group related concerns:
- Users: identity, ssh_keys, dotfiles blocks under each user (plus programs/services)
- Desktop: flat display_manager + environments dict (replaces desktop_manager)
- Services: all customization under config block per service
- All new fields optional, Phase 5c configs unaffected

**Tech Stack:** Lua (schema, section modules), Python 3.12+ (validator), lupa (Lua interpreter), pytest (testing)

**Spec:** Approved by user; structured design with examples

---

## 1. Users Section — Nested Feature Blocks

### Current (Phase 5c)
```lua
users = {
  abuss = {
    shell = "/bin/bash",
  },
}
```

### Phase 5d Proposed Structure
```lua
users = {
  abuss = {
    shell = "/bin/bash",  -- REQUIRED (Phase 5c field, kept)
    
    -- NEW: Identity block (user basics)
    identity = {
      name = "Antal Buss",           -- Display name
      hashed_password = "$6$...",    -- Password hash
      groups = {"wheel", "audio"},   -- Supplementary groups
    },
    
    -- NEW: SSH keys block
    ssh_keys = {
      enabled = true,
      authorized = {
        "ssh-rsa AAAAB3...",
        "ssh-ed25519 AAAAC3...",
      },
    },
    
    -- NEW: Dotfiles block
    dotfiles = {
      enabled = true,
      repo_url = "https://github.com/user/dotfiles.git",
      source_dir = "~/.dotfiles",
      deploy_tool = "stow",  -- or "symlink"
    },
    
    -- NEW: User-level programs (nested)
    programs = {
      git = {
        enable = true,
        config = configs.git({...}),
      },
      neovim = {
        enable = true,
        package = "neovim",
        deploy_config = true,
      },
    },
    
    -- NEW: User-level services (nested)
    services = {
      syncthing = {
        enable = true,
        config = configs.syncthing({...}),
      },
    },
    
    -- NEW: Home config block
    home_config = {
      dotfiles_repos = {
        "home",        -- Deploy ~/.dotfiles/home/* to ~/
        "ghostty",     -- Deploy ~/.dotfiles/ghostty/* to ~/.config/ghostty/
      },
    },
  },
}
```

### Schema Definition (Lua)

```lua
users = {
  type = "dict",
  description = "System users and their configuration",
  fields = {
    ["<username>"] = {
      type = "dict",
      description = "User configuration",
      fields = {
        shell = {
          type = "string",
          description = "User shell",
          required = false,
          default = "/bin/bash",
        },
        
        -- NEW BLOCKS
        identity = {
          type = "dict",
          description = "User identity (name, password, groups)",
          required = false,
          fields = {
            name = {
              type = "string",
              description = "Display name",
            },
            hashed_password = {
              type = "string",
              description = "Hashed password (sha512, bcrypt, etc)",
            },
            groups = {
              type = "list",
              item_type = "string",
              description = "Supplementary groups",
            },
          },
        },
        
        ssh_keys = {
          type = "dict",
          description = "SSH key management",
          required = false,
          fields = {
            enabled = {
              type = "boolean",
              description = "Enable SSH key setup",
              default = false,
            },
            authorized = {
              type = "list",
              item_type = "string",
              description = "SSH public keys",
            },
          },
        },
        
        dotfiles = {
          type = "dict",
          description = "Dotfile management",
          required = false,
          fields = {
            enabled = {
              type = "boolean",
              description = "Enable dotfile deployment",
              default = false,
            },
            repo_url = {
              type = "string",
              description = "Git repository URL",
            },
            source_dir = {
              type = "string",
              description = "Source directory (default ~/.dotfiles)",
              default = "~/.dotfiles",
            },
            deploy_tool = {
              type = "string",
              description = "Deployment tool",
              enum = {"stow", "symlink", "cp"},
              default = "stow",
            },
          },
        },
        
        programs = {
          type = "dict",
          description = "User-level program configuration",
          required = false,
          fields = {
            ["<program_name>"] = {
              type = "dict",
              -- Same structure as top-level programs
            },
          },
        },
        
        services = {
          type = "dict",
          description = "User-level service configuration",
          required = false,
          fields = {
            ["<service_name>"] = {
              type = "dict",
              -- Same structure as top-level services
            },
          },
        },
        
        home_config = {
          type = "dict",
          description = "Home directory configuration",
          required = false,
          fields = {
            dotfiles_repos = {
              type = "list",
              item_type = "string",
              description = "Dotfiles subdirs to deploy",
            },
          },
        },
      },
    },
  },
}
```

### Benefits of This Structure

✅ **Clear semantics:** identity/ssh_keys/dotfiles are self-documenting blocks
✅ **Independent validation:** Each block is typed and validated separately
✅ **Easy extension:** Add new blocks (backup, vpn, etc.) without collisions
✅ **Matches eszkoz:** Real-world config already uses this pattern
✅ **Future-proof:** Phase 5e can add more blocks (e.g., security, monitoring)
✅ **Non-invasive:** All blocks optional, Phase 5c configs still work

---

## 2. Desktop Section — Renamed & Clarified

### Current (Phase 5c)
```lua
desktop = {
  environment = "cosmic",
  enable = true,
}
```

### Phase 5c Problem with Phase 5d Extensions
The eszkoz config tries to do:
```lua
desktop = {
  display_manager = "cosmic-greeter",
  desktop_manager = {  -- Confusing name
    gnome = { enable = true, ... },
    plasma = { enable = false, ... },
    cosmic = { enable = true, ... },
  },
}
```

Problem: `desktop_manager` is a confusing name. Is it for managing DEs? Unclear.

### Phase 5d Proposed Structure
```lua
desktop = {
  display_manager = "cosmic-greeter",  -- Display manager (gdm, sddm, lightdm, cosmic-greeter)
  
  environments = {  -- Renamed from desktop_manager for clarity
    gnome = {
      enabled = true,
      extra_packages = {"gnome-shell-extensions"},
      exclude_packages = {"gnome-contacts"},
    },
    plasma = {
      enabled = false,
      extra_packages = {},
    },
    cosmic = {
      enabled = true,
    },
    budgie = {
      enabled = false,
    },
  },
}
```

### Schema Definition (Lua)

```lua
desktop = {
  type = "dict",
  description = "Desktop environment configuration",
  fields = {
    display_manager = {
      type = "string",
      description = "Display manager (login screen)",
      enum = {"gdm", "sddm", "lightdm", "cosmic-greeter", "lxdm"},
      required = false,
    },
    
    environments = {
      type = "dict",
      description = "Desktop environments to install/configure",
      required = false,
      fields = {
        gnome = {
          type = "dict",
          fields = {
            enabled = { type = "boolean" },
            extra_packages = { type = "list", item_type = "string" },
            exclude_packages = { type = "list", item_type = "string" },
          },
        },
        plasma = {
          type = "dict",
          fields = {
            enabled = { type = "boolean" },
            extra_packages = { type = "list", item_type = "string" },
            exclude_packages = { type = "list", item_type = "string" },
          },
        },
        cosmic = {
          type = "dict",
          fields = {
            enabled = { type = "boolean" },
            extra_packages = { type = "list", item_type = "string" },
          },
        },
        budgie = {
          type = "dict",
          fields = {
            enabled = { type = "boolean" },
            extra_packages = { type = "list", item_type = "string" },
          },
        },
        pantheon = {
          type = "dict",
          fields = {
            enabled = { type = "boolean" },
            extra_packages = { type = "list", item_type = "string" },
          },
        },
      },
    },
  },
}
```

### Benefits

✅ **Clear intent:** display_manager is global, environments describe what to install
✅ **Extendable:** Add new DEs easily (pantheon, xfce, etc.)
✅ **Validation:** Each DE's config is independently typed
✅ **Future-proof:** Same structure for additional metadata later

---

## 3. Services Section — Config Block Namespacing

### Current (Phase 5c)
```lua
services = {
  openssh = {
    enable = true,
  },
  fwupd = {
    enable = true,
  },
}
```

### Phase 5c Problem with Phase 5d Extensions
The eszkoz config wants:
```lua
services = {
  openssh = {
    enable = true,
    service_name = "sshd",  -- Confusing: where does this go?
    settings = {            -- What's the schema here?
      PermitRootLogin = false,
      Port = 2222,
    },
    package = "openssh",     -- Different from service name?
    extra_packages = ["openssh-keyscan"],
  },
}
```

Problem: Multiple customization fields at same level, no structure. `settings` dict is untyped.

### Phase 5d Proposed Structure
```lua
services = {
  openssh = {
    enable = true,
    
    config = {               -- All customization under config block
      service_name = "sshd",      -- Override default service name
      packages = {
        main = "openssh",         -- Main package
        extra = {"openssh-keyscan"}, -- Extra packages
      },
      settings = {          -- Service-specific settings (typed per-service)
        PermitRootLogin = false,
        Port = 2222,
      },
    },
  },
  
  cups = {
    enable = true,
    config = {
      packages = {
        main = "cups",
        extra = {"gutenprint", "aur:brother-dcp-l2550dw"},
      },
    },
  },
  
  fwupd = {
    enable = true,
    -- No config needed (defaults work)
  },
  
  -- NEW: systemd special section
  systemd = {
    enable = true,
    config = {
      mounts = {
        home_backup = {
          what = "/dev/sdb1",
          where = "/mnt/backup",
          type = "ext4",
          options = "defaults",
        },
      },
      units = {
        my_service = {
          description = "Custom service",
          content = "[Unit]\nDescription=...\n",
        },
      },
    },
  },
}
```

### Schema Definition (Lua)

```lua
services = {
  type = "dict",
  description = "System services",
  fields = {
    ["<service_name>"] = {
      type = "dict",
      fields = {
        enable = {
          type = "boolean",
          description = "Enable service",
          required = true,
        },
        
        config = {
          type = "dict",
          description = "Service-specific configuration",
          required = false,
          fields = {
            service_name = {
              type = "string",
              description = "Override systemd service name",
            },
            packages = {
              type = "dict",
              fields = {
                main = {
                  type = "string",
                  description = "Main package name",
                },
                extra = {
                  type = "list",
                  item_type = "string",
                  description = "Extra packages",
                },
              },
            },
            settings = {
              type = "dict",
              -- Type varies per-service (validated by service module)
            },
          },
        },
      },
    },
    
    systemd = {
      type = "dict",
      description = "Systemd units and mounts",
      fields = {
        enable = { type = "boolean" },
        config = {
          type = "dict",
          fields = {
            mounts = {
              type = "dict",
              fields = {
                ["<mount_name>"] = {
                  type = "dict",
                  fields = {
                    what = { type = "string" },
                    where = { type = "string" },
                    type = { type = "string" },
                    options = { type = "string" },
                  },
                },
              },
            },
            units = {
              type = "dict",
              fields = {
                ["<unit_name>"] = {
                  type = "dict",
                  fields = {
                    description = { type = "string" },
                    content = { type = "string" },
                  },
                },
              },
            },
          },
        },
      },
    },
  },
}
```

### Benefits

✅ **Single namespace:** All customization under `config` block
✅ **Clear structure:** `packages.main`, `packages.extra`, `settings` clearly separated
✅ **Validated:** Each service type can define its own settings schema
✅ **Extensible:** New fields add under config, no collisions
✅ **Special handling:** systemd service gets special structure for units/mounts

---

## 4. Boot Section — Minor Addition

### Current (Phase 5c)
```lua
boot = {
  kernel = { ... },
  loader = { type = "systemd-boot", timeout = 10 },
}
```

### Phase 5d Addition
```lua
boot = {
  kernel = { ... },
  loader = {
    type = "systemd-boot",
    timeout = 10,
    include = {"memtest86+"},  -- Additional bootloader entries
  },
}
```

### Schema
```lua
loader = {
  type = "dict",
  fields = {
    type = { type = "string" },
    timeout = { type = "number" },
    include = {
      type = "list",
      item_type = "string",
      description = "Additional bootloader entries",
      required = false,
    },
  },
}
```

---

## 5. Hardware Section — SANE Addition

### Current (Phase 5c)
```lua
hardware = {
  pipewire = { enable = true, extra_packages = {...} },
}
```

### Phase 5d Addition
```lua
hardware = {
  pipewire = { enable = true, extra_packages = {...} },
  sane = {
    enable = true,
    extra_packages = {"sane-airscan", "xsane"},
  },
}
```

### Schema
```lua
sane = {
  type = "dict",
  description = "SANE scanner support",
  required = false,
  fields = {
    enable = { type = "boolean" },
    extra_packages = { type = "list", item_type = "string" },
  },
}
```

---

## 6. Fonts Section — Dual Support

### Current (Phase 5c)
```lua
fonts = {
  monospace = {"ttf-firacode-nerd"},
  sans_serif = {"ttf-fira-sans"},
  emoji = {"noto-fonts-emoji"},
  enable = true,
}
```

### Phase 5d Addition (Alternative Structure)
```lua
fonts = {
  -- Phase 5c structure (still supported)
  monospace = {"ttf-firacode-nerd"},
  sans_serif = {"ttf-fira-sans"},
  emoji = {"noto-fonts-emoji"},
  
  -- Phase 5d addition
  enable = true,
  font_dir = true,  -- Create ~/.local/share/fonts
  packages = {"ttf-nerd-fonts-symbols"},  -- Install by package name
}
```

### Schema
```lua
fonts = {
  type = "dict",
  fields = {
    monospace = { type = "list", item_type = "string" },
    sans_serif = { type = "list", item_type = "string" },
    emoji = { type = "list", item_type = "string" },
    enable = { type = "boolean" },
    
    -- NEW
    font_dir = {
      type = "boolean",
      description = "Create ~/.local/share/fonts directory",
      required = false,
    },
    packages = {
      type = "list",
      item_type = "string",
      description = "Font packages to install",
      required = false,
    },
  },
}
```

---

## Implementation Impact

### New Lua Modules (3)
- `src/kod/sections/users-advanced.lua` — Handle identity/ssh_keys/dotfiles blocks
- `src/kod/sections/dotfiles.lua` — Dotfile deployment logic
- `src/kod/sections/ssh-keys.lua` — SSH key setup logic

### Modified Lua Files
- `src/kod/lib/schema.lua` — Add all new field definitions
- `src/kod/sections/boot.lua` — Support loader.include
- `src/kod/sections/hardware.lua` — Add SANE support
- `src/kod/sections/desktop.lua` — Rename desktop_manager → environments
- `src/kod/sections/fonts.lua` — Add font_dir + packages
- `src/kod/sections/services.lua` — Add config block structure
- `src/kod/lib/planner.lua` — Merge user programs/services into global

### Python Integration
- `src/kod/config/validator.py` — Validate nested blocks, config structures
- `src/kod/planner.py` — Handle planner with nested user programs/services
- `src/kod/bootstrap.py` — Support all new features end-to-end

### Testing
- `tests/test_phase5d_schema.py` — Comprehensive schema validation
- `tests/test_phase5d_sections.lua` — Lua section tests
- `tests/test_phase5d_integration.py` — End-to-end with eszkoz config

---

## Backward Compatibility

✅ All new fields optional
✅ All new blocks optional
✅ Phase 5c configs work unchanged (no breaking changes)
✅ Phase 5c tests remain passing (541+)
✅ Graceful fallback when fields absent

---

## Success Criteria

✅ eszkoz config fully validates with new structure
✅ All ~400 eszkoz steps generate correctly
✅ Schema coherent and extendable (Phase 5e ready)
✅ 100+ new Phase 5d tests pass
✅ 541+ Phase 5c tests pass (no regressions)
✅ Code follows Phase 5c patterns (Lua + Python style)

---

**Design Approval:** Ready for implementation planning

Should I proceed with the writing-plans skill to create the detailed task-by-task implementation plan?
