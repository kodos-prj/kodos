"""Generation management for KodOS.

Handles generation lifecycle: creation, mounting, fstab management, and subvolume operations.
A generation is an immutable snapshot of the system state with its own rootfs, boot, and home mounts.
"""

import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from kod.common import exec


class FsEntry:
    """Represents a filesystem entry for fstab configuration.

    This class encapsulates filesystem mount information including source device,
    destination mountpoint, filesystem type, mount options, and dump/pass values
    used in fstab entries.

    Attributes:
        source (str): Source device or UUID
        destination (str): Mount point destination path
        fs_type (str): Filesystem type (e.g., 'ext4', 'btrfs', 'vfat')
        options (str): Mount options (e.g., 'defaults', 'rw,bind')
        dump (int): Backup frequency for dump utility (usually 0 or 1)
        pass_ (int): Filesystem check order (0=no check, 1=root, 2=other)
    """

    def __init__(
        self, source: str, destination: str, fs_type: str, options: str, dump: int = 0, pass_: int = 0
    ) -> None:
        """Initialize a filesystem entry.

        Args:
            source: Source device path or UUID
            destination: Mount point destination
            fs_type: Filesystem type
            options: Mount options string
            dump: Dump backup frequency. Defaults to 0.
            pass_: Filesystem check pass number. Defaults to 0.
        """
        self.source = source
        self.destination = destination
        self.fs_type = fs_type
        self.options = options
        self.dump = dump
        self.pass_ = pass_

    def __str__(self) -> str:
        """Return a formatted string representation of the fstab entry.

        Returns:
            Formatted fstab entry with proper column alignment.
        """
        return (
            f"{self.source:<25} {self.destination:<15} {self.fs_type:<10} "
            f"{self.options:<10} {self.dump:<10} {self.pass_}"
        )

    def mount(self, install_mountpoint: str) -> str:
        """Generate mount command for this filesystem entry.

        Args:
            install_mountpoint: Base installation mount point path.

        Returns:
            Mount command string for this filesystem entry.
        """
        if self.fs_type == "btrfs":
            return f"mount -o {self.options} {self.source} {install_mountpoint}{self.destination}"
        if self.fs_type == "none":
            return f"mount --bind {self.source} {install_mountpoint}{self.destination}"
        if self.fs_type == "esp":
            return f"mount -t vfat -o {self.options} {self.source} {install_mountpoint}{self.destination}"
        return f"mount -t {self.fs_type} -o {self.options} {self.source} {install_mountpoint}{self.destination}"


def get_partition_devices(conf: Any) -> Tuple[Optional[str], Optional[str]]:
    """Get boot and root partition device paths from configuration.

    This function scans the device configuration to identify which devices
    correspond to boot and root partitions based on partition names.

    Args:
        conf: Configuration object containing device specifications.

    Returns:
        Tuple containing (boot_partition, root_partition) device paths or None if not found.
    """
    devices = conf.devices

    if devices is None:
        return None, None

    boot_partition = None
    root_partition = None
    for d_id, disk in devices.items():
        device = disk["device"]
        partitions = disk["partitions"]

        if "nvme" in device or "mmcblk" in device:
            device_sufix = "p"
        else:
            device_sufix = ""

        for pid, part in partitions.items():
            name = part["name"]
            blockdevice = f"{device}{device_sufix}{pid}"

            if name.lower() == "boot":
                boot_partition = blockdevice
            elif name.lower() == "root":
                root_partition = blockdevice

    return boot_partition, root_partition


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


def get_max_generation() -> int:
    """Retrieve the highest numbered generation directory in /kod/generations.

    If no generation directories exist, return 0.
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
