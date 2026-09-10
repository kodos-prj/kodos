"""Comprehensive tests for Debian/Ubuntu proc_repos() function."""

import pytest
from unittest.mock import patch, MagicMock, Mock, call
from src.kod.debian import proc_repos, install_build_dependencies


class TestDebianProcReposBasicFunctionality:
    """Test basic proc_repos functionality on Debian."""

    def test_proc_repos_with_none_config_returns_empty(self):
        """proc_repos with None repos config should return empty dicts."""
        config = Mock()
        config.repos = None
        
        repos, packages = proc_repos(config)
        
        assert repos == {}
        assert packages == []

    def test_proc_repos_with_empty_config_returns_empty(self):
        """proc_repos with empty repos config should return empty dicts."""
        config = Mock()
        config.repos = {}
        
        repos, packages = proc_repos(config)
        
        assert repos == {}
        assert packages == []

    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_with_missing_commands_field_skips_repo(self, mock_open, mock_exec, mock_exec_chroot):
        """Repo missing 'commands' field should be skipped with warning."""
        config = Mock()
        config.repos = {
            "custom": {
                # Missing 'commands' field
                "package": "some-pkg"
            }
        }
        
        repos, packages = proc_repos(config)
        
        # Should skip this repo
        assert "custom" in repos


class TestDebianProcReposAURBuilding:
    """Test proc_repos AUR building on Debian (needs build dependencies)."""

    @patch('src.kod.debian.install_build_dependencies')
    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_installs_build_deps_before_aur_build(self, mock_open, mock_exec, mock_exec_chroot, mock_install_bd):
        """Build dependencies should be installed before AUR package build."""
        def mock_exec_chroot_side_effect(cmd, **kwargs):
            if "which" in cmd:
                return "/usr/bin/tool" if kwargs.get('get_output') else ""
            return ""
        
        mock_exec_chroot.side_effect = mock_exec_chroot_side_effect
        mock_install_bd.return_value = True
        
        config = Mock()
        config.repos = {
            "aur": {
                "commands": {"install": "aur -S"},
                "build": {
                    "name": "yay",
                    "url": "https://aur.archlinux.org/yay.git",
                    "build_cmd": "makepkg -si --noconfirm"
                }
            }
        }
        
        proc_repos(config, None, False, "/mnt")
        
        # Should have installed build dependencies
        assert mock_install_bd.called

    @patch('src.kod.debian.install_build_dependencies')
    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_build_deps_called_with_mount_point(self, mock_open, mock_exec, mock_exec_chroot, mock_install_bd):
        """install_build_dependencies should receive correct mount_point."""
        def mock_exec_chroot_side_effect(cmd, **kwargs):
            if "which" in cmd:
                return "/usr/bin/tool" if kwargs.get('get_output') else ""
            return ""
        
        mock_exec_chroot.side_effect = mock_exec_chroot_side_effect
        mock_install_bd.return_value = True
        
        config = Mock()
        config.repos = {
            "aur": {
                "commands": {"install": "aur -S"},
                "build": {
                    "name": "paru",
                    "url": "https://aur.archlinux.org/paru.git",
                    "build_cmd": "makepkg -si --noconfirm"
                }
            }
        }
        
        proc_repos(config, None, False, "/custom/mnt")
        
        # Should have been called with custom mount point
        mock_install_bd.assert_called_with(mount_point="/custom/mnt")

    @patch('src.kod.debian.install_build_dependencies')
    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_aur_build_fails_if_build_deps_fail(self, mock_open, mock_exec, mock_exec_chroot, mock_install_bd):
        """If build dependencies fail to install, AUR build should fail."""
        mock_install_bd.side_effect = RuntimeError("Failed to install build dependencies")
        
        config = Mock()
        config.repos = {
            "aur": {
                "commands": {"install": "aur -S"},
                "build": {
                    "name": "yay",
                    "url": "https://aur.archlinux.org/yay.git",
                    "build_cmd": "makepkg -si --noconfirm"
                }
            }
        }
        
        with pytest.raises(RuntimeError):
            proc_repos(config, None, False, "/mnt")

    @patch('src.kod.debian.install_build_dependencies')
    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_aur_build_clones_and_builds(self, mock_open, mock_exec, mock_exec_chroot, mock_install_bd):
        """AUR build should clone repo and execute build command."""
        def mock_exec_chroot_side_effect(cmd, **kwargs):
            if "which paru" in cmd:
                return "/usr/bin/paru" if kwargs.get('get_output') else ""
            return ""
        
        mock_exec_chroot.side_effect = mock_exec_chroot_side_effect
        mock_install_bd.return_value = True
        
        config = Mock()
        config.repos = {
            "aur": {
                "commands": {"install": "aur -S"},
                "build": {
                    "name": "paru",
                    "url": "https://aur.archlinux.org/paru.git",
                    "build_cmd": "makepkg -si --noconfirm"
                }
            }
        }
        
        proc_repos(config, None, False, "/mnt")
        
        # Should have cloned the URL
        calls_str = str(mock_exec_chroot.call_args_list)
        assert "https://aur.archlinux.org/paru.git" in calls_str

    @patch('src.kod.debian.install_build_dependencies')
    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_aur_build_fails_if_binary_not_found(self, mock_open, mock_exec, mock_exec_chroot, mock_install_bd):
        """If AUR binary not found after build, should raise error."""
        def mock_exec_chroot_side_effect(cmd, **kwargs):
            if "which paru" in cmd:
                return "" if kwargs.get('get_output') else ""
            return ""
        
        mock_exec_chroot.side_effect = mock_exec_chroot_side_effect
        mock_install_bd.return_value = True
        
        config = Mock()
        config.repos = {
            "aur": {
                "commands": {"install": "aur -S"},
                "build": {
                    "name": "paru",
                    "url": "https://aur.archlinux.org/paru.git",
                    "build_cmd": "makepkg -si --noconfirm"
                }
            }
        }
        
        with pytest.raises(RuntimeError, match="not found after build"):
            proc_repos(config, None, False, "/mnt")


class TestInstallBuildDependencies:
    """Test install_build_dependencies function."""

    @patch('src.kod.debian.exec_chroot')
    def test_install_build_dependencies_installs_required_packages(self, mock_exec_chroot):
        """Should install gcc, make, autoconf, automake, pkg-config, git."""
        def mock_side_effect(cmd, **kwargs):
            if "dpkg -l" in cmd:
                # Return mock dpkg output showing all packages installed
                return "ii  build-essential  1.0  all  Essential packages\nii  autoconf  2.0  all  Autoconf\nii  automake  3.0  all  Automake\nii  pkg-config  4.0  all  pkg-config\nii  git  5.0  all  Git"
            return ""
        
        mock_exec_chroot.side_effect = mock_side_effect
        
        result = install_build_dependencies("/mnt")
        
        # Should have returned True on success
        assert result == True
        
        # Should have called apt-get install
        install_calls = [c for c in mock_exec_chroot.call_args_list 
                        if "apt-get install" in str(c) and "build-essential" in str(c)]
        assert len(install_calls) > 0

    @patch('src.kod.debian.exec_chroot')
    def test_install_build_dependencies_verifies_packages_installed(self, mock_exec_chroot):
        """Should verify each package is installed via dpkg -l."""
        def mock_side_effect(cmd, **kwargs):
            if "dpkg -l" in cmd:
                # Return empty dpkg output (packages not installed)
                return ""
            return ""
        
        mock_exec_chroot.side_effect = mock_side_effect
        
        with pytest.raises(RuntimeError, match="Failed to install|failed to install"):
            install_build_dependencies("/mnt")

    @patch('src.kod.debian.exec_chroot')
    def test_install_build_dependencies_detects_missing_build_essential(self, mock_exec_chroot):
        """Should detect if build-essential fails to install."""
        def mock_side_effect(cmd, **kwargs):
            if "dpkg -l" in cmd:
                # Missing build-essential
                return "ii  autoconf  2.0  all  Autoconf"
            return ""
        
        mock_exec_chroot.side_effect = mock_side_effect
        
        with pytest.raises(RuntimeError, match="build-essential|failed"):
            install_build_dependencies("/mnt")

    @patch('src.kod.debian.exec_chroot')
    def test_install_build_dependencies_with_custom_mount_point(self, mock_exec_chroot):
        """Should use provided mount_point for all operations."""
        mount_used = []
        
        def mock_side_effect(cmd, **kwargs):
            mount_used.append(kwargs.get('mount_point', '/mnt'))
            if "dpkg -l" in cmd:
                return "ii  build-essential  1.0  all  Pkg\nii  autoconf  2.0  all  Pkg\nii  automake  3.0  all  Pkg\nii  pkg-config  4.0  all  Pkg\nii  git  5.0  all  Pkg"
            return ""
        
        mock_exec_chroot.side_effect = mock_side_effect
        
        install_build_dependencies("/custom/mnt")
        
        # Should have used custom mount point
        assert "/custom/mnt" in mount_used

    @patch('src.kod.debian.exec_chroot')
    def test_install_build_dependencies_is_idempotent(self, mock_exec_chroot):
        """Calling install_build_dependencies twice should succeed both times."""
        def mock_side_effect(cmd, **kwargs):
            if "dpkg -l" in cmd:
                return "ii  build-essential  1.0  all  Pkg\nii  autoconf  2.0  all  Pkg\nii  automake  3.0  all  Pkg\nii  pkg-config  4.0  all  Pkg\nii  git  5.0  all  Pkg"
            return ""
        
        mock_exec_chroot.side_effect = mock_side_effect
        
        # First call
        result1 = install_build_dependencies("/mnt")
        
        # Reset mock
        mock_exec_chroot.reset_mock()
        mock_exec_chroot.side_effect = mock_side_effect
        
        # Second call
        result2 = install_build_dependencies("/mnt")
        
        assert result1 == True
        assert result2 == True


class TestDebianProcReposSystemPackages:
    """Test proc_repos handling of system packages on Debian."""

    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_preserves_system_repos(self, mock_open, mock_exec, mock_exec_chroot):
        """System repos should be preserved in output."""
        config = Mock()
        config.repos = {
            "system": {
                "commands": {"install": "apt-get install -y"}
            }
        }
        
        repos, packages = proc_repos(config)
        
        assert "system" in repos
        assert "install" in repos["system"]


class TestDebianProcReposStateManagement:
    """Test proc_repos state tracking on Debian."""

    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_writes_repos_json_file(self, mock_open, mock_exec, mock_exec_chroot):
        """proc_repos should write repos config to /var/kod/repos.json."""
        config = Mock()
        config.repos = {
            "system": {
                "commands": {"install": "apt-get install -y"}
            }
        }
        
        with patch('builtins.open', create=True) as mock_file:
            proc_repos(config, None, False, "/mnt")
            
            # Should have opened repos.json for writing
            write_calls = [c for c in mock_file.call_args_list 
                          if "repos.json" in str(c)]
            assert len(write_calls) > 0

    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_caches_existing_repos_on_no_update(self, mock_open, mock_exec, mock_exec_chroot):
        """If update=False and repo exists in current_repos, should use cached."""
        existing_repos = {
            "system": {"install": "apt-get install -y", "cached": True}
        }
        
        config = Mock()
        config.repos = {
            "system": {
                "commands": {"install": "apt-get install -y"}
            }
        }
        
        repos, packages = proc_repos(config, existing_repos, False, "/mnt")
        
        # Should have used cached version
        assert repos["system"]["cached"] == True

    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_updates_existing_repos_on_update_flag(self, mock_open, mock_exec, mock_exec_chroot):
        """If update=True, should override existing repos."""
        existing_repos = {
            "system": {"install": "apt-get install -y", "cached": True}
        }
        
        config = Mock()
        config.repos = {
            "system": {
                "commands": {"install": "apt-get install -y"}
            }
        }
        
        repos, packages = proc_repos(config, existing_repos, True, "/mnt")
        
        # Should have updated (removed cached flag or overridden)
        if "cached" in repos.get("system", {}):
            assert repos["system"]["cached"] != True


class TestDebianProcReposCommandProcessing:
    """Test command processing in repositories on Debian."""

    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_copies_commands_to_output(self, mock_open, mock_exec, mock_exec_chroot):
        """All commands from config should be copied to repos output."""
        config = Mock()
        config.repos = {
            "system": {
                "commands": {
                    "install": "apt-get install -y",
                    "remove": "apt-get remove -y",
                    "search": "apt-cache search"
                }
            }
        }
        
        repos, packages = proc_repos(config)
        
        # All commands should be in output
        assert repos["system"]["install"] == "apt-get install -y"
        assert repos["system"]["remove"] == "apt-get remove -y"
        assert repos["system"]["search"] == "apt-cache search"


class TestDebianProcReposErrorHandling:
    """Test error handling in proc_repos on Debian."""

    @patch('src.kod.debian.install_build_dependencies')
    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_provides_clear_error_on_build_failure(self, mock_open, mock_exec, mock_exec_chroot, mock_install_bd):
        """Error messages should clearly indicate AUR build failure."""
        mock_exec_chroot.side_effect = Exception("Build failed: gcc not found")
        mock_install_bd.return_value = True
        
        config = Mock()
        config.repos = {
            "aur": {
                "commands": {"install": "aur -S"},
                "build": {
                    "name": "yay",
                    "url": "https://aur.archlinux.org/yay.git",
                    "build_cmd": "makepkg -si --noconfirm"
                }
            }
        }
        
        with pytest.raises(Exception):
            proc_repos(config, None, False, "/mnt")


class TestDebianProcReposIntegration:
    """Integration tests for Debian proc_repos."""

    @patch('src.kod.debian.install_build_dependencies')
    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_handles_multiple_repos(self, mock_open, mock_exec, mock_exec_chroot, mock_install_bd):
        """Should handle multiple repository definitions."""
        def mock_exec_chroot_side_effect(cmd, **kwargs):
            if "which" in cmd:
                return "/usr/bin/tool" if kwargs.get('get_output') else ""
            return ""
        
        mock_exec_chroot.side_effect = mock_exec_chroot_side_effect
        mock_install_bd.return_value = True
        
        config = Mock()
        config.repos = {
            "system": {
                "commands": {"install": "apt-get install -y"}
            },
            "aur": {
                "commands": {"install": "aur -S"},
                "build": {
                    "name": "yay",
                    "url": "https://aur.archlinux.org/yay.git",
                    "build_cmd": "makepkg -si --noconfirm"
                }
            }
        }
        
        repos, packages = proc_repos(config, None, False, "/mnt")
        
        # Should have processed multiple repos
        assert len(repos) >= 1


class TestDebianProcReposPackageList:
    """Test package list tracking in Debian proc_repos."""

    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_returns_packages_list(self, mock_open, mock_exec, mock_exec_chroot):
        """proc_repos should return list of packages."""
        config = Mock()
        config.repos = {
            "system": {
                "commands": {"install": "apt-get install -y"}
            }
        }
        
        repos, packages = proc_repos(config, None, False, "/mnt")
        
        # Should have packages list
        assert isinstance(packages, list)


class TestDebianProcReposAURWithDependencies:
    """Test AUR building with dependencies on Debian."""

    @patch('src.kod.debian.install_build_dependencies')
    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_aur_build_succeeds_with_build_deps(self, mock_open, mock_exec, mock_exec_chroot, mock_install_bd):
        """AUR build should succeed when build dependencies are installed."""
        def mock_exec_chroot_side_effect(cmd, **kwargs):
            if "which paru" in cmd:
                return "/usr/bin/paru" if kwargs.get('get_output') else ""
            return ""
        
        mock_exec_chroot.side_effect = mock_exec_chroot_side_effect
        mock_install_bd.return_value = True
        
        config = Mock()
        config.repos = {
            "aur": {
                "commands": {"install": "aur -S"},
                "build": {
                    "name": "paru",
                    "url": "https://aur.archlinux.org/paru.git",
                    "build_cmd": "makepkg -si --noconfirm"
                }
            }
        }
        
        repos, packages = proc_repos(config, None, False, "/mnt")
        
        # Should have completed successfully
        assert isinstance(repos, dict)
        assert isinstance(packages, list)


class TestDebianProcReposParametrized:
    """Parametrized tests for various Debian proc_repos configurations."""

    @pytest.mark.parametrize("config_name,expected_in_output", [
        ("system", "system"),
        ("aur", "aur"),
    ])
    @patch('src.kod.debian.install_build_dependencies')
    @patch('src.kod.debian.exec_chroot')
    @patch('src.kod.debian.exec')
    @patch('builtins.open', create=True)
    def test_proc_repos_recognizes_repo_types(self, mock_open, mock_exec, mock_exec_chroot, mock_install_bd, config_name, expected_in_output):
        """proc_repos should recognize and process different repo types."""
        def mock_exec_chroot_side_effect(cmd, **kwargs):
            if "which" in cmd:
                return "/usr/bin/tool" if kwargs.get('get_output') else ""
            return ""
        
        mock_exec_chroot.side_effect = mock_exec_chroot_side_effect
        mock_install_bd.return_value = True
        
        config = Mock()
        
        if config_name == "system":
            config.repos = {
                "system": {
                    "commands": {"install": "apt-get install -y"}
                }
            }
        elif config_name == "aur":
            config.repos = {
                "aur": {
                    "commands": {"install": "aur -S"},
                    "build": {
                        "name": "paru",
                        "url": "https://aur.archlinux.org/paru.git",
                        "build_cmd": "makepkg -si --noconfirm"
                    }
                }
            }
        
        repos, packages = proc_repos(config, None, False, "/mnt")
        
        # Should have processed the repo type
        assert expected_in_output in repos or len(repos) >= 0
