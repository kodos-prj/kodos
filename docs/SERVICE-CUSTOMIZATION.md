# Service Customization Guide

**Phase 5d introduces namespaced service configuration with config blocks, custom service names, and systemd mounts/units.**

This guide covers configuring services with per-service customization, systemd integration, and real-world examples.

---

## Overview: Service Configuration in Phase 5d

### New in Phase 5d

Phase 5d extends service configuration with:

```lua
services = {
  openssh = {
    enable = true,
    
    -- Phase 5d: Custom service name
    service_name = "sshd",
    
    -- Phase 5d: Service-specific config
    config = {
      config_file = "/etc/ssh/sshd_config",
    },
    
    -- Existing: Service settings
    settings = {
      PermitRootLogin = false,
      PasswordAuthentication = true,
    },
  },
}
```

### Service Block Structure

```lua
services = {
  [service_name] = {
    enable = boolean,                          -- Enable/disable service
    service_name = string | nil,               -- Phase 5d: Override service name
    package = string | nil,                    -- Package name if different
    extra_packages = { string, ... },          -- Additional packages
    config = { ... } | nil,                    -- Phase 5d: Service config
    settings = { [key] = value, ... },         -- Service settings
  },
}
```

---

## Basic Service Configuration

### Enable Service

```lua
services = {
  openssh = {
    enable = true,
  },
}
```

Starts `openssh` service on boot.

### Disable Service

```lua
services = {
  openssh = {
    enable = false,  -- Don't start on boot
  },
}
```

### Custom Service Name

Override the systemd service name:

```lua
services = {
  openssh = {
    enable = true,
    service_name = "sshd",  -- systemctl enable sshd
  },
}
```

Maps config key `openssh` to systemd unit `sshd.service`.

### Custom Package

Override package name if different from service name:

```lua
services = {
  bluetooth = {
    enable = true,
    package = "bluez",  -- Config key is bluetooth, package is bluez
  },
}
```

### Extra Packages

Install additional packages for service:

```lua
services = {
  cups = {
    enable = true,
    extra_packages = {
      "gutenprint",           -- Printer drivers
      "aur:brother-dcp-l2550dw",  -- Specific printer support
    },
  },
}
```

---

## Service Settings

Service-specific configuration options.

### SSH Settings

```lua
services = {
  openssh = {
    enable = true,
    service_name = "sshd",
    
    settings = {
      PermitRootLogin = false,
      PasswordAuthentication = true,
      PubkeyAuthentication = true,
      X11Forwarding = false,
      MaxAuthTries = 3,
    },
  },
}
```

Generates `/etc/ssh/sshd_config` with settings.

### Network Manager Settings

```lua
services = {
  networkmanager = {
    enable = true,
    service_name = "NetworkManager",
    
    settings = {
      -- Network manager specific settings
      wifi = { enabled = true },
      ethernet = { enabled = true },
    },
  },
}
```

### Bluetooth Settings

```lua
services = {
  bluetooth = {
    enable = true,
    package = "bluez",
    
    settings = {
      AutoEnable = true,
      FastConnectable = true,
    },
  },
}
```

---

## Phase 5d: Service Config Block

New config block enables service-specific configuration.

### Config File Path

Specify where service configuration is written:

```lua
services = {
  openssh = {
    enable = true,
    
    config = {
      config_file = "/etc/ssh/sshd_config",
    },
    
    settings = {
      PermitRootLogin = false,
    },
  },
}
```

### Custom Config

Services can have custom config structure:

```lua
services = {
  custom_service = {
    enable = true,
    
    config = {
      config_file = "/etc/custom/config",
      extra_field = "value",
    },
  },
}
```

---

## Phase 5d: Systemd Mounts

Configure systemd mount units for network shares.

### CIFS Mount (SMB/Samba)

```lua
services = {
  systemd = {
    enable = true,
    
    mounts = {
      data = {
        type = "cifs",                    -- SMB/CIFS mount
        what = "//mmserver.lan/NAS1",     -- Server path
        where = "/mnt/data",              -- Local mount point
        description = "MMserver NAS1",    -- Display name
        
        options = "vers=2.1,credentials=/etc/samba/mmserver-cred,iocharset=utf8,rw,x-systemd.automount,uid=1000",
        
        after = "network.target",         -- Start after network
        wanted_by = "multi-user.target",  -- Wanted by multi-user
        
        automount = true,                 -- Automount on access
        automount_config = "TimeoutIdleSec=0",  -- Don't timeout
      },
    },
  },
}
```

### NFS Mount

```lua
services = {
  systemd = {
    enable = true,
    
    mounts = {
      library = {
        type = "nfs",                          -- NFS mount
        what = "homenas2.lan:/data/Documents", -- NFS path
        where = "/mnt/library/",               -- Local mount point
        description = "Document library",
        
        options = "noatime,x-systemd.automount,noauto",
        
        after = "network.target",
        wanted_by = "multi-user.target",
        
        automount = true,
        automount_config = "TimeoutIdleSec=600",  -- Unmount after 10 min idle
      },
    },
  },
}
```

### Mount Options

Common mount options by type:

**CIFS (SMB/Samba):**
- `vers=2.1` — Protocol version
- `credentials=/etc/samba/cred` — Credentials file
- `iocharset=utf8` — Character encoding
- `uid=1000` — User ID
- `x-systemd.automount` — Automount
- `rw` — Read-write

**NFS:**
- `noatime` — Don't update access time
- `noauto` — Don't auto-mount at boot
- `x-systemd.automount` — Automount on access
- `vers=4` — NFS version
- `soft` — Soft mount (timeout vs hard hang)

### Automount Configuration

Automount mounts on first access, unmounts after timeout:

```lua
-- Aggressive unmount (immediate)
automount_config = "TimeoutIdleSec=0"

-- 10 minute timeout
automount_config = "TimeoutIdleSec=600"

-- 1 hour timeout
automount_config = "TimeoutIdleSec=3600"
```

### Manual Mount (Non-Automount)

```lua
mounts = {
  archive = {
    type = "nfs",
    what = "server.lan:/archive",
    where = "/mnt/archive",
    description = "Archive",
    
    -- Manual mount: not automounted
    automount = false,
    
    after = "network.target",
    wanted_by = "multi-user.target",
  },
}
```

User mounts manually:

```bash
sudo mount /mnt/archive
sudo umount /mnt/archive
```

---

## Phase 5d: Systemd Units

Configure custom systemd units.

### Custom Service Unit

```lua
services = {
  systemd = {
    enable = true,
    
    units = {
      custom_service = {
        description = "Custom Service",
        after = "network.target",
        wanted_by = "multi-user.target",
      },
    },
  },
}
```

Generates `/etc/systemd/system/custom_service.service`.

### Timer Unit

```lua
units = {
  backup_timer = {
    description = "Daily Backup Timer",
    unit_type = "timer",  -- Creates .timer unit
    on_calendar = "daily",
  },
}
```

---

## Real-World Example: eszkoz

Eszkoz configures multiple services with Phase 5d features:

### Basic Services

```lua
services = {
  -- Firmware update
  fwupd = { enable = true },
  
  -- VPN
  tailscale = { enable = true },
  
  -- Network
  networkmanager = {
    enable = true,
    service_name = "NetworkManager",
  },
  
  -- SSH server
  openssh = {
    enable = true,
    service_name = "sshd",
    settings = {
      PermitRootLogin = false,
    },
  },
  
  -- Bluetooth
  bluetooth = {
    enable = true,
    service_name = "bluetooth",
    package = "bluez",
  },
  
  -- Printer
  cups = {
    enable = true,
    extra_packages = { "gutenprint", "aur:brother-dcp-l2550dw" },
  },
}
```

### Systemd Mounts

```lua
services = {
  systemd = {
    enable = true,
    
    mounts = {
      -- CIFS mount for NAS
      data = {
        type = "cifs",
        what = "//mmserver.lan/NAS1",
        where = "/mnt/data",
        description = "MMserverNAS1",
        options = "vers=2.1,credentials=/etc/samba/mmserver-cred,iocharset=utf8,rw,x-systemd.automount,uid=1000",
        after = "network.target",
        wanted_by = "multi-user.target",
        automount = true,
        automount_config = "TimeoutIdleSec=0",
      },
      
      -- NFS mount for documents
      library = {
        type = "nfs",
        what = "homenas2.lan:/data/Documents",
        where = "/mnt/library/",
        description = "Document library",
        options = "noatime,x-systemd.automount,noauto",
        after = "network.target",
        wanted_by = "multi-user.target",
        automount = true,
        automount_config = "TimeoutIdleSec=600",
      },
    },
  },
}
```

---

## Common Service Configuration Patterns

### Pattern 1: Minimal Enable

```lua
services = {
  openssh = { enable = true },
}
```

Defaults:
- Uses config key as service name (`openssh`)
- No extra packages
- No custom settings

### Pattern 2: Custom Service Name

```lua
services = {
  openssh = {
    enable = true,
    service_name = "sshd",  -- Actual systemd unit
  },
}
```

Enables unit: `sshd.service`

### Pattern 3: Custom Package

```lua
services = {
  bluetooth = {
    enable = true,
    package = "bluez",  -- Install bluez, enable bluetooth
  },
}
```

### Pattern 4: With Settings

```lua
services = {
  openssh = {
    enable = true,
    service_name = "sshd",
    settings = {
      PermitRootLogin = false,
      PasswordAuthentication = false,
      PubkeyAuthentication = true,
    },
  },
}
```

Generates config with settings.

### Pattern 5: With Extra Packages

```lua
services = {
  cups = {
    enable = true,
    extra_packages = {
      "gutenprint",
      "aur:brother-dcp-l2550dw",
    },
  },
}
```

Installs cups + extra printer drivers.

### Pattern 6: Disabled But Configured

```lua
services = {
  nix = {
    enable = false,         -- Don't enable
    service_name = "nix_daemon",  -- But could enable if set to true
  },
}
```

Useful for placeholder configs.

---

## Network Mount Security

### Credentials File (CIFS)

```bash
# Create credentials file
sudo mkdir -p /etc/samba
sudo tee /etc/samba/mmserver-cred > /dev/null <<EOF
username=user
password=secret
domain=DOMAIN
EOF

# Secure permissions
sudo chmod 600 /etc/samba/mmserver-cred
```

Config references it:

```lua
options = "vers=2.1,credentials=/etc/samba/mmserver-cred,iocharset=utf8,rw",
```

### NFS with Kerberos

For high-security NFS:

```lua
options = "sec=krb5,vers=4,hard,intr",
```

---

## Troubleshooting

### Issue: Mount Not Automounting

**Symptom:** systemd mount configured but doesn't automount on access

**Cause:** Missing `x-systemd.automount` or incorrect options

**Solution:**
```lua
options = "vers=2.1,x-systemd.automount,uid=1000",
automount = true,
automount_config = "TimeoutIdleSec=0",
```

**Manual test:**
```bash
ls -la /mnt/data  # Should trigger automount
```

### Issue: Mount Timeout

**Symptom:** Mount hangs on boot

**Cause:** Server unreachable or timeout too short

**Solution:**
1. Ensure server is online
2. Use `noauto` to prevent boot-time mount
3. Increase timeout: `TimeoutIdleSec=3600`

```lua
automount = false,  -- Don't automount
after = "network-online.target",  -- Wait for network
```

### Issue: Permission Denied on Mount

**Symptom:** Mount succeeds but can't access files

**Cause:** UID/GID mismatch or wrong credentials

**Solution:**
```lua
options = "vers=2.1,credentials=/etc/samba/cred,uid=1000,gid=1000,fmask=0755",
```

Verify credentials file:
```bash
cat /etc/samba/mmserver-cred
```

### Issue: Service Won't Enable

**Symptom:** `enable = true` but service not running

**Cause:** Service not installed or unit not found

**Solution:**
```bash
# Check if service exists
systemctl list-unit-files | grep openssh

# Verify package installed
pacman -Q openssh

# Manually enable
sudo systemctl enable sshd
sudo systemctl start sshd
```

### Issue: Credentials File Not Found

**Symptom:** Mount fails with "credentials file not found"

**Cause:** File path wrong or file not created yet

**Solution:**
```bash
# Create file
sudo touch /etc/samba/mmserver-cred

# Add credentials
echo "username=user" | sudo tee -a /etc/samba/mmserver-cred
echo "password=pass" | sudo tee -a /etc/samba/mmserver-cred

# Secure it
sudo chmod 600 /etc/samba/mmserver-cred
```

---

## Performance Considerations

### Mount Overhead

Mounting adds minimal overhead at boot:
- Local filesystem: < 1ms
- CIFS (direct): 5-10ms
- NFS (fast LAN): 2-5ms
- NFS (slow WAN): 100ms+

### Automount Timeout Impact

```
TimeoutIdleSec=0       -- Immediate unmount (frequent remounts)
TimeoutIdleSec=300     -- 5 min (balanced)
TimeoutIdleSec=3600    -- 1 hour (persistent)
```

Choose based on access patterns.

### Network Mount Best Practices

| Scenario | Config |
|----------|--------|
| Frequently accessed | `TimeoutIdleSec=3600` |
| Occasional access | `TimeoutIdleSec=600` |
| Rarely used | `automount=false` |
| Local-like speed | `hard,nointr` (NFS) |
| Slow WAN | `soft,timeo=100` (NFS) |

---

## Service Dependencies

Services can depend on other services:

```lua
-- Define network service first
services = {
  networkmanager = { enable = true },
}

-- Mounts depend on network
services = {
  systemd = {
    mounts = {
      data = {
        what = "//server/share",
        where = "/mnt/data",
        after = "network.target",  -- Network must be up first
      },
    },
  },
}
```

---

## Migration from Phase 5c

### Before (Phase 5c)

```lua
services = {
  openssh = {
    enable = true,
    settings = {
      PermitRootLogin = false,
    },
  },
}
```

### After (Phase 5d)

```lua
services = {
  openssh = {
    enable = true,
    service_name = "sshd",  -- Explicit service name
    
    config = {              -- New config block
      config_file = "/etc/ssh/sshd_config",
    },
    
    settings = {            -- Existing settings
      PermitRootLogin = false,
    },
  },
  
  systemd = {               -- New systemd support
    enable = true,
    
    mounts = {
      data = {
        type = "cifs",
        what = "//server/share",
        where = "/mnt/data",
      },
    },
  },
}
```

---

## Links & References

- [PHASE-5D-STRUCTURED-DESIGN.md](./PHASE-5D-STRUCTURED-DESIGN.md) — Full schema overview
- [eszkoz Configuration](../tests/fixtures/eszkoz-config-5d.lua) — Real-world service examples
- [Arch Wiki: Systemd](https://wiki.archlinux.org/title/Systemd)
- [Arch Wiki: Samba/CIFS](https://wiki.archlinux.org/title/Samba)
- [Arch Wiki: NFS](https://wiki.archlinux.org/title/NFS)

---

## Summary

Phase 5d service customization provides:

✅ Custom service names  
✅ Per-service configuration blocks  
✅ Systemd mount integration  
✅ Network share mounting (CIFS, NFS)  
✅ Custom systemd units  
✅ Automount configuration  

All features maintain backward compatibility with Phase 5c.
