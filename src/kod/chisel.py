"""Chisel specific package and system management functions.

This module provides Chisel specific implementations for package installation,
system configuration, user management, and service handling. It includes functions
for detecting hardware-specific packages and managing Chisel-specific tools.

Chisel is a cross-distribution package manager that brings Arch Linux packages
to any Linux distribution using complete dependency isolation.
"""

from kod.common import exec_chroot, exec
import json
from typing import Dict, Any, Tuple, List


def prepare_for_installation() -> None:
    """Prepare the environment for package installation using Chisel.

    Verifies that Chisel is installed and properly set up for package management.
    Chisel is assumed to be pre-installed and available in the system.
    """
    # Verify chisel is available
    result = exec("which chisel", get_output=True)
    if not result.strip():
        raise RuntimeError("Chisel is not installed or not in PATH")


# Chisel
def get_base_packages(conf: Any) -> Dict[str, Any]:
    """Get the base packages to install for the given configuration.

    The function determines the right microcode package for the CPU and
    the kernel package from the configuration. It then returns a table
    with the packages to install.

    Args:
        conf: The configuration object.

    Returns:
        A dictionary with the packages to install.
    """
    # CPU microcode
    microcode = None
    with open("/proc/cpuinfo") as f:
        while True:
            line = f.readline()
            if not line:
                break
            if "AuthenticAMD" in line:
                microcode = "amd-ucode"
                break
            if "GenuineIntel" in line:
                microcode = "intel-ucode"
                break

    if microcode is None:
        microcode = "intel-ucode"  # Default fallback

    if conf.boot and conf.boot.kernel and conf.boot.kernel.package:
        kernel_package = conf.boot.kernel.package
    else:
        kernel_package = "linux"

    # TODO: add versions to each package
    packages = {
        "kernel": kernel_package,
        "base": [
            "base",
            "base-devel",
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
        ],
    }

    # TODO: review if arch-install-scripts is needed with Chisel
    # packages["base"] += ["arch-install-scripts"]
    return packages


# Chisel
def install_essentials_pkgs(base_pkgs: Dict, mount_point: str) -> None:
    """
    Install essential packages onto the specified mount point using Chisel.

    This function uses the Chisel package manager to install a set of base
    packages including the kernel and other essential packages onto a
    given mount point. The packages to be installed are determined by
    the base_pkgs dictionary, which should contain 'kernel' and 'base'
    keys.

    Args:
        base_pkgs (Dict): A dictionary containing the packages to install,
                          with 'kernel' and 'base' keys.
        mount_point (str): The mount point where the packages will be installed.
    """
    packages_to_install = [base_pkgs["kernel"]] + base_pkgs["base"]

    # Use chisel to install packages
    # Chisel installs to /kod/store/ by default
    exec(f"sudo chisel install {' '.join(packages_to_install)}")


# Chisel
def get_kernel_file(mount_point: str, package: str = "linux") -> Tuple[str, str]:
    """
    Retrieve the kernel file path and version from the specified mount point.

    This function queries Chisel's package store to find the kernel file
    and extract its version information.

    Args:
        mount_point (str): The mount point of the chroot environment to retrieve the kernel file from.
        package (str, optional): The package name to retrieve the kernel file from. Defaults to "linux".

    Returns:
        tuple: A tuple containing the kernel file path as a string and the kernel version as a string.
    """
    # Get installed packages from chisel
    kernel_list = exec_chroot(f"chisel list | grep {package}", mount_point=mount_point, get_output=True)

    if not kernel_list.strip():
        raise RuntimeError(f"Kernel package {package} not found")

    # Parse the output to extract version and path
    # Format: package_name version
    parts = kernel_list.strip().split()
    if len(parts) >= 2:
        pkg_name = parts[0]
        kver = parts[1]
    else:
        raise RuntimeError(f"Cannot parse kernel information: {kernel_list}")

    # Construct kernel file path from Chisel store
    kernel_file = f"/kod/store/{pkg_name}/{kver}/boot/vmlinuz-{kver}"

    return kernel_file, kver


def setup_linux(kernel_package: str) -> str:
    """
    Set up the kernel by copying it to the boot partition.

    Args:
        kernel_package: The kernel package name.

    Returns:
        The kernel version string.
    """
    kernel_file, kver = get_kernel_file(mount_point="/mnt", package=kernel_package)
    exec_chroot(f"cp {kernel_file} /boot/vmlinuz-{kver}")
    return kver


# Chisel
def get_list_of_dependencies(pkg: str) -> List[str]:
    """
    Get the list of dependencies of a given package.

    This function takes a package name and returns a list of packages it depends on.
    It queries Chisel or the Arch database to determine dependencies.

    Args:
        pkg (str): The package name to get the dependencies of.

    Returns:
        list: A list of packages that the given package depends on.
    """
    # Try to get package info from chisel
    pkg_info = exec(f"chisel search {pkg}", get_output=True).strip()

    if not pkg_info:
        return [pkg]

    # For now, return the package itself as we need more robust dependency resolution
    # This would require parsing Arch database files or using chisel's internal APIs
    return [pkg]


# Chisel
def proc_repos(conf, current_repos=None, update=False, mount_point="/mnt") -> Tuple[Dict, List]:
    """
    Process the repository configuration from the given config using Chisel.

    This function reads the repository configuration from the given config and
    register information about how to build, install, or update each repository.
    The function will write the result to /var/kod/repos.json.

    Args:
        conf (dict): The configuration dictionary to read from.
        current_repos (dict): The current repository configuration.
        update (bool): If True, update the package list. Defaults to False.
        mount_point (str): The mount point where the installation is being
            performed. Defaults to "/mnt".

    Returns:
        tuple: A tuple containing the processed repository configuration and
            the list of packages that were installed.
    """
    # TODO: Add support for custom repositories and to be used during rebuild
    repos_conf = conf.repos
    repos = {}
    packages = []
    update_repos = False

    for repo, repo_desc in repos_conf.items():
        if current_repos and repo in current_repos and not update:
            repos[repo] = current_repos[repo]
            continue

        repos[repo] = {}
        for action, cmd in repo_desc["commands"].items():
            repos[repo][action] = cmd

        if "build" in repo_desc:
            build_info = repo_desc["build"]
            url = build_info["url"]
            build_cmd = build_info["build_cmd"]
            name = build_info["name"]

            exec_chroot(
                f"runuser -u kod -- /bin/bash -c 'cd && rm -rf {name} && git clone {url} {name} && cd {name} && {build_cmd}'",
                mount_point=mount_point,
            )

        if "package" in repo_desc:
            # Use chisel to install packages instead of pacman
            exec_chroot(
                f"sudo chisel install {repo_desc['package']}",
                mount_point=mount_point,
            )
            packages += [repo_desc["package"]]
        update_repos = True

    if update_repos:
        exec(f"mkdir -p {mount_point}/var/kod")
        with open(f"{mount_point}/var/kod/repos.json", "w") as f:
            f.write(json.dumps(repos, indent=2))

    return repos, packages


# Chisel
def refresh_package_db(mount_point: str, new_generation: bool) -> None:
    """
    Refresh the package database using Chisel.

    This function runs chisel sync to refresh the Arch package database.
    If new_generation is True, it runs chisel inside the chroot environment.
    Otherwise it runs chisel outside the chroot environment.

    Args:
        mount_point (str): The mount point of the chroot environment.
        new_generation (bool): If True, run chisel inside the chroot environment.
    """
    if new_generation:
        exec_chroot("sudo chisel sync", mount_point=mount_point)
    else:
        exec("sudo chisel sync")


# Chisel
def kernel_update_required(
    current_kernel: str, next_kernel: str, current_installed_packages: Dict, mount_point: str
) -> bool:
    """
    Check if a kernel update is required.

    This function compares the current kernel version with the next one and
    returns True if they are different, indicating that a kernel update is
    required.

    Args:
        current_kernel (str): The name of the current kernel package.
        next_kernel (str): The name of the next kernel package.
        current_installed_packages (dict): A dictionary mapping package names
            to their respective versions.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        bool: True if a kernel update is required, False otherwise.
    """
    if current_kernel != next_kernel:
        return True

    # Get kernel version from chisel
    kernel_info = exec_chroot(f"chisel list {current_kernel}", mount_point=mount_point, get_output=True)

    if not kernel_info.strip():
        return True

    current_kernel_ver = current_installed_packages.get(current_kernel, "")
    # Parse version from chisel output (format: package_name version)
    parts = kernel_info.strip().split()
    new_kernel_ver = parts[1] if len(parts) >= 2 else ""

    if not new_kernel_ver:
        return True

    print(f"{current_kernel}={current_kernel_ver} {next_kernel}={new_kernel_ver} new_kernel_ver={new_kernel_ver}")

    if current_kernel_ver != new_kernel_ver:
        return True

    return False


# Chisel
def generale_package_lock(mount_point: str, state_path: str) -> None:
    """
    Generate a file containing the list of installed packages and their versions.

    This function uses Chisel to get the list of installed packages and their
    versions in a chroot environment. The output is written to a file named
    ``packages.lock`` in the specified ``state_path``.

    Args:
        mount_point (str): The path to the root directory of the chroot environment.
        state_path (str): The path to the state directory where the package information
            should be stored.
    """
    installed_packages_version = exec_chroot("chisel list", mount_point=mount_point, get_output=True)

    with open(f"{state_path}/packages.lock", "w") as f:
        f.write(installed_packages_version)
