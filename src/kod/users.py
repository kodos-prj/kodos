"""User management for KodOS."""

from typing import Dict, Any

from kod.common import exec_chroot
from kod.context import Context


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


def proc_user_dotfile_manager(conf: Any) -> Dict[str, Any]:
    """
    Process the user dotfile manager configuration and generate a dictionary of
    user and their dotfile manager information.

    Args:
        conf (dict): The configuration dictionary containing the user
                     information.

    Returns:
        dict: A dictionary of user name and their dotfile manager information.
    """
    print("- processing user dotfile manager -----------")
    users = conf.users
    dotfile_mngs = {}
    for user_name, info in users.items():
        if info.dotfile_manager:
            print(f"Processing dotfile manager for {user_name}")
            dotfile_mngs[user_name] = info.dotfile_manager

    return dotfile_mngs


def user_dotfile_manager(info: Any) -> Dict[str, Any] | None:
    """
    Process the user dotfile manager configuration and generate a dictionary of
    user and their dotfile manager information.

    Args:
        info (dict): The user information dictionary containing the dotfile
                     manager information.

    Returns:
        dict: A dictionary of user name and their dotfile manager information.
    """
    print("- processing user dotfile manager -----------")
    dotfile_mngs = None
    if info.dotfile_manager:
        print("Processing dotfile manager")
        dotfile_mngs = info.dotfile_manager

    return dotfile_mngs


def proc_user_configs(conf: Any) -> Dict[str, Any]:
    """
    Process user configurations to determine deployable configs and commands.

    This function processes the configuration for each user, extracting programs
    and services to identify which configurations need to be deployed and which
    commands need to be run.

    Args:
        conf (dict): A configuration dictionary containing users and their
                     associated program and service information.

    Returns:
        dict: A dictionary mapping each user to their respective deployable
              configurations and commands to run.
    """
    configs_to_deploy = {}

    print("- processing user programs -----------")
    users = conf.users

    for user, info in users.items():
        deploy_configs = []
        commands_to_run = []
        if info.programs:
            print(f"Processing programs for {user}")
            for name, prog in info.programs.items():
                print(name, prog.enable)
                if prog.enable:
                    if prog.deploy_config:
                        # Program requires deploy config
                        deploy_configs.append(name)

                    # Configure based on the specified parameters
                    if "config" in prog and prog.config:
                        prog_conf = prog.config
                        if "command" in prog_conf:
                            # command = prog_conf.command.format(**prog_conf.config)
                            commands_to_run.append(prog_conf)

        # Add extra deploy configs
        if info.deploy_configs:
            print(f"Processing deploy configs for {user}")
            configs = info.deploy_configs.values()
            deploy_configs += configs

        if info.services:
            for service, desc in info.services.items():
                if desc.enable:
                    print(f"Checking {service} service discription")
                    if desc.config:
                        serv_conf = desc.config
                        if "command" in serv_conf:
                            # command = serv_conf.command.format(**serv_conf.config)
                            commands_to_run.append(serv_conf)

        configs_to_deploy[user] = {"configs": deploy_configs, "run": commands_to_run}

    return configs_to_deploy


def user_configs(user: str, info: Any) -> Dict[str, Any]:
    """
    Process the user configuration to determine deployable configs and commands.

    This function iterates over the user's programs, services, and additional
    configuration settings to identify which configurations need to be deployed
    and which commands need to be executed.

    Args:
        user (str): The user name for which configurations are being processed.
        info (dict): A dictionary containing the user's configuration details,
                     including programs, deploy_configs, and services.

    Returns:
        dict: A dictionary with two keys:
            - "configs": A list of configuration names that need to be deployed.
            - "run": A list of commands that need to be executed based on the
              user's configuration.
    """
    configs_to_deploy = {}

    print("- processing user programs -----------")
    deploy_configs = []
    commands_to_run = []
    if info.programs:
        print(f"Processing programs for {user}")
        for name, prog in info.programs.items():
            print(name, prog.enable)
            if prog.enable:
                if prog.deploy_config:
                    # Program requires deploy config
                    deploy_configs.append(name)

                # Configure based on the specified parameters
                if "config" in prog and prog.config:
                    prog_conf = prog.config
                    if "command" in prog_conf:
                        commands_to_run.append(prog_conf)

    # Add extra deploy configs
    if info.deploy_configs:
        print(f"Processing deploy configs for {user}")
        configs = info.deploy_configs.values()
        deploy_configs += configs

    if info.services:
        for service, desc in info.services.items():
            if desc.enable:
                print(f"Checking {service} service discription")
                if desc.config:
                    serv_conf = desc.config
                    if "command" in serv_conf:
                        commands_to_run.append(serv_conf)

    configs_to_deploy = {"configs": deploy_configs, "run": commands_to_run}

    return configs_to_deploy


def proc_user_home(ctx: Context, user: str, info: Any) -> None:
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


def configure_user_dotfiles(ctx: Context, user: str, user_configs: Any, dotfile_mngrs: Any) -> None:
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


from kod.services import enable_user_services, user_services


def proc_users(ctx: Any, conf: Any) -> None:
    users = conf.users
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
