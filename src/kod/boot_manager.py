"""Boot and Generation Management Module for KodOS.

This module handles bootloader setup, boot entry creation, and generation management.
"""

import glob
import os
from pathlib import Path
from typing import Any, List, Optional

from .common import exec, exec_chroot


def create_boot_entry(
    generation: int,
    partition_list: List,
    boot_options: Optional[List[str]] = None,
    is_current: bool = False,
    mount_point: str = "/mnt",
    kver: Optional[str] = None,
) -> None:
    """
    Create a systemd-boot loader entry for the specified generation.

    Args:
        generation (int): The generation number to create an entry for.
        partition_list (list): A list of Partition objects to use for determining the root device.
        boot_options (list, optional): A list of additional boot options to include in the entry.
        is_current (bool, optional): If True, the entry will be named "kodos" and set as the default.
        mount_point (str, optional): The mount point of the chroot environment to write the entry to.
        kver (str, optional): The kernel version to use in the entry. If not provided, the current kernel
            version will be determined automatically.
    """
    subvol = f"generations/{generation}/rootfs"
    root_fs = [part for part in partition_list if part.destination in ["/"]][0]
    root_device = root_fs.source_uuid()
    options = " ".join(boot_options) if boot_options else ""
    options += f" rootflags=subvol={subvol}"
    entry_name = "kodos" if is_current else f"kodos-{generation}"

    if not kver:
        from kod.system_config import get_kernel_version

        kver = get_kernel_version(mount_point)

    today = exec("date +'%Y-%m-%d %H:%M:%S'", get_output=True).strip()
    entry_conf = f"""
title KodOS
sort-key kodos
version Generation {generation} KodOS (build {today} - {kver})
linux /vmlinuz-{kver}
initrd /initramfs-linux-{kver}.img
options root={root_device} rw {options}
    """
    entries_path = Path(f"{mount_point}/boot/loader/entries/")
    if not entries_path.is_dir():
        entries_path.mkdir(parents=True, exist_ok=True)
    with open(f"{mount_point}/boot/loader/entries/{entry_name}.conf", "w") as f:
        f.write(entry_conf)

    # Update loader.conf
    loader_conf_systemd = f"""
default {entry_name}.conf
timeout 10
console-mode keep
"""
    with open(f"{mount_point}/boot/loader/loader.conf", "w") as f:
        f.write(loader_conf_systemd)


def setup_bootloader(conf: Any, partition_list: List, dist: Any) -> None:
    """
    Set up the bootloader based on the configuration.

    Args:
        conf (dict): The configuration dictionary.
        partition_list (list): A list of Partition objects to use for determining the root device.
        dist (Any): The distribution object for setup operations.
    """
    boot_conf = conf.boot
    loader_conf = boot_conf["loader"]

    if "kernel" in boot_conf and "package" in boot_conf["kernel"]:
        kernel_package = boot_conf["kernel"]["package"]
    else:
        kernel_package = "linux"

    # Default bootloader
    boot_type = "systemd-boot"

    if "type" in loader_conf:
        boot_type = loader_conf["type"]

    # Using systemd-boot as bootloader
    if boot_type == "systemd-boot":
        print("==== Setting up systemd-boot ====")
        kver = dist.setup_linux(kernel_package)
        exec_chroot("bootctl install")
        print("KVER:", kver)
        exec_chroot(f"dracut --kver {kver} --hostonly /boot/initramfs-linux-{kver}.img")
        create_boot_entry(0, partition_list, mount_point="/mnt", kver=kver)

    # Using Grub as bootloader
    if boot_type == "grub":
        pass


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
    from kod.filesystem import load_fstab, change_subvol, generate_fstab

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
