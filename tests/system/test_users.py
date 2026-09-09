"""Tests for kod/system/users.py (Phase 2)."""

import pytest


class TestUserManagement:
    """Test user operations."""

    def test_proc_users_callable(self):
        """proc_users() is callable."""
        from kod.system.users import proc_users
        
        assert callable(proc_users)

    def test_create_user_callable(self):
        """create_user() is callable."""
        from kod.system.users import create_user
        
        assert callable(create_user)

    def test_proc_user_home_callable(self):
        """proc_user_home() is callable."""
        from kod.system.users import proc_user_home
        
        assert callable(proc_user_home)
