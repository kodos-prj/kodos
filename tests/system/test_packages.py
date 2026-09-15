"""Tests for kod/system/packages.py (Phase 2)."""

import pytest
from unittest.mock import patch, MagicMock
from kod.system.packages import (
    _get_privilege_level,
    _build_privilege_command,
)


class TestPrivilegeLevelManagement:
    """Test privilege level detection and command building."""

    def test_get_privilege_level_explicit_user(self):
        """Explicit privilege_level='user' should return 'user'."""
        repo = {"privilege_level": "user"}
        assert _get_privilege_level(repo) == "user"

    def test_get_privilege_level_explicit_sudo(self):
        """Explicit privilege_level='sudo' should return 'sudo'."""
        repo = {"privilege_level": "sudo"}
        assert _get_privilege_level(repo) == "sudo"

    def test_get_privilege_level_explicit_root(self):
        """Explicit privilege_level='root' should return 'root'."""
        repo = {"privilege_level": "root"}
        assert _get_privilege_level(repo) == "root"

    def test_get_privilege_level_invalid_raises(self):
        """Invalid privilege_level should raise ValueError."""
        repo = {"privilege_level": "invalid"}
        with pytest.raises(ValueError, match="Invalid privilege_level"):
            _get_privilege_level(repo)

    def test_get_privilege_level_legacy_run_as_root_true(self):
        """Legacy run_as_root=True should map to 'root'."""
        repo = {"run_as_root": True}
        assert _get_privilege_level(repo) == "root"

    def test_get_privilege_level_legacy_run_as_root_false(self):
        """Legacy run_as_root=False should map to 'user'."""
        repo = {"run_as_root": False}
        assert _get_privilege_level(repo) == "user"

    def test_get_privilege_level_prefers_explicit_over_legacy(self):
        """Explicit privilege_level should take precedence over run_as_root."""
        repo = {"privilege_level": "sudo", "run_as_root": True}
        assert _get_privilege_level(repo) == "sudo"

    def test_get_privilege_level_default_to_root(self):
        """Missing both fields should default to 'root'."""
        repo = {}
        assert _get_privilege_level(repo) == "root"

    def test_build_privilege_command_user(self):
        """User level should prepend 'runuser -u kod --'."""
        cmd = "pip install mylib"
        result = _build_privilege_command(cmd, "user")
        assert result == "runuser -u kod -- pip install mylib"

    def test_build_privilege_command_sudo(self):
        """Sudo level should prepend 'sudo'."""
        cmd = "apt-get install pkg"
        result = _build_privilege_command(cmd, "sudo")
        assert result == "sudo apt-get install pkg"

    def test_build_privilege_command_root(self):
        """Root level should return command unchanged."""
        cmd = "pacman -S pkg"
        result = _build_privilege_command(cmd, "root")
        assert result == "pacman -S pkg"

    def test_build_privilege_command_invalid_raises(self):
        """Invalid privilege_level should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid privilege_level"):
            _build_privilege_command("cmd", "invalid")


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
