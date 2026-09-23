"""Main command-line interface for the KodOS system.

This module provides the primary CLI interface using Click framework for interacting
with KodOS functionality including installation, configuration, and system management.

@Author: Anatal Buss
@version 0.1
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import click

logger = logging.getLogger(__name__)

# from kod.arch import get_base_packages, get_kernel_file, install_essentials_pkgs, proc_repos, refresh_package_db
from kod.common import (
    exec,
    exec_chroot,
    exec_warn,
    set_debug,
    set_verbose,
    setup_chroot_mounts,
)
from kod.config.loader import load_config_lua
from kod.config.validator import validate_config
from kod.context import Context
from kod.system.boot import (
    create_boot_entry_hook,
    update_initramfs_hook,
    update_kernel_hook,
)
from kod.system.distro.factory import get_distro_module
from kod.system.generations import (
    change_subvol,
    create_next_generation,
    generate_fstab,
    get_max_generation,
    get_partition_devices,
    load_fstab,
)
from kod.system.packages import (
    get_packages_to_install,
    load_package_lock,
    load_packages_services,
    load_repos,
    manage_packages_shell,
    store_packages_services,
)
from kod.system.services import (
    get_services_to_enable,
)

# Shorthand: load_config returns Lua table (raw Lua config)
load_config = load_config_lua

# from kod.core import *


#####################################################################################################
@click.group()
@click.option("-d", "--debug", is_flag=True)
@click.option("-v", "--verbose", is_flag=True)
def cli(debug: bool, verbose: bool) -> None:
    set_debug(debug)
    set_verbose(verbose)


def _wrap_text(text: str, width: int = 76, indent: int = 0) -> str:
    """Wrap text to fit within width, with optional indentation."""
    indent_str = " " * indent
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        current_line = []
        current_length = indent
        for word in words:
            if current_length + len(word) + 1 > width and current_line:
                lines.append(indent_str + " ".join(current_line))
                current_line = [word]
                current_length = indent + len(word)
            else:
                current_line.append(word)
                current_length += len(word) + 1
        if current_line:
            lines.append(indent_str + " ".join(current_line))
    return "\n".join(lines)


def _validate_generation_id(generation_id: int) -> None:
    """Validate generation ID to prevent directory traversal attacks.
    
    Generation IDs must be simple non-negative integers to prevent
    path traversal via paths like "../../etc/passwd".
    
    Raises:
        ValueError: If generation_id is invalid
    """
    if not isinstance(generation_id, int) or generation_id < 0:
        raise ValueError(f"Invalid generation ID: {generation_id} (must be non-negative integer)")
    # Additional safety: ensure string representation has no path characters
    gen_str = str(generation_id)
    if not re.match(r'^\d+$', gen_str):
        raise ValueError(f"Invalid generation ID format: {gen_str}")


def _verify_unmount(mount_point: str, max_retries: int = 3) -> None:
    """Verify that a mount point is actually unmounted, with flush and retry.
    
    Lazy unmount (-l flag) can return success even if mounts are still busy.
    This function ensures data is flushed and verifies the unmount actually succeeded.
    
    Args:
        mount_point: Path to verify unmount
        max_retries: Number of retry attempts before raising error
    
    Raises:
        RuntimeError: If mount point remains mounted after retries
    """
    
    # Flush all file buffers to disk
    logger.info(f"Flushing buffers before verifying unmount of {mount_point}")
    os.sync()
    time.sleep(1)  # Give kernel time to process flush
    
    # Verify unmount with retries
    for attempt in range(max_retries):
        result = subprocess.run(
            ["mountpoint", "-q", mount_point],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode != 0:  # mountpoint -q returns 1 if not mounted
            logger.info(f"Successfully verified unmount of {mount_point} on attempt {attempt + 1}")
            return
        
        if attempt < max_retries - 1:
            logger.warning(f"Mount point {mount_point} still mounted, retrying... (attempt {attempt + 1}/{max_retries})")
            time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
    
    raise RuntimeError(f"Failed to unmount {mount_point} after {max_retries} attempts - data may be lost")



def _swap_generations_atomic(current_gen: int, new_gen: int) -> None:
    """Atomically swap generation rootfs directories with rollback on failure.
    
    This operation is critical for system stability. If any step fails,
    the rollback restores the previous generation so the system remains bootable.
    
    Operation:
    1. Validate all paths exist
    2. Create btrfs snapshot backup of current generation
    3. Move current rootfs → new generation dir
    4. Move old rootfs → current generation dir (from /kod/current)
    5. Move generation state files (installed_packages, enabled_services)
    6. On success: delete backup
    7. On failure: restore from backup
    
    Args:
        current_gen: Current generation number (the one to swap out)
        new_gen: New generation number (the one to activate)
    
    Raises:
        RuntimeError: If swap fails at any point
    """
    
    # Validate IDs
    _validate_generation_id(current_gen)
    _validate_generation_id(new_gen)
    
    current_rootfs = f"/kod/generations/{current_gen}/rootfs"
    new_gen_dir = f"/kod/generations/{new_gen}"
    old_rootfs = "/kod/current/old-rootfs"
    backup_path = f"/tmp/backup_gen{current_gen}_{int(time.time())}"
    
    # State files to move
    state_files = [
        ("installed_packages", "installed_packages"),
        ("enabled_services", "enabled_services"),
    ]
    
    # Step 1: Validate all sources exist
    for path in [current_rootfs, old_rootfs, new_gen_dir]:
        if not os.path.exists(path):
            raise RuntimeError(f"Swap failed: missing required path: {path}")
    
    for src_file, _ in state_files:
        if not os.path.exists(f"/kod/current/{src_file}"):
            raise RuntimeError(f"Swap failed: missing state file: /kod/current/{src_file}")
    
    try:
        # Step 2: Create backup via btrfs snapshot (atomic)
        # btrfs snapshot MUST work - if it fails, report the actual error
        try:
            result = subprocess.run(
                ["btrfs", "subvolume", "snapshot", current_rootfs, backup_path],
                check=False, capture_output=True, timeout=60
            )
            if result.returncode != 0:
                stderr = result.stderr.decode()
                raise RuntimeError(
                    f"btrfs subvolume snapshot failed (this is not a safe fallback scenario):\n"
                    f"  Command: btrfs subvolume snapshot {current_rootfs} {backup_path}\n"
                    f"  Error: {stderr}\n"
                    f"  Ensure btrfs is installed and the filesystem is healthy: btrfs filesystem show"
                )
        except Exception as e:
            raise RuntimeError(f"Failed to create backup: {e}")
        
        # Step 3: Move current rootfs to new generation
        try:
            os.rename(current_rootfs, f"{new_gen_dir}/rootfs")
        except Exception as e:
            raise RuntimeError(f"Failed to move current rootfs to {new_gen_dir}: {e}")
        
        # Step 4: Move old rootfs to current position
        try:
            os.rename(old_rootfs, current_rootfs)
        except Exception as e:
            # ROLLBACK: restore current rootfs from new generation
            try:
                os.rename(f"{new_gen_dir}/rootfs", current_rootfs)
            except Exception as rollback_e:
                logger.critical(f"CRITICAL: Failed to rollback after move failure: {rollback_e}")
            raise RuntimeError(f"Failed to move old rootfs to current: {e}")
        
        # Step 5: Move generation state files
        for src_file, dst_file in state_files:
            try:
                os.rename(f"/kod/current/{src_file}", f"/kod/generations/{current_gen}/{dst_file}")
            except Exception as e:
                # ROLLBACK: restore rootfs
                try:
                    os.rename(current_rootfs, old_rootfs)
                    os.rename(f"{new_gen_dir}/rootfs", current_rootfs)
                except Exception as rollback_e:
                    logger.critical(f"CRITICAL: Failed to rollback state file move: {rollback_e}")
                raise RuntimeError(f"Failed to move {src_file}: {e}")
        
        # Step 6: Success - cleanup backup
        try:
            if backup_path.endswith('.tar'):
                os.unlink(backup_path)
            else:
                subprocess.run(["rm", "-rf", backup_path], timeout=30)
        except Exception as e:
            logger.warning(f"Failed to cleanup backup {backup_path}: {e}")
        
        logger.info(f"Successfully swapped generations {current_gen} -> {new_gen}")
        
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Unexpected error during generation swap: {e}")




def _print_section_text(name: str, data: dict, level: int = 0) -> None:
    """Print section in readable text format with proper indentation."""
    indent = "  " * level
    
    if level == 0:
        # Top-level section header
        click.echo(name.upper())
        click.echo("=" * 60)
    
    # Print type and required
    click.echo(f"{indent}Type: {data.get('type', 'unknown')}")
    required = data.get('required', False)
    click.echo(f"{indent}Required: {'Yes' if required else 'No'}")
    click.echo()
    
    # Print description
    description = data.get('description', '')
    if description:
        click.echo(_wrap_text(description, width=76, indent=len(indent)))
        click.echo()
    
    # Print example
    example = data.get('example', '')
    if example:
        click.echo(f"{indent}Example:")
        for line in example.split('\n'):
            click.echo(f"{indent}  {line}")
        click.echo()
    
    # Print fields
    fields = data.get('fields', {})
    if fields:
        click.echo(f"{indent}Fields:")
        for field_name, field_data in fields.items():
            click.echo(f"{indent}  {field_name}:")
            field_indent = "    " * (level + 1)
            click.echo(f"{field_indent}Type: {field_data.get('type', 'unknown')}")
            
            field_required = field_data.get('required', False)
            click.echo(f"{field_indent}Required: {'Yes' if field_required else 'No'}")
            
            field_description = field_data.get('description', '')
            if field_description:
                click.echo(_wrap_text(field_description, width=76, indent=len(field_indent)))
            
            # Print field default if present
            if 'default' in field_data:
                click.echo(f"{field_indent}Default: {field_data['default']}")
            
            # Print field example if present
            if 'example' in field_data:
                click.echo(f"{field_indent}Example: {field_data['example']}")
            
            # Print enum (valid values) if present
            if 'enum' in field_data:
                click.echo(f"{field_indent}Valid values: {', '.join(str(v) for v in field_data['enum'])}")
            
            # Print subfields
            subfields = field_data.get('fields', {})
            if subfields:
                click.echo(f"{field_indent}Subfields:")
                for subfield_name, subfield_data in subfields.items():
                    click.echo(f"{field_indent}  {subfield_name}: {subfield_data.get('description', '')}")
            
            click.echo()
    
    click.echo()


@cli.group()
def config() -> None:
    "Configuration management"


@config.command(name="validate")
@click.option("-c", "--config", default=None, help="System configuration file or directory")
def config_validate(config: str | None) -> None:
    "Validate a configuration file before install/rebuild"
    try:
        conf = load_config_lua(config)
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)
    
    errors = validate_config(conf)
    if errors:
        print(f"❌ Configuration validation failed with {len(errors)} error(s):\n")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
        print()
        sys.exit(1)
    
    # Print summary
    print("✅ Configuration is valid")
    if conf:
        sections = ", ".join(sorted(conf.keys()))
        print(f"   Sections: {sections}")


@config.command(name="schema")
@click.option("--section", default=None, help="Show only this section (e.g., 'boot')")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def config_schema(section: str | None, format: str) -> None:
    "Display configuration schema with descriptions and field documentation."

    from kod.config.schema import get_lua_schema
    schema = get_lua_schema()

    # Validate section name if provided
    if section and section not in schema:
        click.echo(f"Error: Section '{section}' not found", err=True)
        click.echo(f"Valid sections: {', '.join(sorted(schema.keys()))}", err=True)
        sys.exit(1)

    # Determine which sections to display
    sections_to_display = {section: schema[section]} if section else schema
    
    if format == "json":
        # Output as JSON
        output = {k: v for k, v in sections_to_display.items()}
        click.echo(json.dumps(output, indent=2))
    else:
        # Output as readable text
        for sec_name in sorted(sections_to_display.keys()):
            sec_data = sections_to_display[sec_name]
            _print_section_text(sec_name, sec_data)


@config.command(name="init")
@click.option("--distro", type=click.Choice(["arch", "debian"]), default="arch",
              help="Target distribution")
@click.option("--output", type=click.Path(), default=None,
              help="Write to file (default: stdout)")
def config_init(distro: str, output: str | None) -> None:
    """Generate a starter configuration file with all sections documented."""
    from kod.config.template import generate_config_template
    
    template = generate_config_template(distro)
    
    if output:
        with open(output, 'w') as f:
            f.write(template)
        click.echo(f"Template written to {output}")
    else:
        click.echo(template)


# pkgs_installed = []
base_distribution = "arch"

##############################################################################


@cli.command()
@click.option("-c", "--config", default=None, help="System configuration file")
@click.option("-m", "--mount_point", default="/mnt", help="Mount point for install")
def install(config: str | None, mount_point: str) -> None:
    """Install KodOS based on configuration."""
    from kod.context import Context
    from kod.executor import StepError, execute_steps
    from kod.hooks import collect_hooks
    from kod.planner import build_plan, render_plan

    try:
        ctx_obj = Context(os.environ.get("USER", "root"), mount_point=mount_point, use_chroot=True, stage="install")
        conf = load_config(config)
        base_distribution = conf.base_distribution or "arch"
        dist = get_distro_module(base_distribution)
        
        print("-------------------------------")
        print(f"Base distribution: {base_distribution}")
        print(f"Mount point: {mount_point}")
        
        # Build and preview full install plan
        steps = build_plan(conf, dist, baseline="empty")
        print("\n=== Install Plan Preview ===\n")
        print(render_plan(steps, "empty", config))
        print(f"\nPlan contains {len(steps)} steps", file=sys.stderr)
        
        if not steps:
            print("❌ No install steps generated. Check configuration.", file=sys.stderr)
            sys.exit(1)
        
        # Setup execution environment
        env = {
            "mount_point": mount_point,
            "use_chroot": True,
            "stage": "install",
            "dist": dist,
            # Boot entry is a plan step (boot.lua) dispatched here; generation 0 for install.
            "kernel-update": lambda kernel, mp: update_kernel_hook(kernel, mp)(),
            "initramfs-update": lambda kernel, mp: update_initramfs_hook(kernel, mp)(),
            "boot-entry": lambda kernel, mp: create_boot_entry_hook(0, kernel, mp)(),
        }
        
        try:
            hooks_dict = collect_hooks(conf.users or {})
        except Exception as e:
            logger.warning(f"Failed to collect hooks: {e}")
            hooks_dict = {}
        
        # Execute plan (Lua runner when enabled; Python executor otherwise).
        # No mid-execution fallback: a StepError is a real step failure and
        # re-running the whole plan would double-execute partial work.
        print("\n=== Executing Install ===\n")
        results = execute_steps(steps, env, mount_point,
                                use_chroot=True, hooks=hooks_dict)
         
        # Check for critical failures (ignore on_error='warn' steps)
        failures = [r for r in results if not r.success and not r.is_warning]
        if failures:
            print(f"\n❌ Install failed at {len(failures)} step(s):", file=sys.stderr)
            for r in failures:
                print(f"  - {r.step.name}: {r.error}", file=sys.stderr)
            sys.exit(1)
        
        # Record generation 0 state BEFORE unmounting /mnt
        # This must happen while /mnt/kod/generations/0 is still accessible
        print("Recording generation 0 state...")
        state_path = f"{mount_point}/kod/generations/0"
        os.makedirs(state_path, exist_ok=True)
        
        # Ensure /kod/generations is properly permissioned for rebuild (owner+group only)
        # Use chmod via shell to ensure it applies to the mounted subvolume
        try:
            result = os.system(f"chmod 0o755 {mount_point}/kod/generations")
            if result != 0:
                logger.error(f"Failed to chmod /kod/generations: status {result}")
        except Exception as e:
            logger.warning(f"Failed to chmod /kod/generations: {e}")
        
        next_services = get_services_to_enable(ctx_obj, conf)
        packages_to_install, _packages_to_remove = get_packages_to_install(conf)
        
        print(f"DEBUG: state_path = {state_path}")
        print(f"DEBUG: packages_to_install keys: {packages_to_install.keys()}")
        
        try:
            store_packages_services(state_path, packages_to_install, next_services)
            print("DEBUG: store_packages_services succeeded")
            if os.path.exists(state_path):
                print(f"DEBUG: Files in {state_path}: {os.listdir(state_path)}")
            
            dist.generate_package_lock(mount_point, state_path)
            print("DEBUG: generate_package_lock succeeded")
            if os.path.exists(state_path):
                print(f"DEBUG: Files in {state_path} after lock: {os.listdir(state_path)}")
            print("Generation 0 state recorded successfully")
        except Exception as e:
            print(f"ERROR: Failed to record generation 0 state: {e}")
            logger.warning(f"Failed to record generation 0 state: {e}")
            import traceback
            traceback.print_exc()
        
        # Clean up chroot mounts (proc, sys, dev, dev/pts) that were set up during install
        # These must be unmounted before we can safely unmount /mnt
        # Use lazy unmount (-l) to handle busy mounts
        print("Cleaning up chroot mounts...")
        try:
            # First try regular unmount
            exec("umount -R /mnt 2>/dev/null || umount -lR /mnt 2>/dev/null || true")
            # Verify unmount succeeded and flush data
            try:
                _verify_unmount("/mnt", max_retries=3)
            except RuntimeError as e:
                logger.error(f"Unmount verification failed: {e}")
                # Don't exit - let install complete, but warn user
                print(f"⚠️  Warning: {e}", file=sys.stderr)
        except Exception as e:
            logger.warning(f"Failed to cleanup chroot mounts: {e}")

        print("\n✅ Install completed successfully")

    except StepError as e:
        print(f"❌ Step error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Install failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def _cleanup_failed_generation(generation_id: int, new_root_path: str) -> None:
    """Clean up a failed generation snapshot and metadata.
    
    Args:
        generation_id: The generation number to clean up
        new_root_path: The mount point of the new root (to unmount if needed)
    """
    try:
        # Unmount if still mounted
        if new_root_path != "/":
            try:
                exec_warn(f"umount -R {new_root_path}", "Failed to unmount generation")
                # Verify unmount succeeded
                _verify_unmount(new_root_path, max_retries=2)
            except Exception:
                pass
        
        # Remove the generation directory and its snapshots
        generation_path = f"/kod/generations/{generation_id}"
        try:
            exec_warn(f"btrfs subvolume delete {generation_path}/rootfs", "Failed to delete rootfs subvolume")
        except Exception:
            pass
        
        try:
            exec_warn(f"btrfs subvolume delete {generation_path}/boot", "Failed to delete boot subvolume")
        except Exception:
            pass
        
        try:
            exec_warn(f"rm -rf {generation_path}", "Failed to remove generation directory")
        except Exception:
            pass
        
        print(f"⚠️  Cleaned up failed generation {generation_id}")
    except Exception as e:
        print(f"⚠️  Warning: Failed to fully clean up generation {generation_id}: {e}")


def _load_current_state() -> tuple[str, dict, list, dict]:
    """Resolve current generation state read-only. Raises ClickException with hint."""
    try:
        with open("/.generation") as f:
            gen = int(f.readline().strip())
        state_path = f"/kod/generations/{gen}"
        if not Path(f"{state_path}/installed_packages").is_file():
            raise FileNotFoundError(state_path)
        current_packages, current_services = load_packages_services(state_path)
        installed_lock = (load_package_lock(state_path)
                          if Path(f"{state_path}/packages.lock").is_file() else {})
        return state_path, current_packages, current_services, installed_lock
    except (FileNotFoundError, OSError):
        raise click.ClickException(
            "No KodOS generation found on this system. "
            "Use --baseline empty for install previews."
        )


@cli.command()
@click.option("-c", "--config", default=None, help="System configuration file")
@click.option("--baseline", type=click.Choice(["empty", "current"]), default="current",
              help="State to diff against (default: current)")
def plan(config: str | None, baseline: str) -> None:
    "Print the execution plan; never executes"
    from kod.planner import build_plan, render_plan

    conf = load_config(config)
    base_distribution = conf.base_distribution
    base_distribution = "arch" if base_distribution is None else base_distribution
    dist = get_distro_module(base_distribution)

    kwargs: dict = {}
    if baseline == "current":
        _state_path, cur_pkgs, cur_svcs, cur_lock = _load_current_state()
        kwargs = {"current_packages": cur_pkgs, "current_services": cur_svcs,
                  "current_installed_packages": cur_lock}
    steps = build_plan(conf, dist, baseline=baseline, **kwargs)
    print(render_plan(steps, baseline, config))


@cli.command()
@click.option("-c", "--config", default=None, help="System configuration file")
@click.option("-n", "--new_generation", is_flag=True, help="Create a new generation")
@click.option("-u", "--update", is_flag=True, help="Update package versions")
@click.option("--dry-run", is_flag=True, help="Print the plan; do not execute")
def rebuild(config: str | None, new_generation: bool = False, update: bool = False,
            dry_run: bool = False) -> None:
    "Rebuild KodOS system installation"

    from kod.executor import execute_steps
    from kod.hooks import collect_hooks
    from kod.planner import build_plan, render_plan

    # stage = "rebuild"
    conf = load_config(config)
    base_distribution = conf.base_distribution
    base_distribution = "arch" if base_distribution is None else base_distribution
    print("Base distribution:", base_distribution)

    dist = get_distro_module(base_distribution)

    if dry_run:
        _state_path, cur_pkgs, cur_svcs, cur_lock = _load_current_state()
        steps = build_plan(conf, dist, baseline="current", current_packages=cur_pkgs,
                           current_services=cur_svcs, current_installed_packages=cur_lock,
                           update=update)
        print(render_plan(steps, "current", config))
        return

    print("========================================")

    # === Generation bookkeeping (unchanged) ===
    max_generation = get_max_generation()
    generation_id = int(max_generation) + 1
    
    # Validate generation ID to prevent directory traversal
    try:
        _validate_generation_id(generation_id)
    except ValueError as e:
        print(f"❌ Invalid generation ID: {e}", file=sys.stderr)
        sys.exit(1)

    with open("/.generation") as f:
     current_generation = int(f.readline().strip())
     print(f"{current_generation = }")
 
     # Load current installed packages and enabled services
     packages_file = Path(f"/kod/generations/{current_generation}/installed_packages")
     if packages_file.is_file():
         current_state_path = f"/kod/generations/{current_generation}"
     else:
         print(f"❌ Missing installed packages information at {packages_file}", file=sys.stderr)
         print("   Generation 0 state should have been recorded during install.", file=sys.stderr)
         print("   If this appears after a fresh install, the install may have failed silently.", file=sys.stderr)
         sys.exit(1)
 
     current_packages, current_services = load_packages_services(current_state_path)
    print(f"{current_packages = }")
    print(f"{current_services = }")

    boot_partition, root_partition = get_partition_devices(conf)

    next_state_path = f"/kod/generations/{generation_id}"
    new_root_path = None
    use_chroot = False
    
    try:
        exec(f"mkdir -p {next_state_path}")

        if new_generation:
            print("Creating a new generation")
            exec(f"btrfs subvolume snapshot / {next_state_path}/rootfs")
            use_chroot = True
            new_root_path = create_next_generation(boot_partition, root_partition, generation_id)
            # Setup pseudo-filesystems in the new generation for chroot operations
            setup_chroot_mounts(new_root_path)
        else:
            exec("btrfs subvolume snapshot / /kod/current/old-rootfs")
            exec(f"cp /kod/generations/{current_generation}/installed_packages /kod/current/installed_packages")
            exec(f"cp /kod/generations/{current_generation}/enabled_services /kod/current/enabled_services")
            use_chroot = False
            new_root_path = "/"

        ctx = Context(os.environ["USER"], mount_point=new_root_path, use_chroot=use_chroot)

        print("==========================================")
        print("==== Processing packages and services ====")

        # Ensure kod user exists for AUR helper builds (before proc_repos)
        # The kod user is needed if any repos have AUR packages to build.
        # It should persist on the system once created.
        has_aur_repos = any(
            "build" in repo_desc
            for repo_desc in (conf.repos or {}).values()
        )
        
        if has_aur_repos:
            # Create kod user with NOPASSWD sudo if we need to build AUR packages
            try:
                if new_generation:
                    # For new generation: create inside chroot
                    exec_chroot(
                        "useradd -m -r -G wheel -s /bin/bash -d /var/kod/.home kod 2>/dev/null || true",
                        mount_point=new_root_path
                    )
                    exec_chroot(
                        "mkdir -p /etc/sudoers.d && echo 'kod ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/kod",
                        mount_point=new_root_path
                    )
                else:
                    # For current system: create on host (requires root)
                    exec("useradd -m -r -G wheel -s /bin/bash -d /var/kod/.home kod 2>/dev/null || true")
                    exec("mkdir -p /etc/sudoers.d && echo 'kod ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/kod")
            except Exception as e:
                # Non-critical if user creation fails (user may already exist or requires root)
                print(f"Warning: Could not ensure kod user: {e}")

        # === Proc repos (unchanged; feeds manage_packages_shell) ===
        current_repos = load_repos()
        repos, repo_packages = dist.proc_repos(conf, current_repos, update, mount_point=new_root_path)
        print("repo_packages\n", repo_packages)
        if repos is None:
            print("Missing repos information")
            raise ValueError("Failed to process repositories")

        if update:
            print("Updating packages")
            dist.refresh_package_db(new_root_path, new_generation)
            # Full package update now happens as a plan step (system/update-packages)

        # === Build plan ===
        current_installed_packages = load_package_lock(current_state_path)
        steps = build_plan(
            conf, dist, baseline="current",
            current_packages=current_packages,
            current_services=current_services,
            current_installed_packages=current_installed_packages,
            update=update,
            new_generation=new_generation
        )

        # === Setup executor environment ===
        env = {
            "mount_point": new_root_path,
            "repos": repos,
            "generation_id": generation_id,
            "use_chroot": use_chroot,
            # Executor dispatches system steps by name (see executor.py)
            "kernel-update": lambda kernel, mp: update_kernel_hook(kernel, mp)(),
            "initramfs-update": lambda kernel, mp: update_initramfs_hook(kernel, mp)(),
            "boot-entry": lambda kernel, mp: create_boot_entry_hook(generation_id, kernel, mp)(),
        }

        # Collect hooks from program definitions
        try:
            hooks_dict = collect_hooks(conf.users if conf.users else {})
        except Exception as e:
            import logging
            logging.warning(f"Failed to collect hooks: {e}")
            hooks_dict = {}

        # === Execute plan (Lua runner) ===
        print("================== Executing plan ==================")
        results = execute_steps(steps, env, new_root_path, use_chroot,
                                repos=repos, hooks=hooks_dict)

        # Check for failures
        for result in results:
            if not result.success:
                print(f"⚠️  Step '{result.step.name}' failed (non-aborting): {result.error}")

        # === Finalization (unchanged structure) ===
        next_services = get_services_to_enable(ctx, conf)
        packages_to_install, _packages_to_remove = get_packages_to_install(conf)
        store_packages_services(next_state_path, packages_to_install, next_services)
        dist.generate_package_lock(new_root_path, next_state_path)

        partition_list = load_fstab("/")

        print("==== Deploying new generation ====")
        # The boot entry is written by the boot-entry plan step during execute.
        if not new_generation:
            # Atomically swap generations with rollback on failure
            try:
                _swap_generations_atomic(current_generation, generation_id)
            except RuntimeError as e:
                print(f"❌ Failed to swap generations: {e}", file=sys.stderr)
                sys.exit(1)
            
            # Update boot configuration
            partition_list = load_fstab("/")
            updated_partition_list = change_subvol(
                partition_list,
                subvol=f"generations/{generation_id}",
                mount_points=["/"],
            )
            generate_fstab(updated_partition_list, new_root_path)

        # Write generation number
        with open(f"{next_state_path}/rootfs/.generation", "w") as f:
            f.write(str(generation_id))

        if new_generation:
            exec(f"umount -R {new_root_path}")

        print(f"✅ Done. Generation {generation_id} created")
        
    except Exception as e:
        print(f"❌ Rebuild failed: {e}", file=sys.stderr)
        print(f"❌ Rolling back generation {generation_id}...", file=sys.stderr)
        _cleanup_failed_generation(generation_id, new_root_path if new_root_path else "/")
        sys.exit(1)


@cli.command()
@click.option("-c", "--config", default=None, help="System configuration file")
@click.option("--user", default=os.environ["USER"], help="User to rebuild config")
def rebuild_user(config: str | None, user: str = os.environ["USER"]) -> None:
    """Rebuild user configuration using Lua planner system.
    
    Generates and executes a plan for user dotfiles, home directory setup,
    and service configuration from the Lua sections (users, dotfiles, services).
    """
    from kod.executor import StepError, execute_steps
    from kod.hooks import collect_hooks
    from kod.planner import build_plan, render_plan
    
    try:
        Context(os.environ["USER"], mount_point="/", use_chroot=False, stage="rebuild-user")
        conf = load_config(config)
        
        if not conf.users or user not in conf.users:
            print(f"User {user} not found in configuration file")
            return
        
        print("=" * 50)
        print(f"Rebuilding user: {user}")
        print("=" * 50)
        
        # Build full plan and filter to user-specific steps
        # The Lua sections (users.lua, dotfiles.lua, services.lua) will emit
        # steps filtered by user. We execute on current system (baseline="current").
        steps = build_plan(conf, baseline="current", new_generation=False)
        
        # Filter steps to only those for this specific user
        user_steps = [s for s in steps if s.get("user") == user or 
                                           f"_{user}_" in s.get("name", "") or
                                           s.get("name", "").endswith(f"_{user}")]
        
        if not user_steps:
            print(f"No configuration steps found for user {user}")
            return
        
        print(f"\n=== User Rebuild Plan for {user} ===\n")
        print(render_plan(user_steps, "current", config))
        
        # Setup execution environment
        env = {
            "mount_point": "/",
            "use_chroot": False,
            "stage": "rebuild-user",
            "dist": None,
        }
        
        try:
            hooks_dict = collect_hooks(conf.users or {})
        except Exception as e:
            exec_warn(f"Failed to collect hooks: {e}", "Hook collection failed, continuing without hooks")
            hooks_dict = {}
        
        # Execute user-specific plan
        print("\n=== Executing User Rebuild ===\n")
        execute_steps(user_steps, env, mount_point="/",
                                use_chroot=False, hooks=hooks_dict)
        
        print(f"\n✅ User {user} rebuild completed")
        
    except StepError as e:
        print(f"\n❌ Step failed: {e}")
        raise SystemExit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise SystemExit(1)


@cli.command()
@click.option("-p", "--package", default=None, help="Package(s) to install", multiple=True)
def shell(package: tuple[str, ...] | None = None) -> None:
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
