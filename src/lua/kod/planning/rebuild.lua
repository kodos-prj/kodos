-- Rebuild diff planner (baseline="current").
-- Pure table operations over desired vs current state; no shell calls,
-- fully deterministic and golden-testable. Emits the same step sequence
-- as the Python fallback in kod/planner.py plan_rebuild.

local Rebuild = {}
local Repos = require('kod.system.repos')
local Packages = require('kod.sections.packages')

local function to_set(list)
    local s = {}
    for _, v in ipairs(list or {}) do
        s[v] = true
    end
    return s
end

-- sorted list of keys in a - b
local function sorted_diff(a, b)
    local out = {}
    for k in pairs(a) do
        if not b[k] then
            table.insert(out, k)
        end
    end
    table.sort(out)
    return out
end

-- state: {
--   next_packages  = { packages = {...}, kernel = "..." },
--   current_packages = { packages = {...}, kernel = "..." },
--   remove_packages = {...},          -- explicit removals from config
--   next_services    = {...},
--   current_services = {...},
--   boot_generation  = <int>,         -- generation for boot entry
--   update             = bool,
--   new_generation     = bool,
--   kernel_update_required = bool,
--   config = {...},                   -- full config for emit_steps
-- }
function Rebuild.diff(state)
    local steps = {}

    local next_packages = state.next_packages or {}
    local current_packages = state.current_packages or {}
    local next_kernel = next_packages.kernel or "linux"
    local new_gen = state.new_generation
    local distro = state.distro
    local config = state.config
    local boot_generation = state.boot_generation or 0

    if state.update then
        local cmd = Repos.update_cmd(distro)
        if cmd then
            table.insert(steps, { kind = "system", name = "update-packages", command = cmd, chroot = new_gen })
        end
    end

    if not state.new_generation then
        -- Only disable services that were EXPLICITLY DISABLED in the config
        -- Do NOT disable services simply missing from next_services (they may be external)
        for _, svc in ipairs(state.disabled_services or {}) do
            if state.current_services then
                local current_set = to_set(state.current_services)
                if current_set[svc] then
                    table.insert(steps, { kind = "service", name = svc,
                        command = "systemctl disable --now " .. svc, chroot = false })
                end
            end
        end
    end
    
    -- Configure dracut BEFORE kernel install if kernel will be updated
    -- This must happen before package installs so the kernel post-install hook uses correct config
    if state.kernel_update_required then
        local modules = { "btrfs" }
        -- Note: state doesn't have full config, so we only include btrfs
        -- Full kernel.modules would require access to the config object
        local add_lines = {}
        for _, m in ipairs(modules) do
            table.insert(add_lines, "add_drivers+=" .. m)
        end
        local shell_lines = {}
        for _, line in ipairs(add_lines) do
            table.insert(shell_lines, "echo \"" .. line .. "\"")
        end
        local echo_commands = table.concat(shell_lines, " && ")
        
        table.insert(steps, {
            kind = "system",
            name = "boot_kernel_modules_config",
            description = "Configure initramfs modules before kernel update",
            command = "mkdir -p /etc/dracut.conf.d && (" .. echo_commands .. ") > /etc/dracut.conf.d/kodos.conf",
            chroot = new_gen,
            order = 199,
        })
    end

    local remove_set = {}
    for _, p in ipairs(sorted_diff(to_set(current_packages.packages), to_set(next_packages.packages))) do
        remove_set[p] = true
    end
    for _, p in ipairs(state.remove_packages or {}) do
        remove_set[p] = true
    end
    local removes = {}
    for p in pairs(remove_set) do
        table.insert(removes, p)
    end
    table.sort(removes)
    for _, p in ipairs(removes) do
        local cmd = Repos.remove_cmd(distro, p)
        if cmd then
            table.insert(steps, { kind = "package", name = p, command = cmd, chroot = new_gen, on_error = "warn" })
        end
    end

    -- Generate package installation steps using the packages section
    -- This handles normal/aur/flatpak packages with proper sequencing
    -- If config is provided, use emit_steps for proper AUR/flatpak handling
    -- Note: /run must be bind-mounted before AUR/flatpak steps (see devices_setup_mtab)
    if config and next_packages.packages and #next_packages.packages > 0 then
        -- Check if there are new packages to install
        local install_set = {}
        for _, p in ipairs(sorted_diff(to_set(next_packages.packages), to_set(current_packages.packages))) do
            install_set[p] = true
        end
        if state.kernel_update_required then
            install_set[next_kernel] = true
        end
        
        if next(install_set) then
            -- Call packages.emit_steps to generate proper steps
            local pkg_steps = Packages.emit_steps(config, distro) or {}
            
            -- Convert Lua steps to rebuild step format (with kind, name, etc.)
            -- NOTE: package steps do NOT include 'command' field - that stays in Lua/Python
            -- dispatch callbacks. Including command would make the Lua executor treat them
            -- as shell steps and try to run them via os.execute(), which fails for package ops
            for _, pstep in ipairs(pkg_steps) do
                table.insert(steps, {
                    kind = "package",
                    name = pstep.name or "packages",
                    description = pstep.description,
                    -- command omitted: dispatch handler in Python will use pstep.command
                    chroot = pstep.chroot or new_gen,
                    order = pstep.order,
                    timeout_s = pstep.timeout_s,
                    depends_on = pstep.depends_on,
                    on_error = pstep.on_error,
                    -- Store command in meta for dispatch callback
                    meta = { command = pstep.command },
                })
            end
        end
    else
        -- Fallback: if no config, use simple Repos.install_cmd per-package
        -- (this is the old behavior, but should not happen if config is passed)
        local install_set = {}
        for _, p in ipairs(sorted_diff(to_set(next_packages.packages), to_set(current_packages.packages))) do
            install_set[p] = true
        end
        if state.kernel_update_required then
            install_set[next_kernel] = true
        end
        local installs = {}
        for p in pairs(install_set) do
            table.insert(installs, p)
        end
        table.sort(installs)
        for _, p in ipairs(installs) do
            local cmd = Repos.install_cmd(distro, p)
            if cmd then
                table.insert(steps, { kind = "package", name = p, command = cmd, chroot = new_gen })
            end
        end
    end

    -- Flatpak apps: emitted by Packages.emit_steps above (packages_flatpak_install_*),
    -- converted through the same loop, ordered after AUR package steps.

    if state.kernel_update_required then
        table.insert(steps, { kind = "lua-system", name = "kernel-update", 
            meta = { operation = "update_kernel", kernel = next_kernel } })
        table.insert(steps, { kind = "lua-system", name = "initramfs-update", 
            meta = { operation = "update_initramfs", kernel = next_kernel } })
    end

for _, svc in ipairs(sorted_diff(to_set(state.next_services), to_set(state.current_services))) do
    table.insert(steps, { kind = "service", name = svc,
        command = "systemctl enable" .. (new_gen and "" or " --now") .. " " .. svc, chroot = new_gen })
end

    -- Boot entry only during rebuild (not during install)
    -- During install, devices section handles boot setup
    if not state.new_generation then
        table.insert(steps, { kind = "lua-system", name = "boot-entry",
            meta = { operation = "create_boot_entry", kernel = next_kernel, generation = boot_generation } })
    end

    return steps
end

return Rebuild
