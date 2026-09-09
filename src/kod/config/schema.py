"""Configuration schema definition and validation (Phase 1).

Defines the structure of valid Kodos configurations using a schema system.
Provides type checking, enum validation, and helpful error messages.

Key components:
- OptionType: Base class for configuration option types
- Schema: Main schema registry
- Validator: Validates config against schema

Example:
    >>> schema = Schema()
    >>> schema.get("hostname")  # Returns type info
"""

# TODO (Phase 1): Implement schema system
#   - Define core option types (string, enum, bool, list, dict)
#   - Build schema registry for all config options
#   - Add type checking and enum validation
#   - Create validation error formatting
