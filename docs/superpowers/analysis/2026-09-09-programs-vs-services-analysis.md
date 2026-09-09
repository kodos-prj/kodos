# Programs vs Services: Architectural Analysis

**Date:** 2026-09-09  
**Analysis:** Distinguishing between Programs and Services in Kodos configuration system

---

## Current State in Kodos

### Services (Current)
- **Location:** Top-level `services` section (system-level only)
- **Purpose:** Enable/configure systemd services
- **Examples:** openssh, networkmanager, syncthing, bluetooth, cups
- **Scope:** Always system-level
- **Capabilities:**
  - Enable/disable service
  - Install package (if specified)
  - Configure service settings
  - Define systemd mount points

### Programs (Phase 3 Enhancement)
- **Location:** Top-level `programs` (system-level) AND `users.alice.programs` (user-level)
- **Purpose:** Install and configure applications for users
- **Examples:** git, neovim, syncthing
- **Scope:** Can be "system", "user", or "both"
- **Capabilities:**
  - Install application
  - Configure per-user settings
  - Generate user-specific config files

---

## The Problem: Syncthing

Syncthing appears in **two places** in current configs:

```lua
-- TOP-LEVEL services (system-level service)
services = {
    syncthing = {
        enable = true,
        service_name = "syncthing",
        ...
    }
}

-- USER-LEVEL programs (user-specific config)
users = {
    alice = {
        programs = {
            syncthing = {
                auto_start = true,
                listen_address = "127.0.0.1:8384",
                ...
            }
        }
    }
}
```

**Question:** Why are they separate?

---

## NixOS Architecture (Reference)

In NixOS, there's a clear distinction:

### Programs (`environment.systemPackages` and per-user)
- Install packages for users
- Configure user dotfiles/settings
- Can be system-wide or per-user
- Example: `programs.neovim` (per-user editor config)

### Services (`services.<name>`)
- Define and enable systemd services
- System-level only (service runs globally)
- May automatically install required package
- May define user services
- Example: `services.syncthing.enable = true` (runs syncthing daemon)

### Relationship
- **Service can include program setup:** Service installation often includes the package
- **Programs can depend on services:** A program might require a service to be running
- **Separate concerns:** Services = runtime behavior, Programs = user configuration

---

## Current Kodos Design Flaw

The current separation creates **duplication and confusion**:

1. **Duplication:** Syncthing is configured in both `services` and `programs`
2. **Confusion:** Which section controls what?
3. **No coordination:** If service is disabled, does program still run?
4. **Scope mismatch:** Services are always system-level, but programs now support both

---

## Proposed Architecture: Unified Model

### Option 1: Services Only (Simplest)
**Concept:** Services section handles BOTH service enablement AND application-level configuration

```lua
services = {
    syncthing = {
        enable = true,          -- Enable systemd service
        scope = "system",       -- Service scope
        
        -- Application configuration (per-scope)
        config = {
            auto_start = true,
            listen_address = "0.0.0.0:8384"
        }
    },
    
    git = {
        enable = false,         -- Git is not a service, so enable = false
        scope = "user",         -- Git is per-user only
        
        -- User configuration goes here
        users = {
            alice = {
                user_name = "Alice",
                email = "alice@example.com"
            }
        }
    }
}
```

**Pros:**
- Single source of truth (services section)
- Clear scope field on all software
- Services and programs treated uniformly
- Simpler configuration structure

**Cons:**
- Changes existing services schema
- Non-services (like git) in services section feels wrong
- Service-specific fields mixed with program config

---

### Option 2: Programs & Services Separate (Current)
**Concept:** Keep them separate with clear responsibilities

**Services** (system-level service management):
```lua
services = {
    syncthing = {
        enable = true,
        service_name = "syncthing",
        ...
    },
    openssh = {
        enable = true,
        ...
    }
}
```

**Programs** (application installation and configuration):
```lua
programs = {
    -- System-level defaults
    syncthing = {
        scope = "both",
        config = {...}
    }
},

users = {
    alice = {
        programs = {
            git = {scope = "user", ...},
            neovim = {scope = "user", ...},
            syncthing = {scope = "both", ...}  -- User override
        }
    }
}
```

**Pros:**
- Services section stays focused on service management
- Programs section for application setup
- Clear separation of concerns
- Backward compatible with existing services

**Cons:**
- Duplication (syncthing in both places)
- User must understand two sections
- Coordination between sections unclear

---

### Option 3: Programs Only (Most Flexible - Recommended)
**Concept:** Everything goes in programs section. Programs can define associated services.

```lua
programs = {
    -- System-level
    syncthing = {
        scope = "both",
        package = "syncthing",
        
        -- Service configuration (optional)
        service = {
            enable = true,              -- Enable as systemd service
            service_name = "syncthing",
            socket_activation = true,
            user_service = true         -- Can be per-user
        },
        
        config = {
            auto_start = true,
            listen_address = "0.0.0.0:8384"
        }
    },
    
    git = {
        scope = "user",
        package = "git",
        -- No service section (git is not a service)
        
        config = {
            user_name = "Default Name",
            email = "default@example.com"
        }
    },
    
    openssh = {
        scope = "system",
        package = "openssh",
        
        service = {
            enable = true,
            service_name = "sshd",
            socket_activation = false
        },
        
        config = {
            PermitRootLogin = false
        }
    }
},

users = {
    alice = {
        programs = {
            git = {
                user_name = "Alice",
                email = "alice@example.com"
            },
            syncthing = {
                listen_address = "127.0.0.1:8384"  -- User override
            }
        }
    }
}
```

**Structure:**
```
Program Definition (Lua file):
├── name
├── scope: "system", "user", "both"
├── package: what to install
├── service: (optional) systemd service config
│   ├── enable
│   ├── service_name
│   ├── socket_activation
│   └── user_service (can run per-user)
├── schema: program options
├── default_config
└── generate_config()
```

**Pros:**
- Single section for all applications
- No duplication (syncthing only in programs)
- Clear where everything is configured
- Service defined as optional part of program
- Programs with scope covers all cases
- User overrides work naturally
- Can express: program-only, service-only, or combined
- Most flexible and composable

**Cons:**
- Merges two concerns (programs and services)
- Services section becomes unused (migration needed)
- Requires refactoring current services

---

## Recommendation: Option 3 (Programs Only)

**Why:**
1. **Single source of truth** — Everything in `programs` section
2. **No duplication** — Syncthing configured once, not twice
3. **Flexible** — Can express program-only, service-only, or both
4. **Scope-aware** — System/user/both applies to all
5. **User override** — Works naturally with existing Phase 3 enhancement
6. **Forward-thinking** — Aligns with how modern systems think about workloads

**Example: Complete Configuration**

```lua
return {
    programs = {
        -- System-level services + programs
        openssh = {
            scope = "system",
            service = {enable = true, service_name = "sshd"},
            config = {PermitRootLogin = false}
        },
        
        syncthing = {
            scope = "both",
            service = {enable = true, socket_activation = true},
            config = {listen_address = "0.0.0.0:8384"}
        },
        
        git = {
            scope = "user",
            config = {
                user_name = "Default",
                email = "default@example.com"
            }
        }
    },
    
    users = {
        alice = {
            programs = {
                git = {
                    user_name = "Alice",
                    email = "alice@company.com"
                },
                syncthing = {
                    listen_address = "127.0.0.1:8384"  -- Override system
                }
            }
        }
    }
}
```

---

## Implementation Approach

### Phase 3a: Add Service Definition to Programs
1. Allow `service` field in program Lua definitions
2. Validator understands service sub-section
3. Compiler generates both program and service config
4. Installation workflow runs services

### Phase 3b: Consolidate Services Into Programs (Optional Future)
1. Migrate existing system services to programs section
2. Deprecate top-level services section
3. Document migration path
4. Full backward compatibility phase

### Compatibility
- Keep existing `services` section working
- Map old services to new programs structure
- Gradual migration path (both work together initially)

---

## Questions for User

1. **Do you want everything in programs section?** (Option 3)
   - Simpler, single source of truth
   - Requires refactoring services implementation

2. **Or keep services separate?** (Option 2)
   - Backward compatible
   - But syncthing appears in two places

3. **Or completely merge?** (Option 1)
   - Even simpler
   - Services section becomes generic application section

---

## Summary

| Aspect | Option 1 | Option 2 | Option 3 |
|--------|----------|----------|----------|
| **Single Source** | ✅ | ❌ | ✅ |
| **No Duplication** | ✅ | ❌ | ✅ |
| **Backward Compat** | ❌ | ✅ | ~ (migration) |
| **Clear Separation** | ❌ | ✅ | ⚠️ (service optional) |
| **Scope Support** | ✅ | ✅ | ✅ |
| **User Overrides** | ✅ | ✅ | ✅ |
| **Flexibility** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |

**Recommended:** Option 3 (Programs Only) for flexibility and single source of truth.

---
