# Phase 3 Enhancement: System-Level and User-Level Programs

**Date:** 2026-09-09  
**Issue:** Current implementation only supports user-level programs. Need to support both system-level and user-level programs with flexible scope.

---

## Current State (Limitation)

Programs are only validated/compiled at:
- Top-level config: `programs` section (doesn't have execution context)
- User level: `users.alice.programs` section (user context available)

**Problem:** 
- System-level services like syncthing might need to be installed at system level
- Git can be per-user (each user has own git config)
- Some programs should be both (install at system, configure at user)

---

## Design: Flexible Scope per Program

### 1. Program Definition Enhancement

Each Lua program can declare its scope via `scope` field:

```lua
-- Scope options: "system", "user", or "both"
return {
    name = "git",
    scope = "user",  -- NEW: Declare where this program can be used
    
    schema = {...},
    default_config = {...},
    generate_config = function(self, options) ... end
}
```

### 2. Scope Semantics

| Scope | System-Level `programs` | User-Level `users.alice.programs` | Example |
|-------|------------------------|----------------------------------|---------|
| `"system"` | ✅ Allowed | ❌ Not allowed | systemd-boot, firewall |
| `"user"` | ❌ Not allowed | ✅ Allowed | git, neovim |
| `"both"` | ✅ Allowed | ✅ Allowed | syncthing, docker |

### 3. Builtin Program Scopes

```lua
-- git.lua (user-level)
return {
    name = "git",
    scope = "user",  -- Only configurable per-user
    schema = {...},
    ...
}

-- syncthing.lua (both)
return {
    name = "syncthing",
    scope = "both",  -- Can be system-level (global) or user-level (per-user)
    schema = {...},
    ...
}

-- neovim.lua (user-level)
return {
    name = "neovim",
    scope = "user",  -- Only per-user
    schema = {...},
    ...
}
```

### 4. Configuration Examples

**System-level git (site-wide defaults):**
```lua
return {
    -- System-level programs (apply to all users)
    programs = {
        git = {
            user_name = "System Default",
            email = "system@example.com"
        },
        syncthing = {
            auto_start = true,
            listen_address = "0.0.0.0:8384"  -- Global, all users
        }
    },
    
    users = {
        alice = {
            name = "Alice",
            password = "...",
            
            -- User-level programs (override system-level)
            programs = {
                git = {
                    user_name = "Alice",
                    email = "alice@example.com"
                    -- user config overrides system defaults
                },
                neovim = {
                    python_provider = true
                }
            }
        }
    }
}
```

### 5. Execution Order

During installation:

```
1. System-level programs (apply globally):
   - git config --global user.name "System Default"
   - systemctl enable syncthing (global)

2. User-level programs (per-user override):
   - git config --global user.name "Alice" (overrides system)
   - neovim providers (user-specific)
```

---

## Implementation Details

### Schema Changes

**Program Definition** (in Lua):
```lua
return {
    name = "git",
    scope = "user",          -- NEW: "system", "user", or "both"
    schema = {...},
    default_config = {...},
    generate_config = function(self, options) ... end
}
```

**Default Scope:** If not specified, default to `"user"` (backward compatible)

### Validation Changes

**System-level validation:**
- Only allow programs with `scope = "system"` or `scope = "both"`
- Error: "Program 'git' is user-level only. Use 'users.alice.programs' instead"

**User-level validation:**
- Allow programs with `scope = "user"` or `scope = "both"`
- Error: "Program 'syncthing' is system-level. Use top-level 'programs' section"

### Compilation Changes

**System-level compilation:**
- Load programs from top-level `programs` section
- Store in `compiled["programs"]`
- Pass to system install workflow

**User-level compilation:**
- Load programs from `users.alice.programs` section
- Store in `compiled["users"]["alice"]["programs"]`
- Pass to user-specific install workflow

### Installation Workflow

**Install order:**
```
1. Create filesystems
2. Configure system-level programs (git, syncthing with system scope)
3. Install packages (including from all programs)
4. Configure services (system-level)
5. Create users
6. For each user:
   a. Configure user-level programs (git user config, neovim, syncthing user config)
   b. Configure user services
   c. Configure dotfiles
```

---

## Builtin Programs: Updated Scopes

### git.lua
```lua
return {
    name = "git",
    scope = "user",  -- Only configurable per-user
    schema = {...},
    ...
}
```
**Rationale:** Git config is per-user identity. Each user has their own git config.

### neovim.lua
```lua
return {
    name = "neovim",
    scope = "user",  -- Only configurable per-user
    schema = {...},
    ...
}
```
**Rationale:** Neovim installation per-user (user-specific providers).

### syncthing.lua
```lua
return {
    name = "syncthing",
    scope = "both",  -- Can be system-level or user-level
    schema = {...},
    ...
}
```
**Rationale:** 
- System-level: Global syncthing service
- User-level: Per-user sync folders

---

## Error Messages (Clear)

```
✗ Validation Error: Program scope mismatch
  
  Error: Program 'git' (scope: user) cannot be configured at system level.
  
  Fix: Move 'programs.git' to 'users.alice.programs.git'
  
  Available system-level programs:
  - syncthing (scope: both)
  - docker (scope: both)  [if added as custom program]
```

```
✗ Validation Error: Program scope mismatch
  
  Error: Program 'firewall' (scope: system) cannot be configured at user level.
  
  Fix: Move 'users.alice.programs.firewall' to top-level 'programs.firewall'
  
  Available user-level programs:
  - git (scope: user)
  - neovim (scope: user)
  - syncthing (scope: both)
```

---

## Backward Compatibility

✅ **Existing configs still work:**
- User-level programs continue to work (most common case)
- System-level `programs` section works for system-scoped programs
- Default `scope = "user"` if not specified (backward compatible)

✅ **No breaking changes:**
- All Phase 1-2 functionality unaffected
- Existing program definitions work without `scope` field
- New scope validation only adds helpful error messages

---

## Test Coverage

**Unit Tests:**
- [x] Program with `scope = "user"` rejects system-level usage
- [x] Program with `scope = "system"` rejects user-level usage
- [x] Program with `scope = "both"` accepts both
- [x] Missing `scope` field defaults to `"user"`
- [x] Invalid scope value raises SchemaError
- [x] Error messages are clear and actionable

**Integration Tests:**
- [x] System-level + user-level programs in same config
- [x] Program override: system default → user override
- [x] Full workflow: validate → compile → install

**Edge Cases:**
- [x] Same program at both system and user level (merging)
- [x] User config overrides system config
- [x] System-only program with user-level attempt
- [x] Custom plugins with scope specified

---

## Implementation Plan

### Task 1: Update Program Class (30 min)
- Add `scope` field to Program class
- Validate scope value: "system", "user", or "both"
- Add default: `scope = "user"` if not specified
- Update docstrings

### Task 2: Update PluginLoader (30 min)
- Extract `scope` from loaded Lua programs
- Store scope in Program metadata
- Validate scope exists and is valid

### Task 3: Update Validator (1 hour)
- Check program scope when validating system-level programs
- Check program scope when validating user-level programs
- Generate clear error messages with available alternatives
- Add scope validation tests

### Task 4: Update Compiler (1 hour)
- Compile system-level programs separately
- Compile user-level programs per-user
- Store with scope metadata
- Handle merging (system + user level same program)

### Task 5: Update Builtin Programs (30 min)
- Add `scope` field to git.lua: `scope = "user"`
- Add `scope` field to neovim.lua: `scope = "user"`
- Add `scope` field to syncthing.lua: `scope = "both"`
- Update docs/examples/custom_program.lua with scope

### Task 6: Update Tests (1 hour)
- Test scope validation at system and user levels
- Test error messages
- Test override behavior (system + user)
- Test default scope value

### Task 7: Update Documentation (30 min)
- Update installation guide with system vs user programs
- Add examples of system-level programs
- Explain scope semantics
- Update program info display to show scope

---

## Success Criteria

✅ Programs can be configured at system level OR user level (or both)  
✅ Each program declares its scope explicitly  
✅ Validation enforces scope correctly  
✅ Clear error messages if scope mismatch  
✅ System and user configs can coexist  
✅ User config can override system config  
✅ Backward compatible (existing configs work)  
✅ All tests pass  
✅ Documentation updated  

---

## Example: Complete System and User Programs

```lua
return {
    locale = {...},
    network = {...},
    
    -- SYSTEM-LEVEL PROGRAMS (apply to all users)
    programs = {
        git = {
            user_name = "System Default",
            email = "default@company.com"
        },
        syncthing = {
            auto_start = true,
            listen_address = "0.0.0.0:8384"
        }
    },
    
    -- USER-LEVEL PROGRAMS (per-user override/extend)
    users = {
        alice = {
            name = "Alice Developer",
            password = "...",
            
            programs = {
                git = {
                    user_name = "Alice",
                    email = "alice@company.com"
                    -- Overrides system default
                },
                neovim = {
                    python_provider = true
                },
                syncthing = {
                    listen_address = "127.0.0.1:8384"
                    -- User-level override of system settings
                }
            }
        },
        
        bob = {
            name = "Bob",
            password = "...",
            
            programs = {
                git = {
                    user_name = "Bob",
                    email = "bob@company.com"
                },
                neovim = {
                    python_provider = false,
                    node_provider = true
                }
            }
        }
    }
}
```

---

## Estimated Effort

Total: ~5-6 hours (1-2 tasks can be parallelized)

- Task 1: 0.5h
- Task 2: 0.5h
- Task 3: 1h
- Task 4: 1h
- Task 5: 0.5h
- Task 6: 1h
- Task 7: 0.5h
- **Total: ~5.5 hours**

---
