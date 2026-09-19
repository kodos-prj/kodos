"""Service management operations (Phase 2b refactored).

Handles systemd service enablement, user services, and service configuration.
Aggregation logic moved to Lua (src/lua/kod/sections/services.lua).
"""

from typing import Any, List, Dict

from kod.common import exec, exec_chroot

# Aggregation moved to Lua (src/lua/kod/sections/services.lua)


def get_services_to_enable(ctx: Any, conf: Any) -> List[str]:
    """Extract services to enable from config.

    Calls Lua's service aggregation to collect services from all config sections
    (desktop, system services, user services).
    
    Args:
        ctx: Context object (passed through, not used in aggregation)
        conf: The configuration table (Lua table or Python dict) containing service configuration.

    Returns:
        list: A list of service names to enable.
    """
    from kod.lua_runtime import get_lua_runtime
    from kod.lua_utils import lua_table_to_python, python_dict_to_lua_table
    
    # Load Lua and call service aggregation
    lua = get_lua_runtime()
    services_module = lua.require("kod.sections.services")
    
    # Convert Python dict back to Lua table if needed
    if isinstance(conf, dict):
        conf_lua = python_dict_to_lua_table(lua, conf)
    else:
        conf_lua = conf
    
    # Call Lua aggregation function
    lua_services = services_module.aggregate_services(conf_lua)
    
    # Convert lupa.LuaTable to Python list
    services_list = lua_table_to_python(lua_services)
    
    return services_list


# ============================================================================
# EXECUTION FUNCTIONS
# ============================================================================


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
        service = program_data["service"] if "service" in program_data else None
        if service and ("enable" in service and service["enable"]):
            service_name = service["service_name"] if "service_name" in service else None
            if service_name:
                services_to_enable.append(service_name)
    
    # Use existing enable_services() function
    if services_to_enable:
        enable_services(services_to_enable, mount_point=mount_point, use_chroot=use_chroot)




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
        service = program_data["service"] if "service" in program_data else None
        if service and ("enable" in service and service["enable"]):
            service_name = service["service_name"] if "service_name" in service else None
            if service_name:
                services_to_enable.append(service_name)
    
    # Use existing enable_services() function
    if services_to_enable:
        enable_services(services_to_enable, mount_point=mount_point, use_chroot=use_chroot)

