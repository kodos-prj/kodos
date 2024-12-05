-- Disk partition definition

function disk_definition(device, swap_size)
   -- device to define the partitions on. (e.g., device = "/dev/vda")
   -- spap_size is the size of the swap partition (e.g., swap_size = "3GB") or nil

   btrfs_options = "rw,noatime,compress-force=zstd:1,space_cache=v2"
      
   device_definition = {
      device = device,
      efi = true,
      type = "gpt",
   }
   
   partitions = {
      {
         name = "Boot",
         size = "1GB",
         type = "esp",
         mountpoint = "/boot",
      }
   }
   if swap_size then
      swap_part = {
         name = "Swap",
         size = swap_size,
         type = "linux-swap",
         resumeDevice = true,
      }
      table.insert(partitions, swap_part)
   end

   root_part = {
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
            mountOptions = btrfs_options,   -- filesystem = "ext4",
   
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
   }

   table.insert(partitions, root_part)

   device_definition["partitions"] = partitions

   return device_definition
end

function disk_definition_simple(device, swap_size)
   -- device to define the partitions on. (e.g., device = "/dev/vda")
   -- spap_size is the size of the swap partition (e.g., swap_size = "3GB") or nil

   btrfs_options = "rw,noatime,compress-force=zstd:1,space_cache=v2"
      
   device_definition = {
      device = device,
      efi = true,
      type = "gpt",
   }
   
   partitions = {
      {
         name = "Boot",
         size = "1GB",
         type = "esp",
         mountpoint = "/boot",
      }
   }
   if swap_size then
      swap_part = {
         name = "Swap",
         size = swap_size,
         type = "linux-swap",
         resumeDevice = true,
      }
      table.insert(partitions, swap_part)
   end

   root_part = {
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
            mountOptions = btrfs_options,   -- filesystem = "ext4",
   
         },
         var = {
            subvol = "/var",
            mountpoint = "/var",
            mountOptions = btrfs_options,   -- filesystem = "ext4",
   
         },
         kod = {
            subvol = "/kod",
            mountpoint = "/kod",
            mountOptions = btrfs_options,
         }
      }
   }

   table.insert(partitions, root_part)

   device_definition["partitions"] = partitions

   return device_definition
end

return { 
   disk_definition = disk_definition,
   disk_definition_simple = disk_definition_simple 
}