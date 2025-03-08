from kod.common import exec
########################################################################################

_filesystem_cmd = {
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

_filesystem_type = {
    "esp": "ef00",
    # "vfat": "",
    "btrfs": "8300",
    "linux-swap": "8200",
    "noformat": None,
}


# fstab entry
class FsEntry:
    def __init__(self, source, destination, fs_type, options, dump=0, pass_=0):
        self.source = source
        self.destination = destination
        self.fs_type = fs_type
        self.options = options
        self.dump = dump
        self.pass_ = pass_

    def __str__(self):
        return f"{self.source:<25} {self.destination:<15} {self.fs_type:<10} {self.options:<10} {self.dump:<10} {self.pass_}"

    def mount(self, install_mountpoint):
        if self.fs_type == "btrfs":
            return f"mount -o {self.options} {self.source} {install_mountpoint}{self.destination}"
        if self.fs_type == "none":
            return f"mount --bind {self.source} {install_mountpoint}{self.destination}"
        if self.fs_type == "esp":
            return f"mount -t vfat -o {self.options} {self.source} {install_mountpoint}{self.destination}"
        return f"mount -t {self.fs_type} -o {self.options} {self.source} {install_mountpoint}{self.destination}"

    def source_uuid(self):
        if self.source[:5] == "/dev/":
            uuid = exec(f"lsblk -o UUID {self.source} | tail -n 1", get_output=True)
            if uuid:
                return f"UUID={uuid.strip()}"
        return self.source


def create_btrfs(delay_action, part, blockdevice):
    print("Cheking subvolumes")
    fstab_desc = []
    exec(f"mount {blockdevice} /mnt")
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
        exec(f"btrfs subvolume create {create_svol}")

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

    exec("umount -R /mnt")
    print(".......................")
    for f in fstab_desc:
        print(f)
    print(".......................")
    return delay_action


def create_partitions(conf):
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


def create_disk_partitions(disk_info):
    device = disk_info["device"]
    # efi = disk_info['efi']
    partitions = disk_info["partitions"]

    if "nvme" in device or "mmcblk" in device:
        device_sufix = "p"
    else:
        device_sufix = ""

    # Delete partition table
    exec(f"wipefs -a {device}")
    exec("sync")

    # if efi:
    # Create GPT label
    # exec(f"parted -s {device} mklabel gpt")

    print(f"{partitions=}")
    if not partitions:
        return

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

        exec(f"sgdisk -n 0:0:{end} -t 0:{partition_type} -c 0:{name} {device}")

        # Format filesystem
        if filesystem_type in _filesystem_cmd.keys():
            cmd = _filesystem_cmd[filesystem_type]
            if cmd:
                exec(f"{cmd} {blockdevice}")

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


def get_partition_devices(conf):
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
