"""Arch Linux specific package and system management functions.

This module provides Arch Linux specific implementations for package installation,
system configuration, user management, and service handling. It includes functions
for detecting hardware-specific packages and managing Arch-specific tools.
"""

from kod.common import exec_chroot, exec
import json
from typing import Dict, Any


# Arch
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
    with open("/proc/cpuinfo") as f:
        while True:
            line = f.readline()
            if "AuthenticAMD" in line:
                microcode = "amd-ucode"
                break
            if "GenuineIntel" in line:
                microcode = "intel-ucode"
                break

    if conf.boot and conf.boot.kernel and conf.boot.kernel.package:
        kernel_package = conf.boot.kernel.package
    else:
        kernel_package = "linux"

    # TODO: add verions to each package
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

    # TODO: remove this package dependency
    packages["base"] += ["arch-install-scripts"]
    return packages


# Arch
def install_essentials_pkgs(base_pkgs: Dict, mount_point: str):
    """
    Install essential packages onto the specified mount point.

    This function uses the Arch pacstrap command to install a set of base
    packages including the kernel and other essential packages onto a
    given mount point. The packages to be installed are determined by
    the base_pkgs dictionary, which should contain 'kernel' and 'base'
    keys.

    Args:
        base_pkgs (Dict): A dictionary containing the packages to install,
                          with 'kernel' and 'base' keys.
        mount_point (str): The mount point where the packages will be installed.
    """
    exec(f"pacstrap -K {mount_point} {' '.join([base_pkgs['kernel']] + base_pkgs['base'])}")


# Arch
def get_kernel_file(mount_point: str, package: str = "linux"):
    """
    Retrieve the kernel file path and version from the specified mount point.

    Args:
        mount_point (str): The mount point of the chroot environment to retrieve the kernel file from.
        package (str, optional): The package name to retrieve the kernel file from. Defaults to "linux".

    Returns:
        tuple: A tuple containing the kernel file path as a string and the kernel version as a string.
    """
    kernel_file = exec_chroot(
        f"bash -c 'pacman -Ql {package} | grep vmlinuz'", mount_point=mount_point, get_output=True
    )
    print(f"pacman -Ql {package} | grep vmlinuz")
    
    # Validate output before parsing
    if not kernel_file or not kernel_file.strip():
        raise RuntimeError(f"No kernel file found for package '{package}'. Output: {kernel_file}")
    
    kernel_file = kernel_file.split(" ")[-1].strip()
    
    # Validate kernel path format
    if not kernel_file or "/" not in kernel_file:
        raise RuntimeError(f"Invalid kernel file path: {kernel_file}")
    
    kver = kernel_file.split("/")[-2]
    
    # Validate kernel version exists
    if not kver or kver.isspace():
        raise RuntimeError(f"Could not extract kernel version from path: {kernel_file}")
    
    return kernel_file, kver


# Arch
def get_list_of_dependencies(pkg: str):
    """
    Get the list of dependencies of a given package.

    This function takes a package name and returns a list of packages it depends on.
    It first checks if the package is a group, and if it is, it returns the list of
    packages in the group. If it is not a group, it checks the dependencies of the package
    and returns the list of dependencies.

    Args:
        pkg (str): The package name to get the dependencies of.

    Returns:
        list: A list of packages that the given package depends on.
    """
    # Check if it is a group
    group_output = exec(f"pacman -Sgq {pkg}", get_output=True).strip()
    
    # Only use group output if non-empty (filter out empty strings)
    if group_output:
        pkgs_list = group_output.split("\n")
        pkgs_list = [p.strip() for p in pkgs_list if p.strip()]
        if pkgs_list:
            return pkgs_list + [pkg]
    
    # Fallback: check if it is a (meta-)package
    try:
        depend_on = exec(f"pacman -Si {pkg} | grep 'Depends On'", get_output=True).split(":")
        if len(depend_on) >= 2:
            deps = [p.strip() for p in depend_on[1].strip().split() if p.strip()]
            if deps:
                return deps
        return [pkg]
    except Exception:
        return [pkg]


# Arch
def proc_repos(conf, current_repos=None, update=False, mount_point="/mnt"):
    """
    Process the repository configuration from the given config.

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

    if repos_conf is None:
        return repos, packages

    for repo, repo_desc in repos_conf.items():
        if current_repos and repo in current_repos and not update:
            repos[repo] = current_repos[repo]
            continue
        repos[repo] = {}

        if "commands" not in repo_desc:
            print(f"Warning: Repository '{repo}' missing 'commands' field, skipping")
            continue

        for action, cmd in repo_desc["commands"].items():
            repos[repo][action] = cmd

        # Install base package if specified (e.g., flatpak, yay, etc.)
        # MUST happen before AUR build, since build needs git, gcc, etc.
        if "package" in repo_desc:
            pkg_name = repo_desc['package']
            print(f"Installing base package for '{repo}': {pkg_name}")
            try:
                exec_chroot(
                    f"pacman -S --needed --noconfirm {pkg_name}",
                    mount_point=mount_point,
                )
                packages += [pkg_name]
                print(f"✅ Base package '{pkg_name}' installed")
            except Exception as e:
                print(f"❌ Failed to install base package '{pkg_name}': {e}")
                raise

        # Handle Flatpak remote initialization
        if repo == "flatpak" and "init" in repo_desc:
            init_cmd = repo_desc["init"]
            
            # Pre-check: verify flatpak is installed before attempting init
            try:
                flatpak_check = exec_chroot(
                    "which flatpak",
                    mount_point=mount_point,
                    get_output=True
                )
                if not flatpak_check or "not found" in flatpak_check.lower():
                    raise RuntimeError("Flatpak not installed. Install 'flatpak' package first.")
            except RuntimeError:
                # Re-raise our custom error message
                raise
            except Exception as e:
                raise RuntimeError(f"Failed to check flatpak availability: {e}")
            
            print(f"Initializing Flatpak: {init_cmd}")
            try:
                exec_chroot(f"{init_cmd}", mount_point=mount_point)
                print(f"✅ Flatpak remote initialized")
            except Exception as e:
                print(f"⚠️  Warning: Flatpak remote initialization failed: {e}")
                # Don't fail completely, just warn

        # Handle AUR helper build (after base packages installed)
        if "build" in repo_desc:
            build_info = repo_desc["build"]
            url = build_info["url"]
            build_cmd = build_info["build_cmd"]
            name = build_info["name"]

            print(f"Building AUR helper: {name}")
            try:
                # Build AUR helper as kod user, install as root
                exec_chroot(
                    f"runuser -u kod -- /bin/bash -c 'cd && rm -rf {name} && git clone {url} {name} && cd {name} && {build_cmd}'",
                    mount_point=mount_point,
                )
                
                # Verify the build was successful by checking if binary exists
                result = exec_chroot(
                    f"which {name}",
                    mount_point=mount_point,
                    get_output=True
                )
                if not result or "not found" in result.lower():
                    raise RuntimeError(f"AUR helper '{name}' not found after build. Build output: {result}")
                
                print(f"✅ AUR helper '{name}' built successfully")
            except Exception as e:
                print(f"❌ Failed to build AUR helper '{name}': {e}")
                raise
        update_repos = True

    if update_repos:
        exec(f"mkdir -p {mount_point}/var/kod")
        with open(f"{mount_point}/var/kod/repos.json", "w") as f:
            f.write(json.dumps(repos, indent=2))

    return repos, packages


# Arch
def refresh_package_db(mount_point, new_generation):
    """
    Refresh the package database.

    This function runs pacman -Syy --noconfirm to refresh the package database.
    If new_generation is True, it runs pacman inside the chroot environment.
    Otherwise it runs pacman outside the chroot environment.

    Args:
        mount_point (str): The mount point of the chroot environment.
        new_generation (bool): If True, run pacman inside the chroot environment.
    """
    if new_generation:
        exec_chroot("pacman -Syy --noconfirm", mount_point=mount_point)
    else:
        exec("pacman -Syy --noconfirm")


# Arch
def kernel_update_required(current_kernel, next_kernel, current_installed_packages, mount_point):
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
    
    Raises:
        RuntimeError: If kernel version format is invalid.
    """
    if current_kernel != next_kernel:
        return True
    new_kernel = exec_chroot(f"pacman -Q {current_kernel}", mount_point=mount_point, get_output=True)
    current_kernel_ver = current_installed_packages[current_kernel]
    
    # Validate output format before splitting
    split_output = new_kernel.strip().split(" ")
    if len(split_output) < 2:
        raise RuntimeError(f"Invalid kernel version output: {new_kernel}")
    
    new_kernel_ver = split_output[1]

    # Validate kernel version format before parsing
    if not new_kernel_ver or new_kernel_ver.isspace():
        raise RuntimeError(f"Invalid kernel version: {new_kernel_ver}")
    
    split_kver = new_kernel_ver.split(".")
    # Kernel versions should have at least a major.minor format (e.g., "6.1")
    if len(split_kver) < 2 or not split_kver[0]:
        raise RuntimeError(f"Could not parse kernel architecture from: {new_kernel_ver}")

    print(f"{current_kernel}={current_kernel_ver} {next_kernel}={new_kernel_ver} {new_kernel=}")
    if current_kernel_ver != new_kernel_ver:
        return True
    return False


# Arch
def generale_package_lock(mount_point, state_path):
    """
    Generate a file containing the list of installed packages and their versions.

    This function uses the ``pacman -Q --noconfirm`` command to get the list of installed
    packages and their versions in a chroot environment. The output is written to a file
    named ``packages.lock`` in the specified ``state_path``.

    Args:
        mount_point (str): The path to the root directory of the chroot environment.
        state_path (str): The path to the state directory where the package information
            should be stored.
    """
    installed_pakages_version = exec_chroot("pacman -Q --noconfirm", mount_point=mount_point, get_output=True)
    with open(f"{state_path}/packages.lock", "w") as f:
        f.write(installed_pakages_version)
