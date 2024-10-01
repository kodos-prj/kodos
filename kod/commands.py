import glob
import json
from operator import ne
import os
from pathlib import Path
from invoke import task
import lupa as lua

from pprint import pprint

# from kod.archpkgs import follow_dependencies_to_install, init_index, install_pkg
# from kod.debpkgs import follow_dependencies_to_install, init_index, install_pkg
from kod.archpkgs import follow_dependencies_to_install, init_index, install_pkg
from kod.filesytem import create_partitions

@task(help={"root":"root path for the installation"})
def init_root(c, root = "rootfs"):
    # kod hierarchy
    kod_dirs = ["kod/config", "kod/generations", "kod/pkgs"]
    c.config["run"]["env"]["KOD_ROOTFS"] = root 
    root_kod_dirs = [root + "/" + d for d in kod_dirs]
    c.run(f"mkdir -p {' '.join(root_kod_dirs)}")

    # File hierarchy
    fhs_dirs = ["usr/bin", "usr/lib", "usr/share", "etc", "proc", "tmp", "dev", "var", "run", "root", "sys", "var/tmp" ]
    root_fhs_dirs = [root + "/" + d for d in fhs_dirs]
    c.run(f"mkdir -p {' '.join(root_fhs_dirs)}")

    c.run(f"cd {root} && ln -s usr/bin bin && ln -s usr/lib lib && ln -s usr/lib lib64 && ln -s usr/bin sbin && ln -s usr/bin usr/sbin && ln -s usr/lib usr/lib64")

    c.run(f"cd {root}/usr/lib && ln -s ld-linux-x86-64.so.2 ld-linux.so.2")

    c.run(f"cd {root} && touch etc/shells")

    c.run(f"genfstab -U {root} > /mnt/etc/fstab")
    c.run("cat /mnt/etc/fstab | grep /boot > /mnt/etc/fstab.initrd")

    os_release = '''NAME="KodOS Linux"
PRETTY_NAME="KodOS Linux"
ID=kodos
ANSI_COLOR="38;2;23;147;209"
HOME_URL="https://github.com/kodos-prj/kodos/"
DOCUMENTATION_URL="https://github.com/kodos-prj/kodos/"
SUPPORT_URL="https://github.com/kodos-prj/kodos/"
BUG_REPORT_URL="https://github.com/kodos-prj/kodos/issues"'''

    with open(f"{root}/etc/os-release","w") as f:
        f.write(os_release)
   
    # Create user/group files
    with open(f"{root}/etc/passwd","w") as f:
        f.write("root:x:0:0:root:/root:/bin/bash\n")

    with open(f"{root}/etc/shadow","w") as f:
        f.write("root:*:14871::::::\n")


    with open(f"{root}/etc/group","w") as f:
        f.write("root:x:0:root\n")

    with open(f"{root}/etc/gshadow","w") as f:
        f.write("root:::root\n")

    with open(f"{root}/etc/hostname","w") as f:
        f.write("kodos\n")

    with open(f"{root}/etc/hosts","w") as f:
        f.write("127.0.0.1 localhost\n")

    with open(f"{root}/etc/resolv.conf","w") as f:
        f.write("nameserver 8.8.8.8\n")

    with open(f"{root}/etc/motd","w") as f:
        f.write("Welcome to KodOS\n")

    with open(f"{root}/etc/issue","w") as f:
        f.write("KodOS Linux \\r (\\l)\n")

    # c.run(f"rm -f {root} /etc/locale.gen")
    # c.run(f"echo 'en_US.UTF-8 UTF-8' > {root}/etc/locale.gen")

    # rootfs = c.config["run"]["env"]["KOD_ROOTFS"]
    # print("Rootfs:", rootfs)

# ----------------------------------

def load_config(config_filename: str):
    luart = lua.LuaRuntime(unpack_returned_tuples=True)
    config_path = Path(config_filename).resolve().parents[0]
    luart.execute(f"package.path = '{config_path}/?.lua;' .. package.path")
    with open(config_filename) as f:
        config_data = f.read()
        conf = luart.execute(config_data)
    return conf

def get_next_generation():
    generations = glob.glob("kod/generations/*")
    generations = [p for p in generations if not os.path.islink(p)]
    generations = [int(p.split('/')[-1]) for p in generations]
    print(f"{generations=}")
    if generations:
        generation = max(generations)+1
        # generation = int(last_generation.split("/")[-1]) + 1
    else:
        generation = 1
    print(f"{generation=}")
    return generation

def get_list_of_packages_to_install(catalog, pkg_name):
    packages_to_install = {}
    packages_to_install = follow_dependencies_to_install(
        catalog, pkg_name, packages_to_install
    )
    return packages_to_install

def calc_sizes(packages_to_install):
    csize = 0
    isize = 0
    for pkg, desc in packages_to_install.items():
        csize += int(desc["csize"])
        isize += int(desc["isize"])
    return csize / 1e6, isize / 1e6


def make_pkg_generation_links(c, pkgs_to_link, generation, absolute=False):
    cwd = ""
    if absolute:
        cwd = str(Path.cwd())
    for pkg, desc in pkgs_to_link.items():
        pkg_path = f"{cwd}/kod/pkgs" / Path(pkg) / Path(desc["version"])
        # pkg_path = "/workspaces/antos/demofs/kod/pkgspip freeee" / Path(pkg) / Path(desc['version'])
        gen_pkg_path = f"kod/generations/{generation}/{pkg}"
        print("  SYMLINK:", gen_pkg_path, "->", pkg_path)
        # c.run(f"ln -s -f {pkg_path} {gen_pkg_path}")
        c.run(f"ln -s -f ../../pkgs/{pkg}/{desc['version']} {gen_pkg_path}")
        # os.symlink(pkg_path, gen_pkg_path)

def make_file_generation_links(c, pkgs_to_link, target="", absolute=False):
    created_dirs = []
    created_symlinks = []
    cwd = ""
    if absolute:
        cwd = str(Path.cwd())

    print(f"{target=}")
    # sys.exit()

    for pkg, desc in pkgs_to_link.items():
        # install_path = Path(f"{target}/{app_name}/{app_version}")
        # target = "kod/pkgs"
        # current_path = Path(f"kod/generations/current/{pkg}/").resolve()
        pkg_path = "kod/pkgs" / Path(pkg) / Path(desc["version"])
        gen_pkg_path = f"/kod/generations/current/{pkg}"

        # files = list(current_path.rglob("[!.]*"))
        files = list(pkg_path.rglob("[!.]*"))
        # files = list(current_path.rglob("*"))
        # print(files)
        for p in files:
            rel_path_list = str(p).split("/")
            # print(f"{rel_path_list=}")
            rel_path = Path("/".join(rel_path_list[4:]))
            print(rel_path)
            file_path = gen_pkg_path / rel_path

            if p.is_dir():
                if not rel_path.is_dir():
                    # tmp = f"{target / rel_path}"
                    # print(" MKDIR:", target / rel_path, rel_path.is_dir())
                    os.makedirs(target / rel_path, exist_ok=True)
                    # c.run(f"mkdir -p {target/rel_path}")
                    # os.makedirs(rel_path)
                    created_dirs.append(rel_path)
            else:
                if rel_path.is_symlink():
                    # print("  SKIPPING:", target / rel_path, rel_path.is_symlink())
                    os.unlink(target / rel_path)
                    # c.run(f"rm {target/rel_path}")
                # if not rel_path.is_symlink():
                # else:
                print("  SYMLINK:", target / rel_path, "->", cwd + str(file_path))
                os.symlink(cwd + str(file_path), target / rel_path)
                # c.run(f"ln -s -f {target/rel_path} {gen_pkg_path/rel_path}")
                created_symlinks.append(rel_path)

    with open("kod/generations/current/.created_symlink.txt", "w") as f:
        for d in created_symlinks:
            f.write(str(d) + "\n")
    with open("kod/generations/current/.created_dirs.txt", "w") as f:
        for d in created_dirs:
            f.write(str(d) + "\n")


def search_string(string, filename):
    with open(filename) as f:
        return  string in f.read()


def report_install_scripts(c, new_added_pkgs, updated_pkgs, removed_pkgs):
    print(f"{new_added_pkgs = }")
    print(f"{updated_pkgs = }")
    print(f"{removed_pkgs = }")
    pkg_path = Path(f"kod/generations/current/")
    files = list(pkg_path.rglob("*/.INSTALL"))
    for pkg_path in files:
        pkg = pkg_path.parts[3]
        print(pkg, pkg_path)
        # New installed packages
        if pkg in new_added_pkgs:
            if search_string("post_install", pkg_path):
                print(f". {pkg_path} && post_install")
                c.run(f". {pkg_path} && post_install")
            if search_string("post_upgrade", pkg_path):
                print(f". {pkg_path} && post_upgrade")
                c.run(f". {pkg_path} && post_upgrade")

        # Packages that are updated
        if pkg in updated_pkgs:
            if search_string("post_upgrade", pkg_path):
                print(f". {pkg_path} && post_upgrade")
                c.run(f". {pkg_path} && post_upgrade")


def load_catalog(c, sources):
    if not Path("kod/config/catalog.json").exists():
        # Init catalog
        init_index(c, sources)
    with open("kod/config/catalog.json") as f:
        catalog = json.load(f)
    return catalog

def load_installed(gen_path):
    inst_pkgs = {}
    with open(f"{gen_path}/.installed_packages") as f:
        for line in f:
            pkg,version = line.split(" ")
            inst_pkgs[pkg] = version.strip()
        # inst_pkgs = f.readlines()
    return inst_pkgs

def save_installed(generation, inst_pkgs):
    with open(f"kod/generations/{generation}/.installed_packages","w") as f:
        for pkg, info in inst_pkgs.items():
            f.write(f"{pkg} {info['version']}\n")


@task(help={"config":"system configuration file"})
def rebuild(c, config):
    # [x] Check if catalog existsx
    # If not,
    #   [x] read config and get the sources
    #   [x] Download the catalog and create catalog.json
    # [x] Read the catalog.json

    # New rebuild:
    # - [ ] A new generation is created, and the list of packages, pkgs's configurations are recreated
    # - [ ] If new  packages are added, they are downloaded and stored in pkgs directory
    # - [ ] from the list os selected packages, link pkgs in the new generation

    absolute = False

    conf = load_config(config)


    devices = conf.devices
    print(f"{devices=}")

    boot = conf.boot
    print(f"{boot=}")

    locale = conf.locale
    print(f"{locale=}")

    network = conf.network
    print(f"{network=}")

    users = conf.users
    print(f"{users=}")

    pkg_list = list(conf.packages.values())
    print("packages\n",pkg_list)

    # catalog = load_catalog(c, conf.sources)
    if not Path("kod/config/catalog.json").exists():
        # Init catalog
        sources = conf.source
        init_index(c, sources)
    with open("kod/config/catalog.json") as f:
        catalog = json.load(f)

    # created_dirs = []
    # if Path("kod/generations/current/.created_dirs.txt").exists():
    #     with open("kod/generations/current/.created_dirs.txt") as f:
    #         created_dirs = f.read().split("\n")

    # created_symlinks = []
    # if Path("kod/generations/current/.created_symlink.txt").exists():
    #     with open("kod/generations/current/.created_symlink.txt") as f:
    #         created_symlinks = f.read().split("\n")

    previous_installed = None
    generation = get_next_generation()
    c.run(f"mkdir -p kod/generations/{generation}")
    if generation > 1:
        previous_installed = load_installed("kod/generations/current")
        c.run("rm kod/generations/current")
    c.run(f"cd kod/generations && ln -s {generation} current")

    # pkg_list = list(conf.packages.values())
    # print(pkg_list)

    all_pkgs_to_install = {}
    packages_to_install = {}
    for pkgname in pkg_list:
        # print(pkgname)
        packages_to_install = get_list_of_packages_to_install(catalog, pkgname)
        # print(packages_to_install.keys())
        all_pkgs_to_install.update(packages_to_install)

    save_installed(generation, all_pkgs_to_install)

    if previous_installed:
        new_added_pkgs = set(all_pkgs_to_install.keys()) - set(previous_installed.keys())
    else:
        new_added_pkgs = set(all_pkgs_to_install.keys())
    print(f"{new_added_pkgs = }")

    updated_pkgs = []
    if previous_installed:
        same_pkgs = set(all_pkgs_to_install.keys()) & set(previous_installed.keys())
        for pkg in same_pkgs:
            if previous_installed[pkg] != all_pkgs_to_install[pkg]['version']:
                updated_pkgs.append(pkg)
    print(f"{updated_pkgs = }")

    removed_pkgs = []
    if previous_installed:
        removed_pkgs = set(previous_installed.keys() - set(all_pkgs_to_install.keys()))
    print(f"{removed_pkgs = }")

    
    print("========= packages ==========")
    for pkg in all_pkgs_to_install.keys():
        print("-",pkg)
    print("=============================")

    for pkg, desc in all_pkgs_to_install.items():
        download_size, install_size = calc_sizes(packages_to_install)
        print(f"Download size: {download_size}, Install size: {install_size}\n")
        print(pkg, desc["filename"])
        mirror_url = f"{conf.source.url}/{desc['repo']}/os/{conf.source.arch}/"
        # mirror_url = get_mirror_url(globals.source, desc['repo'])
        print(mirror_url)
        install_pkg(c, mirror_url, desc, "")

    make_pkg_generation_links(c, all_pkgs_to_install, generation, absolute=absolute)
    # remove_previous_current(created_symlinks, created_dirs)
    # make_file_generation_links(all_pkgs_to_install, "kod/generations/current/.rootfs")
    make_file_generation_links(c, all_pkgs_to_install, "", absolute=absolute)

    # # TODO:
    # # Remove broken links (files are not used)
    # # Check for packages that have .INSTALL file

    print("************ ****** ***** *** ** *")
    for pkg, desc in all_pkgs_to_install.items():
        print(pkg, desc["version"])

    print("====== ==== == =")
    report_install_scripts(c, new_added_pkgs, updated_pkgs, removed_pkgs)
    # -------


# -----------------------------------------------------
# Intall/create partitions
# -----------------------------------------------------
@task(help={"config":"system configuration file"})
def install(c, config):

    conf = load_config(config)

    devices = conf.devices
    print(f"{devices=}")

    print(f"{list(devices.keys())=}")
    # for k,v in devices.disk.items():
    #     print(f"  {k} = {v}")
    print("->>",devices.disk0)
    for d_id, disk in devices.items():
        print(d_id)
        create_partitions(c, disk)
    print("-------------------------------")

    # boot = conf.boot
    # print(f"{boot=}")


# -----------------------------------------------------
# Intall bootloader
# -----------------------------------------------------
@task(help={"config":"system configuration file"})
def install_boot(c, config):

    conf = load_config(config)

    boot = conf.boot
    print(f"{boot=}")

    initrd = boot.initrd
    print(f"{initrd=}")

    if not Path("kod/config/catalog.json").exists():
        # Init catalog
        sources = conf.source
        init_index(c, sources)
    with open("kod/config/catalog.json") as f:
        catalog = json.load(f)

    linux_desc = catalog["linux"]
    # kver = linux_desc["version"]
    kver = "6.10.10-arch1-1"
    c.run(f"arch-chroot /mnt depmod {kver}")
    # depmod 6.10.10-arch1-1
    c.run(f"arch-chroot /mnt dracut -v -H --add-fstab /etc/fstab.initrd --kver {kver} --libdirs lib64")
    # dracut -v --fstab --kver 6.10.10-arch1-1 --libdirs lib64  # <--- ok

    # loader processing
    loader = boot.loader
    for item,value in loader.items():
        print(item,value)

    loader_type = loader.type

    if loader_type == "systemd-boot":
        print("Using systemd-boot")
        
        # Remove the linked fie to avoid cross partion links
        efi_systemd_boot = "/usr/lib/systemd/boot/efi/systemd-bootx64.efi"
        # mv /usr/lib/systemd/boot/efi/systemd-bootx64.efi /usr/lib/systemd/boot/efi/systemd-bootx64.efi-lnk
        c.run(f"mv /mnt{efi_systemd_boot} /mnt{efi_systemd_boot}-lnk")
        # cp /kod/generations/current/systemd/usr/lib/systemd/boot/efi/systemd-bootx64.efi /usr/lib/systemd/boot/efi/systemd-bootx64.efi
        c.run(f"cp /mnt/kod/generations/current/systemd/{efi_systemd_boot} /mnt{efi_systemd_boot}")

        # ------------
        # bootctl --make-entry-directory=yes install 
        c.run(f"arch-chroot /mnt bootctl --make-entry-directory=yes install")

        # kernel-install -v add 6.10.10-arch1-1 /usr/lib/modules/6.10.10-arch1-1/vmlinuz /boot/initramfs-6.10.10-arch1-1.img 
        c.run(f"arch-chroot /mnt kernel-install -v add {kver} /usr/lib/modules/{kver}/vmlinuz /boot/initramfs-{kver}.img ")

        # ------------
        # rm /usr/lib/systemd/boot/efi/systemd-bootx64.efi
        c.run(f"rm /mnt{efi_systemd_boot}")
        # mv /usr/lib/systemd/boot/efi/systemd-bootx64.efi-lnk /usr/lib/systemd/boot/efi/systemd-bootx64.efi
        c.run(f"mv /mnt{efi_systemd_boot}-lnk /mnt{efi_systemd_boot}")

    entries_to_include = loader.include

    for entry in entries_to_include.values():
        print(f"Include {entry}")
        print(f"install '{entry}-efi' if not installed")
        print(f"Create /boot/loader/entries/{entry}.conf")
        print(f"title\t {entry}\nefi\t /{entry}/{entry}.efi")
    print("-------------------------------")


# -----------------------------------------------------
# Intall bootloader
# -----------------------------------------------------
@task(help={"config":"system configuration file"})
def install_network(c, config):

    conf = load_config(config)

    network = conf.network
    print(f"{network=}")

    if "hostname" in network:
        c.run(f"arch-chroot /mnt hostnamectl set-hostname {network.hostname}")

    c.run(f"arch-chroot /mnt systemctl enable systemd-networkd")

    c.run(f'arch-chroot /mnt timedatectl set-timezone "America/Edmonton"')

    # c.run(f'arch-chroot /mnt timedatectl set-ntp true')

    c.run(f"arch-chroot /mnt passwd -d root")


# ToDO
# create /etc/eo-release
# NAME="KodOS Linux"
# PRETTY_NAME="KodOS Linux"
# ID=kodos
# ANSI_COLOR="38;2;23;147;209"
# HOME_URL="https://github.com/kodos-prj/kodos/"
# DOCUMENTATION_URL="https://github.com/kodos-prj/kodos/"
# SUPPORT_URL="https://github.com/kodos-prj/kodos/"
# BUG_REPORT_URL="https://github.com/kodos-prj/kodos/issues"
## LOGO=archlinux-logo

# To install boot manager (system-boot)
# copy /usr/lib/systemd/boot/efi/systemd-bootx64.efi
# On an x64 UEFI, /usr/lib/systemd/boot/efi/systemd-bootx64.efi will be copied 
# to esp/EFI/systemd/systemd-bootx64.efi and esp/EFI/BOOT/BOOTX64.EFI

# mkdir -p /boot/EFI/systemd/
# mkdir -p /boot/EFI/BOOT/
# cp /usr/lib/systemd/boot/efi/systemd-bootx64.efi /boot/EFI/systemd/
# cp /usr/lib/systemd/boot/efi/systemd-bootx64.efi /boot/EFI/BOOT/BOOTX64.EFI


# bootctl will do the copy <--- ok
# mv /usr/lib/systemd/boot/efi/systemd-bootx64.efi /usr/lib/systemd/boot/efi/systemd-bootx64.efi-lnk
# cp /kod/generations/current/systemd/usr/lib/systemd/boot/efi/systemd-bootx64.efi /usr/lib/systemd/boot/efi/systemd-bootx64.efi

# bootctl --make-entry-directory=yes install   # <-- ok


# mkdir -p /boot/kod
# depmod 6.10.10-arch1-1                                    # <--- ok
# dracut -v --fstab --kver 6.10.10-arch1-1 --libdirs lib64  # <--- ok  
# cp /boot/initramfs-6.10.10-arch1-1.img /boot/kod
# cp /mnt/kod/generations/current/linux/usr/lib/models/6.10.10-arch1-1/vmlinuz /mnt/boot/kod/vmlinuz-6.10.10-arch1-1

# /boot/loader/entries/kodos.conf
# title   KodOS Linux
# linux   /kod/vmlinuz-6.10.10-arch1-1
# initrd  /kod/initramfs-6.10.10-arch1-1.img

# /usr/lib/kernel/install.d/50-depmod.install add 6.10.10-arch1-1 /boot/kodos/6.10.10-arch1-1 /usr/lib/modules/6.10.10-arch1-1/vmlinuz /initrd
# kernel-install -v add 6.10.10-arch1-1 /usr/lib/modules/6.10.10-arch1-1/vmlinuz /initrd

# kernel-install -v add 6.10.10-arch1-1 /usr/lib/modules/6.10.10-arch1-1/vmlinuz /boot/initramfs-6.10.10-arch1-1.img  # <-- ok


# memtest86+ should use copy instead of link
# '/kod/generations/current/memtest86+-efi/boot/memtest86+/memtest.efi' -> 'boot/memtest86+/memtest.efi'


# rd.driver.pre=btrfs

# root=UUID=9ffd9206-5b27-4b36-be06-3c50fd22ab34 rootfstype=ext4 rootflags=rw,relatime


# mkinitcpio -k 6.10.10-arch1-1 -A "systemd" -g /boot/initramfs-6.10.10-arch1-1-mkcpio.img 

# dracut --kver 6.10.10-arch1-1 --force --add "busybox bash shutdown test"
# root=UUID=a1e30583-57d2-4aa0-98e2-b80226d57ae7 rootfstype=ext4 rootflags=rw,relatime


# sudo chroot mnt /usr/bin/env -i HOME=/root TERM="$TERM" PS1='(kodos) \u:\w\$ ' PATH=/usr/bin /bin/bash --login


# git clone https://github.com/kodos-prj/kodos

# fstab only with /boot
# rd.driver.pre=ext4 rd.driver.pre=vfat rd.shell rd.debugg log_buf_len=1M root=/dev/vda2 rw

# 10.0.2.15/24  gw 10.0.2.2