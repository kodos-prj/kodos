"""Tests for kod.registry.programs (Task 1: Program class & ProgramRegistry).

Tests the core Program and ProgramRegistry classes, error hierarchy,
schema validation, and inheritance.
"""

import pytest
import tempfile
from pathlib import Path
from unittest import mock
import sys

# Mock lupa before importing programs module (to prevent actual Lua execution during import)
# This allows the programs module to import without requiring lupa installed
_real_lupa = sys.modules.get('lupa')
sys.modules['lupa'] = mock.MagicMock()

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

# Restore real lupa for tests that need it
if _real_lupa:
    sys.modules['lupa'] = _real_lupa
else:
    # If lupa wasn't loaded before, try to restore it from reimport
    import importlib
    try:
        sys.modules.pop('lupa', None)
        import lupa
        sys.modules['lupa'] = lupa
    except ImportError:
        # lupa not available, keep mock
        pass



# ===== Test Error Hierarchy =====


def test_program_error_is_base_exception():
    """ProgramError should be base for all program errors."""
    with pytest.raises(ProgramError):
        raise ProgramError("test error")


def test_program_not_found_inherits_from_program_error():
    """ProgramNotFound should inherit from ProgramError."""
    with pytest.raises(ProgramError):
        raise ProgramNotFound("git not found")


def test_program_load_error_inherits_from_program_error():
    """ProgramLoadError should inherit from ProgramError."""
    with pytest.raises(ProgramError):
        raise ProgramLoadError("failed to load git")


def test_circular_extend_error_inherits_from_program_load_error():
    """CircularExtendError should inherit from ProgramLoadError."""
    with pytest.raises(ProgramLoadError):
        raise CircularExtendError("circular extend detected")


def test_config_validation_error_inherits_from_program_error():
    """ConfigValidationError should inherit from ProgramError."""
    with pytest.raises(ProgramError):
        raise ConfigValidationError("validation failed")


def test_schema_error_inherits_from_program_error():
    """SchemaError should inherit from ProgramError."""
    with pytest.raises(ProgramError):
        raise SchemaError("schema malformed")


# ===== Test Program Class =====


def test_program_init_minimal():
    """Program should initialize with name and lua_def."""
    lua_def = {
        "name": "git",
        "schema": {"user_name": {"type": "string"}},
        "default_config": {"user_name": "User"},
        "generate_config": lambda self, options: "git config --global user.name '%s'" % options.get("user_name", "User"),
    }
    prog = Program("git", lua_def)
    
    assert prog.name == "git"
    assert prog.lua_def == lua_def
    assert prog.parent is None


def test_program_init_with_parent():
    """Program should accept parent reference."""
    parent_def = {
        "name": "base",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    parent = Program("base", parent_def)
    
    child_def = {
        "name": "derived",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    child = Program("derived", child_def, parent=parent)
    
    assert child.parent is parent
    assert child.parent.name == "base"


def test_program_init_missing_name():
    """Program should raise error if 'name' field missing."""
    lua_def = {
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    with pytest.raises(ProgramLoadError, match="missing required fields"):
        Program("git", lua_def)


def test_program_init_missing_schema():
    """Program should raise error if 'schema' field missing."""
    lua_def = {
        "name": "git",
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    with pytest.raises(ProgramLoadError, match="missing required fields"):
        Program("git", lua_def)


def test_program_init_missing_default_config():
    """Program should raise error if 'default_config' field missing."""
    lua_def = {
        "name": "git",
        "schema": {},
        "generate_config": lambda self, options: "",
    }
    with pytest.raises(ProgramLoadError, match="missing required fields"):
        Program("git", lua_def)


def test_program_init_missing_generate_config():
    """Program should raise error if 'generate_config' field missing."""
    lua_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
    }
    with pytest.raises(ProgramLoadError, match="missing required fields"):
        Program("git", lua_def)


def test_program_get_schema_no_parent():
    """Program.get_schema() should return schema as-is when no parent."""
    schema = {
        "user_name": {"type": "string", "required": True},
        "email": {"type": "string", "required": True},
    }
    lua_def = {
        "name": "git",
        "schema": schema,
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    assert prog.get_schema() == schema


def test_program_get_schema_with_parent():
    """Program.get_schema() should merge schemas when parent exists."""
    parent_schema = {
        "user_name": {"type": "string"},
        "email": {"type": "string"},
    }
    parent_def = {
        "name": "base_git",
        "schema": parent_schema,
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    parent = Program("base_git", parent_def)
    
    child_schema = {
        "sign_commits": {"type": "boolean"},
    }
    child_def = {
        "name": "git",
        "schema": child_schema,
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    child = Program("git", child_def, parent=parent)
    
    merged = child.get_schema()
    
    # Should use allOf composition
    assert "allOf" in merged
    assert len(merged["allOf"]) == 2
    assert merged["allOf"][0] == parent_schema
    assert merged["allOf"][1] == child_schema


def test_program_generate_config_simple():
    """Program.generate_config() should call Lua function and return result."""
    lua_def = {
        "name": "git",
        "schema": {"user_name": {"type": "string"}},
        "default_config": {},
        "generate_config": lambda self, options: "git config --global user.name '%s'" % options.get("user_name", "User"),
    }
    prog = Program("git", lua_def)
    
    result = prog.generate_config({"user_name": "Alice"})
    
    assert result == "git config --global user.name 'Alice'"


def test_program_generate_config_returns_empty_string_on_none():
    """Program.generate_config() should return empty string if Lua returns None."""
    lua_def = {
        "name": "test",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: None,
    }
    prog = Program("test", lua_def)
    
    result = prog.generate_config({})
    
    assert result == ""


def test_program_generate_config_error():
    """Program.generate_config() should raise ProgramLoadError on Lua error."""
    lua_def = {
        "name": "test",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: 1 / 0,  # Will raise ZeroDivisionError
    }
    prog = Program("test", lua_def)
    
    with pytest.raises(ProgramLoadError):
        prog.generate_config({})


def test_program_validate_config_no_hook():
    """Program.validate_config() should pass without error if no validate hook."""
    lua_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    # Should not raise
    prog.validate_config({"user_name": "Alice"})


def test_program_validate_config_with_hook():
    """Program.validate_config() should call Lua validate hook if present."""
    def validate_func(self, options):
        if not options.get("user_name"):
            raise ValueError("user_name required")
    
    lua_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "validate": validate_func,
    }
    prog = Program("git", lua_def)
    
    # Should pass with valid options
    prog.validate_config({"user_name": "Alice"})
    
    # Should raise with invalid options
    with pytest.raises(ConfigValidationError):
        prog.validate_config({})


def test_program_run_hook_validate():
    """Program.run_hook("validate") should call validate function."""
    def validate_func(self, options):
        if not options.get("email"):
            raise ValueError("email required")
    
    lua_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "validate": validate_func,
    }
    prog = Program("git", lua_def)
    
    # Should work with valid options
    prog.run_hook("validate", {"email": "alice@example.com"})
    
    # Should raise with invalid options
    with pytest.raises(ProgramLoadError):
        prog.run_hook("validate", {})


def test_program_run_hook_post_install():
    """Program.run_hook("post_install") should call post_install function."""
    called = []
    
    def post_install_func(self, options, mount_point):
        called.append((options, mount_point))
    
    lua_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "post_install": post_install_func,
    }
    prog = Program("git", lua_def)
    
    prog.run_hook("post_install", {"user_name": "Alice"}, "/mnt/home")
    
    assert called == [({"user_name": "Alice"}, "/mnt/home")]


def test_program_run_hook_missing():
    """Program.run_hook() should return None if hook not present."""
    lua_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    result = prog.run_hook("pre_uninstall", "/mnt/home")
    
    assert result is None


def test_program_run_hook_unknown():
    """Program.run_hook() should return None for unknown hook names."""
    lua_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    result = prog.run_hook("unknown_hook")
    
    assert result is None


def test_program_parent_method():
    """Program._parent_method() should call parent's method."""
    parent_def = {
        "name": "base_git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "git config --global user.name 'Base'",
    }
    parent = Program("base_git", parent_def)
    
    child_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    child = Program("git", child_def, parent=parent)
    
    # Child can call parent's generate_config
    result = child._parent_method("generate_config", {})
    
    assert result == "git config --global user.name 'Base'"


def test_program_parent_method_without_parent():
    """Program._parent_method() should raise error if no parent."""
    lua_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    with pytest.raises(ProgramLoadError, match="no parent"):
        prog._parent_method("generate_config", {})


def test_program_get_parent():
    """Program._get_parent() should return parent reference."""
    parent_def = {
        "name": "base",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    parent = Program("base", parent_def)
    
    child_def = {
        "name": "derived",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    child = Program("derived", child_def, parent=parent)
    
    assert child._get_parent() is parent


def test_program_get_parent_none():
    """Program._get_parent() should return None if no parent."""
    lua_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    assert prog._get_parent() is None


def test_program_get_merged_schema():
    """Program._get_merged_schema() should return schema with inheritance."""
    parent_schema = {"user_name": {"type": "string"}}
    parent_def = {
        "name": "base",
        "schema": parent_schema,
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    parent = Program("base", parent_def)
    
    child_schema = {"email": {"type": "string"}}
    child_def = {
        "name": "git",
        "schema": child_schema,
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    child = Program("git", child_def, parent=parent)
    
    merged = child._get_merged_schema()
    
    assert "allOf" in merged
    assert merged["allOf"][0] == parent_schema
    assert merged["allOf"][1] == child_schema


# ===== Test ProgramRegistry Class =====


def test_registry_init():
    """ProgramRegistry should initialize with empty caches."""
    registry = ProgramRegistry()
    
    assert registry._builtin_cache == {}
    assert registry._user_cache == {}
    assert registry._merged_cache == {}


def test_registry_load_lua_def_simple():
    """Registry._load_lua_def() should load and parse Lua file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lua_file = Path(tmpdir) / "test.lua"
        lua_file.write_text("""
            return {
                name = "test",
                schema = {},
                default_config = {},
                generate_config = function(self, options) return "test" end
            }
        """)
        
        registry = ProgramRegistry()
        lua_def = registry._load_lua_def(lua_file)
        
        assert lua_def["name"] == "test"
        assert "schema" in lua_def
        assert "default_config" in lua_def
        assert "generate_config" in lua_def


def test_registry_load_lua_def_not_dict():
    """Registry._load_lua_def() should raise error if Lua doesn't return dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lua_file = Path(tmpdir) / "test.lua"
        lua_file.write_text("return 'string instead of dict'")
        
        registry = ProgramRegistry()
        
        with pytest.raises(ProgramLoadError, match="must return a dict"):
            registry._load_lua_def(lua_file)


def test_registry_load_lua_def_returns_none():
    """Registry._load_lua_def() should raise error if Lua returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lua_file = Path(tmpdir) / "test.lua"
        lua_file.write_text("-- No return statement")
        
        registry = ProgramRegistry()
        
        with pytest.raises(ProgramLoadError, match="must return a dict"):
            registry._load_lua_def(lua_file)


def test_registry_load_lua_def_syntax_error():
    """Registry._load_lua_def() should raise error on Lua syntax error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lua_file = Path(tmpdir) / "test.lua"
        lua_file.write_text("this is not valid lua ::::")
        
        registry = ProgramRegistry()
        
        with pytest.raises(ProgramLoadError, match="Lua syntax error"):
            registry._load_lua_def(lua_file)


def test_registry_load_lua_def_file_not_found():
    """Registry._load_lua_def() should raise error if file doesn't exist."""
    registry = ProgramRegistry()
    
    with pytest.raises(ProgramLoadError, match="Failed to read"):
        registry._load_lua_def(Path("/nonexistent/file.lua"))


def test_registry_list_programs_empty():
    """Registry.list_programs() should return empty list when no programs loaded."""
    registry = ProgramRegistry()
    
    assert registry.list_programs() == []


def test_registry_get_program_not_found():
    """Registry.get_program() should raise ProgramNotFound if program not in caches."""
    registry = ProgramRegistry()
    
    with pytest.raises(ProgramNotFound):
        registry.get_program("nonexistent")


def test_registry_get_program_info_not_found():
    """Registry.get_program_info() should raise ProgramNotFound if program not found."""
    registry = ProgramRegistry()
    
    with pytest.raises(ProgramNotFound):
        registry.get_program_info("nonexistent")


# ===== Test Program Scope (Task 1) =====


def test_program_scope_user():
    """Program should accept and store scope='user'."""
    lua_def = {
        "name": "git",
        "scope": "user",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    assert prog.scope == "user"
    assert prog.get_scope() == "user"


def test_program_scope_system():
    """Program should accept and store scope='system'."""
    lua_def = {
        "name": "firewall",
        "scope": "system",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("firewall", lua_def)
    
    assert prog.scope == "system"
    assert prog.get_scope() == "system"


def test_program_scope_both():
    """Program should accept and store scope='both'."""
    lua_def = {
        "name": "syncthing",
        "scope": "both",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("syncthing", lua_def)
    
    assert prog.scope == "both"
    assert prog.get_scope() == "both"


def test_program_scope_default_user():
    """Program should default to scope='user' if not specified."""
    lua_def = {
        "name": "git",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    assert prog.scope == "user"
    assert prog.get_scope() == "user"


def test_program_scope_invalid():
    """Program should raise SchemaError for invalid scope value."""
    lua_def = {
        "name": "test",
        "scope": "invalid",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    
    with pytest.raises(SchemaError, match="Invalid scope"):
        Program("test", lua_def)


def test_program_scope_invalid_empty_string():
    """Program should raise SchemaError for empty scope string."""
    lua_def = {
        "name": "test",
        "scope": "",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    
    with pytest.raises(SchemaError, match="Invalid scope"):
        Program("test", lua_def)


def test_program_scope_invalid_number():
    """Program should raise SchemaError for numeric scope value."""
    lua_def = {
        "name": "test",
        "scope": 123,
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    
    with pytest.raises(SchemaError):
        Program("test", lua_def)


def test_program_get_program_info_includes_scope():
    """ProgramRegistry.get_program_info() should include scope in returned dict."""
    lua_def = {
        "name": "git",
        "scope": "user",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    # Manually create registry and add program to cache for testing
    registry = ProgramRegistry()
    registry._user_cache["git"] = prog
    
    info = registry.get_program_info("git")
    
    assert "scope" in info
    assert info["scope"] == "user"


def test_program_get_program_info_scope_system():
    """get_program_info() should include scope='system' for system programs."""
    lua_def = {
        "name": "firewall",
        "scope": "system",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("firewall", lua_def)
    
    registry = ProgramRegistry()
    registry._builtin_cache["firewall"] = prog
    
    info = registry.get_program_info("firewall")
    
    assert info["scope"] == "system"


def test_program_get_program_info_scope_both():
    """get_program_info() should include scope='both' for bidirectional programs."""
    lua_def = {
        "name": "syncthing",
        "scope": "both",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("syncthing", lua_def)
    
    registry = ProgramRegistry()
    registry._user_cache["syncthing"] = prog
    
    info = registry.get_program_info("syncthing")
    
    assert info["scope"] == "both"
