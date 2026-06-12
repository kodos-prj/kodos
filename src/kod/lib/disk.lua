-- Disk partition definition

function disk_definition(device, swap_size)
   -- device to define the partitions on. (e.g., device = "/dev/vda")
   -- spap_size is the size of the swap partition (e.g., swap_size = "3GB") or nil

   btrfs_options = "rw,noatime,compress-force=zstd:1,space_cache=v2"
      
   device_definition = {
      device = device,
      efi = true,
      type = "gpt",
      wipe = true,
   }
   
   partitions = {
      {
         name = "Boot",
         size = "1GB",
         type = "esp",
         mountpoint = "/boot",
         format = true,
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
      format = true,
   }

   table.insert(partitions, root_part)

   device_definition["partitions"] = partitions

   return device_definition
end

function disk_fs_hierarchy(device, swap_size, keep_home, keep_root)
   -- Create a partition definition with Btrfs subvolume hierarchy
   -- Includes the filesystem structure created in create_filesystem_hierarchy
   -- device: The device to define partitions on (e.g., "/dev/vda")
   -- swap_size: The size of swap partition or nil

   -- keep_home: If true, preserves existing home data (if any) during installation
   if keep_home == nil then keep_home = false end
   -- keep_root: If true, preserves existing root data (if any) during installation
   if keep_root == nil then keep_root = false end

   btrfs_options = "rw,noatime,compress-force=zstd:1,space_cache=v2"
   
   device_definition = {
      device = device,
      efi = true,
      type = "gpt",
      -- wipe = false,
   }
   
   partitions = {
      {
         name = "Boot",
         size = "1GB",
         type = "esp",
         mountpoint = "/boot",
         format = true,
         fstype = "vfat",
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
      format = true,
      fstype = "btrfs",
      mountpoint = "/",
      -- Btrfs subvolume hierarchy
      subvolumes = {
         -- Generation 0 (initial/current installation)
         ["/"] ={
            name = "generations/0/rootfs",
            -- mountpoint = "/",
            options = btrfs_options,
         },
         -- Home subvolume
         ["/home"] = {
            name = "persistent/home",
            -- mountpoint = "/home",
            options = btrfs_options,
            initialize = not keep_home, -- Keep existing home data if present
            persist = true, -- Mark as persistent to preserve across generations
         },
         -- System store directories (will be bind-mounted)
         ["/root"] = {
            name = "persistent/root",
            -- mountpoint = "/root",
            options = btrfs_options,
            initialize = not keep_root, -- Keep existing root data if present
            persist = true, -- Mark as persistent to preserve across generations
         },
         ["/var/log"] = {
            name = "persistent/var/log",
            -- mountpoint = "/var/log",
            options = btrfs_options,
            persist = true,
         },
         ["/var/tmp"] = {
            name = "persistent/var/tmp",
            -- mountpoint = "/var/tmp",
            options = btrfs_options,
            persist = true,
         },
         ["/var/cache"] = {
            name = "persistent/var/cache",
            -- mountpoint = "/var/cache",
            options = btrfs_options,
            persist = true,
         },
         ["/var/kod"] = {
            name = "persistent/var/kod",
            -- mountpoint = "/var/kod",
            options = btrfs_options,
            persist = true,
         },
      },
      -- Directory hierarchy for non-subvolume mounts
      directories = {
         "kod",
         "kod/persistent",
         "kod/store",
         "kod/generations",
         "kod/current",
      }
   }

   table.insert(partitions, root_part)

   device_definition["partitions"] = partitions

   return device_definition
end

return { 
   disk_definition = disk_definition,
   disk_fs_hierarchy = disk_fs_hierarchy,
}