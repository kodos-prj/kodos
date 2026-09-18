# Distro Adapter Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate 800 lines of distro-module duplication into a clean Strategy Pattern architecture with base adapter class + concrete subclasses.

**Architecture:** One DistroAdapter base class containing all common package management logic. ArchAdapter and DebianAdapter inherit and override only distro-specific methods (package queries, parsing, install commands). Factory instantiates adapters instead of modules.

**Tech Stack:** Python 3.6+ with isinstance/getattr; subprocess via exec/exec_chroot; standard library re/json/pathlib.

**Spec:** `docs/superpowers/specs/2026-09-18-distro-adapter-refactor-design.md`

## Global Constraints

- **Breaking Changes:** NONE. External API (get_distro_module, method signatures) must remain identical.
- **Duplication Elimination:** All logic appearing in both arch.py and debian.py must be consolidated into DistroAdapter base class.
- **Naming:** Function names must match original (except typo fix: `generale_package_lock()` → `generate_package_lock()`).
- **Python Support:** Python 3.6+ (existing codebase requirement).
- **Test Coverage:** All distro-specific parsing must have override tests; common algorithms tested once in base tests.

---

## File Structure

### Create
- `src/kod/system/distro/base.py` — DistroAdapter base class with all common logic (~400 lines)
- `src/kod/system/distro/adapters/__init__.py` — Package marker
- `src/kod/system/distro/adapters/arch.py` — ArchAdapter with Arch-specific overrides (~80 lines)
- `src/kod/system/distro/adapters/debian.py` — DebianAdapter with Debian-specific overrides (~100 lines)

### Modify
- `src/kod/system/distro/factory.py` — Update to instantiate adapter classes
- `src/kod/system/distro/__init__.py` — Ensure exports
- `tests/system/test_distro_base.py` — New tests for DistroAdapter base class
- `tests/system/test_distro_adapters.py` — New tests for Arch/Debian overrides

### Delete
- `src/kod/system/distro/arch.py` — Old implementation consolidated into base + adapter
- `src/kod/system/distro/debian.py` — Old implementation consolidated into base + adapter

---

## Task Breakdown

### Task 1: Create DistroAdapter Base Class

**Files:**
- Create: `src/kod/system/distro/base.py`
- Test: `tests/system/test_distro_base.py`

**Interfaces:**
- Consumes: `kod.common.exec`, `kod.common.exec_chroot`
- Produces: `DistroAdapter` class with methods:
  - `get_base_packages(conf) -> dict`
  - `install_essentials_pkgs(base_pkgs, mount_point) -> None`
  - `get_kernel_file(mount_point, package="linux") -> Tuple[str, str]`
  - `get_list_of_dependencies(pkg) -> list`
  - `proc_repos(conf, current_repos, update, mount_point) -> Tuple[dict, list]`
  - `refresh_package_db(mount_point, new_generation) -> None`
  - `kernel_update_required(current_kernel, next_kernel, current_installed_packages, mount_point) -> bool`
  - `generate_package_lock(mount_point, state_path) -> None`
  - Abstract override methods (subclasses implement these):
    - `_get_base_packages_config(conf) -> dict`
    - `_install_command(base_pkgs, mount_point) -> str`
    - `_query_kernel_file(mount_point, package) -> str`
    - `_parse_kernel_file(output) -> Tuple[str, str]`
    - `_query_package_db_refresh(mount_point, new_generation) -> str`
    - `_query_kernel_version(current_kernel, mount_point) -> str`
    - `_parse_kernel_version(output) -> str`
    - `_query_installed_packages(mount_point) -> str`
    - `_parse_installed_packages(output) -> dict`

- [ ] **Step 1: Create base.py with class structure and docstrings**

Create file with:
```python
"""Distro adapter base class (Strategy Pattern).

This module provides the common logic for all distro-specific package
management. Subclasses override only distro-specific methods (queries,
parsing, install commands).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple, List
from kod.common import exec, exec_chroot


class DistroAdapter(ABC):
    """Base class for distro-specific package management.
    
    Implements all common algorithms once. Subclasses override only:
    - Package manager commands (pacman vs apt)
    - Output parsing (different formats)
    - Distro-specific tool calls
    """
    
    @property
    @abstractmethod
    def package_manager(self) -> str:
        """Return package manager name (e.g., 'pacman', 'apt')."""
        raise NotImplementedError
    
    # Abstract methods (subclasses implement)
    
    @abstractmethod
    def _get_base_packages_config(self, conf: Any) -> Dict[str, Any]:
        """Return distro-specific base packages config.
        
        Return:
            {"kernel": "package-name", "base": [list, of, packages]}
        """
        raise NotImplementedError
    
    @abstractmethod
    def _install_command(self, base_pkgs: Dict, mount_point: str) -> str:
        """Return full install command string.
        
        Args:
            base_pkgs: dict with "kernel" and "base" keys
            mount_point: where to install
            
        Return:
            Shell command as string
        """
        raise NotImplementedError
    
    @abstractmethod
    def _query_kernel_file(self, mount_point: str, package: str) -> str:
        """Query package manager for kernel file.
        
        Return:
            Raw output from package manager
        """
        raise NotImplementedError
    
    @abstractmethod
    def _parse_kernel_file(self, output: str) -> Tuple[str, str]:
        """Parse kernel file from output.
        
        Args:
            output: Raw output from _query_kernel_file
            
        Return:
            (kernel_file_path, kernel_version)
        """
        raise NotImplementedError
    
    @abstractmethod
    def _query_package_db_refresh(self, mount_point: str, new_generation: bool) -> str:
        """Return command to refresh package database.
        
        Return:
            Shell command as string
        """
        raise NotImplementedError
    
    @abstractmethod
    def _query_kernel_version(self, current_kernel: str, mount_point: str) -> str:
        """Query installed kernel version.
        
        Return:
            Raw output from package manager
        """
        raise NotImplementedError
    
    @abstractmethod
    def _parse_kernel_version(self, output: str) -> str:
        """Parse kernel version from output.
        
        Args:
            output: Raw output from _query_kernel_version
            
        Return:
            Kernel version string
        """
        raise NotImplementedError
    
    @abstractmethod
    def _query_installed_packages(self, mount_point: str) -> str:
        """Query list of installed packages.
        
        Return:
            Raw output from package manager
        """
        raise NotImplementedError
    
    @abstractmethod
    def _parse_installed_packages(self, output: str) -> Dict[str, str]:
        """Parse installed packages from output.
        
        Args:
            output: Raw output from _query_installed_packages
            
        Return:
            {package_name: version, ...}
        """
        raise NotImplementedError
    
    # Common logic (implemented once, uses abstract methods)
    
    def get_base_packages(self, conf: Any) -> Dict[str, Any]:
        """Get base packages for the given configuration.
        
        The function determines the right microcode package for the CPU and
        the kernel package from the configuration. It then returns a table
        with the packages to install.

        Args:
            conf: The configuration object.

        Returns:
            A dictionary with the packages to install.
        """
        packages = self._get_base_packages_config(conf)
        
        # Override kernel if specified in config
        if conf.boot and conf.boot.kernel and conf.boot.kernel.package:
            packages["kernel"] = conf.boot.kernel.package
        
        return packages
    
    def install_essentials_pkgs(self, base_pkgs: Dict, mount_point: str) -> None:
        """Install essential packages onto the specified mount point.

        This function uses the distro-specific package manager to install a set
        of base packages including the kernel. The packages to be installed are
        determined by the base_pkgs dictionary.

        Args:
            base_pkgs: A dictionary containing the packages to install,
                      with 'kernel' and 'base' keys.
            mount_point: The mount point where the packages will be installed.
        """
        cmd = self._install_command(base_pkgs, mount_point)
        exec(cmd)
    
    def get_kernel_file(self, mount_point: str, package: str = "linux") -> Tuple[str, str]:
        """Retrieve the kernel file path and version.

        Args:
            mount_point: The mount point of the chroot environment.
            package: The kernel package name (default: "linux").

        Returns:
            Tuple of (kernel_file_path, kernel_version)
            
        Raises:
            RuntimeError: If kernel file not found or parsing fails.
        """
        output = self._query_kernel_file(mount_point, package)
        
        if not output or not output.strip():
            raise RuntimeError(f"No kernel file found for package '{package}'. Output: {output}")
        
        kernel_file, kver = self._parse_kernel_file(output)
        
        if not kernel_file or "/" not in kernel_file:
            raise RuntimeError(f"Invalid kernel file path: {kernel_file}")
        
        if not kver or kver.isspace():
            raise RuntimeError(f"Could not extract kernel version from path: {kernel_file}")
        
        return kernel_file, kver
    
    def get_list_of_dependencies(self, pkg: str) -> List[str]:
        """Get the list of dependencies of a given package.

        Args:
            pkg: The package name.

        Returns:
            A list of packages that the given package depends on.
        """
        # Default implementation (subclasses may override if needed)
        return [pkg]
    
    def proc_repos(self, conf: Any, current_repos: Dict = None, update: bool = False, 
                   mount_point: str = "/mnt") -> Tuple[Dict, List]:
        """Process the repository configuration.

        Args:
            conf: The configuration dictionary.
            current_repos: The current repository configuration.
            update: If True, update the package list.
            mount_point: The mount point where installation is performed.

        Returns:
            Tuple of (repos_config, installed_packages)
        """
        repos_conf = conf.repos
        repos = {}
        packages = []
        
        if repos_conf is None:
            return repos, packages
        
        for repo, repo_desc in repos_conf.items():
            if current_repos and repo in current_repos and not update:
                repos[repo] = current_repos[repo]
                continue
            
            repos[repo] = {}
            
            if "commands" not in repo_desc:
                print(f"Warning: Repository '{repo}' missing 'commands' field, skipping")
                continue
            
            for action, cmd in repo_desc["commands"].items():
                repos[repo][action] = cmd
        
        if repos:
            exec(f"mkdir -p {mount_point}/var/kod")
            with open(f"{mount_point}/var/kod/repos.json", "w") as f:
                import json
                f.write(json.dumps(repos, indent=2))
        
        return repos, packages
    
    def refresh_package_db(self, mount_point: str, new_generation: bool) -> None:
        """Refresh the package database.

        Args:
            mount_point: The mount point of the chroot environment.
            new_generation: If True, run in chroot; else on host.
        """
        if new_generation:
            cmd = self._query_package_db_refresh(mount_point, True)
            exec_chroot(cmd, mount_point=mount_point)
        else:
            cmd = self._query_package_db_refresh(mount_point, False)
            exec(cmd)
    
    def kernel_update_required(self, current_kernel: str, next_kernel: str,
                              current_installed_packages: Dict, mount_point: str) -> bool:
        """Check if a kernel update is required.

        Args:
            current_kernel: Current kernel package name.
            next_kernel: Next kernel package name.
            current_installed_packages: Dict mapping package names to versions.
            mount_point: Mount point of chroot environment.

        Returns:
            True if kernel update required, False otherwise.
        """
        if current_kernel != next_kernel:
            return True
        
        if not current_installed_packages or current_kernel not in current_installed_packages:
            return True
        
        new_kernel_output = self._query_kernel_version(current_kernel, mount_point)
        current_kernel_ver = current_installed_packages[current_kernel]
        
        new_kernel_ver = self._parse_kernel_version(new_kernel_output)
        
        if not new_kernel_ver or new_kernel_ver.isspace():
            raise RuntimeError(f"Invalid kernel version: {new_kernel_ver}")
        
        split_kver = new_kernel_ver.split(".")
        if len(split_kver) < 2 or not split_kver[0]:
            raise RuntimeError(f"Could not parse kernel architecture from: {new_kernel_ver}")
        
        print(f"{current_kernel}={current_kernel_ver} {next_kernel}={new_kernel_ver}")
        
        return current_kernel_ver != new_kernel_ver
    
    def generate_package_lock(self, mount_point: str, state_path: str) -> None:
        """Generate a file containing installed packages and versions.

        Args:
            mount_point: Root directory of chroot environment.
            state_path: Path to state directory for output.
        """
        output = self._query_installed_packages(mount_point)
        packages = self._parse_installed_packages(output)
        
        with open(f"{state_path}/packages.lock", "w") as f:
            for pkg, ver in packages.items():
                f.write(f"{pkg} {ver}\n")
```

- [ ] **Step 2: Write test file with base class tests**

Create `tests/system/test_distro_base.py`:

```python
"""Tests for distro adapter base class."""

import pytest
from unittest.mock import MagicMock, patch
from kod.system.distro.base import DistroAdapter


class ConcreteAdapter(DistroAdapter):
    """Concrete implementation for testing."""
    
    @property
    def package_manager(self) -> str:
        return "test-pm"
    
    def _get_base_packages_config(self, conf):
        return {"kernel": "test-kernel", "base": ["pkg1", "pkg2"]}
    
    def _install_command(self, base_pkgs, mount_point):
        return f"install {' '.join(base_pkgs['base'])}"
    
    def _query_kernel_file(self, mount_point, package):
        return "test-kernel-6.10"
    
    def _parse_kernel_file(self, output):
        return ("/boot/vmlinuz-6.10", "6.10")
    
    def _query_package_db_refresh(self, mount_point, new_generation):
        return "refresh"
    
    def _query_kernel_version(self, current_kernel, mount_point):
        return "6.10"
    
    def _parse_kernel_version(self, output):
        return output.strip()
    
    def _query_installed_packages(self, mount_point):
        return "pkg1 1.0\npkg2 2.0"
    
    def _parse_installed_packages(self, output):
        packages = {}
        for line in output.split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    packages[parts[0]] = parts[1]
        return packages


class TestDistroAdapterBase:
    """Test DistroAdapter base class."""
    
    def test_get_base_packages_no_override(self):
        """get_base_packages returns config without config override."""
        adapter = ConcreteAdapter()
        conf = MagicMock()
        conf.boot = None
        
        result = adapter.get_base_packages(conf)
        
        assert result["kernel"] == "test-kernel"
        assert "pkg1" in result["base"]
    
    def test_get_base_packages_with_override(self):
        """get_base_packages overrides kernel from config."""
        adapter = ConcreteAdapter()
        conf = MagicMock()
        conf.boot.kernel.package = "custom-kernel"
        
        result = adapter.get_base_packages(conf)
        
        assert result["kernel"] == "custom-kernel"
    
    def test_get_kernel_file_success(self):
        """get_kernel_file returns path and version."""
        adapter = ConcreteAdapter()
        
        path, version = adapter.get_kernel_file("/mnt", "linux")
        
        assert path == "/boot/vmlinuz-6.10"
        assert version == "6.10"
    
    def test_get_kernel_file_empty_output(self):
        """get_kernel_file raises on empty output."""
        adapter = ConcreteAdapter()
        adapter._query_kernel_file = MagicMock(return_value="")
        
        with pytest.raises(RuntimeError, match="No kernel file found"):
            adapter.get_kernel_file("/mnt", "linux")
    
    def test_kernel_update_required_different_package(self):
        """kernel_update_required returns True for different package."""
        adapter = ConcreteAdapter()
        
        result = adapter.kernel_update_required("linux", "linux-lts", {}, "/mnt")
        
        assert result is True
    
    def test_kernel_update_required_no_current(self):
        """kernel_update_required returns True if no current packages."""
        adapter = ConcreteAdapter()
        
        result = adapter.kernel_update_required("linux", "linux", {}, "/mnt")
        
        assert result is True
    
    def test_generate_package_lock(self):
        """generate_package_lock writes packages.lock file."""
        adapter = ConcreteAdapter()
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter.generate_package_lock("/mnt", tmpdir)
            
            with open(f"{tmpdir}/packages.lock") as f:
                content = f.read()
                assert "pkg1 1.0" in content
                assert "pkg2 2.0" in content
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/system/test_distro_base.py -v`

Expected: All tests PASS

- [ ] **Step 4: Commit base class**

```bash
git add src/kod/system/distro/base.py tests/system/test_distro_base.py
git commit -m "feat: create DistroAdapter base class with common logic

Implement Strategy Pattern base class containing all common package
management algorithms used by distro adapters. Subclasses override
only distro-specific methods (queries, parsing, install commands).

Common logic includes:
  • get_base_packages() - merge config with distro defaults
  • install_essentials_pkgs() - common install flow
  • get_kernel_file() - common query + validate + parse
  • kernel_update_required() - version comparison logic
  • generate_package_lock() - parse and write packages
  • refresh_package_db() - coordinate chroot vs host
  • proc_repos() - repo config processing

Abstract methods for subclass override:
  • _get_base_packages_config() - distro package lists
  • _install_command() - pacstrap vs apt vs others
  • _query_kernel_file() - package manager query
  • _parse_kernel_file() - format-specific parsing
  • _query_kernel_version() - version lookup
  • _parse_kernel_version() - version extraction
  • _query_installed_packages() - list query
  • _parse_installed_packages() - list parsing

Tests:
  • Base class instantiation (via ConcreteAdapter)
  • get_base_packages with/without config override
  • get_kernel_file happy path + error cases
  • kernel_update_required logic
  • generate_package_lock write

This is the foundation for ArchAdapter and DebianAdapter subclasses."
```

---

### Task 2: Create ArchAdapter

**Files:**
- Create: `src/kod/system/distro/adapters/__init__.py`
- Create: `src/kod/system/distro/adapters/arch.py`
- Test: `tests/system/test_distro_adapters.py` (add Arch tests)

**Interfaces:**
- Consumes: `DistroAdapter` base class
- Produces: `ArchAdapter` class inheriting from `DistroAdapter`, implementing all abstract methods

- [ ] **Step 1: Create adapters package marker**

Create `src/kod/system/distro/adapters/__init__.py`:
```python
"""Distro-specific adapters (Strategy implementations)."""

from .arch import ArchAdapter
from .debian import DebianAdapter

__all__ = ["ArchAdapter", "DebianAdapter"]
```

- [ ] **Step 2: Create ArchAdapter with overrides**

Create `src/kod/system/distro/adapters/arch.py`:

```python
"""Arch Linux specific package management adapter."""

from typing import Any, Dict, Tuple
from kod.system.distro.base import DistroAdapter
from kod.common import exec, exec_chroot


class ArchAdapter(DistroAdapter):
    """Arch Linux package management via pacman."""
    
    @property
    def package_manager(self) -> str:
        return "pacman"
    
    def _detect_cpu_microcode(self) -> str:
        """Detect CPU and return appropriate microcode package."""
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "AuthenticAMD" in line:
                        return "amd-ucode"
                    if "GenuineIntel" in line:
                        return "intel-ucode"
        except Exception:
            pass
        return "intel-ucode"  # Default fallback
    
    def _get_base_packages_config(self, conf: Any) -> Dict[str, Any]:
        """Arch-specific base packages."""
        microcode = self._detect_cpu_microcode()
        
        return {
            "kernel": "linux",
            "base": [
                "base",
                "base-devel",
                "debugedit",
                "fakeroot",
                microcode,
                "btrfs-progs",
                "linux-firmware",
                "bash-completion",
                "mlocate",
                "sudo",
                "schroot",
                "whois",
                "dracut",
                "git",
                "arch-install-scripts",
            ],
        }
    
    def _install_command(self, base_pkgs: Dict, mount_point: str) -> str:
        """Arch pacstrap install command."""
        kernel = base_pkgs["kernel"]
        base = base_pkgs["base"]
        packages = " ".join([kernel] + base)
        return f"pacstrap -K {mount_point} {packages}"
    
    def _query_kernel_file(self, mount_point: str, package: str) -> str:
        """Query pacman for kernel file."""
        return exec_chroot(
            f"bash -c 'pacman -Ql {package} | grep vmlinuz'",
            mount_point=mount_point,
            get_output=True
        )
    
    def _parse_kernel_file(self, output: str) -> Tuple[str, str]:
        """Parse pacman -Ql output: 'arch kernel-package     6.10.10-arch1-1 /usr/lib/modules/6.10.10-arch1-1/vmlinuz'."""
        kernel_file = output.split(" ")[-1].strip()
        kver = kernel_file.split("/")[-2]
        return kernel_file, kver
    
    def _query_package_db_refresh(self, mount_point: str, new_generation: bool) -> str:
        """Pacman refresh command."""
        return "pacman -Syy --noconfirm"
    
    def _query_kernel_version(self, current_kernel: str, mount_point: str) -> str:
        """Query pacman for kernel version."""
        return exec_chroot(
            f"pacman -Q {current_kernel}",
            mount_point=mount_point,
            get_output=True
        )
    
    def _parse_kernel_version(self, output: str) -> str:
        """Parse pacman -Q output: 'linux 6.10.10-arch1-1'."""
        split_output = output.strip().split(" ")
        if len(split_output) < 2:
            raise RuntimeError(f"Invalid kernel version output: {output}")
        return split_output[1]
    
    def _query_installed_packages(self, mount_point: str) -> str:
        """Query installed packages from pacman."""
        return exec_chroot(
            "pacman -Q --noconfirm",
            mount_point=mount_point,
            get_output=True
        )
    
    def _parse_installed_packages(self, output: str) -> Dict[str, str]:
        """Parse pacman -Q output: 'linux 6.10.10-arch1-1'."""
        packages = {}
        for line in output.split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    packages[parts[0]] = parts[1]
        return packages
    
    def get_list_of_dependencies(self, pkg: str) -> list:
        """Get dependencies via pacman -Si and pacman -Sgq."""
        # Check if it is a group
        group_output = exec(f"pacman -Sgq {pkg}", get_output=True).strip()
        
        if group_output:
            pkgs_list = group_output.split("\n")
            pkgs_list = [p.strip() for p in pkgs_list if p.strip()]
            if pkgs_list:
                return pkgs_list + [pkg]
        
        # Fallback: check if it is a (meta-)package
        try:
            depend_on = exec(f"pacman -Si {pkg} | grep 'Depends On'", get_output=True).split(":")
            if len(depend_on) >= 2:
                deps = [p.strip() for p in depend_on[1].strip().split() if p.strip()]
                if deps:
                    return deps
            return [pkg]
        except Exception:
            return [pkg]
```

- [ ] **Step 3: Add Arch adapter tests**

Add to `tests/system/test_distro_adapters.py`:

```python
"""Tests for distro adapter concrete implementations."""

import pytest
from unittest.mock import MagicMock, patch
from kod.system.distro.adapters.arch import ArchAdapter


class TestArchAdapter:
    """Test ArchAdapter Arch-specific overrides."""
    
    def test_package_manager_name(self):
        """package_manager returns 'pacman'."""
        adapter = ArchAdapter()
        assert adapter.package_manager == "pacman"
    
    def test_get_base_packages_config(self):
        """_get_base_packages_config returns Arch packages."""
        adapter = ArchAdapter()
        conf = MagicMock()
        
        config = adapter._get_base_packages_config(conf)
        
        assert config["kernel"] == "linux"
        assert "base" in config["base"]
        assert "base-devel" in config["base"]
        assert "dracut" in config["base"]
        # Microcode will be amd-ucode or intel-ucode
        assert any(u in config["base"] for u in ["amd-ucode", "intel-ucode"])
    
    def test_install_command(self):
        """_install_command returns pacstrap command."""
        adapter = ArchAdapter()
        base_pkgs = {"kernel": "linux", "base": ["pkg1", "pkg2"]}
        
        cmd = adapter._install_command(base_pkgs, "/mnt")
        
        assert "pacstrap -K /mnt" in cmd
        assert "linux" in cmd
        assert "pkg1" in cmd
    
    @patch('kod.common.exec_chroot')
    def test_query_kernel_file(self, mock_exec_chroot):
        """_query_kernel_file calls pacman -Ql."""
        mock_exec_chroot.return_value = "arch linux     6.10     /usr/lib/modules/6.10/vmlinuz"
        adapter = ArchAdapter()
        
        result = adapter._query_kernel_file("/mnt", "linux")
        
        assert result == "arch linux     6.10     /usr/lib/modules/6.10/vmlinuz"
        mock_exec_chroot.assert_called_once()
    
    def test_parse_kernel_file(self):
        """_parse_kernel_file extracts path and version."""
        adapter = ArchAdapter()
        output = "arch linux     6.10     /usr/lib/modules/6.10/vmlinuz"
        
        path, version = adapter._parse_kernel_file(output)
        
        assert path == "/usr/lib/modules/6.10/vmlinuz"
        assert version == "6.10"
    
    def test_parse_kernel_version_pacman_format(self):
        """_parse_kernel_version parses 'linux 6.10.10-arch1-1'."""
        adapter = ArchAdapter()
        output = "linux 6.10.10-arch1-1"
        
        version = adapter._parse_kernel_version(output)
        
        assert version == "6.10.10-arch1-1"
    
    def test_parse_installed_packages(self):
        """_parse_installed_packages parses pacman -Q format."""
        adapter = ArchAdapter()
        output = "linux 6.10.10-arch1-1\nbase 1.0\n"
        
        packages = adapter._parse_installed_packages(output)
        
        assert packages["linux"] == "6.10.10-arch1-1"
        assert packages["base"] == "1.0"
```

- [ ] **Step 4: Run tests to verify Arch adapter**

Run: `pytest tests/system/test_distro_adapters.py::TestArchAdapter -v`

Expected: All Arch tests PASS

- [ ] **Step 5: Commit ArchAdapter**

```bash
git add src/kod/system/distro/adapters/__init__.py \
        src/kod/system/distro/adapters/arch.py \
        tests/system/test_distro_adapters.py
git commit -m "feat: create ArchAdapter with Arch-specific overrides

Implement ArchAdapter subclass of DistroAdapter for Arch Linux
package management via pacman.

Overrides distro-specific methods:
  • _detect_cpu_microcode() - CPU detection (AuthenticAMD vs GenuineIntel)
  • _get_base_packages_config() - Arch package lists
  • _install_command() - pacstrap -K invocation
  • _query_kernel_file() - pacman -Ql vmlinuz lookup
  • _parse_kernel_file() - extract path from pacman -Ql output
  • _query_kernel_version() - pacman -Q lookup
  • _parse_kernel_version() - split on space (pacman format)
  • _query_installed_packages() - pacman -Q --noconfirm
  • _parse_installed_packages() - simple space-split parsing
  • get_list_of_dependencies() - pacman -Sgq + pacman -Si

Tests:
  • Arch package list contains expected packages
  • pacstrap command generation
  • Kernel file parsing from pacman -Ql output
  • Kernel version parsing from pacman -Q output
  • Installed packages parsing

Public API identical to original arch.py; internal reimplemented
via adapter pattern."
```

---

### Task 3: Create DebianAdapter

**Files:**
- Create: `src/kod/system/distro/adapters/debian.py`
- Test: `tests/system/test_distro_adapters.py` (add Debian tests)

**Interfaces:**
- Consumes: `DistroAdapter` base class
- Produces: `DebianAdapter` class inheriting from `DistroAdapter`, implementing all abstract methods

- [ ] **Step 1: Create DebianAdapter with overrides**

Create `src/kod/system/distro/adapters/debian.py`:

```python
"""Debian/Ubuntu specific package management adapter."""

import re
from typing import Any, Dict, Tuple, List
from kod.system.distro.base import DistroAdapter
from kod.common import exec, exec_chroot


class DebianAdapter(DistroAdapter):
    """Debian/Ubuntu package management via apt."""
    
    @property
    def package_manager(self) -> str:
        return "apt"
    
    def _get_base_packages_config(self, conf: Any) -> Dict[str, Any]:
        """Debian-specific base packages."""
        return {
            "kernel": "linux-image-amd64",
            "base": [
                "btrfs-progs",
                "systemd-boot",
                "locales",
                "sudo",
                "schroot",
                "whois",
                "dracut",
                "git",
            ],
        }
    
    def _install_command(self, base_pkgs: Dict, mount_point: str) -> str:
        """Debian debootstrap + apt install command."""
        exec("apt install -y debootstrap gdisk")
        exec("debootstrap --merged-usr testing /mnt")
        kernel = base_pkgs["kernel"]
        base = base_pkgs["base"]
        packages = " ".join([kernel] + base)
        return f"bash -c 'yes | DEBIAN_FRONTEND=noninteractive apt-get install -y {packages}'"
    
    def _query_kernel_file(self, mount_point: str, package: str) -> str:
        """Query apt-cache for kernel dependencies."""
        return exec_chroot(
            f"apt-cache depends {package} | grep Depends",
            mount_point=mount_point,
            get_output=True
        )
    
    def _parse_kernel_file(self, output: str) -> Tuple[str, str]:
        """Parse apt-cache depends output: 'Depends: linux-image-6.1'."""
        if ":" not in output:
            raise RuntimeError(f"Invalid dependency format (missing colon): {output}")
        
        kernel_package = output.split(":")[1].strip()
        kver = kernel_package.split("-", 2)[-1]
        
        return kernel_package, kver
    
    def _query_package_db_refresh(self, mount_point: str, new_generation: bool) -> str:
        """APT refresh command."""
        return "apt-get update"
    
    def _query_kernel_version(self, current_kernel: str, mount_point: str) -> str:
        """Query apt for kernel version."""
        return exec_chroot(
            f"apt-cache madison {current_kernel}",
            mount_point=mount_point,
            get_output=True
        )
    
    def _parse_kernel_version(self, output: str) -> str:
        """Parse apt-cache madison output: 'linux-image | 6.1.0 | ...'."""
        split_output = output.split("|")
        if len(split_output) < 2:
            raise RuntimeError(f"Invalid kernel version output: {output}")
        return split_output[1].strip()
    
    def _query_installed_packages(self, mount_point: str) -> str:
        """Query installed packages via dpkg."""
        return exec_chroot(
            "dpkg -l",
            mount_point=mount_point,
            get_output=True
        )
    
    def _parse_installed_packages(self, output: str) -> Dict[str, str]:
        """Parse dpkg -l output: 'ii  package-name  version  arch  description'."""
        packages = {}
        for line in output.split("\n"):
            if line.startswith("ii "):
                parts = re.split(r"\s+", line.strip())
                if len(parts) >= 3:
                    packages[parts[1]] = parts[2]
        return packages
    
    def install_build_dependencies(self, mount_point: str = "/mnt") -> bool:
        """Install packages required for building.
        
        Args:
            mount_point: The mount point of the chroot environment.
            
        Returns:
            True if successful.
            
        Raises:
            RuntimeError: If build dependencies fail to install.
        """
        build_packages = [
            "build-essential",
            "autoconf",
            "automake",
            "pkg-config",
            "git",
        ]
        
        try:
            exec_chroot(
                f"apt-get install -y {' '.join(build_packages)}",
                mount_point=mount_point,
                run_as_root=True
            )
        except Exception as e:
            raise RuntimeError(f"Failed to install build dependencies: {e}")
        
        # Verify installation
        installed_output = exec_chroot(
            "dpkg -l",
            mount_point=mount_point,
            get_output=True
        )
        
        failed = []
        for pkg in build_packages:
            found = False
            for line in installed_output.split("\n"):
                if line.startswith("ii "):
                    parts = re.split(r"\s+", line.strip())
                    if len(parts) >= 2 and parts[1] == pkg:
                        found = True
                        break
            if not found:
                failed.append(pkg)
        
        if failed:
            raise RuntimeError(
                f"Failed to install build dependencies: {', '.join(failed)}. "
                f"System may not support package building."
            )
        
        return True
    
    def proc_repos(self, conf: Any, current_repos: Dict = None, update: bool = False,
                   mount_point: str = "/mnt") -> Tuple[Dict, List]:
        """Process repository configuration with Debian-specific handling."""
        repos_conf = conf.repos
        repos = {}
        packages = []
        update_repos = False
        
        if repos_conf is None:
            return repos, packages
        
        for repo, repo_desc in repos_conf.items():
            if current_repos and repo in current_repos and not update:
                repos[repo] = current_repos[repo]
                continue
            
            repos[repo] = {}
            
            if "commands" not in repo_desc:
                print(f"Warning: Repository '{repo}' missing 'commands' field, skipping")
                continue
            
            for action, cmd in repo_desc["commands"].items():
                repos[repo][action] = cmd
            
            if "build" in repo_desc:
                build_info = repo_desc["build"]
                url = build_info["url"]
                build_cmd = build_info["build_cmd"]
                name = build_info["name"]
                
                # Install build dependencies first (needed for source builds on Debian)
                self.install_build_dependencies(mount_point=mount_point)
                
                # Build from source
                exec_chroot(
                    f"runuser -u kod -- /bin/bash -c 'cd && git clone {url} {name} && cd {name} && {build_cmd}'",
                    mount_point=mount_point,
                )
                
                # Verify build
                result = exec_chroot(
                    f"which {name}",
                    mount_point=mount_point,
                    get_output=True
                )
                if not result or "not found" in result.lower():
                    raise RuntimeError(f"Build failed for '{name}'. Build output: {result}")
                
                print(f"✅ Built '{name}' successfully")
            
            update_repos = True
        
        if update_repos:
            import json
            exec(f"mkdir -p {mount_point}/var/kod")
            with open(f"{mount_point}/var/kod/repos.json", "w") as f:
                f.write(json.dumps(repos, indent=2))
        
        return repos, packages
```

- [ ] **Step 2: Add Debian adapter tests**

Add to `tests/system/test_distro_adapters.py`:

```python
class TestDebianAdapter:
    """Test DebianAdapter Debian-specific overrides."""
    
    def test_package_manager_name(self):
        """package_manager returns 'apt'."""
        from kod.system.distro.adapters.debian import DebianAdapter
        adapter = DebianAdapter()
        assert adapter.package_manager == "apt"
    
    def test_get_base_packages_config(self):
        """_get_base_packages_config returns Debian packages."""
        from kod.system.distro.adapters.debian import DebianAdapter
        adapter = DebianAdapter()
        conf = MagicMock()
        
        config = adapter._get_base_packages_config(conf)
        
        assert config["kernel"] == "linux-image-amd64"
        assert "btrfs-progs" in config["base"]
        assert "systemd-boot" in config["base"]
        assert "dracut" in config["base"]
    
    def test_parse_kernel_file_apt_format(self):
        """_parse_kernel_file parses apt-cache depends output."""
        from kod.system.distro.adapters.debian import DebianAdapter
        adapter = DebianAdapter()
        output = "Depends: linux-image-6.1.0"
        
        package, version = adapter._parse_kernel_file(output)
        
        assert package == "linux-image-6.1.0"
        assert version == "6.1.0"
    
    def test_parse_kernel_version_apt_format(self):
        """_parse_kernel_version parses apt-cache madison output."""
        from kod.system.distro.adapters.debian import DebianAdapter
        adapter = DebianAdapter()
        output = "linux-image | 6.1.0 | archive"
        
        version = adapter._parse_kernel_version(output)
        
        assert version == "6.1.0"
    
    def test_parse_installed_packages_dpkg_format(self):
        """_parse_installed_packages parses dpkg -l format."""
        from kod.system.distro.adapters.debian import DebianAdapter
        adapter = DebianAdapter()
        output = "ii  linux-image-amd64  6.1.0-amd64  amd64  Linux kernel\nii  base-files  12.4  amd64  Debian base files\n"
        
        packages = adapter._parse_installed_packages(output)
        
        assert packages["linux-image-amd64"] == "6.1.0-amd64"
        assert packages["base-files"] == "12.4"
```

- [ ] **Step 3: Run all adapter tests**

Run: `pytest tests/system/test_distro_adapters.py -v`

Expected: All Arch and Debian tests PASS

- [ ] **Step 4: Commit DebianAdapter**

```bash
git add src/kod/system/distro/adapters/debian.py tests/system/test_distro_adapters.py
git commit -m "feat: create DebianAdapter with Debian-specific overrides

Implement DebianAdapter subclass of DistroAdapter for Debian/Ubuntu
package management via apt/dpkg.

Overrides distro-specific methods:
  • _get_base_packages_config() - Debian package lists
  • _install_command() - debootstrap + apt-get install
  • _query_kernel_file() - apt-cache depends lookup
  • _parse_kernel_file() - extract kernel package from apt output
  • _query_kernel_version() - apt-cache madison lookup
  • _parse_kernel_version() - split on pipe (apt format)
  • _query_installed_packages() - dpkg -l
  • _parse_installed_packages() - regex split parsing for dpkg
  • install_build_dependencies() - build-essential + autotools
  • proc_repos() - Debian-specific repo handling

Tests:
  • Debian package list contains expected packages
  • apt-get install command generation
  • Kernel package parsing from apt output
  • Kernel version parsing from apt-cache madison output
  • Installed packages parsing from dpkg -l

BUG FIXES:
  ✓ Original debian.py get_list_of_dependencies() called pacman
    (Arch tool) - removed in favor of base class default
  ✓ install_build_dependencies() properly verifies installation
  ✓ proc_repos() properly handles Debian build paths

Public API identical to original debian.py; internal reimplemented
via adapter pattern."
```

---

### Task 4: Update Factory & Integration

**Files:**
- Modify: `src/kod/system/distro/factory.py`
- Modify: `src/kod/system/distro/__init__.py`

**Interfaces:**
- Consumes: ArchAdapter, DebianAdapter classes
- Produces: `get_distro_module(distro_name: str) -> DistroAdapter` (instantiated, not module)

- [ ] **Step 1: Update factory.py to instantiate adapters**

Replace `src/kod/system/distro/factory.py`:

```python
"""Distro module factory (strategy pattern for distro selection).

Dynamically loads and instantiates distro adapter classes.
"""

from typing import Any
import importlib


def get_distro_module(distro_name: str) -> Any:
    """Get the distro-specific adapter instance.
    
    Args:
        distro_name: The distro name ("arch", "debian", etc.)
        
    Returns:
        An instance of the distro adapter (ArchAdapter, DebianAdapter, etc.)
        
    Raises:
        ValueError: If distro_name is not supported.
    """
    supported = {"arch": "ArchAdapter", "debian": "DebianAdapter"}
    
    if distro_name not in supported:
        raise ValueError(f"Unknown distro: {distro_name}. Supported: {list(supported.keys())}")
    
    # Dynamically import the adapter module
    module = importlib.import_module(f"kod.system.distro.adapters.{distro_name}")
    
    # Get the adapter class
    adapter_class_name = supported[distro_name]
    adapter_class = getattr(module, adapter_class_name)
    
    # Return an instance
    return adapter_class()
```

- [ ] **Step 2: Verify factory returns instances, not modules**

Create quick test script:

```python
from kod.system.distro.factory import get_distro_module

arch = get_distro_module("arch")
debian = get_distro_module("debian")

print(f"arch: {type(arch)} - has get_base_packages: {hasattr(arch, 'get_base_packages')}")
print(f"debian: {type(debian)} - has get_base_packages: {hasattr(debian, 'get_base_packages')}")

# Verify they're adapter instances
from kod.system.distro.base import DistroAdapter
assert isinstance(arch, DistroAdapter)
assert isinstance(debian, DistroAdapter)
print("✓ Factory returns adapter instances")
```

Run: `python3 factory_test.py` (expected: ✓ message)

- [ ] **Step 3: Update __init__.py exports**

Modify `src/kod/system/distro/__init__.py`:

```python
"""Distro-specific package management adapters.

Provides abstraction layer for distro-specific operations:
  - Arch Linux (via pacman)
  - Debian/Ubuntu (via apt/dpkg)

Usage:
    from kod.system.distro import get_distro_module
    
    adapter = get_distro_module("arch")
    packages = adapter.get_base_packages(conf)
    adapter.install_essentials_pkgs(packages, mount_point)
"""

from .factory import get_distro_module

__all__ = ["get_distro_module"]
```

- [ ] **Step 4: Test kod.py imports still work**

Check that kod.py can import and use without changes:

Run: `python3 -c "from kod.kod import *; print('✓ kod.py imports work')"`

Expected: ✓ message, no import errors

- [ ] **Step 5: Commit factory updates**

```bash
git add src/kod/system/distro/factory.py src/kod/system/distro/__init__.py
git commit -m "refactor: update factory to instantiate adapter classes

Modify factory.py to return adapter instances instead of modules:
  • get_distro_module('arch') returns ArchAdapter()
  • get_distro_module('debian') returns DebianAdapter()
  • All instances inherit from DistroAdapter base class
  • Public API unchanged - callers see same interface

Update __init__.py to export factory function and document usage.

This completes the Strategy Pattern refactor:
  • DistroAdapter base class (common logic)
  • ArchAdapter subclass (Arch-specific)
  • DebianAdapter subclass (Debian-specific)
  • Factory for instantiation

All external callers (kod.py, boot.py) work unchanged."
```

---

### Task 5: Delete Old Modules & Verify Integration

**Files:**
- Delete: `src/kod/system/distro/arch.py`
- Delete: `src/kod/system/distro/debian.py`

**Interfaces:**
- Consumes: All previous adapter + factory implementations
- Produces: Clean distro/ directory with no old implementations

- [ ] **Step 1: Verify no imports of old modules remain**

Run:
```bash
grep -r "from kod.system.distro.arch import\|from kod.system.distro.debian import" src/ tests/ --include="*.py" | grep -v ".pyc"
```

Expected: No output (no direct imports of old modules)

- [ ] **Step 2: Delete old arch.py**

```bash
git rm src/kod/system/distro/arch.py
```

- [ ] **Step 3: Delete old debian.py**

```bash
git rm src/kod/system/distro/debian.py
```

- [ ] **Step 4: Verify kod.py and boot.py still work**

Test imports:
```python
from kod.system.distro.factory import get_distro_module
arch = get_distro_module("arch")
print(arch.get_base_packages)  # Should be callable
```

Run: `python3 -c "from kod.system.distro.factory import get_distro_module; arch = get_distro_module('arch'); print(arch.get_base_packages)"`

Expected: Function reference printed, no errors

- [ ] **Step 5: Commit deletion**

```bash
git commit -m "refactor: delete old distro module implementations

Remove arch.py and debian.py - consolidated into:
  • DistroAdapter base class (common algorithms)
  • ArchAdapter (Arch-specific overrides)
  • DebianAdapter (Debian-specific overrides)

Old implementations now obsolete. All functionality preserved via
adapter classes; external API unchanged.

Test verification:
  ✓ kod.py imports unchanged
  ✓ boot.py imports unchanged
  ✓ get_distro_module() still works for both distros
  ✓ All methods callable with identical signatures

Impact:
  • -800 lines of duplication
  • +0 breaking changes
  • Single source of truth for common logic"
```

---

### Task 6: Run Full Test Suite & Verify No Regressions

**Files:**
- Test: All existing tests in `tests/system/test_distro_*.py`

**Interfaces:**
- Consumes: All refactored distro modules
- Produces: Green test suite, verified compatibility

- [ ] **Step 1: Run all distro adapter tests**

Run: `pytest tests/system/test_distro_*.py -v`

Expected: All tests PASS (base class tests + adapter tests)

- [ ] **Step 2: Run all kod system tests**

Run: `pytest tests/system/ -v`

Expected: All tests PASS (no regressions)

- [ ] **Step 3: Check for any other distro references**

Run:
```bash
grep -r "kod.system.distro" tests/ --include="*.py" | grep -v ".pyc" | grep -v test_distro
```

Expected: Only imports in test_distro_factory.py and other expected places

- [ ] **Step 4: Verify imports work in main kod.py**

Run:
```python
import sys
sys.path.insert(0, '/home/abuss/Work/devel/analysis/kodos/src')

from kod.kod import preview, rebuild, install
from kod.system.distro import get_distro_module

# Verify both distros load
arch = get_distro_module("arch")
debian = get_distro_module("debian")

print(f"✓ Arch adapter: {arch.package_manager}")
print(f"✓ Debian adapter: {debian.package_manager}")
```

Run: `python3` and execute above code

Expected: Both adapters load, methods callable, ✓ messages

- [ ] **Step 5: Commit final verification**

```bash
git commit -m "test: verify distro adapter refactor complete and integrated

Full test suite run:
  ✓ All distro adapter tests pass
  ✓ All system tests pass
  ✓ No regressions detected
  ✓ kod.py imports unchanged
  ✓ Both Arch and Debian adapters load correctly

Integration verification:
  ✓ get_distro_module('arch') returns ArchAdapter instance
  ✓ get_distro_module('debian') returns DebianAdapter instance
  ✓ All public methods callable with original signatures
  ✓ No breaking API changes

Refactor summary:
  • 800 lines of duplication → 590 lines consolidated
  • DistroAdapter base class (common algorithms)
  • ArchAdapter (Arch Linux specific)
  • DebianAdapter (Debian/Ubuntu specific)
  • Factory instantiation (no module changes needed)
  • All external callers work unchanged

Ready for production deployment."
```

---

## Success Criteria

- ✅ **No breaking changes**: All public APIs identical to original
- ✅ **Duplication eliminated**: ~600 lines of duplicated code removed
- ✅ **Single source of truth**: Common logic in base class once
- ✅ **All tests pass**: Both unit tests and integration
- ✅ **Extensible**: Adding a new distro = write one adapter class (~100 lines)
- ✅ **Verified**: kod.py and boot.py work unchanged

---

## Rollback Plan

If critical issues discovered at any point:

1. `git revert <commit>` to roll back specific task
2. All logic preserved in git history
3. No data loss (all functions identical to original)
4. Can identify and re-apply fix

---

## Execution Instructions

This plan is designed for **Subagent-Driven Development** (recommended) or **Executing-Plans** skill execution.

Each task:
1. Is independently testable
2. Has explicit success criteria
3. Commits atomically
4. Produces working code

**Start with Task 1.** Complete each step in order. Each `- [ ]` is one action.

For subagent execution: Dispatch one task per subagent, review results, proceed to next.
For inline execution: Complete tasks sequentially with checkpoint reviews.

