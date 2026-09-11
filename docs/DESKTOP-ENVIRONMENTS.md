# Desktop Environments & Multi-DE Configuration Guide

**Phase 5d enables multi-environment desktop setup with per-environment customization.**

This guide covers configuring multiple desktop environments simultaneously, display manager setup, and real-world examples.

---

## Overview: Desktop Configuration in Phase 5d

### Phase 5c vs Phase 5d

| Aspect | Phase 5c | Phase 5d |
|--------|----------|---------|
| Desktop Environments | Single only | Multiple (up to 5+) |
| Display Manager | Global | Global + per-environment override |
| Customization | Monolithic | Per-DE packages |
| Use Cases | Single-DE systems | Multi-DE testing, switching |

### Phase 5d Desktop Structure

```lua
desktop = {
  -- Global display manager
  display_manager = "gdm",
  
  -- Multiple environments, any can be enabled
  environments = {
    gnome = {
      enable = true,
      display_manager = "gdm",              -- Optional override
      extra_packages = { "gnome-tweaks" },
      exclude_packages = { "gnome-tour" },
    },
    
    plasma = {
      enable = false,
      display_manager = "sddm",
      extra_packages = { "kde-applications" },
    },
    
    -- ... more environments
  },
}
```

---

## Display Manager Setup

The display manager (DM) is the login screen you see before entering the desktop.

### Display Managers

| DM | Used By | Format |
|----|---------|--------|
| `gdm` | GNOME, Cinnamon | Modern, touch-friendly |
| `sddm` | KDE Plasma | Qt-based, themed |
| `lightdm` | Budgie, Xfce, MATE | Lightweight |
| `cosmic-greeter` | COSMIC | New Rust-based greeter |
| `tdm` | TDE | Trinity Desktop Environment |
| `xdm` | Minimal | X Display Manager (basic) |

### Global Display Manager

Set one display manager globally:

```lua
desktop = {
  display_manager = "gdm",  -- Used for all enabled environments
}
```

### Per-Environment Override

Override globally for specific environment:

```lua
desktop = {
  display_manager = "gdm",  -- Default for all
  
  environments = {
    gnome = {
      enable = true,
      -- Uses global gdm
    },
    
    plasma = {
      enable = true,
      display_manager = "sddm",  -- Override for KDE
    },
  },
}
```

At runtime, user can switch DMs:

```bash
# Show current display manager
echo $DISPLAY_MANAGER

# Switch display manager
sudo update-alternatives --config x-display-manager
```

---

## Desktop Environments

### GNOME

Modern, polished desktop environment with extensive customization.

```lua
gnome = {
  enable = true,
  display_manager = "gdm",
  
  extra_packages = {
    "gnome-tweaks",                              -- Settings tool
    "showtime",                                  -- System monitor
    "gnome-connections",                         -- Remote desktop
    "gnome-shell-extension-appindicator",        -- Legacy tray icons
    "aur:gnome-shell-extension-dash-to-dock",    -- Dock from AUR
    "aur:gnome-shell-extension-blur-my-shell",   -- Blur effects
    "aur:gnome-shell-extension-arc-menu-git",    -- Arc menu
    "aur:gnome-shell-extension-gsconnect",       -- Phone integration
    "gnome-shell-extension-weather-oclock",      -- Weather widget
    "flatpak:com.mattjakeman.ExtensionManager",  -- Extension manager
  },
  
  exclude_packages = {
    "gnome-tour",  -- Tour on first login
    "yelp",        -- Help viewer
  },
}
```

**Supported versions:** GNOME 45+

**Configuration:** dconf settings in user programs

**Extensions:** Installed via GNOME extensions

### KDE Plasma

Highly customizable desktop with widget ecosystem.

```lua
plasma = {
  enable = false,  -- Disabled in eszkoz
  display_manager = "sddm",
  
  extra_packages = {
    "kde-applications",      -- Full KDE apps suite
    "kvantum",               -- Application theme engine
    "aur:plasma6-theme-mcmojave-git",  -- macOS theme
  },
}
```

**Supported versions:** Plasma 5.27+, Plasma 6+

**Configuration:** System Settings application

**Customization:** Widgets, panels, themes

### COSMIC

New Rust-based desktop environment from System76.

```lua
cosmic = {
  enable = true,
  display_manager = "cosmic-greeter",
  
  -- COSMIC automatically configured
  -- Minimal extra setup needed
}
```

**Status:** Beta/stable on Pop!_OS

**Configuration:** Settings application

**Storage:** Configuration in `~/.local/share/cosmic`

### Budgie

Lightweight, clean desktop environment.

```lua
budgie = {
  enable = false,
  display_manager = "lightdm",
  
  extra_packages = {
    "lightdm-gtk-greeter",        -- GTK-based login screen
    "network-manager-applet",     -- Network indicator
  },
}
```

**Supported versions:** Budgie 10+

**Configuration:** Gnome Settings (uses Gnome components)

**Use case:** Lightweight alternative to GNOME

### Pantheon

Elementary OS desktop environment.

```lua
pantheon = {
  enable = false,
  display_manager = "gdm",
  
  -- Pantheon automatically configured
}
```

**Status:** Elementary OS's native DE

**Configuration:** System Settings

**Use case:** Minimal, focused desktop

### Xfce

Lightweight, traditional desktop environment.

```lua
xfce = {
  enable = false,
  display_manager = "lightdm",
  
  extra_packages = {
    "xfce4-whiskermenu-plugin",    -- Application menu
    "xfce4-panel-profiles",         -- Panel customization
  },
}
```

**Status:** Stable, mature

**Configuration:** Xfce Settings Manager

**Use case:** Very lightweight, traditional desktop

---

## Per-Environment Customization

### Extra Packages

Install additional packages for specific environment:

```lua
environments = {
  gnome = {
    enable = true,
    extra_packages = {
      "gnome-tweaks",
      "gnome-extensions-app",
    },
  },
  
  plasma = {
    enable = true,
    extra_packages = {
      "kde-applications",
      "plasma-pa",  -- Sound control
    },
  },
}
```

### Exclude Packages

Remove packages that come with DE by default:

```lua
environments = {
  gnome = {
    enable = true,
    exclude_packages = {
      "gnome-tour",     -- Remove tour
      "yelp",           -- Remove help viewer
      "epiphany",       -- Remove Web browser
    },
  },
}
```

### Repository Packages

Install from specific repositories:

```lua
extra_packages = {
  "llvm",                                  -- System repo
  "aur:yay-bin",                          -- AUR
  "flatpak:com.mattjakeman.ExtensionManager",  -- Flatpak
}
```

---

## Real-World Example: eszkoz

Eszkoz configures 5 desktop environments with only GNOME and COSMIC enabled:

```lua
local use_gnome = true
local use_plasma = false
local use_cosmic = true
local use_pantheon = false
local use_budgie = false
local use_xfce = false

desktop = {
  display_manager = "cosmic-greeter",
  
  environments = {
    gnome = {
      enable = use_gnome,
      exclude_packages = {
        "gnome-tour",
        "yelp",
      },
      extra_packages = {
        "gnome-tweaks",
        "showtime",
        "gnome-connections",
        "gnome-shell-extension-appindicator",
        "aur:gnome-shell-extension-dash-to-dock",
        "aur:gnome-shell-extension-blur-my-shell",
        "aur:gnome-shell-extension-arc-menu-git",
        "aur:gnome-shell-extension-gsconnect",
        "gnome-shell-extension-weather-oclock",
        "flatpak:com.mattjakeman.ExtensionManager",
      },
    },
    
    plasma = {
      enable = use_plasma,
      display_manager = "sddm",
      extra_packages = {
        "kde-applications",
        "kvantum",
        "aur:plasma6-theme-mcmojave-git",
      },
    },
    
    cosmic = {
      enable = use_cosmic,
      display_manager = "cosmic-greeter",
    },
    
    budgie = {
      enable = use_budgie,
      display_manager = "lightdm",
      extra_packages = {
        "lightdm-gtk-greeter",
        "network-manager-applet",
      },
    },
    
    pantheon = {
      enable = use_pantheon,
      display_manager = "gdm",
    },
  },
}
```

### Configuration Flags

Use local variables to control which DEs are enabled:

```lua
local use_gnome = true    -- Enable GNOME
local use_plasma = false  -- Disable KDE
local use_cosmic = true   -- Enable COSMIC
-- ... etc
```

Then reference in configs:

```lua
gnome = {
  enable = use_gnome,
  -- ...
}
```

### Switching at Boot

At login screen, select environment:

1. Enter username/password
2. Click session selector (usually at bottom)
3. Choose environment (GNOME, KDE, COSMIC, etc.)
4. Log in

---

## Desktop Environment Packages

### Base Packages Per DE

| DE | Core Package | Size |
|----|--------------|------|
| GNOME | `gnome` | ~1.5GB |
| Plasma | `plasma-meta` + `kde-applications` | ~2.5GB |
| COSMIC | `cosmic-desktop` | ~800MB |
| Budgie | `budgie-desktop` | ~600MB |
| Pantheon | `elementary-desktop` | ~400MB |
| Xfce | `xfce4` | ~300MB |

### eszkoz Additions

**GNOME extras:**
- `gnome-tweaks` — Advanced settings
- Extensions from AUR and Flathub
- `showtime` — System monitor
- `gnome-connections` — RDP client

**Plasma extras:**
- `kde-applications` — Complete suite
- `kvantum` — Theme engine
- macOS-themed plasma

### Total Desktop Size

Installing all 5 DEs for testing:

```
GNOME:    1.5 GB
Plasma:   2.5 GB
COSMIC:   0.8 GB
Budgie:   0.6 GB
Pantheon: 0.4 GB
───────────────
Total:    ~5.8 GB
```

---

## Display Manager Setup & Switching

### View Installed Display Managers

```bash
# Arch/Pacman
pacman -Q | grep -E "gdm|sddm|lightdm|cosmic-greeter"

# Debian/apt
dpkg -l | grep -E "gdm|sddm|lightdm"
```

### Set Default Display Manager

```bash
# Arch (systemd-boot)
sudo systemctl set-default graphical.target
sudo systemctl enable gdm  # or sddm, lightdm, etc.

# Debian (alternatives)
sudo update-alternatives --install /usr/bin/x-session-manager \
  x-session-manager /usr/bin/gnome-session 100
sudo update-alternatives --config x-display-manager
```

### Switch Display Manager at Runtime

```bash
# Restart display server (will lose session)
sudo systemctl restart display-manager

# Or restart entire GUI
sudo systemctl restart graphical.target
```

---

## Dconf Configuration (GNOME)

### Per-User GNOME Settings

User programs can configure dconf:

```lua
users = {
  abuss = {
    programs = {
      dconf = {
        enable = true,
        config = configs.dconf(require("gnome")),
      },
    },
  },
}
```

### Dconf Settings File Example

```lua
-- gnome.lua module
return {
  ["org/gnome/desktop/interface"] = {
    gtk_theme = "Adwaita",
    icon_theme = "Adwaita",
    cursor_theme = "Adwaita",
  },
  
  ["org/gnome/shell"] = {
    favorite_apps = {
      "org.gnome.Nautilus.desktop",
      "org.gnome.Settings.desktop",
      "firefox.desktop",
    },
  },
}
```

---

## Common Desktop Configuration Tasks

### Task 1: Enable Only GNOME

```lua
desktop = {
  display_manager = "gdm",
  
  environments = {
    gnome = { enable = true },
    plasma = { enable = false },
    cosmic = { enable = false },
    budgie = { enable = false },
    pantheon = { enable = false },
  },
}
```

### Task 2: Test Multiple DEs

```lua
-- Enable all for testing
local testing = true

desktop = {
  display_manager = "gdm",
  
  environments = {
    gnome = { enable = testing },
    plasma = { enable = testing },
    cosmic = { enable = testing },
    budgie = { enable = testing },
    pantheon = { enable = testing },
  },
}
```

**Warning:** Will install ~5.8GB of packages!

### Task 3: Minimal Desktop

```lua
desktop = {
  display_manager = "lightdm",
  
  environments = {
    xfce = { enable = true },  -- Lightweight
  },
}
```

### Task 4: High-End Customization (GNOME + Plasma)

```lua
desktop = {
  display_manager = "gdm",  -- Default for GNOME
  
  environments = {
    gnome = {
      enable = true,
      extra_packages = {
        "gnome-tweaks",
        "gnome-shell-extension-appindicator",
        "aur:gnome-shell-extension-dash-to-dock",
        "aur:gnome-shell-extension-blur-my-shell",
      },
    },
    
    plasma = {
      enable = true,
      display_manager = "sddm",
      extra_packages = {
        "kde-applications",
        "kvantum",
        "aur:plasma6-theme-mcmojave-git",
      },
    },
  },
}
```

---

## Troubleshooting

### Issue: Desktop Won't Start After Config

**Symptom:** Login loop or can't reach desktop

**Cause:** Missing critical packages or bad display manager config

**Solution:**
```bash
# Boot into TTY (Ctrl+Alt+F2)
sudo systemctl restart display-manager

# Check display manager status
sudo systemctl status sddm  # or gdm, lightdm
```

### Issue: Wrong Display Manager Running

**Symptom:** Config specifies GDM but SDDM starts

**Cause:** Display manager not restarted after config change

**Solution:**
```bash
# Check active display manager
sudo systemctl list-units --type=service | grep manager

# Enable correct one
sudo systemctl enable gdm
sudo systemctl disable sddm
sudo systemctl restart gdm
```

### Issue: Environment Selector Not Showing

**Symptom:** Can't select DE at login screen

**Cause:** Session files not installed

**Solution:**
```bash
# Verify session files exist
ls /usr/share/xsessions/  # Desktop sessions
ls /usr/share/wayland-sessions/  # Wayland sessions

# If missing, reinstall DE
sudo pacman -S gnome plasma-desktop cosmic-desktop
```

### Issue: Display Manager Doesn't Start

**Symptom:** Stuck at kernel/boot messages

**Cause:** Display manager service not enabled or failed

**Solution:**
```bash
# Boot into TTY
sudo systemctl status display-manager
sudo systemctl start display-manager

# Enable on boot
sudo systemctl enable display-manager
```

---

## Performance Considerations

### Installation Time

Rough estimates for installation:

| DE | Time |
|----|------|
| GNOME alone | 3-5 min |
| KDE alone | 5-8 min |
| All 5 DEs | 20-30 min |

### Disk Space

| DE | Base | With Extras |
|----|------|-------------|
| GNOME | 1.5 GB | 2.0 GB |
| Plasma | 2.5 GB | 3.0 GB |
| COSMIC | 0.8 GB | 0.9 GB |
| Budgie | 0.6 GB | 0.7 GB |
| Pantheon | 0.4 GB | 0.5 GB |
| **All 5** | **~5.8 GB** | **~7.1 GB** |

### Memory Usage

Typical memory after login:

| DE | RAM |
|----|-----|
| GNOME | 800 MB |
| Plasma | 600 MB |
| COSMIC | 400 MB |
| Budgie | 350 MB |
| Pantheon | 300 MB |

---

## De-Duplication: Shared Components

Many DEs share common libraries:

- GTK libraries (GNOME, Budgie, Xfce)
- D-Bus (all DEs)
- Systemd (system-wide)
- OpenGL/Wayland (all modern DEs)

**Result:** Installing all 5 DEs uses less disk than 5 × individual size due to shared dependencies.

---

## Migration from Phase 5c

### Before (Phase 5c)

```lua
desktop = {
  desktop_manager = "gnome",
  display_manager = "gdm",
}
```

### After (Phase 5d)

```lua
desktop = {
  display_manager = "gdm",
  
  environments = {
    gnome = { enable = true },
  },
}
```

**Backward Compatibility:** Phase 5c configs still work but use single-DE structure.

---

## Advanced: Custom Display Manager Configuration

### SDDM Theme (Plasma)

```lua
plasma = {
  enable = true,
  display_manager = "sddm",
  
  extra_packages = {
    "sddm-sugar-dark",  -- Custom SDDM theme
  },
}
```

### Lightdm GTK Greeter Theme

```lua
budgie = {
  enable = true,
  display_manager = "lightdm",
  
  extra_packages = {
    "lightdm-gtk-greeter-settings",  -- Theme customizer
  },
}
```

---

## Links & References

- [PHASE-5D-STRUCTURED-DESIGN.md](./PHASE-5D-STRUCTURED-DESIGN.md) — Full schema overview
- [ADVANCED-USER-CONFIG.md](./ADVANCED-USER-CONFIG.md) — User-level dconf configuration
- [eszkoz Configuration](../tests/fixtures/eszkoz-config-5d.lua) — Real-world example
- [Arch Wiki: Desktop Environments](https://wiki.archlinux.org/title/Desktop_environment)
- [Arch Wiki: Display Manager](https://wiki.archlinux.org/title/Display_manager)

---

## Summary

Phase 5d desktop configuration:

✅ Support for 5+ desktop environments  
✅ Per-environment package customization  
✅ Global and per-environment display managers  
✅ Easy DE switching at login  
✅ Complete backward compatibility  

Multi-environment testing and switching now easy!
