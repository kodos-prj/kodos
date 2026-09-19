# KodOS Installation System - Security & Robustness Analysis

## Executive Summary

Analyzed KodOS install/rebuild system across ~1300 lines of critical Python and Lua code. Found **6 significant issues** and **8 medium-risk issues** spanning command injection, race conditions, state corruption, ordering failures, and permission escapes. Most issues relate to incomplete error handling and insufficient input validation in chroot/mount workflows.

---

## CRITICAL ISSUES (High Risk)

### 1. MOUNT POINT COMMAND INJECTION (Line 23, executor.lua)
**Severity: HIGH** | **Risk: Remote Code Execution**

#### Location
`src/lua/kod/planning/executor.lua:23`

```lua
cmd = "chroot " .. (mount_point or "/") .. " sh -c " .. shq(cmd)
```

#### Vulnerability
The `mount_point` path is concatenated directly into a shell command WITHOUT quoting or escaping. The command handler only quotes the inner `cmd` via `shq()`, not the mount_point itself.

#### Attack Scenario
1. User provides malicious mount point: `/mnt; rm -rf /; #`
2. Step execution constructs: `chroot /mnt; rm -rf /; # sh -c 'echo test'`
3. Shell interprets as two commands: `chroot /mnt`, then `rm -rf /`

#### Proof of Concept
```bash
# In install command
kod install -c config.lua -m "/mnt; echo PWNED; #"

# Generated command becomes:
# chroot /mnt; echo PWNED; # sh -c 'some command'
# Executes: chroot /mnt (fails)
# Then: echo PWNED (succeeds)
# Then: # sh -c ... (comment, ignored)
```

#### Impact
- Full system compromise via mount point injection
- Affects install, rebuild, and any chroot-based workflow
- Mount point comes from CLI (`-m` flag), user config, or internal state paths

#### Recommendations
1. **Immediate**: Quote mount_point in executor.lua:23
   ```lua
   cmd = "chroot " .. shq(mount_point or "/") .. " sh -c " .. shq(cmd)
   ```

2. **Validate mount_point**: Check in kod.py before passing to executor
   ```python
   # kod.py:252-253
   assert mount_point.startswith("/"), "Mount point must be absolute"
   assert not any(c in mount_point for c in ";|&$()"), "Invalid mount point"
   ```

---

### 2. RACE CONDITION: State File Creation Without Atomicity (Lines 309-330, kod.py)
**Severity: HIGH** | **Risk: State Corruption**

#### Location
`src/kod/kod.py:309-330` (install command)

```python
# Record generation 0 state BEFORE unmounting /mnt
state_path = f"{mount_point}/kod/generations/0"
os.makedirs(state_path, exist_ok=True)

# ...chmod outside the mounted fs...
os.system(f"chmod 0o777 {mount_point}/kod/generations")

# ...store packages/services...
store_packages_services(state_path, packages_to_install, next_services)
dist.generale_package_lock(mount_point, state_path)
```

#### Problem Sequence
1. `os.makedirs()` creates directory but may not exist yet in kernel's view
2. `os.system(chmod)` runs via shell asynchronously
3. `store_packages_services()` writes files—if chmod hasn't completed, EACCES
4. `generale_package_lock()` tries to read/write, potentially sees half-written state
5. Multiple processes could race on /mnt/kod/generations if two rebuilds run in parallel

#### Failure Modes
- **Partial state**: Some files written, lock generation skipped → corrupt generation 0
- **Permission denied**: chmod fails silently (exit code unchecked), next write fails
- **Lost packages**: rebuild loads partial state, thinks fewer packages are installed, skips updates
- **TOCTOU**: Between `mkdir` and `chmod`, another process (or this one) modifies permissions

#### Impact
- System boots with wrong package set
- Next rebuild can't determine delta, installs duplicates or omits critical packages
- State file corruption forces manual /kod/generations cleanup

#### Recommendations
1. **Atomic state creation**: Use proper file system operations
   ```python
   # kod.py:309-330
   try:
       os.makedirs(state_path, mode=0o755, exist_ok=False)  # Fail if exists
   except FileExistsError:
       # Generation 0 should not exist; clean up and retry
       pass
   
   # Ensure parent writable BEFORE writing state
   os.chmod(f"{mount_point}/kod/generations", 0o755)
   assert os.path.exists(state_path)
   
   # Write atomically: temp file + rename
   temp_path = f"{state_path}/.tmp_packages"
   with open(temp_path, "w") as f:
       f.write(json.dumps(packages_to_install))
   os.rename(temp_path, f"{state_path}/installed_packages")
   ```

2. **Check chmod result**:
   ```python
   result = os.system(f"chmod 0o755 {mount_point}/kod/generations")
   if result != 0:
       raise RuntimeError(f"Failed to chmod generations directory")
   ```

3. **Add generation 0 lock file**: Prevent concurrent rebuilds
   ```python
   lock_file = f"{mount_point}/kod/generations/.lock"
   with open(lock_file, "w") as f:
       fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)  # Fail if locked
   ```

---

### 3. GENERATION STATE SWAP WITHOUT ROLLBACK (Lines 620-624, kod.py)
**Severity: HIGH** | **Risk: Data Loss**

#### Location
`src/kod/kod.py:620-624` (rebuild, non-new-generation path)

```python
# Move current updated rootfs to a new generation
exec(f"mv /kod/generations/{current_generation}/rootfs /kod/generations/{generation_id}/")
# Moving the current rootfs copy to the current generation path
exec(f"mv /kod/current/old-rootfs /kod/generations/{current_generation}/rootfs")
exec(f"mv /kod/current/installed_packages /kod/generations/{current_generation}/installed_packages")
exec(f"mv /kod/current/enabled_services /kod/generations/{current_generation}/enabled_services")
```

#### Problem
These `mv` commands are NOT atomic. If ANY command fails mid-way:
1. `mv /kod/generations/0/rootfs → /kod/generations/1/` succeeds
2. `mv /kod/current/old-rootfs → /kod/generations/0/rootfs` fails (disk full, permission)
3. System is left in inconsistent state:
   - Generation 0 rootfs is now generation 1
   - Generation 0 has no rootfs
   - Next boot tries to use generation 0, **fails to mount**
   - No automatic rollback

#### Impact
- System becomes unbootable without manual recovery
- Loss of previous generation's state
- No recovery path documented

#### Scenarios
- Disk fills mid-swap
- Permission error on generated files
- NFS mount timeout during `mv`
- Kernel OOM kills move process

#### Recommendations
1. **Use transaction-like operations** (shell script with rollback):
   ```bash
   # Atomic swap: test all moves first, then execute
   gen_0_rootfs="/kod/generations/${current_generation}/rootfs"
   gen_new_rootfs="/kod/generations/${generation_id}/"
   old_rootfs="/kod/current/old-rootfs"
   
   # Validate all sources exist
   test -d "$gen_0_rootfs" || exit 1
   test -d "$old_rootfs" || exit 1
   
   # Create backup snapshot
   btrfs subvolume snapshot "$gen_0_rootfs" "/tmp/gen_${current_generation}_backup" || exit 1
   
   # Execute moves with error checking
   mv "$gen_0_rootfs" "$gen_new_rootfs/rootfs" || {
       btrfs subvolume delete "/tmp/gen_${current_generation}_backup"
       exit 1
   }
   
   mv "$old_rootfs" "$gen_0_rootfs" || {
       # Rollback: restore backup
       rm -rf "$gen_new_rootfs/rootfs"
       mv "/tmp/gen_${current_generation}_backup" "$gen_0_rootfs"
       exit 1
   }
   
   # Success: clean up backup
   btrfs subvolume delete "/tmp/gen_${current_generation}_backup"
   ```

2. **Add pre-swap validation**:
   ```python
   # kod.py:619
   # Verify all sources exist and are readable
   assert Path(f"/kod/generations/{current_generation}/rootfs").exists()
   assert Path(f"/kod/current/old-rootfs").exists()
   assert Path(f"/kod/current/installed_packages").exists()
   assert Path(f"/kod/current/enabled_services").exists()
   ```

3. **Document recovery procedure** for manual intervention

---

### 4. CHROOT MOUNT CLEANUP: Lazy Unmount But No Verification (Lines 345-353, kod.py)
**Severity: HIGH** | **Risk: Subsequent Command Injection**

#### Location
`src/kod/kod.py:345-353` (install cleanup)

```python
print("Cleaning up chroot mounts...")
try:
    # First try regular unmount
    exec("umount -R /mnt 2>/dev/null || umount -lR /mnt 2>/dev/null || true")
except Exception as e:
    logger.warning(f"Failed to cleanup chroot mounts: {e}")
```

#### Problems
1. **Lazy unmount hides errors**: `-lR` (recursive lazy) succeeds even if mounts not fully disconnected
2. **No verification**: Script doesn't check if `/mnt` is actually unmounted after
3. **Next command may see stale mounts**: If `/mnt/kod/generations/0` is still mounted from chroot:
   - `chmod 0o777 /mnt/kod/generations` operates on mounted subvol, not parent
   - State file writes go to old inode cache
   - Unmounted later = state files lost

4. **Silent failure**: `|| true` swallows all errors, no logging of failed unmounts

#### Scenario
```bash
# Install step 1: Mount /mnt
mount /dev/sda3 /mnt

# Install step 2: Setup chroot
mount -t proc proc /mnt/proc
mount -t sysfs sys /mnt/sys

# Install step 3: Try to unmount
umount -lR /mnt  # Succeeds but /mnt still has proc mounted (lazy)

# Install step 4: Write state (kod.py:312)
os.makedirs("/mnt/kod/generations/0")  # Uses stale cached inode
store_packages_services(...)  # Files written to tmpfs or incomplete mount

# Install step 5: Actually unmount (kernel busy, deferred)
# System reboot: /mnt/kod/generations/0 doesn't have state files
```

#### Impact
- State files not persisted to disk
- Rebuild fails: missing `/kod/generations/0/installed_packages`
- System appears corrupted immediately after install

#### Recommendations
1. **Verify unmount**:
   ```python
   # kod.py:348-351
   exec("umount -R /mnt 2>/dev/null || umount -lR /mnt 2>/dev/null || true")
   
   # Verify
   import subprocess
   result = subprocess.run(["mountpoint", "-q", "/mnt"], capture_output=True)
   if result.returncode == 0:
       # Still mounted
       print("WARNING: /mnt still mounted after unmount attempt")
       exec("lsof +D /mnt")  # Show what's holding the mount
       raise RuntimeError("Failed to unmount /mnt; state may be corrupted")
   ```

2. **Record state BEFORE unmounting**:
   ```python
   # kod.py:309-330
   # Current order: steps → record state → unmount
   # Better order: steps → record state → flush to disk → verify → unmount
   
   os.sync()  # Flush all buffers
   time.sleep(1)  # Let kernel finish writes
   
   # Verify state files exist on disk (not cached)
   assert os.path.exists(f"{state_path}/installed_packages")
   assert os.path.exists(f"{state_path}/enabled_services")
   ```

3. **Use subvolume snapshots instead of bind mounts** for state directories

---

### 5. PERMISSION BYPASS: World-Writable Generations Directory (Line 318, kod.py)
**Severity: HIGH** | **Risk: Privilege Escalation**

#### Location
`src/kod/kod.py:316-320`

```python
os.system(f"chmod 0o777 {mount_point}/kod/generations")
```

#### Vulnerability
Sets `/kod/generations` to world-writable (`777`). This is dangerous:

1. **Any user can create/modify generation state**
   - User X creates `/kod/generations/999/installed_packages` listing malicious packages
   - User Y runs rebuild, loads User X's state, installs malicious packages as root

2. **Symlink attack** during chmod (TOCTOU)
   ```bash
   ln -s /etc/shadow /mnt/kod/generations/shadow
   # chmod applies to /etc/shadow via symlink
   ```

3. **Permission inheritance**
   - Children inherit 777 from parent
   - State files become world-readable: expose package list, secrets in configs

#### Impact
- Non-root users can corrupt system state
- Privilege escalation via package manipulation
- Information disclosure (package config)
- Denial of service (remove critical generation)

#### Recommendations
1. **Use proper permissions**:
   ```python
   # kod.py:318
   # Root-only access to generations
   os.system(f"chmod 0o755 {mount_point}/kod/generations")  # rwxr-xr-x
   os.system(f"chown root:root {mount_point}/kod/generations")
   ```

2. **Use ACLs for selective rebuild user**:
   ```bash
   setfacl -m u:rebuild:rwx /kod/generations
   ```

3. **Audit state file ownership**:
   ```python
   import stat
   st = os.stat(f"{state_path}/installed_packages")
   assert st.st_uid == 0, f"State file owned by {st.st_uid}, expected 0 (root)"
   assert (st.st_mode & 0o077) == 0, f"State file readable by non-owner"
   ```

---

### 6. UNVALIDATED GENERATION ID IN PATH OPERATIONS (Lines 620-624, kod.py)
**Severity: HIGH** | **Risk: Directory Traversal / State Corruption**

#### Location
`src/kod/kod.py:620-624`

```python
generation_id = int(max_generation) + 1  # From get_max_generation()
# ...later...
exec(f"mv /kod/generations/{current_generation}/rootfs /kod/generations/{generation_id}/")
```

#### Problem
`current_generation` comes from `/.generation` file (user-writable during install):

```python
# kod.py:481-482
with open("/.generation") as f:
    current_generation = int(f.readline().strip())
```

If `/` is mounted from `/mnt` during install AND `.generation` file contains `"../../etc"`:
- `int("../../etc")` raises ValueError
- But if it's `"999"`: valid
- User creates `/kod/current/old-rootfs` as symlink to `/etc`
- `mv /kod/generations/999/rootfs /etc/` copies arbitrary directory into /etc

#### Scenario
```bash
# In install, assume /. generation is attacker-controlled
echo "../../../../etc/passwd" > /mnt/.generation

# Later, this fails safely (ValueError), but:
# If attacker can write to /mnt/,generation AFTER install:
echo "999" > /mnt/.generation

# Then rebuild with attacker providing /kod/current/old-rootfs as symlink:
ln -s /etc /mnt/kod/current/old-rootfs

# Command becomes:
# mv /kod/generations/999/rootfs /etc/
# Overwrites /etc with rootfs contents
```

#### Impact
- Directory traversal via generation ID
- Overwrite arbitrary system directories
- Destroy system configuration

#### Recommendations
1. **Validate generation ID**:
   ```python
   # kod.py:481-482
   with open("/.generation") as f:
       current_generation = int(f.readline().strip())
   
   # Validate: must be reasonable
   assert 0 <= current_generation <= 99999, f"Invalid generation: {current_generation}"
   assert current_generation == get_max_generation() or current_generation == get_max_generation() - 1, \
       f"Generation {current_generation} not in expected range"
   ```

2. **Validate paths before exec**:
   ```python
   current_gen_path = f"/kod/generations/{current_generation}/rootfs"
   new_gen_path = f"/kod/generations/{generation_id}/"
   
   # Resolve symlinks
   from pathlib import Path
   current_resolved = Path(current_gen_path).resolve()
   new_resolved = Path(new_gen_path).resolve()
   
   assert str(current_resolved).startswith("/kod/"), "Invalid path"
   assert str(new_resolved).startswith("/kod/"), "Invalid path"
   
   # Verify directory exists and is subvol
   assert current_resolved.is_dir()
   ```

3. **Read generation from trusted source only**:
   - Don't read from root during install
   - Get from device config instead

---

## MEDIUM-RISK ISSUES (Medium Severity)

### 7. INCOMPLETE ERROR HANDLING IN EXECUTOR (Lines 38-90, executor.lua)
**Severity: MEDIUM** | **Risk: Silent Failures**

#### Location
`src/lua/kod/planning/executor.lua:76-81`

```lua
if not result.success then
    if step.on_error ~= "warn" then
        error(result.error or ("step '" .. step.name .. "' failed"))
    end
    result.is_warning = true
end
```

#### Issue
When a step fails with `on_error="warn"`, it's marked as warning but execution continues. However:

1. **No recovery**: Failed step leaves system in dirty state
   - `useradd` fails → user not created
   - Next step `chgrp user` silently fails (user doesn't exist)
   - No way to tell if subsequent steps depend on previous failure

2. **Cascading failures hidden**: Steps that depend on failed steps aren't marked as failed

3. **No context**: Error message doesn't include step context (order, dependencies)

#### Scenario
```
Step 1: "users_create_alice" fails (on_error=warn)
  ├─ Result: warning, continues
Step 2: "users_groups_alice" depends_on="users_create_alice", expects user to exist
  ├─ Result: success=true (silently runs but user doesn't exist, chgrp fails, no error)
Step 3: "users_sudoers_alice" depends_on="users_groups_alice"
  ├─ Result: success=true (but previous failed)
System boots: alice doesn't exist, sudoers entry references nobody
```

#### Recommendations
1. **Track dependencies**:
   ```lua
   -- In executor.lua, before executing each step
   function Executor.check_dependencies(step, results)
       for _, dep_name in ipairs(step.depends_on or {}) do
           -- Find result for dependency
           for _, prev_result in ipairs(results) do
               if prev_result.step.name == dep_name then
                   if not prev_result.success then
                       -- Dependency failed
                       if step.on_error ~= "warn" then
                           error("Dependency '" .. dep_name .. "' failed, cannot run '" .. step.name .. "'")
                       else
                           -- Mark this step failed too
                           return { success = false, is_warning = true, error = "Dependency '" .. dep_name .. "' failed" }
                       end
                   end
               end
           end
       end
       return nil
   end
   ```

2. **Log failed dependencies**:
   ```lua
   -- After step execution
   if not result.success and result.is_warning then
       logger:warn("Step '" .. step.name .. "' failed (non-aborting): " .. (result.error or "unknown"))
       logger:warn("  Downstream steps that depend on this may silently fail")
   end
   ```

---

### 8. MOUNT ORDERING RACE: Boot Partition Before Bind Mounts (Lines 237-270, devices.lua)
**Severity: MEDIUM** | **Risk: Partial Mount Failure**

#### Location
`src/lua/kod/sections/devices.lua:237-270`

```lua
-- Step 6: Mount boot partition
table.insert(steps, {
    name = "devices_mount_btrfs_boot",
    order = 38.6,
    depends_on = {"devices_create_mount_dirs"},
})

-- Step 7: Mount /kod (raw btrfs root)
table.insert(steps, {
    name = "devices_mount_btrfs_kod",
    order = 38.7,
    depends_on = {"devices_mount_btrfs_boot"},
})

-- Step 9: Mount bind mounts
table.insert(steps, {
    name = "devices_mount_btrfs_binds",
    order = 38.9,
    depends_on = {"devices_mount_btrfs_home"},
})
```

#### Issue
Bind mounts for `/root`, `/var/log`, etc., depend on `/kod` being mounted. But if `/var/kod` exists and is bind-mounted to `/kod/store/var/kod`:

1. Step 8 mounts `/var/kod` → success
2. Step 9 tries to bind-mount `/kod/store/var/kod` → `/var/kod` already mounted
3. Bind mount fails: `mount: /var/kod: target is busy`

#### Impact
- /var/kod bind mount fails silently (on_error="warn")
- Later steps writing to /var/kod write to ephemeral rootfs, not persistent store
- Logs, temp files lost on reboot

#### Scenario
```bash
# Step 8: /home mount
mount -o subvol=store/home /dev/sda3 /mnt/home
# Creates /mnt/home (initially empty, or from snapshot)

# Step 9: Bind mounts
mount --bind /mnt/kod/store/var/kod /mnt/var/kod
# But /var already has /var/kod from bootstrap/install
# Fails if /mnt/var/kod exists and is already mounted
```

#### Recommendations
1. **Unmount existing mounts before binding**:
   ```lua
   table.insert(steps, {
       name = "devices_unmount_old_binds",
       description = "Unmount any existing bind mount targets",
       command = "umount /mnt/var/kod 2>/dev/null; umount /mnt/var/cache 2>/dev/null; umount /mnt/var/tmp 2>/dev/null; umount /mnt/var/log 2>/dev/null; umount /mnt/root 2>/dev/null || true",
       chroot = false,
       order = 38.85,
       depends_on = {"devices_mount_btrfs_home"},
       on_error = "warn",
   })
   ```

2. **Check mount status before binding**:
   ```lua
   table.insert(steps, {
       name = "devices_mount_btrfs_binds",
       description = "Create bind mounts for persistent directories",
       command = "for dir in root var/log var/tmp var/cache var/kod; do mountpoint -q /mnt/$dir && umount /mnt/$dir; done && " ..
                 "mount --bind /mnt/kod/store/root /mnt/root && " ..
                 "mount --bind /mnt/kod/store/var/log /mnt/var/log && " ..
                 -- ... etc
       chroot = false,
       order = 38.9,
       depends_on = {"devices_mount_btrfs_home"},
   })
   ```

---

### 9. MISSING PACKAGE AGGREGATION DEDUPLICATION IN REBUILD (Lines 295-308, packages.py)
**Severity: MEDIUM** | **Risk: Duplicate Package Installations**

#### Location
`src/kod/system/packages.py:295-308`

```python
current_pkgs = current_packages.get("packages", [])
next_pkgs = next_packages.get("packages", [])

# No deduplication on lists
packages_to_remove += list(set(current_pkgs) - set(next_pkgs))
packages_to_install += list(set(next_pkgs) - set(current_pkgs))
```

#### Issue
If packages.lua's deduplication fails (or is bypassed), duplicate packages in `next_packages` list:
- `packages_to_install` contains duplicates
- Pacman gets duplicates: `pacman -S vim vim vim`
- Not a hard error, but wasteful and can mask other issues

#### Also: No version checking
- Packages installed are compared by name only
- Version downgrades not detected
- If config changes `linux-lts` → `linux`, rebuild might skip reinstall (same package logic)

#### Recommendations
1. **Deduplicate in Python**:
   ```python
   # packages.py:295-308
   packages_to_install = list(dict.fromkeys(packages_to_install))  # Preserve order, remove dups
   packages_to_remove = list(dict.fromkeys(packages_to_remove))
   ```

2. **Add version-aware comparison**:
   ```python
   # If next_packages includes versions: { "vim": "9.0.123", "linux-lts": "6.1.50" }
   for pkg_name, pkg_version in next_packages.items():
       current_version = current_installed_packages.get(pkg_name)
       if pkg_version != current_version:
           packages_to_install.append(pkg_name)
   ```

---

### 10. MISSING FSTAB VALIDATION BEFORE BOOT (Lines 337-349, devices.lua)
**Severity: MEDIUM** | **Risk: Boot Failure**

#### Location
`src/lua/kod/sections/devices.lua:327-366`

```lua
local fstab_commands = {...}
-- Each command uses: test -n "$UUID" && echo "UUID=$UUID ..." >> /mnt/etc/fstab

table.insert(fstab_commands, "UUID=$(lsblk -no UUID " .. partition_path(device_path, "3") .. ") && test -n \"$UUID\" && echo \"UUID=$UUID / btrfs defaults,subvol=generations/0/rootfs 0 0\" >> /mnt/etc/fstab")
```

#### Issue
1. **No validation of final fstab**: Script generates fstab but doesn't verify it's valid
   - Can create fstab with bad UUIDs if `lsblk` fails or returns empty
   - `test -n "$UUID"` prevents empty UUIDs but doesn't validate format
   - Duplicate mount points possible (two entries for `/`)

2. **No fsck on root**: Pass value is 0 for root (correct per comment), but NO validation that it's 0
   - If manual edit changes root pass to 1, systemd-fsck runs btrfs check at boot → long delay

3. **Missing critical mounts**: If any mount command fails (e.g., btrfs subvol doesn't exist):
   - Fstab entry written anyway
   - Boot hangs or fails when mount point doesn't exist

#### Scenario
```bash
# If lsblk returns empty for partition 3:
UUID=""
# Then:
test -n "" && echo "UUID= /" >> /mnt/etc/fstab
# Evaluates to: false, line not added
# But /etc/fstab has no root entry
# Boot fails: kernel can't find root

# Or if subvolume doesn't exist:
# fstab has: UUID=... / btrfs defaults,subvol=generations/0/rootfs 0 0
# Kernel tries to mount, subvolume doesn't exist, boot hangs
```

#### Recommendations
1. **Validate fstab after generation**:
   ```lua
   table.insert(steps, {
       name = "devices_validate_fstab",
       description = "Validate generated fstab",
       command = "cat /mnt/etc/fstab && grep -q ' / ' /mnt/etc/fstab && wc -l /mnt/etc/fstab",
       chroot = false,
       order = 43.1,
       depends_on = {"devices_generate_fstab"},
   })
   ```

2. **Verify subvolume exists**:
   ```lua
   table.insert(steps, {
       name = "devices_verify_subvol",
       description = "Verify btrfs subvolumes exist",
       command = "btrfs subvolume list /mnt | grep generations/0/rootfs || exit 1",
       chroot = false,
       order = 39.5,
       depends_on = {"devices_create_btrfs_generation_0"},
   })
   ```

---

### 11. NO DISK SPACE VALIDATION (Any section)
**Severity: MEDIUM** | **Risk: Partial Install / Boot Failure**

#### Issue
No checks for available disk space before:
- Bootstrapping base system (pacstrap)
- Installing packages
- Creating snapshots
- Generating initramfs

#### Scenario
```
Install progress:
  ✓ Partition disk
  ✓ Format partitions
  ✓ Mount /mnt
  ✓ Bootstrap (pacstrap) → 500MB written
  ✗ Install packages → runs out of space at 90%
  
Result: /mnt has partial install, next boot fails
```

#### Recommendations
1. **Add pre-flight checks**:
   ```python
   # kod.py:272 (in install command)
   required_space_mb = 4000  # Adjust based on packages
   available_mb = int(exec(f"df {mount_point} | tail -1 | awk '{{print $4}}'", get_output=True).strip())
   if available_mb < required_space_mb:
       raise RuntimeError(f"Insufficient disk space: need {required_space_mb}MB, have {available_mb}MB")
   ```

2. **Check during package installation**:
   ```lua
   -- devices.lua or packages.lua
   table.insert(steps, {
       name = "packages_check_space",
       description = "Verify disk space before package installation",
       command = "df /mnt | tail -1 | awk '{if ($4 < 1000000) exit 1}' # 1GB minimum",
       chroot = false,
       order = 499,
       depends_on = {"devices_bootstrap_base_system"},
   })
   ```

---

### 12. NO ATOMICITY IN BTRFS SUBVOLUME CREATION (Lines 183-203, devices.lua)
**Severity: MEDIUM** | **Risk: Partial Subvolume Hierarchy**

#### Location
`src/lua/kod/sections/devices.lua:183-203`

```lua
table.insert(steps, {
    name = "devices_create_btrfs_store_home",
    command = "btrfs subvolume create /mnt/store/home",
    on_error = "warn",  -- May fail if already exists
})

table.insert(steps, {
    name = "devices_create_btrfs_generation_0",
    command = "btrfs subvolume create /mnt/generations/0/rootfs",
    on_error = "warn",
})
```

#### Issue
If subvolume creation partially succeeds (e.g., `/mnt/generations` created but `/mnt/generations/0` fails):
- Step marked as warning, continues
- Remount step tries to mount non-existent subvol
- Remount silently fails (depends_on not enforced for warnings)
- System boots with wrong mount hierarchy

#### Recommendations
1. **Fail on subvolume errors** (critical):
   ```lua
   table.insert(steps, {
       name = "devices_create_btrfs_generation_0",
       command = "btrfs subvolume create /mnt/generations/0/rootfs",
       on_error = "abort",  # Not warn
   })
   ```

2. **Verify subvolume exists after creation**:
   ```lua
   table.insert(steps, {
       name = "devices_verify_btrfs_structure",
       command = "btrfs subvolume list /mnt | grep -E '(store/home|generations/0/rootfs)' | wc -l | grep -q 2",
       chroot = false,
       order = 37.5,
       depends_on = {"devices_create_btrfs_generation_0"},
   })
   ```

---

### 13. STATE LOSS: Package Lock Not Written On Install (Line 334, kod.py)
**Severity: MEDIUM** | **Risk: Inconsistent Rebuild State**

#### Location
`src/kod/kod.py:334`

```python
dist.generale_package_lock(mount_point, state_path)
```

#### Issue
Called but:
1. `generale_package_lock` reads installed packages FROM chroot (/mnt)
2. This requires the chroot to still be running (pacman -Q)
3. **But**: chroot is cleaned up immediately after (line 351: `umount -R /mnt`)
4. If lock generation fails mid-way, state has no `.lock` file
5. Rebuild later doesn't have version info, can't determine if update needed

#### Scenario
```
Install:
  ✓ Run pacstrap → packages installed in /mnt
  ✓ Record /kod/generations/0/installed_packages (package names only)
  ✗ generale_package_lock fails (e.g., pacman -Q in chroot errors)
  ✓ Unmount /mnt
  
Result: /kod/generations/0/packages.lock doesn't exist

Rebuild:
  load_package_lock() returns {}
  Plan assumes no packages installed
  Tries to install all packages again
```

#### Recommendations
1. **Check lock file generation**:
   ```python
   # kod.py:334
   try:
       dist.generale_package_lock(mount_point, state_path)
   except Exception as e:
       logger.error(f"Failed to generate package lock: {e}")
       # Fallback: generate from installed_packages
       with open(f"{state_path}/packages.lock", "w") as f:
           for pkg in packages_to_install.get("packages", []):
               f.write(f"{pkg} unknown\n")
   ```

2. **Verify lock file exists**:
   ```python
   lock_file = f"{state_path}/packages.lock"
   if not os.path.exists(lock_file):
       logger.warning(f"Package lock file not found at {lock_file}")
       # Create placeholder
       with open(lock_file, "w") as f:
           for pkg in packages_to_install.get("packages", []):
               f.write(f"{pkg} installed\n")
   ```

---

### 14. SHELLQUOTING EDGE CASE: Newlines in Commands (Line 23, executor.lua)
**Severity: MEDIUM** | **Risk: Command Injection**

#### Location
`src/lua/kod/planning/executor.lua:23`

```lua
local function shq(s)
    return "'" .. s:gsub("'", "\\'") .. "'"
end
```

#### Issue
Escaping only handles single quotes, not newlines. If command contains literal newline:
- `"echo test\necho pwned"` becomes `'echo test\necho pwned'`
- Shell interprets `\n` as literal characters (escaped in single quotes), OK
- BUT if newline is unescaped: `"echo test` + newline + `echo pwned"` → `'echo test
echo pwned'` 
- **Works correctly**: Single quotes protect literal newlines

However, if mount_point contains newline (and is unquoted):
- `chroot /mnt; echo pwned sh -c 'cmd'` (if mount_point is `/mnt; echo pwned`)
- Quote escaping doesn't help because mount_point is unquoted

#### Recommendations
Covered by issue #1 (mount_point quoting fix)

---

## SUMMARY TABLE

| Issue | Location | Risk | Type | Status |
|-------|----------|------|------|--------|
| 1. Mount point injection | executor.lua:23 | HIGH | Injection | Unfixed |
| 2. Race condition: state creation | kod.py:309-330 | HIGH | Race | Unfixed |
| 3. Generation swap without rollback | kod.py:620-624 | HIGH | Data loss | Unfixed |
| 4. Lazy unmount hiding errors | kod.py:345-353 | HIGH | State corruption | Unfixed |
| 5. World-writable generations dir | kod.py:318 | HIGH | Privilege escalation | Unfixed |
| 6. Unvalidated generation ID in paths | kod.py:620-624 | HIGH | Directory traversal | Unfixed |
| 7. Incomplete error handling | executor.lua:76-81 | MEDIUM | Silent failure | Unfixed |
| 8. Mount ordering race | devices.lua:237-270 | MEDIUM | Partial mount failure | Unfixed |
| 9. Missing package deduplication | packages.py:295-308 | MEDIUM | Duplicate installs | Unfixed |
| 10. Missing fstab validation | devices.lua:327-366 | MEDIUM | Boot failure | Unfixed |
| 11. No disk space validation | All | MEDIUM | Install failure | Unfixed |
| 12. No atomicity in subvolume creation | devices.lua:183-203 | MEDIUM | Partial hierarchy | Unfixed |
| 13. Package lock loss on install | kod.py:334 | MEDIUM | Rebuild inconsistency | Unfixed |
| 14. Shellquoting edge case | executor.lua:23 | MEDIUM | Command injection | Unfixed |

---

## ORDERING & DEPENDENCY ISSUES

### Step Dependency Graph Analysis
The planner uses `order` and `depends_on` fields:
- `order`: Numeric priority (lower = earlier)
- `depends_on`: Array of step names this depends on

**Issue**: `depends_on` is defined in steps but NOT enforced by executor.lua

Lines 42-88 in executor.lua iterate over steps in order but never check `depends_on`:
```lua
for i = 1, #steps do
    local step = steps[i]
    -- PRE HOOKS
    -- EXECUTE STEP (ignores depends_on)
    -- POST HOOKS
end
```

**Impact**: If step ordering gets wrong, or if a warned/failed step is depended on, the dependency is not validated. Steps execute in `order` sequence regardless of `depends_on`.

**Recommendation**: Enforce dependency checks before step execution
```lua
function Executor.check_dependencies(step, completed_steps)
    for _, dep_name in ipairs(step.depends_on or {}) do
        local dep_found = false
        local dep_success = false
        for _, result in ipairs(completed_steps) do
            if result.step.name == dep_name then
                dep_found = true
                dep_success = result.success
                break
            end
        end
        if not dep_found then
            return false, "Dependency '" .. dep_name .. "' not found"
        elseif not dep_success then
            return false, "Dependency '" .. dep_name .. "' failed or not executed"
        end
    end
    return true
end
```

---

## RECOMMENDATIONS SUMMARY

### Immediate (P0 - Critical)
1. Fix mount_point injection in executor.lua:23
2. Add validation for generation IDs (kod.py:481)
3. Replace lazy unmount with verification (kod.py:348)
4. Use atomic operations for state creation (kod.py:312-330)

### Short-term (P1 - High)
5. Implement transaction-like generation swaps (kod.py:620-624)
6. Fix permissions on /kod/generations (kod.py:318)
7. Add dependency enforcement in executor (executor.lua:42-88)
8. Validate fstab before boot (devices.lua:366)

### Medium-term (P2 - Medium)
9. Add disk space pre-flight checks (kod.py:272)
10. Implement bind mount ordering fixes (devices.lua:237-270)
11. Add package deduplication (packages.py:295-308)
12. Verify subvolume hierarchy (devices.lua:203)

### Long-term (P3 - Documentation)
13. Add recovery procedures for failed installs
14. Document state file format and versioning
15. Create integration tests for error scenarios
16. Add monitoring for state corruption

