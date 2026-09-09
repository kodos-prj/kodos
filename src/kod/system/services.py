"""Service management operations (Phase 2b refactored).

Handles systemd service enablement, user services, and service configuration.
Implementations moved from kod.core into this module during Phase 2b.
"""

from typing import Any, List, Dict, Optional

from kod.common import exec, exec_chroot


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

    if desktop is None:
        return services_to_enable

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


def proc_services(conf: Any) -> List[str]:
    """
    Process the services configuration and generate a list of packages to install.

    This function processes the services configuration and returns a list of
    packages that need to be installed.

    Args:
        conf (dict): The configuration dictionary containing the services
                     information.

    Returns:
        list: A list of package names to be installed.
    """
    packages_to_install = []
    print("- processing services -----------")
    services = conf.services

    if services is None:
        return packages_to_install

    for name, service in services.items():
        print(name, service.enable)
        if service.enable:
            pkgs = []
            if service.package:
                print("  using:", service.package)
                name = service.package
            pkgs.append(name)
            if service.extra_packages:
                print("  extra packages:", service.extra_packages)
                extra_pkgs = list(service.extra_packages.values())
                pkgs += extra_pkgs

            packages_to_install += pkgs

    return packages_to_install


def proc_services_to_enable(ctx: Any, conf: Any) -> List[str]:
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

    if services is None:
        return services_to_enable

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


def get_services_to_enable(ctx: Any, conf: Any) -> List[str]:
    """Extract services to enable from config.
    
    Combines desktop services and system services from configuration.
    """
    desktop_services = proc_desktop_services(conf)
    # System services
    services_to_enable = proc_services_to_enable(ctx, conf)

    return desktop_services + services_to_enable


def enable_services(list_of_services: List[str], mount_point: str = "/mnt", 
                   use_chroot: bool = False) -> None:
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


def disable_services(list_of_services: List[str], mount_point: str = "/mnt",
                    use_chroot: bool = False) -> None:
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


def enable_user_services(ctx: Any, user: str, services: List[str]) -> None:
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


def enable_services_from_programs(
    compiled: Dict[str, Any],
    mount_point: str = "/mnt",
    use_chroot: bool = False
) -> None:
    """Enable services from compiled program definitions.
    
    Extracts services that have enable=true from the compiled programs section
    and enables them via systemctl. This is called during installation after
    packages are installed.
    
    Args:
        compiled: Compiled config with programs section
        mount_point: Path for chroot operations (default: "/mnt")
        use_chroot: Whether to use chroot for service enablement (default: False)
    
    Example:
        >>> compiled = {
        ...     "programs": {
        ...         "openssh": {
        ...             "service": {"enable": True, "service_name": "sshd"}
        ...         }
        ...     }
        ... }
        >>> enable_services_from_programs(compiled)
    """
    if "programs" not in compiled:
        return
    
    services_to_enable = []
    
    for program_name, program_data in compiled["programs"].items():
        service = program_data.get("service")
        if service and service.get("enable"):
            service_name = service.get("service_name")
            if service_name:
                services_to_enable.append(service_name)
    
    # Use existing enable_services() function
    if services_to_enable:
        enable_services(services_to_enable, mount_point=mount_point, use_chroot=use_chroot)

