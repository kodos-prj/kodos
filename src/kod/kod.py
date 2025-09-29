"""Main command-line interface for the KodOS system.

This module provides the primary CLI interface using Click framework for interacting
with KodOS functionality including installation, configuration, and system management.

@Author: Anatal Buss
@version 0.1
"""

import os

import click

# from kod.arch import get_base_packages, get_kernel_file, install_essentials_pkgs, proc_repos, refresh_package_db
from kod.common import exec, set_debug, set_verbose
from kod.core import (
    Context,
    change_subvol,
    configure_system,
    configure_user_dotfiles,
    configure_user_scripts,
    create_boot_entry,
    create_filesystem_hierarchy,
    create_kod_user,
    create_next_generation,
    disable_services,
    enable_services,
    enable_user_services,
    generate_fstab,
    get_max_generation,
    get_packages_to_install,
    get_packages_updates,
    get_pending_packages,
    get_services_to_enable,
    load_config,
    load_fstab,
    load_package_lock,
    load_packages_services,
    load_repos,
    manage_packages,
    manage_packages_shell,
    proc_user_home,
    proc_users,
    setup_bootloader,
    store_packages_services,
    update_all_packages,
    user_configs,
    user_dotfile_manager,
    user_services,
)
from kod.core import set_base_distribution
from kod.filesytem import create_partitions, get_partition_devices

# from kod.core import *


#####################################################################################################
@click.group()
@click.option("-d", "--debug", is_flag=True)
@click.option("-v", "--verbose", is_flag=True)
def cli(debug, verbose):
    set_debug(debug)
    set_verbose(verbose)


# pkgs_installed = []
base_distribution = "arch"

##############################################################################


@cli.command()
@click.option("-c", "--config", default=None, help="System configuration file")
@click.option("-m", "--mount_point", default="/mnt", help="Mount poin used to install")
def install(config, mount_point):
    "Install KodOS based on the given configuration"
    ctx = Context(os.environ["USER"], mount_point=mount_point, use_chroot=True, stage="install")

    conf = load_config(config)

    base_distribution = conf.base_distribution
    base_distribution = "arch" if base_distribution is None else base_distribution
    print("Base distribution:", base_distribution)

    dist = set_base_distribution(base_distribution)

    # if base_distribution == "debian":
    #     from kod.debian import (
    #         generale_package_lock,
    #         get_base_packages,
    #         install_essentials_pkgs,
    #         proc_repos,
    #     )
    #     exec("apt install -y gdisk")
    # else:
    #     from kod.arch import (
    #         generale_package_lock,
    #         get_base_packages,
    #         install_essentials_pkgs,
    #         proc_repos,
    #     )

    print("-------------------------------")
    boot_partition, root_partition, partition_list = create_partitions(conf)

    partition_list = create_filesystem_hierarchy(boot_partition, root_partition, partition_list, mount_point)

    # Install base packages and configure system
    base_packages = dist.get_base_packages(conf)  # TODO: this function requires a wrapper
    dist.install_essentials_pkgs(base_packages, mount_point)  # TODO: this function requires a wrapper
    configure_system(conf, partition_list=partition_list, mount_point=mount_point)
    setup_bootloader(conf, partition_list, base_distribution)
    create_kod_user(mount_point)

    # === Proc packages
    repos, repo_packages = dist.proc_repos(conf, mount_point=mount_point)  # TODO: this function requires a wrapper
    packages_to_install, packages_to_remove = get_packages_to_install(conf)
    pending_to_install = get_pending_packages(packages_to_install)
    print("packages\n", packages_to_install)
    manage_packages(mount_point, repos, "install", pending_to_install, chroot=True)

    # === Proc services
    system_services_to_enable = get_services_to_enable(ctx, conf)
    print(f"Services to enable: {system_services_to_enable}")
    enable_services(system_services_to_enable, use_chroot=True)

    # === Proc users
    print("\n====== Creating users ======")
    proc_users(ctx, conf)

    # print("==== Deploying generation ====")
    store_packages_services(f"{mount_point}/kod/generations/0", packages_to_install, system_services_to_enable)
    dist.generale_package_lock(mount_point, f"{mount_point}/kod/generations/0")

    exec(f"umount -R {mount_point}")

    print("Done")
    exec(f"mount {root_partition} {mount_point}")
    exec(f"cp -r /root/kodos {mount_point}/store/root/")
    exec(f"umount {mount_point}")
    print(" Done installing KodOS")


@cli.command()
@click.option("-c", "--config", default=None, help="System configuration file")
@click.option("-n", "--new_generation", is_flag=True, help="Create a new generation")
@click.option("-u", "--update", is_flag=True, help="Update package versions")
def rebuild(config, new_generation=False, update=False):
    "Rebuild KodOS system installation"

    # stage = "rebuild"
    conf = load_config(config)
    base_distribution = conf.base_distribution
    base_distribution = "arch" if base_distribution is None else base_distribution
    print("Base distribution:", base_distribution)

    dist = set_base_distribution(base_distribution)

    print("========================================")

    # Get next generation number
    max_generation = get_max_generation()
    generation_id = int(max_generation) + 1

    with open("/.generation") as f:
        current_generation = int(f.readline().strip())
    print(f"{current_generation = }")

    # Load current installed packages and enabled services
    if os.path.isfile(f"/kod/generations/{current_generation}/installed_packages"):
        current_state_path = f"/kod/generations/{current_generation}"
    else:
        print("Missing installed packages information")
        return

    current_packages, current_services = load_packages_services(current_state_path)
    print(f"{current_packages = }")
    print(f"{current_services = }")

    boot_partition, root_partition = get_partition_devices(conf)

    next_state_path = f"/kod/generations/{generation_id}"
    exec(f"mkdir -p {next_state_path}")

    if new_generation:
        print("Creating a new generation")
        exec(f"btrfs subvolume snapshot / {next_state_path}/rootfs")
        use_chroot = True
        new_root_path = create_next_generation(boot_partition, root_partition, generation_id)
    else:
        # os._exit(0)
        exec("btrfs subvolume snapshot / /kod/current/old-rootfs")
        exec(f"cp /kod/generations/{current_generation}/installed_packages /kod/current/installed_packages")
        exec(f"cp /kod/generations/{current_generation}/enabled_services /kod/current/enabled_services")
        use_chroot = False
        new_root_path = "/"
        # exec("mount -o remount,rw /usr")

    ctx = Context(os.environ["USER"], mount_point=new_root_path, use_chroot=use_chroot)

    print("==========================================")
    print("==== Processing packages and services ====")

    current_repos = load_repos()
    repos, repo_packages = dist.proc_repos(conf, current_repos, update, mount_point=new_root_path)
    print("repo_packages\n", repo_packages)
    if repos is None:
        print("Missing repos information")
        return

    if update:
        print("Updating packages")
        dist.refresh_package_db(new_root_path, new_generation)  # TODO: this function requires a wrapper
        update_all_packages(new_root_path, new_generation, repos)

    # === Proc packages
    packages_to_install, packages_to_remove = get_packages_to_install(conf)
    print("packages\n", packages_to_install)
    kernel_package = packages_to_install["kernel"] or "linux"

    # Package filtering
    current_installed_packages = load_package_lock(current_state_path)
    new_packages_to_install, packages_to_remove, packages_to_update, hooks_to_run = get_packages_updates(
        dist,
        current_packages,
        packages_to_install,
        packages_to_remove,
        current_installed_packages,
        new_root_path,
    )

    # === Proc services
    next_services = get_services_to_enable(ctx, conf)

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
            except Exception:
                pass
                # print(f"Unable to remove {pkg}")

    if new_packages_to_install:
        print("Packages to install:", new_packages_to_install)
        manage_packages(new_root_path, repos, "install", new_packages_to_install, chroot=use_chroot)

    print("Running hooks")
    for hook in hooks_to_run:
        print(f"Running {hook}")
        hook()

    # System services
    print(f"Services to enable: {new_service_to_enable}")
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
    store_packages_services(next_state_path, packages_to_install, next_services)
    dist.generale_package_lock(new_root_path, next_state_path)

    partition_list = load_fstab("/")

    _kernel_file, kver = dist.get_kernel_file(
        new_root_path, package=kernel_package
    )  # TODO: this function requires a wrapper

    print("==== Deploying new generation ====")
    if new_generation:
        create_boot_entry(generation_id, partition_list, mount_point=new_root_path, kver=kver)
    else:
        # Move current updated rootfs to a new generation
        exec(f"mv /kod/generations/{current_generation}/rootfs /kod/generations/{generation_id}/")
        # Moving the current rootfs copy to the current generation path
        exec(f"mv /kod/current/old-rootfs /kod/generations/{current_generation}/rootfs")
        exec(f"mv /kod/current/installed_packages /kod/generations/{current_generation}/installed_packages")
        exec(f"mv /kod/current/enabled_services /kod/generations/{current_generation}/enabled_services")
        updated_partition_list = change_subvol(
            partition_list,
            subvol=f"generations/{generation_id}",
            mount_points=["/"],
        )
        generate_fstab(updated_partition_list, new_root_path)
        create_boot_entry(generation_id, updated_partition_list, mount_point=new_root_path, kver=kver)

    # Write generation number
    with open(f"{next_state_path}/rootfs/.generation", "w") as f:
        f.write(str(generation_id))

    if new_generation:
        for m in [
            "/boot",
            "/kod",
            "/home",
            "/root",
            "/var/log",
            "/var/tmp",
            "/var/cache",
            "/var/kod",
        ]:
            exec(f"umount {new_root_path}{m}")
        exec(f"umount {new_root_path}")
        exec(f"rm -rf {new_root_path}")

    # else:
    # exec("mount -o remount,ro /usr")

    print(f"Done. Generation {generation_id} created")


@cli.command()
@click.option("-c", "--config", default=None, help="System configuration file")
@click.option("--user", default=os.environ["USER"], help="User to rebuild config")
def rebuild_user(config, user=os.environ["USER"]):
    "Rebuild user configuration"
    # stage = "rebuild-user"
    ctx = Context(os.environ["USER"], mount_point="/", use_chroot=False, stage="rebuild-user")
    conf = load_config(config)
    users = conf.users
    info = users[user] if user in users else None
    print("========================================")

    # === Proc users
    if info:
        print("\n====== Processing users ======")

        dotfile_mngrs = user_dotfile_manager(info)
        user_configs_def = user_configs(user, info)

        proc_user_home(ctx, user, info)

        configure_user_dotfiles(ctx, user, user_configs_def, dotfile_mngrs)
        configure_user_scripts(ctx, user, user_configs_def)

        services_to_enable = user_services(user, info)
        print(f"User services to enable: {services_to_enable}")
        enable_user_services(ctx, user, services_to_enable)
    else:
        print(f"User {user} not found in configuration file")

    print("Done")


@cli.command()
@click.option("-p", "--package", default=None, help="Package(s) to install", multiple=True)
def shell(package=None):
    "Run shell"

    local_session = exec("schroot -c virtual_env -b", get_output=True).strip()
    print(f"{local_session=}")

    if package:
        print(f"{package=}")
        current_repos = load_repos()
        manage_packages_shell(current_repos, "install", package, chroot=local_session)

    exec(f"schroot -r -c {local_session} -p")
    exec(f"schroot -e -c {local_session}")


# # TODO: Update rollbackboot loader
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
