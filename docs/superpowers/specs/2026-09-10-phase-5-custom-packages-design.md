# Phase 5: Custom Package Security — Design Specification

**Date:** September 10, 2026  
**Status:** Design Review Required  
**Approach:** Linear Sequential (5a MVP → 5b Enhanced)  
**Estimated Duration:** 8-10 hours total (5a: 4-5 hours, 5b: 4-5 hours)

---

## Executive Summary

Phase 5 enables users to build custom packages from source with comprehensive security controls. The implementation is split into two sequential phases:

- **Phase 5a (MVP):** Hash verification, approval workflow, basic caching, audit logging
- **Phase 5b (Enhanced):** Bubblewrap sandbox, cache integrity, improved error messages, security docs

Each phase ships independently, allowing user feedback between releases.

---

## Architecture Overview

### Component Model

```
User Configuration (config.lua)
    ↓
Custom Package Definition (name, source, hash, template, build flags)
    ↓
[5a] Source Download & Hash Verification
    ↓
[5a] Build Template Expansion (generate shell commands)
    ↓
[5a] User Approval (show commands, require confirmation)
    ↓
[5b] Build Sandbox (bubblewrap - optional in 5a, required in 5b)
    ↓
Build Execution
    ↓
[5a] Audit Logging (record build details)
    ↓
[5a] Package Caching (store result, track metadata)
    ↓
Cache Lookup & Verification
    ↓
Installation (via existing package manager)
```

### Key Files & Responsibilities

| Component | File | Phase | Responsibility |
|-----------|------|-------|-----------------|
| Schema | src/kod/lib/custom_packages.lua | 5a | Define custom package format in config |
| Download | src/kod/system/packages_custom.py | 5a | Download sources, verify hashes |
| Templates | src/kod/system/build_templates.py | 5a | Generate build commands from templates |
| Approval | src/kod/system/packages_custom.py | 5a | Show commands, get user confirmation |
| Caching | src/kod/system/package_cache.py | 5a | Store/retrieve built packages |
| Logging | src/kod/system/package_audit.py | 5a | Log all build operations |
| Sandbox | src/kod/system/build_sandbox.py | 5b | Bubblewrap integration |
| Integrity | src/kod/system/package_cache.py | 5b | Verify cached package tampering |
| Docs | docs/SECURITY.md | 5b | User-facing security guide |

---

## Phase 5a: MVP Implementation

### 1. Custom Package Schema

**File:** `src/kod/lib/custom_packages.lua`

Custom packages defined in configuration with required fields:

```lua
custom_packages = {
  {
    name = "hello",
    version = "2.12",
    source = "https://ftp.gnu.org/gnu/hello/hello-2.12.tar.gz",
    source_hash = "sha256:abc123def456...",  -- REQUIRED, computed by user
    template = "autotools",                  -- autotools, cmake, make, custom
    build_flags = "--prefix=/usr",          -- Optional
    build_commands = nil,                   -- Custom commands if template = "custom"
  }
}
```

**Validation:**
- All required fields present
- source_hash format: `sha256:` prefix + 64 hex chars
- template value in allowed set
- source is valid HTTPS URL (not http, not file://)
- version matches semantic versioning

**Tests:**
- Valid schema passes
- Missing source_hash fails
- Invalid hash format fails
- HTTP (not HTTPS) rejected
- Malformed URLs rejected

### 2. Source Download & Hash Verification

**File:** `src/kod/system/packages_custom.py` (new functions)

```python
def download_source(url, dest_path, timeout=300):
    """Download package source from URL.
    
    Args:
        url: HTTPS URL to download
        dest_path: Where to save downloaded file
        timeout: Download timeout in seconds
        
    Raises:
        SourceDownloadError: If download fails
    """
    try:
        response = urllib.request.urlopen(url, timeout=timeout)
        with open(dest_path, 'wb') as f:
            f.write(response.read())
    except Exception as e:
        raise SourceDownloadError(f"Failed to download {url}: {e}")

def verify_source_hash(file_path, expected_hash):
    """Verify downloaded source against expected SHA256 hash.
    
    Args:
        file_path: Path to downloaded file
        expected_hash: Expected hash (format: "sha256:abc123...")
        
    Raises:
        SourceVerificationError: If hash doesn't match
    """
    if not expected_hash.startswith("sha256:"):
        raise ValueError("Hash format must be 'sha256:xxx'")
    
    expected = expected_hash.replace("sha256:", "")
    actual = hashlib.sha256(open(file_path, 'rb').read()).hexdigest()
    
    if actual != expected:
        raise SourceVerificationError(
            f"Source hash mismatch for {file_path}\n"
            f"Expected: sha256:{expected}\n"
            f"Actual:   sha256:{actual}\n\n"
            f"Possible causes:\n"
            f"  - Source file changed (upstream)\n"
            f"  - Network corruption\n"
            f"  - Attacker tampering\n\n"
            f"Action: Download source manually and verify hash with 'sha256sum'"
        )
    
    logger.info(f"Source hash verified: {file_path}")
```

**Tests:**
- Valid download and hash verification passes
- Hash mismatch detected and error raised
- Network timeout handled gracefully
- Clear error message on failure
- File cleanup on verification failure

### 3. Build Template System

**File:** `src/kod/system/build_templates.py` (new)

Predefined templates generate build commands from package config:

```python
class BuildTemplate:
    """Base class for build templates."""
    
    def generate_commands(self, pkg_def):
        """Generate list of shell commands to build package.
        
        Args:
            pkg_def: Package definition dict
            
        Returns:
            List of shell commands (strings)
        """
        raise NotImplementedError

class AutotoolsTemplate(BuildTemplate):
    """Autotools (configure, make, make install) template."""
    
    def generate_commands(self, pkg_def):
        commands = [
            "cd $builddir",
            "./configure " + pkg_def.get('build_flags', '--prefix=/usr'),
            "make -j$(nproc)",
            "make install DESTDIR=$destdir",
        ]
        return commands

class CMakeTemplate(BuildTemplate):
    """CMake template."""
    
    def generate_commands(self, pkg_def):
        commands = [
            "cd $builddir",
            "cmake . -DCMAKE_INSTALL_PREFIX=/usr " + pkg_def.get('build_flags', ''),
            "make -j$(nproc)",
            "make install DESTDIR=$destdir",
        ]
        return commands

class MakeTemplate(BuildTemplate):
    """Simple make template."""
    
    def generate_commands(self, pkg_def):
        commands = [
            "cd $builddir",
            "make " + pkg_def.get('build_flags', ''),
            "make install PREFIX=/usr DESTDIR=$destdir",
        ]
        return commands

class CustomTemplate(BuildTemplate):
    """Custom commands from package definition."""
    
    def generate_commands(self, pkg_def):
        if 'build_commands' not in pkg_def:
            raise ValueError("Custom template requires 'build_commands' in package def")
        return pkg_def['build_commands']

TEMPLATES = {
    'autotools': AutotoolsTemplate(),
    'cmake': CMakeTemplate(),
    'make': MakeTemplate(),
    'custom': CustomTemplate(),
}
```

**Tests:**
- Autotools template generates correct commands
- CMake template generates correct commands
- Make template generates correct commands
- Custom template uses provided commands
- Invalid template name raises error
- Build flags properly interpolated
- Variable substitution ($builddir, $destdir) works

### 4. User Approval Workflow

**File:** `src/kod/system/packages_custom.py` (new function)

```python
def show_and_approve_build(pkg_def, commands):
    """Show build commands and get user approval.
    
    Args:
        pkg_def: Package definition
        commands: List of commands to execute
        
    Returns:
        bool: True if user approved, False if cancelled
    """
    print(f"\n{'='*70}")
    print(f"Custom Package Build: {pkg_def['name']} v{pkg_def['version']}")
    print(f"{'='*70}\n")
    
    print(f"Source: {pkg_def['source']}")
    print(f"Hash:   {pkg_def['source_hash']}")
    print(f"Template: {pkg_def['template']}")
    if 'build_flags' in pkg_def:
        print(f"Build flags: {pkg_def['build_flags']}")
    
    print(f"\nBuild commands:")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")
    
    print(f"\n{'='*70}")
    
    while True:
        response = input("Review these commands. Proceed with build? [y/N] ").strip().lower()
        if response == 'y':
            logger.info(f"User approved build for {pkg_def['name']} v{pkg_def['version']}")
            return True
        elif response in ('n', ''):
            logger.info(f"User cancelled build for {pkg_def['name']} v{pkg_def['version']}")
            return False
        else:
            print("Please enter 'y' or 'n'")
```

**Tests:**
- Approval UI shows all necessary information
- User can approve with 'y'
- User can reject with 'n' or Enter
- Invalid input prompts again
- Approval logged to audit trail
- Build proceeds on approval
- Build cancelled on rejection

### 5. Basic Package Caching

**File:** `src/kod/system/package_cache.py` (new)

```python
import json
from pathlib import Path
import hashlib

CACHE_DIR = Path.home() / ".kod" / "package-cache"

def get_cache_path(pkg_def):
    """Get cache file path for package.
    
    Cache filename: {name}-{version}-{template_hash}.tar.gz
    Where template_hash is hash of (template + build_flags)
    """
    cache_key = f"{pkg_def['template']}:{pkg_def.get('build_flags', '')}"
    cache_hash = hashlib.md5(cache_key.encode()).hexdigest()[:8]
    return CACHE_DIR / f"{pkg_def['name']}-{pkg_def['version']}-{cache_hash}.tar.gz"

def get_cache_metadata_path(pkg_def):
    """Get metadata file path (.json)."""
    return get_cache_path(pkg_def).with_suffix('.tar.gz.json')

def save_to_cache(pkg_def, build_output_path):
    """Save built package to cache.
    
    Args:
        pkg_def: Package definition
        build_output_path: Path to built package tarball
        
    Returns:
        Path to cached package
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    cache_path = get_cache_path(pkg_def)
    shutil.copy2(build_output_path, cache_path)
    
    # Save metadata
    metadata = {
        'name': pkg_def['name'],
        'version': pkg_def['version'],
        'source': pkg_def['source'],
        'source_hash': pkg_def['source_hash'],
        'template': pkg_def['template'],
        'build_flags': pkg_def.get('build_flags'),
        'cached_at': datetime.now().isoformat(),
    }
    
    with open(get_cache_metadata_path(pkg_def), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Cached package: {cache_path}")
    return cache_path

def get_from_cache(pkg_def):
    """Get package from cache if valid.
    
    Checks if cache exists and metadata matches current definition.
    
    Returns:
        Path to cached package, or None if not cached/invalid
    """
    cache_path = get_cache_path(pkg_def)
    metadata_path = get_cache_metadata_path(pkg_def)
    
    if not cache_path.exists() or not metadata_path.exists():
        return None
    
    # Verify metadata matches current definition
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Check if any build-affecting field changed
    if (metadata['source'] != pkg_def['source'] or
        metadata['source_hash'] != pkg_def['source_hash'] or
        metadata['template'] != pkg_def['template'] or
        metadata.get('build_flags') != pkg_def.get('build_flags')):
        
        logger.info(f"Cache invalidated for {pkg_def['name']}: definition changed")
        cache_path.unlink()
        metadata_path.unlink()
        return None
    
    logger.info(f"Using cached package: {cache_path}")
    return cache_path
```

**Tests:**
- Cache saved with correct filename and metadata
- Cache retrieved when definition unchanged
- Cache invalidated when source changes
- Cache invalidated when hash changes
- Cache invalidated when template changes
- Cache invalidated when build_flags change
- Cache directory created if needed
- Metadata file format valid JSON

### 6. Audit Logging

**File:** `src/kod/system/package_audit.py` (new)

```python
import json
import logging
from pathlib import Path
from datetime import datetime

AUDIT_LOG = Path.home() / ".kod" / "package-build.log"

def log_build_event(event_type, pkg_def, status, details=None):
    """Log a build event to audit trail.
    
    Args:
        event_type: 'START', 'SUCCESS', 'FAILED', 'CANCELLED'
        pkg_def: Package definition
        status: Status message
        details: Additional details dict
    """
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event': event_type,
        'package': pkg_def['name'],
        'version': pkg_def['version'],
        'source': pkg_def['source'],
        'source_hash': pkg_def['source_hash'],
        'template': pkg_def['template'],
        'build_flags': pkg_def.get('build_flags'),
        'status': status,
        'details': details or {},
    }
    
    with open(AUDIT_LOG, 'a') as f:
        json.dump(log_entry, f)
        f.write('\n')
    
    logger = logging.getLogger('audit')
    logger.info(f"{event_type}: {pkg_def['name']} v{pkg_def['version']} - {status}")

def get_audit_log(package_name=None):
    """Read audit log.
    
    Args:
        package_name: Filter by package name, or None for all
        
    Returns:
        List of log entries
    """
    if not AUDIT_LOG.exists():
        return []
    
    entries = []
    with open(AUDIT_LOG, 'r') as f:
        for line in f:
            entry = json.loads(line)
            if package_name is None or entry['package'] == package_name:
                entries.append(entry)
    
    return entries
```

**Tests:**
- Build event logged with all fields
- Audit log file created if needed
- Multiple entries appended correctly
- Log entries valid JSON
- Filter by package_name works
- Sensitive info (hashes) included
- Timestamps recorded

---

## Phase 5b: Enhanced Implementation

### 1. Bubblewrap Sandbox Integration

**File:** `src/kod/system/build_sandbox.py` (new)

```python
import subprocess
import tempfile
from pathlib import Path

def create_sandbox_command(inner_command, build_dir, install_dir):
    """Wrap a build command in bubblewrap sandbox.
    
    Args:
        inner_command: Shell command to run
        build_dir: Directory containing extracted source
        install_dir: Directory where install goes
        
    Returns:
        Full bwrap command line
    """
    cmd = [
        'bwrap',
        '--ro-bind', '/', '/',           # Root FS read-only
        '--bind', str(build_dir), '/tmp/build',  # Bind writable build dir
        '--bind', str(install_dir), '/tmp/install',  # Bind writable install dir
        '--proc', '/proc',               # Mount proc
        '--dev', '/dev',                 # Mount dev
        '--tmpfs', '/tmp',               # Temp tmpfs
        '--unshare-all',                 # Isolate completely
        '--',
        '/bin/sh', '-c', inner_command,
    ]
    
    return cmd

def run_sandboxed_build(commands, pkg_def):
    """Run build commands in bubblewrap sandbox.
    
    Args:
        commands: List of shell commands
        pkg_def: Package definition (for logging)
        
    Returns:
        Tuple of (success, output)
    """
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        build_dir = Path(tmpdir) / "build"
        install_dir = Path(tmpdir) / "install"
        build_dir.mkdir()
        install_dir.mkdir()
        
        # Adjust commands for sandbox paths
        sandboxed_commands = []
        for cmd in commands:
            # Replace $builddir and $destdir with sandbox paths
            cmd = cmd.replace('$builddir', '/tmp/build')
            cmd = cmd.replace('$destdir', '/tmp/install')
            sandboxed_commands.append(cmd)
        
        # Run all commands in one sandbox session
        full_command = ' && '.join(sandboxed_commands)
        sandbox_cmd = create_sandbox_command(
            full_command,
            build_dir,
            install_dir
        )
        
        try:
            result = subprocess.run(
                sandbox_cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            logger.info(f"Sandboxed build succeeded: {pkg_def['name']}")
            return True, result.stdout
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Sandboxed build failed: {e.stderr}")
            return False, e.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Sandboxed build timeout")
            return False, "Build exceeded 1 hour timeout"
        except Exception as e:
            logger.error(f"Sandbox error: {e}")
            return False, str(e)
```

**Tests:**
- Bubblewrap installed and available
- Sandbox command generated correctly
- Build runs isolated (can't access /root)
- Build can write to tmpdir
- Output captured correctly
- Timeout detected
- Clear error messages

### 2. Cache Integrity Verification

**File:** `src/kod/system/package_cache.py` (enhanced)

```python
def verify_cache_integrity(cache_path, metadata_path):
    """Verify cached package hasn't been tampered with.
    
    Args:
        cache_path: Path to cached package file
        metadata_path: Path to metadata file
        
    Returns:
        Tuple of (valid, message)
    """
    if not cache_path.exists():
        return False, f"Cache file not found: {cache_path}"
    
    if not metadata_path.exists():
        return False, f"Cache metadata not found: {metadata_path}"
    
    # Compute hash of cache file
    actual_hash = hashlib.sha256(open(cache_path, 'rb').read()).hexdigest()
    
    # Load metadata
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Check stored hash
    stored_hash = metadata.get('cache_hash')
    if stored_hash is None:
        # Cache predates integrity checking, compute and store
        metadata['cache_hash'] = actual_hash
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        return True, "Cache integrity baseline established"
    
    if actual_hash != stored_hash:
        logger.warning(f"Cache tampering detected: {cache_path}")
        return False, (
            f"Cache file has been modified!\n"
            f"Expected hash: {stored_hash}\n"
            f"Actual hash:   {actual_hash}\n"
            f"Cache invalidated. Package will be rebuilt."
        )
    
    return True, "Cache integrity verified"
```

**Tests:**
- Integrity check passes for unmodified cache
- Tampering detected if file changed
- Clear error message on tamper
- Baseline established for old caches
- Check works with missing metadata

### 3. Enhanced Error Messages

Error messages throughout both phases provide:
- **What happened:** Clear description of the error
- **Why it happened:** Root cause or possible causes
- **What to do:** Actionable steps to resolve

Examples:
```
Source hash mismatch!
  Expected: sha256:abc123...
  Actual:   sha256:def456...
  
Possible causes:
  - Upstream source file changed
  - Network corruption during download
  - Attacker tampering with source
  
Action: Download source manually and verify hash with 'sha256sum'
```

**Tests:**
- All error paths have descriptive messages
- Messages include context (package name, version, etc.)
- Action items are clear and specific
- No cryptic Python tracebacks exposed to user

### 4. Security Documentation

**File:** `docs/SECURITY.md` (new, 800+ lines)

Comprehensive guide including:
- Threat model overview
- Best practices for users
- How to verify sources
- How to review build commands
- Cache security model
- Audit log interpretation
- FAQs and troubleshooting

---

## Data Flow Examples

### Example 1: Building a Custom Package (5a)

```
1. User adds to config.lua:
   {
     name = "hello",
     version = "2.12",
     source = "https://ftp.gnu.org/gnu/hello/hello-2.12.tar.gz",
     source_hash = "sha256:8cf06e933b0e18b87bcc3a8e8f4e73a6a3f82c37e4a2aab1c09e1cf0...",
     template = "autotools",
   }

2. User runs: kod package build -n hello

3. System:
   a. Validates schema (OK)
   b. Checks cache - miss (not cached)
   c. Downloads source (from URL)
   d. Verifies SHA256 (matches!)
   e. Extracts source
   f. Generates build commands (via autotools template)
   g. Shows commands to user
   h. Waits for approval (user presses 'y')
   i. Logs to audit trail: BUILD_STARTED
   j. Runs build commands
   k. Captures output
   l. Creates package tarball
   m. Saves to cache with metadata
   n. Logs to audit trail: BUILD_SUCCESS
   
4. Package ready for installation
```

### Example 2: Hash Verification Failure (5a)

```
1. User updates config with different source

2. System:
   a. Downloads new source
   b. Computes hash: sha256:fedcba9876543210...
   c. Compares to expected: sha256:8cf06e933b0e18b87bcc...
   d. MISMATCH!
   e. Raises SourceVerificationError with:
      - Expected hash
      - Actual hash
      - Possible causes
      - Action items
   f. Logs to audit trail: HASH_MISMATCH
   g. Cleans up downloaded file
   h. Build aborted

3. User investigates (checks upstream, recomputes hash, etc.)
```

### Example 3: Cache Integrity Check (5b)

```
1. User runs: kod package build -n hello

2. System:
   a. Checks cache - HIT
   b. Loads metadata
   c. Verifies cache file hash
   d. TAMPERING DETECTED!
   e. Logs warning
   f. Deletes corrupted cache
   g. Proceeds to rebuild package
```

---

## Testing Strategy

### Phase 5a Tests

**Unit Tests** (mocked, fast):
- Schema validation (valid/invalid cases)
- Hash verification (match/mismatch)
- Template command generation (all template types)
- Cache metadata (valid/invalid)
- Audit logging (entries formatted correctly)

**Integration Tests** (real builds, slower):
- End-to-end build of simple package (hello-world)
- Source download and verification
- Cache save and retrieval
- Audit trail correctness
- Build cancellation by user

**Test Fixtures:**
- Mock web server for source downloads
- Temporary directories for cache/logs
- Sample package definitions (hello, figlet, etc.)

### Phase 5b Tests

**Unit Tests** (mocked):
- Sandbox command generation
- Cache integrity computation

**Integration Tests** (real, slower):
- Build in sandbox (verify isolation)
- Cache tampering detection
- Error message clarity

### Test Coverage Target

- **Phase 5a:** 85%+ of new code
- **Phase 5b:** 85%+ of new code
- **Total:** 422+ tests passing (maintained from Phase 4)

---

## Success Criteria

### Phase 5a Acceptance

- [ ] All custom package schema fields validated
- [ ] Source download works via HTTPS
- [ ] SHA256 verification detects tampering
- [ ] Build templates generate correct commands
- [ ] User approval workflow blocks/allows builds correctly
- [ ] Packages cached with valid metadata
- [ ] Audit log contains all build events
- [ ] All 5a unit tests passing
- [ ] All 5a integration tests passing
- [ ] Zero regressions (422 tests from Phase 4 still passing)
- [ ] Code reviewed by tech lead
- [ ] Merged to main branch

### Phase 5b Acceptance

- [ ] Bubblewrap sandbox available on test system
- [ ] Builds run isolated (can't access system outside tmpdir)
- [ ] Cache integrity checks detect tampering
- [ ] Enhanced error messages are clear and actionable
- [ ] Security documentation complete and reviewed
- [ ] All 5b unit tests passing
- [ ] All 5b integration tests passing
- [ ] Zero regressions (existing tests still passing)
- [ ] Code reviewed by tech lead
- [ ] Merged to main branch

---

## Timeline & Effort

### Phase 5a: MVP (4-5 hours)
- Schema & validation: 30 min
- Download & hash verification: 45 min
- Build templates: 1 hour
- Approval workflow: 45 min
- Caching: 1 hour
- Audit logging: 45 min
- Testing (unit + integration): 1.5 hours

### Phase 5b: Enhanced (4-5 hours)
- Sandbox integration: 1.5 hours
- Cache integrity: 1 hour
- Error messages: 1 hour
- Security documentation: 1 hour
- Testing (unit + integration): 1.5 hours

**Total: 8-10 hours**

---

## Risk Assessment

### Risks in 5a

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Download timeout | Medium | Low | Configurable timeout, clear error |
| User confusion on approval | Medium | Low | Clear UI, option to review docs |
| Cache invalidation bugs | Low | Medium | Comprehensive testing |
| Audit log corruption | Low | Medium | Line-delimited JSON format |

### Risks in 5b

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Sandbox unavailable (old OS) | Medium | Low | Graceful fallback to 5a |
| Sandbox escapes possible | Low | High | Thorough testing, clear warnings |
| Tamper detection false positives | Low | Medium | Comprehensive test coverage |

---

## Dependencies & Requirements

### Phase 5a
- Python 3.14+ (already required)
- urllib (stdlib)
- hashlib (stdlib)
- json (stdlib)
- tempfile (stdlib)
- No new external dependencies

### Phase 5b
- bubblewrap (external, optional)
- Same as 5a otherwise

### System Requirements
- HTTPS support (curl/urllib)
- Temporary directory access
- Home directory access (~/.kod/)

---

## Future Work (Phase 5c)

Not in scope for this plan, but documented for future:
- Nix sandbox integration (reproducible builds)
- Plugin security sandboxing
- Binary package signing
- Package registry / marketplace

---

## Open Questions for Review

1. Should 5a support custom build commands, or defer to 5b?
   - **Recommendation:** Support in 5a (users may need custom templates)

2. Cache location: ~/.kod/package-cache or /var/cache/kod/?
   - **Recommendation:** ~/.kod/ (user-owned, portable)

3. Audit log retention: keep forever, rotate, archive?
   - **Recommendation:** Keep forever for security audit trail

4. Max download timeout and max build timeout values?
   - **Recommendation:** 5 min download, 1 hour build

---

## Approval Checklist

- [ ] Approach A (linear sequential) approved
- [ ] Phase 5a scope clear and approved
- [ ] Phase 5b scope clear and approved
- [ ] Architecture and data flow understood
- [ ] Test strategy adequate
- [ ] Risk assessment reviewed
- [ ] Ready to proceed with Phase 5a implementation plan
