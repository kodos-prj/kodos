"""User configuration workflow orchestration (Phase 2).

Manages user dotfiles, scripts, and service configuration.

Workflow flow:
1. Load user-specific configurations
2. Deploy dotfiles
3. Configure and enable services
"""

from typing import Any


def configure_user_dotfiles(ctx: Any, user: str, user_configs: Any, dotfile_mngrs: Any) -> None:
    """
    Configure user dotfiles using a specified dotfile manager.

    This function sets up the dotfiles for a user by executing the commands
    from the user's dotfile manager. It temporarily changes the context user
    to the specified user for the duration of the configuration process.

    Args:
        ctx (Context): The context object used for executing commands.
        user (str): The username for which to configure dotfiles.
        user_configs (dict): A dictionary containing user configuration details,
                             including deployable configurations.
        dotfile_mngrs: The dotfile manager object responsible for handling
                       dotfile operations.

    Note:
        The context user is temporarily changed to the specified user for the
        configuration process and is restored to the original user afterward.
    """

    print(f"{dotfile_mngrs=}")
    print(f"Configuring user {user}")
    old_user = ctx.user
    ctx.user = user  # TODO: <-- evaluate if this is still needed
    # Calling dotfile_mngrs
    if user_configs["configs"] and dotfile_mngrs:
        # print("\nUSER:",os.environ['USER'],'\n')
        call_init = True
        for config in user_configs["configs"]:
            command = dotfile_mngrs.command
            prg_config = dotfile_mngrs.config
            command(ctx, prg_config, config, call_init)
            call_init = False
    ctx.user = old_user


def configure_user_scripts(ctx: Any, user: str, user_configs: Any) -> None:
    """
    Configure user scripts based on user configuration.

    This function executes the command configurations specified in the
    user's configuration for the current context stage. It temporarily
    changes the context user to the specified user for the execution of
    these commands and restores it afterward.

    Args:
        ctx (Context): The context object used for executing commands.
        user (str): The username for which to configure scripts.
        user_configs (dict): A dictionary containing user configuration
                             details, including executable commands.

    Note:
        The context user is temporarily changed to the specified user for
        the script execution process and is restored to the original user
        afterward.
    """
    print(f"Configuring user {user}")
    old_user = ctx.user
    ctx.user = user  # TODO: <-- evaluate if this is still needed
    # Calling program's config commands
    if user_configs["run"]:
        for prog_config in user_configs["run"]:
            command = prog_config.command
            config = prog_config.config
            stages = list(prog_config.stages.values())
            if ctx.stage in stages:
                command(ctx, config)
    ctx.user = old_user
