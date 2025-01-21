import os

use_debug = True

class color:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

def set_debug(val=True):
    global use_debug
    use_debug = val

def exec(cmd):
    if use_debug:
        print(">>", color.PURPLE+cmd+color.END) 
    else:
        os.system(cmd)

def exec_chroot(cmd):
    print(cmd)
    chroot_cmd = "arch-chroot /mnt "
    chroot_cmd += cmd
    exec(chroot_cmd)