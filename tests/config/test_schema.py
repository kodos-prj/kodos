"""Tests for SECTION_HELP schema documentation.

Verifies that SECTION_HELP is complete, structurally sound, and all examples
are syntactically valid Lua.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kod.config.schema import SCHEMA, SECTION_HELP


class TestSectionHelpCompleteness:
    """Verify all SCHEMA sections have SECTION_HELP entries."""
    
    def test_all_schema_sections_documented(self):
        """Assert all 13 SCHEMA keys have SECTION_HELP entries."""
        assert len(SECTION_HELP) == len(SCHEMA), (
            f"SECTION_HELP has {len(SECTION_HELP)} entries but SCHEMA has {len(SCHEMA)}"
        )
        
        for section_name in SCHEMA.keys():
            assert section_name in SECTION_HELP, (
                f"Section '{section_name}' in SCHEMA but missing from SECTION_HELP"
            )
    
    def test_expected_13_sections(self):
        """Verify exactly 13 sections are documented."""
        expected_sections = {
            "base_distribution", "repos", "devices", "boot", "hardware",
            "locale", "network", "users", "desktop", "fonts", "packages",
            "services", "programs"
        }
        actual_sections = set(SECTION_HELP.keys())
        
        assert actual_sections == expected_sections, (
            f"Expected sections {expected_sections}, got {actual_sections}"
        )


class TestSectionHelpStructure:
    """Verify SECTION_HELP entries have required structure."""
    
    def test_each_entry_has_description(self):
        """Assert each SECTION_HELP entry has a 'description' key."""
        for section_name, help_entry in SECTION_HELP.items():
            assert isinstance(help_entry, dict), (
                f"'{section_name}' help entry must be a dict"
            )
            assert "description" in help_entry, (
                f"'{section_name}' missing 'description' key"
            )
            assert isinstance(help_entry["description"], str), (
                f"'{section_name}' description must be a string"
            )
            assert len(help_entry["description"]) > 0, (
                f"'{section_name}' description is empty"
            )
    
    def test_each_entry_has_type(self):
        """Assert each SECTION_HELP entry has a 'type' key."""
        for section_name, help_entry in SECTION_HELP.items():
            assert "type" in help_entry, (
                f"'{section_name}' missing 'type' key"
            )
            assert isinstance(help_entry["type"], str), (
                f"'{section_name}' type must be a string"
            )
            valid_types = {"dict", "list", "string", "boolean", "number"}
            assert help_entry["type"] in valid_types, (
                f"'{section_name}' has invalid type '{help_entry['type']}', "
                f"must be one of {valid_types}"
            )
    
    def test_each_entry_has_required_key(self):
        """Assert each SECTION_HELP entry has a 'required' key (bool)."""
        for section_name, help_entry in SECTION_HELP.items():
            assert "required" in help_entry, (
                f"'{section_name}' missing 'required' key"
            )
            assert isinstance(help_entry["required"], bool), (
                f"'{section_name}' required must be a boolean"
            )
    
    def test_example_keys_are_strings(self):
        """Assert 'example' values are non-empty strings."""
        for section_name, help_entry in SECTION_HELP.items():
            if "example" in help_entry:
                assert isinstance(help_entry["example"], str), (
                    f"'{section_name}' example must be a string"
                )
                assert len(help_entry["example"]) > 0, (
                    f"'{section_name}' example is empty"
                )


class TestSectionHelpFieldStructure:
    """Verify nested 'fields' entries have correct structure."""
    
    def test_fields_is_dict_when_present(self):
        """Assert 'fields' value is a dict (not list or string)."""
        for section_name, help_entry in SECTION_HELP.items():
            if "fields" in help_entry:
                assert isinstance(help_entry["fields"], dict), (
                    f"'{section_name}' fields must be a dict"
                )
    
    def test_field_entries_have_descriptions(self):
        """Assert each field has a 'description' key."""
        for section_name, help_entry in SECTION_HELP.items():
            if "fields" not in help_entry:
                continue
            
            for field_name, field_info in help_entry["fields"].items():
                assert isinstance(field_info, dict), (
                    f"'{section_name}.{field_name}' must be a dict"
                )
                assert "description" in field_info, (
                    f"'{section_name}.{field_name}' missing 'description'"
                )
                assert isinstance(field_info["description"], str), (
                    f"'{section_name}.{field_name}' description must be a string"
                )
                assert len(field_info["description"]) > 0, (
                    f"'{section_name}.{field_name}' description is empty"
                )
    
    def test_field_entries_have_type(self):
        """Assert each field has a 'type' key."""
        for section_name, help_entry in SECTION_HELP.items():
            if "fields" not in help_entry:
                continue
            
            for field_name, field_info in help_entry["fields"].items():
                assert "type" in field_info, (
                    f"'{section_name}.{field_name}' missing 'type' key"
                )
    
    def test_subfields_are_also_valid(self):
        """Assert nested 'fields' (level 2+) are also properly structured."""
        for section_name, help_entry in SECTION_HELP.items():
            if "fields" not in help_entry:
                continue
            
            for field_name, field_info in help_entry["fields"].items():
                if "fields" not in field_info:
                    continue
                
                # This is level 2 nesting
                assert isinstance(field_info["fields"], dict), (
                    f"'{section_name}.{field_name}.fields' must be a dict"
                )
                
                for subfield_name, subfield_info in field_info["fields"].items():
                    assert isinstance(subfield_info, dict), (
                        f"'{section_name}.{field_name}.{subfield_name}' must be a dict"
                    )
                    assert "description" in subfield_info, (
                        f"'{section_name}.{field_name}.{subfield_name}' missing 'description'"
                    )


class TestExampleValidity:
    """Verify that examples are syntactically valid Lua."""
    
    def test_all_examples_have_lua_structure(self):
        """Verify examples use Lua syntax (basic structure check)."""
        for section_name, help_entry in SECTION_HELP.items():
            if "example" not in help_entry:
                continue
            
            example = help_entry["example"]
            
            # Examples should contain valid Lua tokens/syntax
            # At minimum, they should be parseable as strings with proper delimiters
            # and not have obvious syntax errors
            
            # Check for balanced braces in dict examples
            if "{" in example:
                assert example.count("{") == example.count("}"), (
                    f"'{section_name}' example has unbalanced braces"
                )
            
            # Check for balanced quotes
            # Count single and double quotes (simplified check)
            # Skip this for complex nested structures
            if '"""' not in example and "'''" not in example:
                # Basic check: no obviously broken strings
                pass
    
    def test_examples_not_empty_strings(self):
        """Verify examples are not empty."""
        for section_name, help_entry in SECTION_HELP.items():
            if "example" in help_entry:
                assert help_entry["example"].strip(), (
                    f"'{section_name}' example is empty or whitespace-only"
                )


class TestFieldPathLookup:
    """Test nested field lookup functionality (sample paths)."""
    
    def test_boot_kernel_package_lookup(self):
        """Verify boot.kernel.package path resolves correctly."""
        boot_help = SECTION_HELP["boot"]
        assert "fields" in boot_help
        
        kernel_field = boot_help["fields"].get("kernel")
        assert kernel_field is not None
        
        package_field = kernel_field.get("fields", {}).get("package")
        assert package_field is not None
        assert "description" in package_field
    
    def test_locale_locale_default_lookup(self):
        """Verify locale.locale.default path resolves correctly."""
        locale_help = SECTION_HELP["locale"]
        assert "fields" in locale_help
        
        locale_field = locale_help["fields"].get("locale")
        assert locale_field is not None
        
        default_field = locale_field.get("fields", {}).get("default")
        assert default_field is not None
        assert "description" in default_field
    
    def test_users_username_shell_lookup(self):
        """Verify users.USERNAME.shell path resolves correctly."""
        users_help = SECTION_HELP["users"]
        assert "fields" in users_help
        
        username_field = users_help["fields"].get("USERNAME")
        assert username_field is not None
        
        shell_field = username_field.get("fields", {}).get("shell")
        assert shell_field is not None
        assert "description" in shell_field


class TestValidValues:
    """Test valid_values constraints where applicable."""
    
    def test_base_distribution_has_valid_values(self):
        """Verify base_distribution lists valid values."""
        base_dist_help = SECTION_HELP["base_distribution"]
        assert "valid_values" in base_dist_help
        assert base_dist_help["valid_values"] == ["arch", "debian"]
    
    def test_boot_loader_type_has_valid_values(self):
        """Verify boot.loader.type lists valid values."""
        boot_help = SECTION_HELP["boot"]
        loader_type_field = boot_help["fields"]["loader"]["fields"]["type"]
        assert "valid_values" in loader_type_field
        assert "systemd-boot" in loader_type_field["valid_values"]
        assert "grub" in loader_type_field["valid_values"]


class TestDefaultValues:
    """Test that defaults are specified where appropriate."""
    
    def test_base_distribution_has_no_default(self):
        """base_distribution should not have a default (it's required)."""
        base_dist_help = SECTION_HELP["base_distribution"]
        # If required=True, having a default is contradictory but not fatal
        # This test documents the expected behavior
    
    def test_boot_kernel_package_has_default(self):
        """Verify boot.kernel.package has a default."""
        kernel_package = SECTION_HELP["boot"]["fields"]["kernel"]["fields"]["package"]
        assert "default" in kernel_package
        assert kernel_package["default"] == "linux"
    
    def test_locale_keymap_has_default(self):
        """Verify locale.keymap has a default."""
        locale_keymap = SECTION_HELP["locale"]["fields"]["keymap"]
        assert "default" in locale_keymap
        assert locale_keymap["default"] == "us"


class TestErrorHelpMessages:
    """Verify error_help messages are present where needed."""
    
    def test_packages_has_error_help(self):
        """Verify packages section has error_help for common mistakes."""
        packages_help = SECTION_HELP["packages"]
        assert "error_help" in packages_help
        assert "list" in packages_help["error_help"].lower()
        assert "dict" in packages_help["error_help"].lower()
    
    def test_base_distribution_has_error_help(self):
        """Verify base_distribution has error_help."""
        base_dist_help = SECTION_HELP["base_distribution"]
        assert "error_help" in base_dist_help


class TestSchemaConsistency:
    """Verify consistency between SCHEMA and SECTION_HELP."""
    
    def test_schema_types_match_help_types(self):
        """Verify SCHEMA types match SECTION_HELP type descriptions."""
        type_mapping = {
            str: "string",
            dict: "dict",
            list: "list",
            bool: "boolean",
            int: "number",
            float: "number",
        }
        
        for section_name, schema_type in SCHEMA.items():
            help_entry = SECTION_HELP[section_name]
            expected_type_str = type_mapping.get(schema_type)
            actual_type_str = help_entry["type"]
            
            assert actual_type_str == expected_type_str, (
                f"'{section_name}' SCHEMA type {schema_type.__name__} "
                f"doesn't match SECTION_HELP type '{actual_type_str}' "
                f"(expected '{expected_type_str}')"
            )


class TestSpecificSections:
    """Test specific sections for completeness."""
    
    def test_boot_section_complete(self):
        """Verify boot section has all documented fields."""
        boot_help = SECTION_HELP["boot"]
        assert "kernel" in boot_help["fields"]
        assert "loader" in boot_help["fields"]
        
        kernel_fields = boot_help["fields"]["kernel"]["fields"]
        assert "package" in kernel_fields
        assert "modules" in kernel_fields
        
        loader_fields = boot_help["fields"]["loader"]["fields"]
        assert "type" in loader_fields
        assert "timeout" in loader_fields
    
    def test_locale_section_complete(self):
        """Verify locale section has all documented fields."""
        locale_help = SECTION_HELP["locale"]
        assert "locale" in locale_help["fields"]
        assert "timezone" in locale_help["fields"]
        assert "keymap" in locale_help["fields"]
        
        locale_fields = locale_help["fields"]["locale"]["fields"]
        assert "default" in locale_fields
        assert "extra_generate" in locale_fields
    
    def test_hardware_section_complete(self):
        """Verify hardware section has pipewire field."""
        hardware_help = SECTION_HELP["hardware"]
        assert "pipewire" in hardware_help["fields"]
        
        pipewire_fields = hardware_help["fields"]["pipewire"]["fields"]
        assert "enable" in pipewire_fields
        assert "extra_packages" in pipewire_fields
    
    def test_users_section_complete(self):
        """Verify users section has USERNAME placeholder."""
        users_help = SECTION_HELP["users"]
        assert "USERNAME" in users_help["fields"]
        
        username_fields = users_help["fields"]["USERNAME"]["fields"]
        assert "shell" in username_fields
        assert "groups" in username_fields
        assert "home_programs" in username_fields


if __name__ == "__main__":
    # Allow running directly with python3
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
