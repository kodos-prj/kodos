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
               mountpoint = "/home",
               mountOptions = btrfs_options,
            },
            root = {
               subvol = "/root",
               mountpoint = "/root",
               mountOptions = btrfs_options,
            },
            cache = {
               subvol = "/cache",
               mountpoint = "/var/cache",
               mountOptions = btrfs_options,
            },
            tmp = {
               subvol = "/tmp",
               mountpoint = "/var/tmp",
               mountOptions = btrfs_options,
            },
            log = {
               subvol = "/log",
               mountpoint = "/var/log",
               mountOptions = btrfs_options,
            },
            kod = {
               subvol = "/kod",
               mountpoint = "/kod",
               mountOptions = btrfs_options,
            }
         }
      },
   },
}
