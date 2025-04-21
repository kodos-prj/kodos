-- type = "cifs";
-- what = "//mmserver.lan/NAS1";
-- where = "/mnt/data";
-- description = "MMserverNAS1";
-- options = "vers=2.1,credentials=/etc/samba/mmserver-cred,iocharset=utf8,rw,x-systemd.automount,uid=1000";
-- after = { "network.target" };
-- wantedBy = { "multi-user.target" };


-- [Unit]
-- After=network.target
-- [Mount]
-- Type=nfs
-- Options=noatime,x-systemd.automount,noauto
-- What=homenas2.lan:/Data2/Documents
-- Where=/mnt/library


-- Automount
-- [Unit]
-- Description=Automount MMServer NAS share

-- [Automount]
-- TimeoutIdleSec=0
-- Where=/mnt/data

-- [Install]
-- WantedBy=multi-user.target


local function systemd-mount(config)
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
