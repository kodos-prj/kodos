local os = require("os")

local function theme(config)
    build_fn = function(context, config)
        if config.repo_url then
            local tmp_dir = os.tmpname()
            print(tmp_dir)
            context:execute("rm -rf "..tmp_dir)
            context:execute("mkdir -p "..tmp_dir)
            context:execute("cd "..tmp_dir.." && git clone "..config.repo_url.." .")
            local cmd = "cd "..tmp_dir.." && ./install.sh "
            for key, value in pairs(config) do
                if key ~= "repo_url" then
                    if type(value) == "boolean" then
                        cmd = cmd .. " --"..key
                    else
                        cmd = cmd .. " --"..key.." "..value
                    end
                end
            end
            -- print(cmd)
            context:execute(cmd)
            context:execute("rm -rf "..tmp_dir)
        end
    end

    return {
        build = build_fn;
        config = config;
    };
end

return theme
