# KodOS Programs-Only Architecture Migration Guide

This guide helps you migrate from the legacy service-only configuration model to the new **Programs-Only Architecture**, where programs can include services as part of their configuration.

## Overview: What Changed?

KodOS now unifies application and service configuration through the **programs** system. Instead of managing services separately in a `services` section, programs can declare and manage their own services internally.

### What's the Same?
- Existing configurations continue to work
- Backward compatibility is fully maintained
- No breaking changes to the configuration language
- All existing services still function identically

### What's New?
- Programs can now include optional `service` fields
- Single source of truth for program + service configuration
- Reduced duplication in config files
- Better validation of program-service relationships

### Timeline

| Phase | Status | Impact |
|-------|--------|--------|
| **Now** | Programs-Only ready | New projects should use programs-only model |
| **Future** | Gradual migration | Existing configs work unchanged, but migration recommended |
| **Eventually** | Services section deprecated | Legacy approach will be phased out (far future) |

**Bottom Line:** No urgent action needed. Migrate at your own pace, starting with new programs.

---

## What Changed in Configuration Structure?

### Before: Service-Only Model

```lua
-- Configuration with legacy services section
return {
    services = {
        openssh = {
            enable = true,
            service_name = "sshd",
            settings = {
                Port = 22,
                PermitRootLogin = false,
            }
        },
        
        cups = {
            enable = true,
            service_name = "cupsd",
        }
    }
}
```

**Issues with this approach:**
- Service and program configuration separated
- Duplication: service_name appears in services section
- If program has config, it's in separate places
- Hard to understand the complete picture of what's being configured

### After: Programs-Only Model

```lua
-- Configuration with programs section including services
return {
    programs = {
        openssh = {
            enable = true,
            service = {
                enable = true,
                service_name = "sshd"
            },
            settings = {
                Port = 22,
                PermitRootLogin = false,
            }
        },
        
        cups = {
            enable = true,
            service = {
                enable = true,
                service_name = "cupsd"
            }
        }
    }
}
```

**Benefits:**
- Single location for program and service config
- Clear: service is part of program
- No duplication
- Full picture in one place

### Change Summary Table

| Aspect | Before (Services) | After (Programs) | Notes |
|--------|-------------------|------------------|-------|
| **Location** | `services.openssh` | `programs.openssh.service` | More organized |
| **Enable flag** | `services.openssh.enable` | `programs.openssh.service.enable` | Explicit per section |
| **Service name** | `service_name` | `service.service_name` | Grouped with service config |
| **Program config** | Separate from service | Part of program | Unified |
| **Configuration scope** | Services only | Programs (can include services) | More flexible |

---

## Step-by-Step Migration Guide

### Step 1: Identify Services to Migrate

List all services currently in your configuration that should become programs.

**Candidates for migration:**
- `openssh` → `programs.openssh`
- `cups` → `programs.cups`
- `networkmanager` → `programs.networkmanager`
- `syncthing` → `programs.syncthing` (can be system or user level)

**Not candidates (no program equivalent yet):**
- Custom services without a program definition
- Services without configuration beyond enable/disable
- Keep these in the legacy `services` section for now

### Step 2: Review Program Definitions

Check if programs exist for your services:

```bash
# List available programs
kod registry list

# Check if openssh program exists
kod registry info openssh

# View complete schema
kod registry schema openssh
```

### Step 3: Update Configuration (Simple Case)

**Before:**
```lua
services = {
    openssh = {
        enable = true,
        service_name = "sshd",
        settings = {
            PermitRootLogin = false,
            PasswordAuthentication = false,
        }
    }
}
```

**After:**
```lua
programs = {
    openssh = {
        enable = true,
        service = {
            enable = true,
            service_name = "sshd"
        },
        settings = {
            PermitRootLogin = false,
            PasswordAuthentication = false,
        }
    }
}
```

**Changes:**
- Move from `services.openssh` → `programs.openssh`
- Wrap service info in `service` table
- Keep program config fields at top level

### Step 4: Update Configuration (With User Services)

**Syncthing example at user level:**

**Before:**
```lua
users = {
    alice = {
        services = {
            syncthing = {
                enable = true,
                service_name = "syncthing"  -- Problem: not user-specific
            }
        }
    }
}
```

**After:**
```lua
users = {
    alice = {
        programs = {
            syncthing = {
                enable = true,
                service = {
                    enable = true,
                    service_name = "syncthing@alice"  -- Now user-specific!
                },
                listen_address = "127.0.0.1:8384",
                auto_start = true
            }
        }
    }
}
```

**Improvements:**
- Service name now includes username (`syncthing@alice`)
- Configuration is user-specific
- All program settings in one place

### Step 5: Validate Configuration

```bash
# Validate your updated configuration
kod config validate path/to/configuration.lua

# Should show:
# ✓ Configuration valid
# ✓ Programs section valid
#   - openssh: Valid
#   - cups: Valid
#   - syncthing: Valid
```

### Step 6: Test Installation (Optional Dry-Run)

Before applying changes to your system:

```bash
# Dry-run: shows what would be installed
kod install --dry-run path/to/configuration.lua

# Review the output to ensure programs are recognized correctly
```

### Step 7: Apply Changes

If migrating an existing system:

```bash
# Rebuild with new configuration
kod rebuild -n -c path/to/configuration

# Creates new generation with migrated configuration
# Reboot to activate: systemctl reboot
```

---

## Real-World Migration Examples

### Example 1: Simple Service Migration

**Before - OpenSSH service only:**
```lua
return {
    services = {
        openssh = {
            enable = true,
            service_name = "sshd",
            settings = {
                Port = 2222,
                PermitRootLogin = false,
            }
        }
    }
}
```

**After - OpenSSH as program:**
```lua
return {
    programs = {
        openssh = {
            enable = true,
            service = {
                enable = true,
                service_name = "sshd"
            },
            settings = {
                Port = 2222,
                PermitRootLogin = false,
            }
        }
    }
}
```

### Example 2: Multi-Service Migration

**Before - Multiple services:**
```lua
return {
    services = {
        openssh = {
            enable = true,
            service_name = "sshd"
        },
        cups = {
            enable = true,
            service_name = "cupsd"
        },
        networkmanager = {
            enable = true,
            service_name = "NetworkManager"
        }
    }
}
```

**After - Migrate all to programs:**
```lua
return {
    programs = {
        openssh = {
            enable = true,
            service = {
                enable = true,
                service_name = "sshd"
            }
        },
        
        cups = {
            enable = true,
            service = {
                enable = true,
                service_name = "cupsd"
            }
        },
        
        networkmanager = {
            enable = true,
            service = {
                enable = true,
                service_name = "NetworkManager"
            }
        }
    }
}
```

### Example 3: Syncthing User-Level Migration

This is where the new model really shines:

**Before - Awkward at user level:**
```lua
users = {
    alice = {
        name = "Alice",
        services = {
            syncthing = {
                enable = true,
                service_name = "syncthing"  -- Not user-specific!
            }
        }
    }
}
```

**After - Clean user-level config:**
```lua
users = {
    alice = {
        name = "Alice",
        programs = {
            syncthing = {
                enable = true,
                service = {
                    enable = true,
                    service_name = "syncthing@alice"  -- Proper user service!
                },
                listen_address = "127.0.0.1:8384"
            }
        }
    }
}
```

**Why this is better:**
- Service name is properly user-scoped (`syncthing@alice`)
- User-level configuration makes sense for per-user sync
- Configuration and service management are unified

### Example 4: System-Level Service

**Before:**
```lua
return {
    services = {
        cups = {
            enable = true,
            service_name = "cupsd"
        }
    },
    
    packages = {
        "cups",
        "gutenprint"
    }
}
```

**After:**
```lua
return {
    programs = {
        cups = {
            enable = true,
            service = {
                enable = true,
                service_name = "cupsd"
            },
            extra_packages = {
                "gutenprint"
            }
        }
    }
}
```

**Improvements:**
- Packages moved into program config
- No need to list packages separately
- Single source of truth for CUPS

---

## Backward Compatibility

### Will Existing Configs Break?

**No.** Existing configurations continue to work:

```lua
-- This still works and will continue to work
return {
    services = {
        openssh = { enable = true }
    }
}
```

### Migration Timeline

| Timeline | Status | Action |
|----------|--------|--------|
| **Now** | Both supported | Use programs for new services |
| **6+ months** | Both supported | Migrate at your pace |
| **1+ year** | Gradual deprecation | Services section discouraged but functional |
| **2+ years** | Far future | Services section may be removed (not soon!) |

### Running Mixed Configurations

You can run both services and programs simultaneously during migration:

```lua
return {
    -- New: Programs with services
    programs = {
        openssh = {
            enable = true,
            service = { enable = true, service_name = "sshd" }
        }
    },
    
    -- Old: Legacy services (still works)
    services = {
        cups = {
            enable = true,
            service_name = "cupsd"
        }
    }
}
```

**Note:** Avoid configuring the same service in both sections. The last definition wins, which can be confusing.

---

## Migration Troubleshooting

### Issue: "Program 'openssh' not found"

**Cause:** Program doesn't exist yet.

**Solution:**
1. Check available programs: `kod registry list`
2. Keep using `services` section for now
3. Wait for program to be added
4. Report missing program to KodOS team

### Issue: "Validation Error: 'service_name' is required"

**Cause:** Program has a service field but you didn't provide service_name.

**Solution:**
```lua
-- ✗ Wrong: Missing service_name
programs = {
    openssh = {
        enable = true,
        service = { enable = true }  -- Missing service_name!
    }
}

-- ✓ Right: Provide service_name
programs = {
    openssh = {
        enable = true,
        service = {
            enable = true,
            service_name = "sshd"  -- Required!
        }
    }
}
```

### Issue: "Conflicting configurations"

**Cause:** Same service configured in both `services` and `programs` sections.

**Solution:** Choose one approach and remove from the other:

```lua
-- ✗ Wrong: openssh in both places
return {
    services = { openssh = { enable = true } },
    programs = { openssh = { enable = true, service = {...} } }
}

-- ✓ Right: Use only programs
return {
    programs = { openssh = { enable = true, service = {...} } }
}
```

### Issue: User-level services not starting

**Cause:** Service name not user-specific.

**Solution:**
```lua
-- ✗ Wrong: Generic service name
users = {
    alice = {
        programs = {
            syncthing = {
                service = { service_name = "syncthing" }  -- System-level!
            }
        }
    }
}

-- ✓ Right: User-specific service name
users = {
    alice = {
        programs = {
            syncthing = {
                service = { service_name = "syncthing@alice" }  -- User-level!
            }
        }
    }
}
```

---

## Frequently Asked Questions

### Q: Do I have to migrate right now?

**A:** No. Existing configurations continue to work unchanged. Migrate when it makes sense for your workflow.

### Q: Can I migrate gradually?

**A:** Yes. You can use both `services` and `programs` sections in the same config during migration. Recommend focusing on programs for new services.

### Q: What if my program needs both system and user config?

**A:** Use scope `"both"` in the program definition:

```lua
-- System-level
programs = {
    syncthing = {
        enable = true,
        service = { enable = true, service_name = "syncthing" }
    }
}

-- User-level overrides
users = {
    alice = {
        programs = {
            syncthing = {
                listen_address = "0.0.0.0:8384"
                -- Inherits system service config, can override
            }
        }
    }
}
```

### Q: How do I check a program's schema?

**A:**
```bash
kod registry info openssh      # Short info
kod registry schema openssh    # Full schema with defaults
```

### Q: What about services that don't have a program?

**A:** Keep using the `services` section for those. Programs are added progressively. Report missing programs at: https://github.com/kodos-prj/kodos/issues

### Q: Can I disable the service but keep the program enabled?

**A:** Yes:

```lua
programs = {
    openssh = {
        enable = true,           -- Program is configured
        service = {
            enable = false        -- But service is not started
        }
    }
}
```

This is useful for testing or when you want to manually manage the service.

### Q: Will migrating break my existing system?

**A:** No. Migration is safe because:
1. Programs and services both use `systemctl` under the hood
2. Service names remain the same
3. Configuration options don't change
4. A new system generation is created (old one stays for rollback)

### Q: How do I roll back if migration causes issues?

**A:** If you created a new generation during migration:

```bash
# Reboot and select previous generation from boot menu
# Or from command line:
systemctl reboot --boot-loader-menu

# After rollback, you can analyze issues before retrying
```

### Q: Should programs include package installation?

**A:** Yes. Programs should be self-contained. If a program needs packages, declare them:

```lua
programs = {
    cups = {
        enable = true,
        service = { enable = true, service_name = "cupsd" },
        extra_packages = { "gutenprint", "foomatic-db" }
    }
}
```

This way: enable program → install packages + configure service, all together.

### Q: What about system vs user level services?

**A:** Program scope handles this:

- **System-level** (scope="system"): Top-level `programs` section, affects all users
- **User-level** (scope="user"): Inside `users.<name>.programs`, per-user config
- **Both** (scope="both"): Can appear at either level, user config overrides system

See `docs/extending.md` for details on scope.

---

## Useful Commands

```bash
# List all available programs
kod registry list

# Check if a program exists
kod registry info openssh

# View program schema and defaults
kod registry schema openssh

# Validate your configuration before applying
kod config validate configuration.lua

# Dry-run: see what would be installed
kod install --dry-run configuration.lua

# Check systemd service status after installation
systemctl status sshd          # System-level
systemctl --user status syncthing@alice  # User-level
```

---

## Next Steps

1. **Review Your Current Config:** Identify services that could become programs
2. **Check Available Programs:** `kod registry list`
3. **Start with One Service:** Migrate the simplest service first
4. **Validate:** `kod config validate configuration.lua`
5. **Test:** `kod install --dry-run configuration.lua`
6. **Apply:** `kod rebuild -n -c configuration`
7. **Verify:** `systemctl status <service_name>`

---

## Resources

- [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) - Programs configuration guide
- [extending.md](extending.md) - Creating custom programs with services
- [examples/system_services_as_programs.lua](examples/system_services_as_programs.lua) - System services example
- [examples/service_inheritance.lua](examples/service_inheritance.lua) - User services example

---

## Questions or Issues?

- Report issues: https://github.com/kodos-prj/kodos/issues
- Check documentation: `docs/extending.md`
- Validate your config: `kod config validate configuration.lua`
