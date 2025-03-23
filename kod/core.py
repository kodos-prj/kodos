# Core functionality

import os
from pathlib import Path
from typing import List

import lupa as lua

from kod.common import exec_chroot, exec
from kod.arch import get_kernel_file, setup_linux
from kod.arch import get_base_packages
import re
import glob
import json
from kod.arch import get_list_of_dependencies
from kod.filesytem import FsEntry
from kod.arch import kernel_update_rquired

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


base_distribution = "arch"


def set_base_distribution(base_dist):
    global base_distribution
    base_distribution = base_dist
    if base_dist == "debian":
        import kod.debian as dist

        return dist
    import kod.arch as dist

    return dist


# Core
def load_config(config_filename: str):
    """
    Load configuration from a file and return it as a table.

    The configuration file is a Lua file that contains different sections to configure
    the different aspects of the system.
    """

    luart = lua.LuaRuntime(unpack_returned_tuples=True)

    if config_filename is None:
        config_filename = "/etc/kodos"

    if Path(config_filename).is_dir():
        config_filename = Path(config_filename).joinpath("configuration.lua")

    print(f"Config file: {config_filename}")
    config_path = Path(config_filename).resolve().parents[0]
    luart.execute(f"package.path = '{config_path}/?.lua;' .. package.path")
    lib_path = Path(__file__).resolve().parents[0]
    luart.execute(f"package.path = '{lib_path}/lib/?.lua;' .. package.path")
    luart.execute("package.path = 'kod/lib/?.lua;' .. package.path")
    luart.execute("print(package.path)")
    print("Loading default libraries")
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
def generate_fstab(partiton_list: List, mount_point: str):
    """
    Generate a fstab file at the specified mount point based on a list of Partitions.

    Args:
        partiton_list (List): A list of Partition objects to be written to the fstab file.
        mount_point (str): The mount point where the fstab file will be written.
    """
    print("Generating fstab")
    with open(f"{mount_point}/etc/fstab", "w") as f:
        for part in partiton_list:
            if part.source[:5] == "/dev/":
                uuid = exec(f"lsblk -o UUID {part.source} | tail -n 1", get_output=True)
                if uuid:
                    part.source = f"UUID={uuid.strip()}"
            f.write(str(part) + "\n")


# Core?
def configure_system(conf, partition_list, mount_point: str):
    # fstab
    """
    Configure a system based on the given configuration.

    This function configures the network, timezone, localization, and other settings
    for the given system. It also configures the schroot environment and generates
    the necessary files for it.

    Args:
        conf (table): The configuration table.
        partition_list (List): A list of Partition objects to be written to the fstab file.
        mount_point (str): The mount point where the system will be configured.
    """
    generate_fstab(partition_list, mount_point)

    # Locale
    locale_conf = conf.locale
    if locale_conf:
        time_zone = locale_conf["timezone"]
    else:
        time_zone = "GMT"
    exec_chroot(f"ln -sf /usr/share/zoneinfo/{time_zone} /etc/localtime")
    exec_chroot("hwclock --systohc")

    # Localization
    locale_spec = locale_conf.locale
    locale_default = locale_spec.default
    locale_to_generate = locale_default + "\n"
    if "extra_generate" in locale_spec and locale_spec.extra_generate:
        locale_to_generate += "\n".join(list(locale_spec.extra_generate.values()))
    with open(f"{mount_point}/etc/locale.gen", "w") as locale_file:
        locale_file.write(locale_to_generate + "\n")
    exec_chroot("locale-gen")

    locale_name = locale_default.split()[0]
    locale_extra = locale_name + "\n"
    if "extra_settings" in locale_spec and locale_spec.extra_settings:
        for k, v in locale_spec.extra_settings.items():
            locale_extra += f"{k}={v}\n"
    with open(f"{mount_point}/etc/locale.conf", "w") as locale_file:
        locale_file.write(f"LANG={locale_extra}\n")

    # Network
    network_conf = conf.network

    # hostname
    hostname = network_conf["hostname"]
    exec(f"echo '{hostname}' > {mount_point}/etc/hostname")
    use_ipv4 = network_conf["ipv4"] if "ipv4" in network_conf else True
    use_ipv6 = network_conf["ipv6"] if "ipv6" in network_conf else True
    eth0_network = """[Match]
Name=*
[Network]
"""
    if use_ipv4:
        eth0_network += "DHCP=ipv4\n"
    if use_ipv6:
        eth0_network += "DHCP=ipv6\n"
    with open(f"{mount_point}/etc/systemd/network/10-eth0.network", "w") as f:
        f.write(eth0_network)

    # hosts
    exec_chroot("echo '127.0.0.1 localhost' > /etc/hosts")
    exec_chroot("echo '::1 localhost' >> /etc/hosts")

    # Replace default os-release
    with open(f"{mount_point}/etc/os-release", "w") as f:
        f.write(os_release)

    # Configure schroot
    system_schroot = """[system]
type=directory
description=KodOS
directory=/
groups=users,root
root-groups=root,wheel
profile=kodos
personality=linux
"""
    with open(f"{mount_point}/etc/schroot/chroot.d/system.conf", "w") as f:
        f.write(system_schroot)

    venv_schroot = """[virtual_env]
type=directory
description=KodOS
directory=/
union-type=overlay
groups=users,root
root-groups=root,wheel
profile=kodos
personality=linux
aliases=user_env
"""
    with open(f"{mount_point}/etc/schroot/chroot.d/virtual_env.conf", "w") as f:
        f.write(venv_schroot)

    # Setting profile
    os.system(f"mkdir -p {mount_point}/etc/schroot/kodos")
    os.system(f"touch {mount_point}/etc/schroot/kodos/copyfiles")
    os.system(f"touch {mount_point}/etc/schroot/kodos/nssdatabases")

    venv_fstab = "# <file system> <mount point>   <type>  <options>       <dump>  <pass>"
    for mpoint in [
        "/proc",
        "/sys",
        "/dev",
        "/dev/pts",
        "/home",
        "/root",
        "/tmp",
        "/run",
        "/var/cache",
        "/var/log",
        "/var/tmp",
        "/var/kod",
    ]:
        venv_fstab += f"{mpoint}\t{mpoint}\tnone\trw,bind\t0\t0\n"

    with open(f"{mount_point}/etc/schroot/kodos/fstab", "w") as f:
        f.write(venv_fstab)


# Core
def get_kernel_version(mount_point: str):
    """
    Retrieve the kernel version from the specified mount point.

    Args:
        mount_point (str): The mount point of the chroot environment to retrieve the kernel version from.

    Returns:
        str: The kernel version as a string.
    """
    kernel_version = exec_chroot("uname -r", mount_point=mount_point, get_output=True).strip()
    return kernel_version


# Core
def create_boot_entry(
    generation,
    partition_list,
    boot_options=None,
    is_current=False,
    mount_point="/mnt",
    kver=None,
):
    """
    Create a systemd-boot loader entry for the specified generation.

    Args:
        generation (int): The generation number to create an entry for.
        partition_list (list): A list of Partition objects to use for determining the root device.
        boot_options (list, optional): A list of additional boot options to include in the entry.
        is_current (bool, optional): If True, the entry will be named "kodos" and set as the default.
        mount_point (str, optional): The mount point of the chroot environment to write the entry to.
        kver (str, optional): The kernel version to use in the entry. If not provided, the current kernel
            version will be determined using `uname -r` in the chroot environment.
    """
    subvol = f"generations/{generation}/rootfs"
    root_fs = [part for part in partition_list if part.destination in ["/"]][0]
    root_device = root_fs.source_uuid()
    options = " ".join(boot_options) if boot_options else ""
    options += f" rootflags=subvol={subvol}"
    entry_name = "kodos" if is_current else f"kodos-{generation}"

    if not kver:
        kver = get_kernel_version(mount_point)

    today = exec("date +'%Y-%m-%d %H:%M:%S'", get_output=True).strip()
    entry_conf = f"""
title KodOS
sort-key kodos
version Generation {generation} KodOS (build {today} - {kver})
linux /vmlinuz-{kver}
initrd /initramfs-linux-{kver}.img
options root={root_device} rw {options}
    """
    entries_path = f"{mount_point}/boot/loader/entries/"
    if not os.path.isdir(entries_path):
        os.makedirs(entries_path)
    with open(f"{mount_point}/boot/loader/entries/{entry_name}.conf", "w") as f:
        f.write(entry_conf)

    # Update loader.conf
    loader_conf_systemd = f"""
default {entry_name}.conf
timeout 10
console-mode keep
"""
    with open(f"{mount_point}/boot/loader/loader.conf", "w") as f:
        f.write(loader_conf_systemd)


# Core
def setup_bootloader(conf, partition_list, dist):
    # bootloader
    """
    Set up the bootloader based on the configuration.

    Args:
        conf (dict): The configuration dictionary.
        partition_list (list): A list of Partition objects to use for determining the root device.
    """
    boot_conf = conf.boot
    loader_conf = boot_conf["loader"]

    if "kernel" in boot_conf and "package" in boot_conf["kernel"]:
        kernel_package = boot_conf["kernel"]["package"]
    else:
        kernel_package = "linux"

    # Default bootloader
    boot_type = "systemd-boot"

    if "type" in loader_conf:
        boot_type = loader_conf["type"]

    # Using systemd-boot as bootloader
    if boot_type == "systemd-boot":
        print("==== Setting up systemd-boot ====")
        kver = dist.setup_linux(kernel_package)
        # if base_distribution == "arch":
        #     kernel_file, kver = get_kernel_file(mount_point="/mnt", package=kernel_package)
        #     exec_chroot(f"cp {kernel_file} /boot/vmlinuz-linux-{kver}")
        # else:
        #     kernel_file, kver = get_kernel_file(mount_point="/mnt", package=kernel_package)
        exec_chroot("bootctl install")
        print("KVER:", kver)
        exec_chroot(f"dracut --kver {kver} --hostonly /boot/initramfs-linux-{kver}.img")
        create_boot_entry(0, partition_list, mount_point="/mnt", kver=kver)

    # Using Grub as bootloader
    if boot_type == "grub":
        pass
        # pkgs_required = ["grub", "efibootmgr", "grub-btrfs"]
        # if "include" in loader_conf:
        #     pkgs_required += loader_conf["include"].values()

        # exec_chroot(f"pacman -S --noconfirm {' '.join(pkgs_required)}")
        # exec_chroot(
        #     "grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB",
        # )
        # exec_chroot("grub-mkconfig -o /boot/grub/grub.cfg")
        # # pkgs_installed += ["efibootmgr"]


# Core
def get_packages_to_install(conf):
    """
    Determine the packages to install and remove based on the given configuration.

    This function aggregates various categories of packages such as base, desktop,
    hardware, services, user programs, system packages, and fonts. It consolidates
    these into a list of packages to install and a list of packages to remove.

    Args:
        conf (table): The configuration table containing details for package selection.

    Returns:
        tuple: A tuple containing two elements:
            - packages_to_install (dict): A dictionary with a "packages" key listing
              all the unique packages to be installed.
            - packages_to_remove (list): A list of packages to be removed.
    """
    packages_to_install = []
    packages_to_remove = []

    # Base packages
    base_packages = get_base_packages(conf)

    # Desktop
    desktop_packages_to_install, desktop_packages_to_remove = proc_desktop(conf)

    # Hardware
    hw_packages_to_install = proc_hardware(conf)

    # Services
    service_packages_to_install = proc_services(conf)

    # User programs
    user_packages_to_install = proc_user_programs(conf)

    # System packages
    system_packages_to_install = proc_system_packages(conf)

    # Font packages
    font_packages_to_install = proc_fonts(conf)

    packages_to_install = base_packages.copy()
    packages_to_install["packages"] = list(
        set(
            desktop_packages_to_install
            + hw_packages_to_install
            + service_packages_to_install
            + user_packages_to_install
            + system_packages_to_install
            + font_packages_to_install
        )
    )

    packages_to_remove = list(set(desktop_packages_to_remove))

    return packages_to_install, packages_to_remove


# Core
def update_fstab(root_path, new_mount_point_map):
    """
    Update the fstab file at the specified root path with new subvolume IDs for specified mount points.

    This function reads the existing fstab file, modifies the subvolume options for mount points
    present in the `new_mount_point_map`, and writes the updated lines back to the fstab file.

    Args:
        root_path (str): The root path where the fstab file is located.
        new_mount_point_map (dict): A dictionary mapping mount points to their new subvolume IDs.

    """
    with open(f"{root_path}/etc/fstab") as f:
        fstab = f.readlines()
    with open(f"{root_path}/etc/fstab", "w") as f:
        for line in fstab:
            cols = line.split()
            if len(cols) > 4 and cols[1] in new_mount_point_map:
                subvol_id = new_mount_point_map[cols[1]]
                cols[3] = re.sub(r"subvol=[^,]+", f"subvol={subvol_id}", cols[3])
                line = "\t".join(cols) + "\n"
            f.write(line)


# Core
def change_subvol(partition_list, subvol, mount_points):
    """
    Modify the partition list by changing the subvolume of the given mount points to the given subvolume.

    Args:
        partition_list (list): The list of Partition objects to modify.
        subvol (str): The new subvolume.
        mount_points (list): The list of mount points to modify.

    Returns:
        list: The modified partition list.
    """
    for part in partition_list:
        if part.destination in mount_points:
            options = part.options.split(",")
            for opt in options:
                if opt.startswith("subvol="):
                    subvol_path = opt.split("/")[-1]
                    part.options = part.options.replace(opt, f"subvol={subvol}/{subvol_path}")
    return partition_list


# Core
def set_ro_mount(mount_point):
    """
    Set the given mount point to be read-only.

    This function takes a mount point and mounts it read-only. This is useful for
    making sure that the system files are not modified during the installation
    process.

    Args:
        mount_point (str): The mount point to set to read-only.
    """
    exec(f"mount -o remount,ro,bind {mount_point}")


# Core
def change_ro_mount(root_path):
    """
    Modify the fstab file at the given root path to mount /usr read-only.

    This function reads the existing fstab file, modifies the mount options for /usr
    to be read-only, and writes the updated lines back to the fstab file.

    Args:
        root_path (str): The root path where the fstab file is located.
    """
    with open(f"{root_path}/etc/fstab") as f:
        fstab = f.readlines()
    with open(f"{root_path}/etc/fstab", "w") as f:
        for line in fstab:
            if "/usr" in line:
                line = line.replace("rw,", "ro,")
            f.write(line)


# Core
def get_max_generation():
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
def load_repos() -> dict | None:
    """
    Load the repository configuration from the file /var/kod/repos.json.

    Returns a dictionary with the repository configuration, or None if the file
    does not exist or is not a valid JSON file.

    """
    repos = None
    with open("/var/kod/repos.json") as f:
        repos = json.load(f)
    return repos


# Core
def create_kod_user(mount_point):
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


# Core
# TODO: Replace official with check of default repo flag
def manage_packages(root_path, repos, action, list_of_packages, chroot=False):
    """
    Manage package installation, update, or removal based on the provided repository configuration.

    This function organizes the packages into their respective repositories,
    executes the specified action (install, update, or remove) for each package
    using the corresponding repository command, and handles privilege escalation
    as needed based on the repository configuration and `chroot` flag.

    Args:
        root_path (str): The root path for chroot operations, if applicable.
        repos (dict): A dictionary containing repository configurations and commands.
        action (str): The action to perform on the packages (e.g., 'install', 'update', 'remove').
        list_of_packages (list): A list of package names, potentially prefixed with
                                 the repository name followed by a colon.
        chroot (bool, optional): If True, execute the commands in a chroot environment
                                 based at `root_path`. Defaults to False.

    Returns:
        list: A list of installed package names.
    """
    packages_installed = []
    pkgs_per_repo = {"official": []}
    for pkg in list_of_packages:
        if ":" in pkg:
            repo, pkg_name = pkg.split(":")
            if repo not in pkgs_per_repo:
                pkgs_per_repo[repo] = []
            pkgs_per_repo[repo].append(pkg_name)
        else:
            pkgs_per_repo["official"].append(pkg)

    for repo, pkgs in pkgs_per_repo.items():
        if len(pkgs) == 0:
            continue
        if "run_as_root" in repos[repo] and not repos[repo]["run_as_root"]:
            if chroot:
                exec_chroot(
                    f"runuser -u kod -- {repos[repo][action]} {' '.join(pkgs)}",
                    mount_point=root_path,
                )
            else:
                exec(f"runuser -u kod -- {repos[repo][action]} {' '.join(pkgs)}")
        else:
            if chroot:
                exec_chroot(f"{repos[repo][action]} {' '.join(pkgs)}", mount_point=root_path)
            else:
                exec(f"{repos[repo][action]} {' '.join(pkgs)}")
        packages_installed += pkgs
    return packages_installed


# --------------------------------------


# Core
def proc_desktop(conf):
    """
    Process the desktop configuration and generate the list of packages to install
    and remove. This function will iterate over the desktop manager options and
    process the packages to install and remove based on the configuration.

    Args:
        conf (dict): The configuration dictionary containing the desktop configuration.

    Returns:
        tuple: A tuple containing two lists: packages to install and packages to remove.
    """
    packages_to_install = []
    packages_to_remove = []
    desktop = conf.desktop

    display_manager = desktop.display_manager
    if display_manager:
        print(f"Installing {display_manager}")
        packages_to_install += [display_manager]

    desktop_manager = desktop.desktop_manager
    if desktop_manager:
        for desktop_mngr, dm_conf in desktop_manager.items():
            if dm_conf.enable:
                print(f"Installing {desktop_mngr}")
                if "extra_packages" in dm_conf:
                    pkg_list = list(dm_conf.extra_packages.values())
                    packages_to_install += pkg_list

                if "exclude_packages" in dm_conf:
                    exclude_pkg_list = list(dm_conf.exclude_packages.values())
                    packages_to_remove += exclude_pkg_list
                else:
                    exclude_pkg_list = []
                if exclude_pkg_list:
                    print(f"Excluding {exclude_pkg_list}")
                    all_pkgs_to_install = get_list_of_dependencies(desktop_mngr)
                    pkgs_to_install = list(set(all_pkgs_to_install) - set(exclude_pkg_list))
                    packages_to_install += pkgs_to_install
                else:
                    packages_to_install += [desktop_mngr]

                if "display_manager" in dm_conf:
                    display_mngr = dm_conf["display_manager"]
                    packages_to_install += [display_mngr]

    return packages_to_install, packages_to_remove


# Core
def proc_desktop_services(conf):
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


# Core
def proc_hardware(conf):
    """
    Process the hardware configuration and generate the list of packages to install.

    This function iterates over the hardware configuration and generates a list of
    packages to install based on the configuration settings.

    Args:
        conf (dict): The configuration dictionary containing the hardware settings.

    Returns:
        list: A list of package names that need to be installed.
    """
    packages = []
    print("- processing hardware -----------")
    hardware = conf.hardware
    for name, hw in hardware.items():
        print(name, hw.enable)
        pkgs = []
        if hw.enable:
            if hw.package:
                print("  using:", hw.package)
                name = hw.package

            pkgs.append(name)
            if hw.extra_packages:
                print("  extra packages:", hw.extra_packages)
                for _, pkg in hw.extra_packages.items():
                    pkgs.append(pkg)
            packages += pkgs

    return packages


# Core
def proc_system_packages(conf):
    """
    Process the system packages configuration and generate a list of packages to install.

    This function extracts the system packages defined in the configuration
    and returns them as a list.

    Args:
        conf (dict): The configuration dictionary containing the system
                     packages information.

    Returns:
        list: A list of system package names to be installed.
    """

    print("- processing packages -----------")
    sys_packages = list(conf.packages.values())
    return sys_packages


# Core
def get_services_to_enable(ctx, conf):
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


# Core
def proc_services(conf):
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


# Core
def proc_services_to_enable(ctx, conf):
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


# Core
def create_user(ctx, user, info):
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
            ctx.execute(f"usermod -p `mkpasswd -m sha-512 {info.password}` {user}")
        else:
            ctx.execute(f"passwd {user}")


# Core
def proc_user_dotfile_manager(conf):
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
def user_dotfile_manager(info):
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
def proc_user_programs(conf):
    """
    Process the user programs configuration and generate a list of packages to install.

    This function iterates over the user configuration and extracts the programs
    that need to be installed. It returns a list of packages to be installed.

    Args:
        conf (dict): The configuration dictionary containing the user
                     information.

    Returns:
        list: A list of packages to be installed.
    """
    packages = []

    print("- processing user programs -----------")
    users = conf.users

    for user, info in users.items():
        if info.programs:
            print(f"Processing programs for {user}")
            pkgs = []
            for name, prog in info.programs.items():
                print(name, prog.enable)
                if prog.enable:
                    if prog.package:
                        print("  using:", prog.package)
                        name = prog.package

                    if prog.extra_packages:
                        print("  extra packages:", prog.extra_packages)
                        for _, pkg in prog.extra_packages.items():
                            pkgs.append(pkg)
                    pkgs.append(name)
            packages += pkgs

        # Packages required for user services
        if info.services:
            for service, desc in info.services.items():
                if "enable" in desc and desc.enable:
                    print(f"Checking {service} service discription")
                    name = service
                    if "package" in desc:
                        name = desc.package

                    if desc.extra_packages:
                        print("  extra packages:", desc.extra_packages)
                        for _, pkg in desc.extra_packages.items():
                            packages.append(pkg)
                    packages.append(name)

    return packages


# Core
def proc_user_configs(conf):
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
def user_configs(user, info):
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
def proc_user_home(ctx, user, info):
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


# Core
def proc_user_services(conf):
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
def user_services(user, info):
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
def proc_fonts(conf):
    """
    Process the fonts configuration and generate a list of font packages to install.

    This function examines the fonts configuration and returns a list of font
    packages specified in the configuration.

    Args:
        conf (dict): The configuration dictionary containing the fonts
                     information.

    Returns:
        list: A list of font package names to be installed.
    """

    packages_to_install = []
    print("- processing fonts -----------")
    fonts = conf.fonts
    if fonts and "packages" in fonts and fonts.packages:
        packages_to_install += fonts.packages.values()
    return packages_to_install


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

    def __init__(self, user, mount_point="/mnt", use_chroot=True, stage="install"):
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

    def execute(self, command):
        """
        Execute a command in the specified context.

        This method constructs and executes a command based on the current context,
        which includes the user, mount point, and chroot settings. If the context
        user is different from the current environment user, the command is wrapped
        with 'su' for user substitution. If chroot execution is enabled, the command
        is executed within the chroot environment at the specified mount point.

        Args:
            command (str): The command to execute.

        Returns:
            bool: True if the command is executed successfully.
        """
        if self.user == os.environ["USER"]:
            exec_prefix = ""
        else:
            exec_prefix = f" su {self.user} -c "

        def wrap(s):
            if self.user == os.environ["USER"]:
                return s
            else:
                return f"'{s}'"

        print(f"[Contex] Command: {command}")
        if self.use_chroot:
            exec_chroot(f"{exec_prefix} {wrap(command)}", mount_point=self.mount_point)
        else:
            exec(f"{exec_prefix} {wrap(command)}")
        return True


# Core
def configure_user_dotfiles(ctx, user, user_configs, dotfile_mngrs):
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


# Core
def configure_user_scripts(ctx, user, user_configs):
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


# Core
def enable_services(list_of_services, mount_point="/mnt", use_chroot=False):
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


# Core
def disable_services(list_of_services, mount_point="/mnt", use_chroot=False):
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


# Core
def enable_user_services(ctx, user, services):
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


# Core
def load_fstab(root_path=""):
    """
    Load a list of Partition objects from the specified fstab file.

    This function reads the specified fstab file, parses its entries, and
    returns a list of Partition objects representing the filesystem
    hierarchy described in the file. The Partition objects are created
    using the FsEntry class.

    Args:
        root_path (str, optional): The root path from which to read the
            fstab file. Defaults to the current working directory.

    Returns:
        list: A list of Partition objects representing the filesystem
            hierarchy described in the fstab file.
    """
    partition_list = []
    with open(f"{root_path}/etc/fstab") as f:
        entries = f.readlines()

    for entry in entries:
        if not entry or entry == "\n" or entry.startswith("#"):
            continue
        (device, mount_point, fs_type, options, dump, pass_) = entry.split()
        partition_list.append(FsEntry(device, mount_point, fs_type, options, int(dump), int(pass_)))
    return partition_list


# Core
def create_filesystem_hierarchy(boot_part, root_part, partition_list, mount_point):
    """
    Create and configure a Btrfs filesystem hierarchy for KodOS.

    This function sets up the initial filesystem hierarchy for KodOS using Btrfs
    subvolumes. It creates necessary directories and subvolumes, mounts the first
    generation, and binds the appropriate directories. It also creates and mounts
    the boot and kod partitions.

    Args:
        boot_part: The boot partition to be mounted.
        root_part: The root partition to be used for creating subvolumes.
        partition_list: A list of Partition objects representing the filesystem hierarchy.
        mount_point: The mount point where the filesystem hierarchy will be created.

    Returns:
        list: An updated list of Partition objects reflecting the created filesystem hierarchy.
    """
    print("===================================")
    print("== Creating filesystem hierarchy ==")
    # Initial generation
    generation = 0
    for dir in ["store", "generations", "current"]:
        exec(f"mkdir -p {mount_point}/{dir}")

    subdirs = ["root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for dir in subdirs:
        exec(f"mkdir -p {mount_point}/store/{dir}")

    # Create home as subvolume if no /home is specified in the config
    # (TODO: Add support for custom home)
    exec(f"sudo btrfs subvolume create {mount_point}/store/home")

    # First generation
    exec(f"mkdir -p {mount_point}/generations/{generation}")
    exec(f"btrfs subvolume create {mount_point}/generations/{generation}/rootfs")

    # Mounting first generation
    exec(f"umount -R {mount_point}")
    exec(f"mount -o subvol=generations/{generation}/rootfs {root_part} {mount_point}")
    partition_list = [
        FsEntry(
            root_part,
            "/",
            "btrfs",
            f"rw,relatime,ssd,space_cache=v2,subvol=generations/{generation}/rootfs",
        )
    ]

    for dir in subdirs + ["boot", "home", "kod"]:
        exec(f"mkdir -p {mount_point}/{dir}")

    exec(f"mount {boot_part} {mount_point}/boot")
    boot_options = (
        "rw,relatime,fmask=0022,dmask=0022,codepage=437,iocharset=ascii,shortname=mixed,utf8,errors=remount-ro"
    )
    partition_list.append(FsEntry(boot_part, "/boot", "vfat", boot_options))

    exec(f"mount {root_part} {mount_point}/kod")
    partition_list.append(FsEntry(root_part, "/kod", "btrfs", "rw,relatime,ssd,space_cache=v2"))

    btrfs_options = "rw,relatime,ssd,space_cache=v2"

    exec(f"mount -o subvol=store/home {root_part} {mount_point}/home")
    partition_list.append(FsEntry(root_part, "/home", "btrfs", btrfs_options + ",subvol=store/home"))

    for dir in subdirs:
        exec(f"mount --bind {mount_point}/kod/store/{dir} {mount_point}/{dir}")
        partition_list.append(FsEntry(f"/kod/store/{dir}", f"/{dir}", "none", "rw,bind"))

    # Write generation number
    with open(f"{mount_point}/.generation", "w") as f:
        f.write(str(generation))

    print("===================================")

    return partition_list


# Core
def create_next_generation(boot_part, root_part, generation):
    """
    Create the next generation of the KodOS installation.

    Mounts the generation at /.next_current and sets up the subvolumes and
    mounts the partitions as specified in the fstab file.

    Args:
        boot_part (str): The device name of the boot partition
        root_part (str): The device name of the root partition
        generation (int): The generation number to create

    Returns:
        str: The path to the mounted generation
    """
    next_current = "/kod/current/.next_current"
    # Mounting generation
    if os.path.ismount(next_current):
        print("Reboot is required to update generation")
        os._exit(0)
        exec(f"umount -R {next_current}")
        exec(f"rm -rf {next_current}")

    exec(f"mkdir -p {next_current}")

    exec(f"mount -o subvol=generations/{generation}/rootfs {root_part} {next_current}")
    exec(f"mount {boot_part} {next_current}/boot")
    exec(f"mount {root_part} {next_current}/kod")
    exec(f"mount -o subvol=store/home {root_part} {next_current}/home")

    subdirs = ["root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for dir in subdirs:
        exec(f"mount --bind /kod/store/{dir} {next_current}/{dir}")

    partition_list = load_fstab()
    change_subvol(partition_list, subvol=f"generations/{generation}", mount_points=["/"])
    generate_fstab(partition_list, next_current)

    # Write generation number
    with open(f"{next_current}/.generation", "w") as f:
        f.write(str(generation))

    print("===================================")

    return next_current


# Core
def update_all_packages(mount_point, new_generation, repos):
    """
    Updates all packages in the system.

    Args:
        mount_point (str): The mount point of the chroot environment.
        new_generation (bool): If True, run pacman inside the chroot environment.
        repos (dict): A dictionary containing repository configurations and commands.
    """
    # Use the repo update entry for all the repos
    for repo, repo_desc in repos.items():
        if "update" in repo_desc:
            print(f"Updating {repo}")
            if new_generation:
                if "run_as_root" in repo_desc and not repo_desc["run_as_root"]:
                    exec_chroot(
                        f"runuser -u kod -- {repo_desc['update']} --noconfirm",
                        mount_point=mount_point,
                    )
                else:
                    exec_chroot(f"{repo_desc['update']}", mount_point=mount_point)
            else:
                if "run_as_root" in repo_desc and not repo_desc["run_as_root"]:
                    exec(
                        f"runuser -u kod -- {repo_desc['update']} --noconfirm",
                        mount_point=mount_point,
                    )
                else:
                    exec(f"{repo_desc['update']}", mount_point=mount_point)


# Core
def proc_users(ctx, conf):
    """
    Process all users in the given configuration.

    For each user, this function creates the user, configures their dotfile manager,
    configures their programs, and enables their services.

    Args:
        ctx (Context): The context object used for executing commands.
        conf (dict): The configuration dictionary containing user information.
    """
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


# Core
def get_generation(mount_point):
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
def get_pending_packages(packages_to_install):
    """
    Get the list of packages that are pending installation.

    Args:
        packages_to_install (dict): A dictionary containing the packages to install.
            The dictionary should have a single key: "packages", which is a list of
            package names.

    Returns:
        list: A list of package names that are pending installation.
    """
    pending_to_install = packages_to_install["packages"]
    return pending_to_install


# Core
def store_packages_services(state_path, packages_to_install, system_services):
    """
    Store the list of packages that are installed and the list of services that are enabled.

    Stores the list of packages that are installed in a JSON file and the list of services
    that are enabled in a plain text file.

    Args:
        state_path (str): The path to the state directory where the package and service
            information should be stored.
        packages_to_install (dict): A dictionary containing the packages to install.
            The dictionary should have a single key: "packages", which is a list of
            package names.
        system_services (list): A list of system services that are enabled.
    """
    packahes_json = json.dumps(packages_to_install, indent=2)
    with open(f"{state_path}/installed_packages", "w") as f:
        f.write(packahes_json)
    with open(f"{state_path}/enabled_services", "w") as f:
        f.write("\n".join(system_services))


# Core
def load_packages_services(state_path):
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


# Core
def load_package_lock(state_path):
    """
    Load the list of installed packages and their versions from a lock file.

    This function reads a file named `packages.lock` located at the provided
    `state_path`. Each line of the file should contain a package name followed
    by its version, separated by a space. The function parses the file and
    returns a dictionary mapping package names to their respective versions.

    Args:
        state_path (str): The path to the directory containing the `packages.lock` file.

    Returns:
        dict: A dictionary where keys are package names and values are their corresponding versions.
    """
    packages = {}
    with open(f"{state_path}/packages.lock") as f:
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue
            package, version = line.split(" ")
            packages[package] = version
    return packages


# Core
def update_kernel_hook(kernel_package, mount_point):
    """
    Create a hook function to update the kernel for a specified package.

    This function generates a hook that, when executed, copies the kernel file
    for the specified kernel package from the chroot environment at the given
    mount point to the /boot directory with a versioned filename.

    Args:
        kernel_package (str): The name of the kernel package to update.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        function: A hook function that performs the kernel update.
    """

    def hook():
        print(f"Update kernel ....{kernel_package}")
        kernel_file, kver = get_kernel_file(mount_point, package=kernel_package)
        print(f"{kver=}")
        print(f"cp {kernel_file} /boot/vmlinuz-linux-{kver}")
        exec_chroot(f"cp {kernel_file} /boot/vmlinuz-linux-{kver}", mount_point=mount_point)

    return hook


# Core
def update_initramfs_hook(kernel_package, mount_point):
    """
    Create a hook function to update the initramfs for a specified package.

    This function generates a hook that, when executed, generates an initramfs
    file for the specified kernel package from the chroot environment at the
    given mount point.

    Args:
        kernel_package (str): The name of the kernel package to update.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        function: A hook function that performs the initramfs update.
    """

    def hook():
        print(f"Update initramfs ....{kernel_package}")
        kernel_file, kver = get_kernel_file(mount_point, package=kernel_package)
        print(f"{kver=}")
        exec_chroot(
            f"dracut --kver {kver} --hostonly /boot/initramfs-linux-{kver}.img",
            mount_point=mount_point,
        )

    return hook


# Core
def get_packages_updates(
    current_packages,
    next_packages,
    remove_packages,
    current_installed_packages,
    mount_point,
):
    """
    Determine the packages to install, remove, and update, as well as any necessary hooks to run.

    This function compares the current and next package sets to decide which packages
    need to be installed, removed, or updated. It also determines if a kernel update is
    required and prepares appropriate hooks for updating the kernel and initramfs.

    Args:
        current_packages (dict): A dictionary containing information about currently installed packages.
        next_packages (dict): A dictionary containing information about packages to be installed.
        remove_packages (list): A list of package names to be removed.
        current_installed_packages (dict): A dictionary mapping currently installed package names to their versions.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        tuple: A tuple containing four elements:
            - packages_to_install (list): A list of package names that need to be installed.
            - packages_to_remove (list): A list of package names that need to be removed.
            - packages_to_update (list): A list of package names that need to be updated.
            - hooks_to_run (list): A list of hook functions that need to be executed.
    """

    packages_to_install = []
    packages_to_remove = []
    packages_to_update = []
    hooks_to_run = []
    current_kernel = current_packages["kernel"]
    next_kernel = next_packages["kernel"]
    if kernel_update_rquired(current_kernel, next_kernel, current_installed_packages, mount_point):
        packages_to_install += [next_kernel]
        hooks_to_run += [
            update_kernel_hook(next_kernel, mount_point),
            update_initramfs_hook(next_kernel, mount_point),
        ]

    remove_pkg = (set(current_packages["packages"]) - set(next_packages["packages"])) | set(remove_packages)
    packages_to_remove += list(remove_pkg)

    added_pkgs = set(next_packages["packages"]) - set(current_packages["packages"])
    packages_to_install += list(added_pkgs)

    update_pkg = set(current_packages) & set(next_packages)
    packages_to_update += list(update_pkg)

    return packages_to_install, packages_to_remove, packages_to_update, hooks_to_run


# Core
def manage_packages_shell(repos, action, list_of_packages, chroot):
    pkgs_per_repo = {"official": []}
    for pkg in list_of_packages:
        if ":" in pkg:
            repo, pkg_name = pkg.split(":")
            if repo not in pkgs_per_repo:
                pkgs_per_repo[repo] = []
            pkgs_per_repo[repo].append(pkg_name)
        else:
            pkgs_per_repo["official"].append(pkg)

    print(f"{pkgs_per_repo = }")
    for repo, pkgs in pkgs_per_repo.items():
        print(repo, "->", pkgs)
        if len(pkgs) == 0:
            continue
        if "run_as_root" in repos[repo] and not repos[repo]["run_as_root"]:
            print(f"schroot -r -c {chroot} -- {repos[repo][action]} {' '.join(pkgs)}")
            exec(f"schroot -r -c {chroot} -- {repos[repo][action]} {' '.join(pkgs)}")
        else:
            exec(f"schroot -r -c {chroot} -u root -- {repos[repo][action]} {' '.join(pkgs)}")
