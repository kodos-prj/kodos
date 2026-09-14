"""Tests for kod/system/boot.py (Phase 2)."""

import pytest


class TestBootManagement:
    """Test boot operations."""

    def test_create_boot_entry_hook_callable(self):
        """create_boot_entry_hook() is callable."""
        from kod.system.boot import create_boot_entry_hook
        
        assert callable(create_boot_entry_hook)

    def test_get_kernel_version_callable(self):
        """get_kernel_version() is callable."""
        from kod.system.boot import get_kernel_version
        
        assert callable(get_kernel_version)

    def test_read_root_device(self, tmp_path):
        fstab = tmp_path / "fstab"
        fstab.write_text("# comment\nUUID=abc-123 / btrfs defaults 0 0\nUUID=def-456 /boot vfat 0 0\n")
        from kod.system.boot import _read_root_device
        assert _read_root_device(str(fstab)) == "UUID=abc-123"

    def test_create_boot_entry_hook_writes_files(self, tmp_path, monkeypatch):
        from kod.system import boot
        monkeypatch.setattr(boot, "get_kernel_file", lambda mp, package="linux": ("/x/vmlinuz", "6.12.0-arch1"))
        monkeypatch.setattr(boot, "exec", lambda cmd, get_output=False: "2026-01-01 00:00:00")
        (tmp_path / "etc").mkdir()
        (tmp_path / "etc/fstab").write_text("UUID=root-uuid / btrfs defaults 0 0\n")
        boot.create_boot_entry_hook(7, "linux", str(tmp_path))()
        entry = (tmp_path / "boot/loader/entries/kodos-7.conf").read_text()
        assert "root=UUID=root-uuid rw rootflags=subvol=generations/7/rootfs" in entry
        assert "linux /vmlinuz-6.12.0-arch1" in entry
        assert "initrd /initramfs-linux-6.12.0-arch1.img" in entry
        loader = (tmp_path / "boot/loader/loader.conf").read_text()
        assert "default kodos-7.conf" in loader
