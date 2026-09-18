"""Base class for distro-specific package management.

This module provides a Strategy Pattern implementation for distro adaptation,
consolidating common logic once and delegating distro-specific operations
to subclass overrides.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Any, Dict
import json
from kod.common import exec, exec_chroot


class DistroAdapter(ABC):
    """Base class for distro-specific package management.

    This adapter consolidates common package management logic that is shared
    across all distro implementations. Subclasses override only the distro-specific
    methods (parsing, command generation) while inheriting all common algorithms.

    Common logic patterns:
    - Public methods implement the algorithm once (common across all distros)
    - Query methods (_query_*) run distro-specific commands
    - Parse methods (_parse_*) parse distro-specific output formats
    - Override methods are abstract; subclasses provide implementations

    Attributes inherited by subclasses:
        All methods; subclasses add no new state.
    """

    # ========== Abstract Properties (must be overridden) ==========

    @property
    @abstractmethod
    def package_manager(self) -> str:
        """Return the package manager name (e.g., 'pacman', 'apt').

        Used in error messages and logging for distro identification.

        Returns:
            str: Package manager command name
        """
        pass

    # ========== Abstract Override Methods (distro-specific implementations) ==========

    @abstractmethod
    def _get_base_packages_config(self, conf: Any) -> dict:
        """Get distro-specific base packages configuration.

        Args:
            conf: The configuration object from KodOS config file

        Returns:
            dict: Dictionary with 'kernel' and 'base' keys, e.g.:
                  {'kernel': 'linux', 'base': ['base', 'base-devel', ...]}
        """
        pass

    @abstractmethod
    def _install_command(self, base_pkgs: dict, mount_point: str) -> str:
        """Generate distro-specific package install command.

        Args:
            base_pkgs: Dictionary with 'kernel' and 'base' package lists
            mount_point: Path where packages will be installed

        Returns:
            str: Complete shell command for package installation
        """
        pass

    @abstractmethod
    def _query_kernel_file(self, mount_point: str, package: str) -> str:
        """Query distro package manager for kernel file location.

        Args:
            mount_point: Chroot mount point to query
            package: Kernel package name to query

        Returns:
            str: Raw output from package manager query
        """
        pass

    @abstractmethod
    def _parse_kernel_file(self, output: str) -> Tuple[str, str]:
        """Parse kernel file path from distro-specific query output.

        Args:
            output: Raw output from _query_kernel_file()

        Returns:
            Tuple[str, str]: (kernel_file_path, kernel_version)

        Raises:
            RuntimeError: If output format is invalid
        """
        pass

    @abstractmethod
    def _query_package_db_refresh(self, mount_point: str, new_generation: bool) -> str:
        """Generate distro-specific package database refresh command.

        Args:
            mount_point: Chroot mount point to refresh
            new_generation: If True, refresh inside chroot; else outside

        Returns:
            str: Shell command to refresh package database
        """
        pass

    @abstractmethod
    def _query_kernel_version(self, current_kernel: str, mount_point: str) -> str:
        """Query distro package manager for kernel version.

        Args:
            current_kernel: Kernel package name to query
            mount_point: Chroot mount point to query

        Returns:
            str: Raw output from package manager query
        """
        pass

    @abstractmethod
    def _parse_kernel_version(self, output: str) -> str:
        """Parse kernel version from distro-specific query output.

        Args:
            output: Raw output from _query_kernel_version()

        Returns:
            str: Kernel version string

        Raises:
            RuntimeError: If output format is invalid
        """
        pass

    @abstractmethod
    def _query_installed_packages(self, mount_point: str) -> str:
        """Query distro package manager for list of installed packages.

        Args:
            mount_point: Chroot mount point to query

        Returns:
            str: Raw output from package manager (e.g., "dpkg -l" or "pacman -Q")
        """
        pass

    @abstractmethod
    def _parse_installed_packages(self, output: str) -> dict:
        """Parse installed package list from distro-specific format.

        Args:
            output: Raw output from _query_installed_packages()

        Returns:
            dict: Dictionary mapping package names to versions
                  e.g., {'linux': '6.10.10', 'base': '2.0', ...}
        """
        pass

    # ========== Public Methods (common logic - implemented once) ==========

    def get_base_packages(self, conf: Any) -> Dict[str, Any]:
        """Get the base packages to install for the given configuration.

        This method determines the right packages for the distro and allows
        the config to override the kernel package if specified.

        The function reads base packages from distro-specific config via
        _get_base_packages_config(), then optionally overrides the kernel
        package from conf.boot.kernel.package if present.

        Args:
            conf: The configuration object

        Returns:
            dict: Dictionary with 'kernel' and 'base' keys containing
                  packages to install
        """
        # Get distro-specific base packages
        packages = self._get_base_packages_config(conf)

        # Allow config to override kernel package
        if conf.boot and conf.boot.kernel and conf.boot.kernel.package:
            packages["kernel"] = conf.boot.kernel.package

        return packages

    def install_essentials_pkgs(self, base_pkgs: dict, mount_point: str) -> None:
        """Install essential packages onto the specified mount point.

        This method executes the distro-specific install command generated
        by _install_command(). It uses exec() to run the command.

        Args:
            base_pkgs: Dictionary with 'kernel' and 'base' package keys
            mount_point: Path where packages will be installed

        Raises:
            OSError: If installation command fails
        """
        cmd = self._install_command(base_pkgs, mount_point)
        exec(cmd)

    def get_kernel_file(self, mount_point: str, package: str = "linux") -> Tuple[str, str]:
        """Retrieve the kernel file path and version from the mount point.

        This method queries the distro package manager for kernel file location,
        validates the output, and parses it into (path, version).

        Args:
            mount_point: The chroot mount point to query
            package: Kernel package name. Defaults to "linux"

        Returns:
            Tuple[str, str]: (kernel_file_path, kernel_version)

        Raises:
            RuntimeError: If no kernel found or output format invalid
        """
        # Query distro package manager
        output = self._query_kernel_file(mount_point, package)

        # Validate output
        if not output or not output.strip():
            raise RuntimeError(f"No kernel file found for package '{package}'. Output: {output}")

        # Parse and return
        return self._parse_kernel_file(output)

    def get_list_of_dependencies(self, pkg: str):
        """Get the list of dependencies of a given package.

        This method uses distro-specific commands to determine if a package
        is a group, and if so returns group members. Otherwise returns the
        package dependencies or the package itself.

        Args:
            pkg: The package name to get dependencies for

        Returns:
            list: A list of packages that the given package depends on
        """
        # This is distro-specific but has identical logic in arch.py.
        # We keep the actual implementation in subclasses for now
        # since the query commands (pacman -Sgq vs apt-cache) differ.
        # Subclasses will override this or we'll extract common logic later.
        raise NotImplementedError(
            "Subclasses must implement get_list_of_dependencies() "
            "or this method will be consolidated in base when distro command patterns are unified"
        )

    def proc_repos(self, conf, current_repos=None, update=False, mount_point="/mnt") -> Tuple[dict, list]:
        """Process the repository configuration from the given config.

        This method reads the repository configuration, preserves existing
        repos when not updating, and extracts commands from new repos.

        The common logic:
        1. Return empty if no repos configured
        2. Preserve current repos when update=False
        3. Extract 'commands' field from each repo config
        4. Skip repos with missing 'commands' field
        5. Write repos.json if anything changed

        Distro-specific logic (handled by subclasses):
        - Package installation (depends on pkg manager)
        - Flatpak initialization (Arch-specific)
        - AUR helper builds (Arch-specific)
        - Build dependency installation (Debian-specific)

        Args:
            conf: Configuration object with .repos attribute
            current_repos: Current repository configuration (default None)
            update: If True, refresh all repos; else preserve existing (default False)
            mount_point: Chroot mount point (default "/mnt")

        Returns:
            Tuple[dict, list]: (repos_dict, packages_list)
                - repos_dict: Repository configurations with commands
                - packages_list: List of installed packages
        """
        repos_conf = conf.repos
        repos = {}
        packages = []

        # No repos configured
        if repos_conf is None:
            return repos, packages

        # Process each repository
        for repo, repo_desc in repos_conf.items():
            # Preserve current repo if not updating
            if current_repos and repo in current_repos and not update:
                repos[repo] = current_repos[repo]
                continue

            # Extract commands (required field)
            if "commands" not in repo_desc:
                print(f"Warning: Repository '{repo}' missing 'commands' field, skipping")
                continue

            # Initialize and populate new repo entry
            repos[repo] = {}
            for action, cmd in repo_desc["commands"].items():
                repos[repo][action] = cmd

        # Write updated repos to file if anything changed
        if repos or update:
            exec(f"mkdir -p {mount_point}/var/kod")
            with open(f"{mount_point}/var/kod/repos.json", "w") as f:
                f.write(json.dumps(repos, indent=2))

        return repos, packages

    def refresh_package_db(self, mount_point: str, new_generation: bool) -> None:
        """Refresh the package database.

        This method executes distro-specific package database refresh command.
        The command runs in chroot if new_generation=True, outside chroot otherwise.

        Args:
            mount_point: The chroot mount point
            new_generation: If True, refresh inside chroot; else outside chroot
        """
        # Generate distro-specific refresh command
        cmd = self._query_package_db_refresh(mount_point, new_generation)

        # Execute in chroot or outside
        if new_generation:
            exec_chroot(cmd, mount_point=mount_point)
        else:
            exec(cmd)

    def kernel_update_required(
        self,
        current_kernel: str,
        next_kernel: str,
        current_installed_packages: dict,
        mount_point: str
    ) -> bool:
        """Check if a kernel update is required.

        This method compares the current kernel package/version with the next one.
        It returns True if:
        1. Package name changed (current_kernel != next_kernel), OR
        2. No current packages installed (fresh install), OR
        3. Kernel version changed (in installed packages vs. available version)

        Args:
            current_kernel: Current kernel package name
            next_kernel: Desired kernel package name
            current_installed_packages: Dict of {package: version} currently installed
            mount_point: Chroot mount point

        Returns:
            bool: True if update required, False if no update needed

        Raises:
            RuntimeError: If kernel version format is invalid
        """
        # Package name changed
        if current_kernel != next_kernel:
            return True

        # Fresh install (no current packages)
        if not current_installed_packages or current_kernel not in current_installed_packages:
            return True

        # Query available kernel version
        output = self._query_kernel_version(current_kernel, mount_point)
        current_kernel_ver = current_installed_packages[current_kernel]

        # Parse new kernel version
        new_kernel_ver = self._parse_kernel_version(output)

        # Validate kernel version format
        split_kver = new_kernel_ver.split(".")
        if len(split_kver) < 2 or not split_kver[0]:
            raise RuntimeError(f"Could not parse kernel version from: {new_kernel_ver}")

        # Compare versions
        return current_kernel_ver != new_kernel_ver

    def generate_package_lock(self, mount_point: str, state_path: str) -> None:
        """Generate a file containing the list of installed packages and their versions.

        This method queries the distro package manager for installed packages,
        parses the output, and writes to state_path/packages.lock in format:
            package_name version
            package_name version
            ...

        Args:
            mount_point: The chroot mount point to query
            state_path: Path to directory where packages.lock will be written

        Raises:
            RuntimeError: If parsing or file write fails
        """
        # Query installed packages from chroot
        output = self._query_installed_packages(mount_point)

        # Parse distro-specific output format
        packages = self._parse_installed_packages(output)

        # Write to lock file
        with open(f"{state_path}/packages.lock", "w") as f:
            for pkg, ver in packages.items():
                f.write(f"{pkg} {ver}\n")
