-- Program Configuration generation

function config_git(config)
    user_name = config.user_name
    user_email = config.user_email
    return { 
        command = "git config --global user.name \"" .. user_name .. "\" && git config --global user.email \"" .. user_email .. "\""
    }
end

function user_systemd(user, service_name, config)
    options = config.options
    config_file = [[cat > ~/.config/systemd/user//etc/${service_name}.service << EOL
[Install]
WantedBy=default.target

[Service]
ExecStart='/usr/bin/syncthing' '-no-browser' '-no-restart' '-logflags=0' '--gui-address=0.0.0.0:8384' '--no-default-folder'
LockPersonality=true
MemoryDenyWriteExecute=true
NoNewPrivileges=true
PrivateUsers=true
Restart=on-failure
RestartForceExitStatus=3
RestartForceExitStatus=4
RestrictNamespaces=true
SuccessExitStatus=3
SuccessExitStatus=4
SystemCallArchitectures=native
SystemCallFilter=@system-service

[Unit]
After=network.target
Description=Syncthing - Open Source Continuous File Synchronization
Documentation=man:syncthing(1)
EOL]]

    return {
        command = config_file:gsub("${service_name}", service_name),
        user = user,
        options = options,
    }
end




return {
    config_git = config_git
}