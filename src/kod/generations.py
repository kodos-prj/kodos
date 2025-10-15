"""Generation and filesystem hierarchy management for KodOS."""

import glob
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

from kod.common import exec, exec_critical
from kod.filesystem import FsEntry
from kod.system import generate_fstab, change_subvol, load_fstab


def get_max_generation() -> int:
    """
    Retrieve the highest numbered generation directory in /kod/generations.

    If no generation directories exist, return 0.

    Returns:
        int: The highest numbered generation directory.
    """
    generations = glob.glob("/kod/generations/*")
    generations = [p.split("/")[-1] for p in generations]
    generations = [int(p) for p in generations if p != "current"]
    print(f"{generations=}")
    if generations:
        generation = max(generations)
    else:
        generation = 0
    print(f"{generation=}")
    return generation


def create_next_generation(boot_part: str, root_part: str, generation: int) -> str:
    """
    Create the next generation of the KodOS installation.

    Mounts the generation at /.next_current and sets up the subvolumes and
    mounts the partitions as specified in the fstab file.

    Args:
        boot_part (str): The device name of the boot partition
        root_part (str): The device name of the root partition
        generation (int): The generation number to create

    Returns:
        str: The path to the mounted generation
    """
    next_current = Path("/kod/current/.next_current")
    # Mounting generation
    if next_current.is_mount():
        print("Reboot is required to update generation")
        os._exit(0)
        exec(f"umount -R {next_current}")
        exec(f"rm -rf {next_current}")

    exec(f"mkdir -p {next_current}")

    exec(f"mount -o subvol=generations/{generation}/rootfs {root_part} {next_current}")
    exec(f"mount {boot_part} {next_current}/boot")
    exec(f"mount {root_part} {next_current}/kod")
    exec(f"mount -o subvol=store/home {root_part} {next_current}/home")

    subdirs = ["root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for dir in subdirs:
        exec(f"mount --bind /kod/store/{dir} {next_current}/{dir}")

    partition_list = load_fstab()
    change_subvol(partition_list, subvol=f"generations/{generation}", mount_points=["/"])
    generate_fstab(partition_list, str(next_current))

    # Write generation number
    with open(f"{next_current}/.generation", "w") as f:
        f.write(str(generation))

    print("===================================")

    return str(next_current)


def get_generation(mount_point: str) -> int:
    """
    Retrieve the generation number from a specified mount point.

    Args:
        mount_point (str): The mount point to read the generation number from.

    Returns:
        int: The generation number as an integer.
    """
    with open(f"{mount_point}/.generation", "r") as f:
        return int(f.read().strip())


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
    packahes_json = json.dumps(packages_to_install, indent=2)
    with open(f"{state_path}/installed_packages", "w") as f:
        f.write(packahes_json)
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


def create_filesystem_hierarchy(boot_part: Any, root_part: Any, partition_list: List, mount_point: str) -> List:
    """
    Create and configure a Btrfs filesystem hierarchy for KodOS.

    This function sets up the initial filesystem hierarchy for KodOS using Btrfs
    subvolumes. It creates necessary directories and subvolumes, mounts the first
    generation, and binds the appropriate directories. It also creates and mounts
    the boot and kod partitions.

    Args:
        boot_part: The boot partition to be mounted.
        root_part: The root partition to be used for creating subvolumes.
        partition_list: A list of Partition objects representing the filesystem hierarchy.
        mount_point: The mount point where the filesystem hierarchy will be created.

    Returns:
        list: An updated list of Partition objects reflecting the created filesystem hierarchy.
    """
    print("===================================")
    print("== Creating filesystem hierarchy ==")
    # Initial generation
    generation = 0
    for dir in ["store", "generations", "current"]:
        exec(f"mkdir -p {mount_point}/{dir}")

    subdirs = ["root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for dir in subdirs:
        exec(f"mkdir -p {mount_point}/store/{dir}")

    # Create home as subvolume if no /home is specified in the config
    # (TODO: Add support for custom home)
    exec_critical(f"sudo btrfs subvolume create {mount_point}/store/home", "Critical filesystem setup failed")

    # First generation
    exec_critical(f"mkdir -p {mount_point}/generations/{generation}", f"Generation setup failed - directory creation")
    exec_critical(
        f"btrfs subvolume create {mount_point}/generations/{generation}/rootfs",
        f"Generation setup failed - subvolume creation",
    )

    # Mounting first generation
    exec_critical(f"umount -R {mount_point}", f"Generation mount failed - unmount")
    exec_critical(
        f"mount -o subvol=generations/{generation}/rootfs {root_part} {mount_point}", f"Generation mount failed - mount"
    )
    partition_list = [
        FsEntry(
            root_part,
            "/",
            "btrfs",
            f"rw,relatime,ssd,space_cache=v2,subvol=generations/{generation}/rootfs",
        )
    ]

    for dir in subdirs + ["boot", "home", "kod"]:
        exec(f"mkdir -p {mount_point}/{dir}")

    exec(f"mount {boot_part} {mount_point}/boot")
    boot_options = (
        "rw,relatime,fmask=0022,dmask=0022,codepage=437,iocharset=ascii,shortname=mixed,utf8,errors=remount-ro"
    )
    partition_list.append(FsEntry(boot_part, "/boot", "vfat", boot_options))

    exec(f"mount {root_part} {mount_point}/kod")
    partition_list.append(FsEntry(root_part, "/kod", "btrfs", "rw,relatime,ssd,space_cache=v2"))

    btrfs_options = "rw,relatime,ssd,space_cache=v2"

    exec(f"mount -o subvol=store/home {root_part} {mount_point}/home")
    partition_list.append(FsEntry(root_part, "/home", "btrfs", btrfs_options + ",subvol=store/home"))

    for dir in subdirs:
        exec(f"mount --bind {mount_point}/kod/store/{dir} {mount_point}/{dir}")
        partition_list.append(FsEntry(f"/kod/store/{dir}", f"/{dir}", "none", "rw,bind"))

    # Write generation number
    with open(f"{mount_point}/.generation", "w") as f:
        f.write(str(generation))

    print("===================================")

    return partition_list
