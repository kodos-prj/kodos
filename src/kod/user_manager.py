"""User Management Module for KodOS.

This module handles user creation, dotfile management, user services,
and user-specific configurations.
"""

from typing import Any, Dict, List, Optional

from .common import Context, exec, exec_chroot


def enable_services(list_of_services: List[str], mount_point: str = "/mnt", use_chroot: bool = False) -> None:
    """
    Enable a list of systemd services.

    Args:
        list_of_services (list): A list of service names to enable.
        mount_point (str, optional): The mount point of the chroot environment. Defaults to "/mnt".
        use_chroot (bool, optional): Whether to use chroot when executing commands. Defaults to False.
    """
    if use_chroot:
        for service in list_of_services:
            exec_chroot(f"systemctl enable {service}", mount_point=mount_point)
    else:
        for service in list_of_services:
            exec(f"systemctl enable {service}")


def disable_services(list_of_services: List[str], mount_point: str = "/mnt", use_chroot: bool = False) -> None:
    """
    Disable a list of systemd services.

    Args:
        list_of_services (list): A list of service names to disable.
        mount_point (str, optional): The mount point of the chroot environment. Defaults to "/mnt".
        use_chroot (bool, optional): Whether to use chroot when executing commands. Defaults to False.
    """
    if use_chroot:
        for service in list_of_services:
            exec_chroot(f"systemctl disable {service}", mount_point=mount_point)
    else:
        for service in list_of_services:
            exec(f"systemctl disable {service}")


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


def create_user(ctx: Context, user: str, info: Any) -> None:
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

    user_name = info.name if hasattr(info, "name") else user
    extra_groups = info.extra_groups if hasattr(info, "extra_groups") else []
    shell = info.shell if hasattr(info, "shell") else "/bin/bash"

    ctx.execute(f"useradd -m {user} -c '{user_name}'")

    print(f"{extra_groups = }")
    if extra_groups:
        if isinstance(extra_groups, dict):
            for group in extra_groups.values():
                ctx.execute(f"usermod -aG {group} {user}")
        else:
            for group in extra_groups:
                ctx.execute(f"usermod -aG {group} {user}")

    if hasattr(info, "hashed_password") and info.hashed_password:
        ctx.execute(f"usermod -p '{info.hashed_password}' {user}")
    elif hasattr(info, "password") and info.password:
        ctx.execute(f"usermod -p `mkpasswd -m sha-512 {info.password}` {user}")
    else:
        print(f"Setting password for {user}")
        ctx.execute(f"passwd {user}")

    ctx.execute(f"usermod -s {shell} {user}")


def get_services_to_enable(ctx: Context, conf: Any) -> List[str]:
    """
    Get services to enable from configuration.

    Args:
        ctx: Context object.
        conf: Configuration object.

    Returns:
        List of service names to enable.
    """
    return proc_services_to_enable(ctx, conf)


def proc_services_to_enable(ctx: Context, conf: Any) -> List[str]:
    """
    Process and return a list of services to enable based on the given configuration.

    Args:
        ctx: Context object.
        conf: Configuration object.

    Returns:
        List of service names to enable.
    """
    system_services = []
    user_services = proc_user_services(conf)

    if hasattr(conf, "services") and conf.services:
        for _, service_info in conf.services.items():
            if hasattr(service_info, "default") and service_info.default:
                system_services.append(service_info.default)

    for user, services in user_services.items():
        system_services.extend(services)

    return system_services


def proc_user_services(conf: Any) -> Dict[str, List[str]]:
    """
    Process user services from configuration.

    Args:
        conf: Configuration object.

    Returns:
        Dictionary mapping usernames to lists of services.
    """
    user_services_dict = {}

    if hasattr(conf, "users") and conf.users:
        for user, user_info in conf.users.items():
            if hasattr(user_info, "services") and user_info.services:
                user_services_dict[user] = user_services(user, user_info)

    return user_services_dict


def user_services(user: str, info: Any) -> List[str]:
    """
    Get user services from user info.

    Args:
        user: Username.
        info: User information object.

    Returns:
        List of service names.
    """
    services = []
    if hasattr(info, "services") and info.services:
        if isinstance(info.services, dict):
            services.extend(info.services.values())
        else:
            services.extend(info.services)
    return services


def enable_user_services(ctx: Context, user: str, services: List[str]) -> None:
    """
    Enable user services for a specific user.

    Args:
        ctx (Context): The context object.
        user (str): The user for which to enable the services.
        services (list): A list of service names to enable.
    """
    print(f"Enabling service: {services} for {user}")

    for service in services:
        if ctx.stage == "rebuild-user":
            ctx.execute(f"systemctl --user enable --now {service}")


def proc_user_configs(conf: Any) -> Dict[str, Any]:
    """
    Process user configurations from the main configuration.

    Args:
        conf: Main configuration object.

    Returns:
        Dictionary of user configurations.
    """
    user_configs = {}
    if hasattr(conf, "users") and conf.users:
        for user, user_info in conf.users.items():
            user_configs[user] = user_configs_from_info(user, user_info)
    return user_configs


def user_configs_from_info(user: str, info: Any) -> Dict[str, Any]:
    """
    Extract user configurations from user info.

    Args:
        user: Username.
        info: User information object.

    Returns:
        User configuration dictionary.
    """
    configs = {"deployable": {}, "executable": {}}

    if hasattr(info, "configs") and info.configs:
        for config_name, config_info in info.configs.items():
            if hasattr(config_info, "deploy"):
                configs["deployable"][config_name] = config_info
            if hasattr(config_info, "execute"):
                configs["executable"][config_name] = config_info

    return configs


def user_configs(user: str, info: Any) -> Dict[str, Any]:
    """
    Get user configurations.

    Args:
        user: Username.
        info: User information object.

    Returns:
        User configuration dictionary.
    """
    return user_configs_from_info(user, info)


def proc_user_dotfile_manager(conf: Any) -> Dict[str, Any]:
    """
    Process user dotfile manager configurations.

    Args:
        conf: Main configuration object.

    Returns:
        Dictionary of dotfile manager configurations.
    """
    dotfile_managers = {}
    if hasattr(conf, "users") and conf.users:
        for user, user_info in conf.users.items():
            if hasattr(user_info, "dotfile_manager"):
                dotfile_managers[user] = user_dotfile_manager(user_info.dotfile_manager)
    return dotfile_managers


def user_dotfile_manager(info: Any) -> Optional[Dict[str, Any]]:
    """
    Get dotfile manager configuration from user info.

    Args:
        info: Dotfile manager information object.

    Returns:
        Dotfile manager configuration or None.
    """
    if hasattr(info, "type") and hasattr(info, "url"):
        return {"type": info.type, "url": info.url, "install_command": getattr(info, "install_command", None)}
    return None


def proc_user_home(ctx: Context, user: str, info: Any) -> None:
    """
    Process user home directory configuration.

    Args:
        ctx (Context): Context object to use for executing commands.
        user (str): The user name for which the home configuration is being processed.
        info (dict): A dictionary containing the user's home configuration information.
    """
    if hasattr(info, "home") and info.home:
        for config_name, config_info in info.home.items():
            if hasattr(config_info, "build"):
                config_info.build(ctx, config_info)


def configure_user_dotfiles(ctx: Context, user: str, user_configs: Any, dotfile_mngrs: Any) -> None:
    """
    Configure dotfiles for a user.

    Args:
        ctx (Context): The context object used for executing commands.
        user (str): The username for which to configure dotfiles.
        user_configs (dict): A dictionary containing user configuration details.
        dotfile_mngrs: The dotfile manager object responsible for handling dotfile operations.
    """
    old_user = ctx.user
    ctx.user = user

    if user in dotfile_mngrs:
        dotfile_manager = dotfile_mngrs[user]
        if dotfile_manager and "install_command" in dotfile_manager:
            ctx.execute(dotfile_manager["install_command"])

    ctx.user = old_user


def configure_user_scripts(ctx: Context, user: str, user_configs: Any) -> None:
    """
    Configure user scripts.

    Args:
        ctx (Context): The context object used for executing commands.
        user (str): The username for which to configure scripts.
        user_configs (dict): A dictionary containing user configuration details.
    """
    old_user = ctx.user
    ctx.user = user

    if user in user_configs and "executable" in user_configs[user]:
        for config_name, config_info in user_configs[user]["executable"].items():
            stages = getattr(config_info, "stages", ["install"])
            if ctx.stage in stages:
                ctx.execute(getattr(config_info, "execute", ""))

    ctx.user = old_user


def proc_users(ctx: Context, conf: Any) -> None:
    """
    Process all users from configuration.

    Args:
        ctx (Context): The context object used for executing commands.
        conf (dict): The configuration dictionary containing user information.
    """
    if hasattr(conf, "users") and conf.users:
        for user, info in conf.users.items():
            create_user(ctx, user, info)

            # Configure user home
            proc_user_home(ctx, user, info)

            # Configure dotfiles and scripts
            user_configs_dict = user_configs(user, info)
            dotfile_managers = {user: user_dotfile_manager(getattr(info, "dotfile_manager", None))}

            configure_user_dotfiles(ctx, user, {user: user_configs_dict}, dotfile_managers)
            configure_user_scripts(ctx, user, {user: user_configs_dict})

            # Enable user services
            services = user_services(user, info)
            enable_user_services(ctx, user, services)
