"""Program definitions and error hierarchy (Phase 3).

Implements Lua-based program definitions with schema validation and inheritance.

Key components:
- Error hierarchy (ProgramError, ProgramNotFound, etc.)
- Program class: wraps Lua definitions with Python interface

Program loading is handled by PluginLoader (in loader.py).

Example:
    >>> from loader import PluginLoader
    >>> loader = PluginLoader()
    >>> git_prog = loader.load_program("git")
    >>> git_prog.validate_config({"user_name": "Alice", "email": "alice@example.com"})
    >>> config = git_prog.generate_config({"user_name": "Alice", "email": "alice@example.com"})
"""

from typing import Dict, Any, Optional, List


# ===== Error Hierarchy =====


class ProgramError(Exception):
    """Base exception for program registry errors."""

    pass


class ProgramNotFound(ProgramError):
    """Program name not found in registry."""

    pass


class ProgramLoadError(ProgramError):
    """Failed to load program (Lua syntax error, missing fields, etc.)."""

    pass


class CircularExtendError(ProgramLoadError):
    """Program extends itself (directly or indirectly)."""

    pass


class ConfigValidationError(ProgramError):
    """User config doesn't match program schema."""

    pass


class SchemaError(ProgramError):
    """Program schema is malformed."""

    pass


# ===== Program Class =====


class Program:
    """Wraps a Lua program definition with Python interface.
    
    A Program represents a configurable application with:
    - Scope: where the program can be configured ("system", "user", or "both")
    - Schema: JSON schema describing valid config options
    - Default config: template values
    - generate_config(): function to generate shell commands from user options
    - Optional service: systemd service definition (only for system/both scope)
    - Optional hooks: validate, post_install, pre_uninstall
    - Optional inheritance: extends another program via _extends field
    
    Service Field (optional):
    - service_name (required): name of systemd service
    - enable (required): boolean to enable service
    - socket_activation (optional, default false): use socket activation
    - user_service (optional, default false): service can run per-user
    - restart_policy (optional, default "always"): systemd restart policy
    - after (optional): list of services to start after
    - wanted_by (optional): list of systemd targets
    - per_user (optional, default false): each user gets own service instance
    
    Service scope compatibility:
    - scope="user": service NOT allowed (user programs don't have services)
    - scope="system": service optional
    - scope="both": service optional (can have per-user service)
    """

    def __init__(self, name: str, lua_def: Dict[str, Any], parent: Optional["Program"] = None):
        """Initialize Program from Lua definition.
        
        Args:
            name: Program name (e.g., "git")
            lua_def: Lua return value (dict from loaded .lua file)
            parent: Parent Program if this extends another
            
        Raises:
            ProgramLoadError: If lua_def missing required fields
            SchemaError: If scope field is invalid or service field invalid
        """
        self.name = name
        self.lua_def = lua_def
        self.parent = parent
        
        # Validate required fields
        # If extending another program, name/schema/default_config/generate_config can come from parent
        required_fields = {"schema", "default_config", "generate_config"}
        if not parent:
            # Top-level program must have name
            required_fields.add("name")
        
        missing = required_fields - set(lua_def.keys())
        if missing:
            raise ProgramLoadError(
                f"Program '{name}' missing required fields: {missing}"
            )
        
        # Extract and validate scope field
        scope = lua_def.get("scope", "user")
        valid_scopes = {"system", "user", "both"}
        if scope not in valid_scopes:
            raise SchemaError(
                f"Invalid scope '{scope}'. Must be 'system', 'user', or 'both'"
            )
        self.scope = scope
        
        # Extract and validate service field
        self.service = self._extract_service(lua_def)
        
        # Store Lua methods
        self._lua_generate_config = lua_def.get("generate_config")
        self._lua_validate = lua_def.get("validate")
        self._lua_post_install = lua_def.get("post_install")
        self._lua_pre_uninstall = lua_def.get("pre_uninstall")

    def get_scope(self) -> str:
        """Return the scope of this program.
        
        Returns:
            One of "system", "user", or "both"
        """
        return self.scope
    
    def get_schema(self) -> Dict[str, Any]:
        """Return merged JSON schema (builtin + user extensions).
        
        If this program extends another:
            {"allOf": [parent_schema, user_schema]}
        Otherwise:
            Raw schema from definition
            
        Returns:
            JSON schema dict
        """
        user_schema = self.lua_def.get("schema", {})
        
        if not self.parent:
            return user_schema
        
        # Merge with parent schema using allOf
        parent_schema = self.parent.get_schema()
        return {
            "allOf": [parent_schema, user_schema]
        }

    def validate_config(self, options: Dict[str, Any]) -> None:
        """Validate options against schema.
        
        Performs basic schema validation:
        1. Check required fields are present
        2. Check field types match schema
        3. Call optional Lua validate hook if present
        
        Args:
            options: User-provided config options
            
        Raises:
            ConfigValidationError: If options don't match schema
        """
        schema = self.get_schema()
        
        # Basic schema validation
        errors = self._validate_against_schema(options, schema)
        if errors:
            error_msg = f"Program '{self.name}': " + "; ".join(errors)
            raise ConfigValidationError(error_msg)
        
        # Use lupa to execute Lua validation hook if present
        if self._lua_validate:
            try:
                # Call Lua validate function with self as first arg
                self._lua_validate(self, options)
            except Exception as e:
                raise ConfigValidationError(
                    f"Program '{self.name}' validation failed: {str(e)}"
                )
    
    def _validate_against_schema(self, options: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        """Validate options against schema.
        
        Basic validation:
        - Check required fields
        - Check field types
        
        Handles Lua tables and converts them to dicts for comparison.
        
        Args:
            options: User-provided options
            schema: Schema dict from program
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Convert lupa tables to dicts
        schema = self._lua_to_dict(schema)
        options = self._lua_to_dict(options)
        
        # Handle allOf (merged schema from inheritance)
        if isinstance(schema, dict) and "allOf" in schema:
            # Collect all schemas and validate against all
            for sub_schema in schema["allOf"]:
                errors.extend(self._validate_against_schema(options, sub_schema))
            return errors
        
        # Normal schema validation
        # Schema can be either {"properties": {...}} or directly {field: {...}}
        if isinstance(schema, dict):
            properties = schema.get("properties", schema)
        else:
            return errors
        
        for field_name, field_schema in properties.items():
            # Skip internal fields like "allOf"
            if field_name.startswith("$") or field_name in ("properties", "allOf", "type"):
                continue
            
            # Skip non-dict field schemas
            if not isinstance(field_schema, dict):
                continue
            
            is_required = field_schema.get("required", False)
            
            if field_name in options:
                # Field present - check type if needed
                value = options[field_name]
                expected_type = field_schema.get("type")
                
                if expected_type and not self._check_type(value, expected_type):
                    errors.append(f"Field '{field_name}' must be {expected_type}, got {type(value).__name__}")
            elif is_required:
                # Field missing but required
                errors.append(f"Missing required field '{field_name}'")
        
        return errors
    
    @staticmethod
    def _lua_to_dict(obj: Any) -> Any:
        """Convert lupa Lua objects to Python dicts/lists.
        
        Args:
            obj: Object potentially from Lua
            
        Returns:
            Python dict/list/value
        """
        # Handle lupa LuaTable
        if hasattr(obj, "items") and not isinstance(obj, dict):
            try:
                return {k: Program._lua_to_dict(v) for k, v in obj.items()}
            except (AttributeError, TypeError):
                return obj
        
        # Handle regular dict
        if isinstance(obj, dict):
            return {k: Program._lua_to_dict(v) for k, v in obj.items()}
        
        # Handle lists/tuples
        if isinstance(obj, (list, tuple)):
            return [Program._lua_to_dict(v) for v in obj]
        
        # Return as-is for scalars
        return obj
    
    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """Check if value matches expected type.
        
        Args:
            value: Value to check
            expected_type: Expected type string (e.g., "string", "boolean", "integer")
            
        Returns:
            True if type matches
        """
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, assume valid
        
        return isinstance(value, expected)

    def generate_config(self, options: Dict[str, Any]) -> str:
        """Generate shell commands or config content.
        
        Calls the Lua generate_config function with self as first argument.
        Lua code can call self:_parent_method() to access parent's methods.
        
        Args:
            options: User-provided config options
            
        Returns:
            Shell commands (string) or config file content
            
        Raises:
            ProgramLoadError: If generate_config fails
        """
        if not self._lua_generate_config:
            raise ProgramLoadError(
                f"Program '{self.name}' missing generate_config method"
            )
        
        try:
            # Call Lua function with self as first argument
            result = self._lua_generate_config(self, options)
            return result if result else ""
        except Exception as e:
            raise ProgramLoadError(
                f"Program '{self.name}' generate_config failed: {str(e)}"
            )

    def run_hook(self, hook_name: str, *args: Any) -> Any:
        """Run a lifecycle hook (validate, post_install, pre_uninstall).
        
        Args:
            hook_name: "validate", "post_install", "pre_uninstall"
            *args: Arguments to pass to hook
            
        Returns:
            Hook result (typically None or error)
            
        Raises:
            ProgramLoadError: If hook fails
        """
        hook_map = {
            "validate": self._lua_validate,
            "post_install": self._lua_post_install,
            "pre_uninstall": self._lua_pre_uninstall,
        }
        
        hook_func = hook_map.get(hook_name)
        if not hook_func:
            return None
        
        try:
            return hook_func(self, *args)
        except Exception as e:
            raise ProgramLoadError(
                f"Program '{self.name}' hook '{hook_name}' failed: {str(e)}"
            )

    def _parent_method(self, method_name: str, *args: Any) -> Any:
        """Call parent's method (used by Lua code).
        
        Allows Lua code to call self:_parent_method("generate_config", options)
        to get the parent program's implementation.
        
        Args:
            method_name: Name of method to call ("generate_config", etc.)
            *args: Arguments to pass to method
            
        Returns:
            Result from parent method
            
        Raises:
            ProgramLoadError: If no parent or method doesn't exist
        """
        if not self.parent:
            raise ProgramLoadError(
                f"Program '{self.name}' has no parent to call {method_name}"
            )
        
        if method_name == "generate_config":
            return self.parent.generate_config(*args)
        elif method_name == "validate":
            return self.parent.run_hook("validate", *args)
        else:
            raise ProgramLoadError(
                f"Unknown parent method: {method_name}"
            )

    def _get_parent(self) -> Optional["Program"]:
        """Get parent program (used by Lua code).
        
        Returns:
            Parent Program object or None
        """
        return self.parent

    def _get_merged_schema(self) -> Dict[str, Any]:
        """Get merged schema (used by Lua code).
        
        Returns:
            Merged JSON schema dict
        """
        return self.get_schema()

    def _extract_service(self, lua_def: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract and validate service definition from Lua definition.
        
        Service field is optional. If present, validates:
        - service_name: required, non-empty string
        - enable: required, boolean
        - socket_activation: optional boolean (default false)
        - user_service: optional boolean (default false)
        - restart_policy: optional string (default "always")
        - after: optional list of strings
        - wanted_by: optional list of strings
        - per_user: optional boolean (default false)
        
        Scope compatibility:
        - scope="user": service NOT allowed
        - scope="system": service optional
        - scope="both": service optional
        
        Args:
            lua_def: Lua definition dict
            
        Returns:
            Service dict with defaults filled in, or None if no service
            
        Raises:
            SchemaError: If service definition is invalid
        """
        service = lua_def.get("service")
        
        # No service field - that's valid
        if service is None:
            return None
        
        # Service not allowed with user-only scope
        if self.scope == "user":
            raise SchemaError(
                f"Service not allowed with scope='user'. "
                f"Services can only be defined for scope='system' or scope='both'."
            )
        
        # Convert Lua table to dict if needed
        service = Program._lua_to_dict(service)
        
        # Validate service dict
        if not isinstance(service, dict):
            raise SchemaError(
                f"Program '{self.name}' service must be a dict"
            )
        
        # Required fields
        if "service_name" not in service:
            raise SchemaError(
                f"Program '{self.name}' service missing required field 'service_name'"
            )
        
        service_name = service.get("service_name")
        if not service_name or not isinstance(service_name, str):
            raise SchemaError(
                f"Program '{self.name}' service_name must be a non-empty string, got {repr(service_name)}"
            )
        
        if "enable" not in service:
            raise SchemaError(
                f"Program '{self.name}' service missing required field 'enable'"
            )
        
        enable = service.get("enable")
        if not isinstance(enable, bool):
            raise SchemaError(
                f"Program '{self.name}' service.enable must be boolean, got {type(enable).__name__}"
            )
        
        # Build service dict with defaults
        extracted_service = {
            "enable": enable,
            "service_name": service_name,
            "socket_activation": service.get("socket_activation", False),
            "user_service": service.get("user_service", False),
            "restart_policy": service.get("restart_policy", "always"),
            "per_user": service.get("per_user", False),
        }
        
        # Optional list fields
        if "after" in service:
            extracted_service["after"] = service.get("after")
        
        if "wanted_by" in service:
            extracted_service["wanted_by"] = service.get("wanted_by")
        
        return extracted_service

    def get_service(self) -> Optional[Dict[str, Any]]:
        """Get service definition for this program.
        
        Returns:
            Service dict if program has a service, None otherwise
        """
        return self.service


# ===== Backward Compatibility =====

def __getattr__(name: str):
    """Lazy import ProgramRegistry from loader to avoid circular imports."""
    if name == "ProgramRegistry":
        from .loader import ProgramRegistry  # noqa: F401
        return ProgramRegistry
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
