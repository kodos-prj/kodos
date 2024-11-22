import glob
import json
import os
from pathlib import Path
# import signal
from invoke import task
import lupa as lua


# from kod.archpkgs import follow_dependencies_to_install, init_index, install_pkg
# from kod.debpkgs import follow_dependencies_to_install, init_index, install_pkg
# from kod.archpkgs import follow_dependencies_to_install, init_index, install_pkg
from kod.filesytem import create_partitions


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

    base_pkgs = ["base","base-devel", microcode,  "btrfs-progs", "linux", "linux-firmware", "bash-completion", "htop", "mlocate", "neovim", 
                 "networkmanager", "openssh", "sudo"]

    exec(c, f"pacstrap -K /mnt {' '.join(base_pkgs)}")
    # pkgs_installed += base_pkgs
    # exec(c, "pacstrap -K /mnt base linux linux-firmware btrfs-progs")


def create_users(c, conf):
    users = conf.users
    for user, info in users.items():
        print(f"Creating user {user}")
        user_name = info["name"]
        # user_pass = info["password"]
        exec_chroot(c, f"useradd -m -G wheel -s /bin/bash {user} -c '{user_name}'")
        exec_chroot(c, f"passwd {user}")
        exec_chroot(c, "sed -i 's/# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers")

def configure_system(c, conf, boot="systemd-boot"):
    # global pkgs_installed
    
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

    # exec_chroot(c, "systemctl enable NetworkManager")
    enable_service(c, "NetworkManager")
    # exec_chroot(c, "systemctl enable sshd.service")
    enable_service(c, "sshd.service")

    # initramfs
    exec_chroot(c, "bash -c echo 'MODULES=(btrfs)' > /etc/mkinitcpio.conf")
    exec_chroot(c, "bash -c echo 'BINARIES=()' >> /etc/mkinitcpio.conf")
    exec_chroot(c, "bash -c echo 'FILES=()' >> /etc/mkinitcpio.conf")
    exec_chroot(c, "bash -c echo 'HOOKS=(base udev keyboard autodetect keymap consolefont modconf block filesystems fsck)' >> /etc/mkinitcpio.conf")

    exec_chroot(c, "mkinitcpio -P")

    # Change root password
    exec_chroot(c, "passwd")


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
    global pkgs_installed
    packages_to_install = []
    packages_to_remove = []

    desktop_manager = conf.desktop_manager
    if desktop_manager:
        for desktop_mngr, dm_conf in desktop_manager.items():
            print(f"Installing {desktop_mngr}")
            if dm_conf["enable"]:
                if "packages" in dm_conf:
                    pkg_list = list(dm_conf["packages"].values())
                    packages_to_install += pkg_list

                if "exclude_packages" in dm_conf:
                    exclude_pkg_list = list(dm_conf["exclude_packages"].values())
                    packages_to_remove += exclude_pkg_list
                else:
                    exclude_pkg_list = []
                if exclude_pkg_list:
                    exclude_pkgs = '\|'.join(exclude_pkg_list)
                    pks_to_install = c.run(f"pacman -Sgq {desktop_mngr} | grep -v '{exclude_pkgs}'").stdout.split()
                    packages_to_install += [p.strip() for p in pks_to_install]
                else:
                    packages_to_install += [desktop_mngr]
                if "display_manager" in dm_conf:
                    display_mngr = dm_conf["display_manager"]
                    packages_to_install += [display_mngr]

    pkg_list = list(conf.packages.values())
    print("packages\n",pkg_list)
    packages_to_install += pkg_list
    pkgs_installed = packages_to_install
    return packages_to_install, packages_to_remove


def base_snapshot(c):
    global pkgs_installed
    print("Creating base snapshot")
    exec_chroot(c, "mkdir -p /kod/generation/0/")
    exec_chroot(c, "btrfs subvolume snapshot -r / /kod/generation/0/rootfs")
    pkgs = "\n".join(pkgs_installed)
    with open("/mnt/kod/generation/0/installed_packages","w") as f:
        f.write(pkgs)
    # exec_chroot(c, f"echo '{pkgs}' > /kod/generation/0/installed_packages")
    
    print("Creating current snapshot")
    exec_chroot(c, "mkdir -p /kod/generation/current/")
    exec_chroot(c, "btrfs subvolume snapshot /kod/generation/0/rootfs /kod/generation/current/rootfs")
    with open("/mnt/kod/generation/current/generation","w") as f:
        f.write("0")
    # exec_chroot(c, "echo '0' > /kod/generation/current/generation")
    
    print("Updating /etc/default/grub")
    exec_chroot(c, "sed -i 's/GRUB_DEFAULT=0/GRUB_DEFAULT=saved/' /etc/default/grub")
    exec_chroot(c, "sed -i 's/#GRUB_SAVEDEFAULT=true/GRUB_SAVEDEFAULT=true/' /etc/default/grub")
    
    print("Recreating grub.cfg")
    exec_chroot(c, "grub-mkconfig -o /boot/grub/grub.cfg")


def get_max_generation():
    generations = glob.glob("/kod/generation/*")
    # generations = [p for p in generations if not os.path.islink(p)]
    generations = [p.split('/')[-1] for p in generations]
    generations = [int(p) for p in generations if p != "current"]
    print(f"{generations=}")
    if generations:
        generation = max(generations)
    else:
        generation = 0
    print(f"{generation=}")
    return generation

# --------------------------------------
def proc_repos(c, conf):
    repos_conf = conf.repos
    repos = {}
    for repo, repo_desc in repos_conf.items():
        repos[repo] = repo_desc['commands']
        if "build" in repo_desc:
            name = repo_desc['name']
            build_info = repo_desc['build']
            url = build_info['url']
            build_cmd = build_info['build_cmd']
            # Check if use kod already exists
            exec_chroot(c, "useradd -m -G wheel -s /bin/bash kod")
            exec_chroot(c, "/bin/bash -c echo 'kod ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/kod")

            exec_chroot(c, "mkdir -p /kod/extra/")
            exec_chroot(c, "chown kod:kod /kod/extra/")
            exec_chroot(c, "pacman -S --needed git base-devel")
            exec_chroot(c, f"/bin/bash -c 'cd /kod/extra/ && git clone {url} {name} && cd {name} && {build_cmd}'")

            # exec_chroot(c, 'userdel -r kod')
            # exec_chroot(c, 'rm -f /etc/sudoers.d/kod')
            
    return repos

# def create_kod_user(c):
#     exec_chroot(c, "useradd -m -G wheel -s /bin/bash kod")
#     exec_chroot(c, "bash -c echo 'kod ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/kod")
#     # exec_chroot('userdel', '-r', 'aur')
#     # exec_chroot('rm', '-f', '/etc/sudoers.d/aur')


# def install_aur_packages(c, aur_packages):
#     return_val = exec_chroot(
#         'runuser', '-u', 'aur', '--', 'paru', '-Sy', '--noconfirm', '--needed',
#         '--noprogressbar', '--skipreview', '--removemake', '--cleanafter', '--ask=4',
#         *aur_packages)
#     exec_chroot('userdel', '-r', 'aur')
#     exec_chroot('rm', '-f', '/etc/sudoers.d/aur')


def install_packages(c, repos, packages_to_install):
    pkgs_per_repo = {"official":[]}
    for pkg in packages_to_install:
        if ":" in pkg:
            repo, pkg_name = pkg.split(":")
            if repo not in pkgs_per_repo:
                pkgs_per_repo[repo] = []
            pkgs_per_repo[repo].append(pkg_name)
        else:
            pkgs_per_repo["official"].append(pkg)

    for repo, pkgs in pkgs_per_repo.items():
        exec_chroot(c, f"{repos[repo]["install"]} --noconfirm {" ".join(pkgs)}")

##############################################################################


@task(help={"config":"system configuration file"})
def install(c, config):
    "Install KodOS in /mnt"
    conf = load_config(config)
    print("-------------------------------")
    create_partitions(c, conf)
    install_essentials_pkgs(c)
    configure_system(c, conf)
    setup_bootloader(c, conf)
    # create_kod_user(c)
    repos = proc_repos(c, conf)
    packages_to_install, _ = get_packages_to_install(c, conf)
    install_packages(c, repos, packages_to_install)
    create_users(c, conf)

    base_snapshot(c)

    print("Done")


@task(help={"config":"system configuration file"})
def rebuild(c, config):
    "Rebuild KodOS installation based on configuration file"

    conf = load_config(config)
    print("========================================")
    # pkg_list = list(conf.packages.values())
    pkg_list, rm_pkg_list = get_packages_to_install(c, conf)
    print("packages\n",pkg_list)
    generation = get_max_generation()
    with open("/kod/generation/current/generation") as f:
        current_generation = f.readline().strip()
    print(f"{current_generation = }")

    with open(f"/kod/generation/{current_generation}/installed_packages") as f:
        inst_pkgs = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    print(inst_pkgs)

    remove_pkg = set(inst_pkgs) - set(pkg_list) | set(rm_pkg_list)
    added_pkgs = set(pkg_list) - set(inst_pkgs)

    if remove_pkg:
        print("Packages to remove:",remove_pkg)
        for pkg in remove_pkg:
            try:
                c.run(f"sudo pacman -Rscn --noconfirm {pkg}")
            except:
                print(f"Unable to remove {pkg}")
                pass
    if added_pkgs:
        print("Packages to install:", added_pkgs)
        c.run(f"sudo pacman -S --noconfirm {' '.join(added_pkgs)}")
    
    new_generation = int(generation)+1
    print(f"New generation: {new_generation}")
    c.run(f"sudo mkdir -p /kod/generation/{new_generation}")
    c.run(f"sudo btrfs subvol snap -r / /kod/generation/{new_generation}/rootfs")
    with open(f"/kod/generation/{new_generation}/installed_packages", "w") as f:
        f.write("\n".join(pkg_list))
    
    print("Updating current generation")
    # Check if rootfs exists
    if os.path.isdir("/kod/generation/current/rootfs-old"):
        c.run("sudo btrfs subvol delete /kod/generation/current/rootfs-old")
    if os.path.isdir("/kod/generation/current/rootfs"):
        c.run("sudo mv /kod/generation/current/rootfs /kod/generation/current/rootfs-old")
    c.run(f"sudo btrfs subvol snap /kod/generation/{new_generation}/rootfs /kod/generation/current/rootfs")
    if os.path.isfile("/kod/generation/current/generation"):
        c.run(f"sudo sed -i 's/.$/{new_generation}/g' /kod/generation/current/generation")
    else:
        c.run(f"sudo echo '{new_generation} > /kod/generation/current/generation")

    print("Recreating grub.cfg")
    c.run("grub-mkconfig -o /boot/grub/grub.cfg")
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
    create_partitions(c, conf)
    install_essentials_pkgs(c)
    # configure_system(c, conf, boot="grub")
    # create_users(c, conf)

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

    # configure_system_test(c, conf)
    # setup_bootloader(c, conf)
    # install_essentials_pkgs(c)
    # packages_to_install = install_packages(c, conf)
    # print(packages_to_install)
    print("========================================")
    rebuild(c, config)

##############################################################################
