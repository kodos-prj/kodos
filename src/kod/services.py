"""Service management for KodOS."""

from typing import List, Any, Dict

from kod.common import exec, exec_chroot
from kod.context import Context


def proc_desktop_services(conf: Any) -> List[str]:
    """
    Process the desktop services configuration to determine which services
    should be enabled based on the provided configuration.

    This function iterates over the desktop manager options and consolidates
    the list of services to enable, including display managers, based on the
    configuration settings provided.

    Args:
        conf (dict): The configuration dictionary containing the desktop
                     services configuration.

    Returns:
        list: A list of service names that need to be enabled.
    """
    services_to_enable = []
    desktop = conf.desktop

    display_manager = desktop.display_manager
    selected_display_manager = False
    if display_manager:
        print(f"Installing {display_manager}")
        services_to_enable += [display_manager]
        selected_display_manager = True

    desktop_manager = desktop.desktop_manager
    if desktop_manager:
        for _, dm_conf in desktop_manager.items():
            if dm_conf.enable:
                if "display_manager" in dm_conf:
                    display_mngr = dm_conf["display_manager"]
                    if not selected_display_manager:
                        services_to_enable += [display_mngr]
                        selected_display_manager = True

    return services_to_enable


def get_services_to_enable(ctx: Context, conf: Any) -> List[str]:
    # Desktop manager service
    """
    Process the services configuration and generate a list of services to enable.

    This function processes the services configuration and returns a list of
    services that need to be enabled.

    Args:
        ctx (Context): The context object.
        conf (dict): The configuration dictionary containing the services
                     information.

    Returns:
        list: A list of service names to be enabled.
    """
    desktop_services = proc_desktop_services(conf)
    # System services
    services_to_enable = proc_services_to_enable(ctx, conf)

    return desktop_services + services_to_enable


def proc_services_to_enable(ctx: Context, conf: Any) -> List[str]:
    """
    Process the services configuration and generate a list of services to enable.

    This function processes the services configuration and returns a list of
    services that need to be enabled.

    Args:
        ctx (Context): The context object.
        conf (dict): The configuration dictionary containing the services
                     information.

    Returns:
        list: A list of service names to be enabled.
    """
    services_to_enable = []
    print("- processing services -----------")
    services = conf.services
    for name, service in services.items():
        service_enable = service.enable or True
        print(name, service_enable)
        service_name = name
        if service_enable:
            if "services" in service:
                for sub_sevice, serv_desc in service.services.items():
                    print(f"Checking {sub_sevice} service discription")
                    if serv_desc.command:
                        service_name = serv_desc.command(ctx, serv_desc.config)
                        services_to_enable.append(service_name)
            else:
                if service.service_name:
                    print("  using:", service.service_name)
                    service_name = service.service_name
                services_to_enable.append(service_name)

    return services_to_enable


def enable_services(list_of_services: List[str], mount_point: str = "/mnt", use_chroot: bool = False) -> None:
    """
    Enable a list of services in the specified mount point.

    This function enables the specified list of services in the context of the
    specified mount point. If `use_chroot` is True, it executes the enabling
    command in a chroot environment based at `mount_point`. If `use_chroot` is
    False (default), it executes the enabling command directly.

    Args:
        list_of_services (list): A list of service names to enable.
        mount_point (str, optional): The mount point for chroot operations, if
                                     applicable. Defaults to "/mnt".
        use_chroot (bool, optional): If True, execute the enabling command in a
                                     chroot environment based at `mount_point`.
                                     Defaults to False.

    Returns:
        None
    """
    for service in list_of_services:
        print(f"Enabling service: {service}")
        if use_chroot:
            exec_chroot(f"systemctl enable {service}", mount_point=mount_point)
        else:
            exec(f"systemctl enable --now {service}")


def disable_services(list_of_services: List[str], mount_point: str = "/mnt", use_chroot: bool = False) -> None:
    """
    Disable a list of services in the specified mount point.

    This function disables the specified list of services in the context of the
    specified mount point. If `use_chroot` is True, it executes the disabling
    command in a chroot environment based at `mount_point`. If `use_chroot` is
    False (default), it executes the disabling command directly.

    Args:
        list_of_services (list): A list of service names to disable.
        mount_point (str, optional): The mount point for chroot operations, if
                                     applicable. Defaults to "/mnt".
        use_chroot (bool, optional): If True, execute the disabling command in a
                                     chroot environment based at `mount_point`.
                                     Defaults to False.

    Returns:
        None
    """
    for service in list_of_services:
        print(f"Disabling service: {service}")
        if use_chroot:
            exec_chroot(f"systemctl disable {service}", mount_point=mount_point)
        else:
            exec(f"systemctl disable --now {service}")


def enable_user_services(ctx: Context, user: str, services: List[str]) -> None:
    """
    Enable services for a user in the specified context.

    This function enables the specified services for the specified user in the
    context of the specified context object. If the context object's stage is
    "rebuild-user", it executes the enabling command; otherwise, it simply prints
    a message indicating that it is not performing the enabling operation.

    Args:
        ctx (Context): The context object.
        user (str): The user for which to enable the services.
        services (list): A list of service names to enable.
    """
    print(f"Enabling service: {services} for {user}")

    for service in services:
        if ctx.stage == "rebuild-user":
            print("Running: ", f"systemctl --user enable --now {service}")
            ctx.execute(f"systemctl --user enable --now {service}")
        print("Done - services enabled")


def proc_user_services(conf: Any) -> Dict[str, Any]:
    """
    Process the user services configuration.

    This function processes the user services configuration and generates a
    dictionary mapping each user to their respective services to enable.

    Args:
        conf (dict): The configuration dictionary containing the user
                     information.

    Returns:
        dict: A dictionary mapping each user to their respective services to
              enable.
    """
    services_to_enable_user = {}
    print("- processing user programs -----------")
    users = conf.users

    for user, info in users.items():
        services = []
        if info.services:
            for service, desc in info.services.items():
                if desc.enable:
                    print(f"Checking {service} service discription")
                    services.append(service)

        if services:
            services_to_enable_user[user] = services

    return services_to_enable_user


def user_services(user: str, info: Any) -> List[str]:
    """
    Process the user services configuration to determine which services
    should be enabled based on the provided configuration.

    This function iterates over the user's services configuration and
    returns a list of service names that need to be enabled.

    Args:
        user (str): The user name for which services are being processed.
        info (dict): A dictionary containing the user's configuration details,
                     including services.

    Returns:
        list: A list of service names that need to be enabled.
    """
    print(f"- processing user services {user} -----------")
    services = []
    if info.services:
        for service, desc in info.services.items():
            if desc.enable:
                print(f"Checking {service} service discription")
                services.append(service)

    return services
