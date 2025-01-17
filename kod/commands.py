import glob
import json
import os
from pathlib import Path
import re

# import signal
from invoke import task
import lupa as lua

from kod.filesytem import create_partitions, get_partition_devices


#####################################################################################################


def exec_chroot(c, cmd):
    print(cmd)
    chroot_cmd = "arch-chroot /mnt "
    chroot_cmd += cmd
    c.run(chroot_cmd)


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


def install_essentials_pkgs(c):
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

    base_pkgs = [
        "base",
        "base-devel",
        microcode,
        "btrfs-progs",
        "linux",
        "linux-firmware",
        "bash-completion",
        "mlocate",
        "sudo",
        "schroot",
        "whois",
    ]
    # TODO: remove this package dependency
    base_pkgs += ["arch-install-scripts"]

    c.run(f"pacstrap -K /mnt {' '.join(base_pkgs)}")


def configure_system(c, conf, root_part):
    # fstab
    c.run("genfstab -U /mnt > /mnt/etc/fstab")

    # Locale
    locale_conf = conf.locale
    if locale_conf:
        time_zone = locale_conf["timezone"]
    else:
        time_zone = "GMT"
    exec_chroot(c, f"ln -sf /usr/share/zoneinfo/{time_zone} /etc/localtime")
    exec_chroot(c, "hwclock --systohc")

    # Localization
    # locale = dict(locale_conf["locale"])["default"]
    locale_spec = locale_conf.locale
    locale_default = locale_spec.default
    locale_to_generate = locale_default + "\n"
    if "extra_generate" in locale_spec and locale_spec.extra_generate:
        locale_to_generate += "\n".join(list(locale_spec.extra_generate.values()))
    with open("/mnt/etc/locale.gen", "w") as locale_file:
        locale_file.write(locale_to_generate+"\n")
    exec_chroot(c, "locale-gen")

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
    c.run(f"echo '{hostname}' > /mnt/etc/hostname")
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
    exec_chroot(c, "echo '127.0.0.1 localhost' > /etc/hosts")
    exec_chroot(c, "echo '::1 localhost' >> /etc/hosts")

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
root-users=abuss
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
root-users=abuss
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


    # Initcpio hooks
    install_hook = """#!/bin/bash
build() {
    add_runscript
}
help() {
    cat <<HELPEOF
This is a custom initcpio hook for mounting /usr subvolume to /usr.
HELPEOF
}
    """
    # To be added to /etc/initcpio/install
    with open("/mnt/etc/initcpio/install/kodos", "w") as f:
        f.write(install_hook)

    run_hook = f"""#!/usr/bin/ash
run_latehook() {{
	mountopts="rw,relatime,ssd,space_cache"
    msg "→ mounting subvolume '/current/usr' at '/usr'"
    mount -o "$mountopts,subvol=current/usr" {root_part} /new_root/usr
}}"""
    # To be added to /etc/initcpio/hooks/
    with open("/mnt/etc/initcpio/hooks/kodos", "w") as f:
        f.write(run_hook)

    # initramfs
    mkinitcpio_conf = """MODULES=(btrfs)
BINARIES=()
FILES=()
HOOKS=(base kms udev keyboard autodetect keymap consolefont modconf block filesystems fsck btrfs kodos)
"""
    with open("/mnt/etc/mkinitcpio.conf", "w") as f:
        f.write(mkinitcpio_conf)

    exec_chroot(c, "mkinitcpio -A kodos -P")


def setup_bootloader(c, conf):
    # bootloader
    boot_conf = conf.boot
    loader_conf = boot_conf["loader"]
    boot_type = loader_conf["type"] if "type" in loader_conf else "grub"

    # Using systemd-boot as bootloader
    if boot_type == "systemd-boot":
        exec_chroot(c, "bootctl install")

        res = c.run("cat /mnt/etc/fstab | grep '[ \t]/[ \t]'")
        mount_point = res.stdout.split()
        root_part = mount_point[0].strip()
        part_type = mount_point[2].strip()
        mount_options = mount_point[3].strip().split(",")
        print(root_part, part_type, mount_options)
        option = ""
        if part_type == "btrfs":
            for opt in mount_options:
                if opt.startswith("subvol"):
                    option = "rootflags=" + opt

        loader_conf_systemd = """
default arch
timeout 3
console-mode max
#editor no"""
        with open("/mnt/boot/loader/loader.conf", "w") as f:
            f.write(loader_conf_systemd)

        kodos_conf = f"""
title KodOS Linux
linux /vmlinuz-linux
initrd /initramfs-linux.img
options root={root_part} rw {option}
    """
        with open("/mnt/boot/loader/entries/kodos.conf", "w") as f:
            f.write(kodos_conf)

        kodos_fb_conf = f"""
title KodOS Linux - fallback
linux /vmlinuz-linux
initrd /initramfs-linux-fallback.img
options root={root_part} rw {option}
    """
        with open("/mnt/boot/loader/entries/kodos-fallback.conf", "w") as f:
            f.write(kodos_fb_conf)

    # Using Grub as bootloader
    if boot_type == "grub":
        pkgs_required = ["grub", "efibootmgr", "grub-btrfs"]
        if "include" in loader_conf:
            pkgs_required += loader_conf["include"].values()

        # exec_chroot(c, "pacman -S --noconfirm grub efibootmgr grub-btrfs")

        exec_chroot(c, f"pacman -S --noconfirm {' '.join(pkgs_required)}")
        exec_chroot(
            c,
            "grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB",
        )
        exec_chroot(c, "grub-mkconfig -o /boot/grub/grub.cfg")
        # pkgs_installed += ["efibootmgr"]


def get_packages_to_install(c, conf):
    packages_to_install = []
    packages_to_remove = []

    # Desktop
    desktop_packages_to_install, desktop_packages_to_remove = proc_desktop(c, conf)

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

    packages_to_install = list(
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


def get_list_of_dependencies(c, pkg):
    pkgs_list = [pkg]
    # check if it is a group
    pkgs_list = c.run(f"pacman -Sgq {pkg}").stdout.split()
    if len(pkgs_list) > 0:
        pkgs_list += [pkg.strip() for pkg in pkgs_list]
    else:
        # check if it is a (meta-)package
        depend_on = c.run(f"pacman -Si {pkg} | grep 'Depends On'").stdout.split()
        pkgs_list += [pkg.strip() for pkg in depend_on[1].strip().split(" ")]
    return pkgs_list


def update_fstab(c, root_path, new_mount_point_map):
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


def set_ro_mount(c, mount_point):
    c.run(f"mount -o remount,ro,bind {mount_point}")


def change_ro_mount(c, root_path):
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


def proc_repos(c, conf):
    # TODO: Add support for custom repositories and to be used during rebuild
    repos_conf = conf.repos
    repos = {}
    packages = []
    for repo, repo_desc in repos_conf.items():
        repos[repo] = {}
        for action, cmd in repo_desc["commands"].items():
            repos[repo][action] = cmd

        if "build" in repo_desc:
            build_info = repo_desc["build"]
            url = build_info["url"]
            build_cmd = build_info["build_cmd"]
            name = build_info["name"]

            # TODO: Generalize this code to support other distros
            exec_chroot(c, "pacman -S --needed --noconfirm git base-devel")
            exec_chroot(
                c,
                f"runuser -u kod -- /bin/bash -c 'cd && git clone {url} {name} && cd {name} && {build_cmd}'",
            )

        if "package" in repo_desc:
            exec_chroot(c, f"pacman -S --needed --noconfirm {repo_desc['package']}")
            packages += [repo_desc["package"]]

    with open("/mnt/var/kod/repos.json", "w") as f:
        f.write(json.dumps(repos, indent=2))

    return repos, packages


def load_repos() -> dict | None:
    repos = None
    with open("/var/kod/repos.json") as f:
        repos = json.load(f)
    return repos


def create_kod_user(c):
    exec_chroot(c, "useradd -m -r -G wheel -s /bin/bash -d /var/kod/.home kod")
    with open("/mnt/etc/sudoers.d/kod", "w") as f:
        f.write("kod ALL=(ALL) NOPASSWD: ALL")


def manage_packages(c, root_path, repos, action, list_of_packages, chroot=False):
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

    if chroot:
        exec_prefix = f"arch-chroot {root_path}"
    else:
        exec_prefix = ""
    for repo, pkgs in pkgs_per_repo.items():
        if len(pkgs) == 0:
            continue
        if "run_as_root" in repos[repo] and not repos[repo]["run_as_root"]:
            c.run(
                f"{exec_prefix} runuser -u kod -- {repos[repo][action]} {' '.join(pkgs)}"
            )
        else:
            c.run(f"{exec_prefix} {repos[repo][action]} {' '.join(pkgs)}")
        packages_installed += pkgs
    return packages_installed


# --------------------------------------

def proc_desktop(c, conf):
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
                    all_pkgs_to_install = get_list_of_dependencies(c, desktop_mngr)
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
        ctx.execute(f"useradd -m -G wheel {user} -c '{user_name}'")
        ctx.execute(
            "sed -i 's/# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers",
        )
        # TODO: Add extra groups

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
    def __init__(self, c, user, mount_point="/mnt", use_chroot=True, stage="install"):
        self.c = c
        self.user = user
        self.mount_point = mount_point
        self.use_chroot = use_chroot
        self.stage = stage

    def execute(self, command):
        # if self.stage == "install":
        #     mountpoint = self.mount_point
        #     exec_prefix = f"arch-chroot {mountpoint}"
        #     exec_prefix += f" su {self.user} -c "
        #     wrap = lambda s: f"'{s}'"
        # else:
        #     mountpoint = ""
        #     exec_prefix = ""
        #     wrap = lambda s: s
        
        if self.use_chroot:
            mountpoint = self.mount_point
            exec_prefix = f"arch-chroot {mountpoint}"
        else:
            mountpoint = ""
            exec_prefix = ""

        if self.user == os.environ['USER']:
            wrap = lambda s: s
        else:
            exec_prefix += f" su {self.user} -c "
            wrap = lambda s: f"'{s}'"
        
        print(f"[Contex] Command: {command}")
        self.c.run(f"{exec_prefix} {wrap(command)}")
        return True


def configure_user_dotfiles(ctx, user, user_configs, dotfile_mngrs):
    print(f"{dotfile_mngrs=}")
    # print(f"{configs_to_deploy=}")
    print(f"Configuring user {user}")

    old_user = ctx.user
    ctx.user = user # TODO: <-- evaluate if this is still needed
    
    # Calling dotfile_mngrs
    if user_configs["configs"]:
        # print("\nUSER:",os.environ['USER'],'\n')
        call_init = True
        for config in user_configs["configs"]:
            command = dotfile_mngrs.command
            prg_config = dotfile_mngrs.config
            command(ctx, prg_config, config, call_init)
            call_init = False
    ctx.user = old_user


def configure_user_scripts(ctx, user, user_configs):
    # print(f"{dotfile_mngrs=}")
    # print(f"{configs_to_deploy=}")
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

def enable_services(c, list_of_services, mount_point="/mnt", use_chroot=False):
    for service in list_of_services:
        print(f"Enabling service: {service}")
        if use_chroot:
            exec_prefix = f"arch-chroot {mount_point}"
            c.run(f"{exec_prefix} systemctl enable {service}")
        else:
            c.run(f"systemctl enable --now {service}")


def disable_services(c, list_of_services, mount_point="/mnt", use_chroot=False):
    for service in list_of_services:
        print(f"Disabling service: {service}")
        if use_chroot:
            exec_prefix = f"arch-chroot {mount_point}"
            c.run(f"{exec_prefix} systemctl disable {service}")
        else:
            c.run(f"systemctl disable --now {service}")


def enable_user_services(ctx, user, services):
    print(f"Enabling service: {services} for {user}")

    for service in services:
        if ctx.stage == "rebuild-user":
            print("Running: ", f"systemctl --user enable --now {service}")
            ctx.execute(f"systemctl --user enable --now {service}")
        print("Done - services enabled")


# def create_filesystem_hierarchy(c, boot_part, root_part, generation=0):
#     print("===================================")
#     print("== Creating filesystem hierarchy ==")
#     c.run("mkdir -p /mnt/{store,generations,current}")
#     c.run("mkdir -p /mnt/store/var")
#     subvolumes = ["home", "root", "var/log", "var/tmp", "var/cache", "var/kod"]
#     for subv in subvolumes:
#         c.run(f"sudo btrfs subvolume create /mnt/store/{subv}")

#     # First generation
#     c.run(f"mkdir -p /mnt/generations/{generation}")
#     c.run(f"btrfs subvolume create /mnt/generations/{generation}/rootfs")
#     c.run(f"btrfs subvolume create /mnt/generations/{generation}/usr")

#     # Mounting first generation
#     c.run("umount -R /mnt")
#     c.run(f"mount -o subvol=generations/{generation}/rootfs {root_part} /mnt")

#     # c.run("mkdir -p /mnt/{home,var,root,boot}")
#     for subv in subvolumes + ["boot", "usr"]:
#         c.run(f"mkdir -p /mnt/{subv}")

#     c.run(f"mount {boot_part} /mnt/boot")
#     c.run(f"mount -o subvol=generations/{generation}/usr {root_part} /mnt/usr")

#     for subv in subvolumes:
#         c.run(f"mount -o subvol=store/{subv} {root_part} /mnt/{subv}")

#     # Write generation number
#     with open("/mnt/.generation", "w") as f:
#         f.write(str(generation))

#     print("===================================")


# def create_filesystem_hierarchy(c, boot_part, root_part, generation=0):
#     print("===================================")
#     print("== Creating filesystem hierarchy ==")
#     c.run("mkdir -p /mnt/{store,generations,current}")
#     subdirs = ["root", "var/log", "var/tmp", "var/cache", "var/kod"]
#     for dir in subdirs:
#         c.run(f"mkdir -p /mnt/store/{dir}")

#     # Create home as subvolume if no /home is specified in the config 
#     # (TODO: Add support for custom home) 
#     c.run("sudo btrfs subvolume create /mnt/store/home")

#     # First generation
#     c.run(f"mkdir -p /mnt/generations/{generation}")
#     c.run(f"btrfs subvolume create /mnt/generations/{generation}/rootfs")
#     c.run(f"btrfs subvolume create /mnt/generations/{generation}/usr")

#     # Mounting first generation
#     c.run("umount -R /mnt")
#     c.run(f"mount -o subvol=generations/{generation}/rootfs {root_part} /mnt")

#     # c.run("mkdir -p /mnt/{home,var,root,boot}")
#     for dir in ["boot", "home", "usr", "var", "kod"]:
#         c.run(f"mkdir -p /mnt/{dir}")

#     # for subv in subvolumes + ["boot", "usr"]:
#         # c.run(f"mkdir -p /mnt/{subv}")

#     c.run(f"mount {boot_part} /mnt/boot")
#     c.run(f"mount -o subvol=generations/{generation}/usr {root_part} /mnt/usr")
#     c.run(f"mount {root_part} /mnt/kod")
    

#     # Mounting home (depends on the config)
#     c.run(f"mount -o subvol=store/home {root_part} /mnt/home")

#     for dir in subdirs:
#         c.run(f"ln -s /kod/store/{dir} /mnt/{dir}")

#     # Write generation number
#     with open("/mnt/.generation", "w") as f:
#         f.write(str(generation))

#     print("===================================")


def create_filesystem_hierarchy(c, boot_part, root_part, generation=0):
    print("===================================")
    print("== Creating filesystem hierarchy ==")
    c.run("mkdir -p /mnt/{store,generations,current}")

    # c.run("mkdir -p /mnt/store/var")
    # subvolumes = ["home", "root", "var/log", "var/tmp", "var/cache", "var/kod"]
    # for subv in subvolumes:
    #     c.run(f"sudo btrfs subvolume create /mnt/store/{subv}")

    subdirs = ["root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for dir in subdirs:
        c.run(f"mkdir -p /mnt/store/{dir}")

    # Create home as subvolume if no /home is specified in the config 
    # (TODO: Add support for custom home) 
    c.run("sudo btrfs subvolume create /mnt/store/home")

    # First generation
    c.run(f"mkdir -p /mnt/generations/{generation}")
    c.run(f"btrfs subvolume create /mnt/generations/{generation}/rootfs")
    c.run(f"btrfs subvolume create /mnt/generations/{generation}/usr")

    # Mounting first generation
    c.run("umount -R /mnt")
    c.run(f"mount -o subvol=generations/{generation}/rootfs {root_part} /mnt")

    # c.run("mkdir -p /mnt/{home,var,root,boot}")
    for dir in subdirs + ["boot", "usr", "kod"]:
        c.run(f"mkdir -p /mnt/{dir}")

    c.run(f"mount {boot_part} /mnt/boot")
    c.run(f"mount {root_part} /mnt/kod")
    c.run(f"mount -o subvol=generations/{generation}/usr {root_part} /mnt/usr")
    c.run(f"mount -o subvol=store/home {root_part} /mnt/home")

    for dir in subdirs:
        c.run(f"mount --bind /mnt/kod/store/{dir} /mnt/{dir}")
        # c.run(f"mount -o subvol=store/{subv} {root_part} /mnt/{subv}")

    # Write generation number
    with open("/mnt/.generation", "w") as f:
        f.write(str(generation))

    print("===================================")


def deploy_generation(
    c, boot_part, root_part, generation, pkgs_installed, service_to_enable
):
    print("===================================")
    print("== Deploying generation ==")
    c.run("mkdir /new_rootfs")
    c.run(f"mount {root_part} /new_rootfs")
    c.run("btrfs subvolume snapshot /mnt /new_rootfs/current/rootfs")
    c.run("btrfs subvolume snapshot /mnt/usr /new_rootfs/current/usr")

    c.run("umount -R /mnt")
    c.run(f"mount -o subvol=current/rootfs {root_part} /mnt")
    c.run(f"mount -o subvol=current/usr {root_part} /mnt/usr")

    c.run("mkdir -p /mnt/kod")
    c.run(f"mount {root_part} /mnt/kod")

    # Create a list of installed packages
    with open(f"/mnt/kod/generations/{generation}/installed_packages", "w") as f:
        f.write("\n".join(pkgs_installed))

    # Create a list of services enabled
    with open(f"/mnt/kod/generations/{generation}/enabled_services", "w") as f:
        f.write("\n".join(service_to_enable))

    c.run(f"mount {boot_part} /mnt/boot")
    c.run(f"mount -o subvol=store/home {root_part} /mnt/home")

    subdirs = ["root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for dir in subdirs:
        c.run(f"mount --bind /mnt/kod/store/{dir} /mnt/{dir}")

    # subvolumes = ["home", "root", "var/log", "var/tmp", "var/cache", "var/kod"]
    # for subv in subvolumes:
    #     c.run(f"mount -o subvol=store/{subv} {root_part} /mnt/{subv}")

    c.run("genfstab -U /mnt > /mnt/etc/fstab")
    # Update to use read only for rootfs
    change_ro_mount(c, "/mnt")

    exec_chroot(c, "mkinitcpio -A kodos -P")
    exec_chroot(c, "grub-mkconfig -o /boot/grub/grub.cfg")
    c.run("umount -R /mnt")
    c.run("umount -R /new_rootfs")
    c.run("rm -rf /new_rootfs")

    print("===================================")


# def deploy_generation(
#     c, boot_part, root_part, generation, pkgs_installed, service_to_enable
# ):
#     print("===================================")
#     print("== Deploying generation ==")
#     c.run("mkdir /new_rootfs")
#     c.run(f"mount {root_part} /new_rootfs")
#     c.run("btrfs subvolume snapshot /mnt /new_rootfs/current/rootfs")
#     c.run("btrfs subvolume snapshot /mnt/usr /new_rootfs/current/usr")

#     c.run("umount -R /mnt")
#     c.run(f"mount -o subvol=current/rootfs {root_part} /mnt")
#     c.run(f"mount -o subvol=current/usr {root_part} /mnt/usr")

#     c.run("mkdir -p /mnt/kod")
#     c.run(f"mount {root_part} /mnt/kod")

#     # Create a list of installed packages
#     with open(f"/mnt/kod/generations/{generation}/installed_packages", "w") as f:
#         f.write("\n".join(pkgs_installed))

#     # Create a list of services enabled
#     with open(f"/mnt/kod/generations/{generation}/enabled_services", "w") as f:
#         f.write("\n".join(service_to_enable))

#     c.run(f"mount {boot_part} /mnt/boot")
#     subvolumes = ["home", "root", "var/log", "var/tmp", "var/cache", "var/kod"]
#     for subv in subvolumes:
#         c.run(f"mount -o subvol=store/{subv} {root_part} /mnt/{subv}")

#     c.run("genfstab -U /mnt > /mnt/etc/fstab")
#     # Update to use read only for rootfs
#     change_ro_mount(c, "/mnt")

#     exec_chroot(c, "mkinitcpio -A kodos -P")
#     exec_chroot(c, "grub-mkconfig -o /boot/grub/grub.cfg")
#     c.run("umount -R /mnt")
#     c.run("umount -R /new_rootfs")
#     c.run("rm -rf /new_rootfs")

#     print("===================================")


# Used for rebuild
def deploy_new_generation(c, boot_part, current_root_part, new_root_path): # , mount_point, generation):
    print("===================================")
    print("== Deploying generation ==")
    print(f"{new_root_path=}")

    # Makes generation usable 
    c.run(f"genfstab -U {new_root_path} > {new_root_path}/etc/fstab")

    c.run(f"arch-chroot {new_root_path} mkinitcpio -A kodos -P")

    #------------- Done with generation creation -------------
    
    # Rename rootfs to old_rootfs
    if os.path.isdir("/kod/current/old_rootfs"):
        c.run("rm -rf /kod/current/old_rootfs")
        c.run("rm -rf /kod/current/old_usr")
    c.run("mv /kod/current/rootfs /kod/current/old_rootfs")
    c.run("mv /kod/current/usr /kod/current/old_usr")

    # Create new rootfs and usr
    c.run(f"btrfs subvolume snapshot {new_root_path} /kod/current/rootfs")
    c.run(f"btrfs subvolume snapshot {new_root_path}/usr /kod/current/usr")
    
    c.run(f"umount -R {new_root_path}")

    new_rootfs = "/.new_rootfs"
    c.run(f"mkdir -p {new_rootfs}")

    c.run(f"mount -o subvol=current/rootfs {current_root_part} {new_rootfs}")
    c.run(f"mount -o subvol=current/usr {current_root_part} {new_rootfs}/usr")

    c.run(f"mount {current_root_part} {new_rootfs}/kod")
    c.run(f"mount {boot_part} {new_rootfs}/boot")
    
    subvolumes = ["home", "root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for subv in subvolumes:
        c.run(f"mount -o subvol=store/{subv} {current_root_part} {new_rootfs}/{subv}")
    
    c.run(f"genfstab -U {new_rootfs} > {new_rootfs}/etc/fstab")

    change_ro_mount(c, new_rootfs)
    # set_ro_mount(c, f"{new_rootfs}/usr")

    c.run(f"arch-chroot {new_rootfs} mkinitcpio -A kodos -P")
    c.run(f"arch-chroot {new_rootfs} grub-mkconfig -o /boot/grub/grub.cfg")

    c.run(f"umount -R {new_rootfs}")
    c.run(f"rm -rf {new_rootfs}")

    print("===================================")


# Used for rebuild
def create_next_generation(c, boot_part, root_part, generation, mount_point):
    # Create generation
    c.run(f"mkdir -p {mount_point}")

    c.run(f"btrfs subvolume snapshot / {mount_point}/rootfs")
    c.run(f"btrfs subvolume snapshot /usr {mount_point}/usr")

    next_current = "/kod/current/next_current"
    # Mounting generation
    if os.path.ismount(next_current):
        c.run(f"umount -R {next_current}")
        c.run(f"rm -rf {next_current}")

    c.run(f"mkdir -p {next_current}")

    c.run(f"mount -o subvol=generations/{generation}/rootfs {root_part} {next_current}")
    c.run(f"mount -o subvol=generations/{generation}/usr {root_part} {next_current}/usr")
    c.run(f"mount {boot_part} {next_current}/boot")
    subvolumes = ["home", "root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for subv in subvolumes:
        c.run(f"mount -o subvol=store/{subv} {root_part} {next_current}/{subv}")
    c.run(f"mkdir -p {next_current}/kod")

    # Write generation number
    with open(f"{next_current}/.generation", "w") as f:
        f.write(str(generation))

    print("===================================")

    return next_current


def refresh_package_db(c, mount_point="/mnt", use_chroot=True):
    if use_chroot:
        exec_prefix = f"arch-chroot {mount_point}"
    else:
        exec_prefix = ""
    c.run(f"{exec_prefix} pacman -Syy")


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


##############################################################################
# stages
# stage=="install" -> mount_point="/mnt", use_chroot=True
# stage=="rebuild" -> if new_generation -> mount_point="/.new_rootfs", use_chroot=True
# stage=="rebuild" -> if not new_generation -> mount_point="/", use_chroot=False
# stage=="rebuild-user" -> mount_point="/", use_chroot=False
##############################################################################

@task(help={"config": "system configuration file", "step": "Starting step"})
def install(c, config, step=None):
    "Install KodOS in /mnt"
    stage = "install"
    ctx = Context(c, os.environ['USER'], mount_point="/mnt", use_chroot=True, stage=stage)
        
    conf = load_config(config)
    print("-------------------------------")
    if not step:
        boot_partition, root_partition = create_partitions(c, conf)

        create_filesystem_hierarchy(c, boot_partition, root_partition, generation=0)

        install_essentials_pkgs(c)
        configure_system(c, conf, root_part=root_partition)
        setup_bootloader(c, conf)
        create_kod_user(c)

        # === Proc packages
        repos, repo_packages = proc_repos(c, conf)
        packages_to_install, packages_to_remove = get_packages_to_install(c, conf)
        print("packages\n", packages_to_install)
        packages_installed = manage_packages(
            c, "/mnt", repos, "install", packages_to_install, chroot=True
        )

        # === Proc services
        system_services_to_enable = get_services_to_enable(conf)
        print(f"Services to enable: {system_services_to_enable}")
        enable_services(c, system_services_to_enable, use_chroot=True)

    if not step or step == "users":
        # === Proc users
        print("\n====== Creating users ======")
        proc_users(ctx, conf)

    print("==== Deploying generation ====")
    deploy_generation(
        c,
        boot_partition,
        root_partition,
        0,
        packages_installed,
        system_services_to_enable,
    )

    print("Done")
    c.run(f"mount -o subvol=store/root {root_partition} /mnt")
    c.run("cp -r /root/kodos /mnt/")
    print(" Done installing KodOS")


@task(help={"config": "system configuration file"})
def rebuild(c, config, new_generation=False, update=False):
    "Rebuild KodOS installation based on configuration file"
    stage = "rebuild"
    conf = load_config(config)
    print("========================================")

    max_generation = get_max_generation()
    with open("/.generation") as f:
        current_generation = f.readline().strip()
    print(f"{current_generation = }")
    
    boot_partition, root_partition = get_partition_devices(conf)

    if new_generation:
        print("Creating a new generation")
        use_chroot = True
        generation_id = int(max_generation) + 1
        # mount_point="/.new_rootfs"
        mount_point = f"/kod/generations/{generation_id}"
        new_root_path = create_next_generation(
            c,
            boot_partition,
            root_partition,
            generation_id,
            mount_point,
        )
    else:
        use_chroot = False
        generation_id = int(current_generation)
        mount_point="/"
        new_root_path = "/"
        c.run("mount -o remount,rw /usr")

    ctx = Context(c, os.environ['USER'], mount_point=mount_point, use_chroot=use_chroot, stage=stage)

    print("========================================")
    repos = load_repos()
    if repos is None:
        print("Missing repos information")
        return

    # Load current installed packages and enabled services
    if os.path.isdir("/kod/current/installed_packages"):
        installed_packages_path = "/kod/current/installed_packages"
        services_enabled_path = "/kod/current/enabled_services"
    else:
        installed_packages_path = (
            f"/kod/generations/{current_generation}/installed_packages"
        )
        services_enabled_path = (
            f"/kod/generations/{current_generation}/enabled_services"
        )

    with open(installed_packages_path) as f:
        installed_packages = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    print(installed_packages)

    with open(services_enabled_path) as f:
        services_enabled = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    print(services_enabled)

   # === Proc packages
    packages_to_install, packages_to_remove = get_packages_to_install(c, conf)
    print("packages\n", packages_to_install)

    # Package filtering
    remove_pkg = (set(installed_packages) - set(packages_to_install)) | set(packages_to_remove)
    added_pkgs = set(packages_to_install) - set(installed_packages)
    update_pkg = set(installed_packages) & set(packages_to_install)

    # === Proc services
    system_services_to_enable = get_services_to_enable(conf)

    # Services filtering
    services_to_disable = list(set(services_enabled) - set(system_services_to_enable))
    new_service_to_enable = list(set(system_services_to_enable) - set(services_enabled))

    disable_services(c, services_to_disable, new_root_path, use_chroot=use_chroot)

    # ======

    # try:
    if remove_pkg:
        print("Packages to remove:", remove_pkg)
        for pkg in remove_pkg:
            try:
                manage_packages(c, new_root_path, repos, "remove", [pkg], chroot=use_chroot)
            except:
                print(f"Unable to remove {pkg}")

    if update and update_pkg:
        print("Packages to update:", update_pkg)
        refresh_package_db(c, new_root_path, use_chroot=use_chroot)
        manage_packages(c, new_root_path, repos, "update", update_pkg, chroot=use_chroot)

    if added_pkgs:
        print("Packages to install:", added_pkgs)
        manage_packages(c, new_root_path, repos, "install", added_pkgs, chroot=use_chroot)

    # System services
    print(f"Services to enable: {new_service_to_enable}")
    # enable_services(c, system_services_to_enable, mount_point, use_chroot=use_chroot)
    enable_services(c, new_service_to_enable, new_root_path, use_chroot=use_chroot)

    # # === Proc users
    # print("\n====== Processing users ======")
    # # TODO: Check if repo is already cloned
    # user_dotfile_mngrs = proc_user_dotfile_manager(conf)
    # user_configs = proc_user_configs(conf)
    # configure_users(c, user_dotfile_mngrs, user_configs)

    # user_services_to_enable = proc_user_services(conf)
    # print(f"User services to enable: {user_services_to_enable}")
    # enable_user_services(c, user_services_to_enable, use_chroot=True)

    if new_generation:
        print("==== Deploying new generation ====")
        new_mount_point = mount_point
        deploy_new_generation(c, boot_partition, root_partition, new_root_path) #, mount_point, generation_id)
    else:
        print("==== Rebuilding current generation ====")
        new_mount_point = "/kod/current"

    # Storing list of installed packages and enabled services
    # Create a list of installed packages
    with open(f"{new_mount_point}/installed_packages", "w") as f:
        f.write("\n".join(pkgs_installed))
    # Create a list of services enabled
    with open(f"{new_mount_point}/enabled_services", "w") as f:
        f.write("\n".join(system_services_to_enable))

    # c.run(f"umount -R {new_root_path}")
    c.run(f"rm -rf {new_root_path}")

    c.run("mount -o remount,ro /usr")

    print("Done")


@task(help={"config": "system configuration file", "user": "User to rebuild config"})
def rebuild_user(c, config, user=os.environ['USER']):
    "Rebuild KodOS installation based on configuration file"
    stage = "rebuild-user"
    ctx = Context(c, os.environ['USER'], mount_point="/", use_chroot=False, stage=stage)   
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


# TODO: Update rollback
# @task(help={"generation": "Generation number to rollback to"})
# def rollback(c, generation=None):
#     "Rollback current generation to use the specified generation"

#     if generation is None:
#         print("Please specify a generation number")
#         return

#     print("Updating current generation")
#     # Check if rootfs exists
#     if os.path.isdir("/kod/generation/current/rootfs-old"):
#         c.run("sudo btrfs subvol delete /kod/generation/current/rootfs-old")
#     if os.path.isdir("/kod/generation/current/rootfs"):
#         c.run(
#             "sudo mv /kod/generation/current/rootfs /kod/generation/current/rootfs-old"
#         )
#     c.run(
#         f"sudo btrfs subvol snap /kod/generation/{generation}/rootfs /kod/generation/current/rootfs"
#     )
#     if os.path.isfile("/kod/generation/current/generation"):
#         c.run(f"sudo sed -i 's/.$/{generation}/g' /kod/generation/current/generation")
#     else:
#         c.run(f"sudo echo '{generation} > /kod/generation/current/generation")

#     print("Recreating grub.cfg")
#     c.run("grub-mkconfig -o /boot/grub/grub.cfg")
#     print("Done")


@task(help={"config": "system configuration file"})
def test_config(c, config):
    conf = load_config(config)

    devices = conf.devices
    print(f"{devices=}")
    for k, v in devices.items():
        print(f"  {k} = {v}")
        disk = devices.disk
        print(f"{disk = }")
        print(dict(v))

    boot = conf.boot
    print(f"{boot=}")
    for k, v in boot.items():
        print(f"  {k} = {v}")

    locale = conf.locale
    print(f"{locale=}")
    for k, v in locale.items():
        print(f"  {k} = {v}")
    print(locale["timezone"])

    network = conf.network
    print(f"{network=}")
    for k, v in network.items():
        print(f"  {k} = {v}")

    users = conf.users
    print(f"{users=}")
    for k, v in users.items():
        print(f"  {k} = {v}")

    packages = conf.packages
    packages_to_install, packages_to_remove = get_packages_to_install(c, conf)
    for k, v in packages.items():
        print(f"  {k} = {v}")
    print(f"{packages_to_install=}")

    print("========================================")
    #    "Install KodOS in /mnt"
    conf = load_config(config)
    print("-------------------------------")
    # boot_partition, root_partition = create_partitions(c, conf)
    boot_partition, root_partition = get_partition_devices(conf)
    print(f"{boot_partition=}")
    print(f"{root_partition=}")


@task(help={"config": "system configuration file"})
def test_packages(c, config, switch=False):
    "Install KodOS in /mnt"
    conf = load_config(config)
    print("-------------------------------")

    # === Proc packages
    # repos, repo_packages = proc_repos(c, conf)
    # packages_to_install, packages_to_remove = get_packages_to_install(c, conf)
    packages_to_install, packages_to_remove = proc_desktop(c, conf)
    print("packages to install\n",packages_to_install)
    print("packages to remove\n",packages_to_remove)

    print("Done")


##############################################################################
