"""Tests for the DistroAdapter base class.

Tests common logic shared across all distros, validating the framework
that distro-specific adapters (Arch, Debian) build upon.
"""

import pytest
from abc import ABC
from typing import Tuple
from unittest.mock import Mock, patch, MagicMock
from kod.system.distro.base import DistroAdapter


class ConcreteDistroAdapter(DistroAdapter):
    """Concrete implementation for testing base class logic."""

    @property
    def package_manager(self) -> str:
        return "test-pkg-mgr"

    def _get_base_packages_config(self, conf) -> dict:
        return {
            "kernel": "linux-test",
            "base": ["base-test", "extra-test"]
        }

    def _install_command(self, base_pkgs: dict, mount_point: str) -> str:
        kernel = base_pkgs["kernel"]
        base = base_pkgs["base"]
        return f"install -p {mount_point} {kernel} {' '.join(base)}"

    def _query_kernel_file(self, mount_point: str, package: str) -> str:
        return f"{package} test 1.0 /usr/lib/vmlinuz"

    def _parse_kernel_file(self, output: str) -> Tuple[str, str]:
        parts = output.split()
        if len(parts) < 4:
            raise RuntimeError("Invalid kernel output format")
        return parts[3], "1.0"

    def _query_package_db_refresh(self, mount_point: str, new_generation: bool) -> str:
        return f"refresh-cmd --generation={new_generation}"

    def _query_kernel_version(self, current_kernel: str, mount_point: str) -> str:
        return f"{current_kernel} 2.0"

    def _parse_kernel_version(self, output: str) -> str:
        parts = output.split()
        if len(parts) < 2:
            raise RuntimeError("Invalid kernel version output")
        return parts[1]

    def _query_installed_packages(self, mount_point: str) -> str:
        return "linux 1.0\nbase-test 2.0\nextra-test 3.0"

    def _parse_installed_packages(self, output: str) -> dict:
        packages = {}
        for line in output.strip().split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    packages[parts[0]] = parts[1]
        return packages


# === Test: Base Class is Abstract ===
class TestDistroAdapterAbstraction:
    """Verify that DistroAdapter is properly abstract."""

    def test_distro_adapter_is_abstract_base_class(self):
        """DistroAdapter should be an ABC."""
        assert isinstance(DistroAdapter, type)
        assert issubclass(DistroAdapter, ABC)

    def test_cannot_instantiate_abstract_class(self):
        """Cannot instantiate DistroAdapter directly."""
        with pytest.raises(TypeError):
            DistroAdapter()

    def test_can_instantiate_concrete_subclass(self):
        """Can instantiate a concrete subclass with all abstract methods."""
        adapter = ConcreteDistroAdapter()
        assert isinstance(adapter, DistroAdapter)


# === Test: get_base_packages (common logic) ===
class TestGetBasePackages:
    """Test the public get_base_packages() method (common logic)."""

    def test_returns_config_packages_by_default(self):
        """Should return base packages from _get_base_packages_config()."""
        adapter = ConcreteDistroAdapter()
        mock_conf = Mock()
        mock_conf.boot = None

        packages = adapter.get_base_packages(mock_conf)

        assert packages["kernel"] == "linux-test"
        assert packages["base"] == ["base-test", "extra-test"]

    def test_overrides_kernel_from_config(self):
        """Should override kernel if specified in conf.boot.kernel.package."""
        adapter = ConcreteDistroAdapter()
        mock_conf = Mock()
        mock_conf.boot = Mock()
        mock_conf.boot.kernel = Mock()
        mock_conf.boot.kernel.package = "custom-kernel"

        packages = adapter.get_base_packages(mock_conf)

        assert packages["kernel"] == "custom-kernel"
        assert packages["base"] == ["base-test", "extra-test"]

    def test_handles_missing_boot_config(self):
        """Should use default kernel if conf.boot is None."""
        adapter = ConcreteDistroAdapter()
        mock_conf = Mock()
        mock_conf.boot = None

        packages = adapter.get_base_packages(mock_conf)

        assert packages["kernel"] == "linux-test"


# === Test: install_essentials_pkgs (common logic) ===
class TestInstallEssentialsPkgs:
    """Test the public install_essentials_pkgs() method."""

    @patch('kod.system.distro.base.exec')
    def test_calls_install_command(self, mock_exec):
        """Should call exec() with the install command."""
        adapter = ConcreteDistroAdapter()
        base_pkgs = {"kernel": "linux-test", "base": ["base-test"]}

        adapter.install_essentials_pkgs(base_pkgs, "/mnt")

        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0][0]
        assert "install" in call_args
        assert "/mnt" in call_args

    @patch('kod.system.distro.base.exec')
    def test_passes_mount_point_to_install_command(self, mock_exec):
        """Install command should include the mount point."""
        adapter = ConcreteDistroAdapter()
        base_pkgs = {"kernel": "linux", "base": ["pkg1", "pkg2"]}

        adapter.install_essentials_pkgs(base_pkgs, "/custom/mount")

        call_args = mock_exec.call_args[0][0]
        assert "/custom/mount" in call_args


# === Test: get_kernel_file (common logic with parsing) ===
class TestGetKernelFile:
    """Test the public get_kernel_file() method (common algorithm)."""

    def test_queries_and_parses_kernel_file(self):
        """Should query kernel file and parse output."""
        adapter = ConcreteDistroAdapter()

        kernel_file, kver = adapter.get_kernel_file("/mnt", "linux-test")

        assert kernel_file == "/usr/lib/vmlinuz"
        assert kver == "1.0"

    def test_raises_on_empty_query_output(self):
        """Should raise RuntimeError if query returns empty output."""
        adapter = ConcreteDistroAdapter()

        # Override to return empty
        adapter._query_kernel_file = Mock(return_value="")

        with pytest.raises(RuntimeError, match="No kernel file found"):
            adapter.get_kernel_file("/mnt", "linux")

    def test_passes_package_parameter_to_query(self):
        """Should pass package name to _query_kernel_file()."""
        adapter = ConcreteDistroAdapter()
        adapter._query_kernel_file = Mock(return_value="linux-custom test 1.0 /usr/lib/vmlinuz")

        adapter.get_kernel_file("/mnt", "linux-custom")

        adapter._query_kernel_file.assert_called_once_with("/mnt", "linux-custom")

    def test_uses_default_package_name(self):
        """Should use 'linux' as default package name."""
        adapter = ConcreteDistroAdapter()
        adapter._query_kernel_file = Mock(return_value="linux test 1.0 /usr/lib/vmlinuz")

        adapter.get_kernel_file("/mnt")

        adapter._query_kernel_file.assert_called_once_with("/mnt", "linux")


# === Test: proc_repos (common logic) ===
class TestProcRepos:
    """Test the public proc_repos() method."""

    def test_returns_empty_repos_when_none_configured(self):
        """Should return empty repos and packages when conf.repos is None."""
        adapter = ConcreteDistroAdapter()
        mock_conf = Mock()
        mock_conf.repos = None

        repos, packages = adapter.proc_repos(mock_conf)

        assert repos == {}
        assert packages == []

    def test_returns_empty_repos_for_empty_config(self):
        """Should return empty dicts for empty repo config."""
        adapter = ConcreteDistroAdapter()
        mock_conf = Mock()
        mock_conf.repos = {}

        repos, packages = adapter.proc_repos(mock_conf)

        assert repos == {}
        assert packages == []

    @patch('kod.system.distro.base.exec')
    @patch('builtins.open', create=True)
    def test_preserves_current_repos_when_not_updating(self, mock_open, mock_exec):
        """Should preserve existing repos when update=False and they're in new config."""
        adapter = ConcreteDistroAdapter()
        mock_conf = Mock()
        # New config has test-repo which was in current_repos
        mock_conf.repos = {"test-repo": {"commands": {}}}
        current_repos = {"test-repo": {"cmd": "echo test"}}

        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        repos, packages = adapter.proc_repos(mock_conf, current_repos=current_repos, update=False)

        # test-repo should be preserved from current_repos (not re-processed)
        assert "test-repo" in repos
        assert repos["test-repo"] == {"cmd": "echo test"}

    @patch('kod.system.distro.base.exec')
    @patch('builtins.open', create=True)
    def test_preserves_commands_from_config(self, mock_open, mock_exec):
        """Should extract and preserve commands from repo config."""
        adapter = ConcreteDistroAdapter()
        mock_conf = Mock()
        mock_conf.repos = {
            "test-repo": {
                "commands": {
                    "setup": "cmd1",
                    "cleanup": "cmd2"
                }
            }
        }

        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        repos, packages = adapter.proc_repos(mock_conf)

        assert repos["test-repo"]["setup"] == "cmd1"
        assert repos["test-repo"]["cleanup"] == "cmd2"

    @patch('kod.system.distro.base.exec')
    @patch('builtins.open', create=True)
    def test_skips_repo_missing_commands(self, mock_open, mock_exec):
        """Should skip repos without 'commands' field."""
        adapter = ConcreteDistroAdapter()
        mock_conf = Mock()
        mock_conf.repos = {
            "bad-repo": {"package": "some-pkg"},  # missing 'commands'
            "good-repo": {"commands": {"init": "cmd"}}
        }

        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        repos, packages = adapter.proc_repos(mock_conf)

        assert "good-repo" in repos
        assert "bad-repo" not in repos


# === Test: refresh_package_db (common logic) ===
class TestRefreshPackageDb:
    """Test the public refresh_package_db() method."""

    @patch('kod.system.distro.base.exec')
    @patch('kod.system.distro.base.exec_chroot')
    def test_runs_refresh_in_chroot_when_new_generation(self, mock_exec_chroot, mock_exec):
        """Should run command in chroot when new_generation=True."""
        adapter = ConcreteDistroAdapter()
        adapter._query_package_db_refresh = Mock(return_value="refresh-cmd")

        adapter.refresh_package_db("/mnt", new_generation=True)

        mock_exec_chroot.assert_called_once()

    @patch('kod.system.distro.base.exec')
    @patch('kod.system.distro.base.exec_chroot')
    def test_runs_refresh_outside_chroot_when_not_new_generation(self, mock_exec_chroot, mock_exec):
        """Should run command outside chroot when new_generation=False."""
        adapter = ConcreteDistroAdapter()
        adapter._query_package_db_refresh = Mock(return_value="refresh-cmd")

        adapter.refresh_package_db("/mnt", new_generation=False)

        mock_exec.assert_called_once()
        mock_exec_chroot.assert_not_called()


# === Test: kernel_update_required (common logic with queries) ===
class TestKernelUpdateRequired:
    """Test the public kernel_update_required() method."""

    def test_returns_true_when_kernel_package_name_changes(self):
        """Should return True if current_kernel != next_kernel."""
        adapter = ConcreteDistroAdapter()

        result = adapter.kernel_update_required("linux", "linux-lts", {}, "/mnt")

        assert result is True

    def test_returns_true_when_no_current_packages(self):
        """Should return True if current_installed_packages is empty (fresh install)."""
        adapter = ConcreteDistroAdapter()
        adapter._query_kernel_version = Mock(return_value="linux 1.0")

        result = adapter.kernel_update_required("linux", "linux", {}, "/mnt")

        assert result is True

    def test_returns_true_when_kernel_version_changed(self):
        """Should return True if current_kernel_ver != new_kernel_ver."""
        adapter = ConcreteDistroAdapter()
        current_packages = {"linux": "1.0"}
        adapter._query_kernel_version = Mock(return_value="linux 2.0")

        result = adapter.kernel_update_required("linux", "linux", current_packages, "/mnt")

        assert result is True

    def test_returns_false_when_kernel_unchanged(self):
        """Should return False if same kernel with same version."""
        adapter = ConcreteDistroAdapter()
        current_packages = {"linux": "1.0"}
        adapter._query_kernel_version = Mock(return_value="linux 1.0")

        result = adapter.kernel_update_required("linux", "linux", current_packages, "/mnt")

        assert result is False


# === Test: generate_package_lock (common logic with parsing) ===
class TestGeneratePackageLock:
    """Test the public generate_package_lock() method."""

    @patch('kod.system.distro.base.exec_chroot')
    @patch('builtins.open', create=True)
    def test_generates_lock_file_with_packages(self, mock_open, mock_exec_chroot):
        """Should generate packages.lock with package name and version."""
        adapter = ConcreteDistroAdapter()
        adapter._query_installed_packages = Mock(return_value="linux 1.0\nbase 2.0")
        adapter._parse_installed_packages = Mock(return_value={"linux": "1.0", "base": "2.0"})

        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        adapter.generate_package_lock("/mnt", "/var/state")

        # Verify file was opened for writing
        mock_open.assert_called_once_with("/var/state/packages.lock", "w")

        # Verify both packages were written
        written_lines = [call[0][0] for call in mock_file.write.call_args_list]
        assert any("linux" in line for line in written_lines)
        assert any("base" in line for line in written_lines)

    @patch('kod.system.distro.base.exec_chroot')
    @patch('builtins.open', create=True)
    def test_creates_lock_file_in_state_path(self, mock_open, mock_exec_chroot):
        """Should write to the correct state path."""
        adapter = ConcreteDistroAdapter()
        adapter._query_installed_packages = Mock(return_value="pkg 1.0")
        adapter._parse_installed_packages = Mock(return_value={"pkg": "1.0"})

        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        adapter.generate_package_lock("/mnt", "/custom/state")

        mock_open.assert_called_once_with("/custom/state/packages.lock", "w")


# === Test: Abstract Method Enforcement ===
class TestAbstractMethods:
    """Verify all abstract methods are required."""

    def test_missing_package_manager_property(self):
        """Subclass must implement package_manager property."""
        class IncompleteAdapter(DistroAdapter):
            def _get_base_packages_config(self, conf): pass
            def _install_command(self, base_pkgs, mount_point): pass
            def _query_kernel_file(self, mount_point, package): pass
            def _parse_kernel_file(self, output): pass
            def _query_package_db_refresh(self, mount_point, new_generation): pass
            def _query_kernel_version(self, current_kernel, mount_point): pass
            def _parse_kernel_version(self, output): pass
            def _query_installed_packages(self, mount_point): pass
            def _parse_installed_packages(self, output): pass

        with pytest.raises(TypeError):
            IncompleteAdapter()
