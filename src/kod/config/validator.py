"""Configuration validation (Phase 1 + Phase 3 + Phase 5c).

Validates a loaded Kodos configuration against the Lua schema.
Returns a list of ValidationError objects; empty list means valid.

Phase 3 additions:
- Validates 'programs' section if present
- Loads each program and validates its options
- Collects all errors before reporting

Phase 5c additions:
- Loads Lua schema as single source of truth
- Python validator reads Lua schema (not duplicate SECTION_HELP)
"""

import logging
from difflib import get_close_matches
from typing import List, Optional, Dict

from kod.config.schema import SCHEMA, SECTION_HELP
from kod.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Lazy-loaded Lua schema (cached)
_lua_schema_cache = None


def _get_lua_schema() -> Optional[Dict]:
    """Load Lua schema and cache it.
    
    Returns:
        Dict with Lua schema, or None if Lua unavailable.
        On first call, loads and caches the schema.
    """
    global _lua_schema_cache
    
    if _lua_schema_cache is not None:
        return _lua_schema_cache
    
    try:
        from kod.lua_runtime import get_lua_runtime
        
        lua = get_lua_runtime()
        schema_module = lua.require('kod.lib.schema')
        
        # Convert Lua schema to Python dict
        schema = {}
        for section_name in [
            'base_distribution', 'repos', 'devices', 'boot', 'hardware',
            'locale', 'network', 'users', 'desktop', 'fonts',
            'packages', 'services', 'programs'
        ]:
            section_def = schema_module[section_name]
            schema[section_name] = _lua_table_to_dict(section_def)
        
        _lua_schema_cache = schema
        return schema
    
    except Exception as e:
        logger.warning(f"Failed to load Lua schema: {e}. Using fallback SECTION_HELP.")
        return None


def _lua_table_to_dict(lua_table) -> Dict:
    """Convert Lua table to Python dict recursively.
    
    Args:
        lua_table: Lua table from lupa
        
    Returns:
        Python dict/list representation
    """
    if lua_table is None:
        return None
    
    if not isinstance(lua_table, dict):
        return lua_table
    
    result = {}
    try:
        for key, value in lua_table.items():
            if isinstance(value, dict):
                result[key] = _lua_table_to_dict(value)
            elif isinstance(value, (list, tuple)):
                result[key] = [_lua_table_to_dict(v) if isinstance(v, dict) else v for v in value]
            else:
                result[key] = value
    except (AttributeError, TypeError):
        # Not a dict-like object, return as-is
        return lua_table
    
    return result


def _lookup_field_help(section_key: str, field_path: List[str]) -> Optional[Dict]:
    """Look up help for a nested field path: ["boot", "kernel", "package"].
    
    First tries Lua schema (Phase 5c), then falls back to SECTION_HELP (Phase 5b).
    
    Args:
        section_key: Top-level section name (e.g., "boot")
        field_path: List of nested field names to follow
    
    Returns:
        Dict with field help info, or None if path not found
    """
    # Try Lua schema first (Phase 5c)
    lua_schema = _get_lua_schema()
    if lua_schema and section_key in lua_schema:
        help_entry = lua_schema[section_key]
        current = help_entry
        for field_name in field_path:
            if "fields" not in current:
                return None
            current = current["fields"].get(field_name)
            if not current:
                return None
        return current
    
    # Fallback to SECTION_HELP (Phase 5b)
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
    # Use Lua schema if available, otherwise SCHEMA
    lua_schema = _get_lua_schema()
    available_keys = list(lua_schema.keys()) if lua_schema else list(SCHEMA.keys())
    match = get_close_matches(key, available_keys, n=1)
    if match:
        return f"Did you mean '{match[0]}'?"
    return None


def _validate_against_lua_schema(config: dict) -> List[ValidationError]:
    """Validate config against Lua schema.
    
    Phase 5c: Use Lua schema as single source of truth.
    Validates:
    - Required fields
    - Type checking (string, dict, list, number, boolean)
    - Enum values
    - Nested field types
    
    Args:
        config: Configuration dict to validate
        
    Returns:
        List of ValidationError objects
    """
    errors: List[ValidationError] = []
    
    lua_schema = _get_lua_schema()
    if not lua_schema:
        # Lua unavailable, skip Lua schema validation
        return errors
    
    # Check required fields
    if 'base_distribution' not in config:
        errors.append(
            ValidationError(
                "Option 'base_distribution' is required.",
                location='base_distribution'
            )
        )
    
    # Validate each section
    for section_name, section_schema in lua_schema.items():
        if section_name not in config:
            continue  # Section not present, that's OK (optional)
        
        section_value = config[section_name]
        section_errors = _validate_section_recursive(
            section_name,
            section_schema,
            section_value,
            section_name
        )
        errors.extend(section_errors)
    
    return errors


def _validate_section_recursive(
    field_name: str,
    schema_def: Dict,
    value,
    path: str
) -> List[ValidationError]:
    """Recursively validate a field against its schema definition.
    
    Args:
        field_name: Name of field being validated
        schema_def: Schema definition (from Lua schema)
        value: Actual value to validate
        path: Dot-separated path for error messages
        
    Returns:
        List of ValidationError objects
    """
    errors: List[ValidationError] = []
    
    if value is None:
        # Optional field can be None
        if schema_def.get('required'):
            errors.append(
                ValidationError(
                    f"Option '{path}' is required.",
                    location=path
                )
            )
        return errors
    
    # Type validation
    schema_type = schema_def.get('type')
    if schema_type == 'string':
        if not isinstance(value, str):
            errors.append(
                ValidationError(
                    f"Option '{path}' must be string, got {type(value).__name__}",
                    location=path
                )
            )
    elif schema_type == 'number':
        if not isinstance(value, (int, float)):
            errors.append(
                ValidationError(
                    f"Option '{path}' must be number, got {type(value).__name__}",
                    location=path
                )
            )
    elif schema_type == 'boolean':
        if not isinstance(value, bool):
            errors.append(
                ValidationError(
                    f"Option '{path}' must be boolean, got {type(value).__name__}",
                    location=path
                )
            )
    elif schema_type == 'dict':
        if not _type_ok(value, dict):
            errors.append(
                ValidationError(
                    f"Option '{path}' must be dict, got {type(value).__name__}",
                    location=path
                )
            )
        else:
            # Validate nested fields
            if 'fields' in schema_def:
                for nested_field_name, nested_schema in schema_def['fields'].items():
                    nested_value = value.get(nested_field_name) if isinstance(value, dict) else None
                    nested_path = f"{path}.{nested_field_name}"
                    nested_errors = _validate_section_recursive(
                        nested_field_name,
                        nested_schema,
                        nested_value,
                        nested_path
                    )
                    errors.extend(nested_errors)
    elif schema_type == 'list':
        if not _type_ok(value, list):
            errors.append(
                ValidationError(
                    f"Option '{path}' must be list, got {type(value).__name__}",
                    location=path
                )
            )
    
    # Enum validation
    if schema_def.get('enum') and value is not None:
        if value not in schema_def['enum']:
            errors.append(
                ValidationError(
                    f"Option '{path}' must be one of {schema_def['enum']}, got {value}",
                    location=path
                )
            )
    
    return errors


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


def _validate_users_section(users: dict) -> List[ValidationError]:
    """Validate the 'users' section in config, including nested programs/services (Task 11).
    
    For each user in the section:
    1. Validate user-level programs (if present)
    2. Validate user-level services (if present)
    3. Collect all errors together
    
    Args:
        users: The users dict from config
        
    Returns:
        List of ValidationError objects (may be empty)
    """
    errors: List[ValidationError] = []
    
    if not users:
        return errors
    
    for username, user_config in users.items():
        if not isinstance(user_config, dict):
            continue
        
        # Validate user-level programs (Task 11)
        if "programs" in user_config:
            user_programs = user_config["programs"]
            if isinstance(user_programs, dict):
                user_prog_errors = _validate_programs_section(
                    user_programs,
                    location=f"users.{username}"
                )
                errors.extend(user_prog_errors)
        
        # Validate user-level services (Task 11)
        if "services" in user_config:
            user_services = user_config["services"]
            if isinstance(user_services, dict):
                user_svc_errors = _validate_services_section(
                    user_services,
                    location=f"users.{username}"
                )
                errors.extend(user_svc_errors)
    
    return errors


def _validate_services_section(services: dict, location: str = "system") -> List[ValidationError]:
    """Validate the 'services' section in config (Task 11 - supports nested user services).
    
    For each service name in the section:
    1. Basic structure validation
    2. Collect errors together
    
    Args:
        services: The services dict from config
        location: "system" or "users.<username>" etc. (default: "system")
        
    Returns:
        List of ValidationError objects (may be empty)
    """
    errors: List[ValidationError] = []
    
    if not services or not isinstance(services, dict):
        return errors
    
    # Determine location suffix for error messages
    if location == "system":
        loc_prefix = "services"
    else:
        loc_prefix = f"{location}.services"
    
    for service_name, service_config in services.items():
        if not isinstance(service_config, dict):
            continue
        
        # Skip reserved fields like 'config' and 'systemd'
        if service_name in ["config", "systemd"]:
            continue
        
        # Basic validation: service_name should be string
        if not isinstance(service_name, str):
            errors.append(
                ValidationError(
                    f"Service name must be string, got {type(service_name).__name__}",
                    location=f"{loc_prefix}.{service_name}",
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
    
    # Phase 5c: Validate using Lua schema (if available)
    lua_schema = _get_lua_schema()
    if lua_schema:
        errors.extend(_validate_against_lua_schema(config))
    else:
        # Fallback to Phase 5b validation (SECTION_HELP-based)
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
    
    # Task 11: Validate users section (including nested programs/services)
    try:
        has_users = "users" in config
    except TypeError:
        # LuaTable or similar object without __contains__
        has_users = False
    
    if has_users:
        errors.extend(_validate_users_section(config["users"]))
    
    # Phase 5b: Validate nested fields (best-effort)
    errors.extend(_validate_nested_fields(config))
    
    return errors
