"""Arch Linux specific package management adapter.

This module implements the DistroAdapter interface for Arch Linux,
providing distro-specific implementations of package management,
kernel handling, and package database operations.
"""

from typing import Tuple, Any
from kod.system.distro.base import DistroAdapter
from kod.common import exec_chroot


class ArchAdapter(DistroAdapter):
    """Arch Linux specific package management."""

    @property
    def package_manager(self) -> str:
        """Arch uses pacman as the package manager."""
        return "pacman"

    def _get_base_packages_config(self, conf: Any) -> dict:
        """Get Arch-specific base packages.

        Detects CPU microcode (AMD or Intel) and returns the appropriate
        base package set for Arch Linux.

        Args:
            conf: Configuration object

        Returns:
            dict: {"kernel": "linux", "base": [...]}
        """
        # CPU microcode detection
        microcode = "intel-ucode"
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "AuthenticAMD" in line:
                        microcode = "amd-ucode"
                        break
                    if "GenuineIntel" in line:
                        microcode = "intel-ucode"
                        break
        except Exception:
            # Default to intel-ucode on error
            microcode = "intel-ucode"

        return {
            "kernel": "linux",
            "base": [
                "base",
                "base-devel",
                "debugedit",
                "fakeroot",
                microcode,
                "btrfs-progs",
                "linux-firmware",
                "bash-completion",
                "mlocate",
                "sudo",
                "schroot",
                "whois",
                "dracut",
                "git",
                "arch-install-scripts",
            ],
        }

    def _install_command(self, base_pkgs: dict, mount_point: str) -> str:
        """Generate pacstrap install command for Arch.

        Args:
            base_pkgs: Dictionary with "kernel" and "base" keys
            mount_point: Path where packages will be installed

        Returns:
            str: Complete pacstrap command
        """
        kernel = base_pkgs["kernel"]
        base = base_pkgs["base"]
        return f"pacstrap -K {mount_point} {kernel} {' '.join(base)}"

    def _query_kernel_file(self, mount_point: str, package: str) -> str:
        """Query Arch package database for kernel file location.

        Uses pacman -Ql to list files in the kernel package.

        Args:
            mount_point: Chroot mount point
            package: Kernel package name (e.g., "linux")

        Returns:
            str: Raw output from pacman -Ql grep vmlinuz
        """
        output = exec_chroot(
            f"bash -c 'pacman -Ql {package} | grep vmlinuz'",
            mount_point=mount_point,
            get_output=True
        )
        return output

    def _parse_kernel_file(self, output: str) -> Tuple[str, str]:
        """Parse kernel file path from pacman -Ql output.

        Format: "arch package-name /usr/lib/modules/VERSION/vmlinuz"
        Extracts the path and derives version from the directory name.

        Args:
            output: Raw pacman -Ql output

        Returns:
            Tuple[str, str]: (kernel_file_path, kernel_version)

        Raises:
            RuntimeError: If output format is invalid
        """
        # Extract the kernel file path (last column)
        kernel_file = output.split(" ")[-1].strip()

        # Validate kernel path format
        if not kernel_file or "/" not in kernel_file:
            raise RuntimeError(f"Invalid kernel file path: {kernel_file}")

        # Extract kernel version from /usr/lib/modules/VERSION/vmlinuz
        # The version is the directory name before /vmlinuz
        kver = kernel_file.split("/")[-2]

        # Validate kernel version exists
        if not kver or kver.isspace():
            raise RuntimeError(f"Could not extract kernel version from path: {kernel_file}")

        return kernel_file, kver

    def _query_package_db_refresh(self, mount_point: str, new_generation: bool) -> str:
        """Generate Arch package database refresh command.

        Uses pacman -Sy to sync the package database.

        Args:
            mount_point: Chroot mount point
            new_generation: Ignored for Arch (same command either way)

        Returns:
            str: pacman -Sy command
        """
        return "pacman -Sy --noconfirm"

    def _query_kernel_version(self, current_kernel: str, mount_point: str) -> str:
        """Query Arch for installed kernel version.

        Uses pacman -Q to query installed package version.

        Args:
            current_kernel: Kernel package name
            mount_point: Chroot mount point

        Returns:
            str: Output of "pacman -Q linux" (format: "linux VERSION")
        """
        output = exec_chroot(
            f"pacman -Q {current_kernel}",
            mount_point=mount_point,
            get_output=True
        )
        return output

    def _parse_kernel_version(self, output: str) -> str:
        """Parse kernel version from pacman -Q output.

        Format: "linux 6.10.10-arch1-1"
        Extracts the version (second column).

        Args:
            output: Raw pacman -Q output

        Returns:
            str: Kernel version string

        Raises:
            RuntimeError: If output format is invalid
        """
        # Parse "package version" format
        split_output = output.strip().split()
        if len(split_output) < 2:
            raise RuntimeError(f"Invalid kernel version output: {output}")

        kver = split_output[1]

        # Validate kernel version format
        if not kver or kver.isspace():
            raise RuntimeError(f"Invalid kernel version: {kver}")

        return kver

    def _query_installed_packages(self, mount_point: str) -> str:
        """Query Arch for list of all installed packages.

        Uses pacman -Q to list all installed packages with versions.

        Args:
            mount_point: Chroot mount point

        Returns:
            str: Output of "pacman -Q" (format: "package version" per line)
        """
        output = exec_chroot(
            "pacman -Q --noconfirm",
            mount_point=mount_point,
            get_output=True
        )
        return output

    def _parse_installed_packages(self, output: str) -> dict:
        """Parse installed package list from pacman -Q output.

        Format: Lines of "package version"
        Returns dictionary mapping package names to versions.

        Args:
            output: Raw pacman -Q output

        Returns:
            dict: {package_name: version, ...}
        """
        packages = {}
        for line in output.split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    packages[parts[0]] = parts[1]
        return packages
