-- Repository functions

function arch_repo(mirrors)
    -- Creates the repo entry for official arch repos 
    --  - mirrors: is list of url mirror in case a particular set of mirror is required
    return {
        type = "arch",
        mirrors = mirrors, --"https://mirror.rackspace.com/archlinux",
        -- arch = "x86_64",
        repo = { "core", "extra" },
        commands = {
            install = "pacman -S --noconfirm --needed",
            update = "pacman -Syu --noconfirm  --needed",
            remove = "pacman -Rscn --noconfirm",
            update_db = "pacman -Syy --noconfirm",
        }
    }
end


function aur_repo(name, url, build_cmd, commands, run_as_root)
    -- Creates the repo entry for AUR packages
    --  - name: name of the package to AUR helper
    --  - url: url for the AUR helper source code
    --  - build_cmd: command to build the AUR helper
    --  - commands: list of commands to interact with the AUR helper (install, update, remove, update_db)
    --  - run_as_root: boolean to indicate if the commands should be run as root 
    default_commands = {
        install = name .. " -S --noconfirm",
        update = name .. " -Syu --noconfirm",
        remove = name .. " -R --noconfirm",
        update_db = name .. " -Sy --noconfirm",
        run_as_root = run_as_root or false,
    }
    
    aur = {
        type = "aur",
        build = {
            name = name,
            url = url,
            build_cmd = build_cmd or "makepkg -si --noconfirm",
        },
    }
    aur.commands = commands or default_commands
    return aur
end


function flatpak_repo(repo, run_as_root)
    -- Creates the repo entry for flatpak packages
    --  - repo: name of the flatpak repo to use (default is flathub)
    --  - run_as_root: boolean to indicate if the commands should be run as root
    repo = repo or "flathub"
    return {
        type = "flatpak",
        package = "flatpak",
        commands = {
            install = "flatpak install -y " .. repo,
            update = "flatpak upgrate -y " .. repo,
            remove = "flatpak uninstall -y " .. repo,
            -- run_as_root = run_as_root or true,
        }
    }
end

return {
    arch_repo = arch_repo,
    aur_repo = aur_repo,
    flatpak_repo = flatpak_repo,
}