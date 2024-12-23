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

def exec(c, cmd):
    c.run(cmd)

def exec_chroot(c,cmd):
    print(cmd)
    chroot_cmd = 'arch-chroot /mnt '
    chroot_cmd += cmd
    exec(c, chroot_cmd)


def enable_service(c, service):
    exec_chroot(c, f"systemctl enable {service}")


def enable_user_service(c, service):
    exec_chroot(c, f"systemctl --global enable {service}")


def mount(c, part, path):
    exec(c, f"mount {part} {path}")


def mkdir(c, path):
    exec(c, f"mkdir -p {path}")


#####################################################################################################
os_release = '''NAME="KodOS Linux"
PRETTY_NAME="KodOS Linux"
ID=kodos
ANSI_COLOR="38;2;23;147;209"
HOME_URL="https://github.com/kodos-prj/kodos/"
DOCUMENTATION_URL="https://github.com/kodos-prj/kodos/"
SUPPORT_URL="https://github.com/kodos-prj/kodos/"
BUG_REPORT_URL="https://github.com/kodos-prj/kodos/issues"
'''

#####################################################################################################

pkgs_installed = []

def load_config(config_filename: str):
    luart = lua.LuaRuntime(unpack_returned_tuples=True)
    config_path = Path(config_filename).resolve().parents[0]
    luart.execute(f"package.path = '{config_path}/?.lua;' .. package.path")
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

    base_pkgs = ["base","base-devel", microcode,  "btrfs-progs", "linux", "linux-firmware", "bash-completion", 
                 "mlocate", "sudo", "schroot", "whois"]
    # TODO: remove this package dependency
    base_pkgs += ["arch-install-scripts"]

    exec(c, f"pacstrap -K /mnt {' '.join(base_pkgs)}")


def create_users(c, conf):
    users = conf.users
    for user, info in users.items():
        # Normal users (no root)
        if user != "root":
            print(f"Creating user {user}")
            user_name = info["name"]
            exec_chroot(c, f"useradd -m -G wheel {user} -c '{user_name}'")
            exec_chroot(c, "sed -i 's/# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers")
            # TODO: Add extra groups

        # Shell 
        if not info.shell:
            shell = "/bin/bash"
        else:
            shell = info["shell"]
        exec_chroot(c, f"usermod -s {shell} {user}")

        # Password
        if not info.no_password:
            if info.hashed_password:
                print("Assign the provided password")
                print(f"usermod -p '{info.hashed_password}' {user}")
                exec_chroot(c, f"usermod -p '{info.hashed_password}' {user}")
            elif info.password:
                print("Assign the provided password after encryption")
                exec_chroot(c, f"usermod -p `mkpasswd -m sha-512 {info.password}` {user}")
            else:
                exec_chroot(c, f"passwd {user}")


def configure_system(c, conf, boot="systemd-boot"):
    
    # fstab
    exec(c, "genfstab -U /mnt > /mnt/etc/fstab")
    
    # Locale
    locale_conf = conf.locale
    if locale_conf:
        time_zone = locale_conf["timezone"]
    else:
        time_zone = "GMT"
    exec_chroot(c, f"ln -sf /usr/share/zoneinfo/{time_zone} /etc/localtime")
    exec_chroot(c, "hwclock --systohc")
    
    # Localization
    locale = dict(locale_conf["locale"])["default"]
    exec_chroot(c, f"echo '{locale}' > /etc/locale.gen")
    exec_chroot(c, "locale-gen")
    locale_name = locale.split()[0]
    exec_chroot(c, f"echo 'LANG={locale_name}' > /etc/locale.conf")
    
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
    # exec_chroot(c, "echo '127.0.0.1 kodos.localdomain kodos' >> /etc/hosts")

    # Replace default os-release
    with open("/mnt/etc/os-release","w") as f:
        f.write(os_release)

    # Configure schroot
    system_schroot = """[system]
type=directory
description=KodOS
directory=/
groups=users,root
root-groups=root
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
root-groups=root
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
/tmp            /tmp            none    rw,bind         0       0
/var/cache	    /var/cache      none	rw,bind		    0   	0
/var/log	    /var/log        none	rw,bind		    0   	0
/var/tmp	    /var/tmp        none	rw,bind		    0   	0
/var/kod	    /var/kod        none	rw,bind		    0   	0
"""
    with open("/mnt/etc/schroot/kodos/fstab", "w") as f:
        f.write(venv_fstab)

    # initramfs
    exec_chroot(c, "bash -c echo 'MODULES=(btrfs)' > /etc/mkinitcpio.conf")
    exec_chroot(c, "bash -c echo 'BINARIES=()' >> /etc/mkinitcpio.conf")
    exec_chroot(c, "bash -c echo 'FILES=()' >> /etc/mkinitcpio.conf")
    exec_chroot(c, "bash -c echo 'HOOKS=(base udev keyboard autodetect keymap consolefont modconf block filesystems fsck btrfs)' >> /etc/mkinitcpio.conf")

    exec_chroot(c, "mkinitcpio -P")

    # Change root password
    # exec_chroot(c, "passwd")


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
                    option = "rootflags="+opt


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
        exec_chroot(c, "grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB")
        exec_chroot(c, "grub-mkconfig -o /boot/grub/grub.cfg")
        # pkgs_installed += ["efibootmgr"]


def get_packages_to_install(c, conf):
    packages_to_install = []
    packages_to_remove = []

    packages_to_install, packages_to_remove = proc_desktop(c, conf)

    # Packages listed in config
    pkg_list = list(conf.packages.values())
    print("packages\n",pkg_list)
    packages_to_install += pkg_list
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


def update_fstab(c, root_path, mount_point, subvol_id):
    with open(f"{root_path}/etc/fstab") as f:
        fstab = f.readlines()
    with open(f"{root_path}/etc/fstab", "w") as f:
        for line in fstab:
            if line[0] == "#":
                f.write(line)
                continue
            cols = line.split()
            if len(cols) > 4 and cols[1] == mount_point:
                cols[3] = re.sub(r"subvol=[^,]+", f"subvol={subvol_id}", cols[3]) 
            f.write("\t".join(cols)+"\n")


def get_max_generation():
    generations = glob.glob("/kod/generations/*")
    generations = [p.split('/')[-1] for p in generations]
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
        for action, cmd in repo_desc['commands'].items():
            repos[repo][action] = cmd

        if "build" in repo_desc:
            build_info = repo_desc['build']
            url = build_info['url']
            build_cmd = build_info['build_cmd']
            name = build_info['name']

            # TODO: Generalize this code to support other distros
            exec_chroot(c, "pacman -S --needed --noconfirm git base-devel")
            exec_chroot(c, f"runuser -u kod -- /bin/bash -c 'cd && git clone {url} {name} && cd {name} && {build_cmd}'")

        if "package" in repo_desc:
            exec_chroot(c, f"pacman -S --needed --noconfirm {repo_desc['package']}")
            packages += [repo_desc['package']]
            
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
    with open("/mnt/etc/sudoers.d/kod","w") as f:
        f.write("kod ALL=(ALL) NOPASSWD: ALL")


def manage_packages(c, root_path, repos, action, list_of_packages, chroot=False):
    packages_installed = []
    pkgs_per_repo = {"official":[]}
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
            c.run(f"{exec_prefix} runuser -u kod -- {repos[repo][action]} {' '.join(pkgs)}")
        else:
            c.run(f"{exec_prefix} {repos[repo][action]} {' '.join(pkgs)}")
        packages_installed += pkgs
    return packages_installed

# --------------------------------------
# packages_to_install, packages_to_remove, packages_to_exclude
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
                if "packages" in dm_conf:
                    pkg_list = list(dm_conf.packages.values())
                    packages_to_install += pkg_list

                if "exclude_packages" in dm_conf:
                    exclude_pkg_list = list(dm_conf.exclude_packages.values())
                    packages_to_remove += exclude_pkg_list
                else:
                    exclude_pkg_list = []
                if exclude_pkg_list:
                    pkgs_to_install = get_list_of_dependencies(c, desktop_mngr)
                    pkgs_to_install = list(set(pkgs_to_install) - set(exclude_pkg_list))
                    packages_to_install += pkgs_to_install
                # else:
                packages_to_install += [desktop_mngr]
                # if "display_manager" in dm_conf:
                #     display_mngr = dm_conf["display_manager"]
                #     packages_to_install += [display_mngr]

    return packages_to_install, packages_to_remove


def proc_hardware(c, conf): #, repos, use_chroot=False):
    packages = []
    print("- processing hardware -----------")
    hardware = conf.hardware
    for name, hw in hardware.items():
        print(name, hw.enable)
        pkgs = []
        if hw.enable:
            if hw.package:
                print("  using:",hw.package)
                name = hw.package
            
            pkgs.append(name)
            if hw.extra_packages:
                print("  extra packages:",hw.extra_packages)
                for _, pkg in hw.extra_packages.items():
                    pkgs.append(pkg)
            packages += pkgs

    return packages


def proc_services(c, conf): #, repos, use_chroot=False):
    packages_to_install = []
    services_to_enable = []
    print("- processing services -----------")
    services = conf.services
    for name, service in services.items():
        print(name, service.enable)
        service_name = name
        if service.enable:
            pkgs = []
            if service.package:
                print("  using:",service.package)
                name = service.package
            if service.service_name:
                print("  using:",service.service_name)
                service_name = service.service_name
            pkgs.append(name)
            if service.extra_packages:
                print("  extra packages:",service.extra_packages)
                for _, pkg in service.extra_packages.items():
                    pkgs.append(pkg)
            # pkgs_installed = manage_packages(c, "/mnt", repos, "install", pkgs, chroot=use_chroot)
            # packages += pkgs_installed
            packages_to_install += pkgs
            services_to_enable.append(service_name)
            # enable_service(c, name+".service")
    return packages_to_install, services_to_enable


def proc_user_dotfile_manager(conf):
    print("- processing user dotfile manager -----------")
    users = conf.users
    dotfile_mngs = {}
    configs_to_deploy = {}
    for user, info in users.items():
        if info.dotfile_manager:
            print(f"Processing dotfile manager for {user}")
            dotfile_mngs[user] = info.dotfile_manager
        if info.deploy_configs:
            print(f"Processing deploy configs for {user}")
            configs_to_deploy[user] = [config for _, config in info.deploy_configs.items()]
    print(configs_to_deploy)
    return dotfile_mngs, configs_to_deploy


def proc_user_programs(c, conf):
    packages = []
    configs_to_deploy = {}
    # services_to_enable = []
    print("- processing user programs -----------")
    users = conf.users

    for user, info in users.items():
        deploy_configs = []
        if info.programs:
            print(f"Processing programs for {user}")
            pkgs = []
            for name, prog in info.programs.items():
                print(name, prog.enable)
                if prog.enable:
                    if prog.deploy_config:
                        # Program requires deploy config
                        deploy_configs.append(name)
                    # else:
                    # Configure based on the specified parameters
                    if prog.create_config:
                        prog_conf = prog.create_config
                        if "command" in prog_conf:
                            c.run(f"su {user} -c '{prog_conf.command}'")
                        else:
                            # TODO: Implement this
                            print(f"Configuring {name} with {prog.items()}")
                    if prog.package:
                        print("  using:",prog.package)
                        name = prog.package
                    if prog.extra_packages:
                        print("  extra packages:",prog.extra_packages)
                        for _, pkg in prog.extra_packages.items():
                            pkgs.append(pkg)
                    pkgs.append(name)
            packages += pkgs
        if deploy_configs:
            configs_to_deploy[user] = deploy_configs

    return packages, configs_to_deploy


def configure_users(c, dotfile_mngrs, configs_to_deploy):
    print(f"{dotfile_mngrs=}")
    print(f"{configs_to_deploy=}")
    print("- configuring users -----------")
    for user, dotmng in dotfile_mngrs.items():
        if user in configs_to_deploy:
            c.run(f"arch-chroot /mnt su {user} -c '{dotmng.init()}'")
            for config in configs_to_deploy[user]:
                c.run(f"arch-chroot /mnt su {user} -c '{dotmng.deploy(config)}'")


def enable_services(c, list_of_services, use_chroot=False):
    for service in list_of_services:
        print(f"Enabling service: {service}")
        if use_chroot:
            exec_chroot(c, f"systemctl enable {service}")
        else:
            exec(c, f"systemctl enable {service}")
        # enable_service(c, service)


def create_filesystem_hierarchy(c, boot_part, root_part, generation=0):
    print("===================================")
    print("== Creating filesystem hierarchy ==")
    c.run("mkdir -p /mnt/{store,generations,current}")
    c.run("mkdir -p /mnt/store/var")
    subvolumes = ["home", "root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for subv in subvolumes:
        c.run(f"sudo btrfs subvolume create /mnt/store/{subv}")

    # First generation
    c.run(f"mkdir -p /mnt/generations/{generation}")
    c.run(f"btrfs subvolume create /mnt/generations/{generation}/rootfs")
    
    # Mounting first generation
    c.run("umount -R /mnt")
    c.run(f"mount -o subvol=generations/{generation}/rootfs {root_part} /mnt")
    
    # c.run("mkdir -p /mnt/{home,var,root,boot}")
    for subv in subvolumes + ["boot"]:
        c.run(f"mkdir -p /mnt/{subv}")
    
    c.run(f"mount {boot_part} /mnt/boot")
    
    for subv in subvolumes:
        c.run(f"mount -o subvol=store/{subv} {root_part} /mnt/{subv}")
    
    # Write generation number
    with open("/mnt/.generation","w") as f:
        f.write(str(generation))
    
    print("===================================")


def deploy_generation(c, boot_part, root_part, generation, pkgs_installed):
    print("===================================")
    print("== Deploying generation ==")
    c.run("mkdir /new_rootfs")
    c.run(f"mount {root_part} /new_rootfs")
    c.run("btrfs subvolume snapshot /mnt /new_rootfs/current/rootfs")

    c.run("umount -R /mnt")
    c.run(f"mount -o subvol=current/rootfs {root_part} /mnt")

    c.run("mkdir -p /mnt/kod")
    c.run(f"mount {root_part} /mnt/kod")

    # Create a list of installed packages
    with open(f"/mnt/kod/generations/{generation}/installed_packages","w") as f:
        f.write("\n".join(pkgs_installed))

    # with open("/mnt/kod/current/generation", "w") as f:
    #     f.write(str(generation))

    # boot_part = "/dev/vda1"
    # device = "/dev/vda3"
    c.run(f"mount {boot_part} /mnt/boot")
    subvolumes = ["home", "root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for subv in subvolumes:
        c.run(f"mount -o subvol=store/{subv} {root_part} /mnt/{subv}")

    c.run("genfstab -U /mnt > /mnt/etc/fstab")
    # TODO: Update to use read only for rootfs
 
    exec_chroot(c, "mkinitcpio -P")
    exec_chroot(c, "grub-mkconfig -o /boot/grub/grub.cfg")
    c.run("umount -R /mnt")
    c.run("umount -R /new_rootfs")
    c.run("rm -rf /new_rootfs")
    
    print("===================================")

# Used for rebuild
def deploy_new_generation(c, boot_part, root_part, new_rootfs, generation, pkgs_installed):
    print("===================================")
    print("== Deploying generation ==")

    if os.path.isdir("/kod/current/rootfs-old"):
        c.run("rm -rf /kod/current/rootfs-old")
    c.run("mv /kod/current/rootfs /kod/current/rootfs-old")
    c.run(f"btrfs subvolume snapshot {new_rootfs} /kod/current/rootfs")

    new_current_rootfs = "/.new_current_rootfs"
    c.run(f"mkdir -p {new_current_rootfs}")
    c.run(f"mount -o subvol=current/rootfs {root_part} {new_current_rootfs}")

    c.run(f"mkdir -p {new_current_rootfs}/kod")
    c.run(f"mount {root_part} {new_current_rootfs}/kod")

    # Create a list of installed packages
    with open(f"{new_current_rootfs}/kod/generations/{generation}/installed_packages","w") as f:
        f.write("\n".join(pkgs_installed))

    # Write generation number
    with open(f"{new_current_rootfs}/.generation","w") as f:
        f.write(str(generation))

    c.run(f"mount {boot_part} {new_current_rootfs}/boot")
    subvolumes = ["home", "root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for subv in subvolumes:
        c.run(f"mount -o subvol=store/{subv} {root_part} {new_current_rootfs}/{subv}")

    c.run(f"genfstab -U {new_current_rootfs} > {new_current_rootfs}/etc/fstab")
    # TODO: Update to use read only for rootfs
 
    c.run(f"arch-chroot {new_current_rootfs} mkinitcpio -P")
    c.run(f"arch-chroot {new_current_rootfs} grub-mkconfig -o /boot/grub/grub.cfg")
    c.run(f"umount -R {new_current_rootfs}")

    for subv in subvolumes + ["boot"]:
        try:
            c.run(f"umount -R {new_rootfs}/{subv}")
        except:
            print(f"Subvolume {new_rootfs}/{subv} is not mounted")
    try:
        c.run(f"umount -R {new_rootfs}")
    except:
        print(f"Subvolume {new_rootfs} is not mounted")
    c.run(f"rm -rf {new_rootfs}")

    c.run(f"rm -rf {new_current_rootfs}")
    
    print("===================================")


# Used for rebuild
def create_next_generation(c, boot_part, root_part, generation, mount_point="/.new_rootfs"):
    # Create generation
    c.run(f"mkdir -p /kod/generations/{generation}")
    c.run(f"btrfs subvolume snapshot / /kod/generations/{generation}/rootfs")
    
    # Mounting generation
    if os.path.ismount(mount_point):
        c.run(f"umount -R {mount_point}")
        c.run(f"rm -rf {mount_point}")
    
    c.run(f"mkdir -p {mount_point}")

    c.run(f"mount -o subvol=generations/{generation}/rootfs {root_part} {mount_point}")
    c.run(f"mount {boot_part} {mount_point}/boot")
    subvolumes = ["home", "root", "var/log", "var/tmp", "var/cache", "var/kod"]
    for subv in subvolumes:
        c.run(f"mount -o subvol=store/{subv} {root_part} {mount_point}/{subv}")
    
    # Write generation number
    with open(f"{mount_point}/.generation","w") as f:
        f.write(str(generation))

    print("===================================")

    return mount_point

##############################################################################


@task(help={"config":"system configuration file"})
def install(c, config):
    "Install KodOS in /mnt"
    conf = load_config(config)
    print("-------------------------------")
    boot_partition, root_partition = create_partitions(c, conf)

    create_filesystem_hierarchy(c, boot_partition, root_partition, generation=0)
    
    install_essentials_pkgs(c)
    configure_system(c, conf)
    setup_bootloader(c, conf)
    create_kod_user(c)

    repos, repo_packages = proc_repos(c, conf)
    packages_to_install, _ = get_packages_to_install(c, conf)
    packages_to_install += repo_packages

    packages_to_install += proc_hardware(c, conf)

    # User configurations
    dotfile_mngrs, configs_to_deploy = proc_user_dotfile_manager(conf)
    user_packages, prog_configs_to_deploy = proc_user_programs(c, conf)
    packages_to_install += user_packages
    configs_to_deploy = {
        k: configs_to_deploy.get(k, []) + prog_configs_to_deploy.get(k, []) 
        for k in configs_to_deploy.keys() | prog_configs_to_deploy.keys()
    }

    # Services
    service_installed, service_to_enable = proc_services(c, conf)
    packages_to_install += service_installed

    packages_to_install = list(set(packages_to_install))

    pkgs_installed = manage_packages(c, "/mnt", repos, "install", packages_to_install, chroot=True)

    print("\n====== Creating users ======")
    create_users(c, conf)

    print("\n====== Configuring users ======")
    configure_users(c, dotfile_mngrs, configs_to_deploy)    

    print(f"Services to enable: {service_to_enable}")
    enable_services(c, service_to_enable, use_chroot=True)
    # pkgs_installed += service_installed

    print("==== Deploying generation ====")
    deploy_generation(c, boot_partition, root_partition, 0, pkgs_installed)

    print("Done")


@task(help={"config":"system configuration file"})
def rebuild(c, config, new_generation=False):
    "Rebuild KodOS installation based on configuration file"
    if new_generation:
        print("Creating a new generation")

    conf = load_config(config)
    print("========================================")
    repos = load_repos()
    if repos is None:
        print("Missing repos information")
        return
    
    boot_partition, root_partition = get_partition_devices(conf)
    # pkg_list = list(conf.packages.values())
    pkg_list, rm_pkg_list = get_packages_to_install(c, conf)
    pkg_list += proc_hardware(c, conf)
    service_list, service_to_enable = proc_services(c, conf)
    pkg_list += service_list

    user_packages, prog_configs_to_deploy = proc_user_programs(c, conf)
    pkg_list += user_packages

    print("packages\n",pkg_list)
    generation = get_max_generation()
    with open("/.generation") as f:
        current_generation = f.readline().strip()
    print(f"{current_generation = }")

    if os.path.isdir("/kod/current/installed_packages"):
        installed_packages_path = "/kod/current/installed_packages"
    else:
        installed_packages_path = f"/kod/generations/{current_generation}/installed_packages"
    with open(installed_packages_path) as f:
        inst_pkgs = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    print(inst_pkgs)

    remove_pkg = set(inst_pkgs) - set(pkg_list) | set(rm_pkg_list)
    added_pkgs = set(pkg_list) - set(inst_pkgs)

    if new_generation:
        new_generation_id = int(generation)+1
        root_path = create_next_generation(c, boot_partition, root_partition, new_generation_id, mount_point="/.new_rootfs")
    else:
        root_path = "/"

    # try:
    if remove_pkg:
        print("Packages to remove:",remove_pkg)
        for pkg in remove_pkg:
            try:
                manage_packages(c, root_path, repos, "remove", [pkg,], chroot=True)        
                # c.run(f"sudo pacman -Rscn --noconfirm {pkg}")
            except:
                print(f"Unable to remove {pkg}")
                pass
    if added_pkgs:
        print("Packages to install:", added_pkgs)
        manage_packages(c, root_path, repos, "install", added_pkgs, chroot=True)
    
    enable_services(c, service_to_enable)

    if new_generation:
        deploy_new_generation(c, boot_partition, root_partition, root_path, new_generation_id, pkg_list)
    else:
        # Create a list of installed packages
        with open("/kod/current/installed_packages","w") as f:
            f.write("\n".join(pkgs_installed))

    print("Done")


@task(help={"config":"system configuration file"})
def rebuild_inplace(c, config):
    "Rebuild KodOS installation based on configuration file"

    conf = load_config(config)
    print("========================================")
    repos = load_repos()
    if repos is None:
        print("Missing repos information")
        return
    
    boot_partition, root_partition = get_partition_devices(conf)
    # pkg_list = list(conf.packages.values())
    pkg_list, rm_pkg_list = get_packages_to_install(c, conf)
    pkg_list += proc_hardware(c, conf, repos)
    service_list, service_to_enable = proc_services(c, conf, repos)
    pkg_list += service_list

    print("packages\n",pkg_list)
    # generation = get_max_generation()
    with open("/.generation") as f:
        current_generation = f.readline().strip()
    print(f"{current_generation = }")

    if os.path.isdir("/kod/current/installed_packages"):
        installed_packages_path = "/kod/current/installed_packages"
    else:
        installed_packages_path = f"/kod/generations/{current_generation}/installed_packages"
    with open(installed_packages_path) as f:
        inst_pkgs = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    print(inst_pkgs)

    remove_pkg = set(inst_pkgs) - set(pkg_list) | set(rm_pkg_list)
    added_pkgs = set(pkg_list) - set(inst_pkgs)

    # new_generation = int(generation)+1
    # root_path = create_next_generation(c, boot_partition, root_partition, new_generation, mount_point="/.new_rootfs")
    root_path = "/"

    # try:
    if remove_pkg:
        print("Packages to remove:",remove_pkg)
        for pkg in remove_pkg:
            try:
                manage_packages(c, root_path, repos, "remove", [pkg,], chroot=False)        
                # c.run(f"sudo pacman -Rscn --noconfirm {pkg}")
            except:
                print(f"Unable to remove {pkg}")
                pass
    if added_pkgs:
        print("Packages to install:", added_pkgs)
        manage_packages(c, root_path, repos, "install", added_pkgs, chroot=False)
    
    enable_services(c, service_to_enable)

    # deploy_new_generation(c, boot_partition, root_partition, root_path, new_generation, pkg_list)
    # Create a list of installed packages
    with open("/kod/current/installed_packages","w") as f:
        f.write("\n".join(pkgs_installed))

    print("Done")


@task(help={"generation":"Generation number to rollback to"})
def rollback(c, generation=None):
    "Rollback current generation to use the specified generation"

    if generation is None:
        print("Please specify a generation number")
        return
    
    print("Updating current generation")
    # Check if rootfs exists
    if os.path.isdir("/kod/generation/current/rootfs-old"):
        c.run("sudo btrfs subvol delete /kod/generation/current/rootfs-old")
    if os.path.isdir("/kod/generation/current/rootfs"):
        c.run("sudo mv /kod/generation/current/rootfs /kod/generation/current/rootfs-old")
    c.run(f"sudo btrfs subvol snap /kod/generation/{generation}/rootfs /kod/generation/current/rootfs")
    if os.path.isfile("/kod/generation/current/generation"):
        c.run(f"sudo sed -i 's/.$/{generation}/g' /kod/generation/current/generation")
    else:
        c.run(f"sudo echo '{generation} > /kod/generation/current/generation")

    print("Recreating grub.cfg")
    c.run("grub-mkconfig -o /boot/grub/grub.cfg")
    print("Done")


@task(help={"config":"system configuration file"})
def test_partition(c, config):

    conf = load_config(config)
    print("-------------------------------")
    # create_partitions(c, conf)
    install_essentials_pkgs(c)
    # configure_system(c, conf, boot="grub")
    create_users(c, conf)

    print("Done")


@task(help={"config":"system configuration file"})
def test_config(c, config):

    conf = load_config(config)

    devices = conf.devices
    print(f"{devices=}")
    for k,v in devices.items():
        print(f"  {k} = {v}")
        disk = devices.disk
        print(f"{disk = }")
        print(dict(v))
        # print(list(disk))
        # for k,v in disk_dict.items():
            # print(f"  {k} = {v}")

    boot = conf.boot
    print(f"{boot=}")
    for k,v in boot.items():
        print(f"  {k} = {v}")

    locale = conf.locale
    print(f"{locale=}")
    for k,v in locale.items():
        print(f"  {k} = {v}")
    print(locale['timezone'])

    network = conf.network
    print(f"{network=}")
    for k,v in network.items():
        print(f"  {k} = {v}")

    users = conf.users
    print(f"{users=}")
    for k,v in users.items():
        print(f"  {k} = {v}")

    print("========================================")
#    "Install KodOS in /mnt"
    conf = load_config(config)
    print("-------------------------------")
    # boot_partition, root_partition = create_partitions(c, conf)
    boot_partition, root_partition = get_partition_devices(conf)
    print(f"{boot_partition=}")
    print(f"{root_partition=}")
    # create_partitions(c, conf)

    # create_filesystem_hierarchy(c, conf)
    
    # install_essentials_pkgs(c)
    # # configure_system(c, conf)
    # setup_bootloader(c, conf)
    # # print("\n====== Creating snapshots ======")
    # pkgs_installed = ["base", "base-devel", "linux", "linux-firmware", "btrfs-progs", "grub", "efibootmgr", "grub-btrfs"]
    # print("==== Deploying generation ====")
    # deploy_generation(c, 0, pkgs_installed)

@task(help={"config":"system configuration file"})
def test_install(c, config, switch=False):
    "Install KodOS in /mnt"
    conf = load_config(config)
    print("-------------------------------")
    # boot_partition, root_partition = create_partitions(c, conf)

    # create_filesystem_hierarchy(c, boot_partition, root_partition, generation=0)
    
    # install_essentials_pkgs(c)
    # configure_system(c, conf)
    # setup_bootloader(c, conf)
    # create_kod_user(c)

    # repos, repo_packages = proc_repos(c, conf)
    repos = {"official":{"install":"pacman -S"},"aur":{"install":"yay -S"}} #load_repos()
    if repos is None:
        print("Missing repos information")
        return
    
    packages_to_install = []
    # packages_to_install, packages_to_remove, packages_to_exclude = get_packages_to_install(c, conf)
    # packages_to_install += repo_packages
    # print("packages:",packages_to_install)

    # packages_to_install += proc_hardware(c, conf)
    # print("packages:",packages_to_install)

    # User configurations
    dotfile_mngrs, configs_to_deploy = proc_user_dotfile_manager(conf)
    user_packages, prog_configs_to_deploy = proc_user_programs(c, conf)
    packages_to_install += user_packages
    configs_to_deploy = {
        k: configs_to_deploy.get(k, []) + prog_configs_to_deploy.get(k, []) 
        for k in configs_to_deploy.keys() | prog_configs_to_deploy.keys()
    }
    print(f"{user_packages=}")

    # Services
    service_installed, service_to_enable = proc_services(c, conf)
    packages_to_install += service_installed

    packages_to_install = list(set(packages_to_install))

    print(f"Installing packages: {packages_to_install}")
    # print(f"Excluding packages: {packages_to_exclude}")
    # print(f"Removing packages: {packages_to_remove}")

    pkgs_installed = manage_packages(c, "/mnt", repos, "install", packages_to_install, chroot=True)

    # print("\n====== Creating users ======")
    # create_users(c, conf)

    # print("\n====== Configuring users ======")
    # configure_users(c, dotfile_mngrs, configs_to_deploy)    

    # print(f"Services to enable: {service_to_enable}")
    # enable_services(c, service_to_enable, use_chroot=True)
    # # pkgs_installed += service_installed

    # print("==== Deploying generation ====")
    # deploy_generation(c, boot_partition, root_partition, 0, pkgs_installed)

    print("Done")


##############################################################################
