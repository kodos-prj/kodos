"""Package management operations (Phase 2b refactored).

Handles package installation, updates, caching, and repository management.
Aggregation logic moved to Lua (src/lua/kod/sections/packages.lua).
"""

import json
import os
from typing import Any

from kod.common import exec, exec_chroot

# Re-exports for backward compatibility with tests
# Note: Aggregation helpers moved to Lua (src/lua/kod/sections/packages.lua)

# ============================================================================
# PRIVILEGE LEVEL MANAGEMENT
# ============================================================================


def _get_privilege_level(repo: dict[str, Any]) -> str:
    """
    Determine the privilege level for a repository.

    Checks for the new 'privilege_level' field first, then falls back to
    the legacy 'run_as_root' boolean for backward compatibility.

    Args:
        repo (dict): Repository configuration.

    Returns:
        str: One of "user", "sudo", or "root".

    Raises:
        ValueError: If privilege_level is invalid.
    """
    # New explicit privilege_level field
    if "privilege_level" in repo:
        level = repo["privilege_level"]
        valid_levels = ["user", "sudo", "root"]
        if level not in valid_levels:
            raise ValueError(
                f"Invalid privilege_level '{level}'. Must be one of {valid_levels}"
            )
        return level

    # Legacy boolean field conversion
    if "run_as_root" in repo:
        # run_as_root=False → user level (runuser context)
        # run_as_root=True → root level (full root)
        # ponytail: mapping legacy bool to new levels; retire run_as_root when all repos updated
        if repo["run_as_root"]:
            return "root"
        else:
            return "user"

    # Default: assume root (for backward compatibility)
    return "root"


def _build_privilege_command(base_cmd: str, privilege_level: str) -> str:
    """
    Build the command with appropriate privilege escalation.

    Args:
        base_cmd (str): The base command to execute.
        privilege_level (str): One of "user", "sudo", "root".

    Returns:
        str: The command with privilege escalation applied.

    Raises:
        ValueError: If privilege_level is invalid.
    """
    valid_levels = ["user", "sudo", "root"]
    if privilege_level not in valid_levels:
        raise ValueError(
            f"Invalid privilege_level '{privilege_level}'. Must be one of {valid_levels}"
        )

    if privilege_level == "user":
        # Run as unprivileged 'kod' user
        return f"runuser -u kod -- {base_cmd}"
    elif privilege_level == "sudo":
        # Run with sudo escalation
        return f"sudo {base_cmd}"
    else:  # root
        # Run as full root (no prefix needed)
        return base_cmd


# Remaining functions: state management, privilege handling, execution
# Aggregation moved to Lua (src/lua/kod/sections/packages.lua)


# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================


def get_packages_to_install(conf: Any) -> tuple[dict[str, list[str]], list[str]]:
    """
    Determine the packages to install based on the given configuration.

    Calls Lua's package aggregation to collect packages from all config sections
    (desktop, hardware, fonts, user programs, system packages). Also collects
    packages to exclude (e.g., gnome-tour from GNOME environment).

    Returns packages wrapped in a dict for compatibility with state storage.

    Args:
        conf (table): The configuration table containing details for package selection.

    Returns:
        tuple: A tuple containing two elements:
            - packages_to_install (dict): A dictionary with "packages" key listing
              all unique packages to be installed.
            - packages_to_remove (list): List of packages to exclude/remove
              (e.g., unwanted environment defaults).
    """
    from kod.bootstrap import _convert_to_lua_table
    from kod.lua_runtime import get_lua_runtime
    from kod.lua_utils import lua_table_to_python

    # Load Lua and call package aggregation
    lua = get_lua_runtime()
    result = lua.require("kod.sections.packages")
    # lupa.require() returns (module, filename) tuple; extract module
    packages_module = result[0] if isinstance(result, tuple) else result

    # Convert Python dict/object to Lua table to ensure proper iteration
    # This handles the case where load_config returns a Python dict
    conf_lua = _convert_to_lua_table(lua, conf)

    # Call Lua aggregation function with Lua table
    # Returns {packages={...}, excluded={...}}
    lua_result = packages_module.aggregate_packages(conf_lua)

    # Convert lupa.LuaTable to Python dict
    result_dict = lua_table_to_python(lua_result)

    # Extract packages and excluded lists
    packages_list = result_dict.get("packages", []) if isinstance(result_dict, dict) else []
    excluded_list = result_dict.get("excluded", []) if isinstance(result_dict, dict) else []

    # Wrap in dict matching original format
    packages_to_install = {
        "packages": packages_list,
        "kernel": "linux",  # Default kernel; can be overridden in config
    }

    packages_to_remove = excluded_list

    return packages_to_install, packages_to_remove


def load_repos() -> dict[str, Any] | None:
    """
    Load the repository configuration from the file /var/kod/repos.json.

    Returns a dictionary with the repository configuration, or None if the file
    does not exist or is not a valid JSON file.

    """
    try:
        with open("/var/kod/repos.json") as f:
            return json.load(f)
    except FileNotFoundError:
        # File doesn't exist yet (e.g., first install or repo config not written)
        return None
    except json.JSONDecodeError:
        # File exists but is invalid JSON
        return None


def update_all_packages(
    mount_point: str, new_generation: bool, repos: dict[str, Any]
) -> None:
    """
    Updates all packages in the system.

    Args:
        mount_point (str): The mount point of the chroot environment.
        new_generation (bool): If True, run pacman inside the chroot environment.
        repos (dict): A dictionary containing repository configurations and commands.
    """
    # Use the repo update entry for all the repos
    for repo, repo_desc in repos.items():
        if "update" in repo_desc:
            print(f"Updating {repo}")
            try:
                privilege_level = _get_privilege_level(repo_desc)
            except ValueError as e:
                print(f"Error: Invalid privilege level for repo '{repo}': {e}")
                continue

            cmd = repo_desc["update"]
            privileged_cmd = _build_privilege_command(cmd, privilege_level)

            if new_generation:
                exec_chroot(privileged_cmd, mount_point=mount_point)
            else:
                exec(privileged_cmd)


def get_pending_packages(packages_to_install: dict[str, list[str]]) -> list[str]:
    """
    Get the list of packages that are pending installation.

    Args:
        packages_to_install (dict): A dictionary containing the packages to install.
            The dictionary should have a single key: "packages", which is a list of
            package names.

    Returns:
        list: A list of package names that are pending installation.
    """
    pending_to_install = packages_to_install["packages"]
    return pending_to_install


def store_packages_services(
    state_path: str,
    packages_to_install: dict[str, list[str]],
    system_services: list[str],
) -> None:
    """
    Store the list of packages that are installed and the list of services that are enabled.

    Stores the list of packages that are installed in a JSON file and the list of services
    that are enabled in a plain text file. Uses atomic writes (temp + rename) to prevent
    corruption if process is interrupted.

    Args:
        state_path (str): The path to the state directory where the package and service
            information should be stored.
        packages_to_install (dict): A dictionary containing the packages to install.
            The dictionary should have a single key: "packages", which is a list of
            package names.
        system_services (list): A list of system services that are enabled.

    Raises:
        OSError: If state_path does not exist or is not writable
    """
    if not os.path.isdir(state_path):
        raise OSError(f"State path does not exist or is not a directory: {state_path}")

    # Write packages atomically (temp + rename)
    packages_json = json.dumps(packages_to_install, indent=2)
    packages_file = f"{state_path}/installed_packages"
    temp_packages = f"{state_path}/.tmp_packages_{os.getpid()}"
    try:
        with open(temp_packages, "w") as f:
            f.write(packages_json)
        os.rename(temp_packages, packages_file)
    except Exception as e:
        if os.path.exists(temp_packages):
            os.unlink(temp_packages)
        raise OSError(f"Failed to write packages atomically to {packages_file}: {e}")

    # Write services atomically (temp + rename)
    services_file = f"{state_path}/enabled_services"
    temp_services = f"{state_path}/.tmp_services_{os.getpid()}"
    try:
        with open(temp_services, "w") as f:
            f.write("\n".join(system_services))
        os.rename(temp_services, services_file)
    except Exception as e:
        if os.path.exists(temp_services):
            os.unlink(temp_services)
        raise OSError(f"Failed to write services atomically to {services_file}: {e}")


def load_package_lock(state_path: str) -> dict[str, str] | None:
    """
    Load the list of installed packages and their versions from a lock file.

    This function reads a file named `packages.lock` located at the provided
    `state_path`. Each line of the file should contain a package name followed
    by its version, separated by a space. The function parses the file and
    returns a dictionary mapping package names to their respective versions.

    Args:
        state_path (str): The path to the directory containing the `packages.lock` file.

    Returns:
        dict: A dictionary where keys are package names and values are their corresponding versions.
    """
    packages = {}
    with open(f"{state_path}/packages.lock") as f:
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue
            package, version = line.split(" ")
            packages[package] = version
    return packages


def get_packages_updates(
    dist: Any,
    current_packages: dict[str, Any],
    next_packages: dict[str, Any],
    remove_packages: list[str],
    current_installed_packages: list[str],
    mount_point: str,
) -> tuple[list[str], list[str], list[str], bool]:
    """
    Determine the packages to install, remove, and update, plus kernel update flag.

    This function compares the current and next package sets to decide which packages
    need to be installed, removed, or updated. It also determines if a kernel update is
    required and returns a flag indicating this.

    Args:
        current_packages (dict): A dictionary containing information about currently installed packages.
        next_packages (dict): A dictionary containing information about packages to be installed.
        remove_packages (list): A list of package names to be removed.
        current_installed_packages (dict): A dictionary mapping currently installed package names to their versions.
        mount_point (str): The mount point of the chroot environment.

    Returns:
        tuple: A tuple containing four elements:
            - packages_to_install (list): A list of package names that need to be installed.
            - packages_to_remove (list): A list of package names that need to be removed.
            - packages_to_update (list): A list of package names that need to be updated.
            - kernel_update_required (bool): True if kernel update is needed; system steps will be emitted by plan_rebuild.
    """

    packages_to_install = []
    packages_to_remove = []
    packages_to_update = []

    current_kernel = current_packages.get("kernel", "linux")
    next_kernel = next_packages.get("kernel", "linux")

    kernel_update_required = dist.kernel_update_required(
        current_kernel, next_kernel, current_installed_packages, mount_point
    )
    if kernel_update_required:
        packages_to_install += [next_kernel]

    current_pkgs = current_packages.get("packages", [])
    next_pkgs = next_packages.get("packages", [])

    remove_pkg = (set(current_pkgs) - set(next_pkgs)) | set(remove_packages)
    packages_to_remove += list(remove_pkg)

    added_pkgs = set(next_pkgs) - set(current_pkgs)
    packages_to_install += list(added_pkgs)

    # Find packages that exist in both current and next (potential updates)
    # This is currently an intersection of package names (not dict keys)
    if current_pkgs and next_pkgs:
        update_pkg = set(current_pkgs) & set(next_pkgs)
        packages_to_update += list(update_pkg)

    return (
        packages_to_install,
        packages_to_remove,
        packages_to_update,
        kernel_update_required,
    )


def manage_packages_shell(
    repos: dict[str, Any], action: str, list_of_packages: list[str], chroot: bool
) -> None:
    """Manage packages using schroot shell.

    Args:
        repos (dict): Repository configurations.
        action (str): Package action (install, remove, etc).
        list_of_packages (list): List of packages to manage.
        chroot (bool): Whether to use chroot.
    """
    pkgs_per_repo = {"official": []}
    for pkg in list_of_packages:
        if ":" in pkg:
            repo, pkg_name = pkg.split(":")
            if repo not in pkgs_per_repo:
                pkgs_per_repo[repo] = []
            pkgs_per_repo[repo].append(pkg_name)
        else:
            pkgs_per_repo["official"].append(pkg)

    print(f"{pkgs_per_repo = }")
    for repo, pkgs in pkgs_per_repo.items():
        print(repo, "->", pkgs)
        if len(pkgs) == 0:
            continue

        try:
            privilege_level = _get_privilege_level(repos[repo])
        except ValueError as e:
            print(f"Error: Invalid privilege level for repo '{repo}': {e}")
            continue

        cmd = f"{repos[repo][action]} {' '.join(pkgs)}"
        privileged_cmd = _build_privilege_command(cmd, privilege_level)

        if privilege_level == "root":
            # Use schroot with root
            exec(f"schroot -r -c {chroot} -u root -- {privileged_cmd}")
        else:
            # Use schroot without root escalation
            exec(f"schroot -r -c {chroot} -- {privileged_cmd}")


def load_packages_services(
    state_path: str,
) -> tuple[dict[str, list[str]] | None, list[str] | None]:
    """Load the list of packages and services from state.

    Reads system state from a directory containing installed packages and enabled
    services information. Used for rebuild operations to determine delta.

    Args:
        state_path: The path to the state directory where package and service
                    information is stored.

    Returns:
        A tuple containing:
        - packages (dict): A dictionary of installed packages by repository.
        - services (list): A list of system services that are enabled.
    """
    with open(f"{state_path}/installed_packages", "r") as f:
        packages = json.load(f)
    with open(f"{state_path}/enabled_services", "r") as f:
        services = [pkg.strip() for pkg in f.readlines() if pkg.strip()]
    return packages, services
