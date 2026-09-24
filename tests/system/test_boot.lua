-- Integration tests for kod.system.boot Lua module
-- Tests that Lua boot operations produce same output as Python versions

local boot = require('kod.system.boot')

local function test_read_root_device()
    -- Create temp fstab
    local fstab = "/tmp/test_fstab_" .. os.time()
    local f = io.open(fstab, "w")
    f:write("# comment\n")
    f:write("UUID=abc-123 / btrfs defaults 0 0\n")
    f:write("UUID=def-456 /boot vfat 0 0\n")
    f:close()
    
    local root = boot.read_root_device(fstab)
    assert(root == "UUID=abc-123", "Expected UUID=abc-123, got " .. root)
    
    os.remove(fstab)
    print("✓ test_read_root_device passed")
end

local function test_read_root_device_no_entry()
    local fstab = "/tmp/test_fstab_no_root_" .. os.time()
    local f = io.open(fstab, "w")
    f:write("UUID=def-456 /boot vfat 0 0\n")
    f:close()
    
    local ok, err = pcall(function()
        boot.read_root_device(fstab)
    end)
    assert(not ok, "Should have raised error for missing root")
    assert(err:match("No '/' entry found"), "Error message should mention missing root entry")
    
    os.remove(fstab)
    print("✓ test_read_root_device_no_entry passed")
end

local function test_read_root_device_with_extra_whitespace()
    -- Test that parser handles extra whitespace correctly
    local fstab = "/tmp/test_fstab_whitespace_" .. os.time()
    local f = io.open(fstab, "w")
    f:write("  UUID=root-uuid    /    btrfs   defaults   0   0  \n")
    f:write("UUID=boot-uuid /boot vfat 0 0\n")
    f:close()
    
    local root = boot.read_root_device(fstab)
    assert(root == "UUID=root-uuid", "Expected UUID=root-uuid with whitespace, got " .. root)
    
    os.remove(fstab)
    print("✓ test_read_root_device_with_extra_whitespace passed")
end

-- Run all tests
test_read_root_device()
test_read_root_device_no_entry()
test_read_root_device_with_extra_whitespace()

print("\nAll Lua boot tests passed!")
