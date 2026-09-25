-- Devices section module - disk and partition configuration
-- Handles disk partitioning, formatting, and mounting

local Schema = require('kod.core.schema')
local FilesystemTypes = require('kod.system.filesystem_types')

-- Partition device path. Kernel/udev convention: base names ending in a
-- digit (nvme0n1, mmcblk0) take a 'p' separator (nvme0n1p1, not nvme0n11);
-- sda/vda-style names append the number directly.
local function partition_path(disk, num)
    if disk:match("%d$") then
        return disk .. "p" .. tostring(num)
    end
    return disk .. tostring(num)
end

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
                      
                      -- Wipe disk before partitioning
                      table.insert(steps, {
                          name = "devices_wipe_" .. disk_name,
                          description = "Wipe partition table on " .. device_path,
                          command = "wipefs -a " .. device_path,
                          chroot = false,
                          order = 8,
                      })
                      
                      -- Initialize GPT partition table (sgdisk requirement)
                      table.insert(steps, {
                          name = "devices_init_" .. disk_name,
                          description = "Initialize GPT partition table on " .. device_path,
                          command = "sgdisk -Z " .. device_path,
                          chroot = false,
                          order = 9,
                          depends_on = {"devices_wipe_" .. disk_name},
                      })
                      
                       -- Create partitions using sgdisk
                        if disk_config.partitions and type(disk_config.partitions) == "table" then
                            for part_num, partition in pairs(disk_config.partitions) do
                                if type(partition) == "table" and partition.size then
                                    local part_name = partition.name or ("part" .. part_num)
                                    local part_size = partition.size
                                    local fs_type = partition.filesystem or "ext4"
                                    
                                    -- Build sgdisk command: -n START:END -t SECTOR:CODE -c SECTOR:NAME
                                    -- Sector numbers: partition number (1-based, but 0 means auto-increment)
                                    -- Size format: +512MiB, +10GiB, or 0 for remaining space
                                    local end_sector = (part_size == "100%") and "0" or ("+" .. part_size)
                                    local sgdisk_args = {"-n", "0:0:" .. end_sector}
                                   
                                   -- Add partition type code if filesystem is mapped
                                   local gpt_type = FilesystemTypes.get_gpt_type(fs_type)
                                   if gpt_type then
                                       table.insert(sgdisk_args, "-t")
                                       table.insert(sgdisk_args, "0:" .. gpt_type)
                                   end
                                   
                                   -- Add partition name
                                   table.insert(sgdisk_args, "-c")
                                   table.insert(sgdisk_args, "0:" .. part_name)
                                   
                                   -- Add device path
                                   table.insert(sgdisk_args, device_path)
                                   
                                   table.insert(steps, {
                                       name = "devices_partition_" .. disk_name .. "_" .. part_num,
                                       description = "Create partition '" .. part_name .. "' on " .. device_path,
                                       command = "sgdisk " .. table.concat(sgdisk_args, " "),
                                       chroot = false,
                                       order = 10 + part_num,
                                       depends_on = {"devices_init_" .. disk_name},
                                   })
                               end
                           end
                       end
                    
                     -- Format partitions
                     if disk_config.partitions and type(disk_config.partitions) == "table" then
                         for part_num, partition in pairs(disk_config.partitions) do
                              if type(partition) == "table" and partition.filesystem then
                                  local fs_type = partition.filesystem
                                  local part_device = partition_path(device_path, part_num)
                                  
                                  -- Get mkfs command from filesystem_types lookup table
                                  local mkfs_cmd = FilesystemTypes.get_mkfs_cmd(fs_type)
                                  
                                  if mkfs_cmd then
                                      table.insert(steps, {
                                          name = "devices_format_" .. disk_name .. "_" .. part_num,
                                          description = "Format partition " .. part_num .. " as " .. fs_type,
                                          command = mkfs_cmd .. " " .. part_device,
                                          chroot = false,
                                          order = 20 + part_num,
                                          depends_on = {"devices_partition_" .. disk_name .. "_" .. part_num},
                                      })
                                  end
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
                                    local part_device = partition_path(device_path, part_num)
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
                       
                       -- Create btrfs filesystem hierarchy with subvolumes and bind mounts
                       -- This must run after mounting but before bootstrap
                       if has_root_partition then
                           -- Step 1: Create top-level directories
                           table.insert(steps, {
                               name = "devices_create_btrfs_dirs",
                               description = "Create btrfs filesystem hierarchy directories",
                               command = "mkdir -p /mnt/store /mnt/generations/0 /mnt/current && mkdir -p /mnt/store/root /mnt/store/var/log /mnt/store/var/tmp /mnt/store/var/cache /mnt/store/var/kod",
                               chroot = false,
                               order = 35,
                               depends_on = {"devices_mount_disk0_3"},
                           })
                           
                           -- Step 2: Create btrfs subvolumes
                           -- store/home subvolume for persistent home directory
                           table.insert(steps, {
                               name = "devices_create_btrfs_store_home",
                               description = "Create btrfs store/home subvolume",
                               command = "btrfs subvolume create /mnt/store/home",
                               chroot = false,
                               order = 36,
                               depends_on = {"devices_create_btrfs_dirs"},
                               on_error = "warn",  -- May fail if already exists
                           })
                           
                           -- Step 3: Create generation 0 rootfs subvolume
                           table.insert(steps, {
                               name = "devices_create_btrfs_generation_0",
                               description = "Create btrfs generation 0 rootfs subvolume",
                               command = "btrfs subvolume create /mnt/generations/0/rootfs",
                               chroot = false,
                               order = 37,
                               depends_on = {"devices_create_btrfs_store_home"},
                           })
                           
                           -- Step 4: Remount filesystem hierarchy
                           -- Unmount current /mnt, then remount generation 0 rootfs as root
                           -- Get the root partition from config to use in mount command
                           local root_partition_device = nil
                           if disk_config.partitions and disk_config.partitions[3] then
                               root_partition_device = partition_path(device_path, "3")
                           end
                           
                           if root_partition_device then
                               table.insert(steps, {
                                   name = "devices_remount_btrfs_generation",
                                   description = "Remount btrfs generation 0 rootfs as root",
                                   command = "umount -R /mnt && mount -o subvol=generations/0/rootfs " .. root_partition_device .. " /mnt",
                                   chroot = false,
                                   order = 38,
                                   depends_on = {"devices_create_btrfs_generation_0"},
                               })
                               
                               -- Step 5: Recreate mount directories inside new root
                               table.insert(steps, {
                                   name = "devices_create_mount_dirs",
                                   description = "Create mount directories in generation rootfs",
                                   command = "mkdir -p /mnt/boot /mnt/kod /mnt/home /mnt/root /mnt/var/log /mnt/var/tmp /mnt/var/cache /mnt/var/kod",
                                   chroot = false,
                                   order = 38.5,
                                   depends_on = {"devices_remount_btrfs_generation"},
                               })
                               
                               -- Step 6: Mount boot partition
                               table.insert(steps, {
                                   name = "devices_mount_btrfs_boot",
                                   description = "Mount boot partition",
                                   command = "mount " .. partition_path(device_path, "1") .. " /mnt/boot",
                                   chroot = false,
                                   order = 38.6,
                                   depends_on = {"devices_create_mount_dirs"},
                               })
                               
                               -- Step 7: Mount /kod (raw btrfs root for subvolume access)
                               table.insert(steps, {
                                   name = "devices_mount_btrfs_kod",
                                   description = "Mount raw btrfs root for store access",
                                   command = "mount " .. root_partition_device .. " /mnt/kod",
                                   chroot = false,
                                   order = 38.7,
                                   depends_on = {"devices_mount_btrfs_boot"},
                               })
                               
                               -- Step 8: Mount /home (store/home subvolume)
                               table.insert(steps, {
                                   name = "devices_mount_btrfs_home",
                                   description = "Mount store/home subvolume",
                                   command = "mount -o subvol=store/home " .. root_partition_device .. " /mnt/home",
                                   chroot = false,
                                   order = 38.8,
                                   depends_on = {"devices_mount_btrfs_kod"},
                               })
                               
                               -- Step 9: Mount bind mounts for persistent directories
                               table.insert(steps, {
                                   name = "devices_mount_btrfs_binds",
                                   description = "Create bind mounts for persistent directories",
                                   command = "mount --bind /mnt/kod/store/root /mnt/root && mount --bind /mnt/kod/store/var/log /mnt/var/log && mount --bind /mnt/kod/store/var/tmp /mnt/var/tmp && mount --bind /mnt/kod/store/var/cache /mnt/var/cache && mount --bind /mnt/kod/store/var/kod /mnt/var/kod",
                                   chroot = false,
                                   order = 38.9,
                                   depends_on = {"devices_mount_btrfs_home"},
                               })
                               
                               -- Step 10: Write generation marker
                               table.insert(steps, {
                                   name = "devices_write_generation_marker",
                                   description = "Write generation number marker",
                                   command = "echo '0' > /mnt/.generation",
                                   chroot = false,
                                   order = 39,
                                   depends_on = {"devices_mount_btrfs_binds"},
                               })
                           end
                       end
                       
                        -- Bootstrap base system (Arch Linux pacstrap)
                        -- This must run after btrfs hierarchy setup, before any chroot steps
                        if has_root_partition then
                             table.insert(steps, {
                                 name = "devices_bootstrap_base_system",
                                 description = "Bootstrap base system to /mnt",
                                 -- Use full essential package list from ArchAdapter._get_base_packages_config()
                                 command = "pacstrap -K /mnt linux-lts base base-devel debugedit fakeroot intel-ucode btrfs-progs linux-firmware bash-completion mlocate sudo schroot whois dracut git arch-install-scripts",
                                 chroot = false,
                                 order = 40,
                                 depends_on = {"devices_write_generation_marker"},
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
                            
                              -- Generate /etc/fstab for system boot with btrfs subvolume support
                              -- This must be created after all partitions are formatted and before boot
                              -- Format: device mountpoint fstype options dump fsck_pass
                              -- Runs on the HOST, not in chroot: a fresh chroot has no udev/blkid
                              -- runtime state, so `lsblk -no UUID` there exits 0 with EMPTY output,
                              -- silently producing an unbootable fstab/boot entry. The test -n
                              -- guard makes an empty UUID fail the step instead of writing garbage.
                              local fstab_commands = {
                                  'echo "# Static information about the filesystems." > /mnt/etc/fstab',
                                  'echo "# See fstab(5) for details." >> /mnt/etc/fstab',
                                  'echo "" >> /mnt/etc/fstab',
                              }
                              
                              -- Root partition (/) - generation 0 rootfs subvolume
                              -- fsck pass must be 0: btrfs has no external fsck; a failing
                              -- fsck@<uuid>.service blocks ALL systemd mounts of this device
                              -- (/kod, /home) at boot. (Root itself mounts via initramfs.)
                              table.insert(fstab_commands, "UUID=$(lsblk -no UUID " .. partition_path(device_path, "3") .. ") && test -n \"$UUID\" && echo \"UUID=$UUID / btrfs defaults,subvol=generations/0/rootfs 0 0\" >> /mnt/etc/fstab")
                              
                              -- Boot partition (/boot)
                              -- fsck pass 0: dosfstools (fsck.vfat) may be absent from base;
                              -- a failing fsck@<uuid>.service would block the /boot mount.
                              table.insert(fstab_commands, "UUID=$(lsblk -no UUID " .. partition_path(device_path, "1") .. ") && test -n \"$UUID\" && echo \"UUID=$UUID /boot vfat defaults,nofail 0 0\" >> /mnt/etc/fstab")
                              
                              -- /kod mount (raw btrfs root for subvolume access)
                              table.insert(fstab_commands, "UUID=$(lsblk -no UUID " .. partition_path(device_path, "3") .. ") && test -n \"$UUID\" && echo \"UUID=$UUID /kod btrfs defaults,nofail 0 0\" >> /mnt/etc/fstab")
                              
                              -- /home (store/home subvolume)
                              table.insert(fstab_commands, "UUID=$(lsblk -no UUID " .. partition_path(device_path, "3") .. ") && test -n \"$UUID\" && echo \"UUID=$UUID /home btrfs defaults,subvol=store/home,nofail 0 0\" >> /mnt/etc/fstab")
                              
                              -- Bind mounts for persistent store directories
                              -- nofail: non-critical at boot; x-systemd.after: bind source must
                              -- exist, i.e. /kod must be mounted first (no implicit ordering).
                              table.insert(fstab_commands, 'echo "/kod/store/root /root none defaults,bind,nofail,x-systemd.after=kod.mount 0 0" >> /mnt/etc/fstab')
                              table.insert(fstab_commands, 'echo "/kod/store/var/log /var/log none defaults,bind,nofail,x-systemd.after=kod.mount 0 0" >> /mnt/etc/fstab')
                              table.insert(fstab_commands, 'echo "/kod/store/var/tmp /var/tmp none defaults,bind,nofail,x-systemd.after=kod.mount 0 0" >> /mnt/etc/fstab')
                              table.insert(fstab_commands, 'echo "/kod/store/var/cache /var/cache none defaults,bind,nofail,x-systemd.after=kod.mount 0 0" >> /mnt/etc/fstab')
                              table.insert(fstab_commands, 'echo "/kod/store/var/kod /var/kod none defaults,bind,nofail,x-systemd.after=kod.mount 0 0" >> /mnt/etc/fstab')
                             
                              table.insert(steps, {
                                  name = "devices_generate_fstab",
                                  description = "Generate /etc/fstab with btrfs subvolume and bind mount configuration",
                                  command = table.concat(fstab_commands, ' && '),
                                  chroot = false,
                                 order = 43,
                                 depends_on = {"devices_pacman_keyring_init"},
                             })
                            
                            -- Copy resolv.conf from host for DNS resolution in chroot
                            -- This allows pacman to resolve mirrors during package installation
                            table.insert(steps, {
                                name = "devices_setup_dns",
                                description = "Copy host /etc/resolv.conf to chroot for DNS resolution",
                                command = "cp /etc/resolv.conf /mnt/etc/resolv.conf || true",
                                chroot = false,  -- Run on host, not in chroot
                                order = 44,
                                 depends_on = {"devices_pacman_keyring_init"},
                                 on_error = "warn",  -- Non-critical if host has no resolv.conf
                             })
                         end
                  end
               end
           end
          
          return steps
      end
}

return module
