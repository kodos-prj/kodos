"""Core functionality and configuration management for KodOS.

This module contains the main functionality for KodOS including Lua configuration
processing, package management, user configuration, and system setup. It serves
as the central orchestrator for the installation and configuration process.
"""

import glob
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Callable

import lupa as lua

from kod.arch import get_base_packages, get_kernel_file, get_list_of_dependencies
from kod.common import exec, exec_chroot, exec_critical
from kod.filesystem import FsEntry
from kod.system.filesystem import (
    generate_fstab,
    load_fstab,
    create_filesystem_hierarchy,
    update_fstab,
    change_subvol,
    set_ro_mount,
    change_ro_mount,
    create_next_generation,
)
from kod.system.users import (
    proc_users,
    create_user,
    proc_user_home,
    create_kod_user,
)

# from kod.arch import kernel_update_required

#####################################################################################################
os_release = """NAME="KodOS Linux"
VERSION="1.0"
PRETTY_NAME="KodOS Linux"
ID=kodos
ANSI_COLOR="38;2;23;147;209"
HOME_URL="https://github.com/kodos-prj/kodos/"
DOCUMENTATION_URL="https://github.com/kodos-prj/kodos/"
SUPPORT_URL="https://github.com/kodos-prj/kodos/"
BUG_REPORT_URL="https://github.com/kodos-prj/kodos/issues"
RELEASE_TYPE="expeirimental"
"""
#####################################################################################################


base_distribution: str = "arch"


def set_base_distribution(base_dist: str) -> Any:
    """Set the base distribution and return the corresponding module.

    Args:
        base_dist: The base distribution name ("debian" or "arch").

    Returns:
        The distribution-specific module.
    """
    global base_distribution
    base_distribution = base_dist
    if base_dist == "debian":
        import kod.debian as dist

        return dist
    import kod.arch as dist

    return dist


# ------------------
def is_dir(path: str) -> bool:
    return Path(path).is_dir()


def home_dir() -> str:
    return Path().home()


def absolute(path: str) -> str:
    return str(Path(path).absolute())


def resolve(path: str) -> str:
    return str(Path(path).resolve())


def expanduser(path: str) -> str:
    return str(Path(path).expanduser())


def exists(path: str) -> bool:
    return Path(path).exists()


def is_file(path: str) -> bool:
    return Path(path).is_file()


# ------------------


# Core
def load_config(config_filename: Optional[str]) -> Any:
    """Load configuration from a file and return it as a table.

    The configuration file is a Lua file that contains different sections to configure
    the different aspects of the system.

    Args:
        config_filename: Path to the configuration file.

    Returns:
        The loaded configuration as a Lua table.
    """

    luart = lua.LuaRuntime()

    if config_filename is None:
        config_filename = "/etc/kodos"

    if Path(config_filename).is_dir():
        config_filename = str(Path(config_filename).joinpath("configuration.lua"))

    print(f"Config file: {config_filename}")
    config_path = Path(config_filename).resolve().parents[0]
    luart.execute(f"package.path = '{config_path}/?.lua;' .. package.path")
    lib_path = Path(__file__).resolve().parents[0]
    luart.execute(f"package.path = '{lib_path}/lib/?.lua;' .. package.path")
    luart.execute("package.path = 'kod/lib/?.lua;' .. package.path")
    luart.execute("print(package.path)")
    print("Loading default libraries")

    # # Load the Lua runtime and add path functionality
    # luart.globals()["is_dir"] = is_dir
    # luart.globals()["home_dir"] = home_dir
    path_module = luart.table_from(
        {
            "is_dir": is_dir,
            "is_file": is_file,
            "home_dir": home_dir,
            "exists": exists,
            "absolute": absolute,
            "expanduser": expanduser,
        }
    )

    # Make the path module available in Lua
    luart.globals()["path"] = path_module

    default_libs = """
list = require("utils").list
map = require("utils").map
If = require("utils").if_true
IfElse = require("utils").if_else
    """
    luart.execute(default_libs)
    with open(config_filename) as f:
        config_data = f.read()
        conf = luart.execute(config_data)
    return conf




# Core
def get_max_generation() -> int:
    """
    Retrieve the highest numbered generation directory in /kod/generations.

    If no generation directories exist, return 0.

    Returns:
        int: The highest numbered generation directory.
    """
    generations = glob.glob("/kod/generations/*")
    generations = [p.split("/")[-1] for p in generations]
    generations = [int(p) for p in generations if p != "current"]
    print(f"{generations=}")
    if generations:
        generation = max(generations)
    else:
        generation = 0
    print(f"{generation=}")
    return generation


# Core


# Core
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


# Core
def user_dotfile_manager(info: Any) -> Optional[Dict[str, Any]]:
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


# Core
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


# Core
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


# Core
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


# Core
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


# Core

# Core
class Context:
    """
    Context class for executing commands.

    This class represents the context in which commands are executed. It stores
    information about the user and mount point that are used to execute commands.
    """

    user: str
    mount_point: str
    use_chroot: bool
    stage: str

    def __init__(self, user: str, mount_point: str = "/mnt", use_chroot: bool = True, stage: str = "install") -> None:
        """
        Initialize the Context object.

        This object stores information about the user and mount point that are
        used to execute commands.

        Parameters
        ----------
        user : str
            The user name to use for executing commands.
        mount_point : str
            The mount point of the root filesystem to use for executing commands.
            Defaults to "/mnt".
        use_chroot : bool
            If True, the command will be executed using chroot. Defaults to True.
        stage : str
            The stage of the installation. This can be either "install" or "rebuild".
        """
        self.user = user
        self.mount_point = mount_point
        self.use_chroot = use_chroot
        self.stage = stage

    def execute(self, command: str, get_output: bool = False) -> str:
        """
        Execute a command in the specified context.

        This method constructs and executes a command based on the current context,
        which includes the user, mount point, and chroot settings. If the context
        user is different from the current environment user, the command is wrapped
        with 'su' for user substitution. If chroot execution is enabled, the command
        is executed within the chroot environment at the specified mount point.

        Args:
            command (str): The command to execute.
            get_output (bool): Whether to return command output. Defaults to False.

        Returns:
            str: Command output if get_output=True, empty string otherwise.
        """
        if self.user == os.environ["USER"]:
            exec_prefix = ""
        else:
            exec_prefix = f" su {self.user} -c "

        def wrap(s: str) -> str:
            if self.user == os.environ["USER"]:
                return s
            else:
                return f"'{s}'"

        print(f"[Contex] Command: {command}")
        if self.use_chroot:
            print(f"##> {exec_prefix} {wrap(command)}")
            result = exec_chroot(f"{exec_prefix} {wrap(command)}", mount_point=self.mount_point, get_output=get_output)
        else:
            result = exec(f"{exec_prefix} {wrap(command)}", get_output=get_output)

        if get_output:
            return result
        else:
            return ""



# Core
def get_generation(mount_point: str) -> int:
    """
    Retrieve the generation number from a specified mount point.

    Args:
        mount_point (str): The mount point to read the generation number from.

    Returns:
        int: The generation number as an integer.
    """
    with open(f"{mount_point}/.generation", "r") as f:
        return int(f.read().strip())


# Core
def load_packages_services(state_path: str) -> Tuple[Optional[Dict[str, List[str]]], Optional[List[str]]]:
    """
    Load the list of packages that are installed and the list of services that are enabled.

    Args:
        state_path (str): The path to the state directory where the package and service
            information is stored.

    Returns:
        tuple: A tuple containing two elements:
            - packages (dict): A dictionary containing the packages to install.
              The dictionary should have a single key: "packages", which is a list of
              package names.
            - services (list): A list of system services that are enabled.
    """
    with open(f"{state_path}/installed_packages", "r") as f:
        packages = json.load(f)
    with open(f"{state_path}/enabled_services", "r") as f:
        services = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    return packages, services


# ============================================================================
# PHASE 2 BACKWARD COMPATIBILITY ALIASES
# ============================================================================
# New modules import and wrap functions from here. This section provides
# import aliases so existing code (kod.py, tests) continues to work.
# Once Phase 2 refactoring is complete, these can be deprecated.

# Workflow entry points (to be moved to kod/core/{install,rebuild,user_config}.py)
# Currently imported from this module, will re-export from new modules

# System operations (to be moved to kod/system/{packages,services,boot,filesystem,users}.py)
# Currently imported from this module, will re-export from new modules

# This section should remain minimal - only add aliases for functions that
# are actually imported by kod.py or tests.


def __getattr__(name: str):
    """Lazy import of refactored functions from kod.system modules.
    
    This allows kod.py to continue importing from kod.core while the actual
    implementations have been moved to respective system modules.
    """
    # Rebuild workflow functions (moved to kod.core.rebuild)
    if name in {
        'get_generation',
        'get_max_generation',
        'create_next_generation',
    }:
        from kod.core import rebuild as rebuild_module
        return getattr(rebuild_module, name)
    
    # Package management functions (moved to kod.system.packages)
    if name in {
        'get_packages_to_install',
        'manage_packages',
        'load_repos',
        'load_package_lock',
        'store_packages_services',
        'get_packages_updates',
        'update_all_packages',
        'get_pending_packages',
        'manage_packages_shell',
    }:
        from kod.system import packages as packages_module
        return getattr(packages_module, name)
    
    # Service management functions (moved to kod.system.services)
    if name in {
        'enable_services',
        'disable_services',
        'enable_user_services',
        'get_services_to_enable',
        'proc_desktop_services',
        'proc_services',
        'proc_services_to_enable',
    }:
        from kod.system import services as services_module
        return getattr(services_module, name)
    
    # User configuration functions (moved to kod.core.user_config)
    if name in {
        'configure_user_dotfiles',
        'configure_user_scripts',
    }:
        from kod.core import user_config as user_config_module
        return getattr(user_config_module, name)
    
    # System configuration functions (moved to kod.core.install)
    if name in {
        'configure_system',
    }:
        from kod.core import install as install_module
        return getattr(install_module, name)
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
