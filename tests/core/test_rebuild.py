"""Tests for kod/core/rebuild.py (Phase 2)."""

import pytest


class TestRebuildWorkflow:
    """Test rebuild workflow."""

    def test_create_next_generation_callable(self):
        """create_next_generation() is callable."""
        from kod.core.rebuild import create_next_generation
        
        assert callable(create_next_generation)

    def test_get_generation_callable(self):
        """get_generation() is callable."""
        from kod.core.rebuild import get_generation
        
        assert callable(get_generation)

    def test_get_max_generation_callable(self):
        """get_max_generation() is callable."""
        from kod.core.rebuild import get_max_generation
        
        assert callable(get_max_generation)
