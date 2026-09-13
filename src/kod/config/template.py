"""Generate template configuration files for KodOS.

This module provides functions to generate starter Lua configuration templates
with all sections documented as comments, using descriptions from the
Lua schema (kod/lib/schema.lua).
"""

from kod.config.schema import get_lua_schema


def generate_config_template(distro: str = "arch") -> str:
    """Generate a starter Lua config file with commented sections.

    Args:
        distro: Target distribution ("arch" or "debian")

    Returns:
        Lua config as string with all sections commented and explained
    """
    lines = [
        "-- KodOS Configuration Template",
        f"-- Distribution: {distro}",
        "--",
        "-- See 'kod config schema' for full documentation.",
        "-- Uncomment sections below and customize as needed.",
        "--",
        "return {",
    ]

    for section_name, help_entry in get_lua_schema().items():
        lines.append("")
        lines.append(f"    -- {section_name.upper()}")

        description = help_entry.get("description", "")
        if description:
            lines.append(f"    -- {description}")

        if help_entry.get("required"):
            lines.append("    -- Required: Yes")

        if help_entry.get("example"):
            lines.append("    --")
            lines.append("    -- Example:")
            for example_line in help_entry["example"].split('\n'):
                lines.append(f"    -- {example_line}")

        lines.append(f"    -- {section_name} = ...,")

    lines.append("")
    lines.append("}")

    return '\n'.join(lines)
