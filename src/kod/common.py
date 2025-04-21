import os

use_debug = True


class color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def set_debug(val=True):
    global use_debug
    use_debug = val


def set_verbose(val=True):
    global use_verbose
    use_verbose = val


def exec(cmd, get_output=False) -> str:
    if use_debug or use_verbose:
        print(">>", color.PURPLE + cmd + color.END)
    if not use_debug:
        if get_output:
            return os.popen(cmd).read()
        else:
            os.system(cmd)
    return ""


def exec_chroot(cmd, mount_point="/mnt", get_output=False) -> str:
    chroot_cmd = f"arch-chroot {mount_point} "
    chroot_cmd += cmd
    return exec(chroot_cmd, get_output=True)
