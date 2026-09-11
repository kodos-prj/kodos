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
                    
                    -- Create partitions if defined
                    if disk_config.partitions and type(disk_config.partitions) == "table" then
                        for part_num, partition in pairs(disk_config.partitions) do
                            if type(partition) == "table" and partition.size then
                                table.insert(steps, {
                                    name = "devices_partition_" .. disk_name .. "_" .. part_num,
                                    description = "Create partition " .. part_num .. " on " .. device_path,
                                    command = "parted -s " .. device_path .. " mkpart primary " .. (partition.start or "0") .. " " .. partition.size,
                                    order = 10 + part_num,
                                })
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
                                if fs_type == "ext4" then
                                    mkfs_cmd = "mkfs.ext4 -F " .. part_device
                                elseif fs_type == "ext3" then
                                    mkfs_cmd = "mkfs.ext3 -F " .. part_device
                                elseif fs_type == "btrfs" then
                                    mkfs_cmd = "mkfs.btrfs -f " .. part_device
                                elseif fs_type == "xfs" then
                                    mkfs_cmd = "mkfs.xfs -f " .. part_device
                                elseif fs_type == "vfat" then
                                    mkfs_cmd = "mkfs.vfat -F 32 " .. part_device
                                else
                                    mkfs_cmd = "mkfs." .. fs_type .. " " .. part_device
                                end
                                
                                table.insert(steps, {
                                    name = "devices_format_" .. disk_name .. "_" .. part_num,
                                    description = "Format partition " .. part_num .. " as " .. fs_type,
                                    command = mkfs_cmd,
                                    order = 20 + part_num,
                                    depends_on = {"devices_partition_" .. disk_name .. "_" .. part_num},
                                })
                            end
                        end
                    end
                    
                    -- Mount partitions
                    if disk_config.partitions and type(disk_config.partitions) == "table" then
                        for part_num, partition in pairs(disk_config.partitions) do
                            if type(partition) == "table" and partition.mountpoint then
                                local part_device = device_path .. part_num
                                local mount_path = partition.mountpoint
                                
                                table.insert(steps, {
                                    name = "devices_mount_" .. disk_name .. "_" .. part_num,
                                    description = "Mount " .. part_device .. " at " .. mount_path,
                                    command = "mkdir -p " .. mount_path .. " && mount " .. part_device .. " " .. mount_path,
                                    order = 30 + part_num,
                                    depends_on = {"devices_format_" .. disk_name .. "_" .. part_num},
                                })
                            end
                        end
                    end
                end
            end
        end
        
        return steps
    end
}

return module
