return {
    ["org/gnome/desktop/datetime"] = {
        automatic_timezone = true;
    };

    ["org/gnome/Weather"] = {
        locations = '[<(uint32 2, <("Edmonton", "CYED", true, [(0.93666003772138751, -1.9803669304139968)], [(0.93462381444296339, -1.9809487010135638)])>)>]';
    };

    ["org/gnome/shell/extensions/user-theme"] = {
        name = 'WhiteSur-Dark-alt-grey';
    };

    ["org/gnome/shell"] = {
        disabled_extensions = { 'apps-menu@gnome-shell-extensions.gcampax.github.com' };
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
    },

    ["org/gnome/desktop/interface"] = {
        color_scheme = "prefer-dark";
        cursor_theme = "Adwaita";
        font_antialiasing = "rgba";
        font_hinting = "slight";
--     font-name = "Work Sans 11";
        gtk_theme = "Adwaita-dark";
--     icon-theme = "ePapirus-Dark";
        icon_theme='WhiteSur-dark';
    };

    ["org/gnome/mutter"] = {
        experimental_features = { 'scale-monitor-framebuffer' };
        workspaces_only_on_primary = true;
    };

    ["org/gnome/desktop/peripherals/mouse"] = {
       natural_scroll = true;
    };

    ["org/gnome/desktop/peripherals/touchpad"] = {
       two_finger_scrolling_enabled = true;
    };

    ["org/gnome/desktop/wm/keybindings"] = {
        switch_to_workspace_1 = { '<Alt>1' };
        switch_to_workspace_2 = { '<Alt>2' };
        switch_to_workspace_3 = { '<Alt>3' };
        switch_to_workspace_4 = { '<Alt>4' };
     };

    ["org/gnome/desktop/wm/preferences"] = {
        button_layout = "appmenu:minimize,maximize,close";
        focus_mode = "sloppy";
        workspace_names = { 'Workspace 1', 'Workspace 2', 'Workspace 3', 'Workspace 4' };
    };
    
    -- gsettings set org.gnome.settings-daemon.plugins.media-keys.custom_keybindings:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ name "Terminal"
    ["org/gnome/settings-daemon/plugins/media-keys"] = {
        custom_keybinding = {
            ['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/'] = {
                binding = '<Control><Alt>t';
                command = "kgx";
                name = "Terminal";
            };
        };
    };

    ["org/gnome/desktop/background"] = {
        color_shading_type = 'solid';
        picture_options = 'zoom';
        picture_uri = 'file:///home/abuss/.config/background';
        picture_uri_dark = 'file:///home/abuss/.config/background';
        primary_color = '#000000000000';
        secondary_color = '#000000000000';
    };

    ["org/gnome/shell/extensions/dash-to-dock"] = {
        -- background_opacity = 0.80000000000000004;
        custom_theme_shrink = true;
        dash_max_icon_size = 32;
        disable_overview_on_startup = true;
        -- dock_position = 'BOTTOM';
        dock_position = 'RIGHT';
        -- height_fraction=0.90000000000000002;
        -- preferred_monitor=-2;
        -- preferred_monitor_by_connector='eDP-1';
    }
    
}

-- gtk = {
--     # "org/gnome/desktop/input-sources" = {
--     #   sources = [ (mkTuple [ "xkb" "us+altgr-intl" ]) ];
--     # };
    
--     enable = true;

--     iconTheme = {
--       name = "ePapirus-Dark";
--       package = pkgs.papirus-icon-theme;
--     };

--     theme = {
--       name = "Adwaita-dark";
--       package = pkgs.nordic;
--     };

--     font = {
--       name = "Work Sans 11";
--       package = pkgs.work-sans;
--     };
--   };
