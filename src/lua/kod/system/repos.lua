-- Repository functions

---Create Arch official repository configuration with optional custom mirrors.
---@param mirrors string|table Optional custom mirror URL(s). Can be:
---  - Single URL string: "https://mirror.example.com/archlinux"
---  - List of URLs: { "https://mirror1.com/archlinux", "https://mirror2.com/archlinux" }
---  - nil/empty: Uses pacman's default mirrors (pre-configured in base image)
---@return table Arch repo configuration table with type="arch"
---
---Example:
---  local repos = require('repos')
---  -- Use default mirrors from pacman.conf
---  repos.arch_repo()
---  -- Use single custom mirror
---  repos.arch_repo("https://mirror.example.com/archlinux")
---  -- Use mirror list with fallbacks
---  repos.arch_repo({
---    "https://mirror1.example.com/archlinux",
---    "https://mirror2.example.com/archlinux"
---  })
local function arch_repo(mirrors)
    return {
        type = "arch",
        mirrors = mirrors,  -- nil, string, or list of mirror URLs
        repo = { "core", "extra" },
        privilege_level = "root",  -- Requires full root for pacman
        commands = {
            install = "pacman -S --noconfirm --needed",
            update = "pacman -Syu --noconfirm  --needed",
            remove = "pacman -Rscn --noconfirm",
            update_db = "pacman -Syy --noconfirm",
            run_as_root = true,
        }
    }
end

local function aur_repo(name, url, build_cmd, commands, run_as_root)
    -- Creates the repo entry for AUR packages
    --  - name: name of the package to AUR helper
    --  - url: url for the AUR helper source code
    --  - build_cmd: command to build the AUR helper
    --  - commands: list of commands to interact with the AUR helper (install, update, remove, update_db)
    --  - run_as_root: boolean to indicate if the commands should be run as root (default: true)
    local default_commands = {
        install = name .. " -S --noconfirm",
        update = name .. " -Syu --noconfirm",
        remove = name .. " -R --noconfirm",
        update_db = name .. " -Sy --noconfirm",
        run_as_root = run_as_root or true,  -- AUR helper needs root for package install
    }

    local aur = {
        type = "aur",
        privilege_level = "user",  -- AUR builds run as unprivileged user
        build = {
            name = name,
            url = url,
            build_cmd = build_cmd or "makepkg -si --noconfirm",
        },
    }
    aur.commands = commands or default_commands
    return aur
end

local function flatpak_repo(repo, run_as_root)
    -- Creates the repo entry for flatpak packages
    --  - repo: name of the flatpak repo to use (default is flathub)
    --  - run_as_root: boolean to indicate if the commands should be run as root
    repo = repo or "flathub"
    return {
        type = "flatpak",
        privilege_level = "sudo",  -- Flatpak init needs elevation, but not full root
        package = "flatpak",
        init = "flatpak remote-add --if-not-exists " .. repo .. " https://flathub.org/repo/flathub.flatpakrepo",
        commands = {
            install = "flatpak install -y " .. repo,
            update = "flatpak update -y",
            remove = "flatpak uninstall -y",
            update_db = "flatpak update -y",
            run_as_root = run_as_root or true,
        }
    }
end

local function deb_repo(mirrors)
    -- Creates the repo entry for official Debian repos
    --  - mirrors: is list of url mirror in case a particular set of mirror is required
    return {
        type = "deb",
        privilege_level = "sudo",  -- apt usually needs escalation, but not full root
        mirrors = mirrors, --"https://mirror.rackspace.com/archlinux",
        -- arch = "x86_64",
        repo = { "stable" },
        commands = {
            -- install = "DEBIAN_FRONTEND=noninteractive yes | apt install -yqq",
            install = "apt-get install -y",
            update = "apt-get reinstall -y",
            remove = "apt-get remove -y",
            update_db = "apt update -y",
        }
    }
end

local function install_cmd(distro, packages)
    -- Returns the install command for the given distro
    -- - distro: "arch" or "debian"
    -- - packages: string or list of package names (may include aur:, flatpak:, etc prefixes)
    -- Returns: install command string, or nil if distro unsupported
    
    -- TODO:
    -- ponytail: Hardcoded repo commands for aur:/flatpak: prefixes.
    -- Better: pass config.repos registry through planning so install_cmd() can look up
    -- actual repo.commands.install from aur_repo/flatpak_repo table definitions.
    -- Avoid duplicating command logic in two places. Upgrade when planner passes repos context.
    
    if not packages then
        return nil
    end
    
    -- Convert to list if string
    local pkg_list = {}
    if type(packages) == "string" then
        for pkg in packages:gmatch("%S+") do
            table.insert(pkg_list, pkg)
        end
    else
        pkg_list = packages
    end
    
    -- Separate packages by their source (arch/aur/flatpak)
    local arch_pkgs = {}
    local aur_pkgs = {}
    local flatpak_pkgs = {}
    
    for _, pkg in ipairs(pkg_list) do
        if pkg:find("^aur:") then
            local name = pkg:sub(5)  -- Remove "aur:" prefix
            table.insert(aur_pkgs, name)
        elseif pkg:find("^flatpak:") then
            local name = pkg:sub(10)  -- Remove "flatpak:" prefix
            table.insert(flatpak_pkgs, name)
        else
            table.insert(arch_pkgs, pkg)
        end
    end
    
    local commands = {}
    
    if distro == "arch" then
        if #arch_pkgs > 0 then
            table.insert(commands, "pacman -S --noconfirm " .. table.concat(arch_pkgs, " "))
        end
        if #aur_pkgs > 0 then
            -- ponytail: Skip AUR packages silently in install (would need yay/paru in chroot).
            -- They don't break the build; just not installed. Defensive skip.
        end
        if #flatpak_pkgs > 0 then
            -- ponytail: Skip flatpak app packages during rebuild (can't initialize in chroot).
            -- Apps are deferred to post-boot via kod-flatpak-install systemd service.
            -- Only the flatpak package itself (installed via arch repos) is available in image.
        end
        if #commands > 0 then
            return table.concat(commands, " && ")
        end
        return nil
    elseif distro == "debian" then
        if #arch_pkgs > 0 then
            return "apt-get install -y " .. table.concat(arch_pkgs, " ")
        end
    end
    return nil
end

local function remove_cmd(distro, packages)
    -- Returns the remove command for the given distro
    -- - distro: "arch" or "debian"
    -- - packages: string or list of package names (may include aur:, flatpak:, etc prefixes)
    -- Returns: remove command string, or nil if distro unsupported
    
    -- ponytail: Hardcoded repo commands (see install_cmd for upgrade path)
    
    if not packages then
        return nil
    end
    
    -- Convert to list if string
    local pkg_list = {}
    if type(packages) == "string" then
        for pkg in packages:gmatch("%S+") do
            table.insert(pkg_list, pkg)
        end
    else
        pkg_list = packages
    end
    
    -- Separate packages by their source
    local arch_pkgs = {}
    local aur_pkgs = {}
    local flatpak_pkgs = {}
    
    for _, pkg in ipairs(pkg_list) do
        if pkg:find("^aur:") then
            local name = pkg:sub(5)  -- Remove "aur:" prefix
            table.insert(aur_pkgs, name)
        elseif pkg:find("^flatpak:") then
            local name = pkg:sub(10)  -- Remove "flatpak:" prefix
            table.insert(flatpak_pkgs, name)
        else
            table.insert(arch_pkgs, pkg)
        end
    end
    
    local commands = {}
    
    if distro == "arch" then
        if #arch_pkgs > 0 then
            table.insert(commands, "pacman -Rscn --noconfirm " .. table.concat(arch_pkgs, " "))
        end
        if #aur_pkgs > 0 then
            -- Skip AUR packages silently (would need yay/paru)
        end
        if #flatpak_pkgs > 0 then
            -- Skip flatpak packages silently (can't work in chroot)
        end
        if #commands > 0 then
            return table.concat(commands, " && ")
        end
        return nil
    elseif distro == "debian" then
        if #arch_pkgs > 0 then
            return "apt-get remove -y " .. table.concat(arch_pkgs, " ")
        end
    end
    return nil
end

local function update_cmd(distro)
    -- Returns the full system update command for the given distro
    -- - distro: "arch" or "debian"
    -- Returns: update command string, or nil if distro unsupported
    if distro == "arch" then
        return "pacman -Syu --noconfirm --needed"
    elseif distro == "debian" then
        return "apt-get upgrade -y"
    end
    return nil
end

-- Repo step generation functions: emit install steps for a given repo type and distro
-- Used by sections/repos.lua to generate repo setup steps

-- TODO: Move this function as part of arch_repo
local function emit_arch_repo_steps(repo_name, repo_config)
    -- Emit steps to configure Arch official repo mirrors
    -- If repo_config.mirrors is provided, generates step to write mirror list to pacman.conf
    -- repo_config.mirrors can be: nil (use defaults), string (single mirror), or list of mirrors
    
    if not repo_config.mirrors then
        -- No custom mirrors; use pacman's defaults (already in base image)
        return {}
    end
    
    -- Convert single string mirror to list for uniform handling
    local mirror_list = {}
    if type(repo_config.mirrors) == "string" then
        table.insert(mirror_list, repo_config.mirrors)
    elseif type(repo_config.mirrors) == "table" then
        mirror_list = repo_config.mirrors
    else
        return {}
    end
    
    if #mirror_list == 0 then
        return {}
    end
    
    -- Build pacman.conf mirror list (preserve Server = format for each mirror)
    local mirror_lines = {}
    for _, mirror_url in ipairs(mirror_list) do
        table.insert(mirror_lines, "Server = " .. mirror_url)
    end
    local mirrors_config = table.concat(mirror_lines, "\n")
    
    -- Generate step: append mirror list to pacman.conf [core] and [extra] sections
    -- ponytail: Simple append; assumes pacman.conf has these sections already.
    -- Better: parse and update only the target sections if they change. Defer when needed.
    return {
        {
            name = "repos_arch_mirrors_" .. repo_name,
            description = "Configure Arch mirrors in pacman.conf",
            -- Append our mirrors after the [core] section (they apply to all repos)
            command = "echo '\n# Custom mirrors for Arch repos' >> /etc/pacman.conf && echo '" .. mirrors_config .. "' >> /etc/pacman.conf",
            order = 50,
        }
    }
end

-- TODO: Move this function as part of aur_repo
local function emit_aur_repo_steps(repo_name, repo_config)
    -- Emit steps to install AUR helper (yay, paru, etc)
    -- repo_config.build.name, .url, .build_cmd
    if not repo_config.build or not repo_config.build.url then
        return {}
    end
    return {
        {
            name = "repos_aur_" .. repo_name,
            description = "Install AUR helper: " .. (repo_config.build.name or repo_name),
            command = "cd /tmp && git clone " .. repo_config.build.url .. " && cd " .. (repo_config.build.name or repo_name) .. " && " .. (repo_config.build.build_cmd or "makepkg -si --noconfirm"),
            order = 50,
        }
    }
end

local function emit_flatpak_repo_steps(repo_name, repo_config)
    -- Emit steps to initialize flatpak repo
    -- repo_config.init has the remote-add command
    if not repo_config.init then
        return {}
    end
    return {
        {
            name = "repos_flatpak_" .. repo_name,
            description = "Add flatpak remote: " .. repo_name,
            command = repo_config.init,
            order = 50,
        }
    }
end

local function emit_deb_repo_steps(repo_name, repo_config)
    -- Emit steps to add Debian repo
    -- ponytail: Skip unless repo_config has custom URL or PPA; default repos pre-configured
    -- Add when: custom repo URLs need adding
    return {}
end

local function emit_repo_steps(repo_name, repo_config, distro)
    -- Dispatch to repo-type-specific emit function
    -- Returns: list of step tables, or empty list if no setup needed
    if not repo_config or not repo_config.type then
        return {}
    end
    
    if repo_config.type == "arch" then
        return emit_arch_repo_steps(repo_name, repo_config)
    elseif repo_config.type == "aur" then
        return emit_aur_repo_steps(repo_name, repo_config)
    elseif repo_config.type == "flatpak" then
        return emit_flatpak_repo_steps(repo_name, repo_config)
    elseif repo_config.type == "deb" then
        return emit_deb_repo_steps(repo_name, repo_config)
    end
    
    return {}
end

return {
    arch_repo = arch_repo,
    aur_repo = aur_repo,
    flatpak_repo = flatpak_repo,
    deb_repo = deb_repo,
    install_cmd = install_cmd,
    remove_cmd = remove_cmd,
    update_cmd = update_cmd,
    emit_repo_steps = emit_repo_steps,
}
