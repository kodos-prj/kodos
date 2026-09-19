# KodOS Installation System - Critical Issues Quick Reference

## 6 CRITICAL ISSUES (HIGH RISK)

### 1️⃣ MOUNT POINT COMMAND INJECTION (executor.lua:23)
**Fix Priority: IMMEDIATE**
```lua
# VULNERABLE:
cmd = "chroot " .. (mount_point or "/") .. " sh -c " .. shq(cmd)

# FIXED:
cmd = "chroot " .. shq(mount_point or "/") .. " sh -c " .. shq(cmd)
```
**Impact**: RCE via `-m "/mnt; rm -rf /; #"`

---

### 2️⃣ RACE CONDITION IN STATE CREATION (kod.py:309-330)
**Fix Priority: IMMEDIATE**
```python
# Problem: os.makedirs() + os.system(chmod) + file write = TOCTOU
# Solution: Use atomic operations with error checking

os.makedirs(state_path, mode=0o755, exist_ok=False)
result = os.system(f"chmod 0o755 {mount_point}/kod/generations")
if result != 0:
    raise RuntimeError("chmod failed")

# Write files atomically: temp + rename
temp_packages = f"{state_path}/.tmp_packages"
with open(temp_packages, "w") as f:
    json.dump(packages_to_install, f)
os.rename(temp_packages, f"{state_path}/installed_packages")
```
**Impact**: Corrupt generation 0 state, rebuild loads wrong packages

---

### 3️⃣ GENERATION SWAP NO ROLLBACK (kod.py:620-624)
**Fix Priority: HIGH**
```python
# Problem: Non-atomic mv commands, no rollback on failure
# Solution: Use shell script with transactional semantics

# Create backup, execute moves, rollback if any fails
bash_script = """
set -e
gen_0="/kod/generations/${current_generation}/rootfs"
gen_new="/kod/generations/${generation_id}/"
old="/kod/current/old-rootfs"

# Validate all sources
[ -d "$gen_0" ] || exit 1
[ -d "$old" ] || exit 1

# Backup
btrfs subvolume snapshot "$gen_0" "/tmp/backup" || exit 1

# Move 1
mv "$gen_0" "$gen_new/rootfs" || {
    rm -rf /tmp/backup
    exit 1
}

# Move 2
mv "$old" "$gen_0" || {
    rm -rf "$gen_new/rootfs"
    mv /tmp/backup "$gen_0"
    exit 1
}

# Success
btrfs subvolume delete /tmp/backup
"""
```
**Impact**: Unbootable system on move failure, no recovery path

---

### 4️⃣ LAZY UNMOUNT HIDES STATE LOSS (kod.py:345-353)
**Fix Priority: HIGH**
```python
# Problem: `umount -lR` succeeds even if mounts still busy
# Solution: Verify unmount succeeds

exec("umount -R /mnt 2>/dev/null || umount -lR /mnt 2>/dev/null || true")

# VERIFY
import subprocess
result = subprocess.run(["mountpoint", "-q", "/mnt"], capture_output=True)
if result.returncode == 0:  # Still mounted
    raise RuntimeError("Failed to unmount /mnt")

# Also: flush before unmount
os.sync()
time.sleep(1)
```
**Impact**: State files written to stale cache, lost on reboot

---

### 5️⃣ WORLD-WRITABLE GENERATIONS DIR (kod.py:318)
**Fix Priority: IMMEDIATE**
```python
# VULNERABLE:
os.system(f"chmod 0o777 {mount_point}/kod/generations")

# FIXED:
os.system(f"chmod 0o755 {mount_point}/kod/generations")
os.system(f"chown root:root {mount_point}/kod/generations")

# Add audit
import stat
st = os.stat(f"{state_path}/installed_packages")
assert st.st_uid == 0
assert (st.st_mode & 0o077) == 0
```
**Impact**: Non-root users can corrupt state, privilege escalation

---

### 6️⃣ UNVALIDATED GENERATION ID IN PATHS (kod.py:620-624)
**Fix Priority: HIGH**
```python
# Problem: Generation ID from `/.generation` file without validation
# Solution: Validate before use

with open("/.generation") as f:
    current_generation = int(f.readline().strip())

# Validate: must be reasonable and path-safe
assert 0 <= current_generation <= 99999
assert current_generation == get_max_generation() or \
       current_generation == get_max_generation() - 1

# Resolve symlinks and verify paths
from pathlib import Path
current_path = Path(f"/kod/generations/{current_generation}/rootfs").resolve()
assert str(current_path).startswith("/kod/"), "Path traversal detected"
```
**Impact**: Directory traversal, overwrite /etc, destroy system

---

## 8 MEDIUM-RISK ISSUES (MEDIUM RISK)

| # | Issue | File | Line | Type | Fix |
|---|-------|------|------|------|-----|
| 7 | No dependency enforcement | executor.lua | 76-81 | Silent failures | Validate `depends_on` before step execution |
| 8 | Mount ordering race | devices.lua | 237-270 | Bind mount fails | Unmount before rebinding |
| 9 | Package dedup missing | packages.py | 295-308 | Duplicate installs | Deduplicate packages list |
| 10 | No fstab validation | devices.lua | 327-366 | Boot failure | Validate root entry exists after generation |
| 11 | No disk space check | kod.py | 272 | Partial install | Check `df` before pacstrap |
| 12 | Subvolume creation partial | devices.lua | 183-203 | Broken hierarchy | Change on_error="warn" to "abort" for critical subvols |
| 13 | Package lock loss | kod.py | 334 | Rebuild inconsistency | Catch exception, create placeholder lock |
| 14 | Shellquoting newline issue | executor.lua | 23 | Command injection | Quote mount_point (covered by issue #1) |

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Critical Fixes (this week)
- [ ] Quote mount_point in executor.lua:23
- [ ] Fix permissions on /kod/generations (chmod 0o755, chown root:root)
- [ ] Validate generation IDs before path ops
- [ ] Add chmod result checking

### Phase 2: High Priority (next 2 weeks)
- [ ] Implement atomic state creation
- [ ] Verify unmounts, add sync/sleep before
- [ ] Add transactional generation swap
- [ ] Enforce dependency checks in executor

### Phase 3: Medium Priority (next month)
- [ ] Add disk space pre-flight checks
- [ ] Fix bind mount ordering (unmount before remount)
- [ ] Validate fstab after generation
- [ ] Package deduplication
- [ ] Handle subvolume creation failures

### Phase 4: Long-term (infrastructure)
- [ ] Document recovery procedures
- [ ] Add integration tests for error scenarios
- [ ] Implement audit logging for state mutations
- [ ] Design state versioning/schema

---

## TESTING SCENARIOS

### Scenario 1: Mount Point Injection (Issue #1)
```bash
kod install -c config.lua -m "/mnt; echo PWNED; #"
# SHOULD FAIL with validation error, not execute echo PWNED
```

### Scenario 2: State Corruption (Issue #2)
```bash
# Simulate race: chmod fails
# Mock os.system to return 1 for chmod
kod install -c config.lua
# SHOULD FAIL with "chmod failed" error
# NOT skip chmod and write to wrong permissions
```

### Scenario 3: Generation Swap Failure (Issue #3)
```bash
# Fill disk during generation swap
# Kill rebuild mid-move
# SHOULD ROLLBACK to original state
# NOT leave system unbootable
```

### Scenario 4: Lazy Unmount (Issue #4)
```bash
# Mock unmount to succeed but stay mounted (lazy umount behavior)
# SHOULD FAIL with "Still mounted after unmount" error
# NOT write state to stale cache
```

### Scenario 5: World-Writable Perms (Issue #5)
```bash
# As non-root user
ls -ld /kod/generations
# SHOULD show: drwxr-xr-x root root (755)
# NOT drwxrwxrwx root root (777)
```

### Scenario 6: Generation ID Validation (Issue #6)
```bash
# Modify /.generation to "999"
# Create symlink: /kod/current/old-rootfs -> /etc
# kad rebuild --new-generation
# SHOULD FAIL with "Path traversal detected"
# NOT overwrite /etc with rootfs
```

---

## METRICS FOR VERIFICATION

After fixes, verify:
1. **No mount point injection**: Test with `-m "/mnt; id; #"` → validation error
2. **State atomic**: Verify all state files exist after install → rebuild succeeds
3. **Swap rollback**: Kill mid-swap → state recoverable with btrfs snapshots
4. **Unmount verified**: Add `mountpoint -q` check → catches lazy unmount issues
5. **Perms locked down**: Verify 755 on /kod/generations
6. **Generation validated**: Test with /.generation="999" → validation error
7. **Dependency enforced**: Mock failed step → dependent steps marked failed
8. **Fstab valid**: Verify root entry with correct UUID → boot succeeds

---

## REFERENCES

Full analysis: See `KOD_INSTALLATION_SECURITY_ANALYSIS.md`

Key files:
- `src/lua/kod/planning/executor.lua` - Step runner (issues #1, #7, #14)
- `src/kod/kod.py` - Install/rebuild CLI (issues #2, #3, #4, #5, #6)
- `src/lua/kod/sections/devices.lua` - Disk/mount setup (issues #8, #10, #12)
- `src/lua/kod/sections/packages.lua` - Package aggregation (issue #9)
