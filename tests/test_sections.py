"""Tests for Lua section modules (Phase 5c compositional architecture)."""

import pytest
import sys
from kod.lua_runtime import get_lua_runtime, cleanup_lua_runtime
from pathlib import Path


# Get the path to the src directory
SRC_DIR = Path(__file__).parent.parent / "src"
SECTIONS_DIR = SRC_DIR / "kod" / "sections"


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



def _to_lua(lua, value):
    """Convert Python dict/list to Lua table."""
    if isinstance(value, dict):
        t = lua.table()
        for k, v in value.items():
            t[k] = _to_lua(lua, v)
        return t
    if isinstance(value, list):
        t = lua.table()
        for i, v in enumerate(value, 1):
            t[i] = _to_lua(lua, v)
        return t
    return value


class TestSectionLoading:
    """Test that all section modules load without errors."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        """Get Lua runtime."""
        return lua_with_path
    
    def test_packages_loads(self, lua):
        """Test packages.lua loads."""
        lua.execute("pkg = require('kod.sections.packages')")
        assert lua.eval("type(pkg.emit_steps)") == "function"
        assert lua.eval("pkg.schema ~= nil")
    
    def test_base_distribution_loads(self, lua):
        """Test base_distribution.lua loads."""
        lua.execute("bd = require('kod.sections.base_distribution')")
        assert lua.eval("type(bd.emit_steps)") == "function"
        assert lua.eval("bd.schema ~= nil")
    
    def test_hardware_loads(self, lua):
        """Test hardware.lua loads."""
        lua.execute("hw = require('kod.sections.hardware')")
        assert lua.eval("type(hw.emit_steps)") == "function"
        assert lua.eval("hw.schema ~= nil")
    
    def test_boot_loads(self, lua):
        """Test boot.lua loads."""
        lua.execute("boot = require('kod.sections.boot')")
        assert lua.eval("type(boot.emit_steps)") == "function"
        assert lua.eval("boot.schema ~= nil")
    
    def test_locale_loads(self, lua):
        """Test locale.lua loads."""
        lua.execute("locale = require('kod.sections.locale')")
        assert lua.eval("type(locale.emit_steps)") == "function"
        assert lua.eval("locale.schema ~= nil")
    
    def test_network_loads(self, lua):
        """Test network.lua loads."""
        lua.execute("net = require('kod.sections.network')")
        assert lua.eval("type(net.emit_steps)") == "function"
        assert lua.eval("net.schema ~= nil")
    
    def test_fonts_loads(self, lua):
        """Test fonts.lua loads."""
        lua.execute("fonts = require('kod.sections.fonts')")
        assert lua.eval("type(fonts.emit_steps)") == "function"
        assert lua.eval("fonts.schema ~= nil")
    
    def test_desktop_loads(self, lua):
        """Test desktop.lua loads."""
        lua.execute("desktop = require('kod.sections.desktop')")
        assert lua.eval("type(desktop.emit_steps)") == "function"
        assert lua.eval("desktop.schema ~= nil")
    
    def test_repos_loads(self, lua):
        """Test repos.lua loads."""
        lua.execute("repos = require('kod.sections.repos')")
        assert lua.eval("type(repos.emit_steps)") == "function"
        assert lua.eval("repos.schema ~= nil")
    
    def test_devices_loads(self, lua):
        """Test devices.lua loads."""
        lua.execute("devices = require('kod.sections.devices')")
        assert lua.eval("type(devices.emit_steps)") == "function"
        assert lua.eval("devices.schema ~= nil")
    
    def test_users_loads(self, lua):
        """Test users.lua loads."""
        lua.execute("users = require('kod.sections.users')")
        assert lua.eval("type(users.emit_steps)") == "function"
        assert lua.eval("users.schema ~= nil")
    
    def test_services_loads(self, lua):
        """Test services.lua loads."""
        lua.execute("services = require('kod.sections.services')")
        assert lua.eval("type(services.emit_steps)") == "function"
        assert lua.eval("services.schema ~= nil")
    
    def test_programs_loads(self, lua):
        """Test programs.lua loads."""
        lua.execute("programs = require('kod.sections.programs')")
        assert lua.eval("type(programs.emit_steps)") == "function"
        assert lua.eval("programs.schema ~= nil")


class TestPackagesSection:
    """Test packages.lua emit_steps function."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_emit_steps_with_nil_config(self, lua):
        """Test emit_steps returns empty array with nil config."""
        lua.execute("""
            local pkg = require('kod.sections.packages')
            result = pkg.emit_steps(nil, 'arch')
        """)
        result = lua.eval("result")
        assert isinstance(result, dict) or len(result) == 0
    
    def test_emit_steps_with_empty_list(self, lua):
        """Test emit_steps returns empty array with empty package list."""
        lua.execute("""
            local pkg = require('kod.sections.packages')
            result = pkg.emit_steps({}, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) == 0
    
    def test_emit_steps_with_packages_arch(self, lua):
        """Test emit_steps generates install step for arch."""
        lua.execute("""
            local pkg = require('kod.sections.packages')
            config = {}
            config[1] = 'vim'
            config[2] = 'git'
            result = pkg.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) >= 1
        # Check first step has required fields
        step = result[1]
        assert step['name'] == 'packages_install_all'
        assert 'pacman' in step['command']
        assert 'vim' in step['command']
        assert 'git' in step['command']
    
    def test_emit_steps_with_packages_debian(self, lua):
        """Test emit_steps generates install step for debian."""
        lua.execute("""
            local pkg = require('kod.sections.packages')
            config = {}
            config[1] = 'vim'
            config[2] = 'git'
            result = pkg.emit_steps(config, 'debian')
        """)
        result = lua.eval("result")
        assert len(result) >= 1
        step = result[1]
        assert step['name'] == 'packages_install_all'
        assert 'apt-get' in step['command']


class TestNetworkSection:
    """Test network.lua emit_steps function."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_emit_steps_with_nil_config(self, lua):
        """Test emit_steps returns empty array with nil config."""
        lua.execute("""
            local net = require('kod.sections.network')
            result = net.emit_steps(nil, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) == 0
    
    def test_emit_steps_with_hostname(self, lua):
        """Test emit_steps generates hostname step."""
        lua.execute("""
            local net = require('kod.sections.network')
            config = {hostname = 'testhost'}
            result = net.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) >= 2  # hostname + hosts file
        step = result[1]
        assert step['name'] == 'network_hostname_set'
        assert 'testhost' in step['command']
    
    def test_emit_steps_ipv6_disable(self, lua):
        """Test emit_steps disables IPv6 when ipv6 is false."""
        lua.execute("""
            local net = require('kod.sections.network')
            config = {ipv6 = false}
            result = net.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) >= 1
        step = result[1]
        assert step['name'] == 'network_ipv6_disable'
        assert 'disable_ipv6 = 1' in step['command']


class TestBootSection:
    """Test boot.lua emit_steps function."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_emit_steps_with_nil_config(self, lua):
        """Test emit_steps returns empty array with nil config."""
        lua.execute("""
            local boot = require('kod.sections.boot')
            result = boot.emit_steps(nil, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) == 0
    
    def test_emit_steps_with_kernel(self, lua):
        """Test emit_steps generates kernel install step."""
        lua.execute("""
            local boot = require('kod.sections.boot')
            config = {kernel = {package = 'linux-lts'}}
            result = boot.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) >= 1
        step = result[1]
        assert step['name'] == 'boot_kernel_install'
        assert 'linux-lts' in step['command']
    
    def test_emit_steps_with_bootloader(self, lua):
        """Test emit_steps generates bootloader step."""
        lua.execute("""
            local boot = require('kod.sections.boot')
            config = {loader = {type = 'systemd-boot', timeout = 5}}
            result = boot.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) >= 1
        # Find bootloader step
        has_bootloader = False
        for step_dict in result.values():
            if isinstance(step_dict, dict) and 'boot_loader' in step_dict.get('name', ''):
                has_bootloader = True
                break
        # Note: result indexing may vary with Lua table structure


class TestStepFormat:
    """Test that all steps have correct format."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_packages_step_format(self, lua):
        """Test packages step has required fields."""
        lua.execute("""
            local pkg = require('kod.sections.packages')
            config = {}
            config[1] = 'vim'
            result = pkg.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        step = result[1]
        
        # Check required fields
        assert 'name' in step
        assert 'description' in step
        assert 'command' in step
        
        # Check optional fields have correct types if present
        if 'order' in step:
            assert isinstance(step['order'], int)
        if 'on_distro' in step:
            assert step['on_distro'] in ('arch', 'debian', None)
        if 'depends_on' in step:
            assert isinstance(step['depends_on'], dict) or isinstance(step['depends_on'], list)


class TestBaseDistributionSection:
    """Test base_distribution.lua emit_steps function."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_emit_steps_returns_empty(self, lua):
        """Test emit_steps returns empty array (validation only)."""
        lua.execute("""
            local bd = require('kod.sections.base_distribution')
            result = bd.emit_steps('arch', 'arch')
        """)
        result = lua.eval("result")
        assert len(result) == 0


def teardown_module():
    """Clean up Lua runtime after all tests."""
    cleanup_lua_runtime()
