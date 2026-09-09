"""Distribution-specific implementations (Phase 2).

Provides abstract Distribution base class and concrete implementations
for Arch, Debian, etc.
"""

from kod.distributions.base import Distribution

__all__ = ["Distribution"]
