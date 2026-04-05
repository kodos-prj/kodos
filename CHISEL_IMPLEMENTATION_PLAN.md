# Chisel Package Manager Integration for Kodos - Implementation Plan

## Overview
This document outlines the detailed plan for creating a new `chisel.py` module in Kodos that mirrors the functionality of the existing `arch.py` module but uses Chisel as the package manager instead of Pacman.

## Goals
- Maintain API compatibility with existing `arch.py` functions
- Provide cross-distribution package management via Chisel
- Ensure same functionality with equivalent Chisel commands
- Support both system-level (chroot) and host-level operations

## Function Mapping: arch.py → chisel.py

### 1. `prepare_for_installation() -> None`
**Current Implementation (arch.py):**
- Empty function that passes

**Chisel Implementation:**
- Verify chisel is installed and accessible
- Check chisel database initialization
- Ensure `/kod/` directory structure is ready
- No changes needed for basic setup since chisel is pre-installed

**Equivalent Commands:**
- Check: `which chisel`
- Initialize: `chisel sync` (will be called separately)

---

### 2. `get_base_packages(conf: Any) -> Dict[str, Any]`
**Current Implementation (arch.py):**
- Detects CPU microcode (AMD or Intel)
- Gets kernel package from configuration or defaults to "linux"
- Returns dict with 'kernel' and 'base' keys
- Base packages include: base, base-devel, microcode, btrfs-progs, linux-firmware, bash-completion, mlocate, sudo, schroot, whois, dracut, git, arch-install-scripts

**Chisel Implementation:**
- **IDENTICAL**: Same CPU microcode detection logic
- **IDENTICAL**: Same kernel package extraction from config
- **IDENTICAL**: Same package list (Chisel can use Arch packages)
- **NOTE**: arch-install-scripts may not be needed with Chisel (needs review)

**Key Differences:**
- Package sources are from Arch mirrors (same packages, different origin)
- All packages are available through Chisel's unified package store

**Return Value:** Same structure as arch.py

---

### 3. `install_essentials_pkgs(base_pkgs: Dict, mount_point: str) -> None`
**Current Implementation (arch.py):**
```
pacstrap -K {mount_point} {kernel} {base_packages}
```

**Chisel Implementation:**
```
chisel install {kernel} {base_packages}
```

**Key Considerations:**
- `pacstrap` is Arch-specific bootstrap tool
- Chisel's `install` command handles package extraction to `/kod/store/`
- Wrapper scripts are generated automatically by Chisel
- May need to handle mount point setup differently
- Consider: Does Chisel need to install to a specific mount point?

**Alternative Approaches:**
1. Direct chisel install (simpler, but may not respect mount point)
2. Use chisel with custom ALPM root pointing to mount point
3. Copy installed packages from `/kod/store/` to mount point after installation

**Recommended Approach:** Option 3 - install to /kod/, then copy to mount point

---

### 4. `get_kernel_file(mount_point: str, package: str = "linux") -> Tuple[str, str]`
**Current Implementation (arch.py):**
```
pacman -Ql {package} | grep vmlinuz
Extract file path and version from output
```

**Chisel Implementation:**
- Need to query Chisel for kernel file location
- Chisel stores packages in `/kod/store/{package}/{version}/`
- Kernel file path would be: `/kod/store/{package}/{version}/usr/bin/vmlinuz-*`

**Possible Commands:**
- `chisel list` - lists installed packages
- Check `/kod/store/` directory structure directly
- Query registry in `/kod/registry.json`

**Recommended Approach:** Check `/kod/store/{package}/` directory structure

**Return Value:** Tuple of (kernel_file_path, kernel_version)

---

### 5. `setup_linux(kernel_package: str) -> str`
**Current Implementation (arch.py):**
- Gets kernel file via `get_kernel_file()`
- Copies kernel to `/boot/vmlinuz-{version}`
- Returns kernel version

**Chisel Implementation:**
- Same logic, but uses Chisel's `get_kernel_file()` implementation
- Copy kernel from `/kod/store/` path to boot partition
- Return kernel version

**No Changes Required:** Uses `get_kernel_file()` internally

---

### 6. `get_list_of_dependencies(pkg: str) -> List[str]`
**Current Implementation (arch.py):**
- Checks if package is a group: `pacman -Sgq {pkg}`
- If not a group, gets dependencies: `pacman -Si {pkg} | grep 'Depends On'`
- Returns list of dependency package names

**Chisel Implementation:**
- Query dependency information from Arch mirrors (same as Pacman)
- Chisel uses the same Arch database format
- Could use: `chisel info {pkg}` or parse registry

**Possible Commands:**
- Direct query of Arch mirrors (would need HTTP client)
- Parse `/kod/db/` Chisel databases directly
- Use Chisel's internal query if available

**Recommendation:** Parse Arch database files in `/kod/db/` or call `chisel search`

---

### 7. `proc_repos(conf, current_repos=None, update=False, mount_point="/mnt") -> Tuple[Dict, List]`
**Current Implementation (arch.py):**
- Processes repository configuration from config
- Handles custom builds via git clone and build commands
- Installs packages via: `pacman -S --needed --noconfirm {package}`
- Writes repo config to `/var/kod/repos.json`

**Chisel Implementation:**
- **SAME**: Repository configuration processing
- **SAME**: Custom build handling (git clone, build commands)
- **CHANGED**: Package installation via `chisel install {package}`
- **SAME**: Repo config output to `/var/kod/repos.json`

**Key Changes:**
- Replace `pacman -S --needed --noconfirm` with `chisel install`
- Ensure packages are installed to correct mount point
- Handle Chisel's store and wrapper creation

**Return Value:** Same structure (repos dict and packages list)

---

### 8. `refresh_package_db(mount_point: str, new_generation: bool) -> None`
**Current Implementation (arch.py):**
- New generation: `pacman -Syy --noconfirm` inside chroot
- Not new generation: `pacman -Syy --noconfirm` on host

**Chisel Implementation:**
- New generation: `chisel sync` inside chroot (or pointing to chroot ALPM root)
- Not new generation: `chisel sync` on host
- Equivalent command: `chisel sync` (replaces `pacman -Syy`)

**Key Differences:**
- Chisel sync downloads Arch databases to `/kod/db/`
- May need to handle mount point for new generations differently

**Return Value:** None

---

### 9. `kernel_update_required(current_kernel: str, next_kernel: str, current_installed_packages: Dict, mount_point: str) -> bool`
**Current Implementation (arch.py):**
- Compares kernel package names
- Gets new kernel version: `pacman -Q {kernel}`
- Compares with stored version from `current_installed_packages`
- Returns True if different

**Chisel Implementation:**
- **SAME**: Compare package names
- **CHANGED**: Get version via Chisel
  - `chisel list {kernel}` or query registry
- **SAME**: Version comparison logic
- **SAME**: Return boolean

**Possible Commands:**
- `chisel list` to get installed packages and versions
- Query `/kod/registry.json` directly
- Check `/kod/store/` directory version folders

**Recommendation:** Query registry.json or use chisel list

**Return Value:** Boolean

---

### 10. `generale_package_lock(mount_point: str, state_path: str) -> None`
**Current Implementation (arch.py):**
- Gets installed packages: `pacman -Q --noconfirm`
- Writes to `{state_path}/packages.lock`

**Chisel Implementation:**
- Get installed packages via `chisel list`
- Write to `{state_path}/packages.lock`

**Possible Commands:**
- `chisel list` - lists all installed packages
- Parse `/kod/registry.json` directly
- Use `chisel list` output

**Recommendation:** Use `chisel list` for consistency

**Return Value:** None (writes file)

---

## Implementation Strategy

### Phase 1: Core Setup
1. Create `/home/abuss/Work/devel/kodos-chisel/kodos/src/kod/chisel.py`
2. Copy module docstring and imports from arch.py
3. Implement `prepare_for_installation()` - verification function
4. Implement `get_base_packages()` - IDENTICAL to arch.py

### Phase 2: Basic Package Management
5. Implement `install_essentials_pkgs()` - use chisel install
6. Implement `refresh_package_db()` - use chisel sync
7. Implement `generale_package_lock()` - use chisel list

### Phase 3: Kernel Management
8. Implement `get_kernel_file()` - query /kod/store/ structure
9. Implement `setup_linux()` - uses get_kernel_file()
10. Implement `kernel_update_required()` - use chisel list

### Phase 4: Repository & Dependency Management
11. Implement `proc_repos()` - replace pacman with chisel
12. Implement `get_list_of_dependencies()` - query arch databases or chisel

### Phase 5: Testing
13. Verify all functions have correct signatures
14. Test chisel command replacements
15. Ensure mount point handling works correctly

---

## Command Mapping Summary

| Function | arch.py Command | chisel.py Command |
|----------|-----------------|-------------------|
| install_essentials_pkgs | pacstrap | chisel install |
| get_kernel_file | pacman -Ql | Check /kod/store/ |
| get_list_of_dependencies | pacman -Sgq, pacman -Si | chisel list, registry.json |
| proc_repos | pacman -S | chisel install |
| refresh_package_db | pacman -Syy | chisel sync |
| kernel_update_required | pacman -Q | chisel list |
| generale_package_lock | pacman -Q | chisel list |

---

## Special Considerations

### Mount Point Handling
- Chisel installs to `/kod/store/` by default
- May need to copy packages to mount point after installation
- Consider using chisel's ALPM root configuration for custom paths

### Package Names
- Arch packages used by Chisel are identical to Pacman
- No renaming needed
- cross-distribution support is transparent to Kodos

### Wrapper Scripts
- Chisel generates wrapper scripts automatically
- Kodos doesn't need to manage these
- Wrappers handle LD_LIBRARY_PATH management

### Dependency Resolution
- Chisel handles dependencies automatically
- Same as Pacman behavior
- No special handling needed in Kodos

---

## Potential Issues & Mitigations

1. **Mount Point Isolation**
   - Issue: Chisel installs globally to /kod/
   - Mitigation: Copy packages to mount point or use custom ALPM root

2. **Package Database Location**
   - Issue: Databases stored in /kod/db/ not /var/lib/pacman/
   - Mitigation: Query registry.json or use chisel list

3. **Microcode Package Names**
   - Issue: May differ between distributions
   - Mitigation: Use Arch names (same as arch.py)

4. **Arch-Install-Scripts**
   - Issue: Not available in Arch for non-Arch systems
   - Mitigation: Remove or make optional

---

## Testing Checklist

- [ ] All functions maintain same signatures as arch.py
- [ ] Function return types match arch.py
- [ ] Chisel commands execute correctly
- [ ] Mount point operations work as expected
- [ ] Package locking works correctly
- [ ] Kernel management functions return correct data
- [ ] Repository processing functions handle configs properly
- [ ] Error handling is consistent with arch.py

---

## Notes for Implementation

1. **Imports**: Use same imports as arch.py (exec_chroot, exec, json, Dict, Any)
2. **Comments**: Keep "# Chisel" markers similar to "# Arch" in arch.py
3. **Docstrings**: Adapt docstrings from arch.py, mention Chisel instead of Pacman
4. **Error Handling**: Inherit error handling from common.py functions
5. **Logging**: Use print statements for consistency with arch.py

