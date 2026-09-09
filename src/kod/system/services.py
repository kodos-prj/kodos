"""Service management operations (Phase 2).

Handles systemd service enablement, user services, and service configuration.
Currently wraps functions from kod.core; internals will be refactored in Phase 2b.
"""

from typing import Any, Dict, List

from kod.core import (
    enable_services as _enable_services,
    disable_services as _disable_services,
    enable_user_services as _enable_user_services,
    get_services_to_enable as _get_services_to_enable,
)


def enable_services(list_of_services: List[str], mount_point: str = "/mnt", 
                   use_chroot: bool = False) -> None:
    """Enable systemd services.
    
    Args:
        list_of_services: Service names to enable
        mount_point: Root mount point (for chroot)
        use_chroot: Whether to use chroot
    
    Wrapper for kod.core.enable_services().
    """
    return _enable_services(list_of_services, mount_point, use_chroot)


def disable_services(list_of_services: List[str], mount_point: str = "/mnt",
                    use_chroot: bool = False) -> None:
    """Disable systemd services.
    
    Wrapper for kod.core.disable_services().
    """
    return _disable_services(list_of_services, mount_point, use_chroot)


def enable_user_services(ctx: Any, user: str, services: List[str]) -> None:
    """Enable user-level systemd services (systemctl --user).
    
    Wrapper for kod.core.enable_user_services().
    """
    return _enable_user_services(ctx, user, services)


def get_services_to_enable(ctx: Any, conf: Dict[str, Any]) -> List[str]:
    """Extract services to enable from config.
    
    Wrapper for kod.core.get_services_to_enable().
    """
    return _get_services_to_enable(ctx, conf)
