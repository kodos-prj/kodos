-- Program Configuration generation

-- local function string_wrap(str)
--     if str:match("^<[(].+[)]>$") then
--         return str
--     else
--         return "'"..str.."'"
--     end
-- end

local function execute(mountpoint, user)
    prefic = ""
    postfix = ""
    if #mountpoint > 0 then
        prefix = "arch-chroot " .. mountpoint .. " "
    end
    if #user > 0 then
        prefix = prefix .. "su " .. user .. " -c '"
        postfix = "'"
    end
    return function (cmd)
        return os.execute(prefix .. cmd .. postfix)
    end
end


local function dconf(config)

    local command = function (config, user, mountpoint)
        local run = execute(mountpoint, user)
        for root, key_vals in pairs(config) do
            local root_path = root:gsub('/', '.')
            for key, val in pairs(key_vals) do
                key = key:gsub("_", "-")
                if type(val) == "string" then
                    -- cmd = exec_prefix .. " dconf write " .. "/"..root.."/"..key.." \''"..val.."'\'"
                    -- local cmd = exec_prefix .. " gsettings set " ..root_path.." "..key.." '"..val.."'"
                    local cmd = "gsettings set " ..root_path.." "..key.." '"..val.."'"
                    -- exit_code = os.execute(cmd)
                    exit_code = run(cmd)
                    if exit_code ~= 0 then
                        print("Error: "..cmd)
                        os.exit(1)
                    end
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
                        -- cmd = exec_prefix .. " dconf write " .. "/"..root.."/"..key.." '"..val_list.."'"
                        -- cmd = exec_prefix .. " gsettings set " ..root_path.." "..key.." \"["..val_list.."]\""
                        cmd = "gsettings set " ..root_path.." "..key.." \"["..val_list.."]\""
                        -- exitcode = os.execute(cmd)
                        exitcode = run(cmd)
                        if exitcode ~= 0 then
                            print("Error: "..cmd)
                            os.exit(1)
                        end
                    else
                        -- list of tables
                        for kname, elem in pairs(val) do
                            for k, v in pairs(elem) do
                                -- cmd = exec_prefix .. " gsettings set " ..root_path.."."..key..":"..kname.." "..k.." '"..v.."'"
                                -- exit_code = os.execute(cmd)
                                cmd = "gsettings set " ..root_path.."."..key..":"..kname.." "..k.." '"..v.."'"
                                exit_code = run(cmd)
                                if exit_code ~= 0 then
                                    print("Error: "..cmd)
                                    os.exit(1)
                                end
                            end
                        end
                    end
                end
            end
        end
    end
    return {
        command = command;
        config = config;
    }
end


local function git(config)
    local command = function (config, user, mountpoint)
        local run = execute(mountpoint, user)
        local user_name = config.user_name
        local user_email = config.user_email
        -- os.execute(exec_prefix .. " git config --global user.name \""..user_name.."\"")
        -- os.execute(exec_prefix .. " git config --global user.email \""..user_email.."\"")
        run("git config --global user.name \""..user_name.."\"")
        run("git config --global user.email \""..user_email.."\"")
    end
    return { 
        command = command,
        config = config,
    }
end


local function syncthing(config)

    local command = function (config, user, mountpoint)
        local run = execute(mountpoint, user)
        local service_name = config.service_name
        local options = config.options
        local service_desc = [[
[Unit]
After=network.target
Description=Syncthing - Open Source Continuous File Synchronization
Documentation=man:syncthing(1)

[Service]
ExecStart='/usr/bin/syncthing' {options}
PrivateUsers=true

[Install]
WantedBy=default.target
]]
        local service_desc = service_desc:gsub("{options}", options)
        
        -- if os.execute(exec_prefix .. " mkdir -p ~/.config/systemd/user/") then
        --     os.execute(exec_prefix .. " echo \""..service_desc.."\" > ~/.config/systemd/user/"..service_name..".service")
        -- end
        if run("mkdir -p ~/.config/systemd/user/") then
            run("echo \""..service_desc.."\" > ~/.config/systemd/user/"..service_name..".service")
        end
    end

    return {
        command = command,
        config = config
    }
end

function copy_file(source)
    local command = function (exec_prefix, source, target, user)
        os.execute(exec_prefix .. " cp " .. source .. " "..target); 
    end
    return map({
        command = command;
        source = source;
    })
end


return {
    exec_prefix = exec_prefix,
    copy_file = copy_file,
    dconf = dconf,
    git = git,
    syncthing = syncthing,
}