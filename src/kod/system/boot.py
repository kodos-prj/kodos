"""Boot management operations (Phase 2).

Handles bootloader configuration, kernel selection, and boot entry management.
Currently wraps functions from kod.core; internals will be refactored in Phase 2b.
"""

from typing import Any, Callable, Dict, List, Optional

from kod.core import (
    setup_bootloader as _setup_bootloader,
    create_boot_entry as _create_boot_entry,
    get_kernel_version as _get_kernel_version,
    update_kernel_hook as _update_kernel_hook,
    update_initramfs_hook as _update_initramfs_hook,
)


def setup_bootloader(conf: Dict[str, Any], partition_list: List, dist: Any) -> None:
    """Configure bootloader (systemd-boot, GRUB, etc).
    
    Wrapper for kod.core.setup_bootloader().
    """
    return _setup_bootloader(conf, partition_list, dist)


def create_boot_entry(kernel_package: str, initramfs_img: str, partition_list: List,
                     dist: Any, cmdline: Optional[str] = None) -> None:
    """Create a boot entry for a kernel.
    
    Wrapper for kod.core.create_boot_entry().
    """
    return _create_boot_entry(kernel_package, initramfs_img, partition_list, dist, cmdline)


def get_kernel_version(mount_point: str) -> str:
    """Get installed kernel version.
    
    Wrapper for kod.core.get_kernel_version().
    """
    return _get_kernel_version(mount_point)


def update_kernel_hook(kernel_package: str, mount_point: str) -> Callable[[], None]:
    """Create a hook for kernel updates.
    
    Wrapper for kod.core.update_kernel_hook().
    """
    return _update_kernel_hook(kernel_package, mount_point)


def update_initramfs_hook(kernel_package: str, mount_point: str) -> Callable[[], None]:
    """Create a hook for initramfs updates.
    
    Wrapper for kod.core.update_initramfs_hook().
    """
    return _update_initramfs_hook(kernel_package, mount_point)
