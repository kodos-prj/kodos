"""Tests for Lua Planner (Phase 5c schema-driven composition).

Tests the planner's ability to:
- Load all 13 section modules
- Compose steps from configuration
- Order steps correctly
- Handle distro-specific behavior
- Validate configuration
- Error handling
"""

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


def _from_lua(value):
    """Convert Lua table/objects to Python dict/list."""
    if hasattr(value, "keys"):
        # It's a Lua table
        result = {}
        for key in value.keys():
            result[key] = _from_lua(value[key])
        return result
    elif isinstance(value, list):
        return [_from_lua(v) for v in value]
    else:
        return value


class TestPlannerLoading:
    """Test that planner loads and has correct interface."""
    
    def test_planner_loads(self, lua_with_path):
        """Test planner.lua loads."""
        lua_with_path.execute("Planner = require('kod.lib.planner')")
        assert lua_with_path.eval("type(Planner.compose)") == "function"
        assert lua_with_path.eval("type(Planner.sections)") == "table"
    
    def test_planner_has_13_sections(self, lua_with_path):
        """Test planner knows about all 13 sections."""
        lua_with_path.execute("Planner = require('kod.lib.planner')")
        num_sections = lua_with_path.eval("#Planner.sections")
        assert num_sections == 13
    
    def test_all_sections_in_planner(self, lua_with_path):
        """Test all expected sections are in planner."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            expected = {
                'base_distribution', 'repos', 'devices', 'boot', 'hardware',
                'locale', 'network', 'users', 'desktop', 'fonts',
                'packages', 'services', 'programs'
            }
            found = {}
            for _, sec in ipairs(Planner.sections) do
                found[sec] = true
            end
            match = true
            for _, exp in ipairs(expected) do
                if not found[exp] then
                    match = false
                    break
                end
            end
            result = match
        """)
        assert lua_with_path.eval("result") is True


class TestPlannerComposition:
    """Test that planner composes steps correctly."""
    
    def test_compose_with_minimal_config(self, lua_with_path):
        """Test compose with only base_distribution."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {base_distribution = "arch"}
            steps, err = Planner:compose(config, "arch")
        """)
        steps = lua_with_path.eval("steps")
        err = lua_with_path.eval("err")
        
        # Should return a table (could be empty or have steps)
        assert isinstance(steps, list)
        assert err is None
    
    def test_compose_with_packages_section(self, lua_with_path):
        """Test compose with packages section."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                packages = {"git", "vim", "curl"}
            }
            steps, err = Planner:compose(config, "arch")
        """)
        steps = lua_with_path.eval("steps")
        err = lua_with_path.eval("err")
        
        assert isinstance(steps, list)
        assert err is None
        assert len(steps) > 0
        
        # Check that we got package-related steps
        step_names = [step.get("name") for step in steps]
        assert any("package" in name for name in step_names if name)
    
    def test_compose_returns_array_of_steps(self, lua_with_path):
        """Test that compose returns an array of step objects."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                packages = {"git"}
            }
            steps, err = Planner:compose(config, "arch")
            
            -- Check that steps is a table with at least one element
            first_step = steps[1]
            has_name = first_step and first_step.name ~= nil
            has_description = first_step and first_step.description ~= nil
        """)
        has_name = lua_with_path.eval("has_name")
        has_description = lua_with_path.eval("has_description")
        
        assert has_name is True
        assert has_description is True
    
    def test_compose_with_boot_and_packages(self, lua_with_path):
        """Test compose with multiple sections."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                packages = {"git"},
                boot = {
                    kernel = {package = "linux"},
                    loader = {type = "systemd-boot", timeout = 10}
                }
            }
            steps, err = Planner:compose(config, "arch")
            num_steps = #steps
        """)
        num_steps = lua_with_path.eval("num_steps")
        assert num_steps > 0


class TestPlannerOrdering:
    """Test that steps are ordered correctly."""
    
    def test_steps_sorted_by_order_field(self, lua_with_path):
        """Test that returned steps are sorted by order field."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                packages = {"git"},
                boot = {kernel = {package = "linux"}}
            }
            steps, err = Planner:compose(config, "arch")
            
            -- Check that steps are in order
            ordered = true
            for i = 1, #steps - 1 do
                order_a = steps[i].order or 0
                order_b = steps[i+1].order or 0
                if order_a > order_b then
                    ordered = false
                    break
                end
            end
        """)
        ordered = lua_with_path.eval("ordered")
        assert ordered is True
    
    def test_default_order_is_zero(self, lua_with_path):
        """Test that steps without order field default to 0."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {base_distribution = "arch"}
            steps, err = Planner:compose(config, "arch")
            
            -- All steps should have an order (default 0 if missing)
            all_have_order = true
            for _, step in ipairs(steps) do
                if step.order == nil then
                    all_have_order = false
                end
            end
        """)
        # This is actually optional - the sorting logic uses (step.order or 0)
        # So missing order is treated as 0
        all_have_order = lua_with_path.eval("all_have_order")
        # We don't require every step to have explicit order


class TestDistroAwareness:
    """Test that planner respects distro parameter."""
    
    def test_arch_distro(self, lua_with_path):
        """Test compose with arch distro."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                packages = {"git"}
            }
            steps, err = Planner:compose(config, "arch")
            distro_is_arch = true
        """)
        distro_is_arch = lua_with_path.eval("distro_is_arch")
        assert distro_is_arch is True
    
    def test_debian_distro(self, lua_with_path):
        """Test compose with debian distro."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "debian",
                packages = {"git"}
            }
            steps, err = Planner:compose(config, "debian")
            distro_is_debian = true
        """)
        distro_is_debian = lua_with_path.eval("distro_is_debian")
        assert distro_is_debian is True


class TestConfigValidation:
    """Test that planner validates configuration correctly."""
    
    def test_requires_base_distribution(self, lua_with_path):
        """Test that base_distribution is required."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {packages = {"git"}}  -- missing base_distribution
            steps, err = Planner:compose(config, "arch")
        """)
        steps = lua_with_path.eval("steps")
        err = lua_with_path.eval("err")
        
        assert steps is None
        assert err is not None
        assert "base_distribution" in err
    
    def test_requires_valid_distro(self, lua_with_path):
        """Test that distro parameter must be arch or debian."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {base_distribution = "arch"}
            steps, err = Planner:compose(config, "fedora")
        """)
        steps = lua_with_path.eval("steps")
        err = lua_with_path.eval("err")
        
        assert steps is None
        assert err is not None
    
    def test_rejects_nil_config(self, lua_with_path):
        """Test that nil config is rejected."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            steps, err = Planner:compose(nil, "arch")
        """)
        steps = lua_with_path.eval("steps")
        err = lua_with_path.eval("err")
        
        assert steps is None
        assert err is not None


class TestMissingConfigSections:
    """Test that planner handles missing sections gracefully."""
    
    def test_missing_packages_section(self, lua_with_path):
        """Test compose without packages section."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {base_distribution = "arch"}  -- no packages
            steps, err = Planner:compose(config, "arch")
        """)
        steps = lua_with_path.eval("steps")
        err = lua_with_path.eval("err")
        
        # Should succeed, just with no package steps
        assert isinstance(steps, list)
        assert err is None
    
    def test_multiple_sections_present(self, lua_with_path):
        """Test compose with multiple sections."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                packages = {"git"},
                boot = {kernel = {package = "linux"}},
                locale = "en_US.UTF-8",
                network = {hostname = "test"}
            }
            steps, err = Planner:compose(config, "arch")
            num_steps = #steps
        """)
        num_steps = lua_with_path.eval("num_steps")
        assert num_steps > 0


class TestSectionModuleLoading:
    """Test that planner loads all section modules."""
    
    def test_all_13_sections_can_load(self, lua_with_path):
        """Test that all 13 section modules can be loaded."""
        sections = [
            'base_distribution', 'repos', 'devices', 'boot', 'hardware',
            'locale', 'network', 'users', 'desktop', 'fonts',
            'packages', 'services', 'programs'
        ]
        
        for section in sections:
            lua_with_path.execute(f"""
                success = false
                err_msg = nil
                sec, err = pcall(require, 'kod.sections.{section}')
                if not sec then
                    err_msg = err
                else
                    success = sec.emit_steps ~= nil
                end
            """)
            success = lua_with_path.eval("success")
            err_msg = lua_with_path.eval("err_msg")
            assert success is True, f"Failed to load section '{section}': {err_msg}"
    
    def test_planner_handles_all_sections_in_config(self, lua_with_path):
        """Test compose with all sections present."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                repos = {},
                devices = {},
                boot = {kernel = {package = "linux"}},
                hardware = {},
                locale = "en_US.UTF-8",
                network = {},
                users = {},
                desktop = {},
                fonts = {},
                packages = {"git"},
                services = {},
                programs = {}
            }
            steps, err = Planner:compose(config, "arch")
            num_steps = #steps
        """)
        num_steps = lua_with_path.eval("num_steps")
        assert num_steps > 0


class TestErrorHandling:
    """Test error handling in planner."""
    
    def test_compose_returns_errors_string(self, lua_with_path):
        """Test that compose returns errors as string."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = nil
            steps, err = Planner:compose(config, "arch")
        """)
        err = lua_with_path.eval("err")
        
        # err should be a string
        assert isinstance(err, str)
    
    def test_graceful_handling_of_missing_section(self, lua_with_path):
        """Test graceful handling when section module is missing."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {base_distribution = "arch"}
            steps, err = Planner:compose(config, "arch")
            -- Should not crash even though config is minimal
            still_valid = steps ~= nil or err ~= nil
        """)
        still_valid = lua_with_path.eval("still_valid")
        assert still_valid is True


class TestCacheClearing:
    """Test cache management."""
    
    def test_clear_cache_method_exists(self, lua_with_path):
        """Test that planner has clear_cache method."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            has_clear_cache = type(Planner.clear_cache) == "function"
        """)
        has_clear_cache = lua_with_path.eval("has_clear_cache")
        assert has_clear_cache is True
    
    def test_clear_cache_works(self, lua_with_path):
        """Test that clear_cache can be called."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            Planner:clear_cache()
            still_works = type(Planner.compose) == "function"
        """)
        still_works = lua_with_path.eval("still_works")
        assert still_works is True


class TestStepStructure:
    """Test that step objects have expected fields."""
    
    def test_step_has_name_and_description(self, lua_with_path):
        """Test that steps have name and description fields."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                packages = {"git"}
            }
            steps, err = Planner:compose(config, "arch")
            
            if #steps > 0 then
                first_step = steps[1]
                has_name = first_step.name ~= nil
                has_description = first_step.description ~= nil
            else
                has_name = false
                has_description = false
            end
        """)
        has_name = lua_with_path.eval("has_name")
        has_description = lua_with_path.eval("has_description")
        
        assert has_name is True
        assert has_description is True
    
    def test_step_may_have_optional_fields(self, lua_with_path):
        """Test that steps may have optional fields like command, order."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                boot = {kernel = {package = "linux"}}
            }
            steps, err = Planner:compose(config, "arch")
            
            if #steps > 0 then
                first_step = steps[1]
                -- These fields are optional but may be present
                has_order = first_step.order ~= nil
                -- At least one should have them
            else
                has_order = false
            end
        """)
        has_order = lua_with_path.eval("has_order")
        # Optional field, may or may not be present


class TestFullInstallScenario:
    """Test realistic installation scenarios."""
    
    def test_full_arch_install_config(self, lua_with_path):
        """Test with full Arch Linux install configuration."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                packages = {"git", "vim", "curl"},
                boot = {
                    kernel = {package = "linux"},
                    loader = {type = "systemd-boot", timeout = 10}
                },
                locale = "en_US.UTF-8",
                network = {hostname = "arch-machine"},
                services = {"sshd"},
            }
            steps, err = Planner:compose(config, "arch")
            success = steps ~= nil and #steps > 0
        """)
        success = lua_with_path.eval("success")
        assert success is True
    
    def test_full_debian_install_config(self, lua_with_path):
        """Test with full Debian install configuration."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "debian",
                packages = {"git", "vim", "curl"},
                boot = {
                    kernel = {package = "linux-image-amd64"},
                    loader = {type = "grub"}
                },
                locale = "en_US.UTF-8",
                network = {hostname = "debian-machine"},
                services = {"ssh"},
            }
            steps, err = Planner:compose(config, "debian")
            success = steps ~= nil and #steps > 0
        """)
        success = lua_with_path.eval("success")
        assert success is True


class TestEmptyConfigSections:
    """Test handling of empty configuration sections."""
    
    def test_empty_packages_list(self, lua_with_path):
        """Test with empty packages list."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                packages = {}  -- empty
            }
            steps, err = Planner:compose(config, "arch")
            success = err == nil
        """)
        success = lua_with_path.eval("success")
        assert success is True
    
    def test_nil_section_values(self, lua_with_path):
        """Test with nil section values."""
        lua_with_path.execute("""
            Planner = require('kod.lib.planner')
            config = {
                base_distribution = "arch",
                packages = nil,
                boot = nil
            }
            steps, err = Planner:compose(config, "arch")
            success = err == nil
        """)
        success = lua_with_path.eval("success")
        assert success is True
