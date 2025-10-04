#!/usr/bin/env python3

import os
import subprocess
import atexit
from typing import List, Optional, Union


class ChrootError(Exception):
    pass


class Chroot:
    def __init__(self):
        self.active_mounts: List[str] = []

    def chroot_add_mount(self, source: str, target: str, *mount_args) -> bool:
        cmd = ["mount"] + list(mount_args) + [source, target]
        try:
            subprocess.run(cmd, check=True)
            self.active_mounts.insert(0, target)
            return True
        except subprocess.CalledProcessError:
            return False

    def chroot_setup(self, chrootdir: str) -> bool:
        self.active_mounts = []
        atexit.register(self.chroot_teardown)

        return (
            self.chroot_add_mount("proc", f"{chrootdir}/proc", "-t", "proc", "-o", "nosuid,noexec,nodev")
            and self.chroot_add_mount("sys", f"{chrootdir}/sys", "-t", "sysfs", "-o", "nosuid,noexec,nodev,ro")
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

    def chroot_teardown(self) -> None:
        if self.active_mounts:
            for mount in self.active_mounts:
                try:
                    subprocess.run(["umount", mount], check=False, capture_output=True)
                except Exception:
                    pass
        self.active_mounts.clear()

    def execute(self, chrootdir: str, command: str | List[str], get_output: bool = False) -> Optional[str]:
        if os.geteuid() != 0:
            raise ChrootError("This operation requires root privileges")

        if not os.path.isdir(chrootdir):
            raise ChrootError(f"Chroot directory does not exist: {chrootdir}")

        if not self.chroot_setup(chrootdir):
            raise ChrootError(f"Failed to setup chroot environment: {chrootdir}")

        # Handle both string commands and list of arguments
        if isinstance(command, list):
            # If command is a list, pass arguments directly
            chroot_args = ["chroot", chrootdir] + command
        else:
            # If command is a string, use bash -c
            # chroot_args = ["chroot", chrootdir, "/bin/bash", "-c"] + command.split(" ")
            chroot_args = ["chroot", chrootdir, command]

        env = os.environ.copy()
        env["SHELL"] = "/bin/bash"

        pid_unshare_cmd = ["unshare", "--fork", "--pid"]
        pid_unshare_cmd.extend(chroot_args)
        print("Executing command in chroot:", pid_unshare_cmd)
        safe_cmd = """ """.join(pid_unshare_cmd)
        print("Safe command:", safe_cmd)
        try:
            if get_output:
                result = subprocess.run(safe_cmd, env=env, shell=True, capture_output=True, text=True, check=True)
                print(result)
                return result.stdout
            else:
                subprocess.run(safe_cmd, env=env, shell=True, check=True)
                return None
        except subprocess.CalledProcessError as e:
            raise ChrootError(f"Command failed in chroot: {command}")


def chroot(chrootdir: str, command: Union[str, List[str]], get_output: bool = False) -> Optional[str]:
    """Execute a command in a chroot environment.

    Args:
        chrootdir: Path to the chroot directory
        command: Command to execute (string or list of arguments)
        get_output: Whether to capture and return command output

    Returns:
        Command output if get_output=True, None otherwise

    Raises:
        ChrootError: If the operation fails
    """
    chroot_instance = Chroot()
    return chroot_instance.execute(chrootdir, command, get_output)
