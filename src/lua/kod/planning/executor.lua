-- Generic step runner for KodOS plans (language-agnostic orchestrator).
-- Runs steps in order, fires pre/post hooks, applies on_error policies.
--
-- Step kinds and execution paths:
--   system/disk: Run as shell commands with `timeout` guard and optional chroot wrap.
--                Uses os.execute for direct shell invocation (no output capture; lupa disables io.popen).
--   lua-system:  Dispatch to Lua system modules (e.g., kod.system.boot) via step.meta.operation.
--                Lua modules call Exec.exec_chroot() wrapper, which routes to Python exec_chroot
--                for kernel operations (distro-specific logic remains in Python for now).
--   package/service: Dispatch to host-side callable dispatch.step(step, ctx).
--                    May return "shell" to fall back to os.execute, or handle the step directly.
--
-- Architecture note:
--   - Executor.run_shell uses os.execute: generic shell runner (no output capture, no dependencies).
--   - Lua system modules (boot.lua) use Exec.exec_chroot: proper error handling and output capture
--     for critical boot operations that need Python's distro integration layer.

local Executor = {}

-- Quote a string for embedding in sh -c '...'
-- Uses the standard shell technique: '...' is literal, so to include a quote,
-- close quote, add escaped quote, reopen: 'foo'"'"'bar' = foo'bar
local function shq(s)
    return "'" .. s:gsub("'", "'\\''") .. "'"
end

-- Run a shell step (system or disk). Returns {success=...} or {success=false, error=...}.
-- Uses os.execute for direct shell invocation (no output capture due to lupa restrictions).
-- For operations requiring Python integration (kernel setup, etc.), use lua-system kind instead,
-- which dispatches to Lua system modules that call Exec.exec_chroot() wrapper.
function Executor.run_shell(step, mount_point)
    local parts = { step.program or step.command or "" }
    for i = 1, #(step.args or {}) do
        table.insert(parts, step.args[i])
    end
    local cmd = table.concat(parts, " ")
    if step.chroot then
        cmd = "chroot " .. shq(mount_point or "/") .. " sh -c " .. shq(cmd)
    end
    -- coreutils `timeout` guards each step; exit 124 on expiry.
    local full = "timeout " .. (step.timeout_s or 300) .. " " .. cmd
    local ok, term, status = os.execute(full)
    if ok then
        return { success = true }
    end
    return { success = false, error = "command failed (status " .. tostring(status) .. "): " .. cmd }
end

-- steps:   array of step tables {kind,name,program,args,chroot,timeout_s,on_error,meta}
-- ctx:     table with mount_point, use_chroot, repos
-- dispatch: table with dispatch.step(step, ctx) for package/service steps (optional)
-- hooks:   table mapping "pre:<kind>"/"post:<kind>" to arrays of callables
--
-- Returns: array of result tables {success, error, is_warning}
function Executor.run(steps, ctx, dispatch, hooks)
    hooks = hooks or {}
    local results = {}

    for i = 1, #steps do
         local step = steps[i]

         -- pre hooks: error aborts the whole run
        for _, hook in ipairs(hooks["pre:" .. step.kind] or {}) do
            local ok, err = pcall(hook, step, ctx)
            if not ok then
                error("pre:" .. step.kind .. " hook failed for step '" .. step.name .. "': " .. tostring(err))
            end
        end

        local result
        -- Package/service steps dispatch to host callbacks (which handle sudo/root)
        -- even if they have commands; other steps with commands are shell steps
        if step.kind == "package" or step.kind == "service" then
            -- Dispatch to host: the host decides whether to run via shell, sudo, or skip
            if dispatch and dispatch.step then
                local ok, r = pcall(dispatch.step, step, ctx)
                if not ok then
                    result = { success = false, error = tostring(r) }
                elseif r == "shell" then
                    result = Executor.run_shell(step, ctx.mount_point)
                else
                    result = { success = true }
                end
            else
                result = { success = true }
            end
        elseif (step.program or step.command) and (step.program or step.command) ~= "" then
            -- Any other step carrying a command is a shell step (system or disk).
            result = Executor.run_shell(step, ctx.mount_point)
        elseif step.kind == "lua-system" then
            -- Lua system module: call the appropriate function from the boot module
            local ok, err = pcall(function()
                local boot = require('kod.system.boot')
                local op = step.meta and step.meta.operation
                local kernel = step.meta and step.meta.kernel
                local generation = step.meta and step.meta.generation
                
                if op == "update_kernel" then
                    boot.update_kernel(kernel, ctx.mount_point)
                elseif op == "update_initramfs" then
                    boot.update_initramfs(kernel, ctx.mount_point)
                elseif op == "create_boot_entry" then
                    boot.create_boot_entry(generation, kernel, ctx.mount_point)
                else
                    error("Unknown lua-system operation: " .. tostring(op))
                end
            end)
            
            if not ok then
                result = { success = false, error = "lua-system step failed: " .. tostring(err) }
            else
                result = { success = true }
            end
        else
            result = { success = false, error = "Unknown step kind: " .. tostring(step.kind) }
        end

        if not result.success then
            if step.on_error ~= "warn" then
                error(result.error or ("step '" .. step.name .. "' failed"))
            end
            result.is_warning = true
        end
        table.insert(results, result)

        -- post hooks: errors are swallowed (parity with Python executor)
        for _, hook in ipairs(hooks["post:" .. step.kind] or {}) do
            pcall(hook, step, ctx)
        end
    end

    return results
end

return Executor
