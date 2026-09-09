"""User configuration workflow orchestration (Phase 2).

Manages user dotfiles, scripts, and service configuration.

Workflow flow:
1. Load user-specific configurations
2. Deploy dotfiles
3. Configure and enable services
"""

from typing import Any, Dict

from kod.core import (
    configure_user_dotfiles as _configure_user_dotfiles,
    configure_user_scripts as _configure_user_scripts,
)


def configure_user_dotfiles(ctx: Any, user: str, user_configs: Dict,
                           dotfile_mngrs: Dict) -> None:
    """Deploy user dotfiles and configuration.
    
    Wrapper for kod.core.configure_user_dotfiles().
    """
    return _configure_user_dotfiles(ctx, user, user_configs, dotfile_mngrs)


def configure_user_scripts(ctx: Any, user: str, user_configs: Dict) -> None:
    """Execute user configuration scripts.
    
    Wrapper for kod.core.configure_user_scripts().
    """
    return _configure_user_scripts(ctx, user, user_configs)
