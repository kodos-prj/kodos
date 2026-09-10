"""Tests for Debian/Ubuntu distribution (Phase 2)."""

import pytest
from unittest.mock import patch, MagicMock
from src.kod.debian import kernel_update_required


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
