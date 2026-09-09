"""Tests for kod/config/compiler.py (Phase 1 + Phase 3 Task 4)."""

import pytest


@pytest.mark.phase3
class TestCompilerSystemUserPrograms:
    """Test compiler with system-level and user-level programs (Task 4)."""
    
    def test_compiler_compiles_system_level_programs(self):
        """Compiler compiles top-level programs section with scope='system'."""
        from kod.config.compiler import compile_config
        
        config = {
            "programs": {
                "git": {
                    "user_name": "System Default",
                    "email": "system@example.com"
                }
            }
        }
        
        compiled = compile_config(config)
        
        # System program should be compiled
        assert "programs" in compiled
        assert "git" in compiled["programs"]
        
        git_compiled = compiled["programs"]["git"]
        assert "program" in git_compiled
        assert "options" in git_compiled
        assert "config" in git_compiled
        assert "scope" in git_compiled
        assert git_compiled["scope"] == "system"
    
    def test_compiler_compiles_user_level_programs(self):
        """Compiler compiles user-level programs with scope='user'."""
        from kod.config.compiler import compile_config
        
        config = {
            "users": {
                "alice": {
                    "programs": {
                        "git": {
                            "user_name": "Alice",
                            "email": "alice@example.com"
                        }
                    }
                }
            }
        }
        
        compiled = compile_config(config)
        
        # User program should be compiled
        assert "users" in compiled
        assert "alice" in compiled["users"]
        assert "programs" in compiled["users"]["alice"]
        assert "git" in compiled["users"]["alice"]["programs"]
        
        git_compiled = compiled["users"]["alice"]["programs"]["git"]
        assert "program" in git_compiled
        assert "options" in git_compiled
        assert "config" in git_compiled
        assert "scope" in git_compiled
        assert git_compiled["scope"] == "user"
    
    def test_compiler_merges_system_and_user_program(self):
        """Compiler merges system and user-level same program (user overrides)."""
        from kod.config.compiler import compile_config
        
        config = {
            "programs": {
                "git": {
                    "user_name": "System Default",
                    "email": "system@example.com"
                }
            },
            "users": {
                "alice": {
                    "programs": {
                        "git": {
                            "user_name": "Alice"
                            # Note: no email, should inherit from system
                        }
                    }
                }
            }
        }
        
        compiled = compile_config(config)
        
        # System program
        system_git = compiled["programs"]["git"]
        assert system_git["scope"] == "system"
        assert system_git["options"]["user_name"] == "System Default"
        assert system_git["options"]["email"] == "system@example.com"
        
        # User program should merge
        user_git = compiled["users"]["alice"]["programs"]["git"]
        assert user_git["scope"] == "user"
        assert "overrides_system" in user_git
        assert user_git["overrides_system"] is True
        
        # Merged options: user_name overridden, email inherited
        assert user_git["options"]["user_name"] == "Alice"
        assert user_git["options"]["email"] == "system@example.com"
    
    def test_compiler_user_overrides_all_system_options(self):
        """User options completely override system options when specified."""
        from kod.config.compiler import compile_config
        
        config = {
            "programs": {
                "syncthing": {
                    "auto_start": True,
                    "listen_address": "0.0.0.0:8384"
                }
            },
            "users": {
                "bob": {
                    "programs": {
                        "syncthing": {
                            "listen_address": "127.0.0.1:8384"
                        }
                    }
                }
            }
        }
        
        compiled = compile_config(config)
        
        # User merged options
        user_syncthing = compiled["users"]["bob"]["programs"]["syncthing"]
        
        # Should have merged options
        assert user_syncthing["options"]["auto_start"] is True  # From system
        assert user_syncthing["options"]["listen_address"] == "127.0.0.1:8384"  # From user
    
    def test_compiler_generated_config_uses_merged_options(self):
        """Generated config for merged program uses merged options."""
        from kod.config.compiler import compile_config
        
        config = {
            "programs": {
                "git": {
                    "user_name": "System Default",
                    "email": "system@example.com"
                }
            },
            "users": {
                "alice": {
                    "programs": {
                        "git": {
                            "user_name": "Alice"
                        }
                    }
                }
            }
        }
        
        compiled = compile_config(config)
        
        user_git = compiled["users"]["alice"]["programs"]["git"]
        
        # Generated config should use merged options
        assert "Alice" in user_git["config"]
        assert "system@example.com" in user_git["config"]
    
    def test_compiler_metadata_overrides_system_flag(self):
        """Compiler sets overrides_system flag correctly."""
        from kod.config.compiler import compile_config
        
        config = {
            "programs": {
                "git": {
                    "user_name": "System",
                    "email": "system@example.com"
                }
            },
            "users": {
                "alice": {
                    "programs": {
                        "git": {
                            "user_name": "Alice",
                            "email": "alice@example.com"
                        }
                    }
                },
                "bob": {
                    "programs": {
                        "neovim": {
                            "python_provider": True
                        }
                    }
                }
            }
        }
        
        compiled = compile_config(config)
        
        # alice overrides system git
        alice_git = compiled["users"]["alice"]["programs"]["git"]
        assert alice_git["overrides_system"] is True
        
        # bob's neovim doesn't override system (no system neovim)
        bob_nvim = compiled["users"]["bob"]["programs"]["neovim"]
        assert bob_nvim["overrides_system"] is False
    
    def test_compiler_compiles_order_system_then_user(self):
        """Compiler compiles system programs first, then user (needed for merge)."""
        from kod.config.compiler import compile_config
        
        config = {
            "programs": {
                "git": {
                    "user_name": "System",
                    "email": "system@example.com"
                }
            },
            "users": {
                "alice": {
                    "programs": {
                        "git": {
                            "user_name": "Alice"
                        }
                    }
                }
            }
        }
        
        # Should not raise any errors (system must be available for merge)
        compiled = compile_config(config)
        
        # Verify merge succeeded
        assert "programs" in compiled
        assert "users" in compiled
        user_git = compiled["users"]["alice"]["programs"]["git"]
        assert user_git["options"]["email"] == "system@example.com"
    
    def test_compiler_user_only_program_no_override(self):
        """User-only program shows overrides_system=False."""
        from kod.config.compiler import compile_config
        
        config = {
            "users": {
                "alice": {
                    "programs": {
                        "neovim": {
                            "python_provider": True
                        }
                    }
                }
            }
        }
        
        compiled = compile_config(config)
        
        user_nvim = compiled["users"]["alice"]["programs"]["neovim"]
        assert user_nvim["scope"] == "user"
        assert user_nvim["overrides_system"] is False
    
    def test_compiler_multiple_users_merge_independently(self):
        """Multiple users compile and merge independently."""
        from kod.config.compiler import compile_config
        
        config = {
            "programs": {
                "git": {
                    "user_name": "System",
                    "email": "system@example.com"
                }
            },
            "users": {
                "alice": {
                    "programs": {
                        "git": {
                            "user_name": "Alice"
                        }
                    }
                },
                "bob": {
                    "programs": {
                        "git": {
                            "user_name": "Bob",
                            "email": "bob@example.com"
                        }
                    }
                }
            }
        }
        
        compiled = compile_config(config)
        
        # Alice: partial override (user_name only)
        alice_git = compiled["users"]["alice"]["programs"]["git"]
        assert alice_git["options"]["user_name"] == "Alice"
        assert alice_git["options"]["email"] == "system@example.com"
        
        # Bob: full override
        bob_git = compiled["users"]["bob"]["programs"]["git"]
        assert bob_git["options"]["user_name"] == "Bob"
        assert bob_git["options"]["email"] == "bob@example.com"


class TestCompiler:
    """Test configuration compilation."""

    def test_compiler_gnome_implies_gdm(self):
        """Compiler: GNOME enabled → display_manager = gdm."""
        from kod.config.compiler import compile_config
        
        config = {
            "desktop": {
                "desktop_manager": {
                    "gnome": {
                        "enable": True,
                    }
                }
            }
        }
        
        compiled = compile_config(config)
        
        # GNOME should imply gdm
        assert compiled["desktop"]["desktop_manager"]["gnome"]["display_manager"] == "gdm"

    def test_compiler_plasma_implies_sddm(self):
        """Compiler: Plasma enabled → display_manager = sddm."""
        from kod.config.compiler import compile_config
        
        config = {
            "desktop": {
                "desktop_manager": {
                    "plasma": {
                        "enable": True,
                    }
                }
            }
        }
        
        compiled = compile_config(config)
        
        # Plasma should imply sddm
        assert compiled["desktop"]["desktop_manager"]["plasma"]["display_manager"] == "sddm"

    def test_compiler_passes_through_unchanged_config(self):
        """Compiler passes through config without dependencies."""
        from kod.config.compiler import compile_config
        
        config = {
            "hostname": "test-vm",
            "packages": ["git", "vim"],
        }
        
        compiled = compile_config(config)
        
        assert compiled["hostname"] == "test-vm"
        assert compiled["packages"] == ["git", "vim"]

    def test_compiler_handles_nested_structures(self):
        """Compiler preserves nested structures."""
        from kod.config.compiler import compile_config
        
        config = {
            "boot": {
                "kernel": {
                    "package": "linux-lts",
                    "modules": ["xhci_pci", "virtio_pci"],
                }
            }
        }
        
        compiled = compile_config(config)
        
        assert compiled["boot"]["kernel"]["package"] == "linux-lts"
        assert "xhci_pci" in compiled["boot"]["kernel"]["modules"]
