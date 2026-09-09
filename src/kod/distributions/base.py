"""Distribution abstraction (Phase 2).

Base class for distribution-specific operations.
Enables clean separation of distro logic (Arch vs Debian vs others).

Key components:
- Distribution: Base class defining the interface
- ArchDistribution: Arch Linux implementation
- DebianDistribution: Debian/Ubuntu implementation

Each Distribution implements:
- install_packages()
- remove_packages()
- update_packages()
- execute_in_root()
- Distro-specific commands and options

Example:
    >>> distro = Distribution.get_distro(detected_distro)
    >>> distro.install_packages(["git", "vim"])
    >>> distro.install_packages_to_root(["linux"], "/mnt/newroot")
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class Distribution(ABC):
    """Base class for distribution operations."""

    @abstractmethod
    def install_packages(self, packages: List[str]) -> None:
        """Install packages on current system.

        Args:
            packages: List of package names to install

        Raises:
            PackageInstallError: If installation fails
        """
        pass

    @abstractmethod
    def remove_packages(self, packages: List[str]) -> None:
        """Remove packages from current system.

        Args:
            packages: List of package names to remove

        Raises:
            PackageError: If removal fails
        """
        pass

    @abstractmethod
    def update_packages(self, packages: List[str]) -> None:
        """Update packages on current system.

        Args:
            packages: List of package names to update

        Raises:
            PackageError: If update fails
        """
        pass

    @abstractmethod
    def install_to_root(self, packages: List[str], root_path: str) -> None:
        """Install packages to root filesystem (chroot).

        Args:
            packages: List of package names to install
            root_path: Path to root filesystem

        Raises:
            PackageInstallError: If installation fails
            OSError: If root_path is invalid
        """
        pass

    @abstractmethod
    def get_package_manager(self) -> str:
        """Get name of package manager (pacman, apt, etc.)."""
        pass

    @staticmethod
    def get_distro(distro_name: str) -> "Distribution":
        """Factory method to get distribution instance.

        Args:
            distro_name: Name of distribution (arch, debian, ubuntu, etc.)

        Returns:
            Distribution instance

        Raises:
            ValueError: If distro is not supported
        """
        # TODO (Phase 2): Implement detection and instantiation
        pass


class ArchDistribution(Distribution):
    """Arch Linux distribution implementation."""

    # TODO (Phase 2): Implement arch-specific methods
    pass


class DebianDistribution(Distribution):
    """Debian/Ubuntu distribution implementation."""

    # TODO (Phase 2): Implement debian-specific methods
    pass
