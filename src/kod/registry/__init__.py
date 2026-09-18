"""Kodos program registry system.

Extensible registry for program definitions and configurations:
- Builtin programs
- Plugin loading system
- Build templates

MAIN API: kod.registry_wrapper
- PluginLoader: Load programs from builtin and user plugins
- Program: Represents a loaded program with validation and generation
- Exception hierarchy: ProgramError, ProgramNotFound, etc.

UTILITIES: kod.registry.util
- lua_to_dict: Convert Lua tables to Python dicts
- Exception classes

See docs/superpowers/specs/2026-09-09-architecture-redesign.md for details.
"""

# NOTE: Imports should use kod.registry_wrapper and kod.registry.util directly
# to avoid circular imports
