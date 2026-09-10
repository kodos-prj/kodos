"""Tests for Arch Linux distribution (Phase 2)."""

import pytest
from unittest.mock import patch, MagicMock, Mock
from src.kod.arch import kernel_update_required, get_list_of_dependencies, proc_repos


class TestArchDistribution:
    """Test Arch Linux implementation."""

    def test_arch_distribution_has_required_methods(self):
        """Arch distribution implements Distribution interface.
        
        This test will pass once arch.py is updated to inherit from Distribution.
        Phase 2b will implement ArchDistribution class with all required methods.
        """
        pytest.skip("Implement after arch.py is updated to use Distribution base class")


class TestKernelUpdateRequired:
    """Test kernel_update_required function with validation."""

    @patch('src.kod.arch.exec_chroot')
    def test_kernel_update_required_validates_kernel_version(self, mock_exec):
        """Malformed kernel version (no dots) should raise RuntimeError."""
        mock_exec.return_value = "linux 5"  # Malformed: no dots in version
        
        with pytest.raises(RuntimeError, match="Could not parse kernel architecture"):
            kernel_update_required(
                "linux",
                "linux",
                {"linux": "5"},
                "/mnt/chroot"
            )

    @patch('src.kod.arch.exec_chroot')
    def test_kernel_update_required_handles_empty_kernel_version(self, mock_exec):
        """Empty kernel version should raise RuntimeError."""
        mock_exec.return_value = "linux "  # Empty version
        
        with pytest.raises(RuntimeError, match="Invalid kernel version"):
            kernel_update_required(
                "linux",
                "linux",
                {"linux": ""},
                "/mnt/chroot"
            )

    @patch('src.kod.arch.exec_chroot')
    def test_kernel_update_required_valid_version(self, mock_exec):
        """Valid kernel version should parse successfully."""
        mock_exec.return_value = "linux 6.1.2-arch1-1"
        
        result = kernel_update_required(
            "linux",
            "linux",
            {"linux": "6.1.2-arch1-1"},
            "/mnt/chroot"
        )
        assert result is False  # Same version

    @patch('src.kod.arch.exec_chroot')
    def test_kernel_update_required_different_versions(self, mock_exec):
        """Different kernel versions should return True."""
        mock_exec.return_value = "linux 6.1.2-arch1-1"
        
        result = kernel_update_required(
            "linux",
            "linux",
            {"linux": "6.0.1-arch1-1"},
            "/mnt/chroot"
        )
        assert result is True


class TestGetListOfDependencies:
    """Test get_list_of_dependencies function."""

    @patch('src.kod.arch.exec')
    def test_get_list_of_dependencies_uses_fallback_when_group_not_found(self, mock_exec):
        """Fallback to -Si query should execute when -Sgq returns nothing."""
        def mock_exec_side_effect(cmd, **kwargs):
            if "-Sgq" in cmd:
                return ""  # Not a group, empty result
            elif "-Si" in cmd:
                return "Depends On: dep1 dep2 dep3"
            return ""
        
        mock_exec.side_effect = mock_exec_side_effect
        result = get_list_of_dependencies("mypackage")
        # Should get dependencies from fallback, not empty string
        assert "dep1" in result
        assert len(result) > 0  # Fallback should have executed
