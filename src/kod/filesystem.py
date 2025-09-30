"""Filesystem management functionality for KodOS.

This module handles filesystem operations including Btrfs subvolume management,
fstab generation, filesystem hierarchy creation, mount operations, and partition management.
It includes support for various filesystem types and handles fstab entries for system mounting.
"""

import re
from typing import List, Dict, Optional, Tuple, Any

from kod.common import exec, exec_critical, exec_warn

########################################################################################

_filesystem_cmd: Dict[str, Optional[str]] = {
    "esp": "mkfs.vfat -F32",
    "fat32": "mkfs.vfat -F32",
    "vfat": "mkfs.vfat",
    "bfs": "mkfs.bfs",
    "cramfs": "mkfs.cramfs",
    "ext3": "mkfs.ext3",
    "fat": "mkfs.fat",
    "msdos": "mkfs.msdos",
    "xfs": "mkfs.xfs",
    "btrfs": "mkfs.btrfs -f",
    "ext2": "mkfs.ext2",
    "ext4": "mkfs.ext4",
    "minix": "mkfs.minix",
    "f2fs": "mkfs.f2fs",
    "linux-swap": "mkswap",
    "noformat": None,
}

_filesystem_type: Dict[str, Optional[str]] = {
    "esp": "ef00",
    # "vfat": "",
    "btrfs": "8300",
    "linux-swap": "8200",
    "noformat": None,
}


# # fstab
# source          destination     type    options         dump    pass
# /proc           /proc           none    rw,bind         0       0
# /sys            /sys            none    rw,bind         0       0
# /dev            /dev            none    rw,bind         0       0
# /dev/pts        /dev/pts        none    rw,bind         0       0
# /home           /home           none    rw,bind         0       0
# /usr            /usr            none    rw,bind         0       0
# /tmp            /tmp            none    rw,bind         0       0
# /var/cache	    /var/cache      none	rw,bind		    0   	0
# /var/log	    /var/log        none	rw,bind		    0   	0
# /var/tmp	    /var/tmp        none	rw,bind		    0   	0
# /var/kod	    /var/kod        none	rw,bind		    0   	0
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

    def source_uuid(self) -> str:
        """Get the UUID representation of the source device.

        If the source is a block device path (starts with /dev/), this method
        attempts to retrieve its UUID and return it in UUID= format. Otherwise,
        returns the original source value.

        Returns:
            UUID=<uuid> format string if device has UUID, otherwise the original source.
        """
        if self.source[:5] == "/dev/":
            uuid = exec(f"lsblk -o UUID {self.source} | tail -n 1", get_output=True)
            if uuid:
                return f"UUID={uuid.strip()}"
        return self.source


def generate_fstab(partition_list: List, mount_point: str) -> None:
    """
    Generate a fstab file at the specified mount point based on a list of Partitions.

    Args:
        partition_list (List): A list of Partition objects to be written to the fstab file.
        mount_point (str): The mount point where the fstab file will be written.
    """
    print("Generating fstab")
    with open(f"{mount_point}/etc/fstab", "w") as f:
        for part in partition_list:
            if part.source[:5] == "/dev/":
                uuid = exec(f"lsblk -o UUID {part.source} | tail -n 1", get_output=True)
                if uuid:
                    part.source = f"UUID={uuid.strip()}"
            f.write(str(part) + "\n")


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


def create_filesystem_hierarchy(boot_part: str, root_part: str, partition_list: List, mount_point: str) -> List:
    """
    Create and configure a Btrfs filesystem hierarchy for KodOS.

    This function sets up the initial filesystem hierarchy for KodOS using Btrfs
    subvolumes. It creates necessary directories and subvolumes, mounts the first
    generation, and binds the appropriate directories. It also creates and mounts
    the boot and kod partitions.

    Args:
        boot_part (str): The boot partition to be mounted.
        root_part (str): The root partition to be used for creating subvolumes.
        partition_list: A list of Partition objects representing the filesystem hierarchy.
        mount_point (str): The mount point where the filesystem hierarchy will be created.

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


def create_btrfs(delay_action: List[str], part: Any, blockdevice: str) -> List[str]:
    """Create BTRFS filesystem with subvolumes and mount configuration.

    This function creates a BTRFS filesystem and sets up subvolumes according
    to the partition configuration. It generates mount commands and fstab entries
    for the subvolumes.

    Args:
        delay_action: List of delayed mount commands to execute later.
        part: Partition configuration containing subvolume information.
        blockdevice: Block device path for the BTRFS filesystem.

    Returns:
        Updated delay_action list with mount commands for subvolumes.
    """
    print("Cheking subvolumes")
    fstab_desc = []
    exec_critical(f"mount {blockdevice} /mnt", f"Failed to mount {blockdevice} to /mnt")

    fstab_desc.append(FsEntry(blockdevice, "/", "btrfs", "defaults", 0, 0))
    print(fstab_desc[0])
    print(fstab_desc[0].mount("/mnt"))
    if not part.subvolumes:
        return delay_action
    for subvol_info in part["subvolumes"].values():
        subvol = subvol_info["subvol"]
        mountpoint = subvol_info["mountpoint"]
        mount_options = subvol_info["mountOptions"]

        create_svol = "/mnt" + subvol
        # print(subvol, mountpoint, mount_options)
        exec_critical(f"btrfs subvolume create {create_svol}", f"Failed to create btrfs subvolume {create_svol}")

        if mount_options:
            mount_options = f"{mount_options},"
        else:
            mount_options = ""

        install_mountpoint = "/mnt" + mountpoint
        if mountpoint == "/":
            delay_action = [
                f"mount -o {mount_options}subvol={subvol} {blockdevice} {install_mountpoint}"
            ] + delay_action
            fstab_desc.append(FsEntry(blockdevice, mountpoint, "btrfs", f"{mount_options}subvol={subvol}", 0, 0))
        else:
            delay_action.append(f"mkdir -p {install_mountpoint}")
            delay_action.append(f"mount -o {mount_options}subvol={subvol} {blockdevice} {install_mountpoint}")
            fstab_desc.append(FsEntry(blockdevice, mountpoint, "btrfs", f"{mount_options}subvol={subvol}", 0, 0))
        # partition_list.append((blockdevice, subvol, mountpoint))

    exec_warn("umount -R /mnt", "Failed to unmount /mnt")
    print(".......................")
    for f in fstab_desc:
        print(f)
    print(".......................")
    return delay_action


def create_partitions(conf: Any) -> Tuple[Optional[str], Optional[str], List[FsEntry]]:
    """Create partitions for all configured devices.

    This function processes all devices in the configuration and creates
    partitions for each device. It identifies boot and root partitions
    and returns them along with a complete partition list.

    Args:
        conf: Configuration object containing device specifications.

    Returns:
        Tuple containing (boot_partition, root_partition, partition_list) where
        boot_partition and root_partition are device paths or None,
        and partition_list contains all created FsEntry objects.
    """
    devices = conf.devices
    print(f"{devices=}")

    print(f"{list(devices.keys())=}")
    print("->>", devices.disk0)
    boot_partition = None
    root_partition = None
    partition_list = []
    for d_id, disk in devices.items():
        print(d_id)
        boot_part, root_part, part_list = create_disk_partitions(disk)
        partition_list += part_list
        if boot_part:
            boot_partition = boot_part
        if root_part:
            root_partition = root_part
    return boot_partition, root_partition, partition_list


def create_disk_partitions(disk_info: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], List[FsEntry]]:
    """Create partitions on a single disk device.

    This function handles the creation of partitions on a single disk according
    to the disk configuration. It wipes the existing partition table, creates
    new partitions with specified filesystems, and sets up mount points.

    Args:
        disk_info: Dictionary containing device path and partition specifications.
                  Expected keys: 'device', 'partitions'

    Returns:
        Tuple containing (boot_partition, root_partition, partitions_list) where
        boot_partition and root_partition are device paths or None,
        and partitions_list contains FsEntry objects for created partitions.
    """
    device = disk_info["device"]
    # efi = disk_info['efi']
    partitions = disk_info["partitions"]

    if "nvme" in device or "mmcblk" in device:
        device_sufix = "p"
    else:
        device_sufix = ""

    # Delete partition table
    exec_critical(f"wipefs -a {device}", f"Failed to wipe partition table on {device}")
    exec_critical("sync", "Failed to sync after wiping partition table")

    # if efi:
    # Create GPT label
    # exec(f"parted -s {device} mklabel gpt")

    print(f"{partitions=}")
    if not partitions:
        return None, None, []

    delay_action = []
    boot_partition = None
    root_partition = None
    partitions_list = []
    for pid, part in partitions.items():
        name = part["name"]
        size = part["size"]
        filesystem_type = part["type"]
        mountpoint = part["mountpoint"]
        blockdevice = f"{device}{device_sufix}{pid}"

        if name.lower() == "boot":
            boot_partition = blockdevice
        elif name.lower() == "root":
            root_partition = blockdevice

        end = 0 if size == "100%" else f"+{size}"
        partition_type = _filesystem_type[filesystem_type]

        exec_critical(
            f"sgdisk -n 0:0:{end} -t 0:{partition_type} -c 0:{name} {device}",
            f"Failed to create partition {name} on {device}",
        )

        # Format filesystem
        if filesystem_type in _filesystem_cmd.keys():
            cmd = _filesystem_cmd[filesystem_type]
            if cmd:
                exec_critical(f"{cmd} {blockdevice}", f"Failed to format {blockdevice} as {filesystem_type}")

        if filesystem_type == "btrfs":
            delay_action = create_btrfs(delay_action, part, blockdevice)

        if mountpoint and mountpoint != "none":
            install_mountpoint = "/mnt" + mountpoint
            if mountpoint != "/":
                print(f"[DELAY] mkdir -p {install_mountpoint}")
                print(f"[DELAY] mount {blockdevice} {install_mountpoint}")
                delay_action.append(f"mkdir -p {install_mountpoint}")
                delay_action.append(f"mount {blockdevice} {install_mountpoint}")
                partitions_list.append(FsEntry(blockdevice, mountpoint, filesystem_type, "defaults", 0, 0))
            else:
                delay_action = [
                    f"mkdir -p {install_mountpoint}",
                    f"mount {blockdevice} {install_mountpoint}",
                ] + delay_action
                partitions_list.append(FsEntry(blockdevice, mountpoint, filesystem_type, "defaults", 0, 0))
            print("====>", blockdevice, mountpoint)

    print("=======================")
    if delay_action:
        for cmd_action in delay_action:
            exec(cmd_action)
    print("=======================")

    return boot_partition, root_partition, partitions_list


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
