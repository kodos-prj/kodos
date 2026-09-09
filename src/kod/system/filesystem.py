"""Filesystem operations (Phase 2).

Handles partitioning, mount point management, fstab, and subvolume operations.
Phase 2b: moved implementations from kod._core to here.
"""

import re
from pathlib import Path
from typing import Any, Dict, List

from kod.common import exec, exec_critical
from kod.filesystem import FsEntry


def generate_fstab(partiton_list: List, mount_point: str) -> None:
    """
    Generate a fstab file at the specified mount point based on a list of Partitions.

    Args:
        partiton_list (List): A list of Partition objects to be written to the fstab file.
        mount_point (str): The mount point where the fstab file will be written.
    """
    print("Generating fstab")
    with open(f"{mount_point}/etc/fstab", "w") as f:
        for part in partiton_list:
            if part.source[:5] == "/dev/":
                uuid = exec(f"lsblk -o UUID {part.source} | tail -n 1", get_output=True)
                if uuid:
                    part.source = f"UUID={uuid.strip()}"
            f.write(str(part) + "\n")


def load_fstab(root_path: str = "") -> List[str]:
    """
    Load a list of Partition objects from the specified fstab file.

    This function reads the specified fstab file, parses its entries, and
    returns a list of Partition objects representing the filesystem
    hierarchy described in the file. The Partition objects are created
    using the FsEntry class.

    Args:
        root_path (str, optional): The root path from which to read the
            fstab file. Defaults to the current working directory.

    Returns:
        list: A list of Partition objects representing the filesystem
            hierarchy described in the fstab file.
    """
    partition_list = []
    with open(f"{root_path}/etc/fstab") as f:
        entries = f.readlines()

    for entry in entries:
        if not entry or entry == "\n" or entry.startswith("#"):
            continue
        (device, mount_point, fs_type, options, dump, pass_) = entry.split()
        partition_list.append(FsEntry(device, mount_point, fs_type, options, int(dump), int(pass_)))
    return partition_list


def update_fstab(root_path: str, new_mount_point_map: Dict[str, str]) -> None:
    """
    Update the fstab file at the specified root path with new subvolume IDs for specified mount points.

    This function reads the existing fstab file, modifies the subvolume options for mount points
    present in the `new_mount_point_map`, and writes the updated lines back to the fstab file.

    Args:
        root_path (str): The root path where the fstab file is located.
        new_mount_point_map (dict): A dictionary mapping mount points to their new subvolume IDs.

    """
    with open(f"{root_path}/etc/fstab") as f:
        fstab = f.readlines()
    with open(f"{root_path}/etc/fstab", "w") as f:
        for line in fstab:
            cols = line.split()
            if len(cols) > 4 and cols[1] in new_mount_point_map:
                subvol_id = new_mount_point_map[cols[1]]
                cols[3] = re.sub(r"subvol=[^,]+", f"subvol={subvol_id}", cols[3])
                line = "\t".join(cols) + "\n"
            f.write(line)


def change_subvol(partition_list: List, subvol: str, mount_points: List[str]) -> List:
    """
    Modify the partition list by changing the subvolume of the given mount points to the given subvolume.

    Args:
        partition_list (list): The list of Partition objects to modify.
        subvol (str): The new subvolume.
        mount_points (list): The list of mount points to modify.

    Returns:
        list: The modified partition list.
    """
    for part in partition_list:
        if part.destination in mount_points:
            options = part.options.split(",")
            for opt in options:
                if opt.startswith("subvol="):
                    subvol_path = opt.split("/")[-1]
                    part.options = part.options.replace(opt, f"subvol={subvol}/{subvol_path}")
    return partition_list


def set_ro_mount(mount_point: str) -> None:
    """
    Set the given mount point to be read-only.

    This function takes a mount point and mounts it read-only. This is useful for
    making sure that the system files are not modified during the installation
    process.

    Args:
        mount_point (str): The mount point to set to read-only.
    """
    exec(f"mount -o remount,ro,bind {mount_point}")


def change_ro_mount(root_path: str) -> None:
    """
    Modify the fstab file at the given root path to mount /usr read-only.

    This function reads the existing fstab file, modifies the mount options for /usr
    to be read-only, and writes the updated lines back to the fstab file.

    Args:
        root_path (str): The root path where the fstab file is located.
    """
    with open(f"{root_path}/etc/fstab") as f:
        fstab = f.readlines()
    with open(f"{root_path}/etc/fstab", "w") as f:
        for line in fstab:
            if "/usr" in line:
                line = line.replace("rw,", "ro,")
            f.write(line)


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
        import os
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
