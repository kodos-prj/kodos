"""Package management functionality for KodOS.

This module handles package installation, updates, dependency resolution,
and package state management for the KodOS system.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Callable

from kod.arch import get_base_packages, get_list_of_dependencies, get_kernel_file
from kod.common import exec, exec_chroot, exec_critical


def get_packages_to_install(conf: Any) -> Tuple[Dict[str, List[str]], List[str]]:
    """
    Determine the packages to install and remove based on the given configuration.

    This function aggregates various categories of packages such as base, desktop,
    hardware, services, user programs, system packages, and fonts. It consolidates
    these into a list of packages to install and a list of packages to remove.

    Args:
        conf (table): The configuration table containing details for package selection.

    Returns:
        tuple: A tuple containing two elements:
            - packages_to_install (dict): A dictionary with a "packages" key listing
              all the unique packages to be installed.
            - packages_to_remove (list): A list of packages to be removed.
    """
    packages_to_install = []
    packages_to_remove = []

    # Base packages
    base_packages = get_base_packages(conf)

    # Desktop
    desktop_packages_to_install, desktop_packages_to_remove = proc_desktop(conf)

    # Hardware
    hw_packages_to_install = proc_hardware(conf)

    # Services
    service_packages_to_install = proc_services(conf)

    # User programs
    user_packages_to_install = proc_user_programs(conf)

    # System packages
    system_packages_to_install = proc_system_packages(conf)

    # Font packages
    font_packages_to_install = proc_fonts(conf)

    packages_to_install = base_packages.copy()
    packages_to_install["packages"] = list(
        set(
            desktop_packages_to_install
            + hw_packages_to_install
            + service_packages_to_install
            + user_packages_to_install
            + system_packages_to_install
            + font_packages_to_install
        )
    )

    packages_to_remove = list(set(desktop_packages_to_remove))

    return packages_to_install, packages_to_remove


def manage_packages(
    root_path: str, repos: Dict[str, Any], action: str, list_of_packages: List[str], chroot: bool = False
) -> List[str]:
    """
    Manage package installation, update, or removal based on the provided repository configuration.

    This function organizes the packages into their respective repositories,
    executes the specified action (install, update, or remove) for each package
    using the corresponding repository command, and handles privilege escalation
    as needed based on the repository configuration and `chroot` flag.

    Args:
        root_path (str): The root path for chroot operations, if applicable.
        repos (dict): A dictionary containing repository configurations and commands.
        action (str): The action to perform on the packages (e.g., 'install', 'update', 'remove').
        list_of_packages (list): A list of package names, potentially prefixed with
                                 the repository name followed by a colon.
        chroot (bool, optional): If True, execute the commands in a chroot environment
                                 based at `root_path`. Defaults to False.

    Returns:
        list: A list of installed package names.
    """
    packages_installed = []
    pkgs_per_repo = {"official": []}
    wrong_pkgs: List[str] = []  # Initialize outside the loop

    for pkg in list_of_packages:
        if ":" in pkg:
            repo, pkg_name = pkg.split(":")
            if repo not in pkgs_per_repo:
                pkgs_per_repo[repo] = []
            pkgs_per_repo[repo].append(pkg_name)
        else:
            pkgs_per_repo["official"].append(pkg)

    for repo, pkgs in pkgs_per_repo.items():
        if len(pkgs) == 0:
            continue
        if "run_as_root" in repos[repo] and not repos[repo]["run_as_root"]:
            if chroot:
                try:
                    exec_chroot(
                        f"runuser -u kod -- {repos[repo][action]} {' '.join(pkgs)}",
                        mount_point=root_path,
                    )
                except Exception as e:
                    print(f"Error: Package operation failed in chroot for {repo}: {e}")
                    print(f"Failed packages: {pkgs}")
                    wrong_pkgs.extend(pkgs)
            else:
                try:
                    exec(f"runuser -u kod -- {repos[repo][action]} {' '.join(pkgs)}")
                except Exception as e:
                    print(f"Error: Package operation failed for {repo}: {e}")
                    print(f"Failed packages: {pkgs}")
                    wrong_pkgs.extend(pkgs)
        else:
            if chroot:
                for pkg in pkgs:
                    try:
                        result = exec_chroot(f"{repos[repo][action]} {pkg}", mount_point=root_path, get_output=True)
                        if re.match(r"^[Ee]rror", result):
                            wrong_pkgs.append(pkg)
                    except Exception as e:
                        print(f"Error: Package operation failed for {pkg} in chroot: {e}")
                        wrong_pkgs.append(pkg)
                # exec_chroot(f"{repos[repo][action]} {' '.join(pkgs)}", mount_point=root_path)
            else:
                for pkg in pkgs:
                    try:
                        result = exec(f"{repos[repo][action]} {pkg}", get_output=True)
                        if re.match(r"^[Ee]rror", result):
                            wrong_pkgs.append(pkg)
                    except Exception as e:
                        print(f"Error: Package operation failed for {pkg}: {e}")
                        wrong_pkgs.append(pkg)
                # exec(f"{repos[repo][action]} {' '.join(pkgs)}")
        packages_installed += pkgs
    print("Wrong packages:", wrong_pkgs)
    return packages_installed


def manage_packages_shell(repos: Dict[str, Any], action: str, list_of_packages: List[str], chroot: bool) -> None:
    """
    Manage packages using schroot for shell-based operations.

    Args:
        repos (dict): Repository configuration.
        action (str): Action to perform ('install', 'update', 'remove').
        list_of_packages (list): List of package names.
        chroot (bool): Whether to use chroot environment.
    """
    pkgs_per_repo = {"official": []}
    for pkg in list_of_packages:
        if ":" in pkg:
            repo, pkg_name = pkg.split(":")
            if repo not in pkgs_per_repo:
                pkgs_per_repo[repo] = []
            pkgs_per_repo[repo].append(pkg_name)
        else:
            pkgs_per_repo["official"].append(pkg)

    print(f"{pkgs_per_repo = }")
    for repo, pkgs in pkgs_per_repo.items():
        print(repo, "->", pkgs)
        if len(pkgs) == 0:
            continue
        if "run_as_root" in repos[repo] and not repos[repo]["run_as_root"]:
            print(f"schroot -r -c {chroot} -- {repos[repo][action]} {' '.join(pkgs)}")
            exec(f"schroot -r -c {chroot} -- {repos[repo][action]} {' '.join(pkgs)}")
        else:
            exec(f"schroot -r -c {chroot} -u root -- {repos[repo][action]} {' '.join(pkgs)}")


def update_all_packages(mount_point: str, new_generation: bool, repos: Dict[str, Any]) -> None:
    """
    Updates all packages in the system.

    Args:
        mount_point (str): The mount point of the chroot environment.
        new_generation (bool): If True, run pacman inside the chroot environment.
        repos (dict): A dictionary containing repository configurations and commands.
    """
    # Use the repo update entry for all the repos
    for repo, repo_desc in repos.items():
        if "update" in repo_desc:
            print(f"Updating {repo}")
            if new_generation:
                if "run_as_root" in repo_desc and not repo_desc["run_as_root"]:
                    exec_chroot(
                        f"runuser -u kod -- {repo_desc['update']} --noconfirm",
                        mount_point=mount_point,
                    )
                else:
                    exec_chroot(f"{repo_desc['update']}", mount_point=mount_point)
            else:
                if "run_as_root" in repo_desc and not repo_desc["run_as_root"]:
                    exec(f"runuser -u kod -- {repo_desc['update']} --noconfirm")
                else:
                    exec(f"{repo_desc['update']}")


def get_pending_packages(packages_to_install: Dict[str, List[str]]) -> List[str]:
    """
    Get the list of packages that are pending installation.

    Args:
        packages_to_install (dict): A dictionary containing the packages to install.
            The dictionary should have a single key: "packages", which is a list of
            package names.

    Returns:
        list: A list of package names that are pending installation.
    """
    pending_to_install = packages_to_install["packages"]
    return pending_to_install


def store_packages_services(
    state_path: str, packages_to_install: Dict[str, List[str]], system_services: List[str]
) -> None:
    """
    Store the list of packages that are installed and the list of services that are enabled.

    Stores the list of packages that are installed in a JSON file and the list of services
    that are enabled in a plain text file.

    Args:
        state_path (str): The path to the state directory where the package and service
            information should be stored.
        packages_to_install (dict): A dictionary containing the packages to install.
            The dictionary should have a single key: "packages", which is a list of
            package names.
        system_services (list): A list of system services that are enabled.
    """
    packages_json = json.dumps(packages_to_install, indent=2)
    with open(f"{state_path}/installed_packages", "w") as f:
        f.write(packages_json)
    with open(f"{state_path}/enabled_services", "w") as f:
        f.write("\n".join(system_services))


def load_packages_services(state_path: str) -> Tuple[Optional[Dict[str, List[str]]], Optional[List[str]]]:
    """
    Load the list of packages that are installed and the list of services that are enabled.

    Args:
        state_path (str): The path to the state directory where the package and service
            information is stored.

    Returns:
        tuple: A tuple containing two elements:
            - packages (dict): A dictionary containing the packages to install.
              The dictionary should have a single key: "packages", which is a list of
              package names.
            - services (list): A list of system services that are enabled.
    """
    with open(f"{state_path}/installed_packages", "r") as f:
        packages = json.load(f)
    with open(f"{state_path}/enabled_services", "r") as f:
        services = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    return packages, services


def load_package_lock(state_path: str) -> Optional[Dict[str, str]]:
    """
    Load the list of installed packages and their versions from a lock file.

    This function reads a file named `packages.lock` located at the provided
    `state_path`. Each line of the file should contain a package name followed
    by its version, separated by a space. The function parses the file and
    returns a dictionary mapping package names to their respective versions.

    Args:
        state_path (str): The path to the directory containing the `packages.lock` file.

    Returns:
        dict: A dictionary where keys are package names and values are their corresponding versions.
    """
    packages = {}
    with open(f"{state_path}/packages.lock") as f:
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue
            package, version = line.split(" ")
            packages[package] = version
    return packages


def update_kernel_hook(kernel_package: str, mount_point: str) -> Callable[[], None]:
    """
    Create a hook function to update the kernel for a specified package.

    This function generates a hook that, when executed, copies the kernel file
    for the specified kernel package from the chroot environment at the given
    mount point to the /boot directory with a versioned filename.

    Args:
        kernel_package (str): The name of the kernel package to update.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        function: A hook function that performs the kernel update.
    """

    def hook() -> None:
        print(f"Update kernel ....{kernel_package}")
        kernel_file, kver = get_kernel_file(mount_point, package=kernel_package)
        print(f"{kver=}")
        print(f"cp {kernel_file} /boot/vmlinuz-{kver}")
        exec_chroot(f"cp {kernel_file} /boot/vmlinuz-{kver}", mount_point=mount_point)

    return hook


def update_initramfs_hook(kernel_package: str, mount_point: str) -> Callable[[], None]:
    """
    Create a hook function to update the initramfs for a specified package.

    This function generates a hook that, when executed, generates an initramfs
    file for the specified kernel package from the chroot environment at the
    given mount point.

    Args:
        kernel_package (str): The name of the kernel package to update.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        function: A hook function that performs the initramfs update.
    """

    def hook() -> None:
        print(f"Update initramfs ....{kernel_package}")
        kernel_file, kver = get_kernel_file(mount_point, package=kernel_package)
        print(f"{kver=}")
        exec_chroot(
            f"dracut --kver {kver} --hostonly /boot/initramfs-linux-{kver}.img",
            mount_point=mount_point,
        )

    return hook


def get_packages_updates(
    dist: Any,
    current_packages: Dict[str, Any],
    next_packages: Dict[str, Any],
    remove_packages: List[str],
    current_installed_packages: List[str],
    mount_point: str,
) -> Tuple[List[str], List[str], List[str], List[Callable[[], None]]]:
    """
    Determine the packages to install, remove, and update, as well as any necessary hooks to run.

    This function compares the current and next package sets to decide which packages
    need to be installed, removed, or updated. It also determines if a kernel update is
    required and prepares appropriate hooks for updating the kernel and initramfs.

    Args:
        dist: Distribution-specific module for kernel operations.
        current_packages (dict): A dictionary containing information about currently installed packages.
        next_packages (dict): A dictionary containing information about packages to be installed.
        remove_packages (list): A list of package names to be removed.
        current_installed_packages (dict): A dictionary mapping currently installed package names to their versions.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        tuple: A tuple containing four elements:
            - packages_to_install (list): A list of package names that need to be installed.
            - packages_to_remove (list): A list of package names that need to be removed.
            - packages_to_update (list): A list of package names that need to be updated.
            - hooks_to_run (list): A list of hook functions that need to be executed.
    """

    packages_to_install = []
    packages_to_remove = []
    packages_to_update = []
    hooks_to_run = []
    current_kernel = current_packages["kernel"]
    next_kernel = next_packages["kernel"]
    if dist.kernel_update_rquired(current_kernel, next_kernel, current_installed_packages, mount_point):
        packages_to_install += [next_kernel]
        hooks_to_run += [
            update_kernel_hook(next_kernel, mount_point),
            update_initramfs_hook(next_kernel, mount_point),
        ]

    remove_pkg = (set(current_packages["packages"]) - set(next_packages["packages"])) | set(remove_packages)
    packages_to_remove += list(remove_pkg)

    added_pkgs = set(next_packages["packages"]) - set(current_packages["packages"])
    packages_to_install += list(added_pkgs)

    update_pkg = set(current_packages) & set(next_packages)
    packages_to_update += list(update_pkg)

    return packages_to_install, packages_to_remove, packages_to_update, hooks_to_run


# Configuration processing functions


def proc_desktop(conf: Any) -> Tuple[List[str], List[str]]:
    """
    Process the desktop configuration and generate the list of packages to install
    and remove. This function will iterate over the desktop manager options and
    process the packages to install and remove based on the configuration.

    Args:
        conf (dict): The configuration dictionary containing the desktop configuration.

    Returns:
        tuple: A tuple containing two lists: packages to install and packages to remove.
    """
    packages_to_install = []
    packages_to_remove = []
    desktop = conf.desktop

    display_manager = desktop.display_manager
    if display_manager:
        print(f"Installing {display_manager}")
        packages_to_install += [display_manager]

    desktop_manager = desktop.desktop_manager
    if desktop_manager:
        for desktop_mngr, dm_conf in desktop_manager.items():
            if dm_conf.enable:
                print(f"Installing {desktop_mngr}")
                if "extra_packages" in dm_conf:
                    pkg_list = list(dm_conf.extra_packages.values())
                    packages_to_install += pkg_list

                if "exclude_packages" in dm_conf:
                    exclude_pkg_list = list(dm_conf.exclude_packages.values())
                    packages_to_remove += exclude_pkg_list
                else:
                    exclude_pkg_list = []
                if exclude_pkg_list:
                    print(f"Excluding {exclude_pkg_list}")
                    all_pkgs_to_install = get_list_of_dependencies(desktop_mngr)
                    pkgs_to_install = list(set(all_pkgs_to_install) - set(exclude_pkg_list))
                    packages_to_install += pkgs_to_install
                else:
                    packages_to_install += [desktop_mngr]

                if "display_manager" in dm_conf:
                    display_mngr = dm_conf["display_manager"]
                    packages_to_install += [display_mngr]

    return packages_to_install, packages_to_remove


def proc_hardware(conf: Any) -> List[str]:
    """
    Process the hardware configuration and generate the list of packages to install.

    This function iterates over the hardware configuration and generates a list of
    packages to install based on the configuration settings.

    Args:
        conf (dict): The configuration dictionary containing the hardware settings.

    Returns:
        list: A list of package names that need to be installed.
    """
    packages = []
    print("- processing hardware -----------")
    hardware = conf.hardware
    for name, hw in hardware.items():
        print(name, hw.enable)
        pkgs = []
        if hw.enable:
            if hw.package:
                print("  using:", hw.package)
                name = hw.package

            pkgs.append(name)
            if hw.extra_packages:
                print("  extra packages:", hw.extra_packages)
                for _, pkg in hw.extra_packages.items():
                    pkgs.append(pkg)
            packages += pkgs

    return packages


def proc_system_packages(conf: Any) -> List[str]:
    """
    Process the system packages configuration and generate a list of packages to install.

    This function extracts the system packages defined in the configuration
    and returns them as a list.

    Args:
        conf (dict): The configuration dictionary containing the system
                     packages information.

    Returns:
        list: A list of system package names to be installed.
    """

    print("- processing packages -----------")
    sys_packages = list(conf.packages.values())
    return sys_packages


def proc_services(conf: Any) -> List[str]:
    """
    Process the services configuration and generate a list of packages to install.

    This function processes the services configuration and returns a list of
    packages that need to be installed.

    Args:
        conf (dict): The configuration dictionary containing the services
                     information.

    Returns:
        list: A list of package names to be installed.
    """
    packages_to_install = []
    print("- processing services -----------")
    services = conf.services
    for name, service in services.items():
        print(name, service.enable)
        if service.enable:
            pkgs = []
            if service.package:
                print("  using:", service.package)
                name = service.package
            pkgs.append(name)
            if service.extra_packages:
                print("  extra packages:", service.extra_packages)
                extra_pkgs = list(service.extra_packages.values())
                pkgs += extra_pkgs

            packages_to_install += pkgs

    return packages_to_install


def proc_user_programs(conf: Any) -> List[str]:
    """
    Process the user programs configuration and generate a list of packages to install.

    This function iterates over the user configuration and extracts the programs
    that need to be installed. It returns a list of packages to be installed.

    Args:
        conf (dict): The configuration dictionary containing the user
                     information.

    Returns:
        list: A list of packages to be installed.
    """
    packages = []

    print("- processing user programs -----------")
    users = conf.users

    for user, info in users.items():
        if info.programs:
            print(f"Processing programs for {user}")
            pkgs = []
            for name, prog in info.programs.items():
                print(name, prog.enable)
                if prog.enable:
                    if prog.package:
                        print("  using:", prog.package)
                        name = prog.package

                    if prog.extra_packages:
                        print("  extra packages:", prog.extra_packages)
                        for _, pkg in prog.extra_packages.items():
                            pkgs.append(pkg)
                    pkgs.append(name)
            packages += pkgs

        # Packages required for user services
        if info.services:
            for service, desc in info.services.items():
                if "enable" in desc and desc.enable:
                    print(f"Checking {service} service discription")
                    name = service
                    if "package" in desc:
                        name = desc.package

                    if desc.extra_packages:
                        print("  extra packages:", desc.extra_packages)
                        for _, pkg in desc.extra_packages.items():
                            packages.append(pkg)
                    packages.append(name)

    return packages


def proc_fonts(conf: Any) -> List[str]:
    """
    Process the fonts configuration and generate a list of font packages to install.

    This function examines the fonts configuration and returns a list of font
    packages specified in the configuration.

    Args:
        conf (dict): The configuration dictionary containing the fonts
                     information.

    Returns:
        list: A list of font package names to be installed.
    """

    packages_to_install = []
    print("- processing fonts -----------")
    fonts = conf.fonts
    if fonts and "packages" in fonts and fonts.packages:
        packages_to_install += fonts.packages.values()
    return packages_to_install
