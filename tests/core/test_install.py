"""Tests for kod/core/install.py (Phase 2)."""

import pytest


class TestInstallWorkflow:
    """Test installation workflow."""

    def test_configure_system_callable(self):
        """configure_system() is callable."""
        from kod.core.install import configure_system
        
        assert callable(configure_system)
