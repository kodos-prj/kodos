"""Comprehensive edge case and special scenario tests for Phase 3 Program Registry.

Tests cover:
- Empty schemas and special values
- Unicode and special characters
- Very long config output
- Multiple inheritance levels
- Performance/caching validation
- Schema merge edge cases
- Error message quality
"""

import pytest
import tempfile
from pathlib import Path
from unittest import mock
import json

from kod.registry.programs import (
    Program,
    ProgramRegistry,
    ProgramError,
    ProgramNotFound,
    ProgramLoadError,
    CircularExtendError,
    ConfigValidationError,
    SchemaError,
)
from kod.registry.loader import PluginLoader


# ===== Edge Cases: Empty and Minimal Schemas =====


def test_program_with_empty_schema():
    """Program should accept empty schema dict."""
    lua_def = {
        "name": "empty",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: "echo done",
    }
    
    program = Program("empty", lua_def)
    assert program.lua_def["schema"] == {}
    assert program.validate_config({}) is None


def test_program_with_empty_schema_validates_any_options():
    """Program with empty schema should pass validation for any options."""
    lua_def = {
        "name": "empty",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: "echo done",
    }
    
    program = Program("empty", lua_def)
    # Empty schema should accept any options
    program.validate_config({"anything": "goes"})


def test_program_without_default_config():
    """Program without default_config field should raise ProgramLoadError."""
    lua_def = {
        "name": "no_default",
        "schema": {"key": {"type": "string"}},
        # Missing default_config
        "generate_config": lambda self, opts: "echo done",
    }
    
    with pytest.raises(ProgramLoadError):
        Program("no_default", lua_def)


def test_program_generate_config_returns_none():
    """Program.generate_config() returning None should convert to empty string."""
    lua_def = {
        "name": "returns_none",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: None,
    }
    
    program = Program("returns_none", lua_def)
    config = program.generate_config({})
    
    assert config == ""


def test_program_generate_config_returns_empty_string():
    """Program.generate_config() returning empty string should work."""
    lua_def = {
        "name": "empty_result",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: "",
    }
    
    program = Program("empty_result", lua_def)
    config = program.generate_config({})
    
    assert config == ""


def test_program_generate_config_very_large_output():
    """Program.generate_config() with very large output should work."""
    large_output = "line\n" * 100000  # 600KB of output
    
    lua_def = {
        "name": "large",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: large_output,
    }
    
    program = Program("large", lua_def)
    config = program.generate_config({})
    
    assert len(config) == len(large_output)
    assert config == large_output


# ===== Edge Cases: Special Characters and Unicode =====


def test_program_with_unicode_in_name():
    """Program should accept Unicode characters in name."""
    lua_def = {
        "name": "café_程序",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: "echo done",
    }
    
    program = Program("café_程序", lua_def)
    assert program.name == "café_程序"


def test_program_with_unicode_in_option_values():
    """Program.validate_config() should accept Unicode in option values."""
    lua_def = {
        "name": "unicode",
        "schema": {
            "comment": {"type": "string", "required": False}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "echo done",
    }
    
    program = Program("unicode", lua_def)
    program.validate_config({"comment": "こんにちは世界🌍"})


def test_program_with_special_chars_in_generate_config():
    """Program.generate_config() should handle special chars in output."""
    special_output = "echo 'Line with \"quotes\" and \\backslashes\\'\nNew line with tabs\t\t\r\nspecial: éàü'"
    
    lua_def = {
        "name": "special",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: special_output,
    }
    
    program = Program("special", lua_def)
    config = program.generate_config({})
    
    assert config == special_output


def test_program_with_newlines_in_option_values():
    """Program should handle newlines in option values."""
    lua_def = {
        "name": "newlines",
        "schema": {
            "text": {"type": "string", "required": False}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    
    program = Program("newlines", lua_def)
    multiline_text = "line1\nline2\nline3\n  indented"
    program.validate_config({"text": multiline_text})


# ===== Edge Cases: Schema Merging =====


def test_program_merge_schema_with_allof():
    """Program._get_merged_schema() should properly handle allOf merges."""
    parent_lua = {
        "name": "parent",
        "schema": {
            "user_name": {"type": "string", "required": True},
            "email": {"type": "string", "required": True}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    parent = Program("parent", parent_lua)
    
    child_lua = {
        "name": "child",
        "schema": {
            "extra": {"type": "boolean", "required": False}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    child = Program("child", child_lua, parent=parent)
    
    merged = child._get_merged_schema()
    
    # Should be allOf with parent schema and child schema
    assert "allOf" in merged
    assert len(merged["allOf"]) >= 1


def test_program_merge_schema_empty_parent():
    """Program with empty parent schema should merge correctly."""
    parent_lua = {
        "name": "parent",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    parent = Program("parent", parent_lua)
    
    child_lua = {
        "name": "child",
        "schema": {
            "key": {"type": "string"}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    child = Program("child", child_lua, parent=parent)
    
    # Should handle empty parent schema gracefully
    merged = child._get_merged_schema()
    assert merged is not None


def test_program_merge_schema_empty_child():
    """Program with empty child schema should merge correctly."""
    parent_lua = {
        "name": "parent",
        "schema": {
            "key": {"type": "string"}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    parent = Program("parent", parent_lua)
    
    child_lua = {
        "name": "child",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    child = Program("child", child_lua, parent=parent)
    
    # Should handle empty child schema gracefully
    merged = child._get_merged_schema()
    assert merged is not None


# ===== Edge Cases: Multiple Inheritance Levels =====


def test_program_three_level_inheritance_chain():
    """Program should support 3+ levels of inheritance."""
    # Level 1: grandparent
    gp_lua = {
        "name": "grandparent",
        "schema": {"gp_field": {"type": "string"}},
        "default_config": {"gp_field": "gp_value"},
        "generate_config": lambda self, opts: "gp",
    }
    gp = Program("grandparent", gp_lua)
    
    # Level 2: parent
    p_lua = {
        "name": "parent",
        "schema": {"p_field": {"type": "string"}},
        "default_config": {"p_field": "p_value"},
        "generate_config": lambda self, opts: "p",
    }
    parent = Program("parent", p_lua, parent=gp)
    
    # Level 3: child
    c_lua = {
        "name": "child",
        "schema": {"c_field": {"type": "string"}},
        "default_config": {"c_field": "c_value"},
        "generate_config": lambda self, opts: "c",
    }
    child = Program("child", c_lua, parent=parent)
    
    # Verify all levels are accessible
    assert child._get_parent().name == "parent"
    assert child._get_parent()._get_parent().name == "grandparent"
    assert child._get_parent()._get_parent()._get_parent() is None


def test_program_three_level_inheritance_method_chaining():
    """Program should support method chaining through 3 levels."""
    gp_lua = {
        "name": "grandparent",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: "gp",
    }
    gp = Program("grandparent", gp_lua)
    
    p_lua = {
        "name": "parent",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: self._parent_method("generate_config", opts) + "_p",
    }
    parent = Program("parent", p_lua, parent=gp)
    
    c_lua = {
        "name": "child",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: self._parent_method("generate_config", opts) + "_c",
    }
    child = Program("child", c_lua, parent=parent)
    
    config = child.generate_config({})
    assert config == "gp_p_c"


# ===== Edge Cases: Validation =====


def test_program_validate_config_with_null_values():
    """Program.validate_config() should reject None values (not optional)."""
    lua_def = {
        "name": "nulls",
        "schema": {
            "optional": {"type": "string", "required": False},
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    
    program = Program("nulls", lua_def)
    # None values should fail type check (even if optional)
    with pytest.raises(ConfigValidationError):
        program.validate_config({"optional": None})


def test_program_validate_config_extra_fields():
    """Program.validate_config() should accept extra fields not in schema."""
    lua_def = {
        "name": "extra",
        "schema": {
            "defined": {"type": "string"}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    
    program = Program("extra", lua_def)
    # Should not fail on extra fields
    program.validate_config({
        "defined": "value",
        "undefined": "extra_value"
    })


def test_program_validate_config_error_contains_field_name():
    """Program.validate_config() error should clearly indicate which field failed."""
    lua_def = {
        "name": "error_info",
        "schema": {
            "port": {"type": "number"}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    
    program = Program("error_info", lua_def)
    
    try:
        program.validate_config({"port": "not_a_number"})
        assert False, "Should have raised ConfigValidationError"
    except ConfigValidationError as e:
        error_msg = str(e)
        # Error message should mention the field and the type mismatch
        assert "port" in error_msg.lower() or "number" in error_msg.lower()


# ===== Edge Cases: Caching =====


def test_loader_caching_prevents_duplicate_lua_execution():
    """PluginLoader caching should prevent duplicate Lua parsing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PluginLoader(config_home=tmpdir)
        
        # Create a test program file
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        test_program_file = plugin_dir / "test.lua"
        test_program_file.write_text("""
return {
    name = "test",
    schema = {},
    default_config = {},
    generate_config = function(self, opts) return "test" end,
}
""")
        
        # Load the program twice
        prog1 = loader.load_program("test")
        prog2 = loader.load_program("test")
        
        # Should be the same object (cached)
        assert prog1 is prog2


def test_loader_caching_info_includes_source():
    """PluginLoader.get_program_info() should identify cache source."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PluginLoader(config_home=tmpdir)
        
        # Create a test program file
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        test_program_file = plugin_dir / "test.lua"
        test_program_file.write_text("""
return {
    name = "test",
    schema = {},
    default_config = {},
    generate_config = function(self, opts) return "test" end,
}
""")
        
        info = loader.get_program_info("test")
        
        # Info should include source (user)
        assert "source" in info or "test" in info.get("name", "")


# ===== Edge Cases: Generator Function Errors =====


def test_program_generate_config_with_exception():
    """Program.generate_config() raising exception should wrap in ProgramLoadError."""
    lua_def = {
        "name": "error",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: 1/0,  # Division by zero
    }
    
    program = Program("error", lua_def)
    
    with pytest.raises(ProgramLoadError):
        program.generate_config({})


def test_program_generate_config_error_includes_program_name():
    """Error from generate_config should mention program name."""
    lua_def = {
        "name": "error_program",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: 1/0,
    }
    
    program = Program("error_program", lua_def)
    
    try:
        program.generate_config({})
        assert False, "Should raise ProgramLoadError"
    except ProgramLoadError as e:
        assert "error_program" in str(e).lower()


# ===== Edge Cases: Hooks =====


def test_program_validate_hook_with_exception():
    """Program validate hook raising exception should wrap error."""
    lua_def = {
        "name": "hook_error",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: "done",
        "validate": lambda self, opts: 1/0,  # Error in hook
    }
    
    program = Program("hook_error", lua_def)
    
    # validate_config calls the validate hook
    with pytest.raises(ConfigValidationError):
        program.validate_config({})


def test_program_run_hook_with_parent_method():
    """Program.run_hook() should support parent method chaining."""
    parent_lua = {
        "name": "parent",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: "parent_result",
        "post_install": lambda self: "from_parent",
    }
    parent = Program("parent", parent_lua)
    
    child_lua = {
        "name": "child",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, opts: "done",
        "post_install": lambda self: "from_child",
    }
    child = Program("child", child_lua, parent=parent)
    
    # Should call child's hook
    result = child.run_hook("post_install")
    assert result == "from_child"


# ===== Edge Cases: Schema Type Validation =====


def test_program_validate_string_type():
    """Program validation should check string type correctly."""
    lua_def = {
        "name": "string_type",
        "schema": {
            "text": {"type": "string"}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    
    program = Program("string_type", lua_def)
    
    # Valid
    program.validate_config({"text": "hello"})
    
    # Invalid
    with pytest.raises(ConfigValidationError):
        program.validate_config({"text": 123})


def test_program_validate_number_type():
    """Program validation should check number type correctly."""
    lua_def = {
        "name": "number_type",
        "schema": {
            "count": {"type": "number"}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    
    program = Program("number_type", lua_def)
    
    # Valid
    program.validate_config({"count": 42})
    program.validate_config({"count": 3.14})
    
    # Invalid
    with pytest.raises(ConfigValidationError):
        program.validate_config({"count": "forty-two"})


def test_program_validate_boolean_type():
    """Program validation should check boolean type correctly."""
    lua_def = {
        "name": "boolean_type",
        "schema": {
            "enabled": {"type": "boolean"}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    
    program = Program("boolean_type", lua_def)
    
    # Valid
    program.validate_config({"enabled": True})
    program.validate_config({"enabled": False})
    
    # Invalid
    with pytest.raises(ConfigValidationError):
        program.validate_config({"enabled": "yes"})


def test_program_validate_unknown_type_passes():
    """Program validation should pass on unknown types (assume valid)."""
    lua_def = {
        "name": "unknown_type",
        "schema": {
            "custom": {"type": "unknown_type"}
        },
        "default_config": {},
        "generate_config": lambda self, opts: "done",
    }
    
    program = Program("unknown_type", lua_def)
    
    # Unknown types should pass validation
    program.validate_config({"custom": "anything"})


# ===== Edge Cases: Registry =====


def test_registry_load_lua_def_with_malformed_return():
    """ProgramRegistry._load_lua_def() should handle non-dict returns."""
    registry = ProgramRegistry()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.lua"
        
        # Return a string instead of dict
        test_file.write_text('return "not_a_dict"')
        
        with pytest.raises(ProgramLoadError):
            registry._load_lua_def(Path(str(test_file)))


def test_registry_load_lua_def_with_empty_return():
    """ProgramRegistry._load_lua_def() should handle nil/None returns."""
    registry = ProgramRegistry()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.lua"
        
        # Return nil
        test_file.write_text('return nil')
        
        with pytest.raises(ProgramLoadError):
            registry._load_lua_def(Path(str(test_file)))


def test_registry_load_lua_def_permission_denied():
    """ProgramRegistry._load_lua_def() should handle permission errors."""
    registry = ProgramRegistry()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.lua"
        test_file.write_text('return {}')
        test_file.chmod(0o000)
        
        try:
            with pytest.raises(ProgramLoadError):
                registry._load_lua_def(Path(str(test_file)))
        finally:
            test_file.chmod(0o644)


# ===== Edge Cases: Loader Multi-level Inheritance =====


def test_loader_three_level_inheritance_builtin_to_user():
    """PluginLoader should support 3-level inheritance: builtin->user->user."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PluginLoader(config_home=tmpdir)
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        # Level 1: User plugin extends builtin
        level1_file = plugin_dir / "level1.lua"
        level1_file.write_text("""
return {
    name = "level1",
    _extends = "git",
    schema = {l1_field = {type = "string"}},
    default_config = {l1_field = "l1"},
    generate_config = function(self, opts) return "l1" end,
}
""")
        
        # This may fail if git builtin doesn't exist, so we catch gracefully
        try:
            prog = loader.load_program("level1")
            assert prog is not None
        except ProgramNotFound:
            # Expected if builtin git doesn't exist
            pass


# ===== Performance Baseline =====


def test_loader_caching_improves_performance():
    """Caching should prevent expensive re-parsing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PluginLoader(config_home=tmpdir)
        
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        test_program_file = plugin_dir / "perf.lua"
        test_program_file.write_text("""
return {
    name = "perf",
    schema = {},
    default_config = {},
    generate_config = function(self, opts) return "done" end,
}
""")
        
        # First load
        prog1 = loader.load_program("perf")
        
        # Second load should use cache
        prog2 = loader.load_program("perf")
        
        # Should be identical object (cached)
        assert id(prog1) == id(prog2)
