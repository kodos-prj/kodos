"""Configuration validation (Phase 1 + Phase 3).

Validates a loaded Kodos configuration against the schema.
Returns a list of ValidationError objects; empty list means valid.

Phase 3 additions:
- Validates 'programs' section if present
- Loads each program and validates its options
- Collects all errors before reporting
"""

from difflib import get_close_matches
from typing import List, Optional

from kod.config.schema import SCHEMA
from kod.exceptions import ValidationError


def _suggest(key: str) -> Optional[str]:
    match = get_close_matches(key, SCHEMA.keys(), n=1)
    if match:
        return f"Did you mean '{match[0]}'?"
    return None


def _type_ok(value, expected) -> bool:
    """Check value against expected type, handling lupa LuaTables.

    Lua has one table type; array-ness is detected from int keys 1..n.
    ponytail: empty tables are ambiguous and accepted for either type.
    """
    if isinstance(value, expected):
        return True
    if expected not in (dict, list):
        return False
    try:
        keys = list(value.keys())
    except (AttributeError, TypeError):
        return False
    if not keys:
        return True
    int_keys = all(isinstance(k, int) for k in keys)
    return int_keys if expected is list else not int_keys


def _validate_programs_section(programs: dict) -> List[ValidationError]:
    """Validate the 'programs' section in config.
    
    For each program name in the section:
    1. Load the program via PluginLoader
    2. Validate the program options against its schema
    3. Collect all errors together
    
    Args:
        programs: The programs dict from config
        
    Returns:
        List of ValidationError objects (may be empty)
    """
    errors: List[ValidationError] = []
    
    # Import here to avoid circular imports
    from kod.registry.loader import PluginLoader
    from kod.registry.programs import ProgramNotFound, ConfigValidationError, ProgramError
    
    loader = PluginLoader()
    
    for program_name, program_options in programs.items():
        try:
            # Try to load the program
            program = loader.load_program(program_name)
            
            # Validate program options against its schema
            try:
                program.validate_config(program_options)
            except ConfigValidationError as e:
                errors.append(
                    ValidationError(
                        str(e),
                        location=f"programs.{program_name}",
                    )
                )
        except ProgramNotFound as e:
            # Build helpful error message with available programs
            available = loader.list_programs()
            available_str = ", ".join(available) if available else "(none)"
            errors.append(
                ValidationError(
                    f"Unknown program '{program_name}'. Available: {available_str}",
                    location=f"programs.{program_name}",
                )
            )
        except ProgramError as e:
            errors.append(
                ValidationError(
                    f"Program '{program_name}': {str(e)}",
                    location=f"programs.{program_name}",
                )
            )
    
    return errors



def validate_config(config: dict) -> List[ValidationError]:
    errors: List[ValidationError] = []
    for key, value in config.items():
        if key not in SCHEMA:
            suggestion = _suggest(key)
            message = f"Unknown option '{key}'"
            if suggestion:
                message += f". {suggestion}"
            errors.append(ValidationError(message, location=key))
            continue
        expected = SCHEMA[key]
        if not _type_ok(value, expected):
            kind = "list" if expected is list else "table"
            errors.append(
                ValidationError(
                    f"Option '{key}' must be a {kind}, "
                    f"got {type(value).__name__}",
                    location=key,
                )
            )
    
    # Phase 3: Validate programs section if present
    # Use try/except to handle lupa LuaTable which may not support 'in' operator
    try:
        has_programs = "programs" in config
    except TypeError:
        # LuaTable or similar object without __contains__
        has_programs = False
    
    if has_programs:
        errors.extend(_validate_programs_section(config["programs"]))
    
    return errors
