-- Program Configuration generation

function git(config)
    user_name = config.user_name
    user_email = config.user_email
    return { 
        command = "git config --global user.name \"{user_name}\" && git config --global user.email \"{user_email}\"",
        config = config,
    }
end

function syncthing(config)
    command = [[cat > ~/.config/systemd/user//etc/{service_name}.service << EOL
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
    git = git,
    syncthing = syncthing,
}