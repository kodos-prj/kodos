# Rebuild Process - Complete Function Call Reference

## Overview

The rebuild process updates an existing KodOS installation with configuration changes. 

**Two Rebuild Modes:**
1. **`new_generation=True`** (snapshot-based rebuild)
   - Creates new generation snapshot at `/kod/generations/N+1/rootfs`
   - Executes all changes in chroot environment
   - No automatic swap (user keeps both generations)
   - Use case: Testing, staged deployments, keeping rollback point

2. **`new_generation=False`** (in-place rebuild) — DEFAULT
   - Modifies current system directly (mount_point="/")
   - No chroot (executes on host)
   - Creates backup snapshot before changes
   - **Atomic swap:** After success, swaps current ↔ previous generations
   - **Rollback capability:** If failure occurs, restores from backup
   - Use case: Production updates, live system modifications

**Both modes:**
- Compute **diffs** between current and target state
- Only generate steps for **changed packages/services**
- Preserve old generation as rollback point

## Phase 1: Entry Point & Mode Selection

### `kod rebuild` (kod.py:639)

**Signature:**
```python
def rebuild(config, new_generation=False, update=False, dry_run=False):
    """Rebuild KodOS system with configuration changes"""
```

**Arguments:**
- `--config TEXT` - Path to configuration file (required)
- `--new-generation` - Create new generation snapshot (don't modify current)
- `--update` - Update package versions before rebuild
- `--dry-run` - Print plan without executing

**Mode Selection (kod.py:703-715):**
```python
if new_generation:
    # Mode 1: Snapshot-based rebuild (kod.py:704-709)
    exec(f"btrfs subvolume snapshot / {next_state_path}/rootfs")
    use_chroot = True                          # Execute in snapshot
    new_root_path = create_next_generation()   # /kod/generations/N+1/rootfs
    setup_chroot_mounts(new_root_path)         # Setup /proc, /sys, /dev
else:
    # Mode 2: In-place rebuild (kod.py:710-715) — DEFAULT
    exec("btrfs subvolume snapshot / /kod/current/old-rootfs")  # Backup
    copy_state_files()                         # Preserve package/service state
    use_chroot = False                         # Execute on host (/)
    new_root_path = "/"                        # Modify current system
```

**Context Creation (kod.py:717):**
```python
ctx = Context(
    user=os.environ["USER"],
    mount_point=new_root_path,      # "/" or "/kod/generations/N+1/rootfs"
    use_chroot=use_chroot           # False or True
)
```

## Phase 2: Plan Composition

### `plan_rebuild()` (kod.py:751)

**Signature:**
```python
def plan_rebuild(config, current_packages, current_services,
                 current_generation, kernel):
    """Build plan for system rebuild (with diffs)"""
    return build_plan(
        config=config,
        distro_name=detect_distro(),
        baseline='current',
        packages=new_packages - current_packages,
        services=new_services - current_services
    )
```

**Key Logic:**
1. Load target config from file
2. Read current state from `/kod/generations/N/installed_packages`
3. Compute differences (package diff, service diff)
4. Pass `baseline='current'` to build_plan (skips unchanged sections)

**Returns:** `list[Step]` with only changes

### `build_plan()` (planner.py:463)

**Signature:**
```python
def build_plan(config, distro_name, baseline='empty',
               packages=None, services=None):
    """Build complete installation plan"""
    return compose_steps_lua(
        config, 
        distro_name,
        baseline,
        packages=packages,
        services=services
    )
```

**Parameters:**
- `baseline='empty'` → Install from scratch (all steps)
- `baseline='current'` → Rebuild (only diff steps)
- `packages` → Only install these packages (if provided)
- `services` → Only enable these services (if provided)

**Returns:** `list[Step]`

### `compose_steps_lua()` (planner.py:108)

**Signature:**
```python
def compose_steps_lua(config, distro_name, baseline='empty',
                      packages=None, services=None):
    """Compose installation plan using Lua sections"""
    lua = get_lua_runtime()  # Singleton lupa interpreter
    
    config_lua = _convert_to_lua_table(lua, config)
    
    planner_module = lua.require('kod.planning.planner')
    lua_steps = planner_module.compose(
        config_lua, 
        distro_name,
        baseline,
        packages=packages,
        services=services
    )
```

**Lua Integration:**
1. Get singleton Lua runtime (lupa)
2. Convert Python dict → Lua table
3. Load `planning/planner.lua:140 - planner_module.compose()`
4. For each section, call `section.emit_steps(config, distro, baseline)`

**Returns:** `list[LuaTable]` (steps)

## Phase 3: Lua Planning (planning/planner.lua)

### `planner_module.compose()` (planning/planner.lua:140)

**Lua Signature:**
```lua
function compose(config, distro, baseline, packages, services)
    local all_steps = {}
    
    -- For each section: base_distribution, repos, devices, boot, ...
    for _, section_name in ipairs(SECTIONS) do
        local section = require('kod.sections.' .. section_name)
        
        -- Skip if baseline='current' and no relevant changes
        if should_emit(section_name, baseline, packages, services) then
            local steps = section.emit_steps(config, distro)
            table.extend(all_steps, steps)
        end
    end
    
    return sort_steps(all_steps)
end
```

**Sections Called (if relevant to rebuild):**

#### 1. `base_distribution.lua:emit_steps()` (skipped if baseline='current')
Returns: distro-specific base steps

#### 2. `repos.lua:emit_steps()` (skipped if baseline='current')
Returns: repository configuration steps

#### 3. `devices.lua:emit_steps()` (skipped unless filesystem changes)
Returns: partition/mount steps (order 100-200)

#### 4. `boot.lua:emit_steps()` (always)
Returns: bootloader steps (order 200-300)

#### 5. `packages.lua:emit_steps()` (only if packages changed)

**Signature:**
```lua
function emit_steps(config, distro)
    -- This is the ONLY section called during rebuild for packages!
    
    -- Step 1: aggregate all packages from config
    local all_pkgs = aggregate_all_packages(config)
    
    -- Step 2: split into streams
    local normal, aur, flatpak = separate_packages(all_pkgs)
    
    -- Step 3: generate installation steps
    return emit_steps(normal, aur, flatpak, distro)
end
```

**Package Aggregation** (packages.lua:368):
```lua
function aggregate_all_packages(config)
    local pkgs = {}
    
    -- Collect from all sources
    for _, env in ipairs(config.desktop.environments) do
        if env.enable then
            table.extend(pkgs, env.extra_packages)
        end
    end
    
    for _, hw in ipairs(config.hardware) do
        if hw.enable then
            table.extend(pkgs, hw.extra_packages)
        end
    end
    
    -- ... more sources ...
    
    return deduplicate(pkgs)
end
```

**Package Separation** (packages.lua:405):
```lua
function separate_packages(packages)
    local normal, aur, flatpak = {}, {}, {}
    
    for _, pkg in ipairs(packages) do
        if starts_with(pkg, 'aur:') then
            table.insert(aur, strip_prefix(pkg))
        elseif starts_with(pkg, 'flatpak:') then
            table.insert(flatpak, strip_prefix(pkg))
        else
            table.insert(normal, pkg)
        end
    end
    
    return normal, aur, flatpak
end
```

**Step Emission** (packages.lua:419):
```lua
function emit_steps(normal_pkgs, aur_pkgs, flatpak_pkgs, distro)
    local steps = {}
    
    -- Normal packages: single pacman -S command
    if #normal_pkgs > 0 then
        table.insert(steps, {
            name = 'packages_install_normal_and_base',
            kind = 'system/package/pacman',
            order = 490,
            program = 'pacman -S --noconfirm --needed ...'
        })
    end
    
    -- AUR packages: 5-step sequence
    if #aur_pkgs > 0 then
        -- Step 490: install base-devel
        -- Step 492: create kod user
        -- Step 493: configure sudoers
        -- Step 494: build yay-bin
        -- Step 500+: build each AUR package
    end
    
    -- Flatpak apps: systemd service
    if #flatpak_pkgs > 0 then
        table.insert(steps, {
            name = 'packages_install_flatpak_apps',
            kind = 'system/service',
            order = 550,
            service = 'kod-flatpak-install.service'
        })
    end
    
    return steps
end
```

#### 6. `services.lua:emit_steps()` (only if services changed)

**Signature:**
```lua
function emit_steps(config, distro)
    local steps = {}
    
    -- For each service in config.services
    for service_name, enabled in pairs(config.services) do
        if enabled then
            table.insert(steps, {
                name = 'service_enable_' .. service_name,
                kind = 'system/service',
                program = 'systemctl enable --now ' .. service_name,
                order = 600 + hash(service_name)
            })
        end
    end
    
    return steps
end
```

**Returns:** List of `systemctl enable` commands

#### 7. Other Sections

`users.lua`, `fonts.lua`, `locale.lua`, `network.lua`, etc.

### `sort_steps()` (planner.py:180)

**Python Signature:**
```python
def sort_steps(lua_steps):
    """Sort Lua steps by order field, handle dependencies"""
    # Extract order values
    steps_with_order = [(step['order'], step) for step in lua_steps]
    steps_with_order.sort()
    
    # Check dependencies
    steps = [step for _, step in steps_with_order]
    
    # Validate DAG (directed acyclic graph)
    for step in steps:
        if 'depends_on' in step:
            for dep in step['depends_on']:
                assert dep_satisfied_before(step)
    
    return steps
```

**Order Values (typical):**
- 100-200: devices (partitioning, mounting)
- 200-300: boot (bootloader setup)
- 300-400: base distribution (pacman.conf, etc.)
- 400-500: users and locale
- 490: packages (normal + base-devel)
- 492-501: AUR setup (yay build)
- 550: services (systemctl enable)
- 600+: other services

## Phase 4: Lua→Python Conversion

### `_convert_lua_step_to_step()` (planner.py:205)

**Signature:**
```python
def _convert_lua_step_to_step(lua_step, index):
    """Convert Lua step table to Python Step object"""
    
    # Extract Lua fields
    kind = lua_step['kind']
    name = lua_step['name']
    program = lua_step.get('program', None)
    args = lua_step.get('args', ())
    order = lua_step.get('order', 0)
    
    # Convert Lua types to Python
    if isinstance(args, lupa.LuaTable):
        args = tuple(args.values())
    
    meta = {}
    if 'meta' in lua_step:
        meta = dict(lua_step['meta'])
    
    # Create Step object
    return Step(
        kind=kind,
        name=name,
        program=program,
        args=args,
        meta=meta,
        index=index,
        order=order
    )
```

## Phase 5: Execution

### `execute_steps()` (executor.py:36)

**Signature:**
```python
def execute_steps(steps, mount_point, use_chroot=True,
                  new_root_path=None):
    """Execute all steps in the plan"""
    
    # Build environment
    env = build_env(mount_point, new_root_path)
    
    # Call Lua executor
    lua = get_lua_runtime()
    executor_module = lua.require('kod.planning.executor')
    
    results = executor_module.run(steps, env, dispatch_callback)
    
    return results
```

**Environment** includes:
- `mount_point`: Root mount path
- Callbacks for kernel update, boot entry creation, etc.

### Lua Executor (planning/executor.lua:40)

**Lua Signature:**
```lua
function run(steps, ctx, dispatch)
    local results = {}
    
    for i, step in ipairs(steps) do
        -- Fire pre-execution hooks
        fire_hook('pre:' .. step.kind, step)
        
        -- Execute based on kind
        if step.program then
            local ret = run_shell(step.program, {
                chroot = step.chroot,
                timeout = step.timeout_s
            })
            table.insert(results, {step = step, code = ret})
        elseif step.kind == 'system/callback' then
            -- Call Python callback
            dispatch(step, ctx)
        end
        
        -- Handle errors
        if ret ~= 0 then
            if step.on_error == 'abort' then
                error('Step failed: ' .. step.name)
            else
                log_warning('Step failed but continuing: ' .. step.name)
            end
        end
        
        -- Fire post-execution hooks
        fire_hook('post:' .. step.kind, step)
    end
    
    return results
end
```

**Step Execution Loop:**
1. Pre hooks (firewall, logging, etc.)
2. Execute command (shell, chroot, timeout)
3. Check return code
4. Apply on_error policy (abort|warn)
5. Post hooks (validation, cleanup)
6. Move to next step

### `run_shell()` (executor.lua:70)

**Lua Signature:**
```lua
function run_shell(cmd, opts)
    local chroot = opts.chroot or false
    local timeout = opts.timeout or nil
    
    if chroot then
        cmd = 'chroot ' .. chroot .. ' /bin/sh -c "' .. cmd .. '"'
    end
    
    if timeout then
        cmd = 'timeout ' .. timeout .. ' ' .. cmd
    end
    
    return os.execute(cmd)
end
```

## Phase 6: State Management

### `store_packages_services()` (packages.py)

**Signature:**
```python
def store_packages_services(state_path, packages, services):
    """Write package and service state to JSON"""
    
    installed = {
        'packages': packages,
        'kernel': detect_kernel()
    }
    
    enabled = {
        'services': services
    }
    
    with open(f'{state_path}/installed_packages', 'w') as f:
        json.dump(installed, f)
    
    with open(f'{state_path}/enabled_services', 'w') as f:
        json.dump(enabled, f)
```

**Files Written:**
- `/kod/generations/N+1/installed_packages` (JSON)
- `/kod/generations/N+1/enabled_services` (JSON)

### `generate_package_lock()` (distro/base.py)

**Signature:**
```python
def generate_package_lock(mount_point, state_path):
    """Generate package lock file with actual versions"""
    
    # Query installed packages with versions
    pacman_cmd = f'pacman -Q'
    output = run_in_chroot(mount_point, pacman_cmd)
    
    lock_data = {
        'pacman': parse_pacman_output(output),
        'aur': extract_aur_packages(installed_packages),
        'flatpak': query_flatpak_versions(),
        'generated_at': datetime.now().isoformat()
    }
    
    with open(f'{state_path}/packages.lock', 'w') as f:
        json.dump(lock_data, f)
```

**Lock File Format:**
```json
{
    "pacman": ["vim-9.0.1234-1", "git-2.55.0-1", ...],
    "aur": ["brother-dcp-l2550dw-4.0.0-2", ...],
    "flatpak": ["com.visualstudio.code/23.1", ...],
    "generated_at": "2026-09-23T23:30:00+00:00"
}
```

## Phase 7: Finalization & Generation Deployment

### Two Paths Based on Mode (kod.py:815-837)

**Path 1: `new_generation=False` (In-place rebuild) — DEFAULT**
```python
if not new_generation:
    # Atomically swap generations with rollback on failure
    try:
        _swap_generations_atomic(current_generation, generation_id)
    except RuntimeError as e:
        print(f"❌ Failed to swap generations: {e}")
        sys.exit(1)
    
    # Update boot configuration
    updated_partition_list = change_subvol(
        partition_list,
        subvol=f"generations/{generation_id}",  # Point to new generation
        mount_points=["/"],
    )
    generate_fstab(updated_partition_list, new_root_path)  # Write to /etc/fstab
```

**Path 2: `new_generation=True` (Snapshot-based rebuild)**
```python
else:
    # Keep new generation as separate snapshot, don't swap
    # User can manually boot into it or test before deploying
    pass  # Just unmount the snapshot
    
# Both paths: Write generation number file
with open(f"{next_state_path}/rootfs/.generation", "w") as f:
    f.write(str(generation_id))

if new_generation:
    exec(f"umount -R {new_root_path}")  # Unmount snapshot
```

**Signature:**
```python
def _swap_generations_atomic(current_gen, next_gen, state_files):
    """Atomically swap current and next generations"""
    
    try:
        # 1. Create backup
        backup_path = f'{current_gen}/.backup'
        run(['btrfs', 'subvolume', 'snapshot', current_gen, backup_path])
        
        # 2. Move next → current
        temp_next = f'{current_gen}/.temp_next'
        run(['btrfs', 'subvolume', 'move', next_gen, temp_next])
        
        # 3. Move current → previous (generation N)
        prev_path = f'/kod/generations/{current_gen_number - 1}'
        run(['btrfs', 'subvolume', 'move', current_gen, prev_path])
        
        # 4. Move temp_next → current
        run(['btrfs', 'subvolume', 'move', temp_next, current_gen])
        
        # 5. Copy state files
        for state_file in state_files:
            run(['cp', f'{prev_path}/{state_file}',
                      f'{current_gen}/{state_file}'])
        
        # 6. Success: cleanup backup
        run(['btrfs', 'subvolume', 'delete', backup_path])
        
    except Exception as e:
        # ROLLBACK: restore backup
        run(['btrfs', 'subvolume', 'move', backup_path, current_gen])
        raise e
```

**Key Properties:**
- Atomic: all-or-nothing
- Reversible: backup kept until success
- Ordered: dependencies respected (don't move current until moved next)

### `change_subvol()` (devices.lua)

**Lua Signature:**
```lua
function change_subvol(new_subvol)
    """Change active subvolume in fstab"""
    
    local fstab_path = '/etc/fstab'
    local content = read_file(fstab_path)
    
    -- Find line with subvol=...
    -- Replace with subvol=new_subvol
    
    write_file(fstab_path, updated_content)
end
```

**Modifies:** `/etc/fstab` (mount subvolume for /)

## Complete Call Sequence (Both Modes)

### Mode 1: `new_generation=False` (In-place rebuild) — DEFAULT

```
kod rebuild [--config CONFIG]          # CLI entry (kod.py:639)
├─ load_config_lua(config_path)        # Load config
├─ get current state from generation N # Read /kod/generations/N/installed_packages
├─ new_generation = False              # Use current system (kod.py:703-715)
├─   exec("btrfs subvolume snapshot / /kod/current/old-rootfs")  # Backup
├─   use_chroot = False                # No chroot (execute on host)
├─   new_root_path = "/"               # Modify current system
│
├─ plan_rebuild(...)                   # Compute package/service diffs
│  └─ build_plan(baseline='current')   # Only emit changed steps (planner.py:766)
│     └─ compose_steps_lua(...)        # Compose steps (planner.py:108)
│        ├─ packages.emit_steps()      # [IF PACKAGES CHANGED]
│        ├─ services.emit_steps()      # [IF SERVICES CHANGED]
│        └─ sort_steps()               # Sort by order
│
├─ execute_steps(steps, "/", use_chroot=False)  # Execute on host (executor.py:797)
│  └─ For each step:
│     ├─ run_shell(cmd)                # Execute directly (no chroot)
│     └─ Check return code, apply on_error policy
│
├─ store_packages_services(...)        # Write state
├─ generate_package_lock(...)          # Generate lock file
│
└─ ATOMIC SWAP (only because new_generation=False) -> kod.py:815
   ├─ _swap_generations_atomic(...)    # Atomic swap (kod.py:818)
   │  ├─ backup current generation     # snapshot current
   │  ├─ move next -> current          # Activate new generation
   │  ├─ move old current -> prev       # Keep as rollback
   │  └─ on failure: restore backup    # Rollback capability
   │
   └─ change_subvol()                  # Update /etc/fstab
      └─ Point root mount to new generation
```

### Mode 2: `new_generation=True` (Snapshot-based rebuild)

```
kod rebuild --new-generation [--config CONFIG]  # CLI entry (kod.py:639)
├─ load_config_lua(config_path)        # Load config
├─ new_generation = True               # Create snapshot (kod.py:703-715)
├─   exec("btrfs subvolume snapshot / /kod/generations/N+1/rootfs")
├─   use_chroot = True                 # Use chroot to snapshot
├─   new_root_path = "/kod/generations/N+1/rootfs"
│
├─ plan_rebuild(...)                   # Compute diffs (same as mode 1)
│  └─ build_plan(baseline='current')   # Only emit changed steps
│
├─ execute_steps(steps, "/kod/generations/N+1/rootfs", use_chroot=True)
│  └─ For each step:
│     └─ chroot /kod/generations/N+1/rootfs sh -c 'cmd'
│
├─ store_packages_services(...)        # Write state to N+1
├─ generate_package_lock(...)          # Generate lock in N+1
│
└─ NO SWAP (because new_generation=True) -> kod.py:836-837
   └─ exec(f"umount -R {new_root_path}")  # Unmount snapshot
      (Snapshot remains available at /kod/generations/N+1)
      (User can manually boot into it or compare with current)
```

```

## Diff Computation (Key Difference from Install)

```python
# Install: all packages from config
# Rebuild: only NEW packages
new_packages = set(config.packages)
current_packages = set(load_from_json('/kod/generations/N/installed_packages'))

packages_to_install = new_packages - current_packages
packages_to_remove = current_packages - new_packages

# Pass to build_plan()
build_plan(config, baseline='current', packages=packages_to_install)
```

## Error Handling

**Per-step policies:**
- `on_error: 'abort'` → Stop immediately, rollback
- `on_error: 'warn'` → Log warning, continue

**Rollback on failure:**
- Pre swap: rollback btrfs snapshot
- Post swap: can't rollback (system already uses new generation)
  - Manual: boot into previous generation and swap back

