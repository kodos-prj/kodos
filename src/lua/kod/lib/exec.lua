-- Execute shell commands in host or chroot environments
-- Native Lua implementation using os.execute and temporary scripts

local M = {}

-- Execute a shell command on the host
-- Options: { get_output=bool, throw_on_error=bool }
function M.exec(cmd, options)
    options = options or {}
    
    if options.get_output then
        -- Capture output by redirecting to temp file
        local tmp_file = "/tmp/kodos_exec_output_" .. os.time() .. math.random(1000000)
        local full_cmd = cmd .. " > " .. tmp_file .. " 2>&1"
        local success, exit_type, exit_code = os.execute(full_cmd)
        
        -- Read output
        local file = io.open(tmp_file, "r")
        local output = file and file:read("*a") or ""
        if file then file:close() end
        os.remove(tmp_file)
        
        -- os.execute returns (success, type, code) in Lua 5.5+
        local status = exit_code or (success and 0 or 1)
        
        if status ~= 0 and options.throw_on_error then
            error("exec failed with status " .. status .. ": " .. output)
        end
        
        return {
            ok = (status == 0),
            output = output,
            error = (status ~= 0) and output or nil,
            status = status
        }
    else
        -- Just run command
        local success, exit_type, exit_code = os.execute(cmd .. " >/dev/null 2>&1")
        local status = exit_code or (success and 0 or 1)
        
        if status ~= 0 and options.throw_on_error then
            error("exec failed with status " .. status)
        end
        
        return {
            ok = (status == 0),
            output = "",
            error = (status ~= 0) and "command failed" or nil,
            status = status
        }
    end
end

-- Execute a shell command in chroot environment
-- ponytail: Uses 'chroot' command directly instead of Python wrapper
-- Options: { get_output=bool, throw_on_error=bool }
function M.exec_chroot(cmd, mount_point, options)
    options = options or {}
    
    -- Build chroot command
    local chroot_cmd = "chroot " .. mount_point .. " /bin/bash -c '" .. cmd:gsub("'", "'\\''") .. "'"
    
    if options.get_output then
        -- Capture output by redirecting to temp file
        local tmp_file = "/tmp/kodos_chroot_output_" .. os.time() .. math.random(1000000)
        local full_cmd = chroot_cmd .. " > " .. tmp_file .. " 2>&1"
        local success, exit_type, exit_code = os.execute(full_cmd)
        
        -- Read output
        local file = io.open(tmp_file, "r")
        local output = file and file:read("*a") or ""
        if file then file:close() end
        os.remove(tmp_file)
        
        -- os.execute returns (success, type, code) in Lua 5.5+
        local status = exit_code or (success and 0 or 1)
        
        if status ~= 0 and options.throw_on_error then
            error("exec_chroot failed with status " .. status .. ": " .. output)
        end
        
        return {
            ok = (status == 0),
            output = output,
            error = (status ~= 0) and output or nil,
            status = status
        }
    else
        -- Just run command
        local success, exit_type, exit_code = os.execute(chroot_cmd .. " >/dev/null 2>&1")
        local status = exit_code or (success and 0 or 1)
        
        if status ~= 0 and options.throw_on_error then
            error("exec_chroot failed with status " .. status)
        end
        
        return {
            ok = (status == 0),
            output = "",
            error = (status ~= 0) and "command failed" or nil,
            status = status
        }
    end
end

return M
