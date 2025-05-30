# Arch specific functions

import re
from kod.common import exec_chroot, exec
import json
from typing import Dict


def prepare_for_installation():
    exec("apt install -y gdisk btrfs-progs dosfstools")


# Debian
def get_base_packages(conf):
    # CPU microcode
    """
    Get the base packages to install for the given configuration.

    The function determines the right microcode package for the CPU and
    the kernel package from the configuration. It then returns a table
    with the packages to install.

    Args:
        conf (table): The configuration table.

    Returns:
        A list with the packages to install.
    """
    with open("/proc/cpuinfo") as f:
        while True:
            line = f.readline()
            if "AuthenticAMD" in line:
                microcode = "amd64-microcode"
                break
            if "GenuineIntel" in line:
                microcode = "intel-microcode"
                break

    if conf.boot and conf.boot.kernel and conf.boot.kernel.package:
        kernel_package = conf.boot.kernel.package
    else:
        kernel_package = "linux-image-amd64"

    # TODO: add verions to each package
    packages = {
        "kernel": kernel_package,
        "base": [
            # "base",
            # "base-devel",
            # microcode,
            "btrfs-progs",
            "systemd-boot",
            # "firmware-linux", # Requires non-free repo
            # "bash-completion",
            # "plocate",
            "locales",
            "sudo",
            "schroot",
            "whois",
            "dracut",
            "git",
        ],
    }
    # TODO: remove this package dependency
    # packages["base"] += ["arch-install-scripts"]
    return packages


# Debian
def install_essentials_pkgs(base_pkgs: Dict, mount_point: str):
    """
    Install essential packages onto the specified mount point.

    This function uses the Debian debootstrap command to install a set of base
    packages including the kernel and other essential packages onto a
    given mount point. The packages to be installed are determined by
    the base_pkgs dictionary, which should contain 'kernel' and 'base'
    keys.

    Args:
        base_pkgs (Dict): A dictionary containing the packages to install,
                          with 'kernel' and 'base' keys.
        mount_point (str): The mount point where the packages will be installed.
    """
    # exec(f"pacstrap -K {mount_point} {' '.join([base_pkgs['kernel']] + base_pkgs['base'])}")
    exec("apt install -y debootstrap gdisk")
    exec("debootstrap --merged-usr testing /mnt")
    exec_chroot(
        f"bash -c 'yes | DEBIAN_FRONTEND=noninteractive apt-get install -y {' '.join([base_pkgs['kernel']] + base_pkgs['base'])}'",
        mount_point=mount_point,
    )


# Debian
def get_kernel_file(mount_point: str, package: str = "linux"):
    """
    Retrieve the kernel file path and version from the specified mount point.

    Args:
        mount_point (str): The mount point of the chroot environment to retrieve the kernel file from.
        package (str, optional): The package name to retrieve the kernel file from. Defaults to "linux".

    Returns:
        tuple: A tuple containing the kernel file path as a string and the kernel version as a string.
    """
    kernel_file_depend = exec_chroot(
        f"apt-cache depends {package} | grep Depends", mount_point=mount_point, get_output=True
    )
    kernel_file = kernel_file_depend.split(":")[1].strip()
    kver = kernel_file.split("-", 2)[-1]
    return kernel_file, kver


def setup_linux(kernel_package):
    _, kver = get_kernel_file(mount_point="/mnt", package=kernel_package)
    return kver


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
    pkgs_list = [pkg]
    # check if it is a group
    pkgs_list = exec(f"pacman -Sgq {pkg}", get_output=True).strip().split("\n")
    # pkgs_list = exec(f"pacman -Sgq {pkg}").strip().split("\n")
    if len(pkgs_list) > 0:
        pkgs_list += [pkg.strip() for pkg in pkgs_list] + [pkg]
    else:
        # check if it is a (meta-)package
        depend_on = exec(f"pacman -Si {pkg} | grep 'Depends On'", get_output=True).split(":")
        # depend_on = exec(f"pacman -Si {pkg} | grep 'Depends On'").split(":")
        pkgs_list += [pkg.strip() for pkg in depend_on[1].strip().split()]
    return pkgs_list


# Debian
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

            # TODO: Generalize this code to support other distros
            # exec_chroot("pacman -S --needed --noconfirm git base-devel")
            exec_chroot(
                f"runuser -u kod -- /bin/bash -c 'cd && git clone {url} {name} && cd {name} && {build_cmd}'",
                mount_point=mount_point,
            )

        # if "package" in repo_desc:
        #     exec_chroot(
        #         f"pacman -S --needed --noconfirm {repo_desc['package']}",
        #         mount_point=mount_point,
        #     )
        #     packages += [repo_desc["package"]]
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


# Debian
def kernel_update_rquired(current_kernel, next_kernel, current_installed_packages, mount_point):
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
    new_kernel = exec_chroot(f"apt-cache madison {current_kernel}", mount_point=mount_point, get_output=True)
    current_kernel_ver = current_installed_packages[current_kernel]
    new_kernel_ver = new_kernel.split("|")[1].strip()

    print(f"{current_kernel}={current_kernel_ver} {next_kernel}={new_kernel_ver} {new_kernel=}")
    if current_kernel_ver != new_kernel_ver:
        return True
    return False


# Debian
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
    installed_pakages_version = exec_chroot("dpkg -l", mount_point=mount_point, get_output=True)
    with open(f"{state_path}/packages.lock", "w") as f:
        for line in installed_pakages_version.split("\n"):
            if line[:2] == "ii":
                pkg = re.split("[ ]+", line)
                f.write(f"{pkg[1]} {pkg[2]}\n")
