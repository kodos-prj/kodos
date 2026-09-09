"""Tests for kod/config/compiler.py (Phase 1)."""

import pytest


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
