"""Kodos orchestration workflows (Phase 2).

This module provides high-level workflows for system operations:
- Install: bootstrap system from scratch
- Rebuild: create snapshots and apply updates
- User Config: manage user dotfiles and services

For backward compatibility, all old core.py functions are re-exported here.
"""

# Re-export everything from the legacy _core module for backward compatibility
from kod._core import *  # noqa: F401, F403

# Import and re-export workflow entry points
from kod.core.install import configure_system
from kod.core.rebuild import (
    create_next_generation,
    get_generation,
    get_max_generation,
)
from kod.core.user_config import (
    configure_user_dotfiles,
    configure_user_scripts,
)

# Re-export refactored functions from kod.system modules (Phase 2b)
# These are now implemented in kod.system.services but re-exported for backward compat
def __getattr__(name: str):
    """Lazy import of refactored functions from kod.system modules."""
    if name in {
        'enable_services',
        'disable_services',
        'enable_user_services',
        'get_services_to_enable',
        'proc_desktop_services',
        'proc_services',
        'proc_services_to_enable',
    }:
        from kod.system import services as services_module
        return getattr(services_module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "configure_system",
    "create_next_generation",
    "get_generation",
    "get_max_generation",
    "configure_user_dotfiles",
    "configure_user_scripts",
    # Phase 2b re-exports from kod.system.services
    "enable_services",
    "disable_services",
    "enable_user_services",
    "get_services_to_enable",
    "proc_desktop_services",
    "proc_services",
    "proc_services_to_enable",
]
