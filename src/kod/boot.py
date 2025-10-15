"""Bootloader configuration and management for KodOS."""

from pathlib import Path
from typing import List, Optional, Callable

from kod.common import exec, exec_chroot


def get_kernel_version(mount_point: str) -> str:
    """
    Retrieve the kernel version from the specified mount point.

    Args:
        mount_point (str): The mount point of the chroot environment to retrieve the kernel version from.

    Returns:
        str: The kernel version as a string.
    """
    kernel_version = exec_chroot("uname -r", mount_point=mount_point, get_output=True).strip()
    return kernel_version


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
            version will be determined using `uname -r` in the chroot environment.
    """
    subvol = f"generations/{generation}/rootfs"
    root_fs = [part for part in partition_list if part.destination in ["/"]][0]
    root_device = root_fs.source_uuid()
    options = " ".join(boot_options) if boot_options else ""
    options += f" rootflags=subvol={subvol}"
    entry_name = "kodos" if is_current else f"kodos-{generation}"

    if not kver:
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


def setup_bootloader(conf: any, partition_list: List, dist: any) -> None:
    # bootloader
    """
    Set up the bootloader based on the configuration.

    Args:
        conf (dict): The configuration dictionary.
        partition_list (list): A list of Partition objects to use for determining the root device.
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


def update_kernel_hook(kernel_package: str, mount_point: str, dist: any) -> Callable[[], None]:
    """
    Create a hook function to update the kernel for a specified package.

    This function generates a hook that, when executed, copies the kernel file
    for the specified kernel package from the chroot environment at the given
    mount point to the /boot directory with a versioned filename.

    Args:
        kernel_package (str): The name of the kernel package to update.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        function: A hook function that performs the kernel update.
    """

    def hook() -> None:
        print(f"Update kernel ....{kernel_package}")
        kernel_file, kver = dist.get_kernel_file(mount_point, package=kernel_package)
        print(f"{kver=}")
        print(f"cp {kernel_file} /boot/vmlinuz-{kver}")
        exec_chroot(f"cp {kernel_file} /boot/vmlinuz-{kver}", mount_point=mount_point)

    return hook


def update_initramfs_hook(kernel_package: str, mount_point: str, dist: any) -> Callable[[], None]:
    """
    Create a hook function to update the initramfs for a specified package.

    This function generates a hook that, when executed, generates an initramfs
    file for the specified kernel package from the chroot environment at the
    given mount point.

    Args:
        kernel_package (str): The name of the kernel package to update.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        function: A hook function that performs the initramfs update.
    """

    def hook() -> None:
        print(f"Update initramfs ....{kernel_package}")
        _, kver = dist.get_kernel_file(mount_point, package=kernel_package)
        exec_chroot(
            f"dracut --kver {kver} --hostonly /boot/initramfs-linux-{kver}.img",
            mount_point=mount_point,
        )

    return hook
