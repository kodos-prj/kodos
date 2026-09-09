"""Installation workflow orchestration (Phase 2).

Coordinates the complete installation process: filesystem setup, package
installation, user configuration, and bootloader setup.

Workflow flow:
1. Create filesystem hierarchy
2. Generate fstab
3. Install base system and packages
4. Create users
5. Configure services
6. Setup bootloader
7. Enable services
"""

from typing import Any, Dict, List

from kod._core import configure_system as _configure_system


def configure_system(conf: Dict[str, Any], partition_list: List, mount_point: str) -> None:
    """Orchestrate the complete system installation.
    
    This is the main entry point for the install workflow. It coordinates:
    - Filesystem preparation (partitions, subvolumes, mounts)
    - Package installation (base system + user-specified packages)
    - User account creation and configuration
    - Service enablement
    - Bootloader setup
    
    Args:
        conf: Configuration dictionary (loaded from Lua)
        partition_list: List of partition definitions
        mount_point: Root mount point for chroot
    
    Wrapper for kod._core.configure_system(). Phase 2b will refactor
    internals to use new kod.system modules directly.
    """
    return _configure_system(conf, partition_list, mount_point)
