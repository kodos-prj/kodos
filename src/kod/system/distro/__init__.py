"""Distribution-specific system management.

This package contains distribution-specific implementations for package management,
system configuration, and initialization. Currently supports Arch Linux with Debian
support available.
"""

from .factory import get_distro_module  # noqa: F401

__all__ = ["get_distro_module"]

