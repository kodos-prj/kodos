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


# ===== Test Service Field =====


def test_program_service_extract_openssh():
    """Program should extract service field for openssh (scope=system)."""
    lua_def = {
        "name": "openssh",
        "scope": "system",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "service": {
            "enable": True,
            "service_name": "sshd",
            "socket_activation": False,
            "restart_policy": "always",
        }
    }
    prog = Program("openssh", lua_def)
    
    service = prog.get_service()
    
    assert service is not None
    assert service["service_name"] == "sshd"
    assert service["enable"] is True


def test_program_service_extract_syncthing():
    """Program should extract service field for syncthing (scope=both)."""
    lua_def = {
        "name": "syncthing",
        "scope": "both",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "service": {
            "enable": True,
            "service_name": "syncthing",
            "socket_activation": True,
            "user_service": True,
            "restart_policy": "always",
        }
    }
    prog = Program("syncthing", lua_def)
    
    service = prog.get_service()
    
    assert service is not None
    assert service["service_name"] == "syncthing"
    assert service["socket_activation"] is True
    assert service["user_service"] is True


def test_program_service_no_service_git():
    """Program without service field should return None from get_service()."""
    lua_def = {
        "name": "git",
        "scope": "user",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    service = prog.get_service()
    
    assert service is None


def test_program_service_no_service_neovim():
    """Program without service field should return None from get_service()."""
    lua_def = {
        "name": "neovim",
        "scope": "user",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("neovim", lua_def)
    
    service = prog.get_service()
    
    assert service is None


def test_program_service_user_scope_invalid():
    """Program with service + scope='user' should raise SchemaError."""
    lua_def = {
        "name": "git",
        "scope": "user",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "service": {
            "enable": True,
            "service_name": "git",
        }
    }
    
    with pytest.raises(SchemaError, match="Service not allowed with scope='user'"):
        Program("git", lua_def)


def test_program_service_missing_service_name():
    """Program with service missing service_name should raise SchemaError."""
    lua_def = {
        "name": "openssh",
        "scope": "system",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "service": {
            "enable": True,
            # Missing service_name
        }
    }
    
    with pytest.raises(SchemaError, match="service_name"):
        Program("openssh", lua_def)


def test_program_service_missing_enable():
    """Program with service missing enable should raise SchemaError."""
    lua_def = {
        "name": "openssh",
        "scope": "system",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "service": {
            "service_name": "sshd",
            # Missing enable
        }
    }
    
    with pytest.raises(SchemaError, match="enable"):
        Program("openssh", lua_def)


def test_program_service_empty_service_name():
    """Program with empty service_name should raise SchemaError."""
    lua_def = {
        "name": "openssh",
        "scope": "system",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "service": {
            "enable": True,
            "service_name": "",  # Empty string
        }
    }
    
    with pytest.raises(SchemaError, match="service_name"):
        Program("openssh", lua_def)


def test_program_service_defaults_filled_in():
    """Program service should have defaults filled in for optional fields."""
    lua_def = {
        "name": "openssh",
        "scope": "system",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "service": {
            "enable": True,
            "service_name": "sshd",
            # No optional fields - should get defaults
        }
    }
    prog = Program("openssh", lua_def)
    
    service = prog.get_service()
    
    assert service["socket_activation"] is False
    assert service["user_service"] is False
    assert service["restart_policy"] == "always"
    assert service["per_user"] is False
    assert service.get("after") is None or service.get("after") == []
    assert service.get("wanted_by") is None or service.get("wanted_by") == []


def test_program_service_get_program_info_includes_service():
    """Program.get_program_info() should include service field."""
    lua_def = {
        "name": "openssh",
        "scope": "system",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
        "service": {
            "enable": True,
            "service_name": "sshd",
        }
    }
    prog = Program("openssh", lua_def)
    
    registry = ProgramRegistry()
    registry._builtin_cache["openssh"] = prog
    
    info = registry.get_program_info("openssh")
    
    assert "service" in info
    assert info["service"] is not None
    assert info["service"]["service_name"] == "sshd"


def test_program_service_get_program_info_no_service():
    """Program.get_program_info() should include service=None when no service."""
    lua_def = {
        "name": "git",
        "scope": "user",
        "schema": {},
        "default_config": {},
        "generate_config": lambda self, options: "",
    }
    prog = Program("git", lua_def)
    
    registry = ProgramRegistry()
    registry._user_cache["git"] = prog
    
    info = registry.get_program_info("git")
    
    assert "service" in info
    assert info["service"] is None


# ===== Test Builtin Service Programs (Task 5) =====

# Import PluginLoader for loading builtin programs
from kod.registry.loader import PluginLoader


def test_builtin_openssh_loads():
    """openssh.lua should load without error."""
    loader = PluginLoader()
    prog = loader.load_program("openssh")
    
    assert prog is not None
    assert prog.name == "openssh"


def test_builtin_openssh_has_service():
    """openssh.lua should have service field."""
    loader = PluginLoader()
    prog = loader.load_program("openssh")
    
    service = prog.get_service()
    assert service is not None
    assert service["service_name"] == "sshd"
    assert service["enable"] is True


def test_builtin_openssh_scope_system():
    """openssh.lua should have scope='system'."""
    loader = PluginLoader()
    prog = loader.load_program("openssh")
    
    assert prog.scope == "system"


def test_builtin_syncthing_loads():
    """syncthing.lua should load without error."""
    loader = PluginLoader()
    prog = loader.load_program("syncthing")
    
    assert prog is not None
    assert prog.name == "syncthing"


def test_builtin_syncthing_has_service():
    """syncthing.lua should have service field."""
    loader = PluginLoader()
    prog = loader.load_program("syncthing")
    
    service = prog.get_service()
    assert service is not None
    assert service["service_name"] == "syncthing"
    assert service["socket_activation"] is True
    assert service["user_service"] is True


def test_builtin_syncthing_scope_both():
    """syncthing.lua should have scope='both'."""
    loader = PluginLoader()
    prog = loader.load_program("syncthing")
    
    assert prog.scope == "both"


def test_builtin_networkmanager_loads():
    """networkmanager.lua should load without error."""
    loader = PluginLoader()
    prog = loader.load_program("networkmanager")
    
    assert prog is not None
    assert prog.name == "networkmanager"


def test_builtin_networkmanager_has_service():
    """networkmanager.lua should have service field."""
    loader = PluginLoader()
    prog = loader.load_program("networkmanager")
    
    service = prog.get_service()
    assert service is not None
    assert service["service_name"] == "NetworkManager"
    assert service["enable"] is True


def test_builtin_networkmanager_scope_system():
    """networkmanager.lua should have scope='system'."""
    loader = PluginLoader()
    prog = loader.load_program("networkmanager")
    
    assert prog.scope == "system"


def test_builtin_cups_loads():
    """cups.lua should load without error."""
    loader = PluginLoader()
    prog = loader.load_program("cups")
    
    assert prog is not None
    assert prog.name == "cups"


def test_builtin_cups_has_service():
    """cups.lua should have service field."""
    loader = PluginLoader()
    prog = loader.load_program("cups")
    
    service = prog.get_service()
    assert service is not None
    assert service["service_name"] == "cupsd"
    assert service["enable"] is True


def test_builtin_cups_scope_system():
    """cups.lua should have scope='system'."""
    loader = PluginLoader()
    prog = loader.load_program("cups")
    
    assert prog.scope == "system"


def test_builtin_bluetooth_loads():
    """bluetooth.lua should load without error."""
    loader = PluginLoader()
    prog = loader.load_program("bluetooth")
    
    assert prog is not None
    assert prog.name == "bluetooth"


def test_builtin_bluetooth_has_service():
    """bluetooth.lua should have service field."""
    loader = PluginLoader()
    prog = loader.load_program("bluetooth")
    
    service = prog.get_service()
    assert service is not None
    assert service["service_name"] == "bluetooth"
    assert service["enable"] is True


def test_builtin_bluetooth_scope_system():
    """bluetooth.lua should have scope='system'."""
    loader = PluginLoader()
    prog = loader.load_program("bluetooth")
    
    assert prog.scope == "system"


def test_builtin_fwupd_loads():
    """fwupd.lua should load without error."""
    loader = PluginLoader()
    prog = loader.load_program("fwupd")
    
    assert prog is not None
    assert prog.name == "fwupd"


def test_builtin_fwupd_has_service():
    """fwupd.lua should have service field."""
    loader = PluginLoader()
    prog = loader.load_program("fwupd")
    
    service = prog.get_service()
    assert service is not None
    assert service["service_name"] == "fwupd"
    assert service["enable"] is True


def test_builtin_fwupd_scope_system():
    """fwupd.lua should have scope='system'."""
    loader = PluginLoader()
    prog = loader.load_program("fwupd")
    
    assert prog.scope == "system"
