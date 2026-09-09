"""Abstract Distribution base class.

Defines the interface that arch.py, debian.py, and other distributions
must implement.

All distributions (Arch, Debian, etc) must implement this interface to ensure
consistent behavior across the kod system installation and configuration process.

Example:
    >>> from kod.distributions import Distribution
    >>> from kod.arch import ArchDistribution
    >>> dist = ArchDistribution()
    >>> packages = dist.get_base_packages()
    >>> dist.manage_services("enable", ["sshd"], "/mnt")
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class Distribution(ABC):
    """Abstract interface for distribution-specific operations.
    
    Each concrete distribution implementation must provide methods for:
    - Getting base packages to install
    - Installing packages into a chroot environment
    - Managing services (enable, disable, check)
    - Identifying the package manager command
    """

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
