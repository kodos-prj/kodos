--- Universal bootstrap step emission (supports both Arch and Debian).
-- Emits: disk operations, mount, fstab, locale, hostname, bootloader steps.
-- Distro-specific logic is minimal (only bootloader type differs).

local M = {}

function M.emit_bootstrap_steps(conf, predicted_partition_list, distro)
    --- Emit full bootstrap step sequence.
    -- Args:
    --   conf (table): Configuration with conf.devices, conf.locale, conf.hostname, etc.
    --   predicted_partition_list (table): Pre-computed list of partitions
    --                                      [{device="/dev/sda1", mountpoint="/boot", filesystem="vfat"}, ...]
    --   distro (string): Distribution type ("arch" or "debian")
    -- Returns:
    --   List of step tables: {kind, name, program, args, meta}
    
    local steps = {}
    local devices = conf.devices or {}
    
    --- Helper: Emit disk operations (wipe, partition, format)
    local function emit_disk_ops()
        for d_id in pairs(devices) do
            local disk = devices[d_id]
            local device = disk.device
            local suffix = (device:match("nvme") or device:match("mmcblk")) and "p" or ""
            
            -- Wipe
            table.insert(steps, {
                kind = "disk",
                name = "wipe:" .. device,
                program = "wipefs",
                args = {"-a", device},
                meta = {},
            })
            
            -- Partition + Format
            local partitions = disk.partitions or {}
            for pid in pairs(partitions) do
                local part = partitions[pid]
                local name = part.name
                local size = part.size
                local fs = part.type
                local mountpoint = part.mountpoint
                local blockdevice = device .. suffix .. pid
                local end_val = size == "100%" and "0" or ("+" .. size)
                
                local partition_args = {"-n", ("0:0:" .. end_val)}
                
                -- Map filesystem to sgdisk type code
                local fs_types = {
                    ["ext4"] = "8300",
                    ["btrfs"] = "8300",
                    ["vfat"] = "EF00",
                    ["esp"] = "ef00",
                }
                if fs_types[fs] then
                    table.insert(partition_args, "-t")
                    table.insert(partition_args, ("0:" .. fs_types[fs]))
                end
                
                table.insert(partition_args, "-c")
                table.insert(partition_args, ("0:" .. name))
                table.insert(partition_args, device)
                
                -- Partition step
                table.insert(steps, {
                    kind = "disk",
                    name = "partition:" .. name,
                    program = "sgdisk",
                    args = partition_args,
                    meta = {size = size, filesystem = fs, mountpoint = mountpoint},
                })
                
                -- Format step
                local fmt_cmds = {
                    ["ext4"] = "mkfs.ext4",
                    ["btrfs"] = "mkfs.btrfs -f",
                    ["vfat"] = "mkfs.vfat",
                    ["esp"] = "mkfs.vfat -F32",
                }
                if fmt_cmds[fs] then
                    table.insert(steps, {
                        kind = "disk",
                        name = "format:" .. name,
                        program = fmt_cmds[fs],
                        args = {blockdevice},
                        meta = {filesystem = fs},
                    })
                end
            end
        end
    end
    
    --- Helper: Emit mount steps from predicted_partition_list
    local function emit_mounts()
        for _, part in ipairs(predicted_partition_list or {}) do
            table.insert(steps, {
                kind = "disk",
                name = "mount:" .. (part.mountpoint == "/" and "root" or part.mountpoint:gsub("/", "-")),
                program = "mount",
                args = {part.device, part.mountpoint},
                meta = {device = part.device, mountpoint = part.mountpoint},
            })
        end
    end
    
    --- Helper: Emit system bootstrap steps (non-disk)
    -- Distro-specific bootloader type is set here based on distro parameter
    local function emit_system_steps()
        -- Determine bootloader type based on distro
        local bootloader_type = "grub"  -- Default
        if distro == "arch" then
            bootloader_type = "systemd-boot"
        elseif distro == "debian" then
            bootloader_type = "grub"
        end
        
        table.insert(steps, {
            kind = "system",
            name = "fstab",
            program = "",
            args = {},
            meta = {partitions = predicted_partition_list},
        })
        
        table.insert(steps, {
            kind = "system",
            name = "locale",
            program = "",
            args = {},
            meta = {locale = conf.locale or "en_US.UTF-8"},
        })
        
        table.insert(steps, {
            kind = "system",
            name = "hostname",
            program = "",
            args = {},
            meta = {hostname = conf.hostname or "kodos"},
        })
        
        table.insert(steps, {
            kind = "system",
            name = "bootloader",
            program = "",
            args = {},
            meta = {bootloader = bootloader_type},
        })
    end
    
    -- Emit in sequence: disk ops → mounts → system config
    emit_disk_ops()
    emit_mounts()
    emit_system_steps()
    
    return steps
end

return M
