"""Distribution-specific system management.

This package contains distribution-specific implementations for package management,
system configuration, and initialization. Currently supports Arch Linux and Debian/Ubuntu.

Public API:
- get_distro_module(distro_name): Legacy factory (returns adapter instance)
- get_distro_adapter(distro_name): New factory (returns adapter instance)
- DistroAdapter: Base class for all distro adapters
- ArchAdapter: Arch Linux adapter
- DebianAdapter: Debian/Ubuntu adapter
"""

from .factory import get_distro_module, get_distro_adapter  # noqa: F401
from .base import DistroAdapter  # noqa: F401
from .adapters import ArchAdapter, DebianAdapter  # noqa: F401

__all__ = [
    "get_distro_module",      # Legacy API (backward compat)
    "get_distro_adapter",     # New API (recommended)
    "DistroAdapter",          # Base class
    "ArchAdapter",            # Arch adapter
    "DebianAdapter",          # Debian adapter
]

