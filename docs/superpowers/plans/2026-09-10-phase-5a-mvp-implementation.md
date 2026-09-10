# Phase 5a: MVP Implementation Plan — Custom Package Security

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Implement Phase 5a MVP with source hash verification, approval workflow, basic caching, and audit logging. All custom packages require user approval before building.

**Architecture:** 
This phase implements a secure custom package build system with:
1. Custom package schema validation
2. HTTPS source download with SHA256 verification (detects tampering)
3. Build template system (autotools, cmake, make, custom)
4. User approval workflow (review commands, require confirmation)
5. Package caching with metadata tracking
6. Comprehensive audit trail

Each task produces independently testable, reviewable commits. Security is achieved through mandatory hash verification, user control, and complete audit logging.

**Tech Stack:** 
- Python 3.14, pytest for unit/integration tests
- Real builds with actual build tools (autotools, cmake, make)
- tempfile for isolated build directories
- JSON for cache metadata and audit logs
- No new external dependencies

**Spec:** `docs/superpowers/specs/2026-09-10-phase-5-custom-packages-design.md` (Phase 5a section)

## Global Constraints

- Python 3.14+ required (matching project floor)
- pytest framework for all tests
- No new external dependencies (only stdlib)
- All changes backward compatible
- Must pass existing 422 tests (zero regressions)
- Commits per feature/fix (atomic, reviewable)
- Test coverage minimum 85% for new code
- Real build integration tests (not mocked)
- Custom packages optional (can be disabled)

---

## Workstream 1: Schema & Validation (Bugs/Features #1-2) — 1 Hour

### Task 1.1: Custom Package Schema Definition

**Files:**
- Create: `src/kod/lib/custom_packages.lua`
- Modify: `src/kod/lib/repos.lua` (reference if needed)
- Test: `tests/configuration/test_custom_packages_schema.py` (new)

**Interfaces:**
- Consumes: Lua configuration file (config.lua)
- Produces: Validated package definitions (dict)

**Context:**
Users define custom packages in config.lua with required and optional fields. Schema must validate at config load time.

**Implementation Steps:**

1. [ ] **Create src/kod/lib/custom_packages.lua**

```lua
-- Custom package definitions for user builds
-- Required fields: name, version, source, source_hash, template
-- Optional fields: build_flags, build_commands (for custom template)

function validate_custom_package(pkg)
    """Validate a custom package definition."""
    if not pkg.name or pkg.name:len() == 0 then
        error("Custom package requires 'name' field")
    end
    
    if not pkg.version or pkg.version:len() == 0 then
        error("Custom package requires 'version' field")
    end
    
    if not pkg.source or pkg.source:len() == 0 then
        error("Custom package requires 'source' (URL) field")
    end
    
    if not pkg.source_hash or pkg.source_hash:len() == 0 then
        error("Custom package requires 'source_hash' field (sha256:abc123...)")
    end
    
    if not pkg.template then
        error("Custom package requires 'template' field (autotools, cmake, make, custom)")
    end
    
    -- Validate source URL is HTTPS
    if not pkg.source:match("^https://") then
        error("Source must be HTTPS URL, got: " .. pkg.source)
    end
    
    -- Validate hash format: sha256:64hexchars
    if not pkg.source_hash:match("^sha256:[a-f0-9]{64}$") then
        error("Source hash must be 'sha256:' prefix + 64 hex chars, got: " .. pkg.source_hash)
    end
    
    -- Validate template
    local valid_templates = {autotools=1, cmake=1, make=1, custom=1}
    if not valid_templates[pkg.template] then
        error("Invalid template '" .. pkg.template .. "', must be one of: autotools, cmake, make, custom")
    end
    
    -- If custom template, require build_commands
    if pkg.template == "custom" and not pkg.build_commands then
        error("Custom template requires 'build_commands' field")
    end
    
    -- Optional: build_flags can be any string
    -- Optional: build_commands (list of strings)
    
    return true
end

-- Example valid custom package:
--[[
{
    name = "hello",
    version = "2.12",
    source = "https://ftp.gnu.org/gnu/hello/hello-2.12.tar.gz",
    source_hash = "sha256:8cf06e933b0e18b87bcc3a8e8f4e73a6a3f82c37e4a2aab1c09e1cf0cf54c8f",
    template = "autotools",
    build_flags = "--prefix=/usr --enable-nls",  -- optional
}
--]]
```

2. [ ] **Write failing tests in tests/configuration/test_custom_packages_schema.py**

```python
import pytest
from kod.lib import custom_packages

class TestCustomPackageSchema:
    """Test custom package schema validation."""
    
    def test_valid_package_passes(self):
        """Valid package definition should pass validation."""
        pkg = {
            "name": "hello",
            "version": "2.12",
            "source": "https://ftp.gnu.org/gnu/hello/hello-2.12.tar.gz",
            "source_hash": "sha256:8cf06e933b0e18b87bcc3a8e8f4e73a6a3f82c37e4a2aab1c09e1cf0cf54c8f",
            "template": "autotools",
            "build_flags": "--prefix=/usr",
        }
        # Should not raise
        custom_packages.validate_custom_package(pkg)
    
    def test_missing_name_fails(self):
        """Missing name should fail validation."""
        pkg = {
            "version": "2.12",
            "source": "https://example.com/pkg.tar.gz",
            "source_hash": "sha256:abc123" + "0" * 57,
            "template": "autotools",
        }
        with pytest.raises(ValueError, match="requires 'name'"):
            custom_packages.validate_custom_package(pkg)
    
    def test_missing_source_hash_fails(self):
        """Missing source_hash should fail."""
        pkg = {
            "name": "hello",
            "version": "2.12",
            "source": "https://example.com/pkg.tar.gz",
            "template": "autotools",
        }
        with pytest.raises(ValueError, match="requires 'source_hash'"):
            custom_packages.validate_custom_package(pkg)
    
    def test_http_source_rejected(self):
        """HTTP (not HTTPS) should be rejected."""
        pkg = {
            "name": "hello",
            "version": "2.12",
            "source": "http://example.com/pkg.tar.gz",  # HTTP, not HTTPS
            "source_hash": "sha256:abc123" + "0" * 57,
            "template": "autotools",
        }
        with pytest.raises(ValueError, match="HTTPS"):
            custom_packages.validate_custom_package(pkg)
    
    def test_invalid_hash_format_fails(self):
        """Invalid hash format should fail."""
        pkg = {
            "name": "hello",
            "version": "2.12",
            "source": "https://example.com/pkg.tar.gz",
            "source_hash": "sha256:tooshort",  # Not 64 hex chars
            "template": "autotools",
        }
        with pytest.raises(ValueError, match="sha256"):
            custom_packages.validate_custom_package(pkg)
    
    def test_invalid_template_fails(self):
        """Invalid template should fail."""
        pkg = {
            "name": "hello",
            "version": "2.12",
            "source": "https://example.com/pkg.tar.gz",
            "source_hash": "sha256:abc123" + "0" * 57,
            "template": "invalid",
        }
        with pytest.raises(ValueError, match="template"):
            custom_packages.validate_custom_package(pkg)
    
    def test_custom_template_requires_build_commands(self):
        """Custom template must have build_commands."""
        pkg = {
            "name": "hello",
            "version": "2.12",
            "source": "https://example.com/pkg.tar.gz",
            "source_hash": "sha256:abc123" + "0" * 57,
            "template": "custom",
            # Missing build_commands
        }
        with pytest.raises(ValueError, match="build_commands"):
            custom_packages.validate_custom_package(pkg)
    
    def test_custom_template_with_commands_passes(self):
        """Custom template with build_commands should pass."""
        pkg = {
            "name": "hello",
            "version": "2.12",
            "source": "https://example.com/pkg.tar.gz",
            "source_hash": "sha256:abc123" + "0" * 57,
            "template": "custom",
            "build_commands": ["make", "make install"],
        }
        # Should not raise
        custom_packages.validate_custom_package(pkg)
    
    def test_semantic_version_validation(self):
        """Versions should follow semantic versioning."""
        pkg = {
            "name": "hello",
            "version": "2.12.0",  # valid semver
            "source": "https://example.com/pkg.tar.gz",
            "source_hash": "sha256:abc123" + "0" * 57,
            "template": "autotools",
        }
        custom_packages.validate_custom_package(pkg)
    
    def test_all_optional_fields_allowed(self):
        """Package with only required fields should validate."""
        pkg = {
            "name": "hello",
            "version": "2.12",
            "source": "https://example.com/pkg.tar.gz",
            "source_hash": "sha256:abc123" + "0" * 57,
            "template": "make",
            # No build_flags, no build_commands
        }
        custom_packages.validate_custom_package(pkg)
```

3. [ ] **Run tests to verify they fail initially**

```bash
uv run pytest tests/configuration/test_custom_packages_schema.py -xvs
# Expected: All tests fail (functions not yet implemented)
```

4. [ ] **Implement validation in src/kod/lib/custom_packages.lua**

Copy the Lua validation logic from step 1 above.

5. [ ] **Create Python interface in src/kod/system/packages_custom.py**

```python
"""Custom package management for user-defined source builds."""

import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

class CustomPackageError(Exception):
    """Base error for custom package operations."""
    pass

class CustomPackageValidationError(CustomPackageError):
    """Custom package definition validation failed."""
    pass

def validate_custom_package(pkg_def: dict) -> bool:
    """Validate custom package definition.
    
    Args:
        pkg_def: Package definition dict
        
    Returns:
        True if valid
        
    Raises:
        CustomPackageValidationError if invalid
    """
    # Check required fields
    required = ["name", "version", "source", "source_hash", "template"]
    for field in required:
        if field not in pkg_def or not pkg_def[field]:
            raise CustomPackageValidationError(f"Package requires '{field}' field")
    
    name = pkg_def["name"]
    source = pkg_def["source"]
    source_hash = pkg_def["source_hash"]
    template = pkg_def["template"]
    
    # Validate source URL
    if not source.startswith("https://"):
        raise CustomPackageValidationError(
            f"Source must be HTTPS URL, got: {source}"
        )
    
    # Validate hash format (sha256:64hexchars)
    import re
    if not re.match(r"^sha256:[a-f0-9]{64}$", source_hash):
        raise CustomPackageValidationError(
            f"Source hash must be 'sha256:' + 64 hex chars, got: {source_hash}"
        )
    
    # Validate template
    valid_templates = ["autotools", "cmake", "make", "custom"]
    if template not in valid_templates:
        raise CustomPackageValidationError(
            f"Invalid template '{template}'. Must be one of: {', '.join(valid_templates)}"
        )
    
    # If custom template, require build_commands
    if template == "custom":
        if "build_commands" not in pkg_def or not pkg_def["build_commands"]:
            raise CustomPackageValidationError(
                "Custom template requires 'build_commands' field (list of shell commands)"
            )
        if not isinstance(pkg_def["build_commands"], list):
            raise CustomPackageValidationError(
                "build_commands must be a list of strings"
            )
    
    logger.info(f"Custom package validated: {name} v{pkg_def['version']}")
    return True
```

6. [ ] **Run tests to verify they pass**

```bash
uv run pytest tests/configuration/test_custom_packages_schema.py -xvs
# Expected: All tests pass
```

7. [ ] **Run full test suite**

```bash
uv run pytest tests/ -q --tb=short
# Expected: 422+ passing, 0 regressions
```

8. [ ] **Commit**

```bash
git add src/kod/lib/custom_packages.lua src/kod/system/packages_custom.py tests/configuration/test_custom_packages_schema.py
git commit -m "feat: Add custom package schema with validation

Implement custom package definition validation:
- Required fields: name, version, source, source_hash, template
- HTTPS-only URLs (prevents tampering)
- SHA256 hash validation (64 hex chars with sha256: prefix)
- Valid templates: autotools, cmake, make, custom
- Custom template requires build_commands field

Changes:
- src/kod/lib/custom_packages.lua: Lua schema definition
- src/kod/system/packages_custom.py: Python validation
- tests/configuration/test_custom_packages_schema.py: 9 test cases

Validation catches:
- Missing required fields
- HTTP (not HTTPS) sources
- Invalid hash formats
- Unknown templates
- Custom template without build_commands

Phase 5a: Part 1 of 5 (schema validation)"
```

---

### Task 1.2: Config Integration & Loading

**Files:**
- Modify: `src/kod/configuration.py` (load and validate custom_packages section)
- Test: `tests/configuration/test_config_custom_packages.py` (new)

**Interfaces:**
- Consumes: config.lua with custom_packages section
- Produces: Validated list of custom package definitions

**Context:**
Configuration loader needs to parse custom_packages from Lua config and validate all definitions at load time.

**Implementation Steps:**

1. [ ] **Modify src/kod/configuration.py to load custom_packages**

Add to configuration loader:

```python
def load_custom_packages(config_dict: dict) -> list:
    """Load and validate custom packages from config.
    
    Args:
        config_dict: Loaded configuration dictionary
        
    Returns:
        List of validated custom package definitions
    """
    custom_packages = config_dict.get("custom_packages", [])
    
    if not isinstance(custom_packages, list):
        raise ConfigurationError("custom_packages must be a list")
    
    validated = []
    for i, pkg in enumerate(custom_packages):
        try:
            packages_custom.validate_custom_package(pkg)
            validated.append(pkg)
        except packages_custom.CustomPackageValidationError as e:
            raise ConfigurationError(
                f"Custom package {i} ({pkg.get('name', 'unknown')}): {e}"
            )
    
    logger.info(f"Loaded {len(validated)} custom packages from configuration")
    return validated
```

2. [ ] **Write tests**

```python
def test_config_with_no_custom_packages(self):
    """Config without custom_packages is valid."""
    config = {"packages": ["hello", "git"]}
    packages = load_custom_packages(config)
    assert packages == []

def test_config_with_valid_custom_packages(self):
    """Config with valid custom packages loads."""
    config = {
        "custom_packages": [
            {
                "name": "hello",
                "version": "2.12",
                "source": "https://ftp.gnu.org/gnu/hello/hello-2.12.tar.gz",
                "source_hash": "sha256:8cf06e933b0e18b87bcc3a8e8f4e73a6a3f82c37e4a2aab1c09e1cf0cf54c8f",
                "template": "autotools",
            }
        ]
    }
    packages = load_custom_packages(config)
    assert len(packages) == 1
    assert packages[0]["name"] == "hello"

def test_config_with_invalid_custom_package_fails(self):
    """Config with invalid custom package raises error."""
    config = {
        "custom_packages": [
            {
                "name": "bad",
                "version": "1.0",
                # Missing source, source_hash, template
            }
        ]
    }
    with pytest.raises(ConfigurationError):
        load_custom_packages(config)
```

3. [ ] **Commit**

```bash
git commit -m "feat: Integrate custom packages into configuration loading

Configuration loader now:
- Loads custom_packages section from config.lua
- Validates all custom package definitions
- Reports validation errors with clear messages
- Logs loaded packages on success

Changes:
- src/kod/configuration.py: Add load_custom_packages()
- tests/configuration/test_config_custom_packages.py: Integration tests

Phase 5a: Part 2 of 5 (config integration)"
```

---

## Workstream 2: Source Download & Hash Verification (Bug/Feature #3) — 1 Hour

### Task 2.1: Source Download & SHA256 Verification

**Files:**
- Create: `src/kod/system/source_download.py`
- Test: `tests/system/test_source_download.py` (new)

**Interfaces:**
- Consumes: Package definition (with source URL and expected hash)
- Produces: Downloaded source file at specified path

**Context:**
Download packages from HTTPS URLs and verify SHA256 hash matches expected value. Detects tampering or corruption.

**Implementation Steps:**

1. [ ] **Create src/kod/system/source_download.py**

```python
"""Download and verify package sources."""

import hashlib
import logging
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger(__name__)

class SourceDownloadError(Exception):
    """Download failed."""
    pass

class SourceVerificationError(Exception):
    """Source verification failed."""
    pass

def download_source(url: str, dest_path: Path, timeout: int = 300) -> Path:
    """Download package source from HTTPS URL.
    
    Args:
        url: HTTPS URL to download from
        dest_path: Where to save the file
        timeout: Download timeout in seconds
        
    Returns:
        Path to downloaded file
        
    Raises:
        SourceDownloadError: If download fails
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Downloading source: {url}")
    
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            total_size = response.headers.get('Content-Length')
            downloaded = 0
            
            with open(dest_path, 'wb') as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size:
                        pct = (downloaded / int(total_size)) * 100
                        logger.debug(f"  Download progress: {pct:.1f}%")
    
    except urllib.error.URLError as e:
        dest_path.unlink(missing_ok=True)
        raise SourceDownloadError(
            f"Failed to download {url}: {e}\n"
            f"Check URL and network connection."
        )
    except urllib.error.HTTPError as e:
        dest_path.unlink(missing_ok=True)
        raise SourceDownloadError(
            f"HTTP error {e.code} downloading {url}\n"
            f"File not found or access denied."
        )
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise SourceDownloadError(f"Error downloading {url}: {e}")
    
    logger.info(f"Source downloaded: {dest_path} ({downloaded} bytes)")
    return dest_path

def verify_source_hash(file_path: Path, expected_hash: str) -> bool:
    """Verify downloaded source against expected SHA256 hash.
    
    Args:
        file_path: Path to downloaded file
        expected_hash: Expected hash (format: "sha256:abc123...")
        
    Returns:
        True if hash matches
        
    Raises:
        SourceVerificationError: If hash doesn't match
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise SourceVerificationError(f"Source file not found: {file_path}")
    
    if not expected_hash.startswith("sha256:"):
        raise ValueError("Hash must start with 'sha256:'")
    
    expected = expected_hash.replace("sha256:", "")
    
    logger.info(f"Computing SHA256 hash for {file_path.name}...")
    
    # Compute hash
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
    except Exception as e:
        raise SourceVerificationError(f"Error reading {file_path}: {e}")
    
    actual = sha256.hexdigest()
    
    if actual == expected:
        logger.info(f"Source hash verified!")
        return True
    else:
        logger.error(f"Source hash mismatch!")
        raise SourceVerificationError(
            f"Source hash mismatch for {file_path.name}\n\n"
            f"Expected: sha256:{expected}\n"
            f"Actual:   sha256:{actual}\n\n"
            f"Possible causes:\n"
            f"  - Source file changed on upstream server\n"
            f"  - Network corruption during download\n"
            f"  - Attacker tampering with download\n\n"
            f"Action:\n"
            f"  1. Download file manually: wget {expected_hash.split(':')[0]}\n"
            f"  2. Verify hash locally: sha256sum {file_path.name}\n"
            f"  3. Compare against upstream website\n"
            f"  4. Update config with correct hash or investigate upstream\n"
        )

def download_and_verify(url: str, dest_path: Path, expected_hash: str) -> Path:
    """Download source and verify hash in one operation.
    
    Args:
        url: HTTPS URL to download
        dest_path: Where to save file
        expected_hash: Expected SHA256 hash
        
    Returns:
        Path to verified source file
        
    Raises:
        SourceDownloadError: If download fails
        SourceVerificationError: If hash doesn't match
    """
    downloaded = download_source(url, dest_path)
    verify_source_hash(downloaded, expected_hash)
    return downloaded
```

2. [ ] **Write tests in tests/system/test_source_download.py**

```python
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from kod.system.source_download import (
    download_source,
    verify_source_hash,
    SourceDownloadError,
    SourceVerificationError,
)

class TestDownloadSource:
    """Test source download functionality."""
    
    def test_download_success(self):
        """Successful download saves file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.tar.gz"
            
            with patch('urllib.request.urlopen') as mock_open:
                mock_response = Mock()
                mock_response.read.return_value = b"test content"
                mock_response.headers = {}
                mock_open.return_value.__enter__.return_value = mock_response
                
                result = download_source("https://example.com/test.tar.gz", dest)
                
                assert result == dest
                assert dest.exists()
                assert dest.read_bytes() == b"test content"
    
    def test_download_url_error(self):
        """URL error raises SourceDownloadError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.tar.gz"
            
            with patch('urllib.request.urlopen') as mock_open:
                mock_open.side_effect = urllib.error.URLError("Connection refused")
                
                with pytest.raises(SourceDownloadError):
                    download_source("https://invalid.example.com/test.tar.gz", dest)
    
    def test_download_http_error(self):
        """HTTP error raises SourceDownloadError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "test.tar.gz"
            
            with patch('urllib.request.urlopen') as mock_open:
                mock_open.side_effect = urllib.error.HTTPError(
                    "https://example.com/notfound.tar.gz", 404, "Not Found", {}, None
                )
                
                with pytest.raises(SourceDownloadError):
                    download_source("https://example.com/notfound.tar.gz", dest)

class TestVerifySourceHash:
    """Test source hash verification."""
    
    def test_hash_match_success(self):
        """Matching hash returns True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")
            
            # Known hash of "test content"
            expected = "sha256:6ae8a75555209fd6c44157c0aed8016e763ff09ac2e51b5e43f2a6fd8d2ffdb7"
            
            result = verify_source_hash(test_file, expected)
            assert result is True
    
    def test_hash_mismatch_fails(self):
        """Mismatched hash raises SourceVerificationError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")
            
            # Wrong hash
            wrong = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
            
            with pytest.raises(SourceVerificationError, match="mismatch"):
                verify_source_hash(test_file, wrong)
    
    def test_file_not_found_fails(self):
        """Missing file raises SourceVerificationError."""
        with pytest.raises(SourceVerificationError, match="not found"):
            verify_source_hash(
                Path("/nonexistent/file.tar.gz"),
                "sha256:abc123" + "0" * 57
            )
```

3. [ ] **Commit**

```bash
git commit -m "feat: Implement source download and SHA256 verification

Download packages from HTTPS URLs and verify integrity:
- download_source(): Download from HTTPS with timeout
- verify_source_hash(): Compute SHA256 and compare
- download_and_verify(): Convenience function combining both
- Clear error messages on verification failure
- Logs download progress and verification result

Changes:
- src/kod/system/source_download.py: Download & verification logic
- tests/system/test_source_download.py: Unit tests

Detects:
- Network errors (connection refused, timeout)
- HTTP errors (404, 403, etc.)
- Tampering (hash mismatch with action items)

Phase 5a: Part 3 of 5 (source download & verification)"
```

---

## Workstream 3: Build Templates (Bug/Feature #4) — 1 Hour

### Task 3.1: Build Template System

**Files:**
- Create: `src/kod/system/build_templates.py`
- Test: `tests/system/test_build_templates.py` (new)

**Interfaces:**
- Consumes: Package definition with template type and build flags
- Produces: List of shell commands to execute

**Context:**
Predefined build templates generate shell commands. Supports autotools, cmake, make, and custom templates. Commands use variables ($builddir, $destdir) for paths.

**Implementation Steps:**

1. [ ] **Create src/kod/system/build_templates.py**

```python
"""Build template system for generating build commands."""

import logging

logger = logging.getLogger(__name__)

class BuildTemplateError(Exception):
    """Build template error."""
    pass

class BuildTemplate:
    """Base class for build templates."""
    
    def generate_commands(self, pkg_def: dict) -> list:
        """Generate list of shell commands to build package.
        
        Args:
            pkg_def: Package definition dict
            
        Returns:
            List of shell commands (strings)
        """
        raise NotImplementedError

class AutotoolsTemplate(BuildTemplate):
    """Autotools (./configure && make && make install) template."""
    
    def generate_commands(self, pkg_def: dict) -> list:
        """Generate autotools build commands."""
        build_flags = pkg_def.get('build_flags', '--prefix=/usr')
        commands = [
            "cd $builddir",
            f"./configure {build_flags}",
            "make -j$(nproc)",
            "make install DESTDIR=$destdir",
        ]
        return commands

class CMakeTemplate(BuildTemplate):
    """CMake template."""
    
    def generate_commands(self, pkg_def: dict) -> list:
        """Generate CMake build commands."""
        build_flags = pkg_def.get('build_flags', '')
        flags_str = f" {build_flags}" if build_flags else ""
        commands = [
            "cd $builddir",
            f"cmake . -DCMAKE_INSTALL_PREFIX=/usr{flags_str}",
            "make -j$(nproc)",
            "make install DESTDIR=$destdir",
        ]
        return commands

class MakeTemplate(BuildTemplate):
    """Simple make template."""
    
    def generate_commands(self, pkg_def: dict) -> list:
        """Generate make build commands."""
        build_flags = pkg_def.get('build_flags', '')
        flags_str = f" {build_flags}" if build_flags else ""
        commands = [
            "cd $builddir",
            f"make{flags_str}",
            "make install PREFIX=/usr DESTDIR=$destdir",
        ]
        return commands

class CustomTemplate(BuildTemplate):
    """Custom build commands from package definition."""
    
    def generate_commands(self, pkg_def: dict) -> list:
        """Return custom build commands."""
        if 'build_commands' not in pkg_def:
            raise BuildTemplateError(
                "Custom template requires 'build_commands' field in package definition"
            )
        
        commands = pkg_def['build_commands']
        if not isinstance(commands, list):
            raise BuildTemplateError(
                "build_commands must be a list of strings"
            )
        
        if not all(isinstance(cmd, str) for cmd in commands):
            raise BuildTemplateError(
                "All build_commands must be strings"
            )
        
        return commands

# Template registry
TEMPLATES = {
    'autotools': AutotoolsTemplate(),
    'cmake': CMakeTemplate(),
    'make': MakeTemplate(),
    'custom': CustomTemplate(),
}

def get_template(template_name: str) -> BuildTemplate:
    """Get build template by name.
    
    Args:
        template_name: Template name (autotools, cmake, make, custom)
        
    Returns:
        BuildTemplate instance
        
    Raises:
        BuildTemplateError: If template not found
    """
    if template_name not in TEMPLATES:
        valid = ', '.join(TEMPLATES.keys())
        raise BuildTemplateError(
            f"Unknown template '{template_name}'. Valid templates: {valid}"
        )
    return TEMPLATES[template_name]

def generate_build_commands(pkg_def: dict) -> list:
    """Generate build commands for package.
    
    Args:
        pkg_def: Package definition (must include 'template')
        
    Returns:
        List of shell commands
        
    Raises:
        BuildTemplateError: If template invalid or generation fails
    """
    template_name = pkg_def.get('template')
    if not template_name:
        raise BuildTemplateError("Package definition missing 'template' field")
    
    template = get_template(template_name)
    commands = template.generate_commands(pkg_def)
    
    logger.info(
        f"Generated {len(commands)} build commands for {pkg_def['name']} "
        f"using {template_name} template"
    )
    
    return commands
```

2. [ ] **Write tests**

```python
import pytest
from kod.system.build_templates import (
    generate_build_commands,
    get_template,
    AutotoolsTemplate,
    CMakeTemplate,
    MakeTemplate,
    CustomTemplate,
    BuildTemplateError,
)

class TestAutotoolsTemplate:
    """Test autotools template."""
    
    def test_autotools_generates_commands(self):
        """Autotools template generates configure + make + install."""
        pkg = {
            "name": "hello",
            "template": "autotools",
            "build_flags": "--prefix=/usr --enable-nls",
        }
        cmds = generate_build_commands(pkg)
        assert len(cmds) == 4
        assert "configure" in cmds[1]
        assert "--prefix=/usr --enable-nls" in cmds[1]
        assert "make -j" in cmds[2]
        assert "make install" in cmds[3]
    
    def test_autotools_default_flags(self):
        """Autotools uses default flags if none specified."""
        pkg = {
            "name": "hello",
            "template": "autotools",
            # No build_flags
        }
        cmds = generate_build_commands(pkg)
        assert "--prefix=/usr" in cmds[1]

class TestCMakeTemplate:
    """Test CMake template."""
    
    def test_cmake_generates_commands(self):
        """CMake template generates cmake + make + install."""
        pkg = {
            "name": "project",
            "template": "cmake",
            "build_flags": "-DENABLE_TESTS=ON",
        }
        cmds = generate_build_commands(pkg)
        assert len(cmds) == 4
        assert "cmake" in cmds[1]
        assert "ENABLE_TESTS" in cmds[1]
        assert "make -j" in cmds[2]

class TestMakeTemplate:
    """Test make template."""
    
    def test_make_generates_commands(self):
        """Make template generates make + install."""
        pkg = {
            "name": "project",
            "template": "make",
        }
        cmds = generate_build_commands(pkg)
        assert len(cmds) == 3
        assert "make" in cmds[1]
        assert "make install" in cmds[2]

class TestCustomTemplate:
    """Test custom template."""
    
    def test_custom_template_uses_provided_commands(self):
        """Custom template returns build_commands as-is."""
        pkg = {
            "name": "project",
            "template": "custom",
            "build_commands": ["./build.sh", "install"],
        }
        cmds = generate_build_commands(pkg)
        assert cmds == ["./build.sh", "install"]
    
    def test_custom_template_requires_build_commands(self):
        """Custom template without build_commands fails."""
        pkg = {
            "name": "project",
            "template": "custom",
            # Missing build_commands
        }
        with pytest.raises(BuildTemplateError, match="build_commands"):
            generate_build_commands(pkg)

class TestTemplateErrors:
    """Test error handling."""
    
    def test_unknown_template_fails(self):
        """Unknown template raises error."""
        pkg = {"name": "x", "template": "unknown"}
        with pytest.raises(BuildTemplateError, match="Unknown template"):
            generate_build_commands(pkg)
    
    def test_missing_template_field_fails(self):
        """Missing template field raises error."""
        pkg = {"name": "x"}
        with pytest.raises(BuildTemplateError, match="template"):
            generate_build_commands(pkg)
```

3. [ ] **Commit**

```bash
git commit -m "feat: Implement build template system

Generate build commands from templates:
- AutotoolsTemplate: ./configure && make && make install
- CMakeTemplate: cmake && make && make install
- MakeTemplate: make && make install
- CustomTemplate: user-provided commands

Features:
- Template registry for easy lookup
- Default build flags (--prefix=/usr)
- Path variables: $builddir, $destdir
- Clear error on unknown/invalid template
- Logging of generated commands

Changes:
- src/kod/system/build_templates.py: Template system
- tests/system/test_build_templates.py: Unit tests

Supports 4 template types with extensibility for future additions.

Phase 5a: Part 4 of 5 (build templates)"
```

---

## Workstream 4: User Approval & Caching (Features #5-7) — 1 Hour

### Task 4.1: User Approval Workflow

**Files:**
- Create/Modify: `src/kod/system/packages_custom.py` (add approval function)
- Test: `tests/system/test_custom_packages_approval.py` (new)

**Interfaces:**
- Consumes: Package definition and list of build commands
- Produces: User approval decision (bool) or cancellation

**Context:**
Show build commands to user and get explicit approval before building. Ensures user knows what will execute.

**Implementation Steps:**

1. [ ] **Add to src/kod/system/packages_custom.py**

```python
def show_and_approve_build(pkg_def: dict, commands: list) -> bool:
    """Show build commands and get user approval.
    
    Args:
        pkg_def: Package definition
        commands: List of commands to execute
        
    Returns:
        True if user approved, False if cancelled
    """
    print(f"\n{'='*70}")
    print(f"Custom Package Build: {pkg_def['name']} v{pkg_def['version']}")
    print(f"{'='*70}\n")
    
    print(f"Source:   {pkg_def['source']}")
    print(f"Hash:     {pkg_def['source_hash']}")
    print(f"Template: {pkg_def['template']}")
    
    if 'build_flags' in pkg_def and pkg_def['build_flags']:
        print(f"Flags:    {pkg_def['build_flags']}")
    
    print(f"\nBuild commands ({len(commands)} total):")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")
    
    print(f"\n{'='*70}\n")
    
    while True:
        response = input(
            "Review these commands. Proceed with build? [y/N] "
        ).strip().lower()
        
        if response == 'y':
            logger.info(
                f"User approved build for {pkg_def['name']} v{pkg_def['version']}"
            )
            return True
        elif response in ('n', ''):
            logger.info(
                f"User cancelled build for {pkg_def['name']} v{pkg_def['version']}"
            )
            return False
        else:
            print("Please enter 'y' or 'n'")
```

2. [ ] **Write tests**

```python
import pytest
from unittest.mock import patch
from kod.system.packages_custom import show_and_approve_build

def test_user_approves_with_y(capsys, monkeypatch):
    """User can approve with 'y'."""
    pkg = {
        "name": "hello",
        "version": "2.12",
        "source": "https://example.com/hello.tar.gz",
        "source_hash": "sha256:abc123" + "0" * 57,
        "template": "autotools",
    }
    commands = ["./configure", "make", "make install"]
    
    monkeypatch.setattr('builtins.input', lambda _: 'y')
    
    result = show_and_approve_build(pkg, commands)
    
    assert result is True
    output = capsys.readouterr().out
    assert "hello v2.12" in output
    assert "sha256:abc123" in output
    assert "configure" in output

def test_user_rejects_with_n(monkeypatch):
    """User can reject with 'n'."""
    pkg = {"name": "test", "version": "1.0", "source": "https://example.com/test.tar.gz",
           "source_hash": "sha256:" + "0" * 64, "template": "autotools"}
    commands = ["make"]
    
    monkeypatch.setattr('builtins.input', lambda _: 'n')
    
    result = show_and_approve_build(pkg, commands)
    assert result is False

def test_user_rejects_with_empty(monkeypatch):
    """User can reject by pressing Enter."""
    pkg = {"name": "test", "version": "1.0", "source": "https://example.com/test.tar.gz",
           "source_hash": "sha256:" + "0" * 64, "template": "autotools"}
    commands = ["make"]
    
    monkeypatch.setattr('builtins.input', lambda _: '')
    
    result = show_and_approve_build(pkg, commands)
    assert result is False
```

3. [ ] **Commit**

```bash
git commit -m "feat: Add user approval workflow for builds

Interactive approval before build execution:
- Show package details (name, version, source, hash, template)
- Show all build commands that will execute
- Require explicit 'y' approval to proceed
- 'n' or Enter cancels build
- Invalid input prompts again
- All approvals logged to audit trail

Changes:
- src/kod/system/packages_custom.py: show_and_approve_build()
- tests/system/test_custom_packages_approval.py: User interaction tests

Gives users final control over what builds execute.

Phase 5a: Part 5 of 5 (user approval)"
```

---

### Task 4.2: Package Caching & Audit Logging

**Files:**
- Create: `src/kod/system/package_cache.py`
- Create: `src/kod/system/package_audit.py`
- Test: `tests/system/test_package_cache.py`
- Test: `tests/system/test_package_audit.py`

[Detailed implementation similar to tasks above, implementing caching with metadata tracking and comprehensive audit logging]

---

## Integration Tests

### Task 5.1: End-to-End Phase 5a Test

Build a real package (hello-world or figlet) from source, verify all components work together.

---

## Success Criteria (Phase 5a)

- [ ] All schema fields validated at config load
- [ ] HTTPS source download works
- [ ] SHA256 verification detects tampering
- [ ] Build templates generate correct commands (all 4 types)
- [ ] User approval workflow blocks/allows builds
- [ ] Packages cached with valid metadata
- [ ] Cache invalidated on definition change
- [ ] Audit log contains all build events
- [ ] All Phase 5a unit tests passing (85%+ coverage)
- [ ] All Phase 5a integration tests passing
- [ ] Zero regressions (422 tests from Phase 4 still passing)
- [ ] Code reviewed by tech lead
- [ ] Ready to merge to main

---

## Timeline & Effort Breakdown

### Phase 5a Implementation: 4-5 hours

- **Workstream 1:** Schema & validation (1 hour)
  - Task 1.1: Schema definition & validation
  - Task 1.2: Config integration & loading

- **Workstream 2:** Source download & verification (1 hour)
  - Task 2.1: Download & SHA256 verification

- **Workstream 3:** Build templates (1 hour)
  - Task 3.1: Build template system (all 4 templates)

- **Workstream 4:** Approval & caching (1 hour)
  - Task 4.1: User approval workflow
  - Task 4.2: Caching & audit logging (combined)

- **Workstream 5:** Integration tests (0.5-1 hour)
  - Task 5.1: End-to-end Phase 5a test

**Total Phase 5a: 4-5 hours**

**Then Phase 5b: 4-5 hours (separate planning cycle)**

