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
    
    The initramfs filename follows Arch's mkinitcpio convention: initramfs-{KERNEL_NAME}.img
    E.g., "linux" package → /initramfs-linux.img, "linux-lts" → /initramfs-linux-lts.img
    """

    def hook() -> None:
        _kernel_file, kver = get_kernel_file(mount_point, package=kernel_package)
        root_device = _read_root_device(f"{mount_point}/etc/fstab")
        subvol = f"generations/{generation}/rootfs"
        entry_name = f"kodos-{generation}"
        today = exec("date +'%Y-%m-%d %H:%M:%S'", get_output=True).strip()
        
        # Initramfs filename follows mkinitcpio convention: initramfs-{kernel_package}.img
        # This is generated automatically by the kernel package's post-install hook
        initramfs_name = f"initramfs-{kernel_package}.img"
        
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
    Create a hook function to verify and locate the initramfs for a specified package.

    On Arch Linux, the kernel package post-install hooks automatically generate
    the initramfs via mkinitcpio. This hook verifies the initramfs was created
    successfully and determines its actual filename (which varies by kernel package).

    Args:
        kernel_package (str): The name of the kernel package (e.g., "linux", "linux-lts").
        mount_point (str): The mount point of the chroot environment.

    Returns:
        function: A hook function that verifies the initramfs exists.
    """

    def hook() -> None:
        print(f"Verifying initramfs for {kernel_package}...")
        distro = get_distro_module("arch")
        kernel_file, kver = distro.get_kernel_file(mount_point, package=kernel_package)
        
        # On Arch, the kernel package post-install hook runs mkinitcpio automatically.
        # mkinitcpio generates initramfs-{KERNEL_PACKAGE_NAME}.img in /boot
        # E.g., for "linux" package → initramfs-linux.img
        # E.g., for "linux-lts" package → initramfs-linux-lts.img
        
        # Map kernel package name to its initramfs filename prefix
        # The pattern is: initramfs-{prefix-derived-from-package-name}.img
        initramfs_prefix = kernel_package.replace("linux", "initramfs")
        if not initramfs_prefix.startswith("initramfs"):
            # Fallback: assume pattern like "linux-custom" → "initramfs-linux-custom"
            initramfs_prefix = f"initramfs-{kernel_package}"
        
        # Check for the initramfs file
        initramfs_path = Path(f"{mount_point}/boot/{initramfs_prefix}.img")
        
        if initramfs_path.exists():
            print(f"✅ Initramfs verified: {initramfs_prefix}.img")
            return
        
        # If not found, check alternative patterns
        # Try to find any initramfs-* file for this kernel
        boot_dir = Path(f"{mount_point}/boot")
        if boot_dir.exists():
            candidates = list(boot_dir.glob("initramfs-*.img"))
            if candidates:
                print(f"⚠️  Expected initramfs not found at {initramfs_prefix}.img")
                print(f"    Found: {', '.join([c.name for c in candidates])}")
                raise RuntimeError(
                    f"Initramfs generation failed: expected {initramfs_prefix}.img "
                    f"not found in /boot. Check mkinitcpio output during kernel package install. "
                    f"Available files: {', '.join([c.name for c in candidates])}"
                )
        
        raise RuntimeError(
            f"Initramfs generation failed: expected {initramfs_prefix}.img "
            f"not found in /boot. mkinitcpio may have failed during kernel package install."
        )

    return hook
