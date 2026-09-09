"""Abstract Distribution base class.

Defines the interface that arch.py, debian.py, and other distributions
must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class Distribution(ABC):
    """Abstract interface for distribution-specific operations."""

    @abstractmethod
    def get_base_packages(self) -> List[str]:
        """Return list of base packages to install."""
        pass

    @abstractmethod
    def install_essentials(self, mount_point: str, packages: List[str]) -> None:
        """Install essential packages into a chroot."""
        pass

    @abstractmethod
    def manage_services(self, action: str, services: List[str], mount_point: str) -> None:
        """Enable, disable, or check services (systemctl, rcctl, etc)."""
        pass

    @abstractmethod
    def get_package_manager(self) -> str:
        """Return the package manager command (pacman, apt, etc)."""
        pass
