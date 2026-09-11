"""Lifecycle hook collection and firing for step-based execution.

Spec: docs/superpowers/specs/2026-09-10-kod-planner-hooks-buildcache-design.md §7.

Fixed hook names: pre:<kind> / post:<kind>, kind ∈ {package, service, program, user}.
Registration: optional `hooks` table in program/plugin module.
Semantics: pre errors abort; post errors log and continue.
"""

from typing import Any, Dict, List, Callable, Optional


class ValidationError(Exception):
    """Invalid hook configuration."""
    pass


# Spec §7: fixed set of hook names
VALID_HOOKS = {
    "pre:package", "post:package",
    "pre:service", "post:service",
    "pre:program", "post:program",
    "pre:user", "post:user",
}


def collect_hooks(programs: Dict[str, Any]) -> Dict[str, List[Callable]]:
    """Extract and validate lifecycle hooks from program definitions.
    
    Args:
        programs: Dict of program name → definition (Lua table converted to dict).
                  Each program may have an optional `hooks` field with
                  event → callable mappings.
    
    Returns:
        Dict mapping hook event name (e.g., "post:service") to list of callables.
        Empty dict if no hooks registered.
    
    Raises:
        ValidationError: If any hook name is not in VALID_HOOKS.
    """
    hooks_map: Dict[str, List[Callable]] = {}
    
    for prog_name, prog_def in programs.items():
        if not isinstance(prog_def, dict):
            continue
        
        prog_hooks = prog_def.get("hooks")
        if not prog_hooks:
            continue
        
        if not isinstance(prog_hooks, dict):
            raise ValidationError(f"Program '{prog_name}' hooks field must be a dict, got {type(prog_hooks)}")
        
        for hook_name, hook_fn in prog_hooks.items():
            # Validate hook name
            if hook_name not in VALID_HOOKS:
                raise ValidationError(
                    f"Program '{prog_name}' registers unknown hook '{hook_name}'. "
                    f"Valid names: {sorted(VALID_HOOKS)}"
                )
            
            # Collect
            if hook_name not in hooks_map:
                hooks_map[hook_name] = []
            hooks_map[hook_name].append(hook_fn)
    
    return hooks_map
