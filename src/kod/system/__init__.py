"""Kodos system operations (Phase 2).

This module provides atomic system-level operations:
- packages: Package management (install, update, cache)
- services: Service enablement/disablement
- boot: Bootloader and kernel management
- filesystem: Partitions, mounts, fstab
- users: User and group management
"""

from kod.system import packages, services

__all__ = [
    "packages",
    "services",
    # Add other modules as they're implemented
]
