-- Boot system module (Phase 2 replacement for Python boot.py)
-- Handles bootloader configuration, kernel selection, boot entry management

local Exec = require('kod.lib.exec')

local M = {}

-- Read the root device from /etc/fstab (single source of truth for root UUID)
-- Parses fstab lines: <device> <mount> <type> <opts> <dump> <pass>
function M.read_root_device(fstab_path)
    local file = assert(io.open(fstab_path, "r"), "Cannot open " .. fstab_path)
    local content = file:read("*a")
    file:close()
    
    for line in content:gmatch("[^\n]+") do
        -- Skip empty lines and comments
        line = line:gsub("^%s+", ""):gsub("%s+$", "")
        if line ~= "" and not line:match("^#") then
            local fields = {}
            for field in line:gmatch("%S+") do
                table.insert(fields, field)
            end
            -- Mount point is second field; root is "/"
            if #fields >= 2 and fields[2] == "/" then
                return fields[1]  -- Device field (e.g. UUID=...)
            end
        end
    end
    
    error("No '/' entry found in " .. fstab_path)
end

-- Get kernel version and file from distro module
-- Returns: (kernel_file, kernel_version)
function M.get_kernel_file(mount_point, kernel_pkg)
    -- For now, we require distro support (arch by default)
    -- This would be provided by a distro abstraction layer
    -- For initial MVP, use Python's get_kernel_file via callback
    
    -- TODO: Move distro logic to Lua
    -- Current: call Python get_kernel_file (temporary measure)
    local py_get_kernel = _G._dispatch_python and _G._dispatch_python.get_kernel_file
    if not py_get_kernel then
        error("Python get_kernel_file not available")
    end
    
    local ok, result = pcall(function()
        return py_get_kernel(mount_point, kernel_pkg or "linux")
    end)
    
    if not ok then
        error("Failed to get kernel file: " .. tostring(result))
    end
    
    -- Result is (kernel_file, kernel_version) tuple; unpack it
    return result[1], result[2]
end

-- Copy kernel file to /boot/vmlinuz-<kver>
function M.update_kernel(kernel_pkg, mount_point)
    local kernel_file, kver = M.get_kernel_file(mount_point, kernel_pkg)
    
    print("Update kernel ...." .. kernel_pkg)
    print("kver=" .. kver)
    print("cp " .. kernel_file .. " /boot/vmlinuz-" .. kver)
    
    local result = Exec.exec_chroot(
        "cp " .. kernel_file .. " /boot/vmlinuz-" .. kver,
        mount_point,
        { throw_on_error = true }
    )
    
    if not result.ok then
        error("Failed to copy kernel: " .. result.error)
    end
end

-- Generate initramfs using dracut
function M.update_initramfs(kernel_pkg, mount_point)
    print("Generating initramfs for " .. kernel_pkg .. " using dracut...")
    
    local kernel_file, kver = M.get_kernel_file(mount_point, kernel_pkg)
    print("Kernel version: " .. kver)
    
    -- Verify dracut is installed
    local verify = Exec.exec_chroot(
        "test -x /usr/bin/dracut",
        mount_point,
        { throw_on_error = false }
    )
    
    if not verify.ok then
        error("dracut not found in chroot at " .. mount_point ..
              ". dracut should be installed as part of base packages. Error: " .. verify.error)
    end
    
    -- Generate initramfs with kernel version in filename
    local output_file = "initramfs-linux-" .. kver .. ".img"
    print("Running: dracut --kver " .. kver .. " --hostonly --force /boot/" .. output_file)
    
    local dracut_result = Exec.exec_chroot(
        "dracut --kver " .. kver .. " --hostonly --force /boot/" .. output_file,
        mount_point,
        { throw_on_error = false }
    )
    
    if not dracut_result.ok then
        error("dracut failed to generate initramfs: " .. dracut_result.error ..
              ". Check dracut logs and kernel module configuration.")
    end
    
    -- Verify the file was created by checking in the mounted path
    local boot_initramfs = mount_point .. "/boot/" .. output_file
    local verify_file = io.open(boot_initramfs, "r")
    if not verify_file then
        error("Initramfs generation failed: expected " .. output_file ..
              " not found in /boot. dracut may have failed silently. Check chroot logs.")
    end
    verify_file:close()
    
    print("✅ Initramfs generated: " .. output_file)
end

-- Create systemd-boot entry + loader.conf for a generation
function M.create_boot_entry(generation, kernel_pkg, mount_point)
    local kernel_file, kver = M.get_kernel_file(mount_point, kernel_pkg)
    local root_device = M.read_root_device(mount_point .. "/etc/fstab")
    local subvol = "generations/" .. generation .. "/rootfs"
    local entry_name = "kodos-" .. generation
    
    -- Get current timestamp
    local today = Exec.exec(
        "date +'%Y-%m-%d %H:%M:%S'",
        { get_output = true, throw_on_error = true }
    )
    today = today.output:gsub("\n", ""):gsub(" *$", "")  -- Strip trailing whitespace
    
    -- Initramfs filename includes kernel version to support multiple generations
    local initramfs_name = "initramfs-linux-" .. kver .. ".img"
    
    local entry_conf = [[
title KodOS
sort-key kodos
version Generation ]] .. generation .. [[ KodOS (build ]] .. today .. [[ - ]] .. kver .. [[)
linux /vmlinuz-]] .. kver .. [[

initrd /]] .. initramfs_name .. [[

options root=]] .. root_device .. [[ rw rootflags=subvol=]] .. subvol
    
    -- Create entries directory
    local entries_path = mount_point .. "/boot/loader/entries/"
    os.execute("mkdir -p " .. entries_path)  -- Use simple os.execute for directory creation
    
    -- Write entry .conf file
    local entry_file = assert(io.open(entries_path .. entry_name .. ".conf", "w"))
    entry_file:write(entry_conf .. "\n")
    entry_file:close()
    
    -- Write loader.conf
    local loader_conf = [[
default ]] .. entry_name .. [[.conf
timeout 10
console-mode keep
]]
    
    local loader_file = assert(io.open(mount_point .. "/boot/loader/loader.conf", "w"))
    loader_file:write(loader_conf)
    loader_file:close()
end

return M
