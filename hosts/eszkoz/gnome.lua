return {
    ["/org/gnome/desktop/datetime"] = {
        automatic_timezone = true,
    },

    ["/org/gnome/Weather"] = {
        locations = "[<(uint32 2, <('Edmonton', 'CYED', true, [(0.93666003772138751, -1.9803669304139968)], [(0.93462381444296339, -1.9809487010135638)])>)>]";
    },

    ["/org/gnome/shell/extensions/user-theme"] = {
        name = 'WhiteSur-Dark-alt-grey'
    },
    ["/org/gnome/shell"] = {
        disabled_extensions = { 'apps-menu@gnome-shell-extensions.gcampax.github.com' },
        enabled_extensions = {
            'appindicatorsupport@rgcjonas.gmail.com', 
            'arcmenu@arcmenu.com', 
            'blur-my-shell@aunetx', 
            'dash-to-dock@micxgx.gmail.com', 
            'status-icons@gnome-shell-extensions.gcampax.github.com', 
            'user-theme@gnome-shell-extensions.gcampax.github.com', 
            'workspace-indicator@gnome-shell-extensions.gcampax.github.com', 
            -- 'monitor@astraext.github.io'
        },
    }
}