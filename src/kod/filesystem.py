"""Filesystem and partition management utilities for KodOS.

This module provides functionality for filesystem creation, partition management,
and mount point configuration. It includes support for various filesystem types
and handles fstab entries for system mounting.
"""

from typing import Any, Dict, List, Optional, Tuple

from kod.common import execute #, exec_critical, exec_warn

########################################################################################

def get_lua_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Safely get an attribute from either a dict or Lua table.
    
    Args:
        obj: The object to access (dict or Lua table)
        key: The key/attribute name to retrieve
        default: Default value if key not found
        
    Returns:
        The value at the key, or default if not found
    """
    try:
        if isinstance(obj, dict):
            return obj.get(key, default)
        elif hasattr(obj, "__getitem__"):
            return obj[key]
        elif hasattr(obj, key):
            return getattr(obj, key)
    except (KeyError, TypeError, AttributeError):
        pass
    return default


def has_lua_attr(obj: Any, key: str) -> bool:
    """Check if a dict or Lua table has a key.
    
    Args:
        obj: The object to check (dict or Lua table)
        key: The key/attribute name to check
        
    Returns:
        True if the key exists, False otherwise
    """
    try:
        if isinstance(obj, dict):
            return key in obj
        elif hasattr(obj, "__contains__"):
            return key in obj
        elif hasattr(obj, "__getitem__"):
            _ = obj[key]
            return True
        elif hasattr(obj, key):
            return True
    except (KeyError, TypeError):
        pass
    return False


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

_parted_fs_type: Dict[str, str] = {
    "esp": "esp",
    "btrfs": "linux",
    "linux-swap": "swap",
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
            uuid = execute(f"lsblk -o UUID {self.source} | tail -n 1", get_output=True)
            if uuid:
                return f"UUID={uuid.strip()}"
        return self.source


def create_btrfs(delay_action: List[str], part: Any, blockdevice: str, dry_run: bool = False) -> List[str]:
    """Create BTRFS filesystem with subvolumes and mount configuration.

    This function creates a BTRFS filesystem and sets up subvolumes according
    to the disk_fs_hierarchy partition configuration. It generates mount
    commands and fstab entries for the subvolumes.

    Args:
        delay_action: List of delayed mount commands to execute later.
        part: Partition configuration containing subvolume information.
        blockdevice: Block device path for the BTRFS filesystem.
        dry_run: If True, simulate actions without making changes.

    Returns:
        Updated delay_action list with mount commands for subvolumes.
    """
    print("Creating BTRFS subvolumes")
    fstab_desc = []
    execute(f"mount {blockdevice} /mnt", f"Failed to mount {blockdevice} to /mnt", dry_run=dry_run)

    # Create top-level directories
    directories = get_lua_attr(part, "directories")
    if directories:
        for directory in directories.values():
            execute(f"mkdir -p /mnt/{directory}", dry_run=dry_run)

    # Add root filesystem entry
    fstab_desc.append(FsEntry(blockdevice, "/", "btrfs", "defaults", 0, 0))

    # Process subvolumes from disk_fs_hierarchy format
    subvolumes = get_lua_attr(part, "subvolumes")
    if not subvolumes:
        execute("umount -R /mnt", "Failed to unmount /mnt", dry_run=dry_run)
        return delay_action

    for mountpoint, subvol_info in subvolumes.items():
        subvol = get_lua_attr(subvol_info, "name")
        # mountpoint = mpoint #get_lua_attr(subvol_info, "mountpoint", "")
        options = get_lua_attr(subvol_info, "options", "")

        if not subvol or not mountpoint:
            continue

        create_svol = f"/mnt/{subvol}"
        execute(
            f"btrfs subvolume create {create_svol}",
            f"Failed to create btrfs subvolume {create_svol}",
            dry_run=dry_run,
        )

        # Format mount options
        mount_options = options + "," if options else ""

        install_mountpoint = f"/mnt{mountpoint}"
        mount_cmd = f"mount -o {mount_options}subvol={subvol} {blockdevice} {install_mountpoint}"

        if mountpoint == "/":
            # Root filesystem should be first in delay_action
            delay_action = [mount_cmd] + delay_action
        else:
            # Other mountpoints
            delay_action.append(f"mkdir -p {install_mountpoint}")
            delay_action.append(mount_cmd)

        # Add to fstab
        fstab_entry = FsEntry(blockdevice, mountpoint, "btrfs", f"{mount_options}subvol={subvol}", 0, 0)
        fstab_desc.append(fstab_entry)

    execute("umount -R /mnt", "Failed to unmount /mnt", dry_run=dry_run)
    print("..................................")
    for f in fstab_desc:
        print(f)
    print("..................................")
    return delay_action


def create_partitions(conf: Any, dry_run: bool = False) -> Tuple[Optional[str], Optional[str], List[FsEntry]]:
    """Create partitions for all configured devices.

    This function processes all devices in the configuration and creates
    partitions for each device according to disk_fs_hierarchy format. It identifies
    boot and root partitions and returns them along with a complete partition list.

    Args:
        conf: Configuration object containing device specifications in disk_fs_hierarchy format.
        dry_run: If True, simulate actions without making changes.

    Returns:
        Tuple containing (boot_partition, root_partition, partition_list) where
        boot_partition and root_partition are device paths or None,
        and partition_list contains all created FsEntry objects.
    """
    print("Starting partition creation process")
    print(f"Dry run mode: {'Enabled' if dry_run else 'Disabled'}")
    # Get devices from configuration
    devices = None
    # if hasattr(conf, "devices") and conf.devices:
    #     devices = conf.devices
    if hasattr(conf, "system") and hasattr(conf.system, "devices"):
        devices = conf.system.devices
    
    if not devices:
        raise ValueError("No devices found in configuration. Expected conf.system.devices")
    
    # Convert Lua table to list of values if it's dict-like
    if hasattr(devices, "values"):
        device_list = list(devices.values())
    # elif hasattr(devices, "__iter__"):
    #     device_list = list(devices)
    else:
        device_list = [devices]
    
    # Create partitions for each device and identify boot/root partitions
    print(f"Creating partitions for {len(device_list)} device(s) [{device_list}]")

    boot_partition = None
    root_partition = None
    partition_list = []

    # Process each device in order
    for disk in device_list:
        # Handle Lua table access - get device property safely
        device_name = "unknown"
        try:
            # Try accessing as attribute first (works for Lua tables)
            if hasattr(disk, "device"):
                device_name = disk.device
            # Try dictionary-style access
            # elif hasattr(disk, "__getitem__"):
            #     device_name = disk["device"]
        except (TypeError, KeyError, AttributeError):
            pass
        
        print(f"\nProcessing device: {device_name}")
        boot_part, root_part, part_list = create_disk_partitions(disk, dry_run=dry_run)
        partition_list += part_list
        if boot_part:
            boot_partition = boot_part
        if root_part:
            root_partition = root_part

    return boot_partition, root_partition, partition_list


def create_disk_partitions(
    disk_info: Dict[str, Any], dry_run: bool = False
) -> Tuple[Optional[str], Optional[str], List[FsEntry]]:
    """Create partitions on a single disk device.

    This function handles the creation of partitions on a single disk according
    to the disk_fs_hierarchy format. It wipes the existing partition table,
    creates new partitions with specified filesystems, and sets up mount points
    including BTRFS subvolumes.

    Args:
        disk_info: Dictionary containing device path and partition specifications.
                  Format: {'device': str, 'partitions': [partition_definitions]}

    Returns:
        Tuple containing (boot_partition, root_partition, partitions_list) where
        boot_partition and root_partition are device paths or None,
        and partitions_list contains FsEntry objects for created partitions.
    """
    device = disk_info["device"]
    print(f"Creating partitions for device: {device}")
    print(f"Dry run mode: {'Enabled' if dry_run else 'Disabled'}")
    conf_partitions = disk_info["partitions"]
    wipe_disk = disk_info.wipe if disk_info.wipe is not None else True
    
    print(f"Creating partitions on device: {device}")
    print(f"Device wipe: {'enabled' if wipe_disk else 'disabled'}")

    if "nvme" in device or "mmcblk" in device:
        device_sufix = "p"
    else:
        device_sufix = ""

    # Delete partition table
    if wipe_disk:
        print(f"Wiping existing partition table on {device}")
        execute(f"wipefs -a {device}", f"Failed to wipe partition table on {device}", dry_run=dry_run)
        execute("sync", "Failed to sync after wiping partition table", dry_run=dry_run)

    # Convert Lua table partitions to a list if needed
    # print(f"Partition definitions: {conf_partitions}")
    partitions = list(conf_partitions.values())
    print(f"Partitions to create: {partitions}")

    if disk_info.type is not None and disk_info.type!="gpt":
        raise ValueError(f"Unsupported partition table type: {disk_info.type}. Only 'gpt' is supported.")
    
    # Create GPT partition table
    execute(f"parted -s {device} mklabel gpt", f"Failed to create GPT label on {device}", dry_run=dry_run)

    print(f"Creating partitions on {device}")
    if not partitions:
        return None, None, []

    delay_action = []
    boot_partition = None
    root_partition = None
    partitions_list = []

    for pid, part in enumerate(partitions, 1):
        name = get_lua_attr(part, "name")
        size = get_lua_attr(part, "size")
        filesystem_type = get_lua_attr(part, "type")
        mountpoint = get_lua_attr(part, "mountpoint", "")
        blockdevice = f"{device}{device_sufix}{pid}"

        print(f"Creating partition: {name} ({filesystem_type}) at {blockdevice}")

        # Identify boot and root partitions
        if name.lower() == "boot":
            boot_partition = blockdevice
        elif name.lower() == "root":
            root_partition = blockdevice

        # Calculate partition end
        end = 0 if size == "100%" else f"+{size}"
        partition_type = _parted_fs_type.get(filesystem_type, "linux")

        # Create partition
        execute(
            f"parted -s {device} mkpart {name} {partition_type} 0 {end}",
            f"Failed to create partition {name} on {device}",
            dry_run=dry_run,
        )

        # Format filesystem
        if filesystem_type in _filesystem_cmd.keys():
            cmd = _filesystem_cmd[filesystem_type]
            if cmd:
                execute(
                    f"{cmd} {blockdevice}",
                    f"Failed to format {blockdevice} as {filesystem_type}",
                    dry_run=dry_run,
                )

        # Handle BTRFS with subvolumes
        print(f"Configuring mount for partition {blockdevice} with filesystem {filesystem_type}")
        if filesystem_type == "btrfs":
            delay_action = create_btrfs(delay_action, part, blockdevice, dry_run=dry_run)
        # Handle other filesystems
        elif mountpoint and mountpoint != "none":
            install_mountpoint = f"/mnt{mountpoint}"
            if mountpoint != "/":
                print(f"[DELAY] mkdir -p {install_mountpoint}")
                print(f"[DELAY] mount {blockdevice} {install_mountpoint}")
                delay_action.append(f"mkdir -p {install_mountpoint}")
                delay_action.append(f"mount {blockdevice} {install_mountpoint}")
            else:
                delay_action = [
                    f"mkdir -p {install_mountpoint}",
                    f"mount {blockdevice} {install_mountpoint}",
                ] + delay_action

            partitions_list.append(FsEntry(blockdevice, mountpoint, filesystem_type, "defaults", 0, 0))
            print(f"====> {blockdevice} -> {mountpoint}")

    print("=======================")
    print(f"Executing {len(delay_action)} delayed mount commands...")
    if delay_action:
        for cmd_action in delay_action:
            execute(cmd_action, dry_run=dry_run)
    print("=======================")

    return boot_partition, root_partition, partitions_list


def get_partition_devices(conf: Any) -> Tuple[Optional[str], Optional[str]]:
    """Get boot and root partition device paths from configuration.

    This function scans the device configuration (disk_fs_hierarchy format)
    to identify which devices correspond to boot and root partitions based
    on partition names.

    Args:
        conf: Configuration object containing device specifications in disk_fs_hierarchy format.

    Returns:
        Tuple containing (boot_partition, root_partition) device paths or None if not found.
    """
    devices = conf.devices if hasattr(conf, "devices") else conf.system.devices

    boot_partition = None
    root_partition = None

    for device in devices:
        dev_path = device["device"]
        partitions = device["partitions"]

        if "nvme" in dev_path or "mmcblk" in dev_path:
            device_sufix = "p"
        else:
            device_sufix = ""

        for pid, part in enumerate(partitions, 1):
            name = part["name"]
            blockdevice = f"{dev_path}{device_sufix}{pid}"

            if name.lower() == "boot":
                boot_partition = blockdevice
            elif name.lower() == "root":
                root_partition = blockdevice

    return boot_partition, root_partition
