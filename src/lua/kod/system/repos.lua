-- Repository functions

local function arch_repo(mirrors)
    -- Creates the repo entry for official arch repos
    --  - mirrors: is list of url mirror in case a particular set of mirror is required
    return {
        type = "arch",
        mirrors = mirrors, --"https://mirror.rackspace.com/archlinux",
        -- arch = "x86_64",
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
            table.insert(commands, "flatpak install -y flathub " .. table.concat(flatpak_pkgs, " "))
        end
        return table.concat(commands, " && ") or nil
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
            table.insert(commands, "flatpak uninstall -y " .. table.concat(flatpak_pkgs, " "))
        end
        return table.concat(commands, " && ") or nil
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

return {
    arch_repo = arch_repo,
    aur_repo = aur_repo,
    flatpak_repo = flatpak_repo,
    deb_repo = deb_repo,
    install_cmd = install_cmd,
    remove_cmd = remove_cmd,
    update_cmd = update_cmd,
}
