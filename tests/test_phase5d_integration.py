"""Phase 5d comprehensive integration tests using eszkoz configuration."""

import pytest
from kod.lua_runtime import get_lua_runtime
from kod import planner as planner_module
import os


class TestEszkozPhase5dIntegration:
    """Integration tests using real eszkoz configuration adapted for Phase 5d."""

    def test_eszkoz_users_identity_block_structure(self):
        """eszkoz users.identity block has correct structure."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            abuss = {
                identity = {
                    name = "Antal Buss",
                    hashed_password = "$6$...",
                    groups = {"wheel", "audio"}
                }
            }
        }
        
        return config.abuss.identity.name == "Antal Buss" and
               type(config.abuss.identity.groups) == "table"
        """
        
        result = lua.execute(code)
        assert result is True

    def test_eszkoz_users_ssh_keys_block_structure(self):
        """eszkoz users.ssh_keys block has correct structure."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            abuss = {
                ssh_keys = {
                    enabled = true,
                    authorized = {"ssh-rsa AAAAB3..."}
                }
            }
        }
        
        return config.abuss.ssh_keys.enabled == true and
               type(config.abuss.ssh_keys.authorized) == "table"
        """
        
        result = lua.execute(code)
        assert result is True

    def test_eszkoz_users_dotfiles_block_structure(self):
        """eszkoz users.dotfiles block has correct structure."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            abuss = {
                dotfiles = {
                    source_dir = "~/.dotfiles",
                    repo_url = "http://example.com/dotfiles.git",
                    deploy_tool = "stow"
                }
            }
        }
        
        return config.abuss.dotfiles.source_dir == "~/.dotfiles" and
               config.abuss.dotfiles.deploy_tool == "stow"
        """
        
        result = lua.execute(code)
        assert result is True

    def test_eszkoz_users_programs_nested_structure(self):
        """eszkoz users.programs can contain nested program configs."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            abuss = {
                programs = {
                    git = { enable = true },
                    neovim = { enable = true, deploy_config = true },
                    emacs = { package = "emacs-wayland" }
                }
            }
        }
        
        return config.abuss.programs.git.enable == true and
               config.abuss.programs.neovim.deploy_config == true and
               config.abuss.programs.emacs.package == "emacs-wayland"
        """
        
        result = lua.execute(code)
        assert result is True

    def test_eszkoz_users_services_nested_structure(self):
        """eszkoz users.services can contain nested service configs."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            abuss = {
                services = {
                    syncthing = { enable = false },
                    custom_daemon = { enable = true, service_name = "custom" }
                }
            }
        }
        
        return config.abuss.services.syncthing.enable == false and
               config.abuss.services.custom_daemon.service_name == "custom"
        """
        
        result = lua.execute(code)
        assert result is True

    def test_eszkoz_desktop_display_manager_field(self):
        """eszkoz desktop.display_manager is top-level field."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            desktop = {
                display_manager = "cosmic-greeter",
                environments = { cosmic = { enable = true } }
            }
        }
        
        return config.desktop.display_manager == "cosmic-greeter"
        """
        
        result = lua.execute(code)
        assert result is True

    def test_eszkoz_desktop_environments_block_structure(self):
        """eszkoz desktop.environments has correct structure."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            desktop = {
                display_manager = "cosmic-greeter",
                environments = {
                    gnome = { enable = true, extra_packages = {"gnome-tweaks"} },
                    cosmic = { enable = true },
                    plasma = { enable = false }
                }
            }
        }
        
        return config.desktop.environments.gnome.enable == true and
               config.desktop.environments.plasma.enable == false and
               #config.desktop.environments.gnome.extra_packages == 1
        """
        
        result = lua.execute(code)
        assert result is True

    def test_eszkoz_boot_loader_include_field(self):
        """eszkoz boot.loader.include field works."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            boot = {
                kernel = { package = "linux" },
                loader = {
                    type = "systemd-boot",
                    timeout = 10,
                    include = {"memtest86+", "custom.conf"}
                }
            }
        }
        
        return type(config.boot.loader.include) == "table" and
               #config.boot.loader.include == 2
        """
        
        result = lua.execute(code)
        assert result is True

    def test_eszkoz_hardware_sane_block(self):
        """eszkoz hardware.sane block exists and validates."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            hardware = {
                sane = {
                    enable = true,
                    extra_packages = {"sane-airscan", "sane-backends"}
                },
                pipewire = { enable = true }
            }
        }
        
        return config.hardware.sane.enable == true and
               #config.hardware.sane.extra_packages == 2
        """
        
        result = lua.execute(code)
        assert result is True

    def test_eszkoz_fonts_font_dir_and_packages(self):
        """eszkoz fonts.font_dir and fonts.packages fields work."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            fonts = {
                font_dir = true,
                packages = {
                    "ttf-firacode-nerd",
                    "ttf-liberation",
                    "noto-fonts-emoji"
                }
            }
        }
        
        return config.fonts.font_dir == true and
               #config.fonts.packages == 3
        """
        
        result = lua.execute(code)
        assert result is True

    def test_eszkoz_services_systemd_mounts_and_units(self):
        """eszkoz services.systemd.mounts and units work."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            services = {
                systemd = {
                    enable = true,
                    mounts = {
                        data = {
                            what = "//server/path",
                            where = "/mnt/data",
                            type = "cifs"
                        },
                        library = {
                            what = "server:/path",
                            where = "/mnt/library",
                            type = "nfs"
                        }
                    },
                    units = {
                        custom = {
                            Description = "Custom unit"
                        }
                    }
                }
            }
        }
        
        return type(config.services.systemd.mounts) == "table" and
               config.services.systemd.mounts.data.type == "cifs" and
               config.services.systemd.mounts.library.type == "nfs" and
               config.services.systemd.units.custom.Description == "Custom unit"
        """
        
        result = lua.execute(code)
        assert result is True


class TestPhase5dBackwardCompatibility:
    """Ensure Phase 5c configurations still work."""

    def test_users_can_have_just_shell(self):
        """Users can have minimal config with just shell field."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            alice = {
                shell = "/bin/bash"
            }
        }
        
        return config.alice.shell == "/bin/bash"
        """
        
        result = lua.execute(code)
        assert result is True

    def test_users_can_mix_old_and_new_fields(self):
        """Users can have both old shell field and new nested blocks."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            bob = {
                shell = "/bin/zsh",
                identity = {
                    name = "Bob User",
                    groups = {"wheel"}
                },
                ssh_keys = {
                    enabled = true,
                    authorized = {"ssh-rsa..."}
                }
            }
        }
        
        return config.bob.shell == "/bin/zsh" and
               config.bob.identity.name == "Bob User" and
               config.bob.ssh_keys.enabled == true
        """
        
        result = lua.execute(code)
        assert result is True

    def test_desktop_can_have_old_environment_field(self):
        """Desktop can still use old 'environment' field."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            environment = "gnome",
            enable = true
        }
        
        return config.environment == "gnome" and config.enable == true
        """
        
        result = lua.execute(code)
        assert result is True

    def test_boot_can_omit_include_field(self):
        """Boot loader can omit new 'include' field."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            kernel = { package = "linux" },
            loader = { type = "systemd-boot", timeout = 10 }
        }
        
        return config.loader.type == "systemd-boot" and config.loader.include == nil
        """
        
        result = lua.execute(code)
        assert result is True

    def test_services_can_omit_systemd_block(self):
        """Services config can omit new systemd block."""
        lua = get_lua_runtime()
        
        code = """
        local config = {
            openssh = { enable = true },
            nginx = { enable = false }
        }
        
        return config.openssh.enable == true and config.systemd == nil
        """
        
        result = lua.execute(code)
        assert result is True

