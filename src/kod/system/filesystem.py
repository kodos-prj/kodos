"""Filesystem operations (Phase 2).

Handles partitioning, mount point management, fstab, and subvolume operations.
Currently wraps functions from kod.core; internals will be refactored in Phase 2b.
"""

from typing import Any, Dict, List

from kod._core import (
    create_filesystem_hierarchy as _create_filesystem_hierarchy,
    generate_fstab as _generate_fstab,
    load_fstab as _load_fstab,
    update_fstab as _update_fstab,
    create_next_generation as _create_next_generation,
    change_subvol as _change_subvol,
    set_ro_mount as _set_ro_mount,
    change_ro_mount as _change_ro_mount,
)


def create_filesystem_hierarchy(boot_part: Any, root_part: Any, partition_list: List,
                               mount_point: str) -> List:
    """Create filesystem hierarchy (subvolumes, mounts).
    
    Wrapper for kod._core.create_filesystem_hierarchy().
    """
    return _create_filesystem_hierarchy(boot_part, root_part, partition_list, mount_point)


def generate_fstab(partition_list: List, mount_point: str) -> None:
    """Generate /etc/fstab.
    
    Wrapper for kod._core.generate_fstab().
    """
    return _generate_fstab(partition_list, mount_point)


def load_fstab(root_path: str = "") -> List[str]:
    """Load /etc/fstab entries.
    
    Wrapper for kod._core.load_fstab().
    """
    return _load_fstab(root_path)


def update_fstab(root_path: str, new_mount_point_map: Dict[str, str]) -> None:
    """Update /etc/fstab with new mount points.
    
    Wrapper for kod._core.update_fstab().
    """
    return _update_fstab(root_path, new_mount_point_map)


def create_next_generation(boot_part: str, root_part: str, generation: int) -> str:
    """Create next generation snapshot.
    
    Wrapper for kod._core.create_next_generation().
    """
    return _create_next_generation(boot_part, root_part, generation)


def change_subvol(partition_list: List, subvol: str, mount_points: List[str]) -> List:
    """Change to a different subvolume.
    
    Wrapper for kod._core.change_subvol().
    """
    return _change_subvol(partition_list, subvol, mount_points)


def set_ro_mount(mount_point: str) -> None:
    """Set mount point to read-only.
    
    Wrapper for kod._core.set_ro_mount().
    """
    return _set_ro_mount(mount_point)


def change_ro_mount(root_path: str) -> None:
    """Change read-only mount status.
    
    Wrapper for kod._core.change_ro_mount().
    """
    return _change_ro_mount(root_path)
