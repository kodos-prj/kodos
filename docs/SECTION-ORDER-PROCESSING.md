# Section Order Processing in Phase 5c & Phase 5d

## Overview

Phase 5c/5d has **two levels of ordering**:

1. **Section Iteration Order** — Which sections are processed (planner)
2. **Step Execution Order** — Which steps within/across sections run first (steps)

**Phase 5d Note:** User-level programs and services are merged into system-level ordering. See [User Programs/Services Merge](#user-programsservices-merge-phase-5d) below.

---

## Level 1: Section Iteration Order (Planner)

### Current Order (Planner.sections)

```lua
Planner.sections = {
    'base_distribution',  -- 1. Validate distro choice
    'repos',              -- 2. Configure package repos
    'devices',            -- 3. Prepare disks/partitions
    'boot',               -- 4. Install kernel & bootloader
    'hardware',           -- 5. Configure hardware (pipewire, etc.)
    'locale',             -- 6. Set locale, timezone, keymap
    'network',            -- 7. Configure hostname, ipv6
    'users',              -- 8. Create users and groups
    'desktop',            -- 9. Install desktop environment
    'fonts',              -- 10. Install font packages
    'packages',           -- 11. Install additional packages
    'services',           -- 12. Enable/start services
    'programs'            -- 13. Install custom programs
}
```

### Why This Order?

**Logical sequence for system bootstrap:**
1. **base_distribution** — Foundation (must be first)
2. **repos** — Package sources (needed before installing anything)
3. **devices** — Disk layout (physical before logical)
4. **boot** — Bootloader (foundational)
5. **hardware** — Low-level hardware setup
6. **locale** — System settings (language, timezone)
7. **network** — Network config (hostname, ipv6)
8. **users** — User accounts (before home configs)
9. **desktop** — Desktop environment
10. **fonts** — Font packages
11. **packages** — Additional packages
12. **services** — Service management
13. **programs** — High-level programs (can depend on anything below)

### Key Principle

**Section order is just iteration order, NOT execution order.**

Sections are processed sequentially **only to collect their steps**. The actual execution order is determined by step `order` fields and `depends_on` relationships.

---

## Level 2: Step Execution Order

### Step Object Format

Each step emitted by a section has:

```lua
{
    name = "unique_step_id",           -- Required: unique identifier
    description = "Human readable",    -- Required: what does it do
    command = "shell command",         -- Required: what to execute
    order = 100,                       -- Optional: execution priority (default: 0)
    on_distro = "arch" or "debian",    -- Optional: distro-specific (nil = both)
    depends_on = {"other_step"},       -- Optional: prerequisite steps
}
```

### Order Field (Numeric Priority)

**Lower `order` values execute first.**

**Boot section example:**

```lua
table.insert(steps, {
    name = "boot_kernel_install",
    description = "Install kernel",
    command = "pacman -S --noconfirm linux",
    order = 200,                       -- Execute at priority 200
})

table.insert(steps, {
    name = "boot_loader_install_systemd",
    description = "Install systemd-boot",
    command = "bootctl install",
    order = 210,                       -- Execute at priority 210 (after kernel)
})

table.insert(steps, {
    name = "boot_loader_timeout",
    description = "Set boot timeout",
    command = "echo 'timeout 10' > /boot/loader/loader.conf",
    order = 211,                       -- Execute at priority 211 (last in boot)
})
```

### Typical Order Values

| Range | Purpose | Examples |
|-------|---------|----------|
| 0-99 | Prep/setup | repo config, disk setup |
| 100-199 | Foundation | base system, kernel |
| 200-299 | Boot setup | bootloader config |
| 300-399 | System config | locale, network, hostname |
| 400-499 | Users/groups | user creation, groups |
| 500-599 | Desktop | DE installation |
| 600-699 | Fonts | font packages |
| 700-799 | Packages | general packages |
| 800-899 | Services | service enablement |
| 900-999 | Programs | custom programs |

### Depends_on: Step Dependencies

**Explicit prerequisite relationships:**

```lua
table.insert(steps, {
    name = "boot_kernel_modules_config",
    description = "Configure kernel modules",
    command = "...",
    order = 201,
    depends_on = {"boot_kernel_install"},  -- Must run AFTER kernel install
})
```

**How it works:**
1. Planner sorts steps by `order` field first
2. Then applies dependency constraints (topological sort)
3. If step B depends on step A, step A runs first (regardless of order values)

### Real Example: Boot Section

```lua
-- Step 1: Install kernel (order=200)
{
    name = "boot_kernel_install",
    order = 200,
}

-- Step 2: Config modules (order=201, depends on kernel)
{
    name = "boot_kernel_modules_config",
    order = 201,
    depends_on = {"boot_kernel_install"},  -- Must wait for kernel
}

-- Step 3: Install bootloader (order=210)
{
    name = "boot_loader_install_systemd",
    order = 210,
}

-- Step 4: Config timeout (order=211, depends on bootloader)
{
    name = "boot_loader_timeout",
    order = 211,
    depends_on = {"boot_loader_install_systemd"},  -- Must wait for bootloader
}

-- Execution order: 1 → 2 → 3 → 4
-- (200 < 201 < 210 < 211, all dependencies satisfied)
```

---

## How Planner Sorts Steps

**File:** `src/kod/lib/planner.lua:sort_steps()`

```lua
local function sort_steps(steps)
    -- Pass 1: Sort by order field (numeric priority)
    table.sort(steps, function(a, b)
        local order_a = a.order or 0
        local order_b = b.order or 0
        if order_a ~= order_b then
            return order_a < order_b  -- Lower order first
        end
        return false  -- Stable sort (preserve insertion order for same order)
    end)
    
    -- Pass 2: Handle dependencies (topological sort)
    local result = {}
    local added = {}
    
    for _, step in ipairs(steps) do
        if step.depends_on and #step.depends_on > 0 then
            -- Try to add dependencies first
            for _, dep_name in ipairs(step.depends_on) do
                if not added[dep_name] then
                    -- Find and add dependency
                    for _, candidate in ipairs(steps) do
                        if candidate.name == dep_name and not added[candidate.name] then
                            table.insert(result, candidate)
                            added[candidate.name] = true
                            break
                        end
                    end
                end
            end
        end
        
        if not added[step.name] then
            table.insert(result, step)
            added[step.name] = true
        end
    end
    
    return result
end
```

**Algorithm:**
1. Sort all steps by `order` field (ascending)
2. Walk through sorted steps
3. For each step, if it has `depends_on`, add those dependencies first
4. Then add the step itself
5. Skip if already added (prevents duplicates)

---

## Practical Examples

### Example 1: Simple Case (Just Order)

**Config:**
```lua
base_distribution = "arch"
packages = {"git", "vim", "tmux"}
```

**Generated steps:**
- packages section emits: install git (order=700), install vim (order=700), install tmux (order=700)
- No dependencies
- Execution: 700 < everything else, all at same priority
- Order: git, vim, tmux (insertion order preserved for same priority)

### Example 2: Complex Case (Order + Dependencies)

**Config:**
```lua
base_distribution = "arch"
boot = {
    kernel = {
        package = "linux-lts",
        modules = {"virtio_blk", "ahci"}
    },
    loader = {
        type = "systemd-boot",
        timeout = 10
    }
}
```

**Generated steps (boot section):**

| # | Step | Order | Depends On | Exec Order |
|---|------|-------|-----------|-----------|
| 1 | boot_kernel_install | 200 | — | 1st |
| 2 | boot_kernel_modules_config | 201 | boot_kernel_install | 2nd |
| 3 | boot_loader_install_systemd | 210 | — | 3rd |
| 4 | boot_loader_timeout | 211 | boot_loader_install_systemd | 4th |

**Sorted by planner:**
1. Step 1 (order 200, no deps) ✓
2. Step 2 (order 201, dep on step 1 which is done) ✓
3. Step 3 (order 210, no deps) ✓
4. Step 4 (order 211, dep on step 3 which is done) ✓

### Example 3: Cross-Section Dependencies

**Scenario:** Users section needs to run after base system setup

**Users section:**
```lua
{
    name = "users_create_alice",
    description = "Create user alice",
    command = "useradd -m -s /bin/bash alice",
    order = 400,
    depends_on = {"system_base_setup"},  -- Wait for base system
}
```

**If system_base_setup (order=100) exists:**
- Even though 400 > 100, dependency forces correct order
- system_base_setup runs first (order 100)
- users_create_alice runs after (depends_on satisfied)

---

## How to Add a New Section

**To maintain correct ordering, follow these steps:**

### Step 1: Determine Section Position

Choose where it logically fits in the sequence:

```lua
Planner.sections = {
    'base_distribution',
    'repos',
    'devices',
    'boot',
    'hardware',
    'locale',
    'network',
    'users',
    'desktop',
    'fonts',
    'packages',
    'MY_NEW_SECTION',  -- <- Insert here if it configures packages
    'services',
    'programs'
}
```

### Step 2: Assign Order Values

Use the range corresponding to when it should execute:

```lua
-- src/kod/sections/my_new_section.lua
emit_steps = function(config, distro)
    local steps = {}
    
    if not config then
        return steps
    end
    
    -- Assuming this configures system files (order range 300-399)
    table.insert(steps, {
        name = "my_section_step_1",
        description = "Do something",
        command = "...",
        order = 350,  -- Between locale (300) and users (400)
    })
    
    return steps
end
```

### Step 3: Add Dependencies If Needed

```lua
table.insert(steps, {
    name = "my_section_step_2",
    description = "Do something else",
    command = "...",
    order = 351,
    depends_on = {"my_section_step_1"},  -- Must run after step 1
})
```

### Step 4: Test

Run planner with test config:
```lua
local planner = require('kod.lib.planner')
local steps = planner:compose(config, "arch")

-- Verify steps are in correct order
for i, step in ipairs(steps) do
    print(i .. ": " .. step.order .. " - " .. step.name)
end
```

---

## Common Patterns

### Pattern 1: Sequential Steps Within Section

```lua
table.insert(steps, {
    name = "section_step_1",
    order = 100,
})

table.insert(steps, {
    name = "section_step_2",
    order = 101,
})

table.insert(steps, {
    name = "section_step_3",
    order = 102,
})
-- Automatic ordering: 100 < 101 < 102
```

### Pattern 2: Dependent Steps

```lua
table.insert(steps, {
    name = "section_prepare",
    order = 100,
})

table.insert(steps, {
    name = "section_execute",
    order = 101,
    depends_on = {"section_prepare"},  -- Explicit requirement
})
-- Forced order: prepare → execute (even if order was reversed)
```

### Pattern 3: Conditional Dependencies

```lua
if config.some_feature then
    table.insert(steps, {
        name = "section_feature_setup",
        order = 100,
    })
end

table.insert(steps, {
    name = "section_main",
    order = 200,
    depends_on = config.some_feature and {"section_feature_setup"} or {},
})
-- If feature enabled: feature_setup (100) → main (200)
-- If feature disabled: main (200) only
```

---

## Performance Considerations

### Caching

Planner caches loaded section modules:

```lua
local function load_section(section_name)
    if Planner._section_cache[section_name] then
        return Planner._section_cache[section_name]
    end
    
    local section = require('kod.sections.' .. section_name)
    Planner._section_cache[section_name] = section
    return section
end
```

**Impact:** Section modules loaded only once per planner instance.

### Step Sorting Complexity

- Pass 1: O(n log n) — standard sort
- Pass 2: O(n²) — topological sort (simple implementation)

For typical config (~50-100 steps): negligible performance impact.

---

## User Programs/Services Merge (Phase 5d)

### New in Phase 5d: User-Level Programs & Services

Phase 5d introduces user-level configuration blocks:

```lua
users = {
  abuss = {
    programs = {                   -- NEW: User programs
      git = { enable = true },
      zsh = { enable = true },
    },
    
    services = {                   -- NEW: User services
      syncthing = { enable = false },
    },
  },
}
```

**Challenge:** How do user-level programs/services integrate with system-level ordering?

### Solution: Merge at Plan Time

**During planning, user programs/services are merged into system step order:**

1. Planner processes `users` section
2. For each user with `programs` block:
   - Extract programs into list
   - Merge with system `programs` section steps
   - Emit combined steps with user context
3. Same process for `services`

### Execution Order: User vs System

**Result:** User program steps are interleaved with system program steps based on step order values.

**Example:**

```lua
-- System config
programs = {
  firefox = { enable = true },
  chromium = { enable = true },
}

-- User config (abuss)
users = {
  abuss = {
    programs = {
      git = { enable = true },
      neovim = { enable = true },
    },
  },
}
```

**Generated steps (merged):**

| Step | Type | Program | Order | User |
|------|------|---------|-------|------|
| 1 | System | firefox | 900 | system |
| 2 | System | chromium | 900 | system |
| 3 | User | git | 900 | abuss |
| 4 | User | neovim | 900 | abuss |

**Execution:** All at order 900 (insertion order preserved): firefox → chromium → git → neovim

### User Context in Steps

Each user program step carries user information:

```lua
{
    name = "programs_user_abuss_git_install",
    description = "Install git for user abuss",
    command = "pacman -S --noconfirm git",
    order = 900,
    user = "abuss",                         -- Phase 5d: User context
    depends_on = {"users_abuss_create"},   -- Wait for user creation
}
```

### User Services Same Pattern

**User services** follow the same merge pattern:

```lua
-- System config
services = {
  openssh = { enable = true },
}

-- User config (abuss)
users = {
  abuss = {
    services = {
      syncthing = { enable = false },
    },
  },
}
```

**Generated steps:**

| Step | Service | Order | User | Depends On |
|------|---------|-------|------|-----------|
| 1 | openssh (system) | 800 | system | — |
| 2 | syncthing (abuss) | 800 | abuss | users_abuss_create |

**Key:** User services depend on user creation step to ensure user exists before service setup.

### Phase 5d User Section Order

The updated section iteration order includes extended `users` processing:

```lua
Planner.sections = {
    'base_distribution',     -- 1. Validate distro
    'repos',                 -- 2. Configure repos
    'devices',               -- 3. Prepare disks
    'boot',                  -- 4. Install kernel & bootloader
    'hardware',              -- 5. Configure hardware
    'locale',                -- 6. Set locale
    'network',               -- 7. Configure network
    'users',                 -- 8. Create users (Phase 5d: now emits 3 phases)
    'desktop',               -- 9. Install desktop environment
    'fonts',                 -- 10. Install fonts
    'packages',              -- 11. Install packages
    'services',              -- 12. Enable services (Phase 5d: merged with user services)
    'programs'               -- 13. Install programs (Phase 5d: merged with user programs)
}
```

### Phase 5d `users` Section Emits Steps in Order

**Phase 1: User creation (order 400)**
```lua
{
    name = "users_abuss_create",
    description = "Create user abuss",
    order = 400,
}
```

**Phase 2: User identity setup (order 410)**
```lua
{
    name = "users_abuss_identity_setup",
    description = "Set password and groups for abuss",
    order = 410,
    depends_on = {"users_abuss_create"},
}
```

**Phase 3: User programs/services (order 900/800)**
```lua
{
    name = "programs_user_abuss_git",
    description = "Install git for abuss",
    order = 900,
    user = "abuss",
    depends_on = {"users_abuss_create"},
}
```

**Benefit:** User setup steps (creation, identity) happen early (order 400+), while user programs/services happen in their proper section order (900/800) but with user context intact.

### Real-World Example: eszkoz User Programs

eszkoz configures user `abuss` with multiple programs:

```lua
users = {
  abuss = {
    identity = { ... },
    ssh_keys = { ... },
    dotfiles = { ... },
    
    programs = {
      git = { enable = true, config = configs.git({...}) },
      zsh = { enable = true, deploy_config = true },
      neovim = { enable = true, deploy_config = true },
      emacs = { enable = true, package = "emacs-wayland", extra_packages = {...} },
    },
  },
}
```

**Generated steps (eszkoz, subset):**

| Order | Step | User | Depends On |
|-------|------|------|-----------|
| 400 | users_abuss_create | — | — |
| 410 | users_abuss_identity_setup | — | users_abuss_create |
| 420 | users_abuss_ssh_keys_setup | — | users_abuss_create |
| 430 | users_abuss_dotfiles_deploy | — | users_abuss_create |
| 700 | packages (all) | — | — |
| 800 | services (system) | — | — |
| 900 | programs_git_install (system) | — | — |
| 900 | programs_user_abuss_git | abuss | users_abuss_create |
| 900 | programs_user_abuss_zsh | abuss | users_abuss_create |
| 900 | programs_user_abuss_neovim | abuss | users_abuss_create |
| 900 | programs_user_abuss_emacs | abuss | users_abuss_create |

### Dotfiles Integration

User dotfiles are deployed as part of user section (order ~430):

```lua
{
    name = "users_abuss_dotfiles_deploy",
    description = "Deploy dotfiles for abuss using stow",
    command = "cd ~/.dotfiles && stow zsh git nvim helix emacs",
    order = 430,
    user = "abuss",
    depends_on = {"users_abuss_create"},
}
```

Then user programs that reference dotfiles (via `deploy_config = true`) run after:

```lua
{
    name = "programs_user_abuss_neovim",
    description = "Install neovim for user abuss",
    command = "pacman -S --noconfirm neovim",
    order = 900,
    user = "abuss",
    depends_on = {
        "users_abuss_create",
        "users_abuss_dotfiles_deploy",  -- Wait for dotfiles
    },
}
```

**Result:** Dotfiles deployed (order 430) → programs installed (order 900) → config files already in place from dotfiles.

---

## Summary

**Section Order Processing:**

1. **Planner iterates sections** in fixed order (base_distribution → programs)
   - Order is just for collecting steps
   - Doesn't affect execution

2. **Each section emits steps** with `order` field (0-999 range)
   - Lower order = executes first
   - Default order = 0

3. **Planner sorts steps** by order (pass 1), then by dependencies (pass 2)
   - Topological sort ensures dependencies met
   - Execution order is deterministic

4. **Steps execute in sorted order** during bootstrap
   - respecting both order field and depends_on constraints

**Key Principle:** _Section iteration order is independent of step execution order._

---

## Files Reference

- **Planner:** `src/kod/lib/planner.lua` (lines 7-79 for sorting)
- **Boot section:** `src/kod/sections/boot.lua` (example step ordering)
- **Users section:** `src/kod/sections/users.lua` (Phase 5d: user programs/services merge)
- **Other sections:** `src/kod/sections/*.lua` (follow same pattern)

## Phase 5d Documentation

- [PHASE-5D-STRUCTURED-DESIGN.md](./PHASE-5D-STRUCTURED-DESIGN.md) — Full Phase 5d schema overview
- [ADVANCED-USER-CONFIG.md](./ADVANCED-USER-CONFIG.md) — User-level programs & services
- [SERVICE-CUSTOMIZATION.md](./SERVICE-CUSTOMIZATION.md) — Service config blocks
- [DESKTOP-ENVIRONMENTS.md](./DESKTOP-ENVIRONMENTS.md) — Multi-DE configuration
