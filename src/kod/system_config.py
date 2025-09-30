"""System Configuration Module for KodOS.

This module handles system configuration tasks including locale, timezone,
network settings, hostname configuration, and schroot setup.
"""

import os
from typing import Any, List

from .common import exec, exec_chroot


OS_RELEASE = """NAME="KodOS Linux"
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


def configure_system(conf: Any, partition_list: List, mount_point: str) -> None:
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
    from kod.filesystem import generate_fstab

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
        f.write(OS_RELEASE)

    # Configure schroot
    configure_schroot(mount_point)


def configure_schroot(mount_point: str) -> None:
    """
    Configure schroot environment for KodOS.

    Args:
        mount_point (str): The mount point where the system is being configured.
    """
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


def get_kernel_version(mount_point: str) -> str:
    """
    Retrieve the kernel version from the specified mount point.

    Args:
        mount_point (str): The mount point of the chroot environment to retrieve the kernel version from.

    Returns:
        str: The kernel version as a string.
    """
    kernel_version = exec_chroot("uname -r", mount_point=mount_point, get_output=True).strip()
    return kernel_version
