"""User configuration workflow orchestration (Phase 2).

Manages user dotfiles, scripts, and service configuration.

Workflow:
1. Load user-specific configurations
2. Deploy dotfiles
3. Configure and enable services
"""

from typing import Any


def configure_user_dotfiles(ctx: Any, user: str, user_configs: Any, dotfile_mngrs: Any) -> None:
    """Configure user dotfiles using a specified dotfile manager.

    Sets up the dotfiles for a user by executing the commands from the user's 
    dotfile manager. Temporarily sets the context user to ensure any logging or 
    permission checks within the dotfile manager use the correct user context.

    Args:
        ctx: The context object used for executing commands.
        user: The username for which to configure dotfiles.
        user_configs: Dict containing user configuration details.
        dotfile_mngrs: The dotfile manager object responsible for dotfile operations.
    """
    old_user = ctx.user
    ctx.user = user  # Set context to current user (needed by dotfile_mngrs)
    if user_configs.get("configs") and dotfile_mngrs:
        call_init = True
        for config in user_configs["configs"]:
            command = dotfile_mngrs.command
            prg_config = dotfile_mngrs.config
            command(ctx, prg_config, config, call_init)
            call_init = False
    ctx.user = old_user


def configure_user_scripts(ctx: Any, user: str, user_configs: Any) -> None:
    """Configure user scripts based on user configuration.

    Executes the command configurations specified in the user's configuration 
    for the current context stage. Temporarily sets the context user to ensure 
    correct user context during script execution.

    Args:
        ctx: The context object used for executing commands.
        user: The username for which to configure scripts.
        user_configs: Dict containing user configuration details.
    """
    old_user = ctx.user
    ctx.user = user  # Set context to current user (needed by prog_config.command)
    if user_configs.get("run"):
        for prog_config in user_configs["run"]:
            command = prog_config.command
            config = prog_config.config
            stages = list(prog_config.stages.values())
            if ctx.stage in stages:
                command(ctx, config)
    ctx.user = old_user
