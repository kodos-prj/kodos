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


# pacman -Sy git poetry
# git clone https://github.com/kodos-prj/kodos
# cd kodos
# poetry install
# poetry shell


# fstab only with /boot
# rd.driver.pre=ext4 rd.driver.pre=vfat rd.shell rd.debugg log_buf_len=1M root=/dev/vda2 rw

# 10.0.2.15/24  gw 10.0.2.2

# # timedatectl set-timezone "America/Edmonton"

# list of packages to install
# pacman -Sp --config pacman.conf base linux linux-firmware mc | awk -F/ '{print $NF}' 


# boot btrfs ratition subvolume
# ]linux	/@/boot/vmlinuz-linux root=UUID=60d2f44d-87a1-4377-bb7c-ccd161d59a78 rw rootflags=subvol=@ cryptdevice=/dev/disk/by-uuid/bb7396f5-f246-4edf-9f1f-298c9ca560ac:cryptroot:allow-discards modprobe.blacklist=ehci_pci i915.semaphores=1 quiet loglevel=3 udev.log-priority=3
# linux	/boot/vmlinuz-linux root=UUID=60d2f44d-87a1-4377-bb7c-ccd161d59a78 rw rootflags=subvol=/rootfs i915.semaphores=1 loglevel=3
