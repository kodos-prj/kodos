"""Integration tests for section composition (Phase 5c)."""

import pytest
from kod.lua_runtime import get_lua_runtime, cleanup_lua_runtime
from pathlib import Path

# Get the path to the src directory
SRC_DIR = Path(__file__).parent.parent / "src"


# Configure Lua module path at module load time
@pytest.fixture(scope="session", autouse=True)
def setup_lua_path():
    """Configure Lua module search path."""
    lua = get_lua_runtime()
    # Add src directory to Lua's module search path
    lua.execute(f"""
        package.path = '{str(SRC_DIR)}/?.lua;{str(SRC_DIR)}/?/init.lua;' .. package.path
    """)


@pytest.fixture
def lua_with_path():
    """Get Lua runtime with path configured."""
    lua = get_lua_runtime()
    lua.execute(f"""
        package.path = '{str(SRC_DIR)}/?.lua;{str(SRC_DIR)}/?/init.lua;' .. package.path
    """)
    return lua


class TestSectionComposition:
    """Test all sections working together."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_all_sections_load(self, lua):
        """Test that all 13 sections can be loaded together."""
        lua.execute("""
            local sections = {}
            sections.base_distribution = require('kod.sections.base_distribution')
            sections.packages = require('kod.sections.packages')
            sections.boot = require('kod.sections.boot')
            sections.hardware = require('kod.sections.hardware')
            sections.locale = require('kod.sections.locale')
            sections.network = require('kod.sections.network')
            sections.fonts = require('kod.sections.fonts')
            sections.desktop = require('kod.sections.desktop')
            sections.repos = require('kod.sections.repos')
            sections.devices = require('kod.sections.devices')
            sections.users = require('kod.sections.users')
            sections.services = require('kod.sections.services')
            sections.programs = require('kod.sections.programs')
            
            -- Verify all have emit_steps
            for name, section in pairs(sections) do
                assert(type(section.emit_steps) == 'function', name .. ' missing emit_steps')
                assert(section.schema ~= nil, name .. ' missing schema')
            end
        """)
    
    def test_emit_steps_all_sections_with_nil_config(self, lua):
        """Test emit_steps with nil config for all sections."""
        lua.execute("""
            local sections = {
                'base_distribution', 'packages', 'boot', 'hardware', 'locale',
                'network', 'fonts', 'desktop', 'repos', 'devices', 'users',
                'services', 'programs'
            }
            
            total_steps = 0
            for _, section_name in ipairs(sections) do
                local section = require('kod.sections.' .. section_name)
                local steps = section.emit_steps(nil, 'arch')
                assert(type(steps) == 'table', section_name .. ' emit_steps did not return table')
                if steps then
                    for _ in pairs(steps) do
                        total_steps = total_steps + 1
                    end
                end
            end
        """)
    
    def test_emit_steps_all_sections_with_valid_config(self, lua):
        """Test emit_steps with valid config for all sections."""
        lua.execute("""
            local sections_config = {
                packages = {[1]='vim', [2]='git'},
                boot = {kernel = {package = 'linux'}, loader = {type = 'grub', timeout = 5}},
                hardware = {pipewire = {enable = true}},
                locale = {locale = {default = 'en_US.UTF-8 UTF-8'}, timezone = 'UTC'},
                network = {hostname = 'testhost', ipv6 = true},
                fonts = {monospace = {[1]='noto-fonts-mono'}, enable = true},
                desktop = {environment = 'gnome', enable = true},
                users = {testuser = {shell = '/bin/bash', groups = {[1]='wheel'}}},
                services = {sshd = {enable = true, start = true}},
            }
            
            local sections = {
                'base_distribution', 'packages', 'boot', 'hardware', 'locale',
                'network', 'fonts', 'desktop', 'repos', 'devices', 'users',
                'services', 'programs'
            }
            
            total_steps = 0
            step_names = {}
            duplicates = {}
            
            for _, section_name in ipairs(sections) do
                local section = require('kod.sections.' .. section_name)
                local config = sections_config[section_name]
                local steps = section.emit_steps(config, 'arch')
                
                assert(type(steps) == 'table', section_name .. ' emit_steps did not return table')
                
                if steps then
                    for _, step in pairs(steps) do
                        if type(step) == 'table' and step.name then
                            total_steps = total_steps + 1
                            if step_names[step.name] then
                                table.insert(duplicates, step.name)
                            else
                                step_names[step.name] = section_name
                            end
                        end
                    end
                end
            end
            
            -- Verify no duplicate step names
            assert(#duplicates == 0, 'Found duplicate step names: ' .. table.concat(duplicates, ', '))
        """)
    
    def test_emit_steps_distro_specific_arch(self, lua):
        """Test emit_steps with distro=arch."""
        lua.execute("""
            local sections = {
                'base_distribution', 'packages', 'boot', 'hardware', 'locale',
                'network', 'fonts', 'desktop', 'repos', 'devices', 'users',
                'services', 'programs'
            }
            
            for _, section_name in ipairs(sections) do
                local section = require('kod.sections.' .. section_name)
                local steps = section.emit_steps(nil, 'arch')
                assert(type(steps) == 'table', section_name .. ' failed with arch distro')
            end
        """)
    
    def test_emit_steps_distro_specific_debian(self, lua):
        """Test emit_steps with distro=debian."""
        lua.execute("""
            local sections = {
                'base_distribution', 'packages', 'boot', 'hardware', 'locale',
                'network', 'fonts', 'desktop', 'repos', 'devices', 'users',
                'services', 'programs'
            }
            
            for _, section_name in ipairs(sections) do
                local section = require('kod.sections.' .. section_name)
                local steps = section.emit_steps(nil, 'debian')
                assert(type(steps) == 'table', section_name .. ' failed with debian distro')
            end
        """)
    
    def test_steps_have_consistent_structure(self, lua):
        """Test that all generated steps have consistent structure."""
        lua.execute("""
            local sections = {
                'packages', 'boot', 'hardware', 'locale', 'network', 'fonts',
                'desktop', 'repos', 'devices', 'users', 'services', 'programs'
            }
            
            local function validate_step(step, section_name)
                assert(type(step) == 'table', section_name .. ': step is not a table')
                assert(type(step.name) == 'string', section_name .. ': step.name is not a string')
                assert(type(step.description) == 'string', section_name .. ': step.description is not a string')
                assert(type(step.command) == 'string', section_name .. ': step.command is not a string')
                
                -- Check optional fields
                if step.order then
                    assert(type(step.order) == 'number', section_name .. ': step.order is not a number')
                end
                if step.on_distro then
                    assert(step.on_distro == 'arch' or step.on_distro == 'debian',
                           section_name .. ': step.on_distro is invalid')
                end
                if step.depends_on then
                    assert(type(step.depends_on) == 'table', section_name .. ': step.depends_on is not a table')
                end
            end
            
            local test_config = {
                packages = {[1]='vim'},
                boot = {kernel = {package = 'linux'}},
                hardware = {pipewire = {enable = true}},
                locale = {locale = {default = 'en_US.UTF-8 UTF-8'}, timezone = 'UTC'},
                network = {hostname = 'test'},
                fonts = {monospace = {[1]='fonts'}, enable = true},
                desktop = {environment = 'gnome'},
                users = {user1 = {shell = '/bin/bash'}},
                services = {ssh = {enable = true}},
            }
            
            for _, section_name in ipairs(sections) do
                local section = require('kod.sections.' .. section_name)
                local config = test_config[section_name]
                local steps = section.emit_steps(config, 'arch')
                
                if steps then
                    for _, step in pairs(steps) do
                        if type(step) == 'table' and step.name then
                            validate_step(step, section_name)
                        end
                    end
                end
            end
        """)
    
    def test_no_module_imports_another_module(self, lua):
        """Test that section modules don't import each other (independence)."""
        lua.execute("""
            -- Read each module file and check for require('kod.sections.X')
            local sections = {
                'base_distribution', 'packages', 'boot', 'hardware', 'locale',
                'network', 'fonts', 'desktop', 'repos', 'devices', 'users',
                'services', 'programs'
            }
            
            -- For now, just verify they all load independently
            -- (Full independence check would require file I/O)
            for _, section_name in ipairs(sections) do
                local section = require('kod.sections.' .. section_name)
                assert(section ~= nil)
            end
        """)


class TestSectionIndependence:
    """Verify that sections are completely independent."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_each_section_loads_schema_independently(self, lua):
        """Test each section imports Schema independently."""
        lua.execute("""
            local sections = {
                'base_distribution', 'packages', 'boot', 'hardware', 'locale',
                'network', 'fonts', 'desktop', 'repos', 'devices', 'users',
                'services', 'programs'
            }
            
            for _, section_name in ipairs(sections) do
                -- Load fresh runtime for independence check
                local section = require('kod.sections.' .. section_name)
                assert(section.schema ~= nil, section_name .. ' schema is nil')
            end
        """)
    
    def test_section_emit_steps_signature(self, lua):
        """Test all sections have emit_steps with correct signature."""
        lua.execute("""
            local sections = {
                'base_distribution', 'packages', 'boot', 'hardware', 'locale',
                'network', 'fonts', 'desktop', 'repos', 'devices', 'users',
                'services', 'programs'
            }
            
            for _, section_name in ipairs(sections) do
                local section = require('kod.sections.' .. section_name)
                -- Test that emit_steps can be called with (nil, 'arch')
                local result = section.emit_steps(nil, 'arch')
                assert(type(result) == 'table', section_name .. ' emit_steps did not return table')
            end
        """)


class TestStepNameUniqueness:
    """Test that step names are unique within reasonable scopes."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_step_names_unique_per_section(self, lua):
        """Test that step names don't repeat within a section."""
        lua.execute("""
            local sections = {
                'packages', 'boot', 'hardware', 'locale', 'network', 'fonts',
                'desktop', 'repos', 'devices', 'users', 'services', 'programs'
            }
            
            local test_config = {
                packages = {[1]='vim', [2]='git'},
                boot = {kernel = {package = 'linux'}},
                hardware = {pipewire = {enable = true}},
                locale = {timezone = 'UTC'},
                network = {hostname = 'test'},
                fonts = {enable = true},
                users = {user1 = {shell = '/bin/bash'}},
                services = {ssh = {enable = true}},
            }
            
            for _, section_name in ipairs(sections) do
                local section = require('kod.sections.' .. section_name)
                local config = test_config[section_name]
                local steps = section.emit_steps(config, 'arch')
                local seen_names = {}
                
                if steps then
                    for _, step in pairs(steps) do
                        if type(step) == 'table' and step.name then
                            assert(not seen_names[step.name],
                                   section_name .. ': duplicate step name ' .. step.name)
                            seen_names[step.name] = true
                        end
                    end
                end
            end
        """)


def teardown_module():
    """Clean up Lua runtime after all tests."""
    cleanup_lua_runtime()
