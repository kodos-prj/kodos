"""Debian/Ubuntu specific package management adapter.

This module implements the DistroAdapter interface for Debian and Ubuntu,
providing distro-specific implementations of package management,
kernel handling, and package database operations.
"""

import re
from typing import Tuple, Any
from kod.system.distro.base import DistroAdapter
from kod.common import exec_chroot


class DebianAdapter(DistroAdapter):
    """Debian/Ubuntu specific package management."""

    @property
    def package_manager(self) -> str:
        """Debian/Ubuntu uses apt as the package manager."""
        return "apt"

    def _get_base_packages_config(self, conf: Any) -> dict:
        """Get Debian-specific base packages.

        Returns the standard Debian base package set. The kernel package
        defaults to linux-image-amd64 but can be overridden by config.

        Args:
            conf: Configuration object

        Returns:
            dict: {"kernel": "linux-image-amd64", "base": [...]}
        """
        if conf.boot and conf.boot.kernel and conf.boot.kernel.package:
            kernel_package = conf.boot.kernel.package
        else:
            kernel_package = "linux-image-amd64"

        return {
            "kernel": kernel_package,
            "base": [
                "btrfs-progs",
                "systemd-boot",
                "locales",
                "sudo",
                "schroot",
                "whois",
                "dracut",
                "git",
            ],
        }

    def _install_command(self, base_pkgs: dict, mount_point: str) -> str:
        """Generate apt-get install command for Debian.

        Uses debootstrap to initialize the chroot, then apt-get to install
        additional packages.

        Args:
            base_pkgs: Dictionary with "kernel" and "base" keys
            mount_point: Path where packages will be installed

        Returns:
            str: Complete install command
        """
        packages_to_install = [base_pkgs["kernel"]] + base_pkgs["base"]
        packages = " ".join(packages_to_install)
        return f"bash -c 'yes | DEBIAN_FRONTEND=noninteractive apt-get install -y {packages}'"

    def _query_kernel_file(self, mount_point: str, package: str) -> str:
        """Query Debian package manager for kernel file location.

        Uses apt-cache depends to find the actual kernel metapackage that
        provides the vmlinuz binary.

        Args:
            mount_point: Chroot mount point
            package: Kernel package name (e.g., "linux-image-amd64")

        Returns:
            str: Raw output from apt-cache depends
        """
        output = exec_chroot(
            f"apt-cache depends {package} | grep Depends",
            mount_point=mount_point,
            get_output=True
        )
        return output

    def _parse_kernel_file(self, output: str) -> Tuple[str, str]:
        """Parse kernel file from apt-cache depends output.

        Format: "  Depends: linux-image-6.10.10"
        Extracts the package name and derives version from the package name.

        Args:
            output: Raw apt-cache depends output

        Returns:
            Tuple[str, str]: (kernel_package_name, kernel_version)

        Raises:
            RuntimeError: If output format is invalid
        """
        # Validate output before parsing
        if not output or not output.strip():
            raise RuntimeError(f"Invalid dependency output: {output}")

        # Format: "  Depends: package-name"
        if ":" not in output:
            raise RuntimeError(f"Invalid dependency format (missing colon): {output}")

        # Extract package name after colon
        kernel_file = output.split(":")[1].strip()

        # Validate kernel package name exists
        if not kernel_file or kernel_file.isspace():
            raise RuntimeError(f"Could not extract kernel file from dependencies: {output}")

        # Extract kernel version from package name (e.g., "linux-image-6.10.10" -> "6.10.10")
        kver = kernel_file.split("-", 2)[-1]

        # Validate kernel version exists
        if not kver or kver.isspace():
            raise RuntimeError(f"Could not extract kernel version from package name: {kernel_file}")

        return kernel_file, kver

    def _query_package_db_refresh(self, mount_point: str, new_generation: bool) -> str:
        """Generate Debian package database refresh command.

        Uses apt-get update to refresh the package database.

        Args:
            mount_point: Chroot mount point
            new_generation: If True, refresh inside chroot; else outside (unused for Debian)

        Returns:
            str: apt-get update command
        """
        return "apt-get update"

    def _query_kernel_version(self, current_kernel: str, mount_point: str) -> str:
        """Query Debian for installed kernel version.

        Uses apt-cache madison to query available kernel version.

        Args:
            current_kernel: Kernel package name
            mount_point: Chroot mount point

        Returns:
            str: Output of "apt-cache madison <kernel>"
        """
        output = exec_chroot(
            f"apt-cache madison {current_kernel}",
            mount_point=mount_point,
            get_output=True
        )
        return output

    def _parse_kernel_version(self, output: str) -> str:
        """Parse kernel version from apt-cache madison output.

        Format: "package-name | version | archive/dist source"
        Extracts the version (second column).

        Args:
            output: Raw apt-cache madison output

        Returns:
            str: Kernel version string

        Raises:
            RuntimeError: If output format is invalid
        """
        # Validate output format before splitting
        split_output = output.split("|")
        if len(split_output) < 2:
            raise RuntimeError(f"Invalid kernel version output: {output}")

        new_kernel_ver = split_output[1].strip()

        # Validate kernel version format before parsing
        if not new_kernel_ver or new_kernel_ver.isspace():
            raise RuntimeError(f"Invalid kernel version: {new_kernel_ver}")

        return new_kernel_ver

    def _query_installed_packages(self, mount_point: str) -> str:
        """Query Debian for list of all installed packages.

        Uses dpkg -l to list all installed packages with versions.

        Args:
            mount_point: Chroot mount point

        Returns:
            str: Output of "dpkg -l"
        """
        output = exec_chroot(
            "dpkg -l",
            mount_point=mount_point,
            get_output=True
        )
        return output

    def _parse_installed_packages(self, output: str) -> dict:
        """Parse installed package list from dpkg -l output.

        Format: Lines starting with "ii" followed by tab-separated fields.
        "ii  package-name  version  arch  description"

        Args:
            output: Raw dpkg -l output

        Returns:
            dict: {package_name: version, ...}

        Raises:
            RuntimeError: If parsing fails
        """
        packages = {}
        for line in output.split("\n"):
            # dpkg -l output has format: "ii  package-name  version  arch  description"
            # Lines start with status flags (ii = installed ok)
            if line.startswith("ii"):
                # Split by whitespace to extract fields
                parts = re.split(r"\s+", line.strip())
                # Validate we have at least status, name, and version
                if len(parts) >= 3:
                    package_name = parts[1]
                    version = parts[2]
                    # Skip packages with invalid names or versions
                    if package_name and version and not package_name.isspace():
                        packages[package_name] = version
        return packages
