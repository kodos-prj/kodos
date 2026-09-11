-- Locale section module - language, timezone, and keymap configuration
-- Handles locale generation, timezone symlink, and console keymap setup

local Schema = require('kod.lib.schema')

local module = {
    schema = Schema.locale,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
        -- Locale configuration
        if config.locale then
            local default_locale = config.locale.default or "en_US.UTF-8 UTF-8"
            
            -- Generate default locale
            table.insert(steps, {
                name = "locale_generate_default",
                description = "Generate default locale: " .. default_locale,
                command = "echo '" .. default_locale .. "' >> /etc/locale.gen && locale-gen",
                chroot = true,
                order = 150,
            })
            
            -- Set default locale
            table.insert(steps, {
                name = "locale_set_default",
                description = "Set default system locale",
                command = "echo 'LANG=" .. (default_locale:gsub(" .*", "")) .. "' > /etc/locale.conf",
                chroot = true,
                order = 151,
                depends_on = {"locale_generate_default"},
            })
            
            -- Generate extra locales
            if config.locale.extra_generate and #config.locale.extra_generate > 0 then
                for _, locale_str in ipairs(config.locale.extra_generate) do
                    table.insert(steps, {
                        name = "locale_generate_extra_" .. locale_str:gsub("[^%w]", "_"),
                        description = "Generate extra locale: " .. locale_str,
                        command = "echo '" .. locale_str .. "' >> /etc/locale.gen && locale-gen",
                        chroot = true,
                        order = 152,
                        depends_on = {"locale_generate_default"},
                    })
                end
            end
            
            -- Set extra locale environment variables
            if config.locale.extra_settings then
                local env_vars = {}
                for key, value in pairs(config.locale.extra_settings) do
                    table.insert(env_vars, "echo '" .. key .. "=" .. value .. "' >> /etc/locale.conf")
                end
                
                if #env_vars > 0 then
                    table.insert(steps, {
                        name = "locale_set_extra_vars",
                        description = "Set extra locale environment variables",
                        command = table.concat(env_vars, " && "),
                        chroot = true,
                        order = 153,
                        depends_on = {"locale_set_default"},
                    })
                end
            end
        end
        
        -- Timezone configuration
        if config.timezone then
            table.insert(steps, {
                name = "locale_timezone_set",
                description = "Set system timezone to " .. config.timezone,
                command = "ln -sf /usr/share/zoneinfo/" .. config.timezone .. " /etc/localtime",
                chroot = true,
                order = 160,
            })
            
            -- Sync hardware clock
            table.insert(steps, {
                name = "locale_hwclock_sync",
                description = "Synchronize hardware clock",
                command = "hwclock --systohc",
                chroot = true,
                order = 161,
                depends_on = {"locale_timezone_set"},
            })
        end
        
        -- Console keymap configuration
        if config.keymap and config.keymap ~= "us" then
            local keymap_cmd
            if distro == "arch" then
                keymap_cmd = "echo 'KEYMAP=" .. config.keymap .. "' > /etc/vconsole.conf"
            elseif distro == "debian" then
                keymap_cmd = "setupcon --keyboard-only"
            else
                return steps
            end
            
            table.insert(steps, {
                name = "locale_keymap_set",
                description = "Set console keymap to " .. config.keymap,
                command = keymap_cmd,
                chroot = true,
                order = 170,
            })
        end
        
        return steps
    end
}

return module
