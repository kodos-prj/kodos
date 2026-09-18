"""Distro-specific adapter implementations."""

from kod.system.distro.adapters.arch import ArchAdapter
from kod.system.distro.adapters.debian import DebianAdapter

__all__ = ["ArchAdapter", "DebianAdapter"]
