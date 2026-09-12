-- Users section module - user account configuration
-- Handles user creation, shell setup, groups, and home configuration

local Schema = require('kod.lib.schema')

local module = {
    schema = Schema.users,
    
    emit_steps = function(config, distro)
        local steps = {}
        
        if not config then
            return steps
        end
        
                  -- Iterate over each user account
                  -- NOTE: chroot steps are wrapped in single quotes by the executor, so
                  -- commands below may only use double quotes.
                  for username, user_config in pairs(config) do
                      if type(user_config) == "table" then
                           local identity = user_config.identity
                           local shell = (identity and identity.shell) or user_config.shell or "/bin/bash"
                           -- groups live under identity (see schema), not at the top level
                           local groups = (identity and identity.groups) or {}

                          -- Skip creating root user (already exists in base system)
                          -- Just configure it instead
                          if username ~= "root" then
                              -- Create user
                              local useradd_cmd = "useradd -m -s " .. shell .. " " .. username

                              table.insert(steps, {
                                  name = "users_create_" .. username,
                                  description = "Create user account: " .. username,
                                  command = useradd_cmd,
                                  chroot = true,
                                  order = 600 + (tonumber(username:match("%d+")) or 0),
                              })
                          else
                              -- Configure existing root user
                              table.insert(steps, {
                                  name = "users_create_" .. username,
                                  description = "Configure root user (already exists)",
                                  command = "true",  -- No-op, root already exists
                                  chroot = true,
                                  order = 600 + (tonumber(username:match("%d+")) or 0),
                              })
                          end

                          -- Set password if configured (identity.password or identity.hashed_password)
                          -- Without this the account stays locked and the greeter rejects
                          -- every password. Double quotes only (see note above); passwords
                          -- containing $ or " are not supported in the plaintext form.
                          local identity = user_config.identity
                          if type(identity) == "table" then
                              if identity.hashed_password then
                                  -- escape $ so the double-quoted sh string passes it literally
                                  local escaped_hash = identity.hashed_password:gsub("$", "\\$")
                                  table.insert(steps, {
                                      name = "users_password_" .. username,
                                      description = "Set hashed password for " .. username,
                                      command = "usermod -p \"" .. escaped_hash .. "\" " .. username,
                                      chroot = true,
                                      order = 600.5,
                                      depends_on = {"users_create_" .. username},
                                  })
                              elseif identity.password then
                                  table.insert(steps, {
                                      name = "users_password_" .. username,
                                      description = "Set password for " .. username,
                                      command = "echo \"" .. username .. ":" .. identity.password .. "\" | chpasswd",
                                      chroot = true,
                                      order = 600.5,
                                      depends_on = {"users_create_" .. username},
                                  })
                              end
                          end
                 
                 -- Add user to groups (including root if needed)
                 if #groups > 0 then
                     local groups_str = table.concat(groups, ",")
                     
                     table.insert(steps, {
                         name = "users_groups_" .. username,
                         description = "Add user " .. username .. " to groups: " .. groups_str,
                         command = "usermod -aG " .. groups_str .. " " .. username,
                         chroot = true,
                         order = 601 + (tonumber(username:match("%d+")) or 0),
                         depends_on = {"users_create_" .. username},
                     })
                 end
                 
                  -- Arch ships %wheel commented out in /etc/sudoers, so group
                  -- membership alone grants no sudo access. Uncomment the
                  -- %wheel line (and pam_wheel for su), as the original Python
                  -- installer did.
                  if #groups > 0 then
                      local has_wheel = false
                      for _, g in ipairs(groups) do
                          if g == "wheel" then has_wheel = true end
                      end
                      if has_wheel then
                          table.insert(steps, {
                              name = "users_sudoers_wheel_" .. username,
                              description = "Enable %wheel sudo access for " .. username,
                              command = "sed -i \"s/# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/\" /etc/sudoers && sed -i \"s/# auth       required   pam_wheel.so/auth       required   pam_wheel.so/\" /etc/pam.d/su",
                              chroot = true,
                              order = 602 + (tonumber(username:match("%d+")) or 0),
                              depends_on = {"users_groups_" .. username},
                          })
                      end
                  end

                  -- Configure home directory (home_programs)
                 if user_config.home_programs and type(user_config.home_programs) == "table" then
                     for program_name, program_config in pairs(user_config.home_programs) do
                         if type(program_config) == "table" then
                             -- Create home program config directory
                             local config_dir = "/home/" .. username .. "/.config/" .. program_name
                             
                             table.insert(steps, {
                                 name = "users_home_config_" .. username .. "_" .. program_name,
                                 description = "Create config directory for " .. program_name .. " in " .. username .. "'s home",
                                 command = "mkdir -p " .. config_dir .. " && chown " .. username .. ":" .. username .. " " .. config_dir,
                                 chroot = true,
                                 order = 610 + (tonumber(username:match("%d+")) or 0),
                                 depends_on = {"users_create_" .. username},
                             })
                         end
                     end
                 end
             end
         end
        
        return steps
    end
}

return module
