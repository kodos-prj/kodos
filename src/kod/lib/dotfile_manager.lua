-- dotfile manager

function stow(config)
    -- TODO: Implement stow
    if config.source_dir then
        source = config.source_dir
    else
        source = "~/dotfiles"
    end

    if config.target_dir then
        target = config.target_dir
    else
        target = "~"
    end
    
    init_fn = function()
        if config.repo_url then
            git_clone = "git clone " .. config.repo_url .. " " .. source
            return "if [ ! -d "..source.." ] ; then\n"..git_clone.."\nfi"
        end
    end

    deploy_fn = function(program)
        return "stow -R -t " .. target .. " -d " .. source .. " " .. program
    end

    return {
        init = init_fn,
        deploy = deploy_fn,
        source_dir = source,
        target_dir = target
    }
end

return {
    stow = stow
}