-- Filesystem type definitions and command mappings
-- Single source of truth for mkfs commands and GPT type codes
-- Used by devices.lua for sgdisk partitioning and mkfs formatting

local filesystem_types = {
    -- Filesystem type to mkfs command mapping
    -- Used by devices.lua to generate format steps
    mkfs_commands = {
        esp = "mkfs.vfat -F32",
        fat32 = "mkfs.vfat -F32",
        vfat = "mkfs.vfat",
        bfs = "mkfs.bfs",
        cramfs = "mkfs.cramfs",
        ext3 = "mkfs.ext3",
        fat = "mkfs.fat",
        msdos = "mkfs.msdos",
        xfs = "mkfs.xfs",
        btrfs = "mkfs.btrfs -f",
        ext2 = "mkfs.ext2",
        ext4 = "mkfs.ext4",
        minix = "mkfs.minix",
        f2fs = "mkfs.f2fs",
        ["linux-swap"] = "mkswap",
        noformat = nil,
    },
    
    -- Filesystem type to SGDisk GPT type code mapping
    -- Reference: https://www.rodsbooks.com/gdisk/ctypes.html
    -- Used by devices.lua to generate sgdisk partition type arguments
    gpt_type_codes = {
        esp = "ef00",          -- EFI System Partition
        fat32 = "0700",        -- Microsoft basic data
        vfat = "0700",         -- Microsoft basic data
        btrfs = "8300",        -- Linux filesystem
        ext2 = "8300",         -- Linux filesystem
        ext3 = "8300",         -- Linux filesystem
        ext4 = "8300",         -- Linux filesystem
        xfs = "8300",          -- Linux filesystem
        ["linux-swap"] = "8200", -- Linux swap
        f2fs = "8300",         -- Linux filesystem
        noformat = nil,        -- No partition type code needed
    },
}

--- Get mkfs command for a filesystem type
-- @param fs_type string: Filesystem type (e.g., "ext4", "btrfs", "esp")
-- @return string|nil: Full mkfs command with flags, or nil if no format needed
function filesystem_types.get_mkfs_cmd(fs_type)
    return filesystem_types.mkfs_commands[fs_type]
end

--- Get SGDisk GPT type code for a filesystem type
-- @param fs_type string: Filesystem type (e.g., "ext4", "btrfs", "esp")
-- @return string|nil: GPT type code (e.g., "8300"), or nil if not mapped
function filesystem_types.get_gpt_type(fs_type)
    return filesystem_types.gpt_type_codes[fs_type]
end

return filesystem_types
