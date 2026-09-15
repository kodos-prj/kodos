# VM Testing Guide for Phase 5d

**Purpose:** Validate Phase 5d schema, section modules, and chroot-based installation on a real (or emulated) system.

**Status:** Phase 5d is complete and ready for VM testing  
**Branch:** `feat/architecture-redesign` (65 commits ahead of origin)  
**Config Used:** `example/eszkoz` (Phase 5d production-ready config)

---

## Prerequisites

### Host Requirements
- Linux system (KodOS is designed for Linux installs)
- 20+ GB free disk space (for VM image + scratch)
- QEMU/KVM or similar VM hypervisor (quickemu recommended)
- Python 3.10+ with `uv` package manager
- Git with this branch checked out

### VM Requirements
- **Distro:** Arch Linux (baseline for Phase 5d testing)
- **Size:** 34 GB virtual disk (as specified in eszkoz)
- **Boot:** UEFI (systemd-boot)
- **Network:** Bridged or NAT (eszkoz config includes NetworkManager)

### Development Setup
```bash
# Clone and activate environment
cd ~/Work/devel/analysis/kodos
git checkout feat/architecture-redesign
uv sync --dev
source .venv/bin/activate
```

---

## Phase 5d Test Scope

### What We're Testing

**Schema & Validation:**
- ✅ All 13 nested blocks parse and validate correctly
- ✅ User-level programs/services merge into global
- ✅ Desktop environments respect enable flags
- ✅ Services config and systemd blocks work

**Section Modules:**
- ✅ All 11 sections generate correct steps
- ✅ Chroot flags set appropriately (34/38 steps in chroot)
- ✅ Dependency ordering correct (depends_on chains)
- ✅ Distro detection works (install_cmd helper)

**Executor Integration:**
- ⚠️ **TODO:** Actual execution on VM (currently mocked in tests)
- Steps execute in correct order
- Chroot environment properly set up
- User creation and programs install correctly
- Services enable and start as expected

**Real-World Config:**
- eszkoz with multiple desktop environments
- SSH keys, dotfiles, custom programs per user
- Systemd mounts (CIFS, NFS)
- Hardware (pipewire, SANE)

---

## VM Testing Workflow

### Step 1: Generate Installation Plan

```bash
# From repo root, show the full plan for eszkoz
kod plan --baseline empty -c example/eszkoz > /tmp/eszkoz-phase5d-plan.txt

# Verify key components
grep "chroot.*true" /tmp/eszkoz-phase5d-plan.txt | wc -l   # Should be ~34
grep "devices_" /tmp/eszkoz-phase5d-plan.txt | head -5     # Disk ops first
grep "users_create" /tmp/eszkoz-phase5d-plan.txt           # User creation
grep "services_enable" /tmp/eszkoz-phase5d-plan.txt        # Services
grep "programs_install" /tmp/eszkoz-phase5d-plan.txt       # Programs
```

**Expected Output Example:**
```
Step 1: devices_partition_disk0_1 — parted (chroot=false)
...
Step 5: network_hostname_set — echo (chroot=true)
...
Step 15: boot_kernel_install — pacman (chroot=true)
...
Step 29: users_create_abuss — useradd (chroot=true)
...
Step 38: programs_install_emacs — pacman (chroot=true)
```

### Step 2: Review Plan Safety

Before executing on VM, verify:

```bash
# 1. Check for dangerous commands that need review
grep -E "rm -rf|dd |mkfs" /tmp/eszkoz-phase5d-plan.txt  # Destructive ops

# 2. Verify disk device is correct (should target /dev/nvme0n1 or similar)
grep "devices_partition" /tmp/eszkoz-phase5d-plan.txt | head -3

# 3. Check user names (should match eszkoz config)
grep "users_create" /tmp/eszkoz-phase5d-plan.txt

# 4. Verify repo mirrors are accessible
grep "repos.*install" /tmp/eszkoz-phase5d-plan.txt | head -2
```

### Step 3: Create VM Image

Using quickemu (recommended) or QEMU directly:

```bash
# Option A: Using quickemu (simplest)
mkdir -p ~/VMs/eszkoz
cd ~/VMs/eszkoz

# Create Arch base image (550 MB minimal download)
quickemu --create-image arch 34

# Boot and minimal setup (optional)
quickemu --vm arch.conf

# Option B: Manual QEMU
qemu-img create -f qcow2 eszkoz.qcow2 34G
qemu-system-x86_64 -enable-kvm -m 4G -hda eszkoz.qcow2 \
  -cdrom ~/Downloads/archlinux-2024.09.01-x86_64.iso
```

### Step 4: Partition & Mount VM Disk

From VM console (or via SSH once NetworkManager is running):

```bash
# Verify disk layout matches eszkoz plan
lsblk
# Expected: /dev/nvme0n1 (or /dev/sda for older VM setup)

# DO NOT run the full kod install yet — we're testing phases first
```

### Step 5: Test Installation Phases

#### Phase 1: Disk Operations (chroot=false)

```bash
# On VM, prepare disk (manually or via kod)
# Steps 1-4 from plan

# Expected results:
lsblk               # Shows partitions 1, 2, 3
mount | grep /boot  # /boot mounted
mount | grep /      # Root mounted
```

#### Phase 2: System Configuration (chroot=true)

After mounting, test chroot environment:

```bash
# Option A: Manual chroot (for debugging)
sudo chroot /boot/.. /bin/bash
  locale-gen
  echo 'en_US.UTF-8 UTF-8' >> /etc/locale.gen
  localectl set-locale LANG=en_CA.UTF-8
  exit

# Option B: Via kod executor (when ready)
# See "Executor Integration Testing" below
```

#### Phase 3: Packages & Services (chroot=true)

```bash
# Test package installation in chroot
chroot /boot/.. pacman -S --noconfirm linux

# Verify installed
chroot /boot/.. pacman -Q linux

# Test service enablement
chroot /boot/.. systemctl enable openssh
chroot /boot/.. systemctl status openssh  # Should show "enabled"
```

#### Phase 4: User Creation (chroot=true)

```bash
# Create user in chroot
chroot /boot/.. useradd -m -s /bin/bash abuss

# Verify user created
chroot /boot/.. id abuss
chroot /boot/.. ls -la /home/abuss
```

### Step 6: Executor Integration Testing

This is the critical Phase 5d test — executor actually runs all steps.

#### Setup Executor Context

```bash
# On host, prepare executor environment
cd ~/Work/devel/analysis/kodos

# Create test executor harness
python3 << 'EOF'
from kod._core import load_config
from kod.planner import compose_steps_lua
from kod.executor import execute_steps
from kod.distributions.arch import manage_packages
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Load config
config = load_config("example/eszkoz")
steps = compose_steps_lua(config, "arch")

# Print phase breakdown
print("Phase 1 (Disk Ops - host):")
for i, s in enumerate(steps[:4], 1):
    print(f"  {i}. {s.name} (chroot={s.chroot})")

print("\nPhase 2 (System Config - chroot):")
for i, s in enumerate(steps[4:15], 5):
    print(f"  {i}. {s.name} (chroot={s.chroot})")

print("\nPhase 3 (Packages - chroot):")
for s in steps:
    if 'install' in s.name or 'enable' in s.name:
        print(f"  {s.name} (chroot={s.chroot})")

print(f"\nTotal: {len(steps)} steps")
print(f"Host: {sum(1 for s in steps if not s.chroot)}")
print(f"Chroot: {sum(1 for s in steps if s.chroot)}")
EOF
```

#### Test Executor Dispatch

```bash
# Run executor in dry-run mode (no actual changes)
python3 << 'EOF'
from kod._core import load_config
from kod.planner import compose_steps_lua
from kod.executor import execute_steps

config = load_config("example/eszkoz")
steps = compose_steps_lua(config, "arch")

# Mock environment (no actual execution)
mock_env = {
    "manage_packages": lambda *args, **kwargs: None,
    "enable_services": lambda *args, **kwargs: None,
    "create_users": lambda *args, **kwargs: None,
}

# Execute in dry-run context (mock env -> no real commands run)
try:
    results = execute_steps(steps, mock_env, "/mnt/target", True,
                            repos=config.get("repos", {}), hooks={})
    print(f"Executed {len(results)} steps successfully")
    for r in results[:10]:
        print(f"  {r.step.name}: {r.success}")
except Exception as e:
    print(f"Error: {e}")
EOF
```

### Step 7: Real Installation Test

**⚠️ WARNING: This step is destructive. Use a fresh VM image.**

```bash
# On VM, run the actual kod install
# This requires kod binary/CLI to be available on the VM

# Option A: Via kod CLI (if installed on VM)
kod install --config /path/to/example/eszkoz --baseline empty

# Option B: Via Python directly
python3 -c "
from kod._core import load_config
from kod.bootstrap import install

config = load_config('example/eszkoz')
install(config, mount_point='/mnt/target')
"

# Monitor output
# - First 4 steps: disk ops (should see parted, mkfs, mount)
# - Steps 5+: should enter chroot and configure system
# - Watch for any chroot-related errors
```

### Step 8: Post-Installation Verification

After install completes:

```bash
# Boot into installed system
# From GRUB/systemd-boot, select the new kernel

# Verify installation
uname -a                          # Should show new kernel
cat /etc/hostname                 # Should be 'eszkoz'
locale                            # Should show en_CA.UTF-8
id abuss                          # Should exist
systemctl status openssh          # Should be enabled
pacman -Q emacs                   # Should be installed
ls /home/abuss/.config/git        # Should have git config

# Check desktop environments
pacman -Q gnome                   # Should be installed
pacman -Q cosmic                  # Should be installed
pacman -Q plasma                  # Should NOT be installed (enable=false)

# Check services
systemctl is-enabled openssh      # Should return 'enabled'
systemctl is-enabled bluetooth    # Should return 'enabled'
systemctl is-enabled avahi        # Should return 'enabled'
```

---

## Key Things to Verify

### 1. Chroot Flag Correctness

| Phase | Steps | Should be | Verify |
|-------|-------|-----------|--------|
| Disk ops | 1-4 | `chroot=false` | Run on host, access block devices |
| System config | 5-14 | `chroot=true` | Run in chroot, modify /etc, /boot |
| Packages | 15+ | `chroot=true` | Install into chroot's pacman root |
| Services | 31-37 | `chroot=true` | Enable in chroot's systemd |
| Users | 29-30 | `chroot=true` | Create in chroot's /etc/passwd |

**Test:** Each step should execute in correct context (host or chroot)

### 2. Enable Flag Behavior

```bash
# From plan output:
# ✓ gnome should install (enable=true)
# ✓ cosmic should install (enable=true)
# ✗ plasma should NOT install (enable=false)
# ✗ avahi should NOT... wait, avahi is enabled!
# Check eszkoz config: avahi enable=true, so SHOULD install

grep "environments_install\|services_enable" /tmp/eszkoz-phase5d-plan.txt
```

**Test:** Only enabled items appear in plan, others skipped

### 3. User-Level Programs/Services

```bash
# eszkoz user 'abuss' has:
# - programs: git, neovim, emacs, fish, zsh, etc.
# - services: syncthing (enable=false for user)

grep "programs_install" /tmp/eszkoz-phase5d-plan.txt | grep -E "git|neovim|emacs"
grep "syncthing" /tmp/eszkoz-phase5d-plan.txt         # Should NOT appear (disabled)

# After install, verify user has programs
sudo -u abuss git --version
sudo -u abuss nvim --version
```

**Test:** User programs merged into global, service disabled correctly

### 4. Nested Block Validation

```bash
# During plan generation, validator should accept:
# - users.abuss.identity.name
# - users.abuss.ssh_keys.[public_keys]
# - users.abuss.dotfiles.repos
# - users.abuss.programs.git.config
# - users.abuss.services.syncthing.enable
# - desktop.environments.gnome.enable
# - services.systemd.mounts.data
# - boot.loader.include

# No validation errors should appear
kod plan --baseline empty -c example/eszkoz 2>&1 | grep -i "error\|invalid"
# Should be empty (or only pre-existing failures)
```

**Test:** All nested blocks accepted by validator

### 5. Dependency Chain

```bash
# Programs should depend on package installation
grep "depends_on" /tmp/eszkoz-phase5d-plan.txt | head -5

# Example: programs_install should run after boot_kernel_install
# Services should run after packages installed
```

**Test:** Steps execute in dependency order (no broken chains)

---

## Expected Test Results

### Unit Tests (Already Passing)
```
712/726 tests passing (99.1%)
- 100+ Phase 5d-specific tests ✓
- 612+ Phase 5c regression tests ✓
- 14 pre-existing failures (unrelated)
```

### VM Installation Tests (To Verify)
```
Phase 1 - Disk Ops:
  ✓ Partitions created
  ✓ Filesystems formatted
  ✓ Mounts active

Phase 2 - System Config:
  ✓ Hostname set
  ✓ Locale configured
  ✓ Timezone set
  ✓ Kernel installed
  ✓ Bootloader working

Phase 3 - Packages & Services:
  ✓ All packages installed
  ✓ Desktop environments selective (gnome, cosmic only)
  ✓ Services enabled
  ✓ Programs available

Phase 4 - Users & Config:
  ✓ Users created with correct shells
  ✓ SSH keys deployed
  ✓ Dotfiles symlinked
  ✓ Per-user programs installed
  ✓ Per-user services configured
```

---

## Troubleshooting

### Issue: Chroot Command Fails

**Symptom:** `chroot: cannot execute command`

**Cause:** New root missing essential binaries (glibc, bash)

**Solution:**
```bash
# Ensure base packages installed before chroot
pacman -Sy
pacman -S --root /mnt/target base linux

# Verify
ls -la /mnt/target/bin/bash
```

### Issue: Services Won't Enable in Chroot

**Symptom:** `systemctl: command not found` in chroot

**Cause:** Systemd not installed yet

**Solution:** Kernel and systemd must install before service enablement

**Verify order:**
```bash
grep -n "boot_kernel\|services_enable" /tmp/eszkoz-phase5d-plan.txt
# boot_kernel_install should appear BEFORE services_enable_*
```

### Issue: User Programs Not Installed

**Symptom:** `pacman -Q emacs` returns nothing

**Cause:** Programs section not running (wrong baseline or disabled)

**Solution:**
```bash
# Check plan includes programs
grep "programs_install" /tmp/eszkoz-phase5d-plan.txt

# Check eszkoz config has programs enabled
grep -A 50 "programs = {" example/eszkoz/configuration.lua | head -20
```

### Issue: Desktop Environment Partially Installed

**Symptom:** GNOME installed but Cosmic not, or vice versa

**Cause:** Enable flag not respected OR one environment failed to install

**Solution:**
```bash
# Check plan has both
grep "environments_install" /tmp/eszkoz-phase5d-plan.txt

# Verify enable flags in eszkoz
grep "use_gnome\|use_cosmic\|enable = " example/eszkoz/configuration.lua | head -10

# Check installation errors
journalctl -xe | grep -i gnome
pacman -Q gnome gnome-extra cosmic
```

---

## When to Stop Testing

Stop when:
1. ✅ All 4 phases complete without chroot errors
2. ✅ Packages install into correct root (host vs chroot)
3. ✅ Desktop environments respect enable flags
4. ✅ Users created with correct shell and groups
5. ✅ Services enable/start correctly
6. ✅ System boots and boots work

Then:
- Document any issues found
- File bugs against specific sections
- Merge Phase 5d into main
- Plan Phase 5e improvements

---

## Additional Resources

- **Architecture:** [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Phase 5d Design:** [PHASE-5D-STRUCTURED-DESIGN.md](./PHASE-5D-STRUCTURED-DESIGN.md)
- **Executor Reference:** [src/kod/executor.py](../src/kod/executor.py)
- **Example Configs:** [example/eszkoz/](../example/eszkoz/)
- **Chroot Reference:** [Linux chroot manual](https://man7.org/linux/man-pages/man1/chroot.1.html)

---

## Next Steps After VM Testing

1. **If tests pass:**
   - Merge Phase 5d into main
   - Tag v5d release
   - Plan Phase 5e based on findings

2. **If issues found:**
   - File bugs against relevant sections
   - Fix in branch, re-test
   - Document workarounds
   - Then merge when satisfied

3. **Long-term:**
   - Automate VM testing in CI
   - Test on Debian alongside Arch
   - Test edge cases (encrypted disk, RAID, etc.)
