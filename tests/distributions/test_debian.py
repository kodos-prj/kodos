"""Tests for Debian/Ubuntu distribution (Phase 2)."""

import pytest
from unittest.mock import patch, MagicMock, call
from src.kod.debian import kernel_update_required, install_essentials_pkgs


class TestInstallEssentialsPackagesVerification:
    """Test install_essentials_pkgs verifies package installation."""

    @patch('src.kod.debian.exec')
    @patch('src.kod.debian.exec_chroot')
    def test_install_essentials_pkgs_verifies_packages_installed(self, mock_exec_chroot, mock_exec):
        """After apt install, should verify packages are actually installed."""
        # Setup: track calls to verify we check dpkg after install
        install_call_count = 0
        
        def side_effect(cmd, **kwargs):
            nonlocal install_call_count
            if "apt install" in cmd and "debootstrap" in cmd:
                # Initial setup apt call
                return ""
            elif "debootstrap" in cmd:
                return ""
            elif "dpkg -l" in cmd:
                # Verification: check packages are listed as installed (ii status)
                return "ii  linux-image-amd64  6.1.2-1  all  Linux kernel image for amd64\nii  git  1:2.34.1-1  all  fast version control system"
            return ""
        
        mock_exec_chroot.side_effect = side_effect
        
        base_pkgs = {
            "kernel": "linux-image-amd64",
            "base": ["git"]
        }
        
        # Should not raise an error
        install_essentials_pkgs(base_pkgs, "/mnt")
        
        # Verify dpkg -l was called to verify installation
        dpkg_calls = [c for c in mock_exec_chroot.call_args_list if "dpkg -l" in str(c)]
        assert len(dpkg_calls) > 0, "Should verify packages with dpkg -l after install"

    @patch('src.kod.debian.exec')
    @patch('src.kod.debian.exec_chroot')
    def test_install_essentials_pkgs_detects_failed_installation(self, mock_exec_chroot, mock_exec):
        """If package not in dpkg list after apt install, should raise error."""
        def side_effect(cmd, **kwargs):
            if "apt install" in cmd and "debootstrap" in cmd:
                return ""
            elif "debootstrap" in cmd:
                return ""
            elif "dpkg -l" in cmd:
                # Verification: git NOT actually installed (not in list)
                return "ii  linux-image-amd64  6.1.2-1  all  Linux kernel image for amd64"
            return ""
        
        mock_exec_chroot.side_effect = side_effect
        
        base_pkgs = {
            "kernel": "linux-image-amd64",
            "base": ["git"]
        }
        
        # Should raise error about failed installation
        with pytest.raises(RuntimeError, match="not installed|failed to install"):
            install_essentials_pkgs(base_pkgs, "/mnt")


class TestDebianDistribution:
    """Test Debian implementation."""

    def test_debian_distribution_has_required_methods(self):
        """Debian distribution implements Distribution interface.
        
        This test will pass once debian.py is updated to inherit from Distribution.
        Phase 2b will implement DebianDistribution class with all required methods.
        """
        pytest.skip("Implement after debian.py is updated to use Distribution base class")


class TestKernelUpdateRequired:
    """Test kernel_update_required function with validation."""

    @patch('src.kod.debian.exec_chroot')
    def test_kernel_update_required_validates_kernel_version(self, mock_exec):
        """Malformed kernel version (no dots) should raise RuntimeError."""
        mock_exec.return_value = "linux-image | 5"  # Malformed: no dots in version
        
        with pytest.raises(RuntimeError, match="Could not parse kernel architecture"):
            kernel_update_required(
                "linux-image-amd64",
                "linux-image-amd64",
                {"linux-image-amd64": "5"},
                "/mnt/chroot"
            )

    @patch('src.kod.debian.exec_chroot')
    def test_kernel_update_required_handles_empty_kernel_version(self, mock_exec):
        """Empty kernel version should raise RuntimeError."""
        mock_exec.return_value = "linux-image | "  # Empty version
        
        with pytest.raises(RuntimeError, match="Invalid kernel version"):
            kernel_update_required(
                "linux-image-amd64",
                "linux-image-amd64",
                {"linux-image-amd64": ""},
                "/mnt/chroot"
            )

    @patch('src.kod.debian.exec_chroot')
    def test_kernel_update_required_valid_version(self, mock_exec):
        """Valid kernel version should parse successfully."""
        mock_exec.return_value = "linux-image-amd64 | 6.1.2-1"
        
        result = kernel_update_required(
            "linux-image-amd64",
            "linux-image-amd64",
            {"linux-image-amd64": "6.1.2-1"},
            "/mnt/chroot"
        )
        assert result is False  # Same version

    @patch('src.kod.debian.exec_chroot')
    def test_kernel_update_required_different_versions(self, mock_exec):
        """Different kernel versions should return True."""
        mock_exec.return_value = "linux-image-amd64 | 6.1.2-1"
        
        result = kernel_update_required(
            "linux-image-amd64",
            "linux-image-amd64",
            {"linux-image-amd64": "6.0.1-1"},
            "/mnt/chroot"
        )
        assert result is True
