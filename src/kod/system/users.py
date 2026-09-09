"""User and group management operations (Phase 2).

Handles user creation, configuration, dotfile management, and services.
Internals refactored in Phase 2b.
"""

from typing import Any, Dict

from kod.common import exec_chroot


def create_kod_user(mount_point: str) -> None:
    """
    Create the 'kod' user and give it NOPASSWD access in the sudoers file.

    This function creates a user named 'kod' with a home directory in
    /var/kod/.home and adds it to the wheel group. It also creates a sudoers
    file for the user which allows it to run any command with NOPASSWD.

    Args:
        mount_point (str): The mount point where the installation is being
            performed.
    """
    exec_chroot("useradd -m -r -G wheel -s /bin/bash -d /var/kod/.home kod")
    with open(f"{mount_point}/etc/sudoers.d/kod", "w") as f:
        f.write("kod ALL=(ALL) NOPASSWD: ALL")


def create_user(ctx: Any, user: str, info: Any) -> None:
    """
    Create a user in the system.

    This function creates a user in the system according to the given information.

    Args:
        ctx (Context): The context object.
        user (str): The user name to be created.
        info (dict): The user information dictionary containing name, shell, password,
                     and extra_groups.
    """
    print(f">>> Creating user {user}")
    # Normal users (no root)
    if user != "root":
        print(f"Creating user {user}")
        user_name = info["name"]
        ctx.execute(f"useradd -m {user} -c '{user_name}'")
        extra_groups = list(info.extra_groups.values()) if "extra_groups" in info else []
        if extra_groups:
            # TODO: Implement group creation
            for group in extra_groups:
                try:
                    ctx.execute(f"usermod -aG {group} {user}")
                except Exception:
                    print(f"Group {group} does not exist")
            if "wheel" in extra_groups:
                ctx.execute(
                    "sed -i 's/# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers",
                )
                ctx.execute(
                    "sed -i 's/# auth       required   pam_wheel.so/auth       required   pam_wheel.so/' /etc/pam.d/su",
                )

    # Shell
    if not info.shell:
        shell = "/bin/bash"
    else:
        shell = info["shell"]
    ctx.execute(f"usermod -s {shell} {user}")

    # Password
    if not info.no_password:
        if info.hashed_password:
            print("Assign the provided password")
            ctx.execute(f"usermod -p '{info.hashed_password}' {user}")
        elif info.password:
            print("Assign the provided password after encryption")
            encrypted_pass = ctx.execute(f"mkpasswd -m sha-512 {info.password}", get_output=True).strip()
            ctx.execute(f"usermod -p '{encrypted_pass}' {user}")
        else:
            ctx.execute(f"passwd {user}")


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


def proc_users(ctx: Any, conf: Any) -> None:
    """
    Process all users in the given configuration.

    For each user, this function creates the user, configures their dotfile manager,
    configures their programs, and enables their services.

    Args:
        ctx (Context): The context object used for executing commands.
        conf (dict): The configuration dictionary containing user information.
    """
    from kod.core import (
        user_dotfile_manager,
        user_configs,
        configure_user_dotfiles,
        configure_user_scripts,
        user_services,
        enable_user_services,
    )

    users = conf.users

    if users is None:
        return

    # For each user: create user, configure dotfile manager, configure user programs
    for user, info in users.items():
        create_user(ctx, user, info)

        dotfile_mngrs = user_dotfile_manager(info)
        user_configs_def = user_configs(user, info)

        configure_user_dotfiles(ctx, user, user_configs_def, dotfile_mngrs)
        configure_user_scripts(ctx, user, user_configs_def)

        proc_user_home(ctx, user, info)

        services_to_enable = user_services(user, info)
        print(f"User services to enable: {services_to_enable}")
        enable_user_services(ctx, user, services_to_enable)
