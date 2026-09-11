# Configuration Review: example/eszkoz/configuration.lua

**Status:** ❌ **NOT CONFORMANT** with Phase 5c schema

**Issues Found:** 25+ schema violations

---

## Summary

The `eszkoz` configuration is **not conformant** with the Phase 5c schema defined in `src/kod/lib/schema.lua`. It contains many extra fields not defined in the schema, and uses nested structures that don't match the schema specification.

**Root Cause:** This configuration was created before Phase 5c schema was finalized. It represents a richer configuration model with more features than the current Phase 5c schema supports.

---

## Issues by Section

### 1. **BOOT Section**

**Extra Fields:**
- Line 44: `loader.include` — **NOT in schema** (intended for additional boot entries?)

**Fix:** Remove lines 44-45

```lua
-- BEFORE (lines 40-45)
loader = {
    type = "systemd-boot",
    timeout = 10,
    include = { "memtest86+" },  -- ❌ NOT IN SCHEMA
},

-- AFTER
loader = {
    type = "systemd-boot",
    timeout = 10,
},
```

---

### 2. **HARDWARE Section**

**Extra Fields:**
- Lines 51-54: `sane` — **NOT in schema** (SANE scanner support)

**Fix:** Remove entire `sane` block

```lua
-- BEFORE (lines 51-54)
sane = {
    enable = true,
    extra_packages = { "sane-airscan" },
},

-- AFTER (remove entirely)
-- Move to programs section if needed in future
```

**Note:** The schema only supports `hardware.pipewire`. SANE support could be added as a custom program in the future.

---

### 3. **USERS Section**

**Multiple Schema Violations:**

#### 3.1 User-Level Extra Fields
Lines 96-98 (root user):
- `no_password` — **NOT in schema**

```lua
-- BEFORE
root = {
    no_password = true,  -- ❌ NOT IN SCHEMA
    shell = "/bin/bash",
},

-- AFTER
root = {
    shell = "/bin/bash",
},
```

Lines 100-211 (abuss user):
- `name` (line 101) — **NOT in schema**
- `hashed_password` (line 103) — **NOT in schema**
- `extra_groups` (line 105) — **NOT in schema** (should be `groups`)
- `openssh_authorized` (lines 106-110) — **NOT in schema**
- `dotfile_manager` (lines 112-116) — **NOT in schema**
- `deploy_configs` (lines 178-182) — **NOT in schema**
- `home` (lines 195-210) — **NOT in schema**

#### 3.2 Nested Programs Under Users
Lines 118-176:
- `programs` nested under user — **STRUCTURE NOT IN SCHEMA**

The schema doesn't support `users.USERNAME.programs`. This is a user-level program configuration that differs from the top-level `programs` section.

```lua
-- BEFORE (lines 118-176)
programs = {
    git = { enable = true, config = ... },
    starship = { enable = true },
    fish = { enable = true },
    -- ... many more
},

-- AFTER (move to top-level 'programs' section, or remove for now)
-- These should be top-level programs, not nested under user
```

#### 3.3 Nested Services Under Users
Lines 184-193:
- `services` nested under user — **STRUCTURE NOT IN SCHEMA**

Schema doesn't support per-user service configuration.

```lua
-- BEFORE (lines 184-193)
services = {
    syncthing = {
        enable = false,
        config = configs.syncthing({...}),
    },
},

-- AFTER (remove from user, move to top-level 'services' if needed)
```

---

### 4. **DESKTOP Section**

**Extra Fields:**
- Line 218: `display_manager` — **NOT in schema** (top-level field)
- Lines 219-274: `desktop_manager` — **STRUCTURE NOT IN schema**

The schema specifies `desktop.environment` (string), not `desktop.desktop_manager` (dict with per-DE config).

```lua
-- BEFORE (lines 214-275)
desktop = {
    display_manager = "cosmic-greeter",  -- ❌ NOT IN SCHEMA
    desktop_manager = {  -- ❌ WRONG STRUCTURE
        gnome = { enable = true, exclude_packages = {...}, extra_packages = {...} },
        plasma = { enable = false, ... },
        cosmic = { enable = true, ... },
        budgie = { enable = false, ... },
        pantheon = { enable = false, ... },
    },
},

-- AFTER (simplified per schema)
desktop = {
    environment = "cosmic",  -- Just specify which DE
    enable = true,
},
```

**Impact:** This represents a significant difference in how DEs are configured. Current schema is simpler.

---

### 5. **FONTS Section**

**Wrong Structure:**
- Line 278: `font_dir` — **NOT in schema**
- Line 279: `packages` — **NOT in schema** (should be at top-level, not nested)

The schema specifies `fonts.monospace`, `fonts.sans_serif`, `fonts.emoji` (arrays), not `fonts.packages`.

```lua
-- BEFORE (lines 277-295)
fonts = {
    font_dir = true,  -- ❌ NOT IN SCHEMA
    packages = {  -- ❌ WRONG STRUCTURE
        "ttf-firacode-nerd",
        "ttf-nerd-fonts-symbols",
        -- ... many more
    },
},

-- AFTER (per schema)
fonts = {
    monospace = { "ttf-firacode-nerd", "ttf-sourcecodepro-nerd" },
    sans_serif = { "ttf-fira-sans", "ttf-liberation" },
    emoji = { "noto-fonts-emoji" },
    enable = true,
},
```

---

### 6. **SERVICES Section**

**Extra Fields in Various Services:**

#### 6.1 `services.networkmanager`
Line 357: `service_name` — **NOT in schema** (should be inferred from service name)

```lua
-- BEFORE
networkmanager = {
    enable = true,
    service_name = "NetworkManager",  -- ❌ NOT IN SCHEMA
},

-- AFTER
networkmanager = {
    enable = true,
},
```

#### 6.2 `services.openssh`
Line 368: `settings` — **NOT in schema**

```lua
-- BEFORE
openssh = {
    enable = true,
    service_name = "sshd",
    settings = {  -- ❌ NOT IN SCHEMA
        PermitRootLogin = false,
    },
},

-- AFTER
openssh = {
    enable = true,
},
```

#### 6.3 `services.cups`
Line 385: `extra_packages` — **NOT in schema**

```lua
-- BEFORE
cups = {
    enable = true,
    extra_packages = { "gutenprint", "aur:brother-dcp-l2550dw" },  -- ❌
},

-- AFTER
cups = {
    enable = true,
},
```

#### 6.4 `services.bluetooth`
Line 392: `package` — **NOT in schema**
Line 393: `settings` — **NOT in schema**

```lua
-- BEFORE
bluetooth = {
    enable = true,
    service_name = "bluetooth",
    package = "bluez",  -- ❌ NOT IN SCHEMA
    settings = {...},   -- ❌ NOT IN SCHEMA
},

-- AFTER
bluetooth = {
    enable = true,
},
```

#### 6.5 `services.systemd`
Lines 400-428: Entire `systemd` service — **NOT in schema**

```lua
-- BEFORE
systemd = {
    enable = false,
    mount = configs.mount({...}),  -- ❌ CUSTOM STRUCTURE
},

-- AFTER (remove)
-- systemd mount configuration not in Phase 5c schema
-- Could be added as a custom program in the future
```

---

## Summary of Violations

| Section | Issue | Lines | Fix |
|---------|-------|-------|-----|
| boot | Extra field: `loader.include` | 44-45 | Remove |
| hardware | Extra section: `sane` | 51-54 | Remove |
| users (root) | Extra field: `no_password` | 96 | Remove |
| users (abuss) | Extra fields: `name`, `hashed_password`, `extra_groups`, `openssh_authorized`, etc. | 101-110 | Remove all extra fields |
| users (abuss) | Nested `programs` (wrong structure) | 118-176 | Move to top-level or remove |
| users (abuss) | Nested `services` (wrong structure) | 184-193 | Move to top-level or remove |
| users (abuss) | Extra fields: `dotfile_manager`, `deploy_configs`, `home` | 112-210 | Remove |
| desktop | Extra field: `display_manager` | 218 | Remove |
| desktop | Wrong structure: `desktop_manager` dict | 219-274 | Replace with `environment` string |
| fonts | Extra field: `font_dir` | 278 | Remove |
| fonts | Wrong structure: `packages` dict | 279-294 | Replace with `monospace`, `sans_serif`, `emoji` |
| services | Extra fields in multiple services | 357-427 | Remove (`service_name`, `settings`, `package`, `extra_packages`) |
| services | Extra service: `systemd` with mount config | 400-428 | Remove |

**Total Violations: 25+**

---

## Recommended Actions

### Option 1: Minimal Conformance (Strip to Schema)

Remove all extra fields and restructure to match Phase 5c schema exactly.

**Advantages:**
- Validates against current schema
- Simpler configuration
- Ready for Phase 5c

**Disadvantages:**
- Loses many features (SANE, SSH keys, dotfiles, per-user programs, advanced DE config)
- Simplified functionality

**Effort:** 30 minutes

### Option 2: Extend Schema (Recommended)

Keep the eszkoz configuration as-is and extend Phase 5c schema to support:
- `hardware.sane` (scanner support)
- `users.USERNAME.{name, hashed_password, extra_groups, openssh_authorized, dotfile_manager, ...}`
- `users.USERNAME.programs` (nested user programs)
- `users.USERNAME.services` (nested user services)
- `desktop.display_manager`, `desktop.desktop_manager` (richer DE config)
- `fonts.{packages, font_dir}` (alternative font structure)
- `services.*.{service_name, settings, package, extra_packages}` (service customization)
- `services.systemd` (systemd mount/unit config)

**Advantages:**
- Keeps all eszkoz features
- More powerful configuration model
- Future-proof design

**Disadvantages:**
- Larger schema (more complexity)
- More validation rules needed
- More section modules to implement

**Effort:** 2-3 hours for full implementation

### Option 3: Hybrid Approach

Keep Phase 5c schema simple, allow eszkoz to use extended fields with warnings:
- Core schema for basic functionality
- Optional/advanced fields allowed but not validated
- Graceful degradation

**Effort:** 1-2 hours

---

## Proposed Fix (Option 1: Minimal Conformance)

Create `example/eszkoz/configuration-5c-compliant.lua`:

```lua
return {
    base_distribution = "arch",
    
    repos = {
        official = repos.arch_repo("https://mirror.rackspace.com/archlinux"),
        aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git"),
        flatpak = repos.flatpak_repo("flathub"),
    },
    
    devices = {
        disk0 = disk.disk_definition("/dev/nvme0n1", "34GB"),
    },
    
    boot = {
        kernel = {
            package = "linux",
            modules = { "xhci_pci", "ohci_pci", "ehci_pci", "virtio_pci", "ahci", "usbhid", "sr_mod", "virtio_blk" },
        },
        loader = {
            type = "systemd-boot",
            timeout = 10,
        },
    },
    
    hardware = {
        pipewire = {
            enable = true,
            extra_packages = { "pipewire-alsa", "pipewire-pulse" },
        },
    },
    
    locale = {
        locale = {
            default = "en_CA.UTF-8 UTF-8",
            extra_generate = { "en_US.UTF-8 UTF-8", "en_GB.UTF-8 UTF-8" },
            extra_settings = {
                LC_ADDRESS = "en_CA.UTF-8",
                -- ... rest of LC_* settings ...
            },
        },
        keymap = "us",
        timezone = "America/Edmonton",
    },
    
    network = {
        hostname = "eszkoz",
        ipv6 = false,
    },
    
    users = {
        root = {
            shell = "/bin/bash",
        },
        abuss = {
            shell = "/usr/bin/zsh",
        },
    },
    
    desktop = {
        environment = "cosmic",
        enable = true,
    },
    
    fonts = {
        monospace = { "ttf-firacode-nerd", "ttf-sourcecodepro-nerd" },
        sans_serif = { "ttf-fira-sans", "ttf-liberation" },
        emoji = { "noto-fonts-emoji" },
        enable = true,
    },
    
    packages = {
        "iw", "stow", "mc", "less", "neovim", "htop",
        "git", "firefox", "openssh",
        -- ... rest of packages ...
    },
    
    services = {
        fwupd = { enable = true },
        tailscale = { enable = true },
        networkmanager = { enable = true },
        openssh = { enable = true },
        avahi = { enable = true },
        cups = { enable = true },
        bluetooth = { enable = true },
    },
}
```

**Size reduction:** 430 lines → ~200 lines (simplified)

---

## Recommendation

**Use Option 3 (Hybrid) or Option 2 (Extended Schema):**

The eszkoz configuration represents a real, rich system setup. Rather than stripping it down, consider:

1. **Phase 5c (Current):** Keep minimal schema as is (foundation)
2. **Phase 5d (Next):** Extend schema to support advanced features
3. **Keep eszkoz as reference:** Document what features are missing from Phase 5c, use eszkoz as input for Phase 5d design

This way:
- Phase 5c remains simple and stable
- eszkoz demonstrates future direction
- Clear path forward for feature expansion
- No loss of functionality

---

## Files to Create/Modify

### Option 1 (Minimal): Create conformant version
```
example/eszkoz/configuration-5c-compliant.lua  (NEW)
```

### Option 2 (Extended): Extend schema
```
docs/EXTENDED-SCHEMA-PROPOSAL.md  (document features needed)
src/kod/lib/schema-extended.lua   (extended schema)
tests/test_extended_schema.lua     (validation tests)
```

### Option 3 (Hybrid): Allow extra fields
```
src/kod/config/validator.py       (MODIFY: allow extra fields with warnings)
docs/VALIDATOR-MODES.md           (document strict vs permissive)
```

---

## Conclusion

**The eszkoz configuration is NOT conformant with Phase 5c schema, but this is intentional:**

- Phase 5c defines a minimal, stable baseline
- eszkoz extends this with advanced features
- This gap highlights what Phase 5d should support
- Use eszkoz as a specification for future extensions
