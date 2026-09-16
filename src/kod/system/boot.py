"""Boot management operations (Phase 2).

Handles bootloader configuration, kernel selection, and boot entry management.
"""

from pathlib import Path
from typing import Callable, Tuple

from kod.system.distro.factory import get_distro_module
from kod.common import exec, exec_chroot


# Re-export for backward compatibility with tests
# This function was moved to distro-specific modules
def get_kernel_file(mount_point: str, package: str = "linux") -> Tuple[str, str]:
    """Get kernel file path and version (re-exported from distro module).
    
    Args:
        mount_point: Path to mounted root filesystem
        package: Kernel package name (default: "linux")
        
    Returns:
        Tuple of (kernel_file_path, kernel_version)
    """
    # For tests and default usage, use Arch
    from kod.system.distro.arch import get_kernel_file as arch_get_kernel
    return arch_get_kernel(mount_point, package)


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
    
    The initramfs filename includes the full kernel version to support multiple
    generations, each with potentially different kernel versions and initramfs.
    """

    def hook() -> None:
        _kernel_file, kver = get_kernel_file(mount_point, package=kernel_package)
        root_device = _read_root_device(f"{mount_point}/etc/fstab")
        subvol = f"generations/{generation}/rootfs"
        entry_name = f"kodos-{generation}"
        today = exec("date +'%Y-%m-%d %H:%M:%S'", get_output=True).strip()
        
        # Initramfs filename includes kernel version to support multiple generations
        # Each generation can have a different kernel version and thus different initramfs
        initramfs_name = f"initramfs-linux-{kver}.img"
        
        entry_conf = f"""
title KodOS
sort-key kodos
version Generation {generation} KodOS (build {today} - {kver})
linux /vmlinuz-{kver}
initrd /{initramfs_name}
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
        kernel_file, kver = get_kernel_file(mount_point, package=kernel_package)
        print(f"{kver=}")
        print(f"cp {kernel_file} /boot/vmlinuz-{kver}")
        exec_chroot(f"cp {kernel_file} /boot/vmlinuz-{kver}", mount_point=mount_point)

    return hook


def update_initramfs_hook(kernel_package: str, mount_point: str) -> Callable[[], None]:
    """
    Create a hook function to generate the initramfs using dracut.

    This function generates a hook that, when executed, creates an initramfs
    file with the kernel version embedded in the filename. This allows multiple
    generations to have different initramfs files if they use different kernels.

    Args:
        kernel_package (str): The name of the kernel package to update.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        function: A hook function that generates the initramfs.
        
    Raises:
        RuntimeError: If dracut is not available or generation fails.
    """

    def hook() -> None:
        print(f"Generating initramfs for {kernel_package} using dracut...")
        distro = get_distro_module("arch")
        kernel_file, kver = distro.get_kernel_file(mount_point, package=kernel_package)
        print(f"Kernel version: {kver}")
        
        # Verify dracut is installed by checking if /usr/bin/dracut exists
        # Don't use 'which' as it may not be in base system
        try:
            exec_chroot(
                "test -x /usr/bin/dracut",
                mount_point=mount_point,
            )
        except Exception as e:
            raise RuntimeError(
                f"dracut not found in chroot at {mount_point}. "
                "dracut should be installed as part of base packages. "
                f"Error: {e}"
            )
        
        # Generate initramfs with kernel version in filename
        # dracut will create: /boot/initramfs-linux-<kver>.img
        output_file = f"initramfs-linux-{kver}.img"
        print(f"Running: dracut --kver {kver} --hostonly --force /boot/{output_file}")
        
        try:
            exec_chroot(
                f"dracut --kver {kver} --hostonly --force /boot/{output_file}",
                mount_point=mount_point,
            )
        except Exception as e:
            raise RuntimeError(
                f"dracut failed to generate initramfs: {e}. "
                f"Check dracut logs and kernel module configuration."
            )
        
        # Verify the file was created
        boot_initramfs = Path(f"{mount_point}/boot/{output_file}")
        if not boot_initramfs.exists():
            raise RuntimeError(
                f"Initramfs generation failed: expected {output_file} not found in /boot. "
                f"dracut may have failed silently. Check chroot logs."
            )
        print(f"✅ Initramfs generated: {output_file}")

    return hook
