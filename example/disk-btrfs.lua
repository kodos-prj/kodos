-- Disk partition definition

btrfs_options = "rw,noatime,compress-force=zstd:1,space_cache=v2"

return  {
   device = "/dev/vda",
   efi = true,
   -- efi_size = 1024,
   type = "gpt",
   filesystem = "ext4",
   partitions = {
      {
         name = "Boot",
         size = "1GB",
         type = "esp",
         mountpoint = "/boot",
      },
      {
         name = "Swap",
         size = "3GB",
         type = "linux-swap",
         resumeDevice = true,
      },
      {
         name = "Root",
         size = "100%",
         type = "btrfs",
         subvolumes = {
            -- Subvolume name is different from mountpoint
            rootfs = {
               subvol = "/rootfs",
               mountpoint = "/"
            },
            -- Subvolume name is the same as the mountpoint
            home = {
               subvol = "/home",
               -- mountOptions = "compress=zstd",
               mountOptions = btrfs_options,
               mountpoint = "/home",
            },
            -- Parent is not mounted so the mountpoint must be set
            root = {
               subvol = "/root",
               mountOptions = btrfs_options,
               mountpoint = "/root",
            },
            cache = {
               subvol = "/cache",
               mountOptions = btrfs_options,
               mountpoint = "/var/cache",
            },
            tmp = {
               subvol = "/tmp",
               mountOptions = btrfs_options,
               mountpoint = "/var/tmp",
            },
            log = {
               subvol = "/log",
               mountOptions = btrfs_options,
               mountpoint = "/var/log",
            },
            kod = {
               subvol = "/kod",
               mountOptions = btrfs_options,
               mountpoint = "/kod",
            }
         }
      },
   },
}
