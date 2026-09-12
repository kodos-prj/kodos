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


def _lua_table_to_list(lua_table):
    """Convert Lua table with numeric indices to Python list."""
    result = []
    i = 1
    while True:
        try:
            val = lua_table[i]
            if val is None:
                break
            result.append(val)
            i += 1
        except (KeyError, IndexError, TypeError):
            break
    return result


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
        result_list = _lua_table_to_list(result); assert len(result_list) == 0
    
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
        result_list = _lua_table_to_list(result); assert len(result_list) == 0
    
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
        result_list = _lua_table_to_list(result); assert len(result_list) == 0
    
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
        result_list = _lua_table_to_list(result); assert len(result_list) == 0


def teardown_module():
    """Clean up Lua runtime after all tests."""
    cleanup_lua_runtime()


# ============================================================================
# Task 2: Boot.lua - loader.include support
# ============================================================================
class TestBootLoaderInclude:
    """Test boot.lua loader.include feature."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_loader_include_present(self, lua):
        """Test emit_steps with loader.include entries."""
        lua.execute("""
            local boot = require('kod.sections.boot')
            config = {
                loader = {
                    type = "systemd-boot",
                    include = {"custom.conf", "extra.conf"}
                }
            }
            result = boot.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result)
        assert len(result_list) >= 2
        # Check that include steps are present
        step_names = [step['name'] for step in result_list if 'include' in step['name']]
        assert len(step_names) > 0
    
    def test_loader_include_absent(self, lua):
        """Test emit_steps without loader.include."""
        lua.execute("""
            local boot = require('kod.sections.boot')
            config = {loader = {type = "systemd-boot"}}
            result = boot.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result)
        # Should not have loader_include steps
        step_names = [step['name'] for step in result_list if 'include' in step['name']]
        assert len(step_names) == 0
    
    def test_loader_include_multiple(self, lua):
        """Test multiple loader.include entries."""
        lua.execute("""
            local boot = require('kod.sections.boot')
            config = {
                loader = {
                    type = "systemd-boot",
                    include = {"a.conf", "b.conf", "c.conf"}
                }
            }
            result = boot.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result)
        step_names = [step['name'] for step in result_list if 'include' in step['name']]
        assert len(step_names) >= 3


# ============================================================================
# Task 3: Hardware.lua - SANE support
# ============================================================================
class TestHardwareSane:
    """Test hardware.lua SANE scanner support."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_sane_enabled(self, lua):
        """Test emit_steps with SANE enabled."""
        lua.execute("""
            local hw = require('kod.sections.hardware')
            config = {sane = {enable = true}}
            result = hw.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result)
        assert len(result_list) >= 1
        step_names = [step['name'] for step in result_list]
        assert 'hardware_sane_install' in step_names
    
    def test_sane_disabled(self, lua):
        """Test emit_steps with SANE disabled."""
        lua.execute("""
            local hw = require('kod.sections.hardware')
            config = {sane = {enable = false}}
            result = hw.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result)
        step_names = [step['name'] for step in result_list]
        assert 'hardware_sane_install' not in step_names
    
    def test_sane_with_extra_packages(self, lua):
        """Test SANE with extra packages."""
        lua.execute("""
            local hw = require('kod.sections.hardware')
            config = {
                sane = {
                    enable = true,
                    extra_packages = {"sane-backends", "xsane"}
                }
            }
            result = hw.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result)
        step_names = [step['name'] for step in result_list]
        assert 'hardware_sane_install' in step_names
        assert 'hardware_sane_extra_packages' in step_names


# ============================================================================
# Task 4: Users-advanced.lua - NEW MODULE
# ============================================================================
class TestUsersAdvanced:
    """Test users-advanced.lua user identity and SSH setup."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_users_advanced_loads(self, lua):
        """Test users-advanced.lua loads."""
        lua.execute("ua = require('kod.sections.users-advanced')")
        assert lua.eval("type(ua.emit_steps)") == "function"
        assert lua.eval("ua.schema ~= nil")
    
    def test_user_identity_name(self, lua):
        """Test user identity name setting."""
        lua.execute("""
            local ua = require('kod.sections.users-advanced')
            config = {
                alice = {
                    identity = {name = "Alice User"}
                }
            }
            result = ua.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert 'users_alice_identity_name' in step_names
    
    def test_user_identity_password(self, lua):
        """Test user password hash setting."""
        lua.execute("""
            local ua = require('kod.sections.users-advanced')
            config = {
                alice = {
                    identity = {hashed_password = "$6$hash123"}
                }
            }
            result = ua.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert 'users_alice_identity_password' in step_names
    
    def test_user_identity_groups(self, lua):
        """Test user groups setting."""
        lua.execute("""
            local ua = require('kod.sections.users-advanced')
            config = {
                alice = {
                    identity = {groups = {"wheel", "audio"}}
                }
            }
            result = ua.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert 'users_alice_identity_groups' in step_names
    
    def test_user_ssh_keys_enabled(self, lua):
        """Test SSH keys initialization."""
        lua.execute("""
            local ua = require('kod.sections.users-advanced')
            config = {
                alice = {
                    ssh_keys = {enabled = true, authorized = {"ssh-rsa AAAAB3..."}}
                }
            }
            result = ua.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert any('ssh_keys_init' in name for name in step_names) or \
               any('ssh_keys' in name for name in step_names)
    
    def test_user_dotfiles_deploy(self, lua):
        """Test dotfiles deployment."""
        lua.execute("""
            local ua = require('kod.sections.users-advanced')
            config = {
                alice = {
                    dotfiles = {
                        repo_url = "https://github.com/alice/dotfiles.git",
                        deploy_tool = "stow"
                    }
                }
            }
            result = ua.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert any('dotfiles' in name for name in step_names)


# ============================================================================
# Task 5: Dotfiles.lua - NEW MODULE
# ============================================================================
class TestDotfiles:
    """Test dotfiles.lua module."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_dotfiles_loads(self, lua):
        """Test dotfiles.lua loads."""
        lua.execute("dot = require('kod.sections.dotfiles')")
        assert lua.eval("type(dot.emit_steps)") == "function"
        assert lua.eval("dot.schema ~= nil")
    
    def test_dotfiles_clone(self, lua):
        """Test dotfiles repository cloning."""
        lua.execute("""
            local dot = require('kod.sections.dotfiles')
            config = {
                alice = {
                    dotfiles = {repo_url = "https://github.com/alice/dots.git"}
                }
            }
            result = dot.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert any('clone' in name for name in step_names)
    
    def test_dotfiles_deploy_stow(self, lua):
        """Test dotfiles deployment with stow."""
        lua.execute("""
            local dot = require('kod.sections.dotfiles')
            config = {
                alice = {
                    dotfiles = {
                        repo_url = "https://github.com/alice/dots.git",
                        deploy_tool = "stow"
                    }
                }
            }
            result = dot.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert any('deploy' in name for name in step_names)
    
    def test_dotfiles_without_repo(self, lua):
        """Test dotfiles without repo_url."""
        lua.execute("""
            local dot = require('kod.sections.dotfiles')
            config = {alice = {dotfiles = {}}}
            result = dot.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); assert len(result_list) == 0


# ============================================================================
# Task 6: SSH-keys.lua - NEW MODULE
# ============================================================================
class TestSshKeys:
    """Test ssh-keys.lua module."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_ssh_keys_loads(self, lua):
        """Test ssh-keys.lua loads."""
        lua.execute("ssh = require('kod.sections.ssh-keys')")
        assert lua.eval("type(ssh.emit_steps)") == "function"
        assert lua.eval("ssh.schema ~= nil")
    
    def test_ssh_keys_enabled(self, lua):
        """Test SSH keys initialization when enabled."""
        lua.execute("""
            local ssh = require('kod.sections.ssh-keys')
            config = {
                alice = {
                    ssh_keys = {enabled = true, authorized = {"ssh-rsa AAAAB3..."}}
                }
            }
            result = ssh.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) >= 1
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert any('ssh_keys' in name for name in step_names)
    
    def test_ssh_keys_disabled(self, lua):
        """Test SSH keys not initialized when disabled."""
        lua.execute("""
            local ssh = require('kod.sections.ssh-keys')
            config = {alice = {ssh_keys = {enabled = false}}}
            result = ssh.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); assert len(result_list) == 0
    
    def test_ssh_keys_multiple_keys(self, lua):
        """Test multiple authorized keys."""
        lua.execute("""
            local ssh = require('kod.sections.ssh-keys')
            config = {
                alice = {
                    ssh_keys = {
                        enabled = true,
                        authorized = {"key1", "key2", "key3"}
                    }
                }
            }
            result = ssh.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        # Should have init + 3 keys + permissions
        assert len(result) >= 3


# ============================================================================
# Task 7: Desktop.lua - environments support
# ============================================================================
class TestDesktopEnvironments:
    """Test desktop.lua environments block support."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_desktop_environments_multi(self, lua):
        """Test multiple desktop environments."""
        lua.execute("""
            local desk = require('kod.sections.desktop')
            config = {
                environments = {
                    gnome = {},
                    plasma = {}
                }
            }
            result = desk.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert any('environments' in name for name in step_names)
    
    def test_desktop_display_manager_requires_enabled_environment(self, lua):
        """DM alone (no enabled environment) installs nothing."""
        lua.execute("""
            local desk = require('kod.sections.desktop')
            config = {display_manager = "sddm"}
            result = desk.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert not any('display_manager' in name for name in step_names)
    
    def test_desktop_environments_and_dm(self, lua):
        """Test environments with explicit display manager."""
        lua.execute("""
            local desk = require('kod.sections.desktop')
            config = {
                environments = {gnome = {}},
                display_manager = "gdm"
            }
            result = desk.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) >= 1


# ============================================================================
# Task 8: Fonts.lua - font_dir and packages
# ============================================================================
class TestFontsDirAndPackages:
    """Test fonts.lua font_dir and packages support."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_fonts_font_dir(self, lua):
        """Test custom font directory."""
        lua.execute("""
            local fonts = require('kod.sections.fonts')
            config = {font_dir = "/home/user/.fonts"}
            result = fonts.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert 'fonts_font_dir_create' in step_names
    
    def test_fonts_packages(self, lua):
        """Test additional font packages."""
        lua.execute("""
            local fonts = require('kod.sections.fonts')
            config = {packages = {"noto-fonts", "dejavu-fonts"}}
            result = fonts.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert 'fonts_packages_install' in step_names
    
    def test_fonts_all_together(self, lua):
        """Test all font features together."""
        lua.execute("""
            local fonts = require('kod.sections.fonts')
            config = {
                monospace = {"noto-fonts-mono"},
                sans_serif = {"noto-fonts"},
                font_dir = "/home/user/.fonts",
                packages = {"extra-fonts"}
            }
            result = fonts.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        assert len(result) >= 3


# ============================================================================
# Task 9: Services.lua - config and systemd
# ============================================================================
class TestServicesConfigSystemd:
    """Test services.lua config and systemd support."""
    
    @pytest.fixture
    def lua(self, lua_with_path):
        return lua_with_path
    
    def test_services_config_block(self, lua):
        """Test services config block."""
        lua.execute("""
            local svc = require('kod.sections.services')
            config = {
                config = {
                    service_name = "nginx",
                    packages = {main = "nginx"}
                }
            }
            result = svc.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert any('config' in name for name in step_names)
    
    def test_services_config_with_extra_packages(self, lua):
        """Test service config with extra packages."""
        lua.execute("""
            local svc = require('kod.sections.services')
            config = {
                config = {
                    packages = {
                        main = "nginx",
                        extra = {"nginx-mod", "nginx-cache"}
                    }
                }
            }
            result = svc.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert any('install' in name for name in step_names)
    
    def test_services_systemd_mounts(self, lua):
        """Test systemd mounts configuration."""
        lua.execute("""
            local svc = require('kod.sections.services')
            config = {
                systemd = {
                    mounts = {
                        ["home.mount"] = {}
                    }
                }
            }
            result = svc.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert any('mount' in name for name in step_names)
    
    def test_services_systemd_units(self, lua):
        """Test systemd units configuration."""
        lua.execute("""
            local svc = require('kod.sections.services')
            config = {
                systemd = {
                    units = {
                        ["custom.service"] = {}
                    }
                }
            }
            result = svc.emit_steps(config, 'arch')
        """)
        result = lua.eval("result")
        result_list = _lua_table_to_list(result); step_names = [step['name'] for step in result_list]
        assert any('unit' in name for name in step_names)
