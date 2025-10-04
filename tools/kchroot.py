#!/usr/bin/env python3
"""
Standalone Python implementation of kchroot.

This is a complete rewrite of the bash arch-chroot script in Python,
providing the same functionality without any external dependencies.
"""

import os
import sys
import argparse
import subprocess
import atexit
from pathlib import Path
from typing import List, Optional


class KChrootError(Exception):
    """Exception raised when kchroot operations fail."""

    pass


class KChroot:
    """Standalone implementation of kchroot functionality."""

    def __init__(self):
        self.active_mounts: List[str] = []
        self.active_lazy_mounts: List[str] = []
        self.active_files: List[str] = []
        self.unshare_mode = False

    def error(self, msg: str, *args) -> None:
        """Print error message to stderr."""
        print(f"==> ERROR: {msg % args}", file=sys.stderr)

    def warning(self, msg: str, *args) -> None:
        """Print warning message to stderr."""
        print(f"==> WARNING: {msg % args}", file=sys.stderr)

    def msg(self, msg: str, *args) -> None:
        """Print info message to stdout."""
        print(f"==> {msg % args}")

    def die(self, msg: str, *args) -> None:
        """Print error and exit."""
        self.error(msg, *args)
        sys.exit(1)

    def run_command(self, cmd: List[str], check: bool = True) -> Optional[subprocess.CompletedProcess]:
        """Run a command with optional error checking."""
        try:
            return subprocess.run(cmd, check=check, capture_output=False)
        except subprocess.CalledProcessError:
            if check:
                self.die("Command failed: %s", " ".join(cmd))
            return None

    def chroot_add_mount(self, source: str, target: str, *mount_args) -> bool:
        """Add a mount and track it for cleanup."""
        cmd = ["mount"] + list(mount_args) + [source, target]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            self.active_mounts.insert(0, target)
            return True
        except subprocess.CalledProcessError:
            return False

    def chroot_add_mount_lazy(self, source: str, target: str, *mount_args) -> bool:
        """Add a lazy mount and track it for cleanup."""
        cmd = ["mount"] + list(mount_args) + [source, target]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            self.active_lazy_mounts.insert(0, target)
            return True
        except subprocess.CalledProcessError:
            return False

    def chroot_maybe_add_mount(self, condition: str, source: str, target: str, *mount_args) -> bool:
        """Conditionally add a mount based on a condition."""
        # Simple condition evaluation for directory existence
        if condition.startswith("os.path.exists(") and condition.endswith(")"):
            path = condition[15:-1].strip("'\"")
            if os.path.exists(path):
                return self.chroot_add_mount(source, target, *mount_args)
        return True

    def chroot_bind_device(self, source: str, target: str) -> bool:
        """Bind mount a device file."""
        try:
            Path(target).touch()
            self.active_files.insert(0, target)
            return self.chroot_add_mount(source, target, "--bind")
        except Exception:
            return False

    def chroot_add_link(self, source: str, target: str) -> bool:
        """Create a symbolic link and track it for cleanup."""
        try:
            if Path(target).exists():
                os.unlink(target)
            os.symlink(source, target)
            self.active_files.insert(0, target)
            return True
        except Exception:
            return False

    def chroot_setup(self, chrootdir: str) -> bool:
        """Set up the chroot environment with necessary mounts."""
        self.active_mounts = []
        atexit.register(self.chroot_teardown)

        return (
            self.chroot_add_mount("proc", f"{chrootdir}/proc", "-t", "proc", "-o", "nosuid,noexec,nodev")
            and self.chroot_add_mount("sys", f"{chrootdir}/sys", "-t", "sysfs", "-o", "nosuid,noexec,nodev,ro")
            and self.chroot_maybe_add_mount(
                f"os.path.exists('{chrootdir}/sys/firmware/efi/efivars')",
                "efivarfs",
                f"{chrootdir}/sys/firmware/efi/efivars",
                "-t",
                "efivarfs",
                "-o",
                "nosuid,noexec,nodev",
            )
            and self.chroot_add_mount("udev", f"{chrootdir}/dev", "-t", "devtmpfs", "-o", "mode=0755,nosuid")
            and self.chroot_add_mount(
                "devpts", f"{chrootdir}/dev/pts", "-t", "devpts", "-o", "mode=0620,gid=5,nosuid,noexec"
            )
            and self.chroot_add_mount("shm", f"{chrootdir}/dev/shm", "-t", "tmpfs", "-o", "mode=1777,nosuid,nodev")
            and self.chroot_add_mount("run", f"{chrootdir}/run", "-t", "tmpfs", "-o", "nosuid,nodev,mode=0755")
            and self.chroot_add_mount(
                "tmp", f"{chrootdir}/tmp", "-t", "tmpfs", "-o", "mode=1777,strictatime,nodev,nosuid"
            )
        )

    def unshare_setup(self, chrootdir: str) -> bool:
        """Set up the unshare chroot environment."""
        self.active_mounts = []
        self.active_lazy_mounts = []
        self.active_files = []
        atexit.register(self.unshare_teardown)

        return (
            self.chroot_add_mount_lazy(chrootdir, chrootdir, "--bind")
            and self.chroot_add_mount("proc", f"{chrootdir}/proc", "-t", "proc", "-o", "nosuid,noexec,nodev")
            and self.chroot_add_mount_lazy("/sys", f"{chrootdir}/sys", "--rbind")
            and self.chroot_add_link(f"{chrootdir}/proc/self/fd", f"{chrootdir}/dev/fd")
            and self.chroot_add_link(f"{chrootdir}/proc/self/fd/0", f"{chrootdir}/dev/stdin")
            and self.chroot_add_link(f"{chrootdir}/proc/self/fd/1", f"{chrootdir}/dev/stdout")
            and self.chroot_add_link(f"{chrootdir}/proc/self/fd/2", f"{chrootdir}/dev/stderr")
            and self.chroot_bind_device("/dev/full", f"{chrootdir}/dev/full")
            and self.chroot_bind_device("/dev/null", f"{chrootdir}/dev/null")
            and self.chroot_bind_device("/dev/random", f"{chrootdir}/dev/random")
            and self.chroot_bind_device("/dev/tty", f"{chrootdir}/dev/tty")
            and self.chroot_bind_device("/dev/urandom", f"{chrootdir}/dev/urandom")
            and self.chroot_bind_device("/dev/zero", f"{chrootdir}/dev/zero")
            and self.chroot_add_mount("run", f"{chrootdir}/run", "-t", "tmpfs", "-o", "nosuid,nodev,mode=0755")
            and self.chroot_add_mount(
                "tmp", f"{chrootdir}/tmp", "-t", "tmpfs", "-o", "mode=1777,strictatime,nodev,nosuid"
            )
        )

    def chroot_teardown(self) -> None:
        """Clean up regular mounts."""
        if self.active_mounts:
            for mount in self.active_mounts:
                try:
                    subprocess.run(["umount", mount], check=False, capture_output=True)
                except Exception:
                    pass
        self.active_mounts.clear()

    def unshare_teardown(self) -> None:
        """Clean up unshare mounts and files."""
        self.chroot_teardown()

        if self.active_lazy_mounts:
            for mount in self.active_lazy_mounts:
                try:
                    subprocess.run(["umount", "--lazy", mount], check=False, capture_output=True)
                except Exception:
                    pass
        self.active_lazy_mounts.clear()

        if self.active_files:
            for file_path in self.active_files:
                try:
                    os.unlink(file_path)
                except Exception:
                    pass
        self.active_files.clear()

    def resolve_link(self, target: str, root: Optional[str] = None) -> str:
        """Resolve symbolic links within a root directory."""
        if root and not root.endswith("/"):
            root += "/"

        while os.path.islink(target):
            target = os.path.realpath(target)
            if root and not target.startswith(root):
                target = root + target.lstrip("/")

        return target

    def chroot_add_resolv_conf(self, chrootdir: str) -> bool:
        """Set up resolv.conf in the chroot."""
        src = self.resolve_link("/etc/resolv.conf")
        dest = self.resolve_link(f"{chrootdir}/etc/resolv.conf", chrootdir)

        # If we don't have a source resolv.conf file, there's nothing useful we can do
        if not os.path.exists(src):
            return True

        if not os.path.exists(dest):
            # Case 1: No resolv.conf in chroot, not concerned with DNS
            if dest == f"{chrootdir}/etc/resolv.conf":
                return True

            # Case 2: Broken link, create dummy file
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                Path(dest).touch()
            except Exception:
                return False

        return self.chroot_add_mount(src, dest, "--bind")

    def is_mountpoint(self, path: str) -> bool:
        """Check if a path is a mountpoint."""
        try:
            result = subprocess.run(["mountpoint", "-q", path], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False

    def kchroot(self, chrootdir: str, args: List[str], userspec: Optional[str] = None) -> None:
        """Execute the kchroot functionality."""
        if os.geteuid() != 0:
            self.die("This script must be run with root privileges")

        if not os.path.isdir(chrootdir):
            self.die("Can't create chroot on non-directory %s", chrootdir)

        setup_func = self.unshare_setup if self.unshare_mode else self.chroot_setup
        if not setup_func(chrootdir):
            self.die("failed to setup chroot %s", chrootdir)

        if not self.chroot_add_resolv_conf(chrootdir):
            self.die("failed to setup resolv.conf")

        if not self.is_mountpoint(chrootdir):
            self.warning("%s is not a mountpoint. This may have undesirable side effects.", chrootdir)

        chroot_args = ["chroot"]
        if userspec:
            chroot_args.extend(["--userspec", userspec])
        chroot_args.extend(["--", chrootdir])
        chroot_args.extend(args if args else ["/bin/bash"])

        env = os.environ.copy()
        env["SHELL"] = "/bin/bash"

        if self.unshare_mode:
            unshare_cmd = [
                "unshare",
                "--fork",
                "--pid",
                "--mount",
                "--map-auto",
                "--map-root-user",
                "--setuid",
                "0",
                "--setgid",
                "0",
            ]
            unshare_cmd.extend(chroot_args)
            subprocess.run(unshare_cmd, env=env)
        else:
            pid_unshare_cmd = ["unshare", "--fork", "--pid"]
            pid_unshare_cmd.extend(chroot_args)
            subprocess.run(pid_unshare_cmd, env=env)


def kchroot(
    chrootdir: str, args: Optional[List[str]] = None, userspec: Optional[str] = None, unshare: bool = False
) -> None:
    """Standalone kchroot function for external use."""
    chroot = KChroot()
    chroot.unshare_mode = unshare
    chroot.kchroot(chrootdir, args or [], userspec)


def main():
    """Main entry point for the script."""
    # Handle the case where command arguments might start with dashes
    # by manually parsing the arguments

    args = sys.argv[1:]
    chrootdir = None
    command_args = []
    unshare_mode = False
    userspec = None

    i = 0
    while i < len(args):
        arg = args[i]

        if arg in ["-h", "--help"]:
            # Show help and exit
            parser = argparse.ArgumentParser(
                description="kchroot - Enhanced chroot command with proper setup",
                formatter_class=argparse.RawDescriptionHelpFormatter,
                epilog="""If 'command' is unspecified, kchroot will launch /bin/bash.

Note that when using kchroot, the target chroot directory *should* be a
mountpoint. This ensures that tools such as pacman(8) or findmnt(8) have an
accurate hierarchy of the mounted filesystems within the chroot.

If your chroot target is not a mountpoint, you can bind mount the directory on
itself to make it a mountpoint, i.e. 'mount --bind /your/chroot /your/chroot'.""",
            )
            parser.add_argument("-N", "--unshare", action="store_true", help="Run in unshare mode as a regular user")
            parser.add_argument(
                "-u", "--userspec", metavar="USER[:GROUP]", help="Specify non-root user and optional group to use"
            )
            parser.add_argument("chrootdir", help="Target chroot directory")
            parser.add_argument("command", nargs="*", help="Command and arguments to run in chroot")
            parser.print_help()
            sys.exit(0)
        elif arg in ["-N", "--unshare"]:
            unshare_mode = True
            i += 1
        elif arg in ["-u", "--userspec"]:
            userspec = args[i + 1] if i + 1 < len(args) else None
            i += 2
        elif arg.startswith("-"):
            print(f"Error: Unknown option '{arg}'", file=sys.stderr)
            print("Use -h or --help for usage information", file=sys.stderr)
            sys.exit(1)
        else:
            # This should be the chrootdir, everything after is command
            chrootdir = arg
            command_args = args[i + 1 :]
            break

    if chrootdir is None:
        print("Error: Missing required argument 'chrootdir'", file=sys.stderr)
        print("Use -h or --help for usage information", file=sys.stderr)
        sys.exit(1)

    chroot = KChroot()
    chroot.unshare_mode = unshare_mode

    try:
        chroot.kchroot(chrootdir, command_args, userspec)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        chroot.die("Unexpected error: %s", str(e))


if __name__ == "__main__":
    main()
