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
    - Compiles programs section into intermediate format
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
    
    # Phase 3: Compile programs section if present
    if "programs" in result:
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
    
    For each program in the programs section:
    1. Load the program via PluginLoader
    2. Validate options against program schema
    3. Generate config via program.generate_config()
    4. Store Program object and generated config
    
    Result structure:
    {
        "programs": {
            "git": {
                "program": <Program object>,
                "options": {"user_name": "Alice", ...},
                "config": "git config --global user.name 'Alice'...",
            },
            ...
        },
        ...
    }
    
    Args:
        config: Config with programs section
        
    Returns:
        Compiled config with programs dict containing Program objects and generated configs
    """
    from kod.registry.loader import PluginLoader
    
    loader = PluginLoader()
    compiled_programs = {}
    
    for program_name, program_options in config["programs"].items():
        # Load program (should already be validated by validator)
        program = loader.load_program(program_name)
        
        # Generate config from options
        generated_config = program.generate_config(program_options)
        
        # Store in compiled format
        compiled_programs[program_name] = {
            "program": program,
            "options": program_options,
            "config": generated_config,
        }
    
    # Replace programs section with compiled version
    config["programs"] = compiled_programs
    
    return config

