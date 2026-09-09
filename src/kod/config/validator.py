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


def _validate_program_service(program, location: str) -> Optional[ValidationError]:
    """Validate service configuration for a program at given location.
    
    Service validation rules:
    - Service field only valid at system level (not user.*)
    - Service requires service_name (non-empty string)
    - Service requires enable (boolean)
    - Program scope must be "system" or "both" to have service
    
    Args:
        program: Program object with get_service() method
        location: "system" or "user.alice" etc.
        
    Returns:
        ValidationError if service is invalid, None if valid
    """
    service = program.get_service()
    if not service:
        return None  # No service field, that's valid
    
    # Service only allowed at system level (not user level)
    if location.startswith("user."):
        location_suffix = f"{location}.programs.{program.name}"
        return ValidationError(
            f"Service configuration for '{program.name}' not allowed at user level. "
            f"Remove service field or move to top-level 'programs' section.",
            location=location_suffix,
        )
    
    # Service only allowed for programs with system/both scope
    scope = program.get_scope()
    if scope not in ["system", "both"]:
        # At system level, just use "programs.{name}"
        if location == "system":
            location_suffix = f"programs.{program.name}"
        else:
            location_suffix = f"{location}.programs.{program.name}"
        return ValidationError(
            f"Program '{program.name}' has service definition but scope='{scope}'. "
            f"Service only allowed with scope='system' or scope='both'. "
            f"Either remove service field or change scope.",
            location=location_suffix,
        )
    
    # Validate required service fields
    required_fields = ["service_name", "enable"]
    for field in required_fields:
        if field not in service:
            if location == "system":
                location_suffix = f"programs.{program.name}"
            else:
                location_suffix = f"{location}.programs.{program.name}"
            return ValidationError(
                f"Program '{program.name}' service missing required field '{field}'.",
                location=location_suffix,
            )
    
    # service_name must be non-empty string
    service_name = service.get("service_name")
    if not isinstance(service_name, str) or not service_name:
        if location == "system":
            location_suffix = f"programs.{program.name}.service.service_name"
        else:
            location_suffix = f"{location}.programs.{program.name}.service.service_name"
        return ValidationError(
            f"Program '{program.name}' service.service_name must be a non-empty string.",
            location=location_suffix,
        )
    
    # enable must be boolean
    enable = service.get("enable")
    if not isinstance(enable, bool):
        if location == "system":
            location_suffix = f"programs.{program.name}.service.enable"
        else:
            location_suffix = f"{location}.programs.{program.name}.service.enable"
        return ValidationError(
            f"Program '{program.name}' service.enable must be boolean.",
            location=location_suffix,
        )
    
    return None


def _validate_programs_section(programs: dict, location: str = "system") -> List[ValidationError]:
    """Validate the 'programs' section in config.
    
    For each program name in the section:
    1. Load the program via PluginLoader
    2. Validate the program options against its schema
    3. Validate service configuration (if present)
    4. Collect all errors together
    
    Args:
        programs: The programs dict from config
        location: "system" or "user.alice" etc. (default: "system")
        
    Returns:
        List of ValidationError objects (may be empty)
    """
    errors: List[ValidationError] = []
    
    # Import here to avoid circular imports
    from kod.registry.loader import PluginLoader
    from kod.registry.programs import ProgramNotFound, ConfigValidationError, ProgramError
    
    loader = PluginLoader()
    
    # Determine location suffix for error messages
    if location == "system":
        loc_prefix = "programs"
    else:
        loc_prefix = f"{location}.programs"
    
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
                        location=f"{loc_prefix}.{program_name}",
                    )
                )
            
            # Validate service configuration (NEW)
            service_error = _validate_program_service(program, location)
            if service_error:
                errors.append(service_error)
                
        except ProgramNotFound as e:
            # Build helpful error message with available programs
            available = loader.list_programs()
            available_str = ", ".join(available) if available else "(none)"
            errors.append(
                ValidationError(
                    f"Unknown program '{program_name}'. Available: {available_str}",
                    location=f"{loc_prefix}.{program_name}",
                )
            )
        except ProgramError as e:
            errors.append(
                ValidationError(
                    f"Program '{program_name}': {str(e)}",
                    location=f"{loc_prefix}.{program_name}",
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
