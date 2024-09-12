########################################################################################

from .units import add_value_unit, convert2byte


_filesystem_cmd = {
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
    "swap": "mkswap",
    "noformat": None,
}


# wipefs -a /dev/vda
# sync

# parted -s /dev/vda mklabel gpt

# ---- 1 -----
# parted -s /dev/vda -a opt mkpart Boot fat32 1 1024MiB
# parted -s /dev/vda set 1 boot on
# mkfs.vfat -F32 /dev/vda1
#### parted -s /dev/vda set 1 esp on

# ---- 2 -----
# parted -s /dev/vda -a opt mkpart Swap linux-swap 1024MiB 2048MiB
# mkswap /dev/vda2

# ---- 3 ----
# parted -s /dev/vda -a opt mkpart Root btrfs 2048MiB 100%
# mkfs.btrfs /dev/vda3
# mount /dev/vda3 /mnt

# btrfs subvolume create /mnt/rootfs
# btrfs subvolume create /mnt/home
# btrfs subvolume create /mnt/kod

# umount /mnt
# mount -o subvol=rootfs /dev/vda3 /mnt
# mkdir -p /mnt/home
# mkdir -p /mnt/kod
# mount -o compress=zstd,subvol=home /dev/vda3 /mnt/home
# mount -o compress=zstd,noatime,subvol=kod /dev/vda3 /mnt/kod


def create_btrfs(c,delay_action, part, blockdevice):
    print("Cheking subvolumes")
    c.run(f"mount {blockdevice} /mnt")
    for subvol_info in part["subvolumes"].values():
        subvol = subvol_info["subvol"]
        mountpoint = subvol_info["mountpoint"]
        mount_options = subvol_info["mountOptions"]

        install_mountpoint = "/mnt" + subvol
        # print(subvol, mountpoint, mount_options)
        c.run(f"btrfs subvolume create {install_mountpoint}")

        if mount_options:
            mount_options = f"{mount_options},"
        else:
            mount_options = ""
        
        if mountpoint == "/":
            install_mountpoint = "/mnt" + mountpoint
            delay_action = [f"mount -o {mount_options}subvol={subvol} {blockdevice} {install_mountpoint}"] + delay_action
        else:
            delay_action.append(f"mkdir -p {install_mountpoint}")
            delay_action.append(f"mount -o {mount_options}subvol={subvol} {blockdevice} {install_mountpoint}")

    c.run("umount /mnt")
    # mount -o subvol=rootfs /dev/vda3 /mnt
    # mkdir -p /mnt/home
    # mkdir -p /mnt/kod
    # mount -o compress=zstd,subvol=home /dev/vda3 /mnt/home
    # mount -o compress=zstd,noatime,subvol=kod /dev/vda3 /mnt/kod
    
    print(".......................")
    return delay_action


def create_partitions(c, disk_info):

    device = disk_info['device']
    efi = disk_info['efi']
    # efi_size = disk_info['efi_size']
    partitions = disk_info['partitions']
# Filesystem

    if 'nvme' in device or 'mmcblk' in device:
        device_sufix = "p"
    else:
        device_sufix = ""

    # Delete partition table
    c.run(f"wipefs -a {device}")
    c.run('sync')

    if efi:
        # Create GPT label
        c.run(f"parted -s {device} mklabel gpt")

    print(f"{partitions=}")
    if not partitions:
        return

    start = "1048KiB"
    delay_action = []
    for pid, part in partitions.items():

        # print(pid, part)
        name = part['name']
        size = part['size']
        filesystem_type = part['type']
        mountpoint = part['mountpoint']
        blockdevice = f"{device}{device_sufix}{pid}"
        end = "{}{}".format(*add_value_unit(start, size))

        print(f"{pid} {name=}, {size=}, {filesystem_type=}, {mountpoint=} {blockdevice=}")

        c.run(f"parted -s {device} -a opt mkpart {name} {filesystem_type} {start} {end}")

        # Format filesystem
        if filesystem_type in _filesystem_cmd.keys():
            cmd = _filesystem_cmd[filesystem_type]
            if cmd:
                c.run(f"{cmd} {blockdevice}")

        if filesystem_type == "btrfs":
            delay_action = create_btrfs(c,delay_action, part, blockdevice)

        if mountpoint and mountpoint != 'none':
            install_mountpoint = "/mnt" + mountpoint
            if mountpoint != "/":
                print(f"[DELAY] mkdir -p {install_mountpoint}")
                print(f"[DELAY] mount {blockdevice} {install_mountpoint}")
                delay_action.append(f"mkdir -p {install_mountpoint}")
                delay_action.append(f"mount {blockdevice} {install_mountpoint}")
            else:
                delay_action = [
                    f"mkdir -p {install_mountpoint}",
                    f"mount {blockdevice} {install_mountpoint}"
                ] + delay_action

            start = end

    print("=======================")
    if delay_action:
        for cmd_action in delay_action:
                c.run(cmd_action)

