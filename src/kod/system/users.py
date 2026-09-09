"""User and group management operations (Phase 2).

Handles user creation, configuration, dotfile management, and services.
Currently wraps functions from kod.core; internals will be refactored in Phase 2b.
"""

from typing import Any, Dict

from kod.core import (
    proc_users as _proc_users,
    create_user as _create_user,
    proc_user_home as _proc_user_home,
    create_kod_user as _create_kod_user,
)


def proc_users(ctx: Any, conf: Dict[str, Any]) -> None:
    """Process users from config and create them.
    
    Wrapper for kod.core.proc_users().
    """
    return _proc_users(ctx, conf)


def create_user(ctx: Any, user: str, info: Dict[str, Any]) -> None:
    """Create a system user.
    
    Wrapper for kod.core.create_user().
    """
    return _create_user(ctx, user, info)


def proc_user_home(ctx: Any, user: str, info: Dict[str, Any]) -> None:
    """Configure user home directory.
    
    Wrapper for kod.core.proc_user_home().
    """
    return _proc_user_home(ctx, user, info)


def create_kod_user(mount_point: str) -> None:
    """Create the special 'kod' build user.
    
    Wrapper for kod.core.create_kod_user().
    """
    return _create_kod_user(mount_point)
