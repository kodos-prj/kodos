"""Kodos orchestration workflows (Phase 2).

This module provides high-level workflows for system operations:
- Install: bootstrap system from scratch
- Rebuild: create snapshots and apply updates
- User Config: manage user dotfiles and services

For backward compatibility, all old core.py functions are re-exported here.
"""

# Re-export everything from the legacy _core module for backward compatibility
from kod._core import *  # noqa: F401, F403

# Import and re-export workflow entry points
from kod.core.user_config import (
    configure_user_dotfiles,
    configure_user_scripts,
)

# Re-export refactored functions from kod.system modules (Phase 2b)
# These are now implemented in kod.system modules but re-exported for backward compat
def __getattr__(name: str):
    """Lazy import of refactored functions from kod.system modules."""
    # Package management functions moved to kod.system.packages
    if name in {
        'get_packages_to_install',
        'manage_packages',
        'load_repos',
        'load_package_lock',
        'store_packages_services',
        'get_packages_updates',
        'update_all_packages',
        'get_pending_packages',
        'manage_packages_shell',
    }:
        from kod.system import packages as packages_module
        return getattr(packages_module, name)
    
    # Service management functions moved to kod.system.services
    if name in {
        'enable_services',
        'disable_services',
        'enable_user_services',
        'get_services_to_enable',
        'proc_desktop_services',
        'proc_services',
        'proc_services_to_enable',
    }:
        from kod.system import services as services_module
        return getattr(services_module, name)
    
    # Boot functions moved to kod.system.boot
    if name in {
        'create_boot_entry_hook',
        'get_kernel_version',
        'update_kernel_hook',
        'update_initramfs_hook',
    }:
        from kod.system import boot as boot_module
        return getattr(boot_module, name)
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "configure_user_dotfiles",
    "configure_user_scripts",
    # Phase 2b re-exports from kod.system.packages
    "get_packages_to_install",
    "manage_packages",
    "load_repos",
    "load_package_lock",
    "store_packages_services",
    "get_packages_updates",
    "update_all_packages",
    "get_pending_packages",
    "manage_packages_shell",
    # Phase 2b re-exports from kod.system.services
    "enable_services",
    "disable_services",
    "enable_user_services",
    "get_services_to_enable",
    "proc_desktop_services",
    "proc_services",
    "proc_services_to_enable",
    # Phase 2b re-exports from kod.system.boot
    "create_boot_entry_hook",
    "get_kernel_version",
    "update_kernel_hook",
    "update_initramfs_hook",
]
