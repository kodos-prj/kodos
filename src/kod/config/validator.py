"""Configuration validation (Phase 1).

Validates a loaded Kodos configuration against the schema.
Provides clear error messages for typos, missing required options, wrong types.

Key components:
- ValidationError: Structured validation errors with line numbers
- Validator: Main validation orchestrator
- validate_config(): Public API

Example:
    >>> validator = Validator(schema)
    >>> errors = validator.validate(config_dict)
    >>> if errors:
    ...     for error in errors:
    ...         print(error)
"""

# TODO (Phase 1): Implement validator
#   - Walk config tree against schema
#   - Report type errors with helpful messages
#   - Check for required options
#   - Validate enum values
#   - Detect dependency implications (GNOME -> gdm)
