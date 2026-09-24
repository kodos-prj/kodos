-- Wrapper for Python exec and exec_chroot functions
--
-- Called from Lua system modules; dispatches to Python implementations.
-- Functions are injected by Python at runtime via _G._dispatch_python.

local M = {}

-- Call Python exec() function via the dispatch table
-- Options: { get_output=bool, throw_on_error=bool }
function M.exec(cmd, options)
    options = options or {}
    
    -- Get the Python exec function from global dispatch (injected at runtime)
    local py_exec = _G._dispatch_python and _G._dispatch_python.exec
    if not py_exec then
        error("Python exec function not available; dispatch not initialized")
    end
    
    local ok, result = pcall(function()
        return py_exec(cmd, options.get_output or false)
    end)
    
    if not ok then
        if options.throw_on_error then
            error("exec failed: " .. tostring(result))
        end
        return { ok = false, output = "", error = tostring(result) }
    end
    
    return { ok = true, output = result or "", error = nil }
end

-- Call Python exec_chroot() function via the dispatch table
-- Options: { get_output=bool, throw_on_error=bool }
function M.exec_chroot(cmd, mount_point, options)
    options = options or {}
    
    local py_exec_chroot = _G._dispatch_python and _G._dispatch_python.exec_chroot
    if not py_exec_chroot then
        error("Python exec_chroot function not available; dispatch not initialized")
    end
    
    local ok, result = pcall(function()
        -- Call with positional args; Lupa will pass them to the Python function
        return py_exec_chroot(cmd, mount_point, options.get_output or false)
    end)
    
    if not ok then
        if options.throw_on_error then
            error("exec_chroot failed: " .. tostring(result))
        end
        return { ok = false, output = "", error = tostring(result) }
    end
    
    return { ok = true, output = result or "", error = nil }
end

return M
