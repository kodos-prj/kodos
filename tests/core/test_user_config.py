"""Tests for kod/core/user_config.py (Phase 2)."""

import pytest


class TestUserConfigWorkflow:
    """Test user config workflow."""

    def test_configure_user_dotfiles_callable(self):
        """configure_user_dotfiles() is callable."""
        from kod.core.user_config import configure_user_dotfiles
        
        assert callable(configure_user_dotfiles)

    def test_configure_user_scripts_callable(self):
        """configure_user_scripts() is callable."""
        from kod.core.user_config import configure_user_scripts
        
        assert callable(configure_user_scripts)
