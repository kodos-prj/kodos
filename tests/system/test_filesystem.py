"""Tests for kod/system/filesystem.py (Phase 2)."""

import pytest


class TestFilesystemOperations:
    """Test filesystem operations."""

    def test_create_filesystem_hierarchy_callable(self):
        """create_filesystem_hierarchy() is callable."""
        from kod.system.filesystem import create_filesystem_hierarchy
        
        assert callable(create_filesystem_hierarchy)

    def test_generate_fstab_callable(self):
        """generate_fstab() is callable."""
        from kod.system.filesystem import generate_fstab
        
        assert callable(generate_fstab)

    def test_load_fstab_callable(self):
        """load_fstab() is callable."""
        from kod.system.filesystem import load_fstab
        
        assert callable(load_fstab)
