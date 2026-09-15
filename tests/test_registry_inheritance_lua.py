"""
Unit tests for registry/inheritance.lua

Tests program inheritance, merging, circular detection, and validation
"""

import pytest
import lupa
import tempfile
from pathlib import Path


class TestRegistryInheritanceLua:
    """Test suite for registry/inheritance.lua"""
    
    @pytest.fixture
    def lua_runtime(self):
        """Create a fresh Lua runtime for each test"""
        return lupa.LuaRuntime()
    
    @pytest.fixture
    def inheritance_env(self, lua_runtime):
        """Set up Lua environment with loader and inheritance modules"""
        # Create mock directory structure
        self.tmpdir = tempfile.TemporaryDirectory()
        self.builtin_dir = Path(self.tmpdir.name) / "builtin"
        self.user_dir = Path(self.tmpdir.name) / "user"
        self.builtin_dir.mkdir()
        self.user_dir.mkdir()
        
        # Load loader.lua
        loader_code = Path('src/kod/lib/registry/loader.lua').read_text()
        loader = lua_runtime.execute(loader_code)
        
        # Set up Lua path to find modules (simplified mock)
        # For this test, we'll create a minimal mock of loader
        lua_runtime.execute("""
        -- Mock loader for inheritance tests
        local mock_loader = {
            _builtin_cache = {},
            _user_cache = {},
            
            get_builtin_cache = function(name)
                return mock_loader._builtin_cache[name]
            end,
            
            get_user_cache = function(name)
                return mock_loader._user_cache[name]
            end,
            
            set_builtin_cache = function(name, def)
                mock_loader._builtin_cache[name] = def
            end,
            
            set_user_cache = function(name, def)
                mock_loader._user_cache[name] = def
            end,
            
            load_program_file = function(path)
                local handle = io.open(path, 'r')
                if not handle then
                    return nil, "File not found: " .. path
                end
                handle:close()
                
                local ok, result = pcall(function() return dofile(path) end)
                if not ok then
                    return nil, "Lua error: " .. tostring(result)
                end
                if type(result) ~= "table" then
                    return nil, "Must return table"
                end
                return result, nil
            end
        }
        
        _G.mock_loader = mock_loader
        """)
        
        return {
            'lua': lua_runtime,
            'builtin_dir': self.builtin_dir,
            'user_dir': self.user_dir,
            'tmpdir': self.tmpdir,
        }
    
    def test_inheritance_loads_successfully(self, inheritance_env):
        """Verify inheritance.lua can be loaded (with mocked loader)"""
        lua = inheritance_env['lua']
        
        # Mock require function
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
            error("Unknown module: " .. path)
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        assert inheritance is not None
        assert hasattr(inheritance, 'resolve_program')
        assert hasattr(inheritance, '_merge_defs')
        assert hasattr(inheritance, 'validate_program_def')
    
    # ========================================================================
    # Program Merging Tests
    # ========================================================================
    
    def test_merge_simple_override(self, inheritance_env):
        """Test simple field override in merge"""
        lua = inheritance_env['lua']
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        parent = lua.eval("{scope='system', schema={}, name='git', version='1.0'}")
        child = lua.eval("{scope='user', name='git-custom'}")
        
        merged = inheritance._merge_defs(parent, child)
        
        # Child should override parent fields
        assert merged['scope'] == 'user'
        assert merged['name'] == 'git-custom'
        # Parent field not in child should be preserved
        assert merged['schema'] is not None
    
    def test_merge_skips_extends_marker(self, inheritance_env):
        """Test that _extends marker is removed during merge"""
        lua = inheritance_env['lua']
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        parent = lua.eval("{scope='system', schema={}}")
        child = lua.eval("{_extends='git', name='custom'}")
        
        merged = inheritance._merge_defs(parent, child)
        
        # _extends should not appear in merged result
        assert merged['_extends'] is None
        assert merged['name'] == 'custom'
    
    def test_merge_table_fields_deep_merge(self, inheritance_env):
        """Test deep merge of table fields (schema, default_config)"""
        lua = inheritance_env['lua']
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        parent = lua.eval("""{
            scope='system',
            schema={properties={port={type='number'}, hostname={type='string'}}},
            default_config={port=22, hostname='localhost'}
        }""")
        
        child = lua.eval("""{
            schema={properties={port={minimum=1024}}},
            default_config={port=2222}
        }""")
        
        merged = inheritance._merge_defs(parent, child)
        
        # Both schema properties should be present (deep merge)
        assert merged['schema']['properties']['port'] is not None
        assert merged['schema']['properties']['hostname'] is not None
        
        # Port should be overridden, hostname preserved
        assert merged['default_config']['port'] == 2222
        assert merged['default_config']['hostname'] == 'localhost'
    
    # ========================================================================
    # Program Validation Tests
    # ========================================================================
    
    def test_validate_valid_minimal_program(self, inheritance_env):
        """Test validation of minimal valid program"""
        lua = inheritance_env['lua']
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        program = lua.eval("{scope='user', schema={type='object'}}")
        
        ok, error = inheritance.validate_program_def(program)
        assert ok == True
        assert error is None
    
    def test_validate_missing_scope(self, inheritance_env):
        """Test validation fails without scope"""
        lua = inheritance_env['lua']
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        program = lua.eval("{schema={type='object'}}")
        
        ok, error = inheritance.validate_program_def(program)
        assert ok is None
        assert error is not None
        assert "scope" in error.lower()
    
    def test_validate_invalid_scope(self, inheritance_env):
        """Test validation fails with invalid scope value"""
        lua = inheritance_env['lua']
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        program = lua.eval("{scope='invalid', schema={type='object'}}")
        
        ok, error = inheritance.validate_program_def(program)
        assert ok is None
        assert error is not None
        assert "scope" in error.lower()
    
    def test_validate_missing_schema(self, inheritance_env):
        """Test validation fails without schema"""
        lua = inheritance_env['lua']
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        program = lua.eval("{scope='user'}")
        
        ok, error = inheritance.validate_program_def(program)
        assert ok is None
        assert error is not None
        assert "schema" in error.lower()
    
    def test_validate_service_with_user_scope_fails(self, inheritance_env):
        """Test validation fails for service with user scope"""
        lua = inheritance_env['lua']
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        program = lua.eval("""{
            scope='user',
            schema={type='object'},
            service={name='test'}
        }""")
        
        ok, error = inheritance.validate_program_def(program)
        assert ok is None
        assert error is not None
        assert "service" in error.lower() and "user" in error.lower()
    
    def test_validate_service_with_system_scope(self, inheritance_env):
        """Test validation passes for service with system scope"""
        lua = inheritance_env['lua']
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        program = lua.eval("""{
            scope='system',
            schema={type='object'},
            service={name='sshd'}
        }""")
        
        ok, error = inheritance.validate_program_def(program)
        assert ok == True
        assert error is None
    
    def test_validate_service_missing_name(self, inheritance_env):
        """Test validation fails for service without name"""
        lua = inheritance_env['lua']
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        program = lua.eval("""{
            scope='system',
            schema={type='object'},
            service={enable=true}
        }""")
        
        ok, error = inheritance.validate_program_def(program)
        assert ok is None
        assert error is not None
        assert "name" in error.lower()
    
    # ========================================================================
    # Integration Tests
    # ========================================================================
    
    def test_minimal_lua_integration(self, inheritance_env):
        """Test basic Lua module integration"""
        lua = inheritance_env['lua']
        
        # Both loader and inheritance should load without errors
        lua.execute("""
        _G.require = function(path)
            if path == "lib.registry.loader" then
                return _G.mock_loader
            end
        end
        """)
        
        inheritance_code = Path('src/kod/lib/registry/inheritance.lua').read_text()
        inheritance = lua.execute(inheritance_code)
        
        assert inheritance is not None
    
    def teardown_method(self, method):
        """Clean up temp directories after each test"""
        if hasattr(self, 'tmpdir') and self.tmpdir:
            self.tmpdir.cleanup()
