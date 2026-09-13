"""Tests for kod.config.schema (Lua schema is the single source of truth)."""

import sys

from kod.config.schema import get_lua_schema

ALL_SECTIONS = [
    "base_distribution", "repos", "devices", "boot", "hardware",
    "locale", "network", "users", "desktop", "fonts",
    "packages", "services", "programs",
]


class TestSchemaStructure:
    """The Lua schema loads and covers all sections."""

    def test_all_sections_present(self):
        schema = get_lua_schema()
        for section in ALL_SECTIONS:
            assert section in schema, f"missing section: {section}"

    def test_every_section_has_type_and_description(self):
        schema = get_lua_schema()
        for name, entry in schema.items():
            assert "type" in entry, f"{name} missing type"
            assert entry.get("description"), f"{name} missing description"

    def test_every_section_has_example(self):
        schema = get_lua_schema()
        for name, entry in schema.items():
            assert entry.get("example"), f"{name} missing example"

    def test_base_distribution_required_with_enum(self):
        entry = get_lua_schema()["base_distribution"]
        assert entry["required"] is True
        assert entry["enum"] == ["arch", "debian"]


class TestFieldPathLookup:
    """Nested field paths resolve through the Lua schema."""

    def _lookup(self, section_key, field_path):
        current = get_lua_schema()[section_key]
        for field_name in field_path:
            if "fields" not in current:
                return None
            current = current["fields"].get(field_name)
            if not current:
                return None
        return current

    def test_boot_kernel_package_lookup(self):
        field = self._lookup("boot", ["kernel", "package"])
        assert field is not None
        assert field["type"] == "string"
        assert field["default"] == "linux"

    def test_users_username_identity_shell_lookup(self):
        """Verify users.USERNAME.identity.shell path resolves correctly."""
        identity = self._lookup("users", ["identity"])
        assert identity is not None

        shell_field = identity.get("fields", {}).get("shell")
        assert shell_field is not None
        assert "description" in shell_field

    def test_users_identity_documents_password_and_groups(self):
        identity = self._lookup("users", ["identity"])
        fields = identity["fields"]
        assert "password" in fields
        assert "hashed_password" in fields
        assert "groups" in fields


class TestSpecificSections:
    """Spot-checks on specific sections."""

    def test_boot_loader_type_has_enum(self):
        loader_type = get_lua_schema()["boot"]["fields"]["loader"]["fields"]["type"]
        assert "systemd-boot" in loader_type["enum"]
        assert "grub" in loader_type["enum"]

    def test_users_section_complete(self):
        """Verify users section documents the identity block."""
        users = get_lua_schema()["users"]
        identity_fields = users["fields"]["identity"]["fields"]
        assert "name" in identity_fields
        assert "shell" in identity_fields
        assert "groups" in identity_fields


if __name__ == "__main__":
    # Allow running directly with python3
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
