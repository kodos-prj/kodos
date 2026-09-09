"""Tests for config schema (Phase 1).

These are placeholder tests showing the expected structure.
Implement as you work on kod/config/schema.py.
"""

import pytest


@pytest.mark.phase1
class TestSchema:
    """Test configuration schema."""

    def test_schema_creation(self):
        """Schema can be created and initialized."""
        pytest.skip("Implement after schema.py is written")

    def test_schema_option_types(self):
        """Schema defines standard option types."""
        pytest.skip("Implement after schema.py is written")

    def test_schema_lookup(self):
        """Can look up options in schema."""
        pytest.skip("Implement after schema.py is written")

    def test_schema_validation_error_messages(self):
        """Validation errors have helpful messages."""
        pytest.skip("Implement after schema.py is written")


@pytest.mark.phase1
class TestValidator:
    """Test configuration validation."""

    def test_validator_accepts_valid_config(self):
        """Validator accepts valid configurations."""
        pytest.skip("Implement after validator.py is written")

    def test_validator_rejects_typos(self):
        """Validator catches typos in option names."""
        pytest.skip("Implement after validator.py is written")

    def test_validator_checks_types(self):
        """Validator checks option types."""
        pytest.skip("Implement after validator.py is written")

    def test_validator_checks_enums(self):
        """Validator validates enum values."""
        pytest.skip("Implement after validator.py is written")


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
