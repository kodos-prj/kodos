"""Tests for kod/system/services.py (Phase 2)."""

import pytest


class TestServiceManagement:
    """Test service operations."""

    def test_enable_services_callable(self):
        """enable_services() is callable."""
        from kod.system.services import enable_services
        
        assert callable(enable_services)

    def test_disable_services_callable(self):
        """disable_services() is callable."""
        from kod.system.services import disable_services
        
        assert callable(disable_services)

    def test_enable_user_services_callable(self):
        """enable_user_services() is callable."""
        from kod.system.services import enable_user_services
        
        assert callable(enable_user_services)

    def test_get_services_to_enable_callable(self):
        """get_services_to_enable() is callable."""
        from kod.system.services import get_services_to_enable
        
        assert callable(get_services_to_enable)
