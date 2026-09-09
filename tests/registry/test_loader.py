"""Tests for kod.registry.loader (Task 2: PluginLoader).

Tests the core PluginLoader class, program discovery, loading, merging,
and error handling.
"""

import pytest
import tempfile
from pathlib import Path
from unittest import mock

from kod.registry.loader import PluginLoader
from kod.registry.programs import (
    Program,
    ProgramNotFound,
    ProgramLoadError,
    CircularExtendError,
)


# ===== Test PluginLoader.__init__ =====


def test_loader_init_default_config_home():
    """PluginLoader should set default config_home to ~/.kod."""
    loader = PluginLoader()
    
    assert loader.config_home == Path.home() / ".kod"
    assert loader.builtin_dir == Path(__file__).parent.parent.parent / "src" / "kod" / "registry" / "builtin"


def test_loader_init_custom_config_home():
    """PluginLoader should accept custom config_home."""
    custom_home = Path("/tmp/custom_kod")
    loader = PluginLoader(config_home=str(custom_home))
    
    assert loader.config_home == custom_home
    assert loader.plugin_dir == custom_home / "plugins" / "programs"


# ===== Test PluginLoader.discover_builtin =====


def test_loader_discover_builtin_empty():
    """discover_builtin() should return empty dict if builtin_dir doesn't exist."""
    loader = PluginLoader()
    
    # Temporarily mock builtin_dir to non-existent path
    loader.builtin_dir = Path("/nonexistent/builtin")
    result = loader.discover_builtin()
    
    assert result == {}


def test_loader_discover_builtin_finds_files():
    """discover_builtin() should find .lua files in builtin_dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir)
        
        # Create some .lua files
        (builtin_dir / "git.lua").write_text("return {name='git'}")
        (builtin_dir / "neovim.lua").write_text("return {name='neovim'}")
        (builtin_dir / "readme.txt").write_text("not a lua file")
        
        loader = PluginLoader()
        loader.builtin_dir = builtin_dir
        result = loader.discover_builtin()
        
        assert "git" in result
        assert "neovim" in result
        assert "readme" not in result
        assert result["git"] == builtin_dir / "git.lua"


# ===== Test PluginLoader.discover_user_plugins =====


def test_loader_discover_user_plugins_empty():
    """discover_user_plugins() should return empty dict if plugin_dir doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PluginLoader(config_home=tmpdir)
        result = loader.discover_user_plugins()
        
        assert result == {}


def test_loader_discover_user_plugins_finds_files():
    """discover_user_plugins() should find .lua files in plugin_dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # Create some .lua files
        (plugin_dir / "git.lua").write_text("return {name='git'}")
        (plugin_dir / "custom_tool.lua").write_text("return {name='custom_tool'}")
        
        loader = PluginLoader(config_home=tmpdir)
        result = loader.discover_user_plugins()
        
        assert "git" in result
        assert "custom_tool" in result
        assert result["git"] == plugin_dir / "git.lua"


# ===== Test PluginLoader.load_program =====


def test_loader_load_program_builtin_only():
    """load_program() should load builtin program if only builtin exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir) / "builtin"
        builtin_dir.mkdir()
        
        # Create builtin git program
        (builtin_dir / "git.lua").write_text("""
            return {
                name = "git",
                schema = {user_name = {type = "string"}},
                default_config = {user_name = "User"},
                generate_config = function(self, options) return "git config" end
            }
        """)
        
        loader = PluginLoader()
        loader.builtin_dir = builtin_dir
        
        program = loader.load_program("git")
        
        assert program.name == "git"
        assert program.parent is None
        assert "user_name" in program.lua_def.get("schema", {})


def test_loader_load_program_user_only():
    """load_program() should load user plugin if only user exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        # Create user plugin
        (plugin_dir / "my_tool.lua").write_text("""
            return {
                name = "my_tool",
                schema = {option = {type = "string"}},
                default_config = {option = "default"},
                generate_config = function(self, options) return "install" end
            }
        """)
        
        loader = PluginLoader(config_home=str(tmpdir))
        
        program = loader.load_program("my_tool")
        
        assert program.name == "my_tool"
        assert program.parent is None


def test_loader_load_program_not_found():
    """load_program() should raise ProgramNotFound if program doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PluginLoader(config_home=tmpdir)
        
        with pytest.raises(ProgramNotFound):
            loader.load_program("nonexistent")


def test_loader_load_program_syntax_error():
    """load_program() should raise ProgramLoadError on Lua syntax error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir) / "builtin"
        builtin_dir.mkdir()
        
        # Create invalid Lua file
        (builtin_dir / "bad.lua").write_text("this is not valid lua ::::")
        
        loader = PluginLoader()
        loader.builtin_dir = builtin_dir
        
        with pytest.raises(ProgramLoadError, match="Lua syntax error"):
            loader.load_program("bad")


def test_loader_load_program_missing_field():
    """load_program() should raise ProgramLoadError if required fields are missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir) / "builtin"
        builtin_dir.mkdir()
        
        # Create Lua file missing required fields
        (builtin_dir / "incomplete.lua").write_text("""
            return {
                name = "incomplete"
                -- missing schema, default_config, generate_config
            }
        """)
        
        loader = PluginLoader()
        loader.builtin_dir = builtin_dir
        
        with pytest.raises(ProgramLoadError, match="missing required fields"):
            loader.load_program("incomplete")


# ===== Test PluginLoader merging (user extends builtin) =====


def test_loader_load_program_user_extends_builtin():
    """load_program() should merge user program extending builtin."""
    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir) / "builtin"
        builtin_dir.mkdir()
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        # Create builtin git program
        (builtin_dir / "git.lua").write_text("""
            return {
                name = "git",
                schema = {user_name = {type = "string", required = true}},
                default_config = {user_name = "User"},
                generate_config = function(self, options) return "git config --global user.name '" .. options.user_name .. "'" end
            }
        """)
        
        # Create user extension
        (plugin_dir / "git.lua").write_text("""
            return {
                _extends = "git",
                schema = {signing_key = {type = "string", required = false}},
                default_config = {signing_key = nil},
                generate_config = function(self, options)
                    local base = self:_parent_method("generate_config", options)
                    if options.signing_key then
                        base = base .. "\\ngit config --global user.signingkey '" .. options.signing_key .. "'"
                    end
                    return base
                end
            }
        """)
        
        loader = PluginLoader(config_home=str(tmpdir))
        loader.builtin_dir = builtin_dir
        
        program = loader.load_program("git")
        
        assert program.name == "git"
        assert program.parent is not None
        assert program.parent.name == "git"
        
        # Check merged schema
        schema = program.get_schema()
        assert "allOf" in schema or "user_name" in schema


def test_loader_load_program_missing_parent():
    """load_program() should raise error if user extends non-existent parent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        # Create user plugin extending non-existent parent
        (plugin_dir / "custom.lua").write_text("""
            return {
                _extends = "nonexistent",
                schema = {},
                default_config = {},
                generate_config = function(self, options) return "" end
            }
        """)
        
        loader = PluginLoader(config_home=str(tmpdir))
        
        with pytest.raises(ProgramNotFound):
            loader.load_program("custom")


def test_loader_load_program_circular_extends():
    """load_program() should detect circular inheritance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir) / "builtin"
        builtin_dir.mkdir()
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        # Create circular reference: git builtin extends git user
        (builtin_dir / "git.lua").write_text("""
            return {
                name = "git",
                _extends = "git_user",
                schema = {},
                default_config = {},
                generate_config = function(self, options) return "" end
            }
        """)
        
        (plugin_dir / "git_user.lua").write_text("""
            return {
                name = "git_user",
                _extends = "git",
                schema = {},
                default_config = {},
                generate_config = function(self, options) return "" end
            }
        """)
        
        loader = PluginLoader(config_home=str(tmpdir))
        loader.builtin_dir = builtin_dir
        
        with pytest.raises(CircularExtendError):
            loader.load_program("git")


# ===== Test PluginLoader.list_programs =====


def test_loader_list_programs_empty():
    """list_programs() should return builtin programs with no user plugins."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PluginLoader(config_home=tmpdir)
        result = loader.list_programs()
        
        # Should include all builtin programs (no user plugins in tmpdir)
        # Builtins: git, neovim, syncthing, openssh, networkmanager, cups, bluetooth, fwupd
        assert set(result) == {"git", "neovim", "syncthing", "openssh", "networkmanager", "cups", "bluetooth", "fwupd"}


def test_loader_list_programs_mixed():
    """list_programs() should return sorted list of all programs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir) / "builtin"
        builtin_dir.mkdir()
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        # Create programs
        (builtin_dir / "neovim.lua").write_text("return {name='neovim', schema={}, default_config={}, generate_config=function(s,o)return''end}")
        (builtin_dir / "git.lua").write_text("return {name='git', schema={}, default_config={}, generate_config=function(s,o)return''end}")
        (plugin_dir / "custom.lua").write_text("return {name='custom', schema={}, default_config={}, generate_config=function(s,o)return''end}")
        
        loader = PluginLoader(config_home=str(tmpdir))
        loader.builtin_dir = builtin_dir
        result = loader.list_programs()
        
        assert result == ["custom", "git", "neovim"]


# ===== Test PluginLoader.get_program_info =====


def test_loader_get_program_info_builtin():
    """get_program_info() should return info for builtin program."""
    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir) / "builtin"
        builtin_dir.mkdir()
        
        (builtin_dir / "git.lua").write_text("""
            return {
                name = "git",
                schema = {user_name = {type = "string"}},
                default_config = {user_name = "User"},
                generate_config = function(self, options) return "" end
            }
        """)
        
        loader = PluginLoader()
        loader.builtin_dir = builtin_dir
        
        info = loader.get_program_info("git")
        
        assert info["name"] == "git"
        assert info["source"] == "builtin"
        assert info["extends"] is None
        assert "user_name" in info["schema"]


def test_loader_get_program_info_merged():
    """get_program_info() should return info for merged program."""
    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir) / "builtin"
        builtin_dir.mkdir()
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        (builtin_dir / "git.lua").write_text("""
            return {
                name = "git",
                schema = {user_name = {type = "string"}},
                default_config = {user_name = "User"},
                generate_config = function(self, options) return "" end
            }
        """)
        
        (plugin_dir / "git.lua").write_text("""
            return {
                _extends = "git",
                schema = {signing_key = {type = "string"}},
                default_config = {},
                generate_config = function(self, options) return "" end
            }
        """)
        
        loader = PluginLoader(config_home=str(tmpdir))
        loader.builtin_dir = builtin_dir
        
        info = loader.get_program_info("git")
        
        assert info["name"] == "git"
        assert info["source"] == "merged"
        assert info["extends"] == "git"


def test_loader_get_program_info_not_found():
    """get_program_info() should raise ProgramNotFound for missing program."""
    loader = PluginLoader()
    
    with pytest.raises(ProgramNotFound):
        loader.get_program_info("nonexistent")


# ===== Test Caching =====


def test_loader_caching_builtin():
    """load_program() should cache builtin programs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        builtin_dir = Path(tmpdir) / "builtin"
        builtin_dir.mkdir()
        
        (builtin_dir / "git.lua").write_text("""
            return {
                name = "git",
                schema = {},
                default_config = {},
                generate_config = function(self, options) return "" end
            }
        """)
        
        loader = PluginLoader()
        loader.builtin_dir = builtin_dir
        
        # Load twice
        prog1 = loader.load_program("git")
        prog2 = loader.load_program("git")
        
        # Should be the same object (cached)
        assert prog1 is prog2


def test_loader_caching_user():
    """load_program() should cache user programs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir) / "plugins" / "programs"
        plugin_dir.mkdir(parents=True)
        
        (plugin_dir / "custom.lua").write_text("""
            return {
                name = "custom",
                schema = {},
                default_config = {},
                generate_config = function(self, options) return "" end
            }
        """)
        
        loader = PluginLoader(config_home=str(tmpdir))
        
        # Load twice
        prog1 = loader.load_program("custom")
        prog2 = loader.load_program("custom")
        
        # Should be the same object (cached)
        assert prog1 is prog2
