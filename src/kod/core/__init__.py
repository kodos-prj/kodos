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

__all__ = [
    "configure_system",
    "create_next_generation",
    "get_generation",
    "get_max_generation",
    # Add user_config workflow as implemented
]
