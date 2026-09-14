"""User and group management operations (Phase 2).

Handles user creation, configuration, dotfile management, and services.
Internals refactored in Phase 2b.
"""

from typing import Any


def proc_user_home(ctx: Any, user: str, info: Any) -> None:
    """
    Process the user's home configuration.

    This function processes the user's home configuration, looking for any
    configuration values that have a "build" key. If such a key is present,
    the function calls the associated build function with the ctx and config
    parameters.

    Args:
        ctx (Context): Context object to use for executing commands.
        user (str): The user name for which the home configuration is being
            processed.
        info (dict): A dictionary containing the user's home configuration
            information.
    """
    print(f"Processing home for {user}")
    if info.home:
        for key, val in info.home.items():
            if "build" in val:
                print(f"Building {key} for {user}")
                val.build(ctx, val.config)
    print("Done - home processed")
