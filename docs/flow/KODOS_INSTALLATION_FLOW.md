# KodOS Installation & Rebuild Flow Analysis

## Overview
KodOS uses a multi-phase architecture with Lua sections (configuration builders) feeding into Python orchestration layers. The flow separates **planning** (step composition) from **execution** (running those steps).

---

## 1. MAIN ENTRY POINTS

### CLI Commands (src/kod/kod.py)

| Command | Function | Stage | Line | Baseline |
|---------|----------|-------|------|----------|
| `kod install` | Full install from scratch | install | 427 | "empty" |
| `kod rebuild` | In-system rebuild | rebuild | 639 | "current" |
| `kod plan` | Dry-run preview | plan | 616 | "empty" or "current" |
| `kod rebuild-user` | User-only config update | rebuild-user | 851 | "current" |
| `kod config validate` | Config validation | validate | 347 | N/A |

---

## 2. INSTALL FLOW (Full System)

### Phase 1: Configuration Loading
```
kod install [--config FILE] [--mount_point MOUNT]
  └─> load_config(config)  [kod.py:436]
       └─> load_config_lua()  [config/loader.py] → returns Lua table
            └─> Parses .lua config file → Python object wrapper
```

### Phase 2: Plan Composition
```
build_plan(conf, dist, baseline="empty")  [planner.py:463]
  └─> plan_install(conf)  [planner.py:394]
       └─> compose_steps_lua(config, distro)  [planner.py:108]
            ├─> lua = get_lua_runtime()  [lua_runtime.py]
            ├─> Load: "kod.planning.planner" module
            └─> planner_module.compose(config_lua, distro)  [planning/planner.lua:140]
                 └─> For each section in sections list (devices, boot, packages, services, users, ...):
                      ├─> load_section(section_name)  [planning/planner.lua:18]
                      │    └─> lua.require('kod.sections.' + section_name)
                      ├─> section.emit_steps(config[section] or config, distro)
                      │    └─> Returns list of step tables with: {kind, name, program, args, order, ...}
                      └─> Collect all steps
                 └─> sort_steps(all_steps)  [planning/planner.lua:38]
                      └─> Sort by order field, handle dependencies
                 └─> Return: list of Python Step objects
```

**Section Modules** (src/lua/kod/sections/)
| Section | Purpose | Key Output |
|---------|---------|-----------|
| devices.lua | Disk partitioning, formatting, mounting | disk wipe/format/mount steps |
| boot.lua | Boot loader setup | boot-entry, kernel-update steps |
| base_distribution.lua | Distro-specific base config | base distribution metadata |
| packages.lua | System package aggregation & installation | package install/AUR/flatpak steps |
| services.lua | Service enablement | systemctl enable steps |
| users.lua | User account creation | useradd steps |
| desktop.lua | DE/display manager setup | desktop environment steps |
| repos.lua | Repository configuration | repo metadata steps |
| programs.lua | Global system programs | program installation steps |

### Phase 3: Execution Setup
```
execute_steps(steps, env, mount_point, use_chroot=True, hooks=hooks_dict)  [executor.py:36]
  ├─> env dict with:
  │    ├─> mount_point: "/mnt"
  │    ├─> use_chroot: true
  │    ├─> stage: "install"
  │    ├─> dist: distro module
  │    └─> callbacks: {
  │         "kernel-update": lambda (kernel, mp) → update_kernel_hook(),
  │         "initramfs-update": lambda (kernel, mp) → update_initramfs_hook(),
  │         "boot-entry": lambda (kernel, mp) → create_boot_entry_hook(0, kernel, mp)
  │       }
  ├─> hooks_dict: collected from users section (program pre/post hooks)
  └─> Calls: lua.require("kod.planning.executor")
       └─> module.run(steps_lua, ctx_lua, dispatch_lua, hooks_lua)  [planning/executor.lua:40]
            ├─> For each step in order:
            │    ├─> Fire pre:<kind> hooks
            │    ├─> Execute based on kind:
            │    │    ├─> if (program or command) → run_shell(step)
            │    │    │    └─> Wrap in chroot if step.chroot=true
            │    │    │    └─> Guard with timeout
            │    │    │    └─> os.execute() via lupa
            │    │    ├─> elif kind="system/package/service" → dispatch.step(step, ctx)
            │    │    │    └─> Python callback from env
            │    │    └─> else → metadata-only no-op
            │    ├─> Apply on_error policy (abort|warn)
            │    └─> Fire post:<kind> hooks
            └─> Return: array of StepResult with success/error
```

### Phase 4: Post-Install Finalization
```
store_packages_services(state_path, packages_to_install, next_services)  [packages.py]
  └─> Writes JSON files:
       ├─> /kod/generations/0/installed_packages
       └─> /kod/generations/0/enabled_services

dist.generate_package_lock(mount_point, state_path)  [distro adapter]
  └─> Creates: /kod/generations/0/packages.lock
       └─> JSON: {package_name: version, ...}

Cleanup chroot mounts:
  └─> umount -R /mnt  (proc, sys, dev, dev/pts, etc.)
```

---

## 3. PACKAGE HANDLING FLOW

### 3a. Package Aggregation (Lua)
```
packages.lua:aggregate_all_packages(config)  [packages.lua:218]
  ├─> aggregate_base_packages(config)
  ├─> aggregate_desktop_packages(config)
  │    └─> Scan config.desktop.environments[*].enable
  │    └─> Add desktop environment + extra_packages
  ├─> aggregate_hardware_packages(config)
  │    └─> Scan config.hardware[*].enable
  ├─> aggregate_system_packages(config)
  │    └─> config.packages list
  ├─> aggregate_font_packages(config)
  ├─> aggregate_global_program_packages(config)
  │    └─> config.programs[*].enable
  ├─> aggregate_user_program_packages(config)
  │    └─> config.users[*].programs[*].enable
  │    └─> config.users[*].services[*].enable
  └─> deduplicate_packages()
       └─> Remove duplicates, preserve order
       └─> Return: list of package names with prefixes
```

### 3b. Package Type Separation (Lua)
```
packages.lua:separate_packages(packages)  [packages.lua:260]
  ├─> normal_pkgs: no prefix (e.g., "vim", "base-devel")
  │    └─> Install via: pacman -S --noconfirm --needed
  ├─> aur_pkgs: "aur:" prefix (e.g., "aur:yay", "aur:some-git-pkg")
  │    └─> Stripped prefix (e.g., "yay", "some-git-pkg")
  │    └─> Install via: yay -S --noconfirm (after building yay)
  └─> flatpak_pkgs: "flatpak:" prefix (e.g., "flatpak:org.gnome.Evolution")
       └─> Stripped prefix
       └─> Install via: flatpak install
```

### 3c. Install Step Emission (Arch)
```
packages.lua:emit_steps(config, "arch")  [packages.lua:295]
  
  Step 1: Install normal packages + base-devel (if AUR packages exist)
    Name: "packages_install_normal_and_base"
    Command: pacman -S --noconfirm --needed [normal_pkgs...] [base-devel] [git]
    Order: 490
    Chroot: true
  
  Step 1.5: Create kod user (if AUR packages exist)
    Name: "packages_create_kod_user"
    Command: useradd -r -m -s /bin/bash kod 2>/dev/null || true
    Order: 492
    Depends: ["packages_install_normal_and_base"]
  
  Step 1.6: Add kod to sudoers
    Name: "packages_kod_sudoers"
    Command: echo 'kod ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers.d/kod
    Order: 493
    Depends: ["packages_create_kod_user"]
  
  Step 1.7: Build yay (AUR helper)
    Name: "packages_build_yay_helper"
    Command: cd /tmp && git clone ... && chown -R kod:kod && cd yay-bin && sudo -u kod makepkg -si --noconfirm
    Order: 494
    Timeout: 900s
    Depends: ["packages_kod_sudoers"]
  
  Step 2+: Build each AUR package
    Name: "packages_build_aur_{aur_pkg}"
    Command: sudo -u kod yay -S --noconfirm --needed 'pkg'
    Order: 500 + i
    Timeout: 900s per package
    Depends: ["packages_build_yay_helper"]

For Debian:
  Single step:
    Name: "packages_install_normal"
    Command: apt-get install -y [normal_pkgs...]
    Order: 500
    Chroot: true
```

### 3d. Python Integration
```
get_packages_to_install(conf)  [packages.py:98]
  ├─> lua = get_lua_runtime()
  ├─> Load: "kod.sections.packages" module
  ├─> conf_lua = _convert_to_lua_table(lua, conf)
  ├─> lua_packages = packages_module.aggregate_packages(conf_lua)
  ├─> packages_list = lua_table_to_python(lua_packages)
  └─> Return: {
       "packages": [list of all packages],
       "kernel": "linux"
      }

manage_packages_shell()  [packages.py]
  └─> Fallback shell interface (schroot, chroot sandbox)
```

---

## 4. REBUILD FLOW (Incremental Update)

### Phase 1: State Loading
```
_load_current_state()  [kod.py:593]
  ├─> Read: /.generation (current generation number)
  ├─> Load: /kod/generations/{gen}/installed_packages (JSON)
  ├─> Load: /kod/generations/{gen}/enabled_services (JSON)
  ├─> Load: /kod/generations/{gen}/packages.lock (JSON, if exists)
  └─> Return: (state_path, current_packages, current_services, installed_lock)
```

### Phase 2: Generation Preparation
```
if new_generation:
  ├─> max_generation = get_max_generation()  [generations.py]
  │    └─> Find max numeric subdir in /kod/generations/
  ├─> generation_id = max_generation + 1
  ├─> exec(f"btrfs subvolume snapshot / {next_state_path}/rootfs")
  │    └─> Create snapshot of current root filesystem
  ├─> create_next_generation(boot_partition, root_partition, generation_id)  [generations.py]
  │    └─> Clone boot partition to generation
  │    └─> Mount new generation rootfs at {new_root_path}
  └─> setup_chroot_mounts(new_root_path)
       └─> Mount proc, sys, dev, dev/pts in chroot
else:
  ├─> exec("btrfs subvolume snapshot / /kod/current/old-rootfs")
  │    └─> Snapshot for rollback
  ├─> Copy current generation state files to /kod/current/
  └─> new_root_path = "/"  (in-place modification)
```

### Phase 3: Repository Processing
```
dist.proc_repos(conf, current_repos, update, mount_point)  [distro adapter]
  ├─> Load current repos from /var/kod/repos.json
  ├─> Process config.repos:
  │    ├─> For each repo: add/remove/update per config
  │    └─> Mark AUR vs normal repos
  ├─> For AUR repos: ensure kod user exists
  └─> Return: (repos, repo_packages)

if update:
  └─> dist.refresh_package_db(new_root_path, new_generation)
       └─> Arch: pacman -Sy
       └─> Debian: apt-get update
```

### Phase 4: Plan Composition (Diff-based)
```
current_installed_packages = load_package_lock(current_state_path)

build_plan(conf, dist, baseline="current",
           current_packages=cur_pkgs,
           current_services=cur_svcs,
           current_installed_packages=cur_lock,
           update=update,
           new_generation=new_generation)
  └─> plan_rebuild(conf, dist, ...)  [planner.py:407]
       ├─> next_packages, remove_packages = get_packages_to_install(conf)
       ├─> next_services = get_services_to_enable(ctx, conf)
       ├─> kernel_update_required = dist.kernel_update_required(
       │    current_kernel, next_kernel, installed_lock, mount_point)
       │    └─> Compare installed package versions with new kernel
       └─> compose_rebuild_steps_lua({
            "next_packages": {...},
            "current_packages": {...},
            "remove_packages": [...],
            "next_services": [...],
            "current_services": [...],
            "update": bool,
            "new_generation": bool,
            "kernel_update_required": bool,
            "config": conf_lua
           })  [planner.py:187]
            └─> lua.require("kod.planning.rebuild")
                 └─> module.diff(state_lua)  [planning/rebuild.lua:41]
                      ├─> Compute: removed services
                      │    └─> sorted_diff(current_services, next_services)
                      │    └─> Emit: systemctl disable --now
                      ├─> Configure dracut if kernel update
                      ├─> Compute: removed packages
                      │    └─> sorted_diff(current_packages, next_packages)
                      │    └─> Emit: pacman -R / apt-get remove
                      ├─> Compute: installed packages
                      │    └─> sorted_diff(next_packages, current_packages)
                      │    └─> Call: Packages.emit_steps(config, distro)
                      │    └─> Emit: install steps (normal/aur/flatpak)
                      ├─> If kernel_update_required:
                      │    └─> Emit: kernel-update, initramfs-update
                      ├─> Compute: new services
                      │    └─> sorted_diff(next_services, current_services)
                      │    └─> Emit: systemctl enable [--now]
                      └─> Emit: boot-entry
```

### Phase 5: Execution
```
execute_steps(steps, env, new_root_path, use_chroot)  [executor.py:36]
  └─> (same as install: shell execution, hook firing, on_error policy)
```

### Phase 6: State Update & Generation Swap
```
next_services = get_services_to_enable(ctx, conf)
packages_to_install, _ = get_packages_to_install(conf)
store_packages_services(next_state_path, packages_to_install, next_services)
dist.generate_package_lock(new_root_path, next_state_path)

if not new_generation:
  └─> _swap_generations_atomic(current_generation, generation_id)  [kod.py:156]
       ├─> Validate generation IDs
       ├─> Create btrfs snapshot backup: current_rootfs → backup_path
       ├─> Move rootfs: current_rootfs → new_gen_dir/rootfs
       ├─> Move old rootfs: old_rootfs → current_rootfs
       ├─> Move state files: /kod/current/{installed_packages,enabled_services} → /kod/generations/{current_gen}/
       ├─> On success: rm backup_path
       └─> On failure: rollback all moves from backup
  
  └─> Update boot config:
       └─> partition_list = load_fstab("/")
       └─> change_subvol(partition_list, subvol=f"generations/{generation_id}", mount_points=["/"])
       └─> generate_fstab(updated_partition_list, new_root_path)

if new_generation:
  └─> umount -R new_root_path

Write generation marker:
  └─> echo generation_id > /kod/generations/{generation_id}/rootfs/.generation
```

---

## 5. LUA-PYTHON INTEGRATION ARCHITECTURE

### Lua Runtime Singleton
```
lua_runtime.py:get_lua_runtime()  [lua_runtime.py]
  └─> Returns: persistent Lua state (created once per session)
  └─> Allows: mixed Python/Lua execution without "different Lua runtime" errors
```

### Data Conversion
```
_convert_to_lua_table(lua, python_value)  [bootstrap.py:20]
  ├─> dict → lua.table() with key-value pairs
  ├─> list → lua.table() with integer keys (1-indexed)
  ├─> object.__dict__ → lua.table()
  └─> scalar → pass through

lua_table_to_python(lua_table)  [lua_utils.py]
  ├─> lua.table() → dict or list
  └─> Handles 1-indexed Lua arrays → 0-indexed Python lists
```

### Module Loading
```
lua.require("kod.sections.packages")
  └─> lupa automatically:
       ├─> Searches package.path
       ├─> Loads .lua file
       ├─> Executes Lua code
       └─> Returns: (module_table, filename) tuple

Step conversion (lua_step → Python Step):
  └─> _convert_lua_step_to_step(lua_step)  [planner.py:52]
       └─> Extract: kind, name, program, args, chroot, timeout_s, on_error, meta
       └─> Convert: lua.table args/meta → Python tuple/dict
       └─> Return: Step(kind, name, program, args, ...)
```

---

## 6. SERVICE & SYSTEM CONFIGURATION FLOW

### Service Aggregation (Lua)
```
services.lua:aggregate_services(config)  [services.lua]
  ├─> From config.services[*].enable
  ├─> From config.desktop.*.services[*].enable
  ├─> From config.programs[*].services[*].enable
  ├─> From config.users[*].services[*].enable
  └─> Return: sorted list of service names
```

### Service Enablement
```
For install:
  └─> systemctl enable {service}  (chrooted, no --now)

For rebuild (new_generation=true):
  └─> systemctl enable {service}  (chrooted, no --now)

For rebuild (new_generation=false, in-place):
  └─> systemctl enable --now {service}  (on current system)

For removal (rebuild only):
  └─> systemctl disable --now {service}
```

### System Hooks (Boot, Kernel, Initramfs)
```
update_kernel_hook(kernel, mount_point)  [system/boot.py]
  └─> Detects installed kernel
  └─> Copies kernel image to /boot/vmlinuz-{version}

update_initramfs_hook(kernel, mount_point)  [system/boot.py]
  └─> Runs dracut to regenerate initramfs
  └─> Copies to /boot/initramfs-{version}.img

create_boot_entry_hook(generation_id, kernel, mount_point)  [system/boot.py]
  └─> Creates EFI boot entry via efibootmgr
  └─> Or GRUB entry (distro-dependent)
  └─> Links to /boot/vmlinuz-{version}, /boot/initramfs-{version}.img
```

---

## 7. DISTRO-SPECIFIC PACKAGE FLOW

### Distro Adapter Interface
```
get_distro_module(distro_name)  [distro/factory.py]
  ├─> "arch" → Arch()  [distro/adapters/arch.py]
  └─> "debian" → Debian()  [distro/adapters/debian.py]

DistroAdapter abstract methods:
  ├─> proc_repos(conf, current_repos, update, mount_point)
  ├─> refresh_package_db(mount_point, new_generation)
  ├─> kernel_update_required(current_kernel, next_kernel, installed_lock, mount_point)
  ├─> get_kernel_file(mount_point, kernel_package)
  ├─> query_installed_packages(mount_point)
  └─> generate_package_lock(mount_point, state_path)
```

### Arch-Specific Flow
```
Arch.proc_repos(conf, ...)  [adapters/arch.py]
  ├─> Parse conf.repos: {repo_name: {url, packages, build: [], enabled}}
  ├─> For each repo:
  │    ├─> If build=[]: AUR packages → require kod user + yay
  │    ├─> Else: normal packages → pacman repo (arch/community/extra)
  └─> Return: (repos_dict, repo_packages_dict)

Arch.query_installed_packages()
  └─> Run: pacman -Q --upgradable
  └─> Parse: "pacman -Qi {kernel}" for version

Arch.generate_package_lock()
  └─> Run: pacman -Q > {state_path}/packages.lock
  └─> JSON: {pkg_name: version, ...}
```

### Debian-Specific Flow
```
Debian.proc_repos(conf, ...)  [adapters/debian.py]
  ├─> Parse conf.repos: {repo_name: {ppa, components, ...}}
  ├─> No AUR equivalent (skip yay/makepkg)
  ├─> Normal packages → apt repositories
  └─> Return: (repos_dict, {})

Debian.query_installed_packages()
  └─> Run: dpkg -l | grep '^ii'
  └─> Parse: "apt-cache policy {kernel}"

Debian.generate_package_lock()
  └─> Run: dpkg -l | grep '^ii' > {state_path}/packages.lock
```

---

## 8. USER & DOTFILES CONFIGURATION FLOW

### User Creation (Lua sections)
```
users.lua:emit_steps(config.users, distro)  [sections/users.lua]
  ├─> For each user in config.users:
  │    ├─> Emit: useradd -m -G wheel -s /bin/bash {user}
  │    ├─> If home_password: Emit: passwd {user}
  │    ├─> If enable_sudo: Emit: usermod -aG wheel {user}
  │    └─> Emit: mkdir -p /home/{user}/{.config,Documents,...}
  └─> Return: steps list
```

### Dotfiles Sync
```
dotfiles.lua:emit_steps(config.dotfiles, distro)  [sections/dotfiles.lua]
  ├─> For each dotfile source:
  │    ├─> rsync, git clone, or copy
  │    └─> Set permissions
  └─> Emit: shell steps to sync/install dotfiles
```

### User-Level Services
```
User services in config.users[user].services[*]:
  ├─> Emit: systemctl --user enable {service}  (as user context)
  └─> Emit: systemctl --user start {service}  (if needed)

System-level services for user context:
  ├─> e.g., "bluetooth" for user device access
  └─> Emit: systemctl enable {service}  (system-wide)
```

---

## 9. ERROR HANDLING & ROLLBACK

### On-Error Policies
```
Step.on_error:
  ├─> "abort": Step failure stops entire plan, raises StepError
  ├─> "warn": Step failure logs warning but continues plan
```

### Generation Rollback
```
If rebuild fails during execution:
  └─> _cleanup_failed_generation(generation_id, new_root_path)  [kod.py:554]
       ├─> Unmount new_root_path
       ├─> btrfs subvolume delete {generation_path}/rootfs
       ├─> btrfs subvolume delete {generation_path}/boot  (if exists)
       └─> rm -rf {generation_path}
```

### Atomic Generation Swap Failure
```
If _swap_generations_atomic fails:
  ├─> Step 2 failed → current_rootfs still in place (no rollback needed)
  ├─> Step 3 failed → restore current_rootfs from new_gen_dir (rollback)
  ├─> Step 4 failed → restore both rootfs AND old_rootfs (complex rollback)
  └─> Raises RuntimeError with context for manual recovery
```

---

## 10. CONFIGURATION SCHEMA FLOW

### Lua-Driven Schema
```
config/schema.py:get_lua_schema()  [config/schema.py]
  └─> Loads Lua schema definitions from kod.core.schema
  └─> Returns: nested dict with all section docs

config validate:
  └─> validate_config(conf)  [config/validator.py]
       ├─> Check required fields per section
       ├─> Validate field types and enum values
       └─> Return: list of error strings or []
```

---

## 11. KEY DATA STRUCTURES

### Step (Python)
```python
@dataclass(frozen=True)
class Step:
    kind: str           # "disk", "system", "package", "service", "user"
    name: str           # "packages_install_normal", "useradd_bob"
    program: str        # "pacman", "useradd", "systemctl"
    args: tuple         # ("-S", "--noconfirm", "vim")
    chroot: bool        # True if runs inside chroot
    timeout_s: int      # 300, 600, 900
    on_error: str       # "abort" or "warn"
    meta: dict          # {kernel: "linux", order: 490, depends_on: [...]}
```

### Generated State Files
```json
// /kod/generations/{gen}/installed_packages
{
  "packages": ["base", "linux", "grub", ...],
  "kernel": "linux"
}

// /kod/generations/{gen}/enabled_services
["systemd-networkd", "sshd", ...]

// /kod/generations/{gen}/packages.lock
{
  "linux": "6.1.42-1",
  "base": "3-1",
  "vim": "9.0.1234-1",
  ...
}
```

---

## 12. EXECUTION ORDER (Install Phase)

1. Load config (Lua)
2. Compose steps:
   - devices → wipe/partition/format/mount steps
   - boot → bootloader setup
   - base_distribution → distro defaults
   - repos → repository config
   - hardware → hardware packages
   - packages → install normal/aur/flatpak (with yay build for AUR)
   - services → systemctl enable
   - users → useradd
   - dotfiles → config sync
   - desktop → DE/display manager
   - fonts → font installation
   - locale → locale setup
   - network → network config
3. Execute steps (chrooted, with hooks)
4. Record generation 0 state
5. Cleanup chroot mounts
6. Return success

---

## 13. EXECUTION ORDER (Rebuild Phase)

1. Load current state (generation marker, installed packages, enabled services)
2. Create new generation (btrfs snapshot or in-place prepare)
3. Process repos (proc_repos)
4. Compute differences:
   - Packages to remove (current - next)
   - Packages to install (next - current)
   - Services to disable (current - next)
   - Services to enable (next - current)
5. Compose rebuild steps:
   - Disable removed services
   - Configure dracut if kernel update
   - Remove old packages
   - Install new packages (normal/aur/flatpak)
   - Kernel & initramfs update
   - Enable new services
   - Create/update boot entries
6. Execute steps
7. Store generation state (packages, services, lock file)
8. Swap generations (atomic with rollback)
9. Update boot config
10. Return success

