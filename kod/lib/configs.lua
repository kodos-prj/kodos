-- Program Configuration generation

local function isdir(spath)
    local response = os.execute( "cd " .. spath )
    if response then
      return true
    end
    return false
end



local function stow(config)
    local command = function (context, config, program, init)
        local source = config.source_dir or "~/dotfiles"
        local target = config.target_dir or "~"
        
        local git_clone = "git clone " .. config.repo_url .. " " .. source
        
        if init then
            -- context:execute("if [ ! -d "..source.." ] ; then\n"..git_clone.."\nfi")
            if not isdir(source) then
                context:execute(git_clone)
            end
        end
        context:execute("stow -R -t " .. target .. " -d " .. source .. " " .. program)
    end
    return {
        name = "stow",
        command = command;
        config = config;
        stages = { "install", "rebuild-user" };
    }
end


local function dconf(config)

    local command = function (context, config)
        for root, key_vals in pairs(config) do
            local root_path = root:gsub('/', '.')
            for key, val in pairs(key_vals) do
                key = key:gsub("_", "-")
                if type(val) == "table" then
                    -- val could be:
                    --  - list of strings
                    --  - list of tables

                    if type(val[1]) == "string" then
                        -- list of strings
                        val_list = ""
                        for i, elem in pairs(val) do
                            val_list = val_list .. "'"..elem.."'"
                            if i < #val then
                                val_list = val_list ..","
                            end
                        end
                        cmd = "gsettings set " ..root_path.." "..key.." \"["..val_list.."]\""
                        exit_code = context:execute(cmd)
                        -- if exitcode ~= 0 then
                        --     print("Error: "..cmd)
                        --     os.exit(1)
                        -- end
                    else
                        -- list of tables
                        for kname, elem in pairs(val) do
                            for k, v in pairs(elem) do
                                cmd = "gsettings set " ..root_path.."."..key..":"..kname.." "..k.." '"..v.."'"
                                exit_code = context:execute(cmd)
                                -- if exit_code ~= 0 then
                                --     print("Error: "..cmd)
                                --     os.exit(1)
                                -- end
                            end
                        end
                    end
                else
                    if type(val) == "string" then val = "'"..val.."'" end
                    sval = string.format("%s",val)
                    local cmd = "gsettings set " ..root_path.." "..key.." "..sval
                    exit_code = context:execute(cmd)
                    -- if exit_code ~= 0 then
                    --     print("Error: "..cmd)
                    --     os.exit(1)
                    -- end
                end
            end
        end
    end
    return {
        name = "dconf",
        command = command;
        config = config;
        stages = { "rebuild-user" };
    }
end


local function git(config)
    local command = function (context, config)
        local user_name = config.user_name
        local user_email = config.user_email
        context:execute("git config --global user.name \""..user_name.."\"")
        context:execute("git config --global user.email \""..user_email.."\"")
    end
    return {
        name = "git",
        command = command,
        config = config,
        stages = { "install", "rebuild-user" };
    }
end


local function syncthing(config)

    local command = function (context, config)
        local service_name = config.service_name
        local options = config.options
        local service_desc = [[cat > ~/.config/systemd/user/{service_name}.service << EOL
[Unit]
After=network.target
Description=Syncthing - Open Source Continuous File Synchronization
Documentation=man:syncthing(1)

[Service]
ExecStart='/usr/bin/syncthing' {options}
PrivateUsers=true

[Install]
WantedBy=default.target
EOL]]
        local service_desc = service_desc:gsub("{service_name}", service_name)
        local service_desc = service_desc:gsub("{options}", options)
        print("Configuring Syncthing")
        if context:execute("mkdir -p ~/.config/systemd/user/") then
            context:execute(service_desc)
        end
    end

    return {
        name = "syncthing",
        command = command;
        config = config;
        stages = { "rebuild-user" };
    }
end


function copy_file(context, source)
    local command = function (exec_prefix, source, target, user)
        context:execute("cp " .. source .. " "..target); 
    end
    return {
        name = "copy_file";
        command = command;
        source = source;
        stages = { "install", "rebuild-user" };
    }
end

-- Systemd-mount config
local function systemd_mount(config)
    local command = function (context, config)
        -- iterate over the config
        for name, conf in config.pairs() 
            local service_name = "mnt-" .. name
            local service_desc = [[cat > /etc/systemd/system/{service_name}.mount << EOL
[Unit]
After={after}
Description={description}

[Automount]
TimeoutIdleSec=0
Where={where}

[Install]
WantedBy={wanted_by}
EOL]]
            local service_desc = service_desc:gsub("{service_name}", service_name)
            for name, value in pairs(conf) do
                service_desc = service_desc:gsub("{"..name.."}", value)
            print("Configuring systemd-mount " .. service_name)
            if context:execute("mkdir -p /etc/systemd/system/") then
                context:execute(service_desc)
            end
            if config.automount then
                local automount_desc = [[cat > /etc/systemd/system/{service_name}.automount << EOL
[Unit]
After={after}
Description={description}

[Automount]
{automount_config}
Where={where}

[Install]
WantedBy={wanted_by}
EOL]]
                local automount_desc = automount_desc:gsub("{service_name}", service_name)
                for name, value in pairs(conf) do
                    automount_desc = automount_desc:gsub("{"..name.."}", value)
                
                print("Configuring systemd-automount " .. service_name)
                if context:execute("mkdir -p /etc/systemd/system/") then
                    context:execute(automount_desc)
                end
                
            end
        end
    end

    return {
        name = "systemd-mount",
        command = command;
        config = config;
        stages = { "install", "rebuild" };
    }
end


return {
    stow = stow,
    copy_file = copy_file,
    dconf = dconf,
    git = git,
    syncthing = syncthing,
    mount = systemd_mount,
}