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

# def preexec():
#     signal.signal(signal.SIGHUP, signal.SIG_IGN)
#     signal.signal(signal.SIGINT, signal.SIG_IGN)
#     signal.signal(signal.SIGQUIT, signal.SIG_IGN)


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
    # global pkgs_installed
    # cpuinfo = c.run("grep vendor_id /proc/cpuinfo | head -n 1")
    microcode = "amd-ucode"
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


        loader_conf = """
default arch
timeout 3
console-mode max
#editor no"""
        with open("/mnt/boot/loader/loader.conf", "w") as f:
            f.write(loader_conf)
        
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
        exec_chroot(c, "pacman -S --noconfirm grub efibootmgr grub-btrfs")
        exec_chroot(c, "grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB")
        exec_chroot(c, "grub-mkconfig -o /boot/grub/grub.cfg")
        # pkgs_installed += ["efibootmgr"]


def install_packages(c, conf):
    global pkgs_installed
    pkg_list = list(conf.packages.values())
    print("packages\n",pkg_list)
    exec_chroot(c, "pacman -S --noconfirm {}".format(" ".join(pkg_list)))
    pkgs_installed = pkg_list


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


def get_next_generation():
    generations = glob.glob("/kod/generations/*")
    generations = [p for p in generations if not os.path.islink(p)]
    generations = [int(p.split('/')[-1]) for p in generations]
    print(f"{generations=}")
    if generations:
        generation = max(generations)+1
    else:
        generation = 1
    print(f"{generation=}")
    return generation


##############################################################################


@task(help={"config":"system configuration file"})
def install(c, config):
    "Install KodOS in /mnt"
    conf = load_config(config)
    print("-------------------------------")
    create_partitions(c, conf)
    install_essentials_pkgs(c)
    configure_system(c, conf)
    install_packages(c, conf)
    create_users(c, conf)

    base_snapshot(c)

    print("Done")


@task(help={"config":"system configuration file"})
def rebuild(c, config):

    conf = load_config(config)
    print("========================================")
    pkg_list = list(conf.packages.values())
    print("packages\n",pkg_list)
    generation = get_next_generation()
    # with open("/kod/generation/current/generation") as f:
        # generation = f.readline().strip()
    print(generation)

    with open(f"/kod/generation/{generation}/installed_packages") as f:
        inst_pkgs = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    print(inst_pkgs)

    remove_pkg = set(inst_pkgs) - set(pkg_list)
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
        c.run(f"sudo pacman -S --noconfirm {" ".join(added_pkgs)}")
    
    new_generation = int(generation)+1
    print(f"New generation: {new_generation}")
    c.run(f"sudo mkdir -p /kod/generation/{new_generation}")
    c.run(f"sudo btrfs subvol snap -r / /kod/generation/{new_generation}/rootfs")
    with open(f"/kod/generation/{new_generation}/installed_packages", "w") as f:
        f.write("\n".join(pkg_list))
    
    print("Updating current generation")
    # Check if rootfs exists
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


@task(help={"config":"system configuration file"})
def test_partition(c, config):

    conf = load_config(config)
    print("-------------------------------")
    create_partitions(c, conf)
    install_essentials_pkgs(c)
    # configure_system(c, conf, boot="grub")
    # create_users(c, conf)

    print("Done")


# @task(help={"config":"system configuration file"})
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
    # configure_system_test(c, conf)

##############################################################################
