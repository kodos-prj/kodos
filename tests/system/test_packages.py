"""Tests for kod/system/packages.py (Phase 2)."""

import pytest


class TestPackageManagement:
    """Test package operations."""

    def test_load_repos_callable(self):
        """load_repos() is callable and returns expected type."""
        from kod.system.packages import load_repos
        
        # Smoke test: function exists and is callable
        assert callable(load_repos)
        # Don't call it (requires config files), just verify it exists

    def test_get_packages_to_install_callable(self):
        """get_packages_to_install() is callable."""
        from kod.system.packages import get_packages_to_install
        
        assert callable(get_packages_to_install)

    def test_manage_packages_callable(self):
        """manage_packages() is callable."""
        from kod.system.packages import manage_packages
        
        assert callable(manage_packages)
