# Phase 3 Part 2: Programs-Only Architecture - Specification

**Date:** 2026-09-09  
**Architecture:** Unified Programs Section with Optional Service Definitions  
**Objective:** Merge Services and Programs into single section, eliminate duplication

---

## Executive Summary

Consolidate all application management (programs + services) into a single `programs` section. Services become an optional sub-field within program definitions. This eliminates duplication (syncthing configured once) while maintaining full flexibility.

---

## Architecture

### Program Definition Structure (Lua)

```lua
return {
    name = "syncthing",
    scope = "user",  -- "system", "user", or "both"
    
    -- Application installation
    package = "syncthing",
    
    -- OPTIONAL: Service configuration (new)
    service = {
        enable = true,              -- Enable as systemd service
        service_name = "syncthing", -- systemd service name
        socket_activation = false,  -- Use socket activation
        user_service = true,        -- Can run per-user
        restart_policy = "always",  -- systemd restart policy
        
        -- Service dependencies
        after = {"network.target"},
        wanted_by = {"multi-user.target"},
        
        -- Per-user service? (if user_service = true)
        per_user = false  -- true: each user gets own service instance
    },
    
    -- Application configuration (existing)
    schema = {
        -- Schema same as before
    },
    
    default_config = {
        -- Defaults same as before
    },
    
    generate_config = function(self, options)
        -- Generate config same as before
    end
}
```

### Scope & Service Semantics

| Scope | Service Allowed? | Meaning |
|-------|------------------|---------|
| `"system"` | ✅ Yes | System-level service, system-level program config |
| `"user"` | ❌ No (ignored) | User-level only, no systemd service |
| `"both"` | ✅ Yes | Service at system level, config at system or user |

### Configuration Examples

**Example 1: System-Only Service (openssh)**
```lua
programs = {
    openssh = {
        scope = "system",
        package = "openssh",
        service = {
            enable = true,
            service_name = "sshd"
        },
        config = {
            PermitRootLogin = false
        }
    }
}
```

**Example 2: Both Levels (syncthing)**
```lua
programs = {
    syncthing = {
        scope = "both",
        package = "syncthing",
        service = {
            enable = true,
            socket_activation = true,
            user_service = true
        },
        config = {
            listen_address = "0.0.0.0:8384"
        }
    }
}

users = {
    alice = {
        programs = {
            syncthing = {
                listen_address = "127.0.0.1:8384"  -- User override
            }
        }
    }
}
```

**Example 3: User-Only Program (git, neovim)**
```lua
programs = {
    git = {
        scope = "user",
        package = "git",
        -- No service field (git is not a service)
        config = {
            user_name = "Default",
            email = "default@example.com"
        }
    },
    
    neovim = {
        scope = "user",
        package = "neovim",
        -- No service field
        config = {
            python_provider = true
        }
    }
}
```

---

## Builtin Programs with Service Definitions

### git.lua (No Service)
```lua
return {
    name = "git",
    scope = "user",
    package = "git",
    -- No service field
    schema = {...},
    default_config = {...},
    generate_config = function(self, options) ... end
}
```

### neovim.lua (No Service)
```lua
return {
    name = "neovim",
    scope = "user",
    package = "neovim",
    -- No service field
    schema = {...},
    default_config = {...},
    generate_config = function(self, options) ... end
}
```

### syncthing.lua (With Service)
```lua
return {
    name = "syncthing",
    scope = "both",
    package = "syncthing",
    
    -- Service configuration (NEW)
    service = {
        enable = true,
        service_name = "syncthing",
        socket_activation = true,
        user_service = true,
        restart_policy = "always",
        after = {"network.target"},
        wanted_by = {"multi-user.target"}
    },
    
    schema = {...},
    default_config = {...},
    generate_config = function(self, options) ... end
}
```

### openssh.lua (With Service) - FROM EXISTING SERVICES
```lua
return {
    name = "openssh",
    scope = "system",
    package = "openssh",
    
    -- Service configuration (MIGRATED from services section)
    service = {
        enable = true,
        service_name = "sshd",
        socket_activation = false,
        user_service = false,
        restart_policy = "always",
        after = {"network.target"},
        wanted_by = {"multi-user.target"}
    },
    
    schema = {
        type = "object",
        properties = {
            PermitRootLogin = {type = "boolean"},
            -- ... other SSH config
        }
    },
    
    default_config = {
        PermitRootLogin = false
    },
    
    generate_config = function(self, options)
        -- Generate sshd_config
    end
}
```

---

## Migration Path: Services → Programs

### Current Config (Old)
```lua
services = {
    openssh = {
        enable = true,
        service_name = "sshd",
        settings = {
            PermitRootLogin = false
        }
    },
    
    syncthing = {
        enable = true,
        config = configs.syncthing({...})
    }
}

programs = {
    git = {
        user_name = "Default",
        email = "default@example.com"
    }
}
```

### New Config (Programs-Only)
```lua
programs = {
    openssh = {
        scope = "system",
        config = {
            PermitRootLogin = false
        }
    },
    
    syncthing = {
        scope = "both",
        config = {
            listen_address = "0.0.0.0:8384"
        }
    },
    
    git = {
        scope = "user",
        config = {
            user_name = "Default",
            email = "default@example.com"
        }
    }
}
```

### Backward Compatibility Strategy
1. **Phase 1 (Immediate):** Support both old `services` and new `programs` sections
2. **Phase 2 (Next release):** Deprecation warnings for `services` section
3. **Phase 3 (Future):** Remove `services` section, programs-only

---

## Implementation Details

### Service Field Validation

**In Program schema (Lua):**
```lua
-- Optional service field
if lua_def.service then
    assert(lua_def.scope ~= "user", 
        "Service not allowed with scope='user'")
    
    local service = lua_def.service
    assert(service.service_name, "service_name required")
    assert(service.enable ~= nil, "enable field required")
end
```

**Service field structure validation (in validator):**
```python
service_schema = {
    "enable": bool,
    "service_name": str,
    "socket_activation": bool,  # optional
    "user_service": bool,       # optional
    "restart_policy": str,      # optional
    "after": list,              # optional
    "wanted_by": list,          # optional
    "per_user": bool            # optional
}
```

### Compilation Output

**System-level service compilation:**
```python
compiled["programs"]["openssh"] = {
    "program": <Program object>,
    "options": {...},
    "config": "sshd_config content",
    "scope": "system",
    "service": {
        "enable": True,
        "service_name": "sshd",
        "socket_activation": False,
        "user_service": False,
        "restart_policy": "always",
        "unit_file_path": "/etc/systemd/system/sshd.service"
    }
}
```

**User-level program (no service):**
```python
compiled["users"]["alice"]["programs"]["git"] = {
    "program": <Program object>,
    "options": {...},
    "config": "git config content",
    "scope": "user",
    # No service field
}
```

**User-level service override:**
```python
compiled["users"]["alice"]["programs"]["syncthing"] = {
    "program": <Program object>,
    "options": {...},  # Merged with system
    "config": "syncthing config content",
    "scope": "user",
    "overrides_system": True,
    "service": {
        # Inherited from system, or can be overridden
        "enable": True,
        "per_user": True  # User-specific service instance
    }
}
```

### Installation Workflow Integration

**Order of operations:**
```
1. Install packages (from all programs, system + user)
2. Enable system-level services
3. Create users
4. For each user:
   a. Install user packages
   b. Generate user program configs
   c. Enable user services (if service.user_service = true)
   d. Start user services
5. Start system services
```

---

## Key Decisions

### Decision 1: Service Enable in Programs or Config?
**Chosen:** Service config is separate from program config
- `service.enable` controls systemd service enablement
- `program.config` is application-specific settings
- Clear separation of concerns

### Decision 2: User-Level Services?
**Chosen:** User services allowed only when `user_service = true` in service definition
- Some services make sense per-user (syncthing folders)
- Others don't (openssh daemon)
- Program declares if user services are supported

### Decision 3: Service Override at User Level?
**Chosen:** Limited override capability
- User can override program config
- User cannot change service name or basic service config
- User can enable/disable for themselves (if `per_user = true`)
- Prevents breaking system service configuration

---

## Builtin Programs Needing Service Definitions

From current `services` section in example configs:

1. **openssh** (scope: "system")
   - Service: sshd
   - No per-user

2. **networkmanager** (scope: "system")
   - Service: NetworkManager
   - No per-user

3. **cups** (scope: "system")
   - Service: cupsd
   - No per-user

4. **bluetooth** (scope: "system")
   - Service: bluetooth
   - No per-user

5. **syncthing** (scope: "both")
   - Service: syncthing
   - Supports per-user

6. **fwupd** (scope: "system")
   - Service: fwupd
   - No per-user

7. **systemd_mount** (scope: "system")
   - Complex: custom mount services
   - Generated per-mount

---

## Validation Rules

1. Service can only exist if `scope` in ["system", "both"]
2. Service.service_name must be non-empty
3. Service.enable must be boolean
4. Service.user_service can only be true if scope supports it
5. If program has no service field, that's valid (program-only)
6. User-level program can only override program.config, not service

---

## Error Messages

**Service with user-only scope:**
```
✗ Validation Error
Program 'git' has service definition but scope='user'

Fix: Remove service field (user-level programs don't have services)
Or: Change scope to 'system' or 'both'
```

**User trying to override service config:**
```
✗ Validation Error
Cannot override service configuration at user level.

Program 'openssh' service cannot be modified per-user.
User-level configuration only available for: program settings

Available service overrides: (none for this program)
```

---

## Success Criteria

✅ Programs section is the single source of truth  
✅ Services are optional sub-fields in programs  
✅ No duplication (syncthing configured once, not twice)  
✅ Scope semantics: "system", "user", "both"  
✅ Service field validation  
✅ Backward compatible with existing services  
✅ Clear migration path  
✅ Installation workflow handles services  
✅ User-level service configuration supported  
✅ All tests pass  
✅ Full documentation  

---

## Files to Modify/Create

**Lua Programs:**
- `src/kod/registry/builtin/git.lua` (no change - no service)
- `src/kod/registry/builtin/neovim.lua` (no change - no service)
- `src/kod/registry/builtin/syncthing.lua` (ADD service field)
- `src/kod/registry/builtin/openssh.lua` (NEW - migrated from services)
- `src/kod/registry/builtin/networkmanager.lua` (NEW)
- `src/kod/registry/builtin/cups.lua` (NEW)
- `src/kod/registry/builtin/bluetooth.lua` (NEW)
- `src/kod/registry/builtin/fwupd.lua` (NEW)

**Python Code:**
- `src/kod/registry/programs.py` (ADD service field handling)
- `src/kod/config/validator.py` (ADD service validation)
- `src/kod/config/compiler.py` (ADD service compilation)
- `src/kod/system/services.py` (REFACTOR to use new structure)
- `src/kod/install/workflows.py` (ADD service workflow integration)

**Tests:**
- `tests/registry/test_programs.py` (ADD service field tests)
- `tests/config/test_validator.py` (ADD service validation tests)
- `tests/config/test_compiler.py` (ADD service compilation tests)
- `tests/registry/test_service_programs.py` (NEW - comprehensive service tests)

**Documentation:**
- `docs/INSTALLATION_GUIDE.md` (UPDATE - programs-only section)
- `docs/extending.md` (UPDATE - service field in programs)
- `README.md` (UPDATE - programs-only architecture)
- `docs/MIGRATION_GUIDE.md` (NEW - services → programs migration)

---

## Estimated Effort

| Task | Hours | Notes |
|------|-------|-------|
| 1. Design/finalize structure | 0.5h | ✅ Done |
| 2. Program class service field | 1h | Extract service, validate |
| 3. Validator service handling | 1.5h | Validate service config |
| 4. Compiler service integration | 1.5h | Compile service definitions |
| 5. Builtin service programs | 2h | openssh, syncthing, etc. |
| 6. Installation workflow | 1h | Run services in order |
| 7. Comprehensive tests | 2h | Service + program tests |
| 8. Documentation + migration | 1.5h | Guides and examples |
| **Total** | **~11 hours** | Can parallelize after task 1 |

---

## Phasing

**Phase A (Immediate):** Tasks 1-4
- Core infrastructure: Programs + Services unified
- Backward compat with existing services

**Phase B (Follow-up):** Tasks 5-8
- Builtin service programs
- Full testing and documentation
- Migration guide

---

## Backward Compatibility

### Compatibility Approach
1. Keep existing `services` section working
2. Internally convert old services to programs format
3. No breaking changes to existing configs
4. Deprecation path for future removal

### Migration Strategy
**Old config still works:**
```lua
services = { openssh = {...} }
programs = { git = {...} }
```

**Internally converted to:**
```lua
programs = {
    openssh = {..., service = {...}},
    git = {...}
}
```

**Users can migrate gradually:**
- Keep old services section (works)
- Gradually move to programs section
- Full services → programs conversion optional

---
