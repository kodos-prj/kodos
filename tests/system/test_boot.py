"""Tests for kod/system/boot.py (Phase 2)."""

import pytest


class TestBootManagement:
    """Test boot operations."""

    def test_setup_bootloader_callable(self):
        """setup_bootloader() is callable."""
        from kod.system.boot import setup_bootloader
        
        assert callable(setup_bootloader)

    def test_create_boot_entry_callable(self):
        """create_boot_entry() is callable."""
        from kod.system.boot import create_boot_entry
        
        assert callable(create_boot_entry)

    def test_get_kernel_version_callable(self):
        """get_kernel_version() is callable."""
        from kod.system.boot import get_kernel_version
        
        assert callable(get_kernel_version)
