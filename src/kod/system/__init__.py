"""Kodos system operations (Phase 2).

This module provides atomic system-level operations:
- packages: Package management (install, update, cache)
- services: Service enablement/disablement
- boot: Bootloader and kernel management
- filesystem: Partitions, mounts, fstab
- users: User and group management
"""

from kod.system import packages, services, boot, filesystem

__all__ = [
    "packages",
    "services",
    "boot",
    "filesystem",
    # Add other modules as they're implemented
]
