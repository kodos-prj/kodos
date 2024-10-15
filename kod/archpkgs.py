# Arch linux related functions

# def get_mirror_url(source, repo):
#     print(repo, source)
#     # source = SimpleNamespace(**source)
#     return f"{source.url}/{repo}/os/{source.arch}/"

# Process Arch package descriptions
import glob
import json
import os
from pathlib import Path
from pprint import pprint
import re


def get_desc(desc):
    sections = desc.split("\n\n")
    desc_dict = {}
    for sec in sections:
        items = sec.split("\n")
        name = items[0].replace("%", "").lower()
        desc_dict[name] = items[1] if len(items) == 2 else items[1:]
    return desc_dict


def get_file(c, repo_url, filename, target):
    # response = requests.get(repo_url + filename)
    c.run(f"curl -# {repo_url}{filename} -o {target}/{filename}")
    # return response.content


# Generate a package catalog from Arch packages
def generate_index(c, source, repo):
    repo_url = f"{source.url}/{repo}/os/{source.arch}/"
    db_filename = f"{repo}.db.tar.gz"
    print(f"Downloading {db_filename}")
    target = "tmp/index"
    c.run(f"mkdir -p {target}")
    c.run(f"curl -# {repo_url}{db_filename} -o tmp/{db_filename}")
    c.run(f"tar xzf tmp/{db_filename} -C {target}")

    packages_desc = glob.glob(f"{target}/*")
    catalog = {}
    for pkg in packages_desc:
        print(pkg)
        with open(f"{pkg}/desc") as fdesc:
            raw_desc = fdesc.read()
            desc = get_desc(raw_desc)
            if desc:
                desc["repo"] = repo
                catalog[desc["name"]] = desc
    c.run(f"rm -rf tmp/{db_filename}")
    c.run(f"rm -rf {target}")
    print(catalog)
    return catalog


# Uses Arch index for each repo to get the list of packages
def init_index(c, source):
    # List of Arch repos (e.g., core, extra, community)
    repos = source.repo.values()
    # Unified catalog
    catalog = {}
    for repo in repos:
        # Process the downloaded index
        repo_catalog = generate_index(c, source, repo)
        catalog.update(repo_catalog)
    # Write unified catalog to disk
    with open("kod/config/catalog.json", "w") as f:
        json.dump(catalog, f, indent=4)
    providers = get_providers(catalog)
    with open("kod/config/providers.json", "w") as f:
        json.dump(providers, f, indent=4)

def get_providers(catalog):
    providers = {}
    for pkg,desc in catalog.items():
        if "provides" in desc:
            # print("---->",pkg, desc["provides"])
            provider = desc["provides"]
            if isinstance(provider,str):
                provider = [provider]
            for p in provider:
                if p != pkg:            
                    if p not in providers:
                        providers[p] = []
                    if pkg not in providers[p]:
                        providers[p].append(pkg)
    return providers

# Download a package from a mirror, open it, and extract it to the target directory
def install_pkg(c, repo_url, pkg_desc, target_gen):
    target = "kod/pkgs"
    filename = pkg_desc["filename"]
    print("---------------------------")
    print(filename)
    app_name = pkg_desc["name"]
    app_version = pkg_desc["version"]

    install_path = Path(f"{target}/{app_name}/{app_version}")
    # current_path = Path(f"{target}/{app_name}/current")

    if not os.path.isdir(install_path):
        # get_file(c, repo_url, filename, "tmp")
        c.run(f"curl -# {repo_url}{filename} -o tmp/{filename}")
        c.run(f"zstd -d --rm tmp/{filename} -o tmp/pkg.tar")

        print("installing", install_path)
        c.run(f"mkdir -p {install_path}")
        c.run(f"tar xf tmp/pkg.tar -C {install_path}")
        c.run("rm tmp/pkg.tar")
        # link current
        c.run(f"cd {target}/{app_name} && ln -s -f {app_version} current")

    else:
        print(f"{install_path} already installed")


packages_to_skip = ["filesystem", "pacman", "archlinux-keyring"]

def follow_dependencies_to_install(catalog, providers, pkg_name, packages_to_install):
    print(" >>", pkg_name)
    if pkg_name in packages_to_skip:
        print("**** Skipping", pkg_name)
        return packages_to_install
    if pkg_name not in packages_to_install:
        print(pkg_name, "not in packages_to_install")
        if pkg_name in catalog:
            desc = catalog[pkg_name]
            print("\n---------------\n",pkg_name,desc['version'])
            # pprint(desc)
            libdepend = []
            pkgdepend = []
            depends = desc["depends"] if "depends" in desc else []
            if isinstance(depends, str):
                depends = [depends]
            # print(f"{depends = }")
            for line in depends:
                if re.match(r"^([^=]+)=(.*)", line):
                    libdepend.append(line)
                else:
                    pkgdepend.append(line)
            # libdepend = [line for line in desc["depends"] if re.match(r"^([^=]+)=(.*)", line)]
            # print(f"{pkgdepend = }")
            dependencies = pkgdepend
            # print(f"{libdepend = }")
            for lib in libdepend:
                if lib in providers:
                    for p in providers[lib]:
                        dependencies += [p]
                name,ver = re.split("=|>=|>=|<|<=", lib)
                if name[-3:] != ".so":
                    dependencies += [name]
            print(f"{dependencies = }")

            packages_to_install[pkg_name] = desc

            for dep in dependencies:
                packages_to_install.update(
                    follow_dependencies_to_install(catalog, providers, dep, packages_to_install)
                )
    else:
        print(pkg_name, "already in packages_to_install")

    return packages_to_install
