"""Kodos system operations (Phase 2).

This module provides atomic system-level operations:
- packages: Package management (install, update, cache)
- services: Service enablement/disablement
- boot: Bootloader and kernel management
- filesystem: Partitions, mounts, fstab
- users: User and group management

Note: Submodules are NOT imported here to avoid circular imports during
kod.core initialization. Import them directly as needed:
    from kod.system import packages
    from kod.system import services
    etc.
"""

__all__ = [
    "packages",
    "services",
    "boot",
    "filesystem",
    "users",
    # Add other modules as they're implemented
]
