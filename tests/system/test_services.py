"""Tests for kod/system/services.py (Phase 2)."""

import pytest
from unittest.mock import MagicMock, patch, call


class TestServiceManagement:
    """Test service operations."""

    def test_enable_services_callable(self):
        """enable_services() is callable."""
        from kod.system.services import enable_services
        
        assert callable(enable_services)

    def test_disable_services_callable(self):
        """disable_services() is callable."""
        from kod.system.services import disable_services
        
        assert callable(disable_services)

    def test_enable_user_services_callable(self):
        """enable_user_services() is callable."""
        from kod.system.services import enable_user_services
        
        assert callable(enable_user_services)

    def test_get_services_to_enable_callable(self):
        """get_services_to_enable() is callable."""
        from kod.system.services import get_services_to_enable
        
        assert callable(get_services_to_enable)


class TestEnableServicesFromPrograms:
    """Test enable_services_from_programs() - new Phase 3 Part 2 functionality."""

    def test_enable_services_from_programs_callable(self):
        """enable_services_from_programs() is callable."""
        from kod.system.services import enable_services_from_programs
        
        assert callable(enable_services_from_programs)

    def test_enable_services_from_programs_extracts_services(self):
        """Extract service names from compiled programs."""
        from kod.system.services import enable_services_from_programs
        
        compiled = {
            "programs": {
                "openssh": {
                    "program": MagicMock(),
                    "service": {
                        "enable": True,
                        "service_name": "sshd"
                    }
                },
                "syncthing": {
                    "program": MagicMock(),
                    "service": {
                        "enable": True,
                        "service_name": "syncthing"
                    }
                },
                "git": {
                    "program": MagicMock(),
                    # No service field
                }
            }
        }
        
        with patch("kod.system.services.enable_services") as mock_enable:
            enable_services_from_programs(compiled)
            
            # Should call enable_services with extracted service names
            mock_enable.assert_called_once()
            args = mock_enable.call_args[0]
            services = args[0]
            
            # Both services should be enabled
            assert "sshd" in services
            assert "syncthing" in services
            assert len(services) == 2

    def test_enable_services_from_programs_respects_enable_flag(self):
        """Only enable services with enable=true."""
        from kod.system.services import enable_services_from_programs
        
        compiled = {
            "programs": {
                "openssh": {
                    "program": MagicMock(),
                    "service": {
                        "enable": True,
                        "service_name": "sshd"
                    }
                },
                "cups": {
                    "program": MagicMock(),
                    "service": {
                        "enable": False,  # Disabled
                        "service_name": "cupsd"
                    }
                }
            }
        }
        
        with patch("kod.system.services.enable_services") as mock_enable:
            enable_services_from_programs(compiled)
            
            args = mock_enable.call_args[0]
            services = args[0]
            
            # Only sshd should be enabled
            assert "sshd" in services
            assert "cupsd" not in services
            assert len(services) == 1

    def test_enable_services_from_programs_no_programs_section(self):
        """Handle compiled config with no programs section."""
        from kod.system.services import enable_services_from_programs
        
        compiled = {}  # No programs section
        
        with patch("kod.system.services.enable_services") as mock_enable:
            enable_services_from_programs(compiled)
            
            # Should not call enable_services if no programs
            mock_enable.assert_not_called()

    def test_enable_services_from_programs_no_services(self):
        """Handle programs with no services defined."""
        from kod.system.services import enable_services_from_programs
        
        compiled = {
            "programs": {
                "git": {
                    "program": MagicMock(),
                    # No service field
                },
                "neovim": {
                    "program": MagicMock(),
                    # No service field
                }
            }
        }
        
        with patch("kod.system.services.enable_services") as mock_enable:
            enable_services_from_programs(compiled)
            
            # Should not call enable_services if no services to enable
            mock_enable.assert_not_called()

    def test_enable_services_from_programs_with_mount_point(self):
        """Pass mount_point to enable_services()."""
        from kod.system.services import enable_services_from_programs
        
        compiled = {
            "programs": {
                "openssh": {
                    "program": MagicMock(),
                    "service": {
                        "enable": True,
                        "service_name": "sshd"
                    }
                }
            }
        }
        
        with patch("kod.system.services.enable_services") as mock_enable:
            enable_services_from_programs(compiled, mount_point="/custom/mount")
            
            # Should pass mount_point to enable_services
            mock_enable.assert_called_once()
            _, kwargs = mock_enable.call_args
            assert kwargs.get("mount_point") == "/custom/mount"

    def test_enable_services_from_programs_with_chroot(self):
        """Pass use_chroot flag to enable_services()."""
        from kod.system.services import enable_services_from_programs
        
        compiled = {
            "programs": {
                "openssh": {
                    "program": MagicMock(),
                    "service": {
                        "enable": True,
                        "service_name": "sshd"
                    }
                }
            }
        }
        
        with patch("kod.system.services.enable_services") as mock_enable:
            enable_services_from_programs(compiled, use_chroot=True)
            
            # Should pass use_chroot to enable_services
            mock_enable.assert_called_once()
            _, kwargs = mock_enable.call_args
            assert kwargs.get("use_chroot") is True

    def test_enable_services_from_programs_system_level(self):
        """System-level services enabled in correct order."""
        from kod.system.services import enable_services_from_programs
        
        compiled = {
            "programs": {
                "openssh": {
                    "program": MagicMock(name="openssh"),
                    "service": {
                        "enable": True,
                        "service_name": "sshd"
                    }
                },
                "networkmanager": {
                    "program": MagicMock(name="networkmanager"),
                    "service": {
                        "enable": True,
                        "service_name": "NetworkManager"
                    }
                },
                "cups": {
                    "program": MagicMock(name="cups"),
                    "service": {
                        "enable": True,
                        "service_name": "cupsd"
                    }
                }
            }
        }
        
        with patch("kod.system.services.enable_services") as mock_enable:
            enable_services_from_programs(compiled)
            
            args = mock_enable.call_args[0]
            services = args[0]
            
            # All three services should be enabled
            assert len(services) == 3
            assert set(services) == {"sshd", "NetworkManager", "cupsd"}

    def test_enable_services_from_programs_empty_services_list(self):
        """Handle when no services meet enable criteria."""
        from kod.system.services import enable_services_from_programs
        
        compiled = {
            "programs": {
                "openssh": {
                    "program": MagicMock(),
                    "service": {
                        "enable": False,
                        "service_name": "sshd"
                    }
                }
            }
        }
        
        with patch("kod.system.services.enable_services") as mock_enable:
            enable_services_from_programs(compiled)
            
            # Should not call enable_services if list is empty
            mock_enable.assert_not_called()

    def test_enable_services_from_programs_missing_service_name(self):
        """Handle services with missing service_name gracefully."""
        from kod.system.services import enable_services_from_programs
        
        compiled = {
            "programs": {
                "bad_service": {
                    "program": MagicMock(),
                    "service": {
                        "enable": True,
                        "service_name": None  # Missing
                    }
                },
                "good_service": {
                    "program": MagicMock(),
                    "service": {
                        "enable": True,
                        "service_name": "good-svc"
                    }
                }
            }
        }
        
        with patch("kod.system.services.enable_services") as mock_enable:
            enable_services_from_programs(compiled)
            
            args = mock_enable.call_args[0]
            services = args[0]
            
            # Only good_service should be enabled
            assert "good-svc" in services
            assert len(services) == 1

    def test_enable_services_from_programs_installation_order(self):
        """Test typical installation workflow order."""
        from kod.system.services import enable_services_from_programs
        
        # Simulate what would be passed during installation:
        # 1. System packages installed
        # 2. System services compiled
        # 3. Now enable services before creating users
        compiled = {
            "programs": {
                "openssh": {
                    "program": MagicMock(),
                    "scope": "system",
                    "service": {
                        "enable": True,
                        "service_name": "sshd",
                        "restart_policy": "always"
                    }
                },
                "syncthing": {
                    "program": MagicMock(),
                    "scope": "both",
                    "service": {
                        "enable": True,
                        "service_name": "syncthing",
                        "user_service": True
                    }
                },
                "git": {
                    "program": MagicMock(),
                    "scope": "user",
                    # No service - user-level only
                }
            }
        }
        
        with patch("kod.system.services.enable_services") as mock_enable:
            # Enable system services
            enable_services_from_programs(compiled, use_chroot=True)
            
            # Should have enabled system services before user creation
            mock_enable.assert_called_once()
            args = mock_enable.call_args[0]
            services = args[0]
            
            # Both sshd and syncthing at system level
            assert "sshd" in services
            assert "syncthing" in services
            assert len(services) == 2
            
            # Check chroot flag was passed
            _, kwargs = mock_enable.call_args
            assert kwargs.get("use_chroot") is True

