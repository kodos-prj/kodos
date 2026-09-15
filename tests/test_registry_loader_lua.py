"""
Unit tests for registry/loader.lua

Tests file discovery, loading, parsing, and caching logic
All tests use Python's lupa library to run Lua code
"""

import pytest
import lupa
import tempfile
from pathlib import Path


class TestRegistryLoaderLua:
    """Test suite for registry/loader.lua"""
    
    @pytest.fixture
    def lua_runtime(self):
        """Create a fresh Lua runtime for each test"""
        return lupa.LuaRuntime()
    
    @pytest.fixture
    def loader(self, lua_runtime):
        """Load registry/loader.lua module"""
        code = Path('src/kod/lib/registry/loader.lua').read_text()
        return lua_runtime.execute(code)
    
    def test_loader_loads_successfully(self, loader):
        """Verify loader.lua can be loaded without errors"""
        assert loader is not None
        assert hasattr(loader, 'discover_builtin_files')
        assert hasattr(loader, 'discover_user_files')
        assert hasattr(loader, 'load_program_file')
    
    # ========================================================================
    # File Discovery Tests
    # Note: Directory scanning requires lfs library which may not be available
    # in sandboxed Lua. These tests verify the functions exist and handle
    # cases gracefully. Actual directory scanning is tested from Python layer.
    # ========================================================================
    
    def test_discover_builtin_files_callable(self, loader):
        """Test that discover_builtin_files function exists and is callable"""
        assert hasattr(loader, 'discover_builtin_files')
        assert callable(loader.discover_builtin_files)
    
    def test_discover_user_files_callable(self, loader):
        """Test that discover_user_files function exists and is callable"""
        assert hasattr(loader, 'discover_user_files')
        assert callable(loader.discover_user_files)
    
    # ========================================================================
    # Program File Loading Tests
    # ========================================================================
    
    def test_load_program_file_valid_simple(self, loader):
        """Test loading valid simple program definition"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prog_file = Path(tmpdir) / "git.lua"
            prog_file.write_text("""
return {
    scope = "user",
    schema = {type = "object"},
    default_config = {}
}
""")
            
            result, error = loader.load_program_file(str(prog_file))
            assert error is None
            assert result is not None
            assert result['scope'] == 'user'
            assert result['schema'] is not None
    
    def test_load_program_file_valid_complex(self, loader):
        """Test loading valid complex program definition"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prog_file = Path(tmpdir) / "openssh.lua"
            prog_file.write_text("""
return {
    scope = "system",
    schema = {
        type = "object",
        properties = {
            port = {type = "number", minimum = 1, maximum = 65535}
        }
    },
    default_config = {port = 22},
    service = {
        name = "sshd",
        enable = true
    }
}
""")
            
            result, error = loader.load_program_file(str(prog_file))
            assert error is None
            assert result['scope'] == 'system'
            assert result['service']['name'] == 'sshd'
            assert result['default_config']['port'] == 22
    
    def test_load_program_file_not_found(self, loader):
        """Test loading from non-existent file"""
        result, error = loader.load_program_file("/nonexistent/path/git.lua")
        assert result is None
        assert error is not None
        assert "not found" in error.lower()
    
    def test_load_program_file_invalid_lua_syntax(self, loader):
        """Test handling of Lua syntax errors"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prog_file = Path(tmpdir) / "bad.lua"
            prog_file.write_text("return {this is invalid lua syntax")
            
            result, error = loader.load_program_file(str(prog_file))
            assert result is None
            assert error is not None
            assert "syntax" in error.lower() or "error" in error.lower()
    
    def test_load_program_file_returns_nil(self, loader):
        """Test handling when .lua file returns nil"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prog_file = Path(tmpdir) / "nil.lua"
            prog_file.write_text("return nil")
            
            result, error = loader.load_program_file(str(prog_file))
            assert result is None
            assert error is not None
            assert "must return a table" in error.lower()
    
    def test_load_program_file_returns_string(self, loader):
        """Test handling when .lua file returns non-table"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prog_file = Path(tmpdir) / "string.lua"
            prog_file.write_text("return 'not a table'")
            
            result, error = loader.load_program_file(str(prog_file))
            assert result is None
            assert error is not None
            assert "must return a table" in error.lower()
    
    def test_load_program_file_returns_number(self, loader):
        """Test handling when .lua file returns number"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prog_file = Path(tmpdir) / "number.lua"
            prog_file.write_text("return 42")
            
            result, error = loader.load_program_file(str(prog_file))
            assert result is None
            assert error is not None
            assert "must return a table" in error.lower()
    
    def test_load_program_file_returns_empty_table(self, loader):
        """Test loading file that returns empty table (valid but unusual)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prog_file = Path(tmpdir) / "empty.lua"
            prog_file.write_text("return {}")
            
            result, error = loader.load_program_file(str(prog_file))
            assert error is None
            assert result is not None
            assert len(result) == 0
    
    # ========================================================================
    # Caching Tests
    # ========================================================================
    
    def test_cache_builtin_program(self, lua_runtime, loader):
        """Test caching builtin program"""
        program_def = lua_runtime.eval("{scope='user', schema={}}")
        loader.set_builtin_cache("git", program_def)
        
        cached = loader.get_builtin_cache("git")
        assert cached is not None
    
    def test_cache_user_program(self, lua_runtime, loader):
        """Test caching user program"""
        program_def = lua_runtime.eval("{scope='system', schema={}}")
        loader.set_user_cache("custom", program_def)
        
        cached = loader.get_user_cache("custom")
        assert cached is not None
    
    def test_cache_not_found(self, loader):
        """Test retrieving non-existent cache entry"""
        cached = loader.get_builtin_cache("nonexistent")
        assert cached is None
    
    def test_clear_cache(self, lua_runtime, loader):
        """Test clearing all caches"""
        loader.set_builtin_cache("git", lua_runtime.eval("{scope='user'}"))
        loader.set_user_cache("custom", lua_runtime.eval("{scope='system'}"))
        
        loader.clear_cache()
        
        assert loader.get_builtin_cache("git") is None
        assert loader.get_user_cache("custom") is None
    
    def test_get_cached_names_empty(self, loader):
        """Test getting cached names when cache is empty"""
        loader.clear_cache()
        names = loader.get_cached_names()
        assert len(names) == 0 or names == []
    
    def test_get_cached_names_builtin_only(self, lua_runtime, loader):
        """Test getting cached names with builtin programs"""
        loader.clear_cache()
        loader.set_builtin_cache("git", lua_runtime.eval("{scope='user'}"))
        loader.set_builtin_cache("neovim", lua_runtime.eval("{scope='user'}"))
        
        names_table = loader.get_cached_names()
        # Lua returns array-like table; convert values to list
        names = [v for k, v in names_table.items()]
        assert len(names) == 2
        assert "git" in names
        assert "neovim" in names
    
    def test_get_cached_names_user_only(self, lua_runtime, loader):
        """Test getting cached names with user programs"""
        loader.clear_cache()
        loader.set_user_cache("custom1", lua_runtime.eval("{scope='system'}"))
        loader.set_user_cache("custom2", lua_runtime.eval("{scope='system'}"))
        
        names_table = loader.get_cached_names()
        names = [v for k, v in names_table.items()]
        assert len(names) == 2
        assert "custom1" in names
        assert "custom2" in names
    
    def test_get_cached_names_mixed(self, lua_runtime, loader):
        """Test getting cached names with both builtin and user"""
        loader.clear_cache()
        loader.set_builtin_cache("git", lua_runtime.eval("{scope='user'}"))
        loader.set_user_cache("custom", lua_runtime.eval("{scope='system'}"))
        
        names_table = loader.get_cached_names()
        names = [v for k, v in names_table.items()]
        assert len(names) == 2
        assert "git" in names
        assert "custom" in names
    
    def test_get_cached_names_sorted(self, lua_runtime, loader):
        """Test that cached names are returned sorted"""
        loader.clear_cache()
        loader.set_builtin_cache("zebra", lua_runtime.eval("{scope='user'}"))
        loader.set_builtin_cache("apple", lua_runtime.eval("{scope='user'}"))
        loader.set_builtin_cache("mango", lua_runtime.eval("{scope='user'}"))
        
        names_table = loader.get_cached_names()
        names = [v for k, v in names_table.items()]
        assert names == sorted(names)
    
    # ========================================================================
    # Integration Tests
    # ========================================================================
    
    def test_load_and_cache_workflow(self, lua_runtime, loader):
        """Test typical workflow: load files then cache them"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test program files
            git_file = Path(tmpdir) / "git.lua"
            git_file.write_text("""
return {
    scope = "user",
    schema = {type = "object"}
}
""")
            
            # Load git
            result, error = loader.load_program_file(str(git_file))
            assert error is None
            assert result is not None
            assert result['scope'] == 'user'
            
            # Cache it
            loader.set_builtin_cache("git", result)
            
            # Retrieve from cache
            cached = loader.get_builtin_cache("git")
            assert cached is not None
            assert cached['scope'] == 'user'
