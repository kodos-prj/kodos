"""Configuration validation (Phase 1 + Phase 3).

Validates a loaded Kodos configuration against the schema.
Returns a list of ValidationError objects; empty list means valid.

Phase 3 additions:
- Validates 'programs' section if present
- Loads each program and validates its options
- Collects all errors before reporting
"""

from difflib import get_close_matches
from typing import List, Optional, Dict

from kod.config.schema import SCHEMA, SECTION_HELP
from kod.exceptions import ValidationError


def _lookup_field_help(section_key: str, field_path: List[str]) -> Optional[Dict]:
    """Look up help for a nested field path: ["boot", "kernel", "package"].
    
    Args:
        section_key: Top-level section name (e.g., "boot")
        field_path: List of nested field names to follow
    
    Returns:
        Dict with field help info, or None if path not found
    """
    help_entry = SECTION_HELP.get(section_key)
    if not help_entry:
        return None
    
    current = help_entry
    for field_name in field_path:
        if "fields" not in current:
            return None
        current = current["fields"].get(field_name)
        if not current:
            return None
    
    return current


def _suggest(key: str) -> Optional[str]:
    match = get_close_matches(key, SCHEMA.keys(), n=1)
    if match:
        return f"Did you mean '{match[0]}'?"
    return None


def _format_error_with_help(base_message: str, section_key: str, help_info: Optional[Dict] = None) -> str:
    """Format an error message with help text from SECTION_HELP.
    
    Args:
        base_message: The base error message
        section_key: Top-level section name
        help_info: Optional help dict from SECTION_HELP or _lookup_field_help()
    
    Returns:
        Formatted error message with help text
    """
    if not help_info:
        help_info = SECTION_HELP.get(section_key, {})
    
    lines = [base_message]
    
    # Add error_help if available
    if "error_help" in help_info:
        lines.append("")
        lines.append(f"  {help_info['error_help']}")
    # Otherwise add description
    elif "description" in help_info:
        lines.append("")
        lines.append(f"  {help_info['description']}")
    
    # Add example if available
    if "example" in help_info:
        lines.append("")
        lines.append("  Example:")
        for ex_line in help_info["example"].split("\n"):
            lines.append(f"    {ex_line}")
    
    return "\n".join(lines)


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


def _validate_nested_fields(config: dict) -> List[ValidationError]:
    """Validate nested field types (best-effort, optional fields only).
    
    Checks known nested fields like boot.kernel, locale.timezone, etc.
    Does NOT validate enum values or dependent fields.
    Unknown fields are silently ignored (not errors).
    
    Args:
        config: The config dict
    
    Returns:
        List of ValidationError objects for nested field type mismatches
    """
    errors: List[ValidationError] = []
    
    # Define nested field type checks: (section_key, [field_path], expected_type)
    nested_checks = [
        ("boot", ["kernel"], dict),
        ("boot", ["kernel", "modules"], list),
        ("boot", ["loader"], dict),
        ("hardware", ["pipewire"], dict),
        ("hardware", ["pipewire", "enable"], bool),
        ("hardware", ["pipewire", "extra_packages"], list),
        ("locale", ["locale"], dict),
        ("locale", ["timezone"], str),
        ("locale", ["keymap"], str),
        ("network", ["hostname"], str),
        ("network", ["ipv6"], bool),
        ("services", None, dict),  # Services dict itself must be dict
        ("users", None, dict),  # Users dict itself must be dict
    ]
    
    for check in nested_checks:
        section_key = check[0]
        field_path = check[1]
        expected_type = check[2]
        
        # Skip if section not in config
        try:
            has_section = section_key in config
        except TypeError:
            # LuaTable or similar; try get instead
            try:
                section_value = config.get(section_key) if hasattr(config, 'get') else None
                has_section = section_value is not None
            except (AttributeError, TypeError):
                continue
        
        if not has_section:
            continue
        
        section_value = config[section_key]
        
        # If field_path is None, we already checked the section type
        if field_path is None:
            continue
        
        # Navigate to the nested field
        current = section_value
        try:
            for i, field_name in enumerate(field_path):
                if isinstance(current, dict):
                    current = current.get(field_name)
                else:
                    # Can't navigate further, skip this check
                    current = None
                    break
                
                if current is None:
                    # Field not present, that's ok (optional)
                    break
        except (AttributeError, TypeError):
            # Not a dict-like object, skip
            continue
        
        # If we found the field, validate its type
        if current is not None and not _type_ok(current, expected_type):
            kind = "list" if expected_type is list else "dict" if expected_type is dict else expected_type.__name__
            field_path_str = ".".join(field_path)
            location = f"{section_key}.{field_path_str}"
            
            # Try to get help for this nested field
            help_info = _lookup_field_help(section_key, field_path)
            if help_info:
                message = _format_error_with_help(
                    f"Option '{location}' must be a {kind}, got {type(current).__name__}",
                    section_key,
                    help_info
                )
            else:
                message = f"Option '{location}' must be a {kind}, got {type(current).__name__}"
            
            errors.append(ValidationError(message, location=location))
    
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
            base_message = f"Option '{key}' must be a {kind}, got {type(value).__name__}"
            # Use new formatting with help info
            message = _format_error_with_help(base_message, key)
            errors.append(
                ValidationError(message, location=key)
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
    
    # Phase 5b: Validate nested fields (best-effort)
    errors.extend(_validate_nested_fields(config))
    
    return errors
