"""Pistacho (pith) specific package and system management functions.

This module provides Pistacho-specific implementations for package
installation, system configuration, and maintenance. It mirrors the
interface of the former ``kod.arch`` module but drives the ``pith``
package manager (which installs Arch packages without pacman) instead of
pacman itself.

The pith store lives on the top-level Btrfs subvolume, which KodOS binds
into every generation at ``/kod``. All commands therefore target
``<mount_point>/kod`` and install with ``--chroot <mount_point>`` so the
packages are extracted directly into the generation's rootfs.
"""

import glob
import json
import os
from typing import Any

from kod.common import exec, exec_chroot

PITH_VERSION = "0.4.3"
PITH_BINARY_NAME = f"pith-v{PITH_VERSION}-linux-amd64"
PITH_DOWNLOAD_URL = f"https://github.com/kodos-prj/pistacho/releases/latest/download/{PITH_BINARY_NAME}"


def pith_bin() -> str:
    """Return the path to the pith binary used by the host."""
    return os.environ.get("KOD_PITH_BIN", "/usr/local/bin/pith")


def _store_path(mount_point: str) -> str:
    return f"{mount_point}/kod"


def prepare_for_installation() -> None:
    """Download the pith binary to the host if it is not already present."""
    pith = pith_bin()
    if os.path.isfile(pith):
        print(f"Using existing pith binary: {pith}")
        return
    print(f"Downloading pith {PITH_VERSION} from {PITH_DOWNLOAD_URL}")
    exec(f"mkdir -p {os.path.dirname(pith)}")
    exec(f"curl -fL -o {pith} {PITH_DOWNLOAD_URL}")
    exec(f"chmod +x {pith}")
    print(f"pith binary installed: {pith}")


def get_base_packages(conf: Any) -> dict[str, Any]:
    """Return the base packages to install for the given configuration.

    Args:
        conf: The configuration object.

    Returns:
        A dictionary with the packages to install, containing the kernel
        package and the list of base packages.
    """
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

    packages = {
        "kernel": kernel_package,
        "base": [
            # base + base-devel dependencies (filesystem and pacman excluded)
            "archlinux-keyring",
            "autoconf",
            "automake",
            "bash",
            "binutils",
            "bison",
            "btrfs-progs",
            "bzip2",
            "coreutils",
            "debugedit",
            "dracut",
            "fakeroot",
            "file",
            "findutils",
            "flex",
            "gawk",
            "gcc",
            "gcc-libs",
            "gettext",
            "git",
            "glibc",
            "grep",
            "groff",
            "gzip",
            microcode,
            "iproute2",
            "iputils",
            "libtool",
            "licenses",
            "linux-firmware",
            "m4",
            "make",
            "pciutils",
            "patch",
            "pkgconf",
            "procps-ng",
            "psmisc",
            "sed",
            "shadow",
            "sudo",
            "systemd",
            "systemd-sysvcompat",
            "tar",
            "texinfo",
            "util-linux",
            "which",
            "whois",
            "xz",
        ],
    }
    return packages


def install_essentials_pkgs(base_pkgs: dict, mount_point: str) -> None:
    """Install essential packages onto the specified mount point.

    This replaces the Arch ``pacstrap`` flow. ``pith`` is used to sync the
    package databases and to install the base packages (including the
    kernel) directly into the given mount point. The shared pith store is
    expected to live at ``<mount_point>/kod``.

    Args:
        base_pkgs: A dictionary with the ''kernel'' and ''base'' keys.
        mount_point: The mount point where the packages will be installed.
    """
    prepare_for_installation()
    pith = pith_bin()
    store = _store_path(mount_point)

    print("Syncing pith package databases...")
    exec(f"{pith} --base-dir {store} sync")

    pkgs = " ".join([base_pkgs["kernel"]] + base_pkgs["base"])
    print(f"Installing base packages with pith (kernel={base_pkgs['kernel']})")
    # Install but not create symlimks
    no_symlink_pkgs = "filesystem"
    exec(f"{pith} --base-dir {store} install --chroot {mount_point} --no-symlink {no_symlink_pkgs}")
    # Install the selected packages
    exec(f"{pith} --base-dir {store} install --chroot {mount_point} {pkgs}")

    create_merged_usr_symlinks(mount_point)
    write_pith_config(mount_point)
    copy_pith_to_rootfs(mount_point)


def install_selected_pkgs(list_of_packages: list[str], mount_point: str) -> None:
    """Install essential packages onto the specified mount point.

    This replaces the Arch ``pacstrap`` flow. ``pith`` is used to sync the
    package databases and to install the base packages (including the
    kernel) directly into the given mount point. The shared pith store is
    expected to live at ``<mount_point>/kod``.

    Args:
        base_pkgs: A dictionary with the ''kernel'' and ''base'' keys.
        mount_point: The mount point where the packages will be installed.
    """
    # prepare_for_installation()
    pith = pith_bin()
    store = _store_path(mount_point)

    pkgs = " ".join(list_of_packages)
    print(f"Installing selected packages with pith")
    # Install the selected packages
    exec(f"{pith} --base-dir {store} install --chroot {mount_point} {pkgs}")


def write_pith_config(mount_point: str) -> None:
    """Write the pith config file inside the rootfs.

    The runtime config points pith at the shared store mounted at ``/kod``
    and at an Arch mirror for future database syncs.

    Args:
        mount_point: The mount point of the rootfs being installed.
    """
    config_path = f"{mount_point}/etc/pith/config.json"
    exec(f"mkdir -p {os.path.dirname(config_path)}")
    config = {
        "base_dir": "/kod",
        "mirror_url": "https://mirror.rackspace.com/archlinux",
    }
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Written pith config: {config_path}")


def copy_pith_to_rootfs(mount_point: str) -> None:
    """Copy the pith binary into the rootfs so future operations can use it."""
    pith = pith_bin()
    dst = f"{mount_point}/usr/bin/pith"
    exec(f"mkdir -p {os.path.dirname(dst)}")
    exec(f"cp {pith} {dst}")
    exec(f"chmod +x {dst}")
    print(f"Copied pith binary to {dst}")


def create_merged_usr_symlinks(mount_point: str) -> None:
    """Create merged-usr symlinks and missing directories that the filesystem package normally provides.

    Creates relative symlinks (/bin -> usr/bin, not /bin -> /usr/bin) and
    directories (/dev, /proc, /run, /sys, /tmp) that would otherwise be
    provided by the filesystem package.

    Args:
        mount_point: The mount point of the rootfs being installed.
    """
    # Relative symlinks (no leading /)
    symlinks = {
        "bin": "usr/bin",
        "lib": "usr/lib",
        "lib64": "usr/lib",
        "sbin": "usr/bin",
    }

    for name, target in symlinks.items():
        link_path = f"{mount_point}/{name}"
        if os.path.islink(link_path) or os.path.exists(link_path):
            print(f"Symlink {name} already exists, skipping")
            os.remove(link_path)
        os.symlink(target, link_path)
        print(f"Created symlink {name} -> {target}")

    # Missing directories normally created by the filesystem package
    dirs = [
        "dev",
        "opt",
        "proc",
        "run",
        "sys",
        "tmp",
    ]
    for d in dirs:
        dir_path = f"{mount_point}/{d}"
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            print(f"Created directory {d}")


def run_install_scripts(mount_point: str) -> None:
    """Execute package install scripts inside the chroot context.

    ``pith`` does not run post_install/post_upgrade scripts during a
    ``--chroot`` install, so they must be executed explicitly after all
    packages are in place.

    Args:
        mount_point: The mount point of the rootfs container.
    """
    pith = pith_bin()
    store = _store_path(mount_point)
    exec(f"{pith} --base-dir {store} install-scripts --chroot {mount_point}")


def get_kernel_file(mount_point: str, package: str = "linux") -> tuple[str, str]:
    """Retrieve the kernel file path and version for the given package.

    The kernel is looked up in the shared pith pool at
    ``<mount_point>/kod/pool/<package>/current/usr/lib/modules/<kver>/vmlinuz``.

    Args:
        mount_point: The mount point of the chroot environment.
        package: The package name to retrieve the kernel file from.

    Returns:
        A tuple with the kernel file path (as seen from inside the chroot)
        and the kernel version.
    """
    pool_root = f"{_store_path(mount_point)}/pool/{package}/current/usr/lib/modules"
    candidates = glob.glob(f"{pool_root}/*/vmlinuz")
    if not candidates:
        raise RuntimeError(f"kernel vmlinuz not found in pith pool: {pool_root}")
    kernel_file = candidates[0]
    kver = kernel_file.split("/")[-2]
    print(f"Found kernel {kver} at {kernel_file}")
    # The path from inside the chroot resolves through the /kod bind mount.
    chroot_kernel = kernel_file.replace(mount_point, "", 1)
    return chroot_kernel, kver


def setup_linux(kernel_package) -> str:
    """Copy the kernel into the boot directory and return its version."""
    kernel_file, kver = get_kernel_file(mount_point="/mnt", package=kernel_package)
    exec_chroot(f"cp {kernel_file} /boot/vmlinuz-{kver}", mount_point="/mnt")
    return kver


def get_list_of_dependencies(pkg: str) -> list[str]:
    """Return the list of packages a given package/group depends on.

    ``pith`` resolves groups and dependencies natively at install time, so
    the package/group name is returned as-is and the full resolution is
    performed later by ``pith install``.

    Args:
        pkg: The package or group name.

    Returns:
        A list containing the package/group name.
    """
    return [pkg]


def proc_repos(conf, current_repos=None, update=False, mount_point="/mnt") -> tuple[dict[str, Any], list[str]]:
    """Process the repository configuration from the configuration.

    This writes the configured repositories and their pith command strings
    to ``<mount_point>/var/kod/repos.json``, and installs any repository
    helper packages (e.g. flatpak) as requested by the configuration.

    Args:
        conf: The configuration dictionary.
        current_repos: The current repository configuration.
        update: If True, update the package list.
        mount_point: The mount point where the installation is done.

    Returns:
        A tuple with the processed repository configuration and the list of
        packages that were installed.
    """
    repos_conf = conf.repos
    repos = {}
    packages: list[str] = []
    update_repos = False
    for repo, repo_desc in repos_conf.items():
        if current_repos and repo in current_repos and not update:
            repos[repo] = current_repos[repo]
            continue
        repos[repo] = {}
        for action, cmd in repo_desc["commands"].items():
            repos[repo][action] = cmd

        if "package" in repo_desc:
            exec_chroot(
                f"pith install --chroot / {repo_desc['package']}",
                mount_point=mount_point,
            )
            packages += [repo_desc["package"]]
        update_repos = True

    if update_repos:
        exec(f"mkdir -p {mount_point}/var/kod")
        with open(f"{mount_point}/var/kod/repos.json", "w") as f:
            f.write(json.dumps(repos, indent=2))

    return repos, packages


def refresh_package_db(mount_point, new_generation) -> None:
    """Refresh the pith package database.

    Args:
        mount_point: The mount point of the chroot environment.
        new_generation: If True, run inside the chroot (unsupported by pith
            from the host; sync always targets the shared store).
    """
    pith = pith_bin()
    store = _store_path(mount_point)
    exec(f"{pith} --base-dir {store} sync")


def kernel_update_required(current_kernel, next_kernel, current_installed_packages, mount_point) -> bool:
    """Check if a kernel update is required.

    Package updates are handled by ``pith upgrade``; kernel change
    detection is not implemented yet.

    Returns:
        True if a kernel update is required.
    """
    return current_kernel != next_kernel


def generale_package_lock(mount_point, state_path) -> None:
    """Generate a file containing the list of installed packages.

    The list is read from the pith registry at ``<mount_point>/kod/registry.json``
    and written to ``packages.lock`` in the given state path.

    Args:
        mount_point: The mount point of the chroot environment.
        state_path: The path to the state directory.
    """
    installed_packages: dict[str, str] = {}
    registry_path = f"{_store_path(mount_point)}/registry.json"
    if os.path.isfile(registry_path):
        with open(registry_path) as f:
            registry = json.load(f)
        for name, info in registry.items():
            installed_packages[name] = info.get("version", "")
    else:
        pith = pith_bin()
        store = _store_path(mount_point)
        lines = exec(f"{pith} --base-dir {store} list", get_output=True).splitlines()
        started = False
        for line in lines:
            if line.startswith("----"):
                started = True
                continue
            if started and len(line.split()) >= 2:
                name, version = line.split()[:2]
                installed_packages[name] = version

    with open(f"{state_path}/packages.lock", "w") as f:
        for name in sorted(installed_packages):
            f.write(f"{name} {installed_packages[name]}\n")
