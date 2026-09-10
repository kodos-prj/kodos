# Medium-Priority Bugs from Codebase Audit

Found during codebase audit to identify patterns similar to AUR/Flatpak fixes.
These 7 medium-priority issues should be addressed in Phase 4.

## Summary Table

| # | Bug | Severity | Location | Type | Similar To |
|----|-----|----------|----------|------|-----------|
| 1 | Privilege escalation logic gap | MEDIUM | packages.py:341-343 | Logic | run_as_root handling |
| 2 | Build dependencies not installed | MEDIUM | debian.py:204 (TODO) | Missing Impl | AUR build validation |
| 3 | Kernel version parsing no validation | MEDIUM | arch.py:293-295, debian.py:266-268 | Parsing | Kernel file parsing (Critical #5) |
| 4 | Dependency resolution fallback unreachable | MEDIUM | arch.py:135-143 | Logic | Conditional logic |
| 5 | Flatpak init error handling weak | MEDIUM | arch.py:218-227 | Error Handling | AUR verification |
| 6 | Package installation missing verification | MEDIUM | arch.py:230-242 | Validation | AUR build verification |
| 7 | No tests for proc_repos() | MEDIUM | tests/test_packages.py | Coverage | Test gaps |

---

## BUG #1: Privilege Escalation Logic Gap

**Severity:** MEDIUM  
**Location:** `src/kod/system/packages.py:341-343`  
**Type:** Logic bug  
**Related to:** Bug #6 from critical fixes (run_as_root flag handling)  

### Problem
```python
should_run_as_root = repos[repo].get("run_as_root", True)

if not should_run_as_root:
    # Run as regular "kod" user
```

Current logic:
- Some non-root tools (like yay) still need elevation internally
- No cascade between sudo elevation vs full root
- Privilege model is binary (all-root or all-user)
- Could leave tools unable to gain needed permissions

### Impact
- Incomplete: Some operations may need intermediate privilege levels
- No clear escalation path if a tool needs temporary root

### Suggested Fix
Create privilege escalation levels:
- `False` = user-only (no elevation)
- `"sudo"` = sudo without password
- `True` = full root
- Default based on repo type

### Effort: 2-3 hours
- Refactor run_as_root to support levels
- Update repos.lua to specify levels
- Test all repo types with new levels

### Should be fixed in Phase 4
- After critical AUR/Flatpak fixes prove stable
- When adding more repo types that need mid-level elevation

---

## BUG #2: Build Dependencies Not Installed Before Build

**Severity:** MEDIUM  
**Location:** `src/kod/debian.py:204` (TODO marker)  
**Type:** Missing implementation  
**Related to:** Critical Bug #3 (Initialization order)  

### Problem
```python
# TODO: Generalize this code to support other distros
# exec_chroot("pacman -S --needed --noconfirm git base-devel")
exec_chroot(
    f"runuser -u kod -- /bin/bash -c 'cd && git clone {url} {name} && cd {name} && {build_cmd}'",
    mount_point=mount_point,
)
```

Current issues:
- Debian AUR build assumes git is available
- Doesn't install build-essential for compilation
- Commented-out code suggests incomplete implementation
- Will fail silently if tools missing

### Impact
- AUR builds on Debian will fail if build tools missing
- Arch has implicit base-devel in build container
- Debian doesn't have same guarantee

### Suggested Fix
Before AUR build on Debian:
```python
# Install build dependencies
exec_chroot(
    "apt-get update && apt-get install -y build-essential git",
    mount_point=mount_point,
)
```

Then AUR build will have required tools.

### Effort: 30 minutes
- Add apt install before build
- Add validation (same as arch.py)
- Test Debian AUR build flow

### Should be fixed in Phase 4
- After verifying Arch AUR builds work
- Before shipping production Debian support

---

## BUG #3: Kernel Version Parsing No Validation

**Severity:** MEDIUM  
**Location:** `src/kod/arch.py:293-295, src/kod/debian.py:266-268`  
**Type:** Parsing without validation  
**Related to:** Critical Bug #5 (Kernel file parsing)  

### Problem
```python
# arch.py:293-295
kernel_version = next_kernel_file.split("-")[-2]
split_kver = kernel_version.split(".")
arch = split_kver[0]

# debian.py:266-268
kernel_version = next_kernel_file.split("-", 2)[-1]
split_kver = kernel_version.split(".")
arch = split_kver[0]
```

Current issues:
- Parses kernel_version without validating format
- Assumes kernel_version has dots (splits on ".")
- Crashes if kernel_version is empty or malformed
- arch = split_kver[0] assumes split succeeded

### Impact
- Kernel version detection can crash
- No graceful fallback for unexpected versions

### Suggested Fix
Add validation before parsing:
```python
if not kernel_version or kernel_version.isspace():
    raise RuntimeError(f"Invalid kernel version: {kernel_version}")

split_kver = kernel_version.split(".")
if not split_kver or not split_kver[0]:
    raise RuntimeError(f"Could not parse kernel architecture from: {kernel_version}")

arch = split_kver[0]
```

### Effort: 20 minutes
- Add validation in both files
- Test with edge cases (unusual kernel names)

### Should be fixed in Phase 4
- After kernel file parsing fix (already done)
- Part of comprehensive output validation hardening

---

## BUG #4: Dependency Resolution Fallback Never Runs

**Severity:** MEDIUM  
**Location:** `src/kod/arch.py:135-143`  
**Type:** Logic bug (unreachable code)  
**Related to:** Error handling improvements  

### Problem
```python
def get_list_of_dependencies(pkg: str):
    # ... 
    group_packages = exec_chroot(f"pacman -Sgq {pkg}", get_output=True)
    
    # BUG: group_packages is always truthy!
    # Empty string is returned, not None
    if group_packages:
        return group_packages.split('\n')
    
    # This fallback never runs because empty string is still truthy
    return exec_chroot(f"pacman -Si {pkg} | grep Depends").split()
```

Current issues:
- `exec_chroot()` returns empty string `""` if no output
- Empty string is truthy in Python
- Fallback code never executes
- If -Sgq returns nothing, function returns empty list

### Impact
- Group dependency detection incomplete
- Fallback query never used even when needed
- May miss dependencies on first call

### Suggested Fix
Check for empty string explicitly:
```python
group_packages = exec_chroot(f"pacman -Sgq {pkg}", get_output=True)

if group_packages and group_packages.strip():  # Check for non-empty
    return group_packages.split('\n')

# Fallback now works correctly
return exec_chroot(f"pacman -Si {pkg} | grep Depends").split()
```

### Effort: 15 minutes
- Add .strip() checks
- Add test case for fallback path
- Verify both paths work

### Should be fixed in Phase 4
- Low impact but important for completeness
- Good catch for code quality review

---

## BUG #5: Flatpak Init Error Handling Weak

**Severity:** MEDIUM  
**Location:** `src/kod/arch.py:218-227`  
**Type:** Error handling  
**Related to:** Critical Bug #4 (AUR build verification)  

### Problem
```python
# Handle Flatpak remote initialization
if repo == "flatpak" and "init" in repo_desc:
    init_cmd = repo_desc["init"]
    print(f"Initializing Flatpak: {init_cmd}")
    try:
        exec_chroot(f"{init_cmd}", mount_point=mount_point)
        print(f"✅ Flatpak remote initialized")
    except Exception as e:
        print(f"⚠️  Warning: Flatpak remote initialization failed: {e}")
        # Don't fail completely, just warn
```

Current issues:
- Issues a warning but continues
- Doesn't check if flatpak is actually installed
- If flatpak package missing, init fails silently
- Later commands will fail with cryptic errors

### Impact
- Users get warned but then fail later with unclear error
- No validation that flatpak system is ready
- Could confuse debugging

### Suggested Fix
Pre-check before attempting init:
```python
if repo == "flatpak" and "init" in repo_desc:
    init_cmd = repo_desc["init"]
    
    # First verify flatpak is installed
    flatpak_check = exec_chroot(
        "which flatpak",
        mount_point=mount_point,
        get_output=True
    )
    
    if not flatpak_check or "not found" in flatpak_check:
        raise RuntimeError("Flatpak not installed. Install 'flatpak' package first.")
    
    # Now safe to initialize
    print(f"Initializing Flatpak: {init_cmd}")
    try:
        exec_chroot(f"{init_cmd}", mount_point=mount_point)
        print(f"✅ Flatpak remote initialized")
    except Exception as e:
        raise RuntimeError(f"Flatpak initialization failed: {e}")
```

### Effort: 20 minutes
- Add pre-check for flatpak binary
- Change to error instead of warning
- Test flatpak initialization flow

### Should be fixed in Phase 4
- After base package installation validation
- Before shipping production flatpak support

---

## BUG #6: Package Installation Missing Verification

**Severity:** MEDIUM  
**Location:** `src/kod/arch.py:230-242`  
**Type:** Missing validation  
**Related to:** Critical Bug #4 (AUR build verification)  

### Problem
```python
# Install base package if specified (e.g., flatpak, yay, etc.)
if "package" in repo_desc:
    pkg_name = repo_desc['package']
    print(f"Installing base package for '{repo}': {pkg_name}")
    try:
        exec_chroot(
            f"pacman -S --needed --noconfirm {pkg_name}",
            mount_point=mount_point,
        )
        packages += [pkg_name]
        print(f"✅ Base package '{pkg_name}' installed")
    except Exception as e:
        print(f"❌ Failed to install base package '{pkg_name}': {e}")
        raise
```

Current issues:
- No verification that package actually installed
- `pacman -S --needed` succeeds even if package skipped
- No check that binary/package exists after install
- Silent failures if install was only partial

### Impact
- Could report success when package not actually installed
- Later operations on missing package fail with unclear errors
- No way to distinguish "already installed" from "install failed"

### Suggested Fix
Add verification after install:
```python
if "package" in repo_desc:
    pkg_name = repo_desc['package']
    print(f"Installing base package for '{repo}': {pkg_name}")
    try:
        exec_chroot(
            f"pacman -S --needed --noconfirm {pkg_name}",
            mount_point=mount_point,
        )
        
        # Verify installation succeeded
        result = exec_chroot(
            f"pacman -Q {pkg_name}",
            mount_point=mount_point,
            get_output=True
        )
        if not result or "not found" in result:
            raise RuntimeError(f"Package '{pkg_name}' not found after install attempt")
        
        packages += [pkg_name]
        print(f"✅ Base package '{pkg_name}' installed")
    except Exception as e:
        print(f"❌ Failed to install base package '{pkg_name}': {e}")
        raise
```

### Effort: 20 minutes
- Add pacman -Q validation after install
- Test with already-installed packages
- Test with missing packages

### Should be fixed in Phase 4
- Part of comprehensive verification hardening
- Similar pattern to AUR build verification

---

## BUG #7: No Tests for proc_repos()

**Severity:** MEDIUM  
**Location:** `tests/test_packages.py` (missing coverage)  
**Type:** Test coverage gap  
**Related to:** All previous fixes  

### Problem
Critical functions untested:
- `proc_repos()` - main repo processing logic
- AUR helper building
- AUR helper building on Debian
- Flatpak remote initialization
- Flatpak package installation
- Base package installation

Current coverage:
- repo_types() tested ✓
- get_list_of_dependencies() tested ✓
- manage_packages() tested ✓
- proc_repos() tested ✗ (MISSING)

### Impact
- AUR/Flatpak fixes only verified by manual testing
- No regression detection if proc_repos changes
- Can't catch future bugs in repo initialization
- 13 bugs found via code review because not tested

### Suggested Fix
Add test suite for proc_repos():

```python
class TestProcRepos:
    def test_proc_repos_processes_official_arch_repo(self, mock_chroot):
        """Test official Arch repo"""
        
    def test_proc_repos_builds_aur_helper(self, mock_chroot):
        """Test AUR build on Arch"""
        
    def test_proc_repos_verifies_aur_helper_exists(self, mock_chroot):
        """Test that AUR binary validation works"""
        
    def test_proc_repos_initializes_flatpak_remote(self, mock_chroot):
        """Test Flatpak remote-add"""
        
    def test_proc_repos_installs_base_package(self, mock_chroot):
        """Test base package installation"""
        
    def test_proc_repos_debian_aur_build(self, mock_chroot):
        """Test AUR build on Debian"""
        
    def test_proc_repos_debian_kernel_version_parsing(self, mock_chroot):
        """Test kernel version extraction on Debian"""
        
    def test_proc_repos_dependency_isolation_non_root(self, mock_chroot):
        """Test per-package install for non-root repos"""
```

### Effort: 3-4 hours
- Write 8+ test cases
- Mock exec_chroot() calls
- Test success and failure paths
- Test Arch and Debian variations

### Should be fixed in Phase 4
- Before shipping to production
- Before accepting new AUR/Flatpak features
- Will catch future regressions

---

## Priority for Phase 4

### First (Week 1)
1. Bug #2 - Build dependencies on Debian (blocks Debian AUR)
2. Bug #5 - Flatpak error handling (blocks Flatpak)
3. Bug #6 - Package install verification (completes verification hardening)

### Second (Week 2)
4. Bug #3 - Kernel version parsing validation
5. Bug #1 - Privilege escalation levels (infrastructure)
6. Bug #4 - Dependency resolution fallback

### Third (Week 3)
7. Bug #7 - proc_repos() test suite (foundation for future work)

---

## Effort Summary

| Bug | Time |
|-----|------|
| All 7 bugs | 7-8 hours |
| Quick fixes (1,3,4,5) | 1 hour |
| Build dependencies (2) | 30 min |
| Verification (6) | 20 min |
| Privilege levels (1) | 2-3 hours |
| Test suite (7) | 3-4 hours |

Total if all fixed: **7-8 hours** (distributed over Phase 4)
Quick wins first: **1 hour** fixes 4 bugs

---

## Related Work

This audit was triggered by finding 8 bugs in previous sessions:
1. Session 1: Generation cleanup + AUR/Flatpak bugs (2 bugs)
2. Session 2: Codebase audit (6 critical bugs)
3. Session 3 (Phase 4): 7 medium bugs from this list

Defensive programming pattern observed:
- Output validation is weak across codebase
- Error isolation incomplete in batch operations
- Dependency ordering not enforced
- Type/field identifiers sometimes missing
- Verification after operations is inconsistent

Recommendation: Apply same rigor to all package/repo operations during Phase 4.
