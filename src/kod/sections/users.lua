-- Users section module - user account configuration
-- Handles user creation, shell setup, groups, and home configuration

local Schema = require('kod.lib.core.schema')

-- Run a config closure against a recording context: captures the shell
-- commands it would execute instead of running them. Planning stays
-- read-only; execution happens later via the generic chroot runner.
local function capture_commands(closure, ...)
    local cmds = {}
    -- Closures call context.execute in both dot form (execute(cmd)) and
    -- colon form (context:execute(cmd)); the command is always the last arg.
    local rec_ctx = {
        execute = function(...)
            local args = {...}
            table.insert(cmds, args[#args])
            return 0
        end,
    }
    closure(rec_ctx, ...)
    return cmds
end

-- Closures declare the stages they apply to (e.g. {"install", "rebuild-user"}).
-- Sections only run in the install flow, so keep closures that include "install".
local function applies_to_install(pconf)
    local stages = pconf.stages
    if type(stages) ~= "table" then
        return true
    end
    for _, s in pairs(stages) do
        if s == "install" then
            return true
        end
    end
    return false
end

local function emit_config_steps(steps, username, kind, name, pconf, order_base)
    local command = pconf.command
    if type(command) ~= "function" or not applies_to_install(pconf) then
        return
    end
    -- Closures receive the inner data table (pconf.config), matching
    -- configure_user_scripts which calls command(ctx, prog_config.config).
    local i = 0
    for _, cmd in ipairs(capture_commands(command, pconf.config)) do
        i = i + 1
        table.insert(steps, {
            name = "users_" .. username .. "_" .. kind .. "_" .. name .. "_" .. i,
            description = "Deploy " .. kind .. " " .. name .. " config for " .. username,
            command = cmd,
            chroot = true,
            order = order_base + i,
        })
    end
end

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

                  -- Per-user program config deployment: run each enabled
                  -- program's config closure against a recording context and
                  -- emit the captured shell commands as chroot steps.
                  local user_num = tonumber(username:match("%d+")) or 0
                  if user_config.programs and type(user_config.programs) == "table" then
                      for pname, prog in pairs(user_config.programs) do
                          if type(prog) == "table" and prog.enable and type(prog.config) == "table" then
                              emit_config_steps(steps, username, "program", pname, prog.config, 650 + user_num)
                          end
                      end
                  end

                  -- Same for per-user services that carry a config closure.
                  if user_config.services and type(user_config.services) == "table" then
                      for sname, svc in pairs(user_config.services) do
                          if type(svc) == "table" and svc.enable and type(svc.config) == "table" then
                              emit_config_steps(steps, username, "service", sname, svc.config, 660 + user_num)
                          end
                      end
                  end
              end
          end
        
        return steps
    end
}

return module
