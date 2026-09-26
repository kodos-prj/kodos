-- Packages section module - aggregates and installs system packages
-- Emits steps to install packages from aggregated config sections

local Schema = require('kod.core.schema')
local Repos = require('kod.system.repos')

-- ============================================================================
-- AGGREGATION: Collect packages from all config sections
-- ============================================================================

local function aggregate_base_packages(config)
    local packages = {}
    
    -- Base packages come from distro defaults (e.g., base, linux, grub)
    -- These are typically set in the distro schema, not user config
    -- For now, rely on packages section to be explicit
    
    return packages
end

local function aggregate_desktop_packages(config)
    local packages = {}
    
    if not config.desktop then
        return packages
    end
    
    local desktop = config.desktop
    
    -- Display manager - use rawget to safely access potentially missing keys
    local display_manager = rawget(desktop, 'display_manager')
    if display_manager then
        table.insert(packages, display_manager)
    end
    
    -- Desktop environments and extra packages (legacy desktop_manager structure)
    local desktop_manager = rawget(desktop, 'desktop_manager')
    if desktop_manager then
        for dm_name, dm_conf in pairs(desktop_manager) do
            if dm_conf.enable then
                table.insert(packages, dm_name)
                
                -- Extra packages for this desktop
                if dm_conf.extra_packages then
                    for _, pkg in pairs(dm_conf.extra_packages) do
                        table.insert(packages, pkg)
                    end
                end
            end
        end
    end
    
    -- Modern desktop environments structure
    local environments = rawget(desktop, 'environments')
    if environments then
        for env_name, env_conf in pairs(environments) do
            if env_conf.enable then
                -- Main environment package (e.g., 'gnome', 'plasma', 'cosmic')
                table.insert(packages, env_name)
                
                -- Extra packages for this environment
                if env_conf.extra_packages then
                    for _, pkg in pairs(env_conf.extra_packages) do
                        table.insert(packages, pkg)
                    end
                end
            end
        end
    end
    
    return packages
end

local function aggregate_hardware_packages(config)
    local packages = {}
    
    if not config.hardware then
        return packages
    end
    
    for hw_name, hw_conf in pairs(config.hardware) do
        if hw_conf.enable then
            -- Use custom package name if specified, otherwise hw name
            local pkg_name = hw_conf.package or hw_name
            table.insert(packages, pkg_name)
            
            -- Extra packages for this hardware
            if hw_conf.extra_packages then
                for _, pkg in pairs(hw_conf.extra_packages) do
                    table.insert(packages, pkg)
                end
            end
        end
    end
    
    return packages
end

local function aggregate_system_packages(config)
    local packages = {}
    
    if not config.packages then
        return packages
    end
    
    -- User-specified system packages
    for _, pkg in pairs(config.packages) do
        table.insert(packages, pkg)
    end
    
    return packages
end

local function aggregate_font_packages(config)
    local packages = {}
    
    if not config.fonts then
        return packages
    end
    
    if config.fonts.packages then
        for _, pkg in pairs(config.fonts.packages) do
            table.insert(packages, pkg)
        end
    end
    
    return packages
end

local function aggregate_user_program_packages(config)
    local packages = {}
    
    if not config.users then
        return packages
    end
    
    for user_name, user_conf in pairs(config.users) do
        -- User programs
        if user_conf.programs then
            for prog_name, prog_conf in pairs(user_conf.programs) do
                if prog_conf.enable then
                    -- Use custom package name if specified, otherwise prog name
                    local pkg_name = prog_conf.package or prog_name
                    table.insert(packages, pkg_name)
                    
                    -- Extra packages for this program
                    if prog_conf.extra_packages then
                        for _, pkg in pairs(prog_conf.extra_packages) do
                            table.insert(packages, pkg)
                        end
                    end
                end
            end
        end
        
        -- User services
        if user_conf.services then
            for service_name, service_conf in pairs(user_conf.services) do
                if service_conf.enable then
                    -- Use custom package name if specified, otherwise service name
                    local pkg_name = service_conf.package or service_name
                    table.insert(packages, pkg_name)
                    
                    -- Extra packages for this service
                    if service_conf.extra_packages then
                        for _, pkg in pairs(service_conf.extra_packages) do
                            table.insert(packages, pkg)
                        end
                    end
                end
            end
        end
    end
    
    return packages
end

local function aggregate_excluded_packages(config)
    local excluded = {}
    
    if not config.desktop then
        return excluded
    end
    
    local desktop = config.desktop
    
    -- Desktop environments: collect exclude_packages from each enabled environment
    local environments = rawget(desktop, 'environments')
    if environments then
        for env_name, env_conf in pairs(environments) do
            if env_conf.enable and env_conf.exclude_packages then
                for _, pkg in pairs(env_conf.exclude_packages) do
                    table.insert(excluded, pkg)
                end
            end
        end
    end
    
    return excluded
end

local function aggregate_global_program_packages(config)
    local packages = {}
    
    if not config.programs then
        return packages
    end
    
    -- Global system-level programs (not per-user). Enable semantics match
    -- sections/programs.lua: only an explicit enable=false is skipped.
    for prog_name, prog_conf in pairs(config.programs) do
        if prog_conf.enable ~= false then
            -- Use custom package name if specified, otherwise prog name
            local pkg_name = prog_conf.package or prog_name
            table.insert(packages, pkg_name)
            
            -- Extra packages for this program (e.g., printer drivers, plugins)
            if prog_conf.extra_packages then
                for _, pkg in pairs(prog_conf.extra_packages) do
                    table.insert(packages, pkg)
                end
            end
        end
    end
    
    return packages
end

local function deduplicate_packages(packages)
    local seen = {}
    local unique = {}
    
    for _, pkg in ipairs(packages) do
        if not seen[pkg] then
            seen[pkg] = true
            table.insert(unique, pkg)
        end
    end
    
    return unique
end

local function aggregate_all_packages(config)
    local packages = {}
    local excluded = {}
    
    -- Collect from all sources
    local sources = {
        aggregate_base_packages(config),
        aggregate_desktop_packages(config),
        aggregate_hardware_packages(config),
        aggregate_system_packages(config),
        aggregate_font_packages(config),
        aggregate_global_program_packages(config),
        aggregate_user_program_packages(config),
    }
    
    -- Flatten
    for _, source_packages in ipairs(sources) do
        for _, pkg in ipairs(source_packages) do
            table.insert(packages, pkg)
        end
    end
    
    -- Collect excluded packages from desktop environments
    excluded = aggregate_excluded_packages(config)
    
    -- Remove duplicates while preserving order
    packages = deduplicate_packages(packages)
    excluded = deduplicate_packages(excluded)
    
    -- Return both packages and excluded packages
    -- Lua table with both arrays: {packages={...}, excluded={...}}
    return {
        packages = packages,
        excluded = excluded,
    }
end

-- ============================================================================
-- PACKAGE FILTERING BY PREFIX
-- ============================================================================
-- Filter by prefix: no prefix = normal install, aur: = aur install, flatpak: = flatpak install

local function extract_flatpak_apps(packages)
    -- Extract flatpak app names from package list, removing 'flatpak:' prefix
    local apps = {}
    for _, pkg in ipairs(packages) do
        if type(pkg) == "string" and pkg:find("^flatpak:") then
            local app_name = pkg:sub(9)  -- Remove "flatpak:" prefix (8 chars + 1)
            table.insert(apps, app_name)
        end
    end
    return apps
end

local function separate_packages(packages)
    -- Separate packages by type: normal, aur, flatpak
    local normal_pkgs = {}
    local aur_pkgs = {}
    local flatpak_pkgs = {}
    
    for _, pkg in ipairs(packages) do
        if type(pkg) == "string" then
            if pkg:find("^aur:") then
                local name = pkg:sub(5)  -- Remove "aur:" prefix
                table.insert(aur_pkgs, name)
            elseif pkg:find("^flatpak:") then
                local name = pkg:sub(9)  -- Remove "flatpak:" prefix
                table.insert(flatpak_pkgs, name)
            else
                table.insert(normal_pkgs, pkg)
            end
        end
    end
    
    return normal_pkgs, aur_pkgs, flatpak_pkgs
end

-- ============================================================================
-- STEP EMISSION
-- ============================================================================

local module = {
    schema = Schema.packages,
    
    -- Export aggregation function for Python to call
    aggregate_packages = aggregate_all_packages,
    -- Export flatpak extraction for use by desktop.lua after aggregation
    extract_flatpak_apps = extract_flatpak_apps,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Aggregate packages from all config sections
        local pkg_data = aggregate_all_packages(config)
        local packages = pkg_data.packages
        local excluded = pkg_data.excluded
        
        if #packages == 0 then
            return steps
        end
        
        -- Separate packages by type: normal/aur/flatpak
        local normal_pkgs, aur_pkgs, flatpak_pkgs = separate_packages(packages)
        
        -- Only handle arch distro (Debian doesn't support AUR)
        if distro == "arch" then
            -- Step 1: Install normal packages + base-devel (needed to build yay) as root
            local pkgs_with_helper = {}
            for _, pkg in ipairs(normal_pkgs) do
                table.insert(pkgs_with_helper, pkg)
            end
            -- Add base-devel if there are AUR packages (needed to build from source)
            if #aur_pkgs > 0 then
                table.insert(pkgs_with_helper, "base-devel")
                table.insert(pkgs_with_helper, "git")
            end
            
            if #pkgs_with_helper > 0 then
                local install_cmd = "pacman -S --noconfirm --needed " .. table.concat(pkgs_with_helper, " ")
                table.insert(steps, {
                    name = "packages_install_normal_and_base",
                    description = "Install system packages and build dependencies",
                    command = install_cmd,
                    chroot = true,
                    order = 490,
                    timeout_s = 600,
                })
            end
            
            -- AUR packages: the kod user and AUR helper (yay) are created by the
            -- repos section's aur step (repos_aur_*), which builds the helper in
            -- kod's home. Here we only build the configured AUR packages, also
            -- from kod's home via runuser.
            for i, aur_pkg in ipairs(aur_pkgs) do
                local build_cmd = "runuser -u kod -- /bin/bash -c 'cd ~ && yay -S --noconfirm --needed \"" .. aur_pkg .. "\"'"

                table.insert(steps, {
                    name = "packages_build_aur_" .. aur_pkg,
                    description = "Build and install AUR package: " .. aur_pkg,
                    command = build_cmd,
                    chroot = true,
                    order = 500 + i,
                    timeout_s = 900,  -- 15 minutes per package
                    depends_on = {"repos_aur_aur"},
                })
            end

            -- Flatpak applications: installed in chroot after AUR packages.
            -- Requires /run mounted (devices_setup_mtab) and the flathub remote
            -- added by the repos section (repos_flatpak_init_*).
            for i, app in ipairs(flatpak_pkgs) do
                table.insert(steps, {
                    name = "packages_flatpak_install_" .. app:gsub("%W", "_"),
                    description = "Install flatpak application: " .. app,
                    command = "flatpak install -y flathub " .. app,
                    chroot = true,
                    order = 510 + i,
                    timeout_s = 600,
                })
            end
        else
            -- For Debian, just install normal packages (skip AUR)
            if #normal_pkgs > 0 then
                local install_cmd = "apt-get install -y " .. table.concat(normal_pkgs, " ")
                table.insert(steps, {
                    name = "packages_install_normal",
                    description = "Install system packages",
                    command = install_cmd,
                    chroot = true,
                    order = 500,
                    timeout_s = 600,
                })
            end
        end
        
        return steps
    end
}

return module
