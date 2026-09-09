"""Package management operations (Phase 2).

Handles package installation, updates, caching, and repository management.
Currently wraps functions from kod.core; internals will be refactored in Phase 2b.
"""

from typing import Any, Dict, List, Optional, Tuple

# Import functions from old core.py to expose as this module's interface
from kod.core import (
    get_packages_to_install as _get_packages_to_install,
    manage_packages as _manage_packages,
    load_repos as _load_repos,
    load_package_lock as _load_package_lock,
    store_packages_services as _store_packages_services,
    get_packages_updates as _get_packages_updates,
    update_all_packages as _update_all_packages,
    get_pending_packages as _get_pending_packages,
    proc_system_packages as _proc_system_packages,
    manage_packages_shell as _manage_packages_shell,
)


def get_packages_to_install(conf: Dict[str, Any]) -> Tuple[Dict[str, List[str]], List[str]]:
    """Extract packages to install from config.
    
    Returns (packages_by_repo, all_packages).
    Wrapper for kod.core.get_packages_to_install().
    """
    return _get_packages_to_install(conf)


def manage_packages(ctx: Any, packages: List[str], action: str, 
                   mount_point: str = "/mnt", chroot: bool = False) -> None:
    """Install/remove/update packages.
    
    Wrapper for kod.core.manage_packages().
    """
    return _manage_packages(ctx, packages, action, mount_point, chroot)


def load_repos() -> Optional[Dict[str, Any]]:
    """Load repository configuration.
    
    Wrapper for kod.core.load_repos().
    """
    return _load_repos()


def load_package_lock(state_path: str) -> Optional[Dict[str, str]]:
    """Load cached package versions.
    
    Wrapper for kod.core.load_package_lock().
    """
    return _load_package_lock(state_path)


def store_packages_services(state_path: str, packages: Dict[str, List[str]],
                           services: List[str]) -> None:
    """Cache packages and services to disk.
    
    Wrapper for kod.core.store_packages_services().
    """
    return _store_packages_services(state_path, packages, services)


def get_packages_updates(repos: Dict[str, Any], current: Dict[str, str]) -> Tuple[List[str], Dict[str, str]]:
    """Calculate package updates.
    
    Wrapper for kod.core.get_packages_updates().
    """
    return _get_packages_updates(repos, current)


def update_all_packages(mount_point: str, new_generation: bool, repos: Dict[str, Any]) -> None:
    """Update all packages.
    
    Wrapper for kod.core.update_all_packages().
    """
    return _update_all_packages(mount_point, new_generation, repos)


def get_pending_packages(packages_to_install: Dict[str, List[str]]) -> List[str]:
    """Get list of packages pending installation.
    
    Wrapper for kod.core.get_pending_packages().
    """
    return _get_pending_packages(packages_to_install)


# ponytail: not exporting proc_system_packages, manage_packages_shell
# (internal helpers; add if they need to be part of the public API)
