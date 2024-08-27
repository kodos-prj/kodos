print("config.lua")
-- require("core.lua")

return {
    -- source = {
    --     url = "https://mirror.rackspace.com/archlinux",
    --     arch = "x86_64",
    --     repo = { "core", "extra" },
    --     -- repo = {"core" },
    --     type = "arch",
    -- },
    source = {
        -- url = "http://ftp.ca.debian.org/debian/dists/stable/main/binary-amd64/Packages.gz",
        url = "http://ftp.ca.debian.org/debian/dists/stable/",
        -- url2 = "https://mirror.rackspace.com/archlinux",
        arch = "amd64",
        -- repo = { "main", "contrib" },
        repo = {"main" },
        type = "deb",
    },


    packages = {
        -- "base",
        "bash",
        "linux",
        "python",
        -- "python-pip",
        -- "python-virtualenv",
        -- "python-hatch",
        -- "python-lupa",
        -- "python-requests",
        -- "python-click",
        -- "python-pyzstd",
        "grep",
        "mc",
        "systemd",
        -- "openssl",
        -- "neovim",
        -- "libvterm",
        -- "lua51-lpeg",
        -- "ca-certificates-utils",
        -- "p11-kit",
        -- "libp11-kit"
    }
}
