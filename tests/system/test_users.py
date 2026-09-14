"""Tests for kod/system/users.py (Phase 2)."""

import pytest


class TestUserManagement:
    """Test user operations."""

    def test_proc_user_home_callable(self):
        """proc_user_home() is callable."""
        from kod.system.users import proc_user_home
        
        assert callable(proc_user_home)
