"""Placeholder tests for not-yet-implemented Phase 1 modules.

Implemented coverage lives in:
- test_validator.py (schema + validator unit tests)
- test_cli.py (kod config validate CLI)
- test_example_config.py (end-to-end with real example config)
"""

import pytest


@pytest.mark.phase1
class TestLoader:
    """Test configuration loading."""

    def test_loader_loads_lua_config(self):
        """Loader can load Lua config files."""
        pytest.skip("Implement after loader.py is written")

    def test_loader_resolves_imports(self):
        """Loader resolves module imports."""
        pytest.skip("Implement after loader.py is written")

    def test_loader_merges_configs(self):
        """Loader merges configs from multiple files."""
        pytest.skip("Implement after loader.py is written")

    def test_loader_detects_circular_imports(self):
        """Loader detects and rejects circular imports."""
        pytest.skip("Implement after loader.py is written")


@pytest.mark.phase1
class TestCompiler:
    """Test configuration compilation."""

    def test_compiler_resolves_dependencies(self):
        """Compiler resolves dependency implications."""
        pytest.skip("Implement after compiler.py is written")

    def test_compiler_gnome_implies_gdm(self):
        """Compiler: GNOME desktop implies gdm display manager."""
        pytest.skip("Implement after compiler.py is written")

    def test_compiler_detects_conflicts(self):
        """Compiler detects conflicting options."""
        pytest.skip("Implement after compiler.py is written")

    def test_compiler_generates_install_plan(self):
        """Compiler generates an executable install plan."""
        pytest.skip("Implement after compiler.py is written")
