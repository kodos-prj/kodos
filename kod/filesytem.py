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

def create_btrfs(c, delay_action, part, blockdevice):
    print("Cheking subvolumes")
    c.run(f"mount {blockdevice} /mnt")
    if not part.subvolumes:
        return delay_action
    for subvol_info in part["subvolumes"].values():
        subvol = subvol_info["subvol"]
        mountpoint = subvol_info["mountpoint"]
        mount_options = subvol_info["mountOptions"]

        create_svol = "/mnt" + subvol
        # print(subvol, mountpoint, mount_options)
        c.run(f"btrfs subvolume create {create_svol}")

        if mount_options:
            mount_options = f"{mount_options},"
        else:
            mount_options = ""
        
        install_mountpoint = "/mnt" + mountpoint
        if mountpoint == "/":
            delay_action = [f"mount -o {mount_options}subvol={subvol} {blockdevice} {install_mountpoint}"] + delay_action
        else:
            delay_action.append(f"mkdir -p {install_mountpoint}")
            delay_action.append(f"mount -o {mount_options}subvol={subvol} {blockdevice} {install_mountpoint}")

    
    # Adding extra subvolumes
    # sv_opts="rw,noatime,compress-force=zstd:1,space_cache=v2"
    # subvolumes = ['/kod', '/etc', '/usr', '/var','/log', '/tmp']
    # mountpoints = ['kod', 'etc', 'usr', 'var', 'kod/log', 'var/tmp']
    # subvolumes = ['/kod', '/log', '/tmp']
    # mountpoints = ['kod', 'kod/log', 'var/tmp']
    # for svol, mpoint in zip(subvolumes, mountpoints):
    #     c.run(f"btrfs subvolume create /mnt{svol}")
    #     delay_action.append(f"mkdir -p /mnt/{mpoint}")
    #     delay_action.append(f"mount -o {sv_opts},subvol={svol} {blockdevice} /mnt/{mpoint}")

    # delay_action.append(f"mkdir -p /mnt/kod/cache")
    # delay_action.append(f"cd /mnt && ln -s /kod/cache var/cache")


    # btrfs subvolume create /mnt/@home
    # btrfs subvolume create /mnt/@snapshots
    # btrfs subvolume create /mnt/@cache
    # btrfs subvolume create /mnt/@libvirt
    # btrfs subvolume create /mnt/@log
    # btrfs subvolume create /mnt/@tmp
    # mkdir -p /mnt/{home,.snapshots,var/cache,var/lib/libvirt,var/log,var/tmp}

    # Mount the additional subvolumes ...

    # mount -o ${sv_opts},subvol=@home /dev/mapper/cryptdev /mnt/home
    # mount -o ${sv_opts},subvol=@snapshots /dev/mapper/cryptdev /mnt/.snapshots
    # mount -o ${sv_opts},subvol=@cache /dev/mapper/cryptdev /mnt/var/cache
    # mount -o ${sv_opts},subvol=@libvirt /dev/mapper/cryptdev /mnt/var/lib/libvirt
    # mount -o ${sv_opts},subvol=@log /dev/mapper/cryptdev /mnt/var/log
    # mount -o ${sv_opts},subvol=@tmp /dev/mapper/cryptdev /mnt/var/tmp


    c.run("umount -R /mnt")
    # mount -o subvol=rootfs /dev/vda3 /mnt
    # mkdir -p /mnt/home
    # mkdir -p /mnt/kod
    # mount -o compress=zstd,subvol=home /dev/vda3 /mnt/home
    # mount -o compress=zstd,noatime,subvol=kod /dev/vda3 /mnt/kod
    
    print(".......................")
    return delay_action

def create_partitions(c, conf):
    devices = conf.devices
    print(f"{devices=}")

    print(f"{list(devices.keys())=}")
    print("->>",devices.disk0)
    for d_id, disk in devices.items():
        print(d_id)
        create_disk_partitions(c, disk)


def create_disk_partitions(c, disk_info):

    device = disk_info['device']
    efi = disk_info['efi']
    partitions = disk_info['partitions']

    if 'nvme' in device or 'mmcblk' in device:
        device_sufix = "p"
    else:
        device_sufix = ""

    # Delete partition table
    c.run(f"wipefs -a {device}")
    c.run('sync')

    # if efi:
        # Create GPT label
        # c.run(f"parted -s {device} mklabel gpt")

    print(f"{partitions=}")
    if not partitions:
        return

    delay_action = []
    boot_partition = None
    root_partition = None
    for pid, part in partitions.items():
        name = part['name']
        size = part['size']
        filesystem_type = part['type']
        mountpoint = part['mountpoint']
        blockdevice = f"{device}{device_sufix}{pid}"
        
        if name == "boot":
            boot_partition = blockdevice
        elif name == "root":
            root_partition = blockdevice

        end = 0 if size == "100%" else f"+{size}"
        partition_type = _filesystem_type[filesystem_type]

        c.run(f"sgdisk -n 0:0:{end} -t 0:{partition_type} -c 0:{name} {device}") 
        
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

    print("=======================")
    if delay_action:
        for cmd_action in delay_action:
                c.run(cmd_action)

    return boot_partition, root_partition

def get_partition_deviced(conf):
    devices = conf.devices

    boot_partition = None
    root_partition = None
    for d_id, disk in devices.items():

        device = disk['device']
        partitions = disk['partitions']

        if 'nvme' in device or 'mmcblk' in device:
            device_sufix = "p"
        else:
            device_sufix = ""

        for pid, part in partitions.items():
            name = part['name']
            blockdevice = f"{device}{device_sufix}{pid}"
            
            if name == "boot":
                boot_partition = blockdevice
            elif name == "root":
                root_partition = blockdevice

    return boot_partition, root_partition