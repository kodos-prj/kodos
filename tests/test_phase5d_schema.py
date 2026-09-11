"""Test Phase 5d schema extensions (nested blocks and new fields)."""

import pytest
from kod.lua_runtime import get_lua_runtime


class TestPhase5dSchemaExtensions:
    """Test that Phase 5d schema extensions are properly defined."""

    def test_boot_loader_include_field_exists(self):
        """boot.loader.include field exists and is a list."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local field = Schema.boot.fields.loader.fields.include
        return field and field.type == 'list'
        """
        result = lua.execute(code)
        assert result is True

    def test_boot_loader_include_is_optional(self):
        """boot.loader.include is optional (not required)."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local field = Schema.boot.fields.loader.fields.include
        return field.required ~= true
        """
        result = lua.execute(code)
        assert result is True

    def test_hardware_sane_block_exists(self):
        """hardware.sane block exists and is a dict."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local block = Schema.hardware.fields.sane
        return block and block.type == 'dict'
        """
        result = lua.execute(code)
        assert result is True

    def test_hardware_sane_enable_field(self):
        """hardware.sane.enable field is boolean and optional."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local field = Schema.hardware.fields.sane.fields.enable
        return field.type == 'boolean' and field.required ~= true
        """
        result = lua.execute(code)
        assert result is True

    def test_hardware_sane_extra_packages_field(self):
        """hardware.sane.extra_packages field is list and optional."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local field = Schema.hardware.fields.sane.fields.extra_packages
        return field.type == 'list' and field.required ~= true
        """
        result = lua.execute(code)
        assert result is True

    def test_desktop_display_manager_field(self):
        """desktop.display_manager field exists and is optional string."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local field = Schema.desktop.fields.display_manager
        return field.type == 'string' and field.required ~= true
        """
        result = lua.execute(code)
        assert result is True

    def test_desktop_environments_block_exists(self):
        """desktop.environments block exists and is a dict."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local block = Schema.desktop.fields.environments
        return block and block.type == 'dict'
        """
        result = lua.execute(code)
        assert result is True

    def test_desktop_environments_has_all_des(self):
        """desktop.environments has all required DE types."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local envs = Schema.desktop.fields.environments.fields
        return (envs.gnome ~= nil) and (envs.plasma ~= nil) and (envs.cosmic ~= nil) and (envs.budgie ~= nil) and (envs.pantheon ~= nil)
        """
        result = lua.execute(code)
        assert result is True

    def test_fonts_font_dir_field(self):
        """fonts.font_dir field exists and is optional string."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local field = Schema.fonts.fields.font_dir
        return field.type == 'string' and field.required ~= true
        """
        result = lua.execute(code)
        assert result is True

    def test_fonts_packages_field(self):
        """fonts.packages field exists and is optional list."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local field = Schema.fonts.fields.packages
        return field.type == 'list' and field.required ~= true
        """
        result = lua.execute(code)
        assert result is True

    def test_services_systemd_block_exists(self):
        """services.systemd block exists and is a dict."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local block = Schema.services.fields.systemd
        return block and block.type == 'dict'
        """
        result = lua.execute(code)
        assert result is True

    def test_services_systemd_mounts_field(self):
        """services.systemd.mounts field exists and is optional dict."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local field = Schema.services.fields.systemd.fields.mounts
        return field.type == 'dict' and field.required ~= true
        """
        result = lua.execute(code)
        assert result is True

    def test_services_systemd_units_field(self):
        """services.systemd.units field exists and is optional dict."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local field = Schema.services.fields.systemd.fields.units
        return field.type == 'dict' and field.required ~= true
        """
        result = lua.execute(code)
        assert result is True


class TestBackwardCompatibility:
    """Test that Phase 5c schema still works (backward compatibility)."""

    def test_phase5c_boot_config_validates(self):
        """Phase 5c boot config (without include) validates."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local config = {
            kernel = {package = "linux"},
            loader = {type = "systemd-boot", timeout = 10}
        }
        local ok, err = Schema:validate_field(Schema.boot, config)
        return ok == true
        """
        result = lua.execute(code)
        assert result is True

    def test_phase5c_hardware_config_validates(self):
        """Phase 5c hardware config (without sane) validates."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local config = {
            pipewire = {enable = true}
        }
        local ok, err = Schema:validate_field(Schema.hardware, config)
        return ok == true
        """
        result = lua.execute(code)
        assert result is True

    def test_phase5c_desktop_config_validates(self):
        """Phase 5c desktop config (without display_manager) validates."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local config = {
            environment = "gnome",
            enable = true
        }
        local ok, err = Schema:validate_field(Schema.desktop, config)
        return ok == true
        """
        result = lua.execute(code)
        assert result is True

    def test_phase5c_fonts_config_validates(self):
        """Phase 5c fonts config (without font_dir/packages) validates."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local config = {
            monospace = {"noto-fonts-mono"},
            enable = true
        }
        local ok, err = Schema:validate_field(Schema.fonts, config)
        return ok == true
        """
        result = lua.execute(code)
        assert result is True

    def test_phase5c_services_config_validates(self):
        """Phase 5c services config (without systemd) validates."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local config = {}
        local ok, err = Schema:validate_field(Schema.services, config)
        return ok == true
        """
        result = lua.execute(code)
        assert result is True


class TestPhase5dValidation:
    """Test that Phase 5d configs with new fields validate correctly."""

    def test_phase5d_boot_config_with_include_validates(self):
        """Phase 5d boot config with include field validates."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local config = {
            kernel = {package = "linux"},
            loader = {
                type = "systemd-boot",
                timeout = 10,
                include = {"/boot/loader/entries/custom.conf"}
            }
        }
        local ok, err = Schema:validate_field(Schema.boot, config)
        return ok == true
        """
        result = lua.execute(code)
        assert result is True

    def test_phase5d_hardware_config_with_sane_validates(self):
        """Phase 5d hardware config with sane block validates."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local config = {
            pipewire = {enable = true},
            sane = {
                enable = true,
                extra_packages = {"sane", "sane-backends-genesys"}
            }
        }
        local ok, err = Schema:validate_field(Schema.hardware, config)
        return ok == true
        """
        result = lua.execute(code)
        assert result is True

    def test_phase5d_desktop_config_validates(self):
        """Phase 5d desktop config with display_manager and environments validates."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local config = {
            environment = "gnome",
            enable = true,
            display_manager = "gdm",
            environments = {
                gnome = {extensions_enabled = true},
                plasma = {theme = "breeze-dark"}
            }
        }
        local ok, err = Schema:validate_field(Schema.desktop, config)
        return ok == true
        """
        result = lua.execute(code)
        assert result is True

    def test_phase5d_fonts_config_validates(self):
        """Phase 5d fonts config with font_dir and packages validates."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local config = {
            monospace = {"noto-fonts-mono"},
            font_dir = "/home/user/.local/share/fonts",
            packages = {"noto-fonts-cjk"},
            enable = true
        }
        local ok, err = Schema:validate_field(Schema.fonts, config)
        return ok == true
        """
        result = lua.execute(code)
        assert result is True

    def test_phase5d_services_config_with_systemd_validates(self):
        """Phase 5d services config with systemd block validates."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        local config = {
            systemd = {
                mounts = {storage = {What = "/dev/sdb1"}},
                units = {custom = {Description = "Custom unit"}}
            }
        }
        local ok, err = Schema:validate_field(Schema.services, config)
        return ok == true
        """
        result = lua.execute(code)
        assert result is True


class TestDocumentationStrings:
    """Test that all new fields have documentation."""

    def test_all_phase5d_fields_have_descriptions(self):
        """All Phase 5d fields have description strings."""
        lua = get_lua_runtime()
        code = """
        local Schema = require('src.kod.lib.schema')
        
        local fields_to_check = {
            Schema.boot.fields.loader.fields.include,
            Schema.hardware.fields.sane,
            Schema.hardware.fields.sane.fields.enable,
            Schema.hardware.fields.sane.fields.extra_packages,
            Schema.desktop.fields.display_manager,
            Schema.desktop.fields.environments,
            Schema.fonts.fields.font_dir,
            Schema.fonts.fields.packages,
            Schema.services.fields.systemd,
            Schema.services.fields.systemd.fields.mounts,
            Schema.services.fields.systemd.fields.units,
        }
        
        for _, field in ipairs(fields_to_check) do
            if not field.description or field.description == "" then
                return false
            end
        end
        return true
        """
        result = lua.execute(code)
        assert result is True
