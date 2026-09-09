"""Configuration compilation and dependency resolution (Phase 1).

Takes a validated config and compiles it into an executable plan.
Resolves dependencies (e.g., GNOME -> gdm, services -> packages).

Key components:
- compile_config(): Main entry point
- resolve_dependencies(): Resolve implied dependencies

Example:
    >>> from kod.config.compiler import compile_config
    >>> compiled = compile_config(config)
    >>> # compiled has all implicit dependencies resolved
"""

from typing import Any, Dict


def compile_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Compile config by resolving all dependencies.
    
    This handles implicit dependencies:
    - GNOME enabled → display_manager = gdm
    - Plasma enabled → display_manager = sddm
    - etc.
    
    Args:
        config: Loaded and validated config dict
    
    Returns:
        Compiled config with all dependencies resolved
    
    ponytail: simple recursive walk + pattern matching.
              Add more rules as new dependency patterns emerge.
    """
    # Make a deep copy to avoid mutating the original
    result = _deep_copy(config)
    
    # Apply dependency rules
    result = _apply_desktop_manager_dependencies(result)
    
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
