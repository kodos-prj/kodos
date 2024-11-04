-- Disk partition definition

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
               mountOptions = "compress=zstd",
               mountpoint = "/home",
            },
            -- Parent is not mounted so the mountpoint must be set
            kod = {
               subvol = "/kod",
               mountOptions = "compress=zstd,noatime",
               mountpoint = "/kod",
            }
         }
      },
   },
}
