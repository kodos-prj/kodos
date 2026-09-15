-- Rebuild diff planner (baseline="current").
-- Pure table operations over desired vs current state; no shell calls,
-- fully deterministic and golden-testable. Emits the same step sequence
-- as the Python fallback in kod/planner.py plan_rebuild.

local Rebuild = {}

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
--   update             = bool,
--   new_generation     = bool,
--   kernel_update_required = bool,
-- }
function Rebuild.diff(state)
    local steps = {}

    local function add(kind, name, meta, on_error)
        table.insert(steps, { kind = kind, name = name, meta = meta, on_error = on_error })
    end

    local next_packages = state.next_packages or {}
    local current_packages = state.current_packages or {}
    local next_kernel = next_packages.kernel or "linux"
    local new_gen = state.new_generation

    if state.update then
        add("system", "update-packages")
    end

if not state.new_generation then
    for _, svc in ipairs(sorted_diff(to_set(state.current_services), to_set(state.next_services))) do
        table.insert(steps, { kind = "service", name = svc,
            command = "systemctl disable --now " .. svc, chroot = false })
    end
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
        add("package", p, { action = "remove" }, "warn")
    end

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
        add("package", p, { action = "install" })
    end

    if state.kernel_update_required then
        add("system", "kernel-update", { kernel = next_kernel })
        add("system", "initramfs-update", { kernel = next_kernel })
    end

for _, svc in ipairs(sorted_diff(to_set(state.next_services), to_set(state.current_services))) do
    table.insert(steps, { kind = "service", name = svc,
        command = "systemctl enable" .. (new_gen and "" or " --now") .. " " .. svc, chroot = new_gen })
end

    add("system", "boot-entry", { kernel = next_kernel })

    return steps
end

return Rebuild
