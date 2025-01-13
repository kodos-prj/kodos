-- Program Configuration generation


local function stow(config)
    local command = function (context, config, program, init)
        local source = config.source_dir or "~/dotfiles"
        local target = config.target_dir or "~"
        
        local git_clone = "git clone " .. config.repo_url .. " " .. source
        
        if init and context:execute("if [ ! -d "..source.." ] ; then\n"..git_clone.."\nfi") then
            print("Error: "..git_clone)
            os.exit(1)
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
                if type(val) == "string" then
                    local cmd = "gsettings set " ..root_path.." "..key.." '"..val.."'"
                    exit_code = context:execute(cmd)
                    -- if exit_code ~= 0 then
                    --     print("Error: "..cmd)
                    --     os.exit(1)
                    -- end
                end
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
            -- context:execute("echo \""..service_desc.."\" > ~/.config/systemd/user/"..service_name..".service")
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
        command = command;
        source = source;
        stages = { "install", "rebuild-user" };
    }
end


return {
    stow = stow,
    copy_file = copy_file,
    dconf = dconf,
    git = git,
    syncthing = syncthing,
}