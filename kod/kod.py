import glob
import json
import os
from pathlib import Path
import re
from inspect import getsourcefile
from os.path import abspath

# import signal
# from invoke import task
import click
import lupa as lua


from kod.common import set_debug, exec, exec_chroot
from kod.filesytem import FsEntry, create_partitions, get_partition_devices


#####################################################################################################
@click.group()
@click.option('-d', '--debug', is_flag=True)
def cli(debug):
    set_debug(debug)


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

pkgs_installed = []


def load_config(config_filename: str):
    luart = lua.LuaRuntime(unpack_returned_tuples=True)
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

def get_base_packages(conf):
    # CPU microcode
    with open("/proc/cpuinfo") as f:
        while True:
            line = f.readline()
            if "AuthenticAMD" in line:
                microcode = "amd-ucode"
                break
            if "GenuineIntel" in line:
                microcode = "intel-ucode"
                break

    if conf.boot and conf.boot.kernel and conf.boot.kernel.package:
        kernel_package = conf.boot.kernel.package
    else:
        kernel_package = "linux"

    # TODO: add verions to each package
    packages = {
        "kernel": kernel_package,
        "base": [
            "base",
            "base-devel",
            microcode,
            "btrfs-progs",
            "linux-firmware",
            "bash-completion",
            "mlocate",
            "sudo",
            "schroot",
            "whois",
            "dracut",
            "git",
        ]
    }

    # TODO: remove this package dependency
    packages["base"] += ["arch-install-scripts"]
    return packages


def install_essentials_pkgs(base_pkgs):
    exec(f"pacstrap -K /mnt {' '.join([base_pkgs["kernel"]] + base_pkgs['base'])}")


def generate_fstab(partiton_list, mount_point="/mnt"):
    print("Generating fstab")
    with open(f"{mount_point}/etc/fstab", "w") as f:
        for part in partiton_list:
            if part.source[:5] == "/dev/":
                uuid = exec(f"lsblk -o UUID {part.source} | tail -n 1", get_output=True)
                if uuid:
                    part.source = f"UUID={uuid.strip()}"
            f.write(str(part) + "\n")


def configure_system(conf, root_part, partition_list):
    # fstab
    # exec("genfstab -U /mnt > /mnt/etc/fstab")
    generate_fstab(partition_list, "/mnt")

    # Locale
    locale_conf = conf.locale
    if locale_conf:
        time_zone = locale_conf["timezone"]
    else:
        time_zone = "GMT"
    exec_chroot(f"ln -sf /usr/share/zoneinfo/{time_zone} /etc/localtime")
    exec_chroot("hwclock --systohc")

    # Localization
    # locale = dict(locale_conf["locale"])["default"]
    locale_spec = locale_conf.locale
    locale_default = locale_spec.default
    locale_to_generate = locale_default + "\n"
    if "extra_generate" in locale_spec and locale_spec.extra_generate:
        locale_to_generate += "\n".join(list(locale_spec.extra_generate.values()))
    with open("/mnt/etc/locale.gen", "w") as locale_file:
        locale_file.write(locale_to_generate+"\n")
    exec_chroot("locale-gen")

    locale_name = locale_default.split()[0]
    locale_extra = locale_name + "\n"
    if "extra_settings" in locale_spec and locale_spec.extra_settings:
        for k,v in locale_spec.extra_settings.items():
            locale_extra += f"{k}={v}\n"
    with open("/mnt/etc/locale.conf", "w") as locale_file:
        locale_file.write(f"LANG={locale_extra}\n")

    # Network
    network_conf = conf.network

    # hostname
    hostname = network_conf["hostname"]
    exec(f"echo '{hostname}' > /mnt/etc/hostname")
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
    with open("/mnt/etc/systemd/network/10-eth0.network", "w") as f:
        f.write(eth0_network)

    # hosts
    exec_chroot("echo '127.0.0.1 localhost' > /etc/hosts")
    exec_chroot("echo '::1 localhost' >> /etc/hosts")

    # Replace default os-release
    with open("/mnt/etc/os-release", "w") as f:
        f.write(os_release)

    # Configure schroot
    system_schroot = """[system]
type=directory
description=KodOS
directory=/
groups=users,root
root-groups=root,wheel
# root-users=abuss
profile=kodos
personality=linux
"""
    with open("/mnt/etc/schroot/chroot.d/system.conf", "w") as f:
        f.write(system_schroot)

    venv_schroot = """[virtual_env]
type=directory
description=KodOS
directory=/
union-type=overlay
groups=users,root
root-groups=root,wheel
# root-users=abuss
profile=kodos
personality=linux
aliases=user_env
"""
    with open("/mnt/etc/schroot/chroot.d/virtual_env.conf", "w") as f:
        f.write(venv_schroot)

    # Setting profile
    os.system("mkdir -p /mnt/etc/schroot/kodos")
    os.system("touch /mnt/etc/schroot/kodos/copyfiles")
    os.system("touch /mnt/etc/schroot/kodos/nssdatabases")

    venv_fstab = """# <file system> <mount point>   <type>  <options>       <dump>  <pass>
/proc           /proc           none    rw,bind         0       0
/sys            /sys            none    rw,bind         0       0
/dev            /dev            none    rw,bind         0       0
/dev/pts        /dev/pts        none    rw,bind         0       0
/home           /home           none    rw,bind         0       0
/usr            /usr            none    rw,bind         0       0
/tmp            /tmp            none    rw,bind         0       0
/var/cache	    /var/cache      none	rw,bind		    0   	0
/var/log	    /var/log        none	rw,bind		    0   	0
/var/tmp	    /var/tmp        none	rw,bind		    0   	0
/var/kod	    /var/kod        none	rw,bind		    0   	0
"""
    with open("/mnt/etc/schroot/kodos/fstab", "w") as f:
        f.write(venv_fstab)

    # Dracut config
#     kod_path = abspath(getsourcefile(lambda:0))
#     print(f"=========================\n{kod_path = }\n=========================")
#     exec("mkdir -p /mnt/var/kod/scripts")
#     exec(f"cp {kod_path}/scripts/dracut_install.sh /mnt/var/kod/scripts/")
#     exec("chmod +x /mnt/var/kod/scripts/dracut_install.sh")
#     dracut_install = """[Trigger]
# Type = Path
# Operation = Install
# Operation = Upgrade
# Target = usr/lib/modules/*/pkgbase

# [Action]
# Description = Updating linux initcpios (with dracut!)...
# When = PostTransaction
# Exec = /var/kod/scripts/dracut-install.sh
# Depends = dracut
# NeedsTargets
# """
#     exec("mkdir -p /mnt/etc/pacman.d/hooks")
#     with open("/mnt/etc/pacman.d/hooks/dracut-install.hook", "w") as f:
#         f.write(dracut_install)

#     # Initcpio hooks
#     install_hook = """#!/bin/bash
# build() {
#     add_runscript
# }
# help() {
#     cat <<HELPEOF
# This is a custom initcpio hook for mounting /usr subvolume to /usr.
# HELPEOF
# }
#     """
#     # To be added to /etc/initcpio/install
#     with open("/mnt/etc/initcpio/install/kodos", "w") as f:
#         f.write(install_hook)

#     run_hook = f"""#!/usr/bin/ash
# run_latehook() {{
# 	mountopts="rw,relatime,ssd,space_cache"
#     msg "→ mounting subvolume '/current/usr' at '/usr'"
#     mount -o "$mountopts,subvol=current/usr" {root_part} /new_root/usr
# }}"""
#     # To be added to /etc/initcpio/hooks/
#     with open("/mnt/etc/initcpio/hooks/kodos", "w") as f:
#         f.write(run_hook)

#     # initramfs
#     mkinitcpio_conf = """MODULES=(btrfs)
# BINARIES=()
# FILES=()
# HOOKS=(base kms udev keyboard autodetect keymap consolefont modconf block filesystems fsck btrfs kodos)
# """
#     with open("/mnt/etc/mkinitcpio.conf", "w") as f:
#         f.write(mkinitcpio_conf)

    # exec_chroot("mkinitcpio -A kodos -P")


def get_kernel_version(mount_point):
    kernel_version = exec_chroot("uname -r", mount_point=mount_point, get_output=True).strip()
    return kernel_version


def get_kernel_file(mount_point, package="linux"):
    kernel_file = exec_chroot(f"pacman -Ql {package} | grep vmlinuz", mount_point=mount_point, get_output=True)
    kernel_file = kernel_file.split(" ")[-1].strip()
    return kernel_file


def create_boot_entry(generation, partition_list, boot_options=None, is_current=False, mount_point="/mnt", kver=None):
    subvol=f"generations/{generation}/rootfs"
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
linux /vmlinuz-linux-{kver}
initrd /initramfs-linux-{kver}.img
options root={root_device} rw {options}
    """
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


def setup_bootloader(conf, partition_list):
    # bootloader
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
        # Update /etc/dracut.conf.d/00-kodos.conf
        # with open("/mnt/etc/dracut.conf.d/00-kodos.conf", "w") as f:
        #     f.write("hostonly=\"yes\"\n")
        #     f.write("add_dracutmodules+=\"btrfs\"\n")

        print("==== Setting up systemd-boot ====")
        # kver = get_kernel_version(mount_point="/mnt")
        kernel_file = get_kernel_file(mount_point="/mnt", package=kernel_package)
        kver = kernel_file.split("/")[-2]
        print(f"{kver=}")
        exec_chroot(f"cp {kernel_file} /boot/vmlinuz-linux-{kver}")
        exec_chroot("bootctl install")
        exec_chroot(f"dracut --kver {kver} --fstab --hostonly /boot/initramfs-linux-{kver}.img")
        create_boot_entry(0, partition_list, mount_point="/mnt", kver=kver)

    # Using Grub as bootloader
    if boot_type == "grub":
        pkgs_required = ["grub", "efibootmgr", "grub-btrfs"]
        if "include" in loader_conf:
            pkgs_required += loader_conf["include"].values()

        # exec_chroot(c, "pacman -S --noconfirm grub efibootmgr grub-btrfs")

        exec_chroot(f"pacman -S --noconfirm {' '.join(pkgs_required)}")
        exec_chroot(
            "grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB",
        )
        exec_chroot("grub-mkconfig -o /boot/grub/grub.cfg")
        # pkgs_installed += ["efibootmgr"]


def get_packages_to_install(conf):
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
            set(desktop_packages_to_install
                + hw_packages_to_install
                + service_packages_to_install
                + user_packages_to_install
                + system_packages_to_install
                + font_packages_to_install
            )
        )
    
    packages_to_remove = list(set(desktop_packages_to_remove))

    return packages_to_install, packages_to_remove


def get_list_of_dependencies(pkg):
    pkgs_list = [pkg]
    # check if it is a group
    pkgs_list = exec(f"pacman -Sgq {pkg}",get_output=True).strip().split("\n")
    if len(pkgs_list) > 0:
        pkgs_list += [pkg.strip() for pkg in pkgs_list] + [pkg]
    else:
        # check if it is a (meta-)package
        depend_on = exec(f"pacman -Si {pkg} | grep 'Depends On'", get_output=True).split(":")
        pkgs_list += [pkg.strip() for pkg in depend_on[1].strip().split()]
    return pkgs_list


def update_fstab(root_path, new_mount_point_map):
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


def change_subvol(partition_list, subvol, mount_points):
    for part in partition_list:
        if part.destination in mount_points:
            options = part.options.split(",")
            for opt in options:
                if opt.startswith("subvol="):
                    subvol_path = opt.split("/")[-1]
                    part.options = part.options.replace(opt, f"subvol={subvol}/{subvol_path}")
    return partition_list

def set_ro_mount(mount_point):
    exec(f"mount -o remount,ro,bind {mount_point}")


def change_ro_mount(root_path):
    with open(f"{root_path}/etc/fstab") as f:
        fstab = f.readlines()
    with open(f"{root_path}/etc/fstab", "w") as f:
        for line in fstab:
            if "/usr" in line:
                line = line.replace("rw,", "ro,")
            f.write(line)

def get_max_generation():
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


# def proc_repos(conf):
#     # TODO: Add support for custom repositories and to be used during rebuild
#     repos_conf = conf.repos
#     repos = {}
#     packages = []
#     for repo, repo_desc in repos_conf.items():
#         repos[repo] = {}
#         for action, cmd in repo_desc["commands"].items():
#             repos[repo][action] = cmd

#         if "build" in repo_desc:
#             build_info = repo_desc["build"]
#             url = build_info["url"]
#             build_cmd = build_info["build_cmd"]
#             name = build_info["name"]

#             # TODO: Generalize this code to support other distros
#             exec_chroot("pacman -S --needed --noconfirm git base-devel")
#             exec_chroot(
#                 f"runuser -u kod -- /bin/bash -c 'cd && git clone {url} {name} && cd {name} && {build_cmd}'",
#             )

#         if "package" in repo_desc:
#             exec_chroot(f"pacman -S --needed --noconfirm {repo_desc['package']}")
#             packages += [repo_desc["package"]]

#     exec("mkdir -p /mnt/var/kod")
#     with open("/mnt/var/kod/repos.json", "w") as f:
#         f.write(json.dumps(repos, indent=2))

#     return repos, packages



def proc_repos(conf, current_repos=None, update=False):
    # TODO: Add support for custom repositories and to be used during rebuild
    repos_conf = conf.repos
    repos = {}
    packages = []
    update_repos = False
    for repo, repo_desc in repos_conf.items():
        if current_repos and repo in current_repos and not update:
            repos[repo] = current_repos[repo]
            continue
        repos[repo] = {}
        for action, cmd in repo_desc["commands"].items():
            repos[repo][action] = cmd

        if "build" in repo_desc:
            build_info = repo_desc["build"]
            url = build_info["url"]
            build_cmd = build_info["build_cmd"]
            name = build_info["name"]

            # TODO: Generalize this code to support other distros
            # exec_chroot("pacman -S --needed --noconfirm git base-devel")
            exec_chroot(
                f"runuser -u kod -- /bin/bash -c 'cd && git clone {url} {name} && cd {name} && {build_cmd}'",
            )

        if "package" in repo_desc:
            exec_chroot(f"pacman -S --needed --noconfirm {repo_desc['package']}")
            packages += [repo_desc["package"]]
        update_repos = True

    if update_repos:
        exec("mkdir -p /mnt/var/kod")
        with open("/mnt/var/kod/repos.json", "w") as f:
            f.write(json.dumps(repos, indent=2))

    return repos, packages


def load_repos() -> dict | None:
    repos = None
    with open("/var/kod/repos.json") as f:
        repos = json.load(f)
    return repos


def create_kod_user():
    exec_chroot("useradd -m -r -G wheel -s /bin/bash -d /var/kod/.home kod")
    with open("/mnt/etc/sudoers.d/kod", "w") as f:
        f.write("kod ALL=(ALL) NOPASSWD: ALL")


def manage_packages(root_path, repos, action, list_of_packages, chroot=False):
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

    # if chroot:
    #     exec_prefix = f"arch-chroot {root_path}"
    # else:
    #     exec_prefix = ""

    for repo, pkgs in pkgs_per_repo.items():
        if len(pkgs) == 0:
            continue
        if "run_as_root" in repos[repo] and not repos[repo]["run_as_root"]:
            if chroot:
                exec_chroot(f"runuser -u kod -- {repos[repo][action]} {' '.join(pkgs)}", mount_point=root_path)
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

def proc_desktop(conf):
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
                    pkgs_to_install = list(
                        set(all_pkgs_to_install) - set(exclude_pkg_list)
                    )
                    packages_to_install += pkgs_to_install
                else:
                    packages_to_install += [desktop_mngr]

                if "display_manager" in dm_conf:
                    display_mngr = dm_conf["display_manager"]
                    packages_to_install += [display_mngr]

    return packages_to_install, packages_to_remove


def proc_desktop_services(conf):
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


def proc_hardware(conf):
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


def proc_system_packages(conf):
    print("- processing packages -----------")
    sys_packages = list(conf.packages.values())
    return sys_packages


def get_services_to_enable(conf):
    desktop_services = proc_desktop_services(conf)
    services_to_enable = proc_services_to_enable(conf)

    return desktop_services + services_to_enable


def proc_services(conf):
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


def proc_services_to_enable(conf):
    services_to_enable = []
    print("- processing services -----------")
    services = conf.services
    for name, service in services.items():
        print(name, service.enable)
        service_name = name
        if service.enable:
            if service.service_name:
                print("  using:", service.service_name)
                service_name = service.service_name
            services_to_enable.append(service_name)

    return services_to_enable


def create_user(ctx, user, info):
    # Normal users (no root)
    print(f">>> Creating user {user}")
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
                except:
                    print(f"Group {group} does not exist")
            if "wheel" in extra_groups:
                ctx.execute(
                    "sed -i 's/# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers",
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


def proc_user_dotfile_manager(conf):
    print("- processing user dotfile manager -----------")
    users = conf.users
    dotfile_mngs = {}
    for user_name, info in users.items():
        if info.dotfile_manager:
            print(f"Processing dotfile manager for {user_name}")
            dotfile_mngs[user_name] = info.dotfile_manager

    return dotfile_mngs


def user_dotfile_manager(info):
    print("- processing user dotfile manager -----------")
    dotfile_mngs = None
    if info.dotfile_manager:
        print("Processing dotfile manager")
        dotfile_mngs = info.dotfile_manager

    return dotfile_mngs


def proc_user_programs(conf):
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
                        print("  extra packages:", prog.extra_packages)
                        for _, pkg in desc.extra_packages.items():
                            packages.append(pkg)
                    packages.append(name)

    return packages


def proc_user_configs(conf):
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


def user_configs(user, info):
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

    configs_to_deploy = {"configs": deploy_configs, "run": commands_to_run}

    return configs_to_deploy


def proc_user_services(conf):
    services_to_enable_user = {}
    # services_to_enable = []
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


def user_services(user, info):
    print(f"- processing user services {user} -----------")

    services = []
    if info.services:
        for service, desc in info.services.items():
            if desc.enable:
                print(f"Checking {service} service discription")
                services.append(service)

    return services


def proc_fonts(conf):
    packages_to_install = []
    print("- processing fonts -----------")
    fonts = conf.fonts
    if fonts and "packages" in fonts and fonts.packages:
        packages_to_install += fonts.packages.values()
    return packages_to_install


class Context:
    def __init__(self, user, mount_point="/mnt", use_chroot=True, stage="install"):
        self.user = user
        self.mount_point = mount_point
        self.use_chroot = use_chroot
        self.stage = stage

    def execute(self, command):
        if self.user == os.environ['USER']:
            exec_prefix = ""
            wrap = lambda s: s
        else:
            exec_prefix = f" su {self.user} -c "
            wrap = lambda s: f"'{s}'"
        
        print(f"[Contex] Command: {command}")
        if self.use_chroot:
            exec_chroot(f"{exec_prefix} {wrap(command)}", mount_point=self.mount_point)
        else:
            exec(f"{exec_prefix} {wrap(command)}")
        return True


def configure_user_dotfiles(ctx, user, user_configs, dotfile_mngrs):
    print(f"{dotfile_mngrs=}")
    # print(f"{configs_to_deploy=}")
    print(f"Configuring user {user}")

    old_user = ctx.user
    ctx.user = user # TODO: <-- evaluate if this is still needed
    
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


def configure_user_scripts(ctx, user, user_configs):
    print(f"Configuring user {user}")

    old_user = ctx.user
    ctx.user = user # TODO: <-- evaluate if this is still needed
    # Calling program's config commands
    if user_configs["run"]:
        for prog_config in user_configs["run"]:
            command = prog_config.command
            config = prog_config.config
            stages = list(prog_config.stages.values())
            if ctx.stage in stages:
                command(ctx, config)
    ctx.user = old_user


def enable_services(list_of_services, mount_point="/mnt", use_chroot=False):
    for service in list_of_services:
        print(f"Enabling service: {service}")
        if use_chroot:
            exec_chroot(f"systemctl enable {service}", mount_point=mount_point)
        else:
            exec(f"systemctl enable --now {service}")


def disable_services(list_of_services, mount_point="/mnt", use_chroot=False):
    for service in list_of_services:
        print(f"Disabling service: {service}")
        if use_chroot:
            exec_chroot(f"systemctl disable {service}", mount_point=mount_point)
        else:
            exec(f"systemctl disable --now {service}")


def enable_user_services(ctx, user, services):
    print(f"Enabling service: {services} for {user}")

    for service in services:
        if ctx.stage == "rebuild-user":
            print("Running: ", f"systemctl --user enable --now {service}")
            ctx.execute(f"systemctl --user enable --now {service}")
        print("Done - services enabled")


def load_fstab(root_path=""):
    partition_list = []
    with open(f"{root_path}/etc/fstab") as f:
        entries = f.readlines()
    
    for entry in entries:
        if not entry or entry == "\n" or entry.startswith("#"):
            continue
        (device, mount_point, fs_type, options, dump, pass_) = entry.split()
        partition_list.append(FsEntry(device, mount_point, fs_type, options, dump, pass_))
    return partition_list


def create_filesystem_hierarchy(boot_part, root_part, partition_list):
    print("===================================")
    print("== Creating filesystem hierarchy ==")
    # Initial generation
    generation = 0 
    exec("mkdir -p /mnt/{store,generations,current}")

    subdirs = ["root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for dir in subdirs:
        exec(f"mkdir -p /mnt/store/{dir}")

    # Create home as subvolume if no /home is specified in the config 
    # (TODO: Add support for custom home) 
    exec("sudo btrfs subvolume create /mnt/store/home")

    # First generation
    exec(f"mkdir -p /mnt/generations/{generation}")
    exec(f"btrfs subvolume create /mnt/generations/{generation}/rootfs")
    exec(f"btrfs subvolume create /mnt/generations/{generation}/usr")

    # Mounting first generation
    exec("umount -R /mnt")
    exec(f"mount -o subvol=generations/{generation}/rootfs {root_part} /mnt")
    partition_list = [FsEntry(root_part, "/", "btrfs", f"rw,relatime,ssd,space_cache=v2,subvol=generations/{generation}/rootfs")]

    # exec("mkdir -p /mnt/{home,var,root,boot}")
    for dir in subdirs + ["boot", "home", "usr", "kod"]:
        exec(f"mkdir -p /mnt/{dir}")

    exec(f"mount {boot_part} /mnt/boot")
    boot_options = "rw,relatime,fmask=0022,dmask=0022,codepage=437,iocharset=ascii,shortname=mixed,utf8,errors=remount-ro"
    partition_list.append(FsEntry(boot_part, "/boot", "vfat", boot_options))

    exec(f"mount {root_part} /mnt/kod")
    partition_list.append(FsEntry(root_part, "/kod", "btrfs", "rw,relatime,ssd,space_cache=v2"))

    exec(f"mount -o subvol=generations/{generation}/usr {root_part} /mnt/usr")
    btrfs_options = "rw,relatime,ssd,space_cache=v2"
    partition_list.append(FsEntry(root_part, "/usr", "btrfs", btrfs_options+f",subvol=generations/{generation}/usr"))

    exec(f"mount -o subvol=store/home {root_part} /mnt/home")
    partition_list.append(FsEntry(root_part, "/home", "btrfs", btrfs_options+",subvol=store/home"))

    for dir in subdirs:
        exec(f"mount --bind /mnt/kod/store/{dir} /mnt/{dir}")
        partition_list.append(FsEntry(f"/kod/store/{dir}", f"/{dir}", "none", "rw,bind"))

    # Write generation number
    with open("/mnt/.generation", "w") as f:
        f.write(str(generation))

    print("===================================")
        
    return partition_list


def create_next_generation(boot_part, root_part, generation):
    # Create generation

    next_current = "/kod/current/.next_current"
    # Mounting generation
    if os.path.ismount(next_current):
        print("Reboot is required to update generation")
        os._exit(0)
        exec(f"umount -R {next_current}")
        exec(f"rm -rf {next_current}")

    exec(f"mkdir -p {next_current}")

    exec(f"mount -o subvol=generations/{generation}/rootfs {root_part} {next_current}")
    exec(f"mount -o subvol=generations/{generation}/usr {root_part} {next_current}/usr")
    exec(f"mount {boot_part} {next_current}/boot")
    exec(f"mount {root_part} {next_current}/kod")
    exec(f"mount -o subvol=store/home {root_part} {next_current}/home")
    
    subdirs = ["root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for dir in subdirs:
        exec(f"mount --bind /kod/store/{dir} {next_current}/{dir}")

    partition_list = load_fstab()
    change_subvol(partition_list, subvol=f"generations/{generation}", mount_points=["/", "/usr"])
    generate_fstab(partition_list, next_current)

    # Write generation number
    with open(f"{next_current}/.generation", "w") as f:
        f.write(str(generation))

    print("===================================")

    return next_current


def refresh_package_db(mount_point, new_generation):
    if new_generation:
        exec_chroot("pacman -Syy --noconfirm", mount_point=mount_point)
    else:
        exec("pacman -Syy --noconfirm")


def proc_users(ctx, conf):
    users = conf.users
    # For each user: create user, configure dotfile manager, configure user programs
    for user, info in users.items():    
        create_user(ctx, user, info)

        dotfile_mngrs = user_dotfile_manager(info)
        user_configs_def = user_configs(user, info)

        configure_user_dotfiles(ctx, user, user_configs_def, dotfile_mngrs)
        configure_user_scripts(ctx, user, user_configs_def)

        services_to_enable = user_services(user, info)
        print(f"User services to enable: {services_to_enable}")
        enable_user_services(ctx, user, services_to_enable)


def get_generation(mount_point):
    with open(f"{mount_point}/.generation", "r") as f:
        return int(f.read().strip())


def get_pending_packages(packages_to_install):
    pending_to_install = packages_to_install["packages"]
    return pending_to_install


def store_packages_services(state_path, packages_to_install, system_services):
    packahes_json = json.dumps(packages_to_install, indent=2)
    with open(f"{state_path}/installed_packages", "w") as f:
        f.write(packahes_json)
    with open(f"{state_path}/enabled_services", "w") as f:
        f.write("\n".join(system_services))


def load_packages_services(state_path):
    with open(f"{state_path}/installed_packages", "r") as f:
        packages = json.load(f)
    with open(f"{state_path}/enabled_services", "r") as f:
        services = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    return packages, services


def get_packages_updates(current_packages, next_packages, remove_packages):
    packages_to_install = []
    packages_to_remove = []
    packages_to_update = []
    hooks_to_run = []
    current_kernel = current_packages["kernel"]
    next_kernel = next_packages["kernel"]
    if current_kernel != next_kernel:
        packages_to_install += [next_kernel]
        hooks_to_run += [ "update_kelnel_hook", "update_initramfs_hook" ]
    # # TODO: Check kernel versions
    # if next_kernel.version == current_kernel.version: 
    #     packages_to_update += [next_kernel]
    #     hooks_to_run += [ "update_kelnel_hook", "update_initramfs_hook" ]

    remove_pkg = (set(current_packages["packages"]) - set(next_packages["packages"])) | set(remove_packages)
    packages_to_remove += list(remove_pkg)

    added_pkgs = set(next_packages["packages"]) - set(current_packages["packages"])
    packages_to_install += list(added_pkgs)

    update_pkg = set(current_packages) & set(next_packages)
    packages_to_update += list(update_pkg)

    return packages_to_install, packages_to_remove, packages_to_update, hooks_to_run

##############################################################################
# stages
# stage=="install" -> mount_point="/mnt", use_chroot=True
# stage=="rebuild" -> if new_generation -> mount_point="/.new_rootfs", use_chroot=True
# stage=="rebuild" -> if not new_generation -> mount_point="/", use_chroot=False
# stage=="rebuild-user" -> mount_point="/", use_chroot=False
##############################################################################

@cli.command()
@click.option('-c', '--config', default=None, help='System configuration file')
# @click.option('--step', default=None, help='Step to start installing')
def install(config):
    "Install KodOS in /mnt"
    
    ctx = Context(os.environ['USER'], mount_point="/mnt", use_chroot=True, stage="install")
        
    conf = load_config(config)
    print("-------------------------------")
    # if not step:
    boot_partition, root_partition, partition_list = create_partitions(conf)

    partition_list = create_filesystem_hierarchy(boot_partition, root_partition, partition_list)

    # Install base packages and configure system
    base_packages = get_base_packages(conf)
    install_essentials_pkgs(base_packages)
    configure_system(conf, root_part=root_partition, partition_list=partition_list)
    setup_bootloader(conf, partition_list)
    create_kod_user()

    # === Proc packages
    repos, repo_packages = proc_repos(conf)
    packages_to_install, packages_to_remove = get_packages_to_install(conf)
    # pending_to_install = list(set(packages_to_install["packages"]) - setbase_packages["packages"]))
    pending_to_install = get_pending_packages(packages_to_install)
    print("packages\n", packages_to_install)
    manage_packages("/mnt", repos, "install", pending_to_install, chroot=True)
    # Include installed base packages
    # packages_to_install += base_packages

    # === Proc services
    system_services_to_enable = get_services_to_enable(conf)
    print(f"Services to enable: {system_services_to_enable}")
    enable_services(system_services_to_enable, use_chroot=True)

    # if not step or step == "users":
    # === Proc users
    print("\n====== Creating users ======")
    proc_users(ctx, conf)

    # print("==== Deploying generation ====")
    store_packages_services("/mnt/kod/generations/0", packages_to_install, system_services_to_enable)
    # with open("/mnt/kod/generations/0/installed_packages", "w") as f:
    #     f.write("\n".join(packages_to_install))
    # with open("/mnt/kod/generations/0/enabled_services", "w") as f:
    #     f.write("\n".join(system_services_to_enable))
  
    exec("umount -R /mnt")

    print("Done")
    exec(f"mount {root_partition} /mnt")
    exec("cp -r /root/kodos /mnt/store/root/")
    exec("umount /mnt")
    print(" Done installing KodOS")


@cli.command()
@click.option('-c', '--config', default=None, help='System configuration file')
@click.option('-n', '--new_generation', is_flag=True, help='Create a new generation')
@click.option('-u', '--update', is_flag=True, help='Update package versions')
def rebuild(config, new_generation=False, update=False):
    "Rebuild KodOS installation based on configuration file"

    # stage = "rebuild"
    conf = load_config(config)
    print("========================================")

    current_repos = load_repos()
    repos, repo_packages = proc_repos(conf, current_repos, update)
    print("repo_packages\n", repo_packages)
    if repos is None:
        print("Missing repos information")
        return
    
    # Get next generation number
    max_generation = get_max_generation()
    generation_id = int(max_generation) + 1

    with open("/.generation") as f:
        current_generation = int(f.readline().strip())
    print(f"{current_generation = }")

    # Load current installed packages and enabled services
    if os.path.isfile(f"/kod/generations/{current_generation}/installed_packages"):
        # installed_packages_path = f"/kod/generations/{current_generation}/installed_packages"
        # services_enabled_path = f"/kod/generations/{current_generation}/enabled_services"
        current_state_path = f"/kod/generations/{current_generation}"
    else:
        print("Missing installed packages information")
        return

    current_packages, current_services = load_packages_services(current_state_path)
    # with open(installed_packages_path) as f:
    #     installed_packages = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    print(f"{current_packages = }")

    # with open(services_enabled_path) as f:
    #     services_enabled = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    print(f"{current_services = }")

    boot_partition, root_partition = get_partition_devices(conf)

    next_state_path = f"/kod/generations/{generation_id}"
    exec(f"mkdir -p {next_state_path}")

    if new_generation:
        print("Creating a new generation")
        exec(f"btrfs subvolume snapshot / {next_state_path}/rootfs")
        exec(f"btrfs subvolume snapshot /usr {next_state_path}/usr")
        use_chroot = True
        new_root_path = create_next_generation(boot_partition, root_partition, generation_id)
    else:
        # os._exit(0)
        exec("btrfs subvolume snapshot / /kod/current/old-rootfs")
        exec("btrfs subvolume snapshot /usr /kod/current/old-usr")
        exec(f"cp /kod/generations/{current_generation}/installed_packages /kod/current/installed_packages")
        exec(f"cp /kod/generations/{current_generation}/enabled_services /kod/current/enabled_services")
        # gen_mount_point = f"/kod/generations/{current_generation}"
        use_chroot = False
        new_root_path = "/"
        exec("mount -o remount,rw /usr")

    # ctx = Context(os.environ['USER'], mount_point=mount_point, use_chroot=use_chroot)

    print("==========================================")
    print("==== Processing packages and services ====")

   # === Proc packages
    packages_to_install, packages_to_remove = get_packages_to_install(conf)
    print("packages\n", packages_to_install)

    # Package filtering
    new_packages_to_install, packages_to_remove, packages_to_update, hooks_to_run = get_packages_updates(current_packages, packages_to_install, packages_to_remove)

    # remove_pkg = (set(installed_packages) - set(packages_to_install)) | set(packages_to_remove)
    # added_pkgs = set(packages_to_install) - set(installed_packages)
    # update_pkg = set(installed_packages) & set(packages_to_install)

    # === Proc services
    next_services = get_services_to_enable(conf)

    # Services filtering
    services_to_disable = list(set(current_services) - set(next_services))
    new_service_to_enable = list(set(next_services) - set(current_services))

    if not new_generation and services_to_disable:
        disable_services(services_to_disable, new_root_path, use_chroot=use_chroot)

    # ======

    # try:
    if packages_to_remove:
        print("Packages to remove:", packages_to_remove)
        for pkg in packages_to_remove:
            try:
                manage_packages(new_root_path, repos, "remove", [pkg], chroot=use_chroot)
            except:
                pass
                # print(f"Unable to remove {pkg}")

    if update and packages_to_update:
        print("Packages to update:", packages_to_update)
        refresh_package_db(new_root_path, new_generation)
        manage_packages(new_root_path, repos, "update", packages_to_update, chroot=use_chroot)

    if new_packages_to_install:
        print("Packages to install:", new_packages_to_install)
        manage_packages(new_root_path, repos, "install", new_packages_to_install, chroot=use_chroot)

    print("Running hooks")
    for hook in hooks_to_run:
        print(f"Running {hook}")

    # System services
    print(f"Services to enable: {new_service_to_enable}")
    # enable_services(c, system_services_to_enable, mount_point, use_chroot=use_chroot)
    enable_services(new_service_to_enable, new_root_path, use_chroot=use_chroot)

    # # === Proc users
    # print("\n====== Processing users ======")
    # # TODO: Check if repo is already cloned
    # user_dotfile_mngrs = proc_user_dotfile_manager(conf)
    # user_configs = proc_user_configs(conf)
    # configure_users(c, user_dotfile_mngrs, user_configs)

    # user_services_to_enable = proc_user_services(conf)
    # print(f"User services to enable: {user_services_to_enable}")
    # enable_user_services(c, user_services_to_enable, use_chroot=True)

    # Storing list of installed packages and enabled services
    # Create a list of installed packages
    store_packages_services(next_state_path, packages_to_install, new_service_to_enable)
    # with open(f"{next_state_path}/installed_packages", "w") as f:
    #     f.write("\n".join(packages_to_install))
    # # Create a list of services enabled
    # with open(f"{next_state_path}/enabled_services", "w") as f:
    #     f.write("\n".join(system_services_to_enable))

    partition_list = load_fstab("/")

    print("==== Deploying new generation ====")
    if new_generation:
        create_boot_entry(generation_id, partition_list, mount_point=new_root_path)
    else:
        # Move current updated rootfs to a new generation
        exec(f"mv /kod/generations/{current_generation}/rootfs /kod/generations/{generation_id}/")
        exec(f"mv /kod/generations/{current_generation}/usr /kod/generations/{generation_id}/")
        # Moving the current rootfs copy to the current generation path
        exec(f"mv /kod/current/old-rootfs /kod/generations/{current_generation}/rootfs")
        exec(f"mv /kod/current/old-usr /kod/generations/{current_generation}/usr")
        exec(f"mv /kod/current/installed_packages /kod/generations/{current_generation}/installed_packages")
        exec(f"mv /kod/current/enabled_services /kod/generations/{current_generation}/enabled_services")
        updated_partition_list = change_subvol(partition_list, subvol=f"generations/{generation_id}", mount_points=["/", "/usr"])
        generate_fstab(updated_partition_list, new_root_path)
        create_boot_entry(generation_id, updated_partition_list, mount_point=new_root_path)

    # Write generation number
    with open(f"{next_state_path}/rootfs/.generation", "w") as f:
        f.write(str(generation_id))

    if new_generation:
        for m in ["/boot", "/usr", "/kod", "/home", "/root", "/var/log", "/var/tmp", "/var/cache", "/var/kod"]:
            exec(f"umount {new_root_path}{m}")
        exec(f"umount {new_root_path}")
        # exec(f"mount | grep {new_root_path}")
        exec(f"rm -rf {new_root_path}")

    else:
        exec("mount -o remount,ro /usr")

    print("Done")


@cli.command()
@click.option('-c', '--config', default=None, help='System configuration file')
@click.option('--user', default=os.environ['USER'], help='User to rebuild config')
def rebuild_user(config, user=os.environ['USER']):
    "Rebuild KodOS installation based on configuration file"
    # stage = "rebuild-user"
    ctx = Context(os.environ['USER'], mount_point="/", use_chroot=False, stage="rebuild-user")   
    conf = load_config(config)
    users = conf.users
    info = users[user] if user in users else None   
    print("========================================")

    # === Proc users
    if info:
        print("\n====== Processing users ======")

        dotfile_mngrs = user_dotfile_manager(info)
        user_configs_def = user_configs(user, info)

        configure_user_dotfiles(ctx, user, user_configs_def, dotfile_mngrs)
        configure_user_scripts(ctx, user, user_configs_def)

        services_to_enable = user_services(user, info)
        print(f"User services to enable: {services_to_enable}")
        enable_user_services(ctx, user, services_to_enable)
    else:
        print(f"User {user} not found in configuration file")

    print("Done")


# # TODO: Update rollback
# # @task(help={"generation": "Generation number to rollback to"})
# @cli.command()
# @click.option('-c', '--config', default=None, help='System configuration file')
# @click.option('-g','--generation', default=None, help='Generation number to rollback to')
# def rollback(config, generation=None):
#     "Rollback current generation to use the specified generation"

#     if generation is None:
#         print("Please specify a generation number")
#         return
    
#     conf = load_config(config)

#     print("Updating current generation")
#     rollback_path = f"/kod/generations/{generation}"
#     boot_partition, root_partition = get_partition_devices(conf)
#     copy_generation(boot_partition, root_partition, rollback_path, "/kod/current", new_generation=True)
    
#     update_boot(boot_partition, root_partition, "/current")

#     # print("Recreating grub.cfg")
#     # exec("grub-mkconfig -o /boot/grub/grub.cfg")
#     print("Done")

##############################################################################

if __name__ == "__main__":
    cli()
