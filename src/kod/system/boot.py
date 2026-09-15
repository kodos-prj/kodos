"""Boot management operations (Phase 2).

Handles bootloader configuration, kernel selection, and boot entry management.
"""

from pathlib import Path
from typing import Callable

from kod.system.distro.factory import get_distro_module
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


def _read_root_device(fstab_path: str) -> str:
    """Return the device field (e.g. 'UUID=...') of the '/' entry in an fstab."""
    with open(fstab_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) >= 2 and fields[1] == "/":
                return fields[0]
    raise RuntimeError(f"No '/' entry found in {fstab_path}")


def create_boot_entry_hook(generation: int, kernel_package: str, mount_point: str) -> Callable[[], None]:
    """Create a hook that writes a systemd-boot entry + loader.conf for a generation.

    Self-contained: kver is derived from the installed kernel package and the root
    device UUID is read from the target fstab (single source of truth). The subvol is
    always generations/<generation>/rootfs, so this works identically for install
    (gen 0) and rebuild (gen N) regardless of which generation the fstab points at.
    """

    def hook() -> None:
        distro = get_distro_module("arch")
        _kernel_file, kver = distro.get_kernel_file(mount_point, package=kernel_package)
        root_device = _read_root_device(f"{mount_point}/etc/fstab")
        subvol = f"generations/{generation}/rootfs"
        entry_name = f"kodos-{generation}"
        today = exec("date +'%Y-%m-%d %H:%M:%S'", get_output=True).strip()
        entry_conf = f"""
title KodOS
sort-key kodos
version Generation {generation} KodOS (build {today} - {kver})
linux /vmlinuz-{kver}
initrd /initramfs-linux-{kver}.img
options root={root_device} rw rootflags=subvol={subvol}
    """
        entries_path = Path(f"{mount_point}/boot/loader/entries/")
        entries_path.mkdir(parents=True, exist_ok=True)
        with open(f"{entries_path}/{entry_name}.conf", "w") as f:
            f.write(entry_conf)

        loader_conf = f"""
default {entry_name}.conf
timeout 10
console-mode keep
"""
        with open(f"{mount_point}/boot/loader/loader.conf", "w") as f:
            f.write(loader_conf)

    return hook


def update_kernel_hook(kernel_package: str, mount_point: str) -> Callable[[], None]:
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
        distro = get_distro_module("arch")
        kernel_file, kver = distro.get_kernel_file(mount_point, package=kernel_package)
        print(f"{kver=}")
        print(f"cp {kernel_file} /boot/vmlinuz-{kver}")
        exec_chroot(f"cp {kernel_file} /boot/vmlinuz-{kver}", mount_point=mount_point)

    return hook


def update_initramfs_hook(kernel_package: str, mount_point: str) -> Callable[[], None]:
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
        distro = get_distro_module("arch")
        kernel_file, kver = distro.get_kernel_file(mount_point, package=kernel_package)
        exec_chroot(
            f"dracut --kver {kver} --hostonly /boot/initramfs-linux-{kver}.img",
            mount_point=mount_point,
        )

    return hook
