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
                        -- Mount root first (order 30), then other partitions (order 31+)
                        local has_root_partition = false
                        local mount_steps = {}
                        
                        if disk_config.partitions and type(disk_config.partitions) == "table" then
                            -- First pass: find root partition and collect all mount steps
                            for part_num, partition in pairs(disk_config.partitions) do
                                if type(partition) == "table" and partition.mountpoint then
                                    local part_device = device_path .. part_num
                                    local mount_path = partition.mountpoint
                                    -- For chroot installation, mount to /mnt staging area
                                    -- Root (/) mounts to /mnt, /boot mounts to /mnt/boot, etc.
                                    local chroot_mount_path = "/mnt" .. (mount_path == "/" and "" or mount_path)
                                    
                                    -- Calculate order: root first (30), then others (31+)
                                    local mount_order = (mount_path == "/" and 30) or (30 + part_num)
                                    
                                    table.insert(mount_steps, {
                                        name = "devices_mount_" .. disk_name .. "_" .. part_num,
                                        description = "Mount " .. part_device .. " at " .. chroot_mount_path,
                                        command = "mkdir -p " .. chroot_mount_path .. " && mount " .. part_device .. " " .. chroot_mount_path,
                                        chroot = false,
                                        order = mount_order,
                                        depends_on = {"devices_format_" .. disk_name .. "_" .. part_num},
                                        mount_path = mount_path,
                                    })
                                    
                                    -- Track if we have a root partition
                                    if mount_path == "/" then
                                        has_root_partition = true
                                    end
                                end
                            end
                            
                            -- Sort mount steps: root first, then by order
                            table.sort(mount_steps, function(a, b)
                                if a.mount_path == "/" then return true end
                                if b.mount_path == "/" then return false end
                                return a.order < b.order
                            end)
                            
                            -- Add sorted mount steps and update their order values
                            local mount_order_counter = 30
                            for _, step in ipairs(mount_steps) do
                                step.order = mount_order_counter
                                mount_order_counter = mount_order_counter + 1
                                table.insert(steps, step)
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
                           
                           -- Generate /etc/mtab for chroot environment
                           -- This is required for pacman to work inside chroot
                           table.insert(steps, {
                               name = "devices_setup_mtab",
                               description = "Generate /etc/mtab for chroot environment",
                               command = "mount -t proc proc /mnt/proc && mount -t sysfs sys /mnt/sys && mount -o bind /dev /mnt/dev && mount -o bind /dev/pts /mnt/dev/pts && ln -sf /proc/mounts /mnt/etc/mtab",
                               chroot = false,
                               order = 41,
                               depends_on = {"devices_bootstrap_base_system"},
                           })
                           
                            -- Initialize pacman keyring for package verification
                            -- This must run in chroot AFTER bootstrap and BEFORE any pacman installs
                            table.insert(steps, {
                                name = "devices_pacman_keyring_init",
                                description = "Initialize pacman keyring for package verification",
                                command = "pacman-key --init && pacman-key --populate archlinux",
                                chroot = true,
                                order = 42,
                                depends_on = {"devices_setup_mtab"},
                            })
                            
                            -- Generate /etc/fstab for system boot
                            -- This must be created after all partitions are formatted and before boot
                            -- Collect partition info and generate fstab entries
                            local fstab_entries = {}
                            if disk_config.partitions and type(disk_config.partitions) == "table" then
                                for part_num, partition in pairs(disk_config.partitions) do
                                    if type(partition) == "table" and partition.mountpoint then
                                        local part_device = device_path .. part_num
                                        local mount_point = partition.mountpoint
                                        local fs_type = partition.filesystem or "ext4"
                                        local mount_opts = partition.mount_options or "defaults"
                                        local dump = partition.dump or "0"
                                        local fsck_pass = partition.fsck_pass or "0"
                                        
                                        -- Adjust fsck_pass for root and boot
                                        if mount_point == "/" then
                                            fsck_pass = "1"
                                        elseif mount_point == "/boot" then
                                            fsck_pass = "2"
                                        end
                                        
                                        -- Format: device mount fs_type opts dump fsck_pass
                                        local fstab_line = part_device .. "\t" .. mount_point .. "\t" .. fs_type .. "\t" .. mount_opts .. "\t" .. dump .. "\t" .. fsck_pass
                                        table.insert(fstab_entries, fstab_line)
                                    end
                                end
                            end
                            
                            if #fstab_entries > 0 then
                                local fstab_content = table.concat(fstab_entries, "\\n")
                                table.insert(steps, {
                                    name = "devices_generate_fstab",
                                    description = "Generate /etc/fstab for system boot",
                                    command = "echo -e '" .. fstab_content .. "' > /etc/fstab",
                                    chroot = true,
                                    order = 43,
                                    depends_on = {"devices_pacman_keyring_init"},
                                })
                            end
                        end
                 end
             end
         end
         
         return steps
     end
}

return module
