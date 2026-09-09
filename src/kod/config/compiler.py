"""Configuration compilation and dependency resolution (Phase 1 + Phase 3).

Takes a validated config and compiles it into an executable plan.
Resolves dependencies (e.g., GNOME -> gdm, services -> packages).

Phase 3 additions:
- Compiles programs section into intermediate format
- Loads and validates programs
- Stores Program objects for install workflow

Key components:
- compile_config(): Main entry point
- resolve_dependencies(): Resolve implied dependencies
- _compile_programs(): Phase 3 program compilation

Example:
    >>> from kod.config.compiler import compile_config
    >>> compiled = compile_config(config)
    >>> # compiled has all implicit dependencies resolved + programs compiled
"""

from typing import Any, Dict


def compile_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Compile config by resolving all dependencies and compiling programs.
    
    This handles implicit dependencies:
    - GNOME enabled → display_manager = gdm
    - Plasma enabled → display_manager = sddm
    - etc.
    
    Phase 3 additions:
    - Compiles programs section into intermediate format (system-level)
    - Compiles user-level programs for each user
    - Merges system and user programs (user overrides system)
    - Loads and validates each program
    - Stores Program objects in compiled.programs dict
    
    Args:
        config: Loaded and validated config dict
    
    Returns:
        Compiled config with all dependencies resolved and programs compiled
    
    ponytail: simple recursive walk + pattern matching.
              Add more rules as new dependency patterns emerge.
    """
    # Make a deep copy to avoid mutating the original
    result = _deep_copy(config)
    
    # Apply dependency rules
    result = _apply_desktop_manager_dependencies(result)
    
    # Phase 3: Compile programs section (system-level + user-level)
    result = _compile_programs(result)
    
    return result


def _deep_copy(value: Any) -> Any:
    """Deep copy a nested structure."""
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_deep_copy(v) for v in value]
    else:
        return value


def _apply_desktop_manager_dependencies(config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve desktop environment → display manager dependencies.
    
    ponytail: hardcoded rules for the common cases (GNOME, Plasma, etc).
              Add more as needed.
    """
    if "desktop" not in config:
        return config
    
    desktop = config["desktop"]
    if "desktop_manager" not in desktop:
        return config
    
    managers = desktop["desktop_manager"]
    
    # GNOME → gdm
    if "gnome" in managers:
        gnome = managers["gnome"]
        if isinstance(gnome, dict) and gnome.get("enable"):
            if "display_manager" not in gnome:
                gnome["display_manager"] = "gdm"
    
    # Plasma → sddm
    if "plasma" in managers:
        plasma = managers["plasma"]
        if isinstance(plasma, dict) and plasma.get("enable"):
            if "display_manager" not in plasma:
                plasma["display_manager"] = "sddm"
    
    # Pantheon → lightdm
    if "pantheon" in managers:
        pantheon = managers["pantheon"]
        if isinstance(pantheon, dict) and pantheon.get("enable"):
            if "display_manager" not in pantheon:
                pantheon["display_manager"] = "lightdm"
    
    return config


def _compile_programs(config: Dict[str, Any]) -> Dict[str, Any]:
    """Compile programs section into intermediate format for install workflow.
    
    Handles both system-level and user-level programs with proper merging:
    
    1. System-level programs (top-level 'programs' section):
       - Loaded and compiled
       - Stored with scope="system"
    
    2. User-level programs (inside 'users.alice.programs' sections):
       - Loaded and compiled
       - If same program exists at system level, merge with user overriding
       - Stored with scope="user" and overrides_system flag
    
    Compilation order matters:
    - System-level first (provides defaults)
    - User-level second (can override system)
    
    Result structure:
    {
        "programs": {
            "git": {
                "program": <Program object>,
                "options": {"user_name": "System Default", ...},
                "config": "git config --global...",
                "scope": "system"
            },
            ...
        },
        "users": {
            "alice": {
                "programs": {
                    "git": {
                        "program": <Program object>,
                        "options": {merged: system + user override},
                        "config": "git config --global...",
                        "scope": "user",
                        "overrides_system": True
                    },
                    ...
                },
                ...
            }
        }
    }
    
    Args:
        config: Config with optional programs section and users section
        
    Returns:
        Compiled config with programs compiled at system and user levels
    """
    from kod.registry.loader import PluginLoader
    
    loader = PluginLoader()
    
    # Initialize compiled structure
    if "programs" not in config:
        config["programs"] = {}
    
    # Step 1: Compile system-level programs
    system_programs = {}
    if "programs" in config and config["programs"]:
        for program_name, program_options in config["programs"].items():
            # Load program
            program = loader.load_program(program_name)
            
            # Generate config from options
            generated_config = program.generate_config(program_options)
            
            # Extract service definition (if present)
            service = program.get_service()
            
            # Store in compiled format
            system_programs[program_name] = {
                "program": program,
                "options": program_options,
                "config": generated_config,
                "scope": "system",
                "service": service
            }
    
    # Replace programs section with compiled version
    config["programs"] = system_programs
    
    # Step 2: Compile user-level programs (if users section exists)
    if "users" in config:
        for user_name, user_config in config["users"].items():
            if "programs" in user_config and user_config["programs"]:
                user_programs = {}
                
                for program_name, program_options in user_config["programs"].items():
                    # Load program
                    program = loader.load_program(program_name)
                    
                    # Check if same program exists at system level
                    merged_options = program_options
                    overrides_system = False
                    inherited_service = None
                    
                    if program_name in system_programs:
                        # Merge: user options override system options
                        base_options = system_programs[program_name]["options"]
                        merged_options = {**base_options, **program_options}
                        overrides_system = True
                        # Inherit service from system (user cannot override service)
                        inherited_service = system_programs[program_name].get("service")
                    
                    # Generate config from merged options
                    generated_config = program.generate_config(merged_options)
                    
                    # For user-level programs, use inherited service from system if available,
                    # otherwise use program's own service (though user-scope programs shouldn't have one)
                    service = inherited_service if inherited_service is not None else program.get_service()
                    
                    # Store in compiled format
                    user_programs[program_name] = {
                        "program": program,
                        "options": merged_options,
                        "config": generated_config,
                        "scope": "user",
                        "overrides_system": overrides_system,
                        "service": service
                    }
                
                # Replace user's programs section with compiled version
                config["users"][user_name]["programs"] = user_programs
    
    return config

