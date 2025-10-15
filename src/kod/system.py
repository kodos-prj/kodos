"""System configuration, file system and hardware management for KodOS."""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any

import lupa as lua

from kod.common import exec, exec_chroot
from kod.filesystem import FsEntry

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


def is_dir(path: str) -> bool:
    return Path(path).is_dir()


def home_dir() -> str:
    return str(Path().home())


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


def generate_fstab(partiton_list: List, mount_point: str) -> None:
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


def update_fstab(root_path: str, new_mount_point_map: Dict[str, str]) -> None:
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


def change_subvol(partition_list: List, subvol: str, mount_points: List[str]) -> List:
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


def set_ro_mount(mount_point: str) -> None:
    """
    Set the given mount point to be read-only.

    This function takes a mount point and mounts it read-only. This is useful for
    making sure that the system files are not modified during the installation
    process.

    Args:
        mount_point (str): The mount point to set to read-only.
    """
    exec(f"mount -o remount,ro,bind {mount_point}")


def change_ro_mount(root_path: str) -> None:
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


def load_repos() -> Optional[Dict[str, Any]]:
    """
    Load the repository configuration from the file /var/kod/repos.json.

    Returns a dictionary with the repository configuration, or None if the file
    does not exist or is not a valid JSON file.

    """
    repos = None
    with open("/var/kod/repos.json") as f:
        repos = json.load(f)
    return repos


def load_fstab(root_path: str = "") -> List[str]:
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
