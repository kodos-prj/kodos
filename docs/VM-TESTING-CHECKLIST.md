# Phase 5d VM Testing Checklist

Quick reference for Phase 5d VM testing on real/emulated system.

---

## Pre-Test Setup

- [ ] Branch checked out: `git checkout feat/architecture-redesign`
- [ ] Tests passing: `pytest tests/ -q` → 712/726 passing
- [ ] Plan generates: `kod plan --baseline empty -c example/eszkoz`
- [ ] VM created with 34GB disk
- [ ] Network accessible (for pacman mirrors)
- [ ] Backup: VM image backed up before testing

---

## Phase 1: Disk Operations (Host - chroot=false)

These commands run BEFORE chroot is entered.

**On VM console:**

- [ ] Disk device identified: `lsblk` shows `/dev/nvme0n1` (or correct device)
- [ ] Partitions created: `parted -s /dev/nvme0n1 print` shows 3 partitions
- [ ] Filesystems formatted: `lsblk -f` shows ext4 on partitions 2 & 3
- [ ] Mounts active:
  - [ ] `mount | grep /boot` → /dev/nvme0n11 mounted
  - [ ] `mount | grep -v /boot | grep /mnt` → /dev/nvme0n12 mounted at /

**Expected Output:**
```bash
$ lsblk
nvme0n1           259:0    0   34G  0 disk
├─nvme0n11        259:1    0    1G  0 part /boot
├─nvme0n12        259:2    0   33G  0 part /
```

---

## Phase 2: System Configuration (Chroot - chroot=true)

These commands run INSIDE chroot (new root).

**On VM in chroot context:**

- [ ] Hostname set: `cat /etc/hostname` → `eszkoz`
- [ ] Hosts file updated: `grep eszkoz /etc/hosts`
- [ ] IPv6 disabled: `grep disable_ipv6 /etc/sysctl.d/*` → `= 1`
- [ ] Locale generated: `locale -a | grep en_CA` → `en_CA.utf8` listed
- [ ] Default locale set: `localectl` → `LANG=en_CA.UTF-8`
- [ ] Extra locales added: `localectl list-locales | grep en_US` → exists
- [ ] Timezone set: `ls -l /etc/localtime` → points to `/usr/share/zoneinfo/America/Edmonton`
- [ ] Kernel installed: `pacman -Q linux` → kernel package listed
- [ ] Bootloader installed: `ls -la /boot/loader/` → `loader.conf` exists
- [ ] Bootloader timeout: `grep timeout /boot/loader/loader.conf` → `timeout 10`
- [ ] Memtest included: `grep memtest /boot/loader/loader.conf`

**Expected Output:**
```bash
$ cat /etc/hostname
eszkoz

$ localectl
System Locale: LANG=en_CA.UTF-8
...

$ pacman -Q linux
linux 6.x.x-x-x
```

---

## Phase 3: Packages & Services (Chroot - chroot=true)

**Package Installation:**

- [ ] Pipewire installed: `pacman -Q pipewire`
- [ ] SANE installed: `pacman -Q sane`
- [ ] GNOME installed: `pacman -Q gnome`
  - [ ] GNOME extra: `pacman -Q gnome-extra`
- [ ] Cosmic installed: `pacman -Q cosmic`
- [ ] **Plasma NOT installed:** `pacman -Q plasma` → error (expected)
- [ ] System packages installed: `pacman -Q htop less`
- [ ] Emacs installed: `pacman -Q emacs-wayland`
- [ ] Neovim installed: `pacman -Q neovim`
- [ ] Flatpak installed: `pacman -Q flatpak`

**Service Enablement:**

- [ ] OpenSSH enabled: `systemctl is-enabled openssh` → `enabled`
- [ ] Bluetooth enabled: `systemctl is-enabled bluetooth` → `enabled`
- [ ] Cups enabled: `systemctl is-enabled cupsd` → `enabled`
- [ ] Tailscale enabled: `systemctl is-enabled tailscale` → `enabled`
- [ ] NetworkManager enabled: `systemctl is-enabled NetworkManager` → `enabled`
- [ ] Avahi enabled: `systemctl is-enabled avahi-daemon` → `enabled`
- [ ] Syncthing NOT enabled (user service): `systemctl is-enabled syncthing` → N/A (user scope)
- [ ] Pipewire enabled: `systemctl --user is-enabled --global pipewire` → `enabled`
- [ ] Fwupd enabled: `systemctl is-enabled fwupd` → `enabled`

**Expected Output:**
```bash
$ pacman -Q | grep -E "gnome|cosmic|plasma"
gnome 47.x-x
gnome-extra 47.x-x
cosmic 1.x-x
```

---

## Phase 4: User Creation & Configuration (Chroot - chroot=true)

**User Creation:**

- [ ] Root user exists: `id root` → uid=0
- [ ] Abuss user exists: `id abuss`
  - [ ] Shell correct: `echo $SHELL` → `/bin/bash`
  - [ ] Home created: `ls -d /home/abuss`

**User Programs (Merged into Global):**

- [ ] Git installed: `pacman -Q git`
- [ ] Neovim installed: `pacman -Q neovim`
- [ ] Emacs installed: `pacman -Q emacs-wayland`
- [ ] Fish shell installed: `pacman -Q fish`
- [ ] Zsh installed: `pacman -Q zsh`
- [ ] Starship installed: `pacman -Q starship`
- [ ] Helix installed: `pacman -Q helix`

**User Config Files (From dotfiles/ssh-keys):**

- [ ] .config directory created: `ls -d /home/abuss/.config`
- [ ] Git config deployed: `cat /home/abuss/.config/git/config` (if deployed)
- [ ] SSH directory created: `ls -d /home/abuss/.ssh`
- [ ] SSH key permissions: `ls -la /home/abuss/.ssh/` → 700 directory, 600 files
- [ ] Dotfiles repo present: Check for symlinks from git clone

**Expected Output:**
```bash
$ id abuss
uid=1000(abuss) gid=1000(abuss) groups=1000(abuss),10(wheel)

$ pacman -Q | grep -E "git|neovim|fish"
git 2.x.x-x
neovim 0.x.x-x
fish 3.x.x-x
```

---

## Phase 5: Desktop Environment Verification

**Check enabled environments only:**

- [ ] GNOME installed: `pacman -Q gnome gnome-extra`
  - [ ] Display manager set for GNOME
- [ ] Cosmic installed: `pacman -Q cosmic`
  - [ ] Display manager set for Cosmic
- [ ] **Plasma NOT installed:** `pacman -Q plasma` → ERROR (correct, enable=false)
- [ ] **Pantheon NOT installed:** `pacman -Q pantheon` → ERROR
- [ ] **Budgie NOT installed:** `pacman -Q budgie` → ERROR
- [ ] **XFCE NOT installed:** `pacman -Q xfce4` → ERROR

**Display Manager:**

- [ ] Cosmic Greeter installed: `pacman -Q cosmic-greeter`
- [ ] Cosmic Greeter enabled: `systemctl is-enabled cosmic-greeter` → `enabled`

**Expected Output:**
```bash
$ pacman -Q gnome
gnome 47.x-x

$ pacman -Q cosmic
cosmic 1.x-x

$ pacman -Q plasma 2>&1
error: package 'plasma' not found
```

---

## Phase 6: Boot & System Verification

**After reboot into new system:**

- [ ] System boots successfully
- [ ] Linux kernel running: `uname -a` shows new kernel
- [ ] Hostname correct: `hostname` → `eszkoz`
- [ ] Locale correct: `locale` shows `en_CA.UTF-8`
- [ ] Timezone correct: `timedatectl` shows `America/Edmonton`
- [ ] Bootloader works: Boot into second kernel option, then back (systemd-boot menu)
- [ ] Network works: `ping 8.8.8.8`
- [ ] Users can SSH: `ssh abuss@localhost` (if key deployed)
- [ ] Desktop session starts: Select Cosmic or GNOME at login

---

## Chroot Flag Validation

**Generate plan and verify:**

```bash
kod plan --baseline empty -c example/eszkoz 2>&1 | tee /tmp/plan.txt

# Check counts
grep -c "chroot.*true" /tmp/plan.txt   # Should be ~34
grep -c "chroot.*false" /tmp/plan.txt  # Should be ~4 (disk ops)

# Verify order (disk ops first, chroot second)
head -10 /tmp/plan.txt | grep "devices_" | wc -l    # Should be 4
head -20 /tmp/plan.txt | grep "network_" | wc -l    # Should be ~3-4
```

**Expected:**
```
001-004: devices_* (chroot=false) — parted, mkfs, mount
005-014: network/locale/boot (chroot=true)
015+: hardware/desktop/packages/services/users/programs (chroot=true)
```

---

## Enable Flag Validation

**Verify selective installation:**

- [ ] Plan shows GNOME install: `grep "environments_install_gnome" /tmp/plan.txt`
- [ ] Plan shows Cosmic install: `grep "environments_install_cosmic" /tmp/plan.txt`
- [ ] Plan does NOT show Plasma: `grep "environments_install_plasma" /tmp/plan.txt` → empty
- [ ] Plan shows OpenSSH enable: `grep "services_enable_openssh" /tmp/plan.txt`
- [ ] Plan does NOT show disabled services: `grep "services_enable.*false" /tmp/plan.txt` → empty
- [ ] Plan shows git program: `grep "programs_install_git" /tmp/plan.txt`
- [ ] Plan does NOT show disabled programs: Check eszkoz config for disabled ones

**After install on system:**
- [ ] Gnome installed: `pacman -Q gnome`
- [ ] Cosmic installed: `pacman -Q cosmic`
- [ ] Plasma NOT installed: `pacman -Q plasma 2>&1 | grep "not found"`
- [ ] OpenSSH enabled: `systemctl is-enabled openssh`
- [ ] Service NOT enabled if disabled in config

---

## Common Issues & Quick Fixes

| Issue | Check | Fix |
|-------|-------|-----|
| Chroot command fails | `/mnt/target/bin/bash` exists | Ensure base-devel installed before chroot |
| Services won't enable | Systemd installed in chroot | Install kernel before systemctl enable |
| Programs not found | `pacman -Q <program>` | Check enable flag in eszkoz config |
| Wrong DE installed | `pacman -Q gnome plasma` | Verify enable flags in eszkoz: `use_gnome`, `use_cosmic` |
| Hostname not set | `cat /etc/hostname` | Ensure network section ran in chroot |
| Network not working | `ip link` | Install NetworkManager and enable before boot |
| SSH key not deployed | `cat /home/abuss/.ssh/authorized_keys` | Check ssh-keys section in users config |

---

## Test Completion Criteria

✅ **PASS** if all of:

1. **Phase 1 (Disk):** Partitions created, filesystems formatted, mounts active
2. **Phase 2 (Config):** Hostname, locale, timezone, kernel, bootloader all set
3. **Phase 3 (Packages):** GNOME & Cosmic installed, Plasma NOT installed
4. **Phase 4 (Users):** abuss created with correct shell, programs installed
5. **Phase 5 (Services):** OpenSSH, NetworkManager, Bluetooth enabled
6. **Phase 6 (Boot):** System boots, network works, users can login
7. **Chroot flags:** All disk ops run on host, everything else in chroot
8. **Enable flags:** Only enabled items install, disabled items skipped

❌ **FAIL** if any of:

- Chroot errors during installation
- Wrong partition/filesystem created
- Plasma installed (should be skipped)
- Users not created or SSH keys not deployed
- Services not enabled
- System won't boot
- Chroot flags set incorrectly

---

## After Testing

- [ ] Document any issues in GitHub issues
- [ ] Note any differences from expected output
- [ ] Collect log files: `journalctl`, `pacman.log`
- [ ] Decision: Merge to main if passing, or fix issues first

