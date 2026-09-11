-- Devices section module - disk and partition configuration
-- Handles disk partitioning, formatting, and mounting

local Schema = require('kod.lib.schema')

local module = {
    schema = Schema.devices,
    
    emit_steps = function(config, distro)
         local steps = {}
         
         if not config then
             return steps
         end
         
         -- Iterate over each device (disk) definition
         for disk_name, disk_config in pairs(config) do
             if type(disk_config) == "table" then
                 -- Each disk_config should have device configuration
                 -- Check if there's a disk_definition or similar function
                 if disk_config.device then
                     -- Basic disk operations
                     local device_path = disk_config.device
                     
                     -- Initialize partition table if needed
                     if disk_config.type then
                         table.insert(steps, {
                             name = "devices_init_" .. disk_name,
                             description = "Initialize partition table on " .. device_path .. " as " .. disk_config.type,
                             command = "parted -s " .. device_path .. " mklabel " .. disk_config.type,
                             chroot = false,
                             order = 9,
                         })
                     end
                     
                      -- Create partitions if defined
                      if disk_config.partitions and type(disk_config.partitions) == "table" then
                          -- Calculate partition positions based on sizes
                          local current_pos = "0"
                          
                          for part_num, partition in pairs(disk_config.partitions) do
                              if type(partition) == "table" and partition.size then
                                  local part_name = partition.name or ("part" .. part_num)
                                  local part_type = partition.type or "primary"
                                  local part_size = partition.size
                                  
                                  -- Map partition types to parted FS types
                                  local parted_fs_type = "ext4"  -- default
                                  if part_type == "esp" then
                                      parted_fs_type = "fat32"
                                  elseif part_type == "linux-swap" then
                                      parted_fs_type = "linux-swap"
                                  elseif part_type == "btrfs" then
                                      parted_fs_type = "btrfs"
                                  elseif part_type == "xfs" then
                                      parted_fs_type = "xfs"
                                  end
                                  
                                  -- Build parted mkpart command with proper syntax
                                  local mkpart_cmd = "parted -s " .. device_path .. " mkpart "
                                  if disk_config.type == "gpt" then
                                      -- GPT: mkpart PART-TYPE FS-TYPE START END
                                      -- PART-TYPE is usually "primary" for GPT (or part name in some versions)
                                      mkpart_cmd = mkpart_cmd .. 'primary ' .. parted_fs_type .. " " .. current_pos .. " " .. part_size
                                  else
                                      -- MBR: mkpart [PRIMARY|EXTENDED|LOGICAL] [FS-TYPE] START END
                                      mkpart_cmd = mkpart_cmd .. part_type .. " " .. parted_fs_type .. " " .. current_pos .. " " .. part_size
                                  end
                                  
                                  table.insert(steps, {
                                      name = "devices_partition_" .. disk_name .. "_" .. part_num,
                                      description = "Create " .. part_type .. " partition '" .. part_name .. "' on " .. device_path,
                                      command = mkpart_cmd,
                                      chroot = false,
                                      order = 10 + part_num,
                                      depends_on = disk_config.type and {"devices_init_" .. disk_name} or nil,
                                  })
                                  
                                  -- For GPT ESP partitions, set the esp flag
                                  if disk_config.type == "gpt" and part_type == "esp" then
                                      table.insert(steps, {
                                          name = "devices_set_esp_" .. disk_name .. "_" .. part_num,
                                          description = "Mark partition " .. part_num .. " as EFI System Partition",
                                          command = "parted -s " .. device_path .. " set " .. part_num .. " esp on",
                                          chroot = false,
                                          order = 11 + part_num,
                                          depends_on = {"devices_partition_" .. disk_name .. "_" .. part_num},
                                      })
                                  end
                                  
                                  -- Update current position for next partition
                                  current_pos = part_size
                              end
                          end
                      end
                    
                     -- Format partitions
                     if disk_config.partitions and type(disk_config.partitions) == "table" then
                         for part_num, partition in pairs(disk_config.partitions) do
                             if type(partition) == "table" and partition.filesystem then
                                 local fs_type = partition.filesystem
                                 local part_device = device_path .. part_num
                                 
                                 local mkfs_cmd
                                 if fs_type == "esp" or fs_type == "vfat" then
                                     mkfs_cmd = "mkfs.vfat -F 32 " .. part_device
                                 elseif fs_type == "ext4" then
                                     mkfs_cmd = "mkfs.ext4 -F " .. part_device
                                 elseif fs_type == "ext3" then
                                     mkfs_cmd = "mkfs.ext3 -F " .. part_device
                                 elseif fs_type == "btrfs" then
                                     mkfs_cmd = "mkfs.btrfs -f " .. part_device
                                 elseif fs_type == "xfs" then
                                     mkfs_cmd = "mkfs.xfs -f " .. part_device
                                 elseif fs_type == "linux-swap" then
                                     mkfs_cmd = "mkswap " .. part_device
                                 else
                                     mkfs_cmd = "mkfs." .. fs_type .. " " .. part_device
                                 end
                                 
                                 table.insert(steps, {
                                     name = "devices_format_" .. disk_name .. "_" .. part_num,
                                     description = "Format partition " .. part_num .. " as " .. fs_type,
                                     command = mkfs_cmd,
                                     chroot = false,
                                     order = 20 + part_num,
                                     depends_on = {"devices_partition_" .. disk_name .. "_" .. part_num},
                                 })
                             end
                         end
                     end
                    
                       -- Mount partitions to /mnt staging area (for chroot installation)
                       local has_root_partition = false
                       if disk_config.partitions and type(disk_config.partitions) == "table" then
                           for part_num, partition in pairs(disk_config.partitions) do
                               if type(partition) == "table" and partition.mountpoint then
                                   local part_device = device_path .. part_num
                                   local mount_path = partition.mountpoint
                                   -- For chroot installation, mount to /mnt staging area
                                   -- Root (/) mounts to /mnt, /boot mounts to /mnt/boot, etc.
                                   local chroot_mount_path = "/mnt" .. (mount_path == "/" and "" or mount_path)
                                   
                                   table.insert(steps, {
                                       name = "devices_mount_" .. disk_name .. "_" .. part_num,
                                       description = "Mount " .. part_device .. " at " .. chroot_mount_path,
                                       command = "mkdir -p " .. chroot_mount_path .. " && mount " .. part_device .. " " .. chroot_mount_path,
                                       chroot = false,
                                       order = 30 + part_num,
                                       depends_on = {"devices_format_" .. disk_name .. "_" .. part_num},
                                   })
                                   
                                   -- Track if we have a root partition
                                   if mount_path == "/" then
                                       has_root_partition = true
                                   end
                               end
                           end
                       end
                       
                       -- Bootstrap base system (Arch Linux pacstrap)
                       -- This must run after mounting, before any chroot steps
                       if has_root_partition then
                           table.insert(steps, {
                               name = "devices_bootstrap_base_system",
                               description = "Bootstrap base system to /mnt",
                               command = "pacstrap /mnt base linux-lts",
                               chroot = false,
                               order = 40,
                               depends_on = {"devices_mount_disk0_3"},
                           })
                           
                           -- Initialize pacman keyring for package verification
                           -- This must run in chroot AFTER bootstrap and BEFORE any pacman installs
                           table.insert(steps, {
                               name = "devices_pacman_keyring_init",
                               description = "Initialize pacman keyring for package verification",
                               command = "pacman-key --init && pacman-key --populate archlinux",
                               chroot = true,
                               order = 41,
                               depends_on = {"devices_bootstrap_base_system"},
                           })
                       end
                end
            end
        end
        
        return steps
    end
}

return module
