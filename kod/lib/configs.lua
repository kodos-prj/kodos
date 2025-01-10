-- Program Configuration generation

local function string_wrap(str)
    if str:match("^<[(].+[)]>$") then
        return str
    else
        return "'"..str.."'"
    end
end


function dconf(config)
    local commands = list({})
    for root, key_vals in pairs(config) do
        for key, val in pairs(key_vals) do
            key = key:gsub("_", "-")
            if type(val) == "string" then
                cmd = "dconf write " .. "/"..root.."/"..key.." \"'"..val.."'\""
                commands = commands .. { cmd }
            end
            if type(val) == "table" then
                val_list = "["
                for i, elem in pairs(val) do
                    val_list = val_list .. string_wrap(elem)
                    if i < #val then
                        val_list = val_list ..","
                    end
                end
                val_list = val_list .."]"
                cmd = "dconf write " .. "/"..root.."/"..key.." \""..val_list.."\""
                commands = commands .. { cmd }
            end
        end
    end

    tmpfile = "._tmp_user_dconf.tmp"
    -- file = io.open (tmpfile, "w")
    -- file:write(table.concat(commands, "\n"))
    -- file:close()

    commands = "cat > /tmp/"..tmpfile.." << EOL\n"..table.concat(commands, "\n").."\nEOL\n"

    return {
        command = commands.."; bash /tmp/"..tmpfile.."; rm -f /tmp/"..tmpfile;
        config = config;
    }
end


function git(config)
    user_name = config.user_name
    user_email = config.user_email
    return { 
        command = "git config --global user.name \"{user_name}\" && git config --global user.email \"{user_email}\"",
        config = config,
    }
end

function syncthing(config)
    command = [[mkdir -p ~/.config/systemd/user/ &&
cat > ~/.config/systemd/user/{service_name}.service << EOL
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

    return {
        command = command,
        config = config
    }
end

function copy_file(source)
    return map({
        command = "cp " .. source .. " {targer}",
    })
end

-- function copy_file(config)
--     source = config.source
--     target = config.target
--     return {
--         command = "cp " .. source .. " " .. target,
--         config = config
--     }
-- end

-- function user_systemd(service_name, exec_start, config)
--     options = config.options
--     config_file = [[cat > ~/.config/systemd/user//etc/${service_name}.service << EOL
-- [Install]
-- WantedBy=default.target

-- [Service]
-- ExecStart='/usr/bin/syncthing' ${options} '-no-browser' '-no-restart' '-logflags=0' '--gui-address=0.0.0.0:8384' '--no-default-folder'
-- PrivateUsers=true

-- [Unit]
-- After=network.target
-- Description=Syncthing - Open Source Continuous File Synchronization
-- Documentation=man:syncthing(1)
-- EOL]]

--     config_file = config_file:gsub("${service_name}", service_name)
--     config_file = config_file:gsub("${options}", options)
    
--     return {
--         command = config_file,
--         user = user,
--         options = options,
--     }
-- end




return {
    copy_file = copy_file,
    dconf = dconf,
    git = git,
    syncthing = syncthing,
}