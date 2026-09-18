"""Tests for distro adapter implementations.

Tests Arch-specific and Debian-specific parsing, command generation, and query methods.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from kod.system.distro.adapters.arch import ArchAdapter
from kod.system.distro.adapters.debian import DebianAdapter


class TestArchAdapterProperties:
    """Test ArchAdapter basic properties."""

    def test_package_manager_is_pacman(self):
        """ArchAdapter should identify pacman as its package manager."""
        adapter = ArchAdapter()
        assert adapter.package_manager == "pacman"


class TestArchGetBasePackagesConfig:
    """Test Arch-specific base package configuration."""

    def test_includes_arch_base_packages(self):
        """Should include Arch-specific base packages."""
        adapter = ArchAdapter()
        mock_conf = Mock()

        packages = adapter._get_base_packages_config(mock_conf)

        assert "kernel" in packages
        assert "base" in packages
        assert packages["kernel"] == "linux"
        # Verify some core Arch packages
        assert "base" in packages["base"]
        assert "base-devel" in packages["base"]
        assert "arch-install-scripts" in packages["base"]

    def test_detects_intel_microcode(self):
        """Should detect Intel CPU and include intel-ucode."""
        adapter = ArchAdapter()
        mock_conf = Mock()

        # Mock /proc/cpuinfo with Intel CPU
        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__.return_value = mock_file
            mock_file.__iter__.return_value = ["GenuineIntel\n"]
            mock_open.return_value = mock_file

            packages = adapter._get_base_packages_config(mock_conf)

            assert "intel-ucode" in packages["base"]

    def test_detects_amd_microcode(self):
        """Should detect AMD CPU and include amd-ucode."""
        adapter = ArchAdapter()
        mock_conf = Mock()

        # Mock /proc/cpuinfo with AMD CPU
        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__.return_value = mock_file
            mock_file.__iter__.return_value = ["AuthenticAMD\n"]
            mock_open.return_value = mock_file

            packages = adapter._get_base_packages_config(mock_conf)

            assert "amd-ucode" in packages["base"]

    def test_defaults_to_intel_on_read_error(self):
        """Should default to intel-ucode if /proc/cpuinfo read fails."""
        adapter = ArchAdapter()
        mock_conf = Mock()

        # Mock /proc/cpuinfo read failure
        with patch("builtins.open", side_effect=Exception("Read error")):
            packages = adapter._get_base_packages_config(mock_conf)

            # Should still include intel-ucode as default
            assert "intel-ucode" in packages["base"]


class TestArchInstallCommand:
    """Test Arch pacstrap install command generation."""

    def test_generates_pacstrap_command(self):
        """Should generate pacstrap command with kernel and base packages."""
        adapter = ArchAdapter()
        base_pkgs = {
            "kernel": "linux",
            "base": ["base", "base-devel"]
        }

        cmd = adapter._install_command(base_pkgs, "/mnt")

        assert "pacstrap -K /mnt" in cmd
        assert "linux" in cmd
        assert "base" in cmd
        assert "base-devel" in cmd

    def test_includes_custom_mount_point(self):
        """Should use provided mount point in command."""
        adapter = ArchAdapter()
        base_pkgs = {"kernel": "linux", "base": []}

        cmd = adapter._install_command(base_pkgs, "/custom/mount")

        assert "/custom/mount" in cmd

    def test_handles_multiple_base_packages(self):
        """Should handle multiple base packages correctly."""
        adapter = ArchAdapter()
        base_pkgs = {
            "kernel": "linux-lts",
            "base": ["pkg1", "pkg2", "pkg3"]
        }

        cmd = adapter._install_command(base_pkgs, "/mnt")

        assert "linux-lts" in cmd
        assert "pkg1" in cmd
        assert "pkg2" in cmd
        assert "pkg3" in cmd


class TestArchParseKernelFile:
    """Test parsing Arch kernel file output."""

    def test_extracts_kernel_path_from_pacman_output(self):
        """Should extract kernel file path from pacman -Ql output."""
        adapter = ArchAdapter()
        # Format: "arch linux 6.10.10-arch1-1 /usr/lib/modules/6.10.10-arch1-1/vmlinuz"
        output = "arch linux 6.10.10-arch1-1 /usr/lib/modules/6.10.10-arch1-1/vmlinuz"

        kernel_file, kver = adapter._parse_kernel_file(output)

        assert kernel_file == "/usr/lib/modules/6.10.10-arch1-1/vmlinuz"
        assert kver == "6.10.10-arch1-1"

    def test_extracts_version_from_module_path(self):
        """Should derive kernel version from the module directory name."""
        adapter = ArchAdapter()
        output = "arch linux 5.4.0-arch1-1 /usr/lib/modules/5.4.0-arch1-1/vmlinuz"

        kernel_file, kver = adapter._parse_kernel_file(output)

        # Version should be the directory name in the path
        assert kver == "5.4.0-arch1-1"

    def test_raises_on_invalid_path_format(self):
        """Should raise RuntimeError if kernel path has no slashes."""
        adapter = ArchAdapter()
        output = "arch linux 6.10 vmlinuz"  # No path separators

        with pytest.raises(RuntimeError, match="Invalid kernel file path"):
            adapter._parse_kernel_file(output)

    def test_raises_on_missing_version_in_path(self):
        """Should raise RuntimeError if version directory is missing."""
        adapter = ArchAdapter()
        output = "arch linux 6.10 /vmlinuz"  # No version directory

        with pytest.raises(RuntimeError, match="Could not extract kernel version"):
            adapter._parse_kernel_file(output)

    def test_handles_multiword_output(self):
        """Should extract last word as kernel file path."""
        adapter = ArchAdapter()
        output = "arch linux 6.10.10-arch1-1 /usr/lib/modules/6.10.10-arch1-1/vmlinuz-fallback"

        kernel_file, kver = adapter._parse_kernel_file(output)

        assert kernel_file == "/usr/lib/modules/6.10.10-arch1-1/vmlinuz-fallback"


class TestArchParseKernelVersion:
    """Test parsing Arch kernel version output."""

    def test_extracts_version_from_pacman_q_output(self):
        """Should extract version from 'pacman -Q' output."""
        adapter = ArchAdapter()
        output = "linux 6.10.10-arch1-1"

        kver = adapter._parse_kernel_version(output)

        assert kver == "6.10.10-arch1-1"

    def test_handles_whitespace(self):
        """Should handle leading/trailing whitespace."""
        adapter = ArchAdapter()
        output = "  linux   6.10.10-arch1-1  \n"

        kver = adapter._parse_kernel_version(output)

        assert kver == "6.10.10-arch1-1"

    def test_raises_on_invalid_format(self):
        """Should raise RuntimeError if output doesn't have version."""
        adapter = ArchAdapter()
        output = "linux"  # Missing version

        with pytest.raises(RuntimeError, match="Invalid kernel version output"):
            adapter._parse_kernel_version(output)

    def test_raises_on_empty_version(self):
        """Should raise RuntimeError if version is whitespace."""
        adapter = ArchAdapter()
        output = "linux    "  # No version, just spaces

        with pytest.raises(RuntimeError, match="Invalid kernel version"):
            adapter._parse_kernel_version(output)


class TestArchParseInstalledPackages:
    """Test parsing Arch installed packages output."""

    def test_parses_pacman_q_output(self):
        """Should parse 'pacman -Q' output into package dict."""
        adapter = ArchAdapter()
        output = "linux 6.10.10-arch1-1\nbase 2.0\nbase-devel 2.0"

        packages = adapter._parse_installed_packages(output)

        assert packages["linux"] == "6.10.10-arch1-1"
        assert packages["base"] == "2.0"
        assert packages["base-devel"] == "2.0"

    def test_handles_empty_lines(self):
        """Should skip empty lines."""
        adapter = ArchAdapter()
        output = "linux 6.10\n\nbase 2.0\n\n"

        packages = adapter._parse_installed_packages(output)

        assert len(packages) == 2
        assert "linux" in packages
        assert "base" in packages

    def test_handles_single_package(self):
        """Should handle single package."""
        adapter = ArchAdapter()
        output = "linux 6.10.10-arch1-1"

        packages = adapter._parse_installed_packages(output)

        assert packages == {"linux": "6.10.10-arch1-1"}

    def test_handles_empty_output(self):
        """Should return empty dict for empty output."""
        adapter = ArchAdapter()
        output = ""

        packages = adapter._parse_installed_packages(output)

        assert packages == {}

    def test_skips_malformed_lines(self):
        """Should skip lines without version."""
        adapter = ArchAdapter()
        output = "linux 6.10\nbroken-line\nbase 2.0"

        packages = adapter._parse_installed_packages(output)

        assert len(packages) == 2
        assert "broken-line" not in packages


class TestArchQueryPackageDbRefresh:
    """Test Arch package database refresh command generation."""

    def test_generates_pacman_sy_command(self):
        """Should generate 'pacman -Sy' command."""
        adapter = ArchAdapter()

        cmd = adapter._query_package_db_refresh("/mnt", new_generation=True)

        assert "pacman -Sy" in cmd
        assert "--noconfirm" in cmd

    def test_same_command_regardless_of_generation_flag(self):
        """Should use same command regardless of new_generation flag."""
        adapter = ArchAdapter()

        cmd_new = adapter._query_package_db_refresh("/mnt", new_generation=True)
        cmd_old = adapter._query_package_db_refresh("/mnt", new_generation=False)

        # Both should be the same for Arch (no difference between new/old generation)
        assert cmd_new == cmd_old


class TestArchQueryKernelFile:
    """Test Arch kernel file query."""

    @patch('kod.system.distro.adapters.arch.exec_chroot')
    def test_queries_pacman_for_kernel_file(self, mock_exec_chroot):
        """Should call exec_chroot with pacman -Ql command."""
        adapter = ArchAdapter()
        mock_exec_chroot.return_value = "arch linux 6.10 /usr/lib/modules/6.10/vmlinuz"

        output = adapter._query_kernel_file("/mnt", "linux")

        mock_exec_chroot.assert_called_once()
        call_args = mock_exec_chroot.call_args
        assert "pacman -Ql linux" in call_args[0][0]
        assert call_args[1]["mount_point"] == "/mnt"

    @patch('kod.system.distro.adapters.arch.exec_chroot')
    def test_uses_provided_package_name(self, mock_exec_chroot):
        """Should query the provided kernel package."""
        adapter = ArchAdapter()
        mock_exec_chroot.return_value = "output"

        adapter._query_kernel_file("/mnt", "linux-lts")

        call_args = mock_exec_chroot.call_args
        assert "pacman -Ql linux-lts" in call_args[0][0]


class TestArchQueryKernelVersion:
    """Test Arch kernel version query."""

    @patch('kod.system.distro.adapters.arch.exec_chroot')
    def test_queries_pacman_for_kernel_version(self, mock_exec_chroot):
        """Should call exec_chroot with pacman -Q command."""
        adapter = ArchAdapter()
        mock_exec_chroot.return_value = "linux 6.10.10-arch1-1"

        output = adapter._query_kernel_version("linux", "/mnt")

        mock_exec_chroot.assert_called_once()
        call_args = mock_exec_chroot.call_args
        assert "pacman -Q linux" in call_args[0][0]
        assert call_args[1]["mount_point"] == "/mnt"

    @patch('kod.system.distro.adapters.arch.exec_chroot')
    def test_uses_provided_kernel_name(self, mock_exec_chroot):
        """Should query the provided kernel package name."""
        adapter = ArchAdapter()
        mock_exec_chroot.return_value = "output"

        adapter._query_kernel_version("linux-lts", "/mnt")

        call_args = mock_exec_chroot.call_args
        assert "pacman -Q linux-lts" in call_args[0][0]


class TestArchQueryInstalledPackages:
    """Test Arch installed packages query."""

    @patch('kod.system.distro.adapters.arch.exec_chroot')
    def test_queries_pacman_for_all_packages(self, mock_exec_chroot):
        """Should call exec_chroot with pacman -Q command."""
        adapter = ArchAdapter()
        mock_exec_chroot.return_value = "linux 6.10\nbase 2.0"

        output = adapter._query_installed_packages("/mnt")

        mock_exec_chroot.assert_called_once()
        call_args = mock_exec_chroot.call_args
        assert "pacman -Q" in call_args[0][0]
        assert call_args[1]["mount_point"] == "/mnt"


class TestArchAdapterIntegration:
    """Integration tests for ArchAdapter public methods."""

    def test_get_base_packages_returns_dict_with_kernel_and_base(self):
        """get_base_packages should return properly structured dict."""
        adapter = ArchAdapter()
        mock_conf = Mock()
        mock_conf.boot = None

        packages = adapter.get_base_packages(mock_conf)

        assert isinstance(packages, dict)
        assert "kernel" in packages
        assert "base" in packages
        assert isinstance(packages["base"], list)

    @patch('kod.system.distro.adapters.arch.exec_chroot')
    def test_get_kernel_file_queries_and_parses(self, mock_exec_chroot):
        """get_kernel_file should query and parse correctly."""
        adapter = ArchAdapter()
        mock_exec_chroot.return_value = "arch linux 6.10 /usr/lib/modules/6.10/vmlinuz"

        kernel_file, kver = adapter.get_kernel_file("/mnt", "linux")

        assert kernel_file == "/usr/lib/modules/6.10/vmlinuz"
        assert kver == "6.10"


# ============================================================================
# DEBIAN ADAPTER TESTS
# ============================================================================


class TestDebianAdapterProperties:
    """Test DebianAdapter basic properties."""

    def test_package_manager_is_apt(self):
        """DebianAdapter should identify apt as its package manager."""
        adapter = DebianAdapter()
        assert adapter.package_manager == "apt"


class TestDebianGetBasePackagesConfig:
    """Test Debian-specific base package configuration."""

    def test_includes_debian_base_packages(self):
        """Should include Debian-specific base packages."""
        adapter = DebianAdapter()
        mock_conf = Mock()
        mock_conf.boot = None

        packages = adapter._get_base_packages_config(mock_conf)

        assert "kernel" in packages
        assert "base" in packages
        assert packages["kernel"] == "linux-image-amd64"
        # Verify some core Debian packages
        assert "btrfs-progs" in packages["base"]
        assert "systemd-boot" in packages["base"]
        assert "git" in packages["base"]
        assert "sudo" in packages["base"]

    def test_allows_config_override_of_kernel(self):
        """Should allow config to override kernel package."""
        adapter = DebianAdapter()
        mock_conf = Mock()
        mock_conf.boot = Mock()
        mock_conf.boot.kernel = Mock()
        mock_conf.boot.kernel.package = "linux-image-arm64"

        packages = adapter._get_base_packages_config(mock_conf)

        assert packages["kernel"] == "linux-image-arm64"

    def test_defaults_when_config_has_no_boot(self):
        """Should default to linux-image-amd64 when no boot config."""
        adapter = DebianAdapter()
        mock_conf = Mock()
        mock_conf.boot = None

        packages = adapter._get_base_packages_config(mock_conf)

        assert packages["kernel"] == "linux-image-amd64"

    def test_defaults_when_kernel_package_not_specified(self):
        """Should default when boot.kernel.package is not specified."""
        adapter = DebianAdapter()
        mock_conf = Mock()
        mock_conf.boot = Mock()
        mock_conf.boot.kernel = Mock()
        mock_conf.boot.kernel.package = None

        packages = adapter._get_base_packages_config(mock_conf)

        assert packages["kernel"] == "linux-image-amd64"


class TestDebianInstallCommand:
    """Test Debian apt-get install command generation."""

    def test_generates_apt_install_command(self):
        """Should generate apt-get install command with packages."""
        adapter = DebianAdapter()
        base_pkgs = {
            "kernel": "linux-image-amd64",
            "base": ["git", "sudo"]
        }

        cmd = adapter._install_command(base_pkgs, "/mnt")

        assert "apt-get install" in cmd
        assert "-y" in cmd
        assert "linux-image-amd64" in cmd
        assert "git" in cmd
        assert "sudo" in cmd

    def test_includes_noninteractive_frontend(self):
        """Should set DEBIAN_FRONTEND=noninteractive."""
        adapter = DebianAdapter()
        base_pkgs = {"kernel": "linux", "base": []}

        cmd = adapter._install_command(base_pkgs, "/mnt")

        assert "DEBIAN_FRONTEND=noninteractive" in cmd

    def test_handles_multiple_base_packages(self):
        """Should handle multiple base packages correctly."""
        adapter = DebianAdapter()
        base_pkgs = {
            "kernel": "linux-image-amd64",
            "base": ["pkg1", "pkg2", "pkg3", "pkg4"]
        }

        cmd = adapter._install_command(base_pkgs, "/mnt")

        assert "linux-image-amd64" in cmd
        assert "pkg1" in cmd
        assert "pkg2" in cmd
        assert "pkg3" in cmd
        assert "pkg4" in cmd


class TestDebianParseKernelFile:
    """Test parsing Debian kernel file output."""

    def test_extracts_kernel_package_from_apt_cache_output(self):
        """Should extract kernel package from apt-cache depends output."""
        adapter = DebianAdapter()
        # Format: "  Depends: linux-image-6.10.10"
        output = "  Depends: linux-image-6.10.10"

        kernel_file, kver = adapter._parse_kernel_file(output)

        assert kernel_file == "linux-image-6.10.10"
        assert kver == "6.10.10"

    def test_extracts_version_from_package_name(self):
        """Should derive kernel version from the package name."""
        adapter = DebianAdapter()
        output = "  Depends: linux-image-5.4.0-42"

        kernel_file, kver = adapter._parse_kernel_file(output)

        assert kernel_file == "linux-image-5.4.0-42"
        assert kver == "5.4.0-42"

    def test_raises_on_invalid_format_no_colon(self):
        """Should raise RuntimeError if output has no colon."""
        adapter = DebianAdapter()
        output = "InvalidFormat linux-image-6.10"

        with pytest.raises(RuntimeError, match="Invalid dependency format"):
            adapter._parse_kernel_file(output)

    def test_raises_on_missing_package_name(self):
        """Should raise RuntimeError if package name is missing."""
        adapter = DebianAdapter()
        output = "  Depends:   "  # Empty after colon

        with pytest.raises(RuntimeError, match="Could not extract kernel file"):
            adapter._parse_kernel_file(output)

    def test_raises_on_empty_version(self):
        """Should raise RuntimeError if version is empty."""
        adapter = DebianAdapter()
        output = "  Depends: linux-image-"  # No version after dash

        with pytest.raises(RuntimeError, match="Could not extract kernel version"):
            adapter._parse_kernel_file(output)

    def test_raises_on_empty_output(self):
        """Should raise RuntimeError on empty output."""
        adapter = DebianAdapter()
        output = ""

        with pytest.raises(RuntimeError, match="Invalid dependency output"):
            adapter._parse_kernel_file(output)

    def test_handles_complex_version_strings(self):
        """Should handle complex kernel versions with multiple parts."""
        adapter = DebianAdapter()
        output = "  Depends: linux-image-6.10.10-13-generic"

        kernel_file, kver = adapter._parse_kernel_file(output)

        assert kernel_file == "linux-image-6.10.10-13-generic"
        assert kver == "6.10.10-13-generic"


class TestDebianParseKernelVersion:
    """Test parsing Debian kernel version output."""

    def test_extracts_version_from_apt_cache_madison_output(self):
        """Should extract version from 'apt-cache madison' output."""
        adapter = DebianAdapter()
        # Format: "package-name | version | archive/dist source"
        output = "linux-image-6.10 | 6.10.10-1 | bookworm/main amd64 Packages"

        kver = adapter._parse_kernel_version(output)

        assert kver == "6.10.10-1"

    def test_handles_whitespace(self):
        """Should handle leading/trailing whitespace."""
        adapter = DebianAdapter()
        output = "  linux-image | 6.10.10-1 | bookworm/main  \n"

        kver = adapter._parse_kernel_version(output)

        assert kver == "6.10.10-1"

    def test_raises_on_invalid_format(self):
        """Should raise RuntimeError if output doesn't have pipe separator."""
        adapter = DebianAdapter()
        output = "linux-image 6.10.10-1 bookworm"  # Missing pipe

        with pytest.raises(RuntimeError, match="Invalid kernel version output"):
            adapter._parse_kernel_version(output)

    def test_raises_on_empty_version(self):
        """Should raise RuntimeError if version is whitespace."""
        adapter = DebianAdapter()
        output = "linux-image |   | bookworm"  # Empty version

        with pytest.raises(RuntimeError, match="Invalid kernel version"):
            adapter._parse_kernel_version(output)

    def test_raises_on_no_pipe_separator(self):
        """Should raise RuntimeError if no pipe separator."""
        adapter = DebianAdapter()
        output = "linux-image 6.10 bookworm"  # No pipe

        with pytest.raises(RuntimeError, match="Invalid kernel version output"):
            adapter._parse_kernel_version(output)


class TestDebianParseInstalledPackages:
    """Test parsing Debian installed packages output."""

    def test_parses_dpkg_l_output(self):
        """Should parse 'dpkg -l' output into package dict."""
        adapter = DebianAdapter()
        # dpkg -l format: "ii  package-name  version  arch  description"
        output = (
            "ii  linux-image-6.10  6.10.10-1  amd64  Linux kernel image\n"
            "ii  base-files  12.4  amd64  System base files\n"
            "ii  git  2.40.0  amd64  Fast, scalable, distributed revision control"
        )

        packages = adapter._parse_installed_packages(output)

        assert packages["linux-image-6.10"] == "6.10.10-1"
        assert packages["base-files"] == "12.4"
        assert packages["git"] == "2.40.0"

    def test_handles_empty_lines(self):
        """Should skip empty lines."""
        adapter = DebianAdapter()
        output = "ii  linux  6.10  amd64  Kernel\n\nii  base  2.0  amd64  Base\n\n"

        packages = adapter._parse_installed_packages(output)

        assert len(packages) == 2
        assert "linux" in packages
        assert "base" in packages

    def test_skips_non_installed_packages(self):
        """Should skip packages not marked as 'ii' (installed)."""
        adapter = DebianAdapter()
        output = (
            "ii  installed  1.0  amd64  Installed package\n"
            "un  uninstalled  2.0  amd64  Removed package\n"
            "rc  removed  3.0  amd64  Removed config\n"
            "ii  another  4.0  amd64  Another package"
        )

        packages = adapter._parse_installed_packages(output)

        # Only 'ii' status packages should be included
        assert len(packages) == 2
        assert "installed" in packages
        assert "another" in packages
        assert "uninstalled" not in packages
        assert "removed" not in packages

    def test_handles_single_package(self):
        """Should handle single package."""
        adapter = DebianAdapter()
        output = "ii  linux-image-6.10  6.10.10-1  amd64  Linux kernel image"

        packages = adapter._parse_installed_packages(output)

        assert packages == {"linux-image-6.10": "6.10.10-1"}

    def test_handles_empty_output(self):
        """Should return empty dict for empty output."""
        adapter = DebianAdapter()
        output = ""

        packages = adapter._parse_installed_packages(output)

        assert packages == {}

    def test_skips_malformed_lines(self):
        """Should skip lines without enough fields."""
        adapter = DebianAdapter()
        output = (
            "ii  linux  6.10  amd64  Kernel\n"
            "ii  malformed-package\n"
            "ii  another  2.0  amd64  Package"
        )

        packages = adapter._parse_installed_packages(output)

        assert len(packages) == 2
        assert "linux" in packages
        assert "another" in packages
        assert "malformed-package" not in packages

    def test_handles_complex_whitespace(self):
        """Should handle lines with multiple spaces/tabs."""
        adapter = DebianAdapter()
        # dpkg -l can have varying whitespace
        output = "ii  linux-image-6.10  6.10.10-1    amd64    Linux kernel\n"

        packages = adapter._parse_installed_packages(output)

        assert packages["linux-image-6.10"] == "6.10.10-1"


class TestDebianQueryPackageDbRefresh:
    """Test Debian package database refresh command generation."""

    def test_generates_apt_get_update_command(self):
        """Should generate 'apt-get update' command."""
        adapter = DebianAdapter()

        cmd = adapter._query_package_db_refresh("/mnt", new_generation=True)

        assert "apt-get update" in cmd

    def test_same_command_regardless_of_generation_flag(self):
        """Should use same command regardless of new_generation flag."""
        adapter = DebianAdapter()

        cmd_new = adapter._query_package_db_refresh("/mnt", new_generation=True)
        cmd_old = adapter._query_package_db_refresh("/mnt", new_generation=False)

        # Both should be the same for Debian (no difference between new/old generation)
        assert cmd_new == cmd_old
        assert cmd_new == "apt-get update"


class TestDebianQueryKernelFile:
    """Test Debian kernel file query."""

    @patch('kod.system.distro.adapters.debian.exec_chroot')
    def test_queries_apt_cache_for_kernel_file(self, mock_exec_chroot):
        """Should call exec_chroot with apt-cache depends command."""
        adapter = DebianAdapter()
        mock_exec_chroot.return_value = "  Depends: linux-image-6.10.10"

        output = adapter._query_kernel_file("/mnt", "linux-image-amd64")

        mock_exec_chroot.assert_called_once()
        call_args = mock_exec_chroot.call_args
        assert "apt-cache depends linux-image-amd64" in call_args[0][0]
        assert call_args[1]["mount_point"] == "/mnt"

    @patch('kod.system.distro.adapters.debian.exec_chroot')
    def test_uses_provided_package_name(self, mock_exec_chroot):
        """Should query the provided kernel package."""
        adapter = DebianAdapter()
        mock_exec_chroot.return_value = "output"

        adapter._query_kernel_file("/mnt", "linux-image-arm64")

        call_args = mock_exec_chroot.call_args
        assert "apt-cache depends linux-image-arm64" in call_args[0][0]


class TestDebianQueryKernelVersion:
    """Test Debian kernel version query."""

    @patch('kod.system.distro.adapters.debian.exec_chroot')
    def test_queries_apt_cache_for_kernel_version(self, mock_exec_chroot):
        """Should call exec_chroot with apt-cache madison command."""
        adapter = DebianAdapter()
        mock_exec_chroot.return_value = "linux-image-6.10 | 6.10.10-1 | bookworm/main"

        output = adapter._query_kernel_version("linux-image-amd64", "/mnt")

        mock_exec_chroot.assert_called_once()
        call_args = mock_exec_chroot.call_args
        assert "apt-cache madison linux-image-amd64" in call_args[0][0]
        assert call_args[1]["mount_point"] == "/mnt"

    @patch('kod.system.distro.adapters.debian.exec_chroot')
    def test_uses_provided_kernel_name(self, mock_exec_chroot):
        """Should query the provided kernel package name."""
        adapter = DebianAdapter()
        mock_exec_chroot.return_value = "output"

        adapter._query_kernel_version("linux-image-arm64", "/mnt")

        call_args = mock_exec_chroot.call_args
        assert "apt-cache madison linux-image-arm64" in call_args[0][0]


class TestDebianQueryInstalledPackages:
    """Test Debian installed packages query."""

    @patch('kod.system.distro.adapters.debian.exec_chroot')
    def test_queries_dpkg_for_all_packages(self, mock_exec_chroot):
        """Should call exec_chroot with dpkg -l command."""
        adapter = DebianAdapter()
        mock_exec_chroot.return_value = "ii  linux  6.10  amd64  Kernel\nii  base  2.0  amd64  Base"

        output = adapter._query_installed_packages("/mnt")

        mock_exec_chroot.assert_called_once()
        call_args = mock_exec_chroot.call_args
        assert "dpkg -l" in call_args[0][0]
        assert call_args[1]["mount_point"] == "/mnt"


class TestDebianAdapterIntegration:
    """Integration tests for DebianAdapter public methods."""

    def test_get_base_packages_returns_dict_with_kernel_and_base(self):
        """get_base_packages should return properly structured dict."""
        adapter = DebianAdapter()
        mock_conf = Mock()
        mock_conf.boot = None

        packages = adapter.get_base_packages(mock_conf)

        assert isinstance(packages, dict)
        assert "kernel" in packages
        assert "base" in packages
        assert isinstance(packages["base"], list)

    @patch('kod.system.distro.adapters.debian.exec_chroot')
    def test_get_kernel_file_queries_and_parses(self, mock_exec_chroot):
        """get_kernel_file should query and parse correctly."""
        adapter = DebianAdapter()
        mock_exec_chroot.return_value = "  Depends: linux-image-6.10.10"

        kernel_file, kver = adapter.get_kernel_file("/mnt", "linux-image-amd64")

        assert kernel_file == "linux-image-6.10.10"
        assert kver == "6.10.10"
