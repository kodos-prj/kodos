import glob
import json
import os
from pathlib import Path
from invoke import task
import lupa as lua

# from kod.archpkgs import follow_dependencies_to_install, init_index, install_pkg
from kod.debpkgs import follow_dependencies_to_install, init_index, install_pkg
# from kod.archpkgs import follow_dependencies_to_install, init_index, install_pkg

@task(help={"root":"root path for the installation"})
def init_root(c, root = "rootfs"):
    # ant hierarchy
    ant_dirs = ["kod/config", "kod/generations", "kod/pkgs"]
    c.config["run"]["env"]["KOD_ROOTFS"] = root 
    root_ant_dirs = [root + "/" + d for d in ant_dirs]
    c.run(f"mkdir -p {' '.join(root_ant_dirs)}")

    # File hierarchy
    fhs_dirs = ["usr/bin", "usr/lib", "usr/share", "etc", "proc", "tmp", "dev", "var", "run", "root" ]
    root_fhs_dirs = [root + "/" + d for d in fhs_dirs]
    c.run(f"mkdir -p {' '.join(root_fhs_dirs)}")

    c.run(f"cd {root} && ln -s usr/bin bin && ln -s usr/lib lib64")
    rootfs = c.config["run"]["env"]["KOD_ROOTFS"]
    print("Rootfs:", rootfs)

# ----------------------------------

def load_config(config_filename: str):
    luart = lua.LuaRuntime(unpack_returned_tuples=True)
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
        # pkg_path = "/workspaces/antos/demofs/ant/pkgspip freeee" / Path(pkg) / Path(desc['version'])
        gen_pkg_path = f"ant/generations/{generation}/{pkg}"
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
        # target = "ant/pkgs"
        # current_path = Path(f"ant/generations/current/{pkg}/").resolve()
        pkg_path = "ant/pkgs" / Path(pkg) / Path(desc["version"])
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
                else:
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


def report_install_scripts():
    pkg_path = Path(f"kod/generations/current/")  # {app_name}/current")
    # files = os.
    files = list(pkg_path.rglob("*/.INSTALL"))
    for f in files:
        print(f)


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

    if not Path("kod/config/catalog.json").exists():
        # Init catalog
        sources = conf.source
        init_index(c, sources)
    with open("kod/config/catalog.json") as f:
        catalog = json.load(f)

    created_dirs = []
    if Path("kod/generations/current/.created_dirs.txt").exists():
        with open("kod/generations/current/.created_dirs.txt") as f:
            created_dirs = f.read().split("\n")

    created_symlinks = []
    if Path("kod/generations/current/.created_symlink.txt").exists():
        with open("kod/generations/current/.created_symlink.txt") as f:
            created_symlinks = f.read().split("\n")

    generation = get_next_generation()
    c.run(f"mkdir -p kod/generations/{generation}")
    if generation > 1:
        c.run("rm kod/generations/current")
    c.run(f"cd kod/generations && ln -s {generation} current")

    pkg_list = list(conf.packages.values())
    print(pkg_list)

    all_pkgs_to_install = {}
    packages_to_install = {}
    for pkgname in pkg_list:
        print(pkgname)
        packages_to_install = get_list_of_packages_to_install(catalog, pkgname)
        print(packages_to_install.keys())
        all_pkgs_to_install.update(packages_to_install)

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
    # make_file_generation_links(all_pkgs_to_install, "ant/generations/current/.rootfs")
    make_file_generation_links(c, all_pkgs_to_install, "", absolute=absolute)

    # # TODO:
    # # Remove broken links (files are not used)
    # # Check for packages that have .INSTALL file

    print("************ ****** ***** *** ** *")
    for pkg, desc in all_pkgs_to_install.items():
        print(pkg, desc["version"])

    print("====== ==== == =")
    report_install_scripts()
    # -------

