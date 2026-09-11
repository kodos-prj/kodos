"""Tests for kod/bootstrap.py (Lua bootstrap module invocation)."""

import pytest
from kod.bootstrap import emit_bootstrap_steps
from kod.planner import Step


def make_conf(**sections):
    """Build a simple dict conf for testing."""
    return sections


def test_emit_bootstrap_steps_arch_returns_list():
    """Bootstrap emission returns list of Step objects."""
    conf = {
        "devices": {"1": {"device": "/dev/sda", "partitions": {
            "1": {"name": "root", "size": "100%", "type": "ext4", "mountpoint": "/"}
        }}},
        "locale": "en_US.UTF-8",
        "hostname": "testhost",
    }
    predicted_partition_list = [
        {"device": "/dev/sda1", "mountpoint": "/", "filesystem": "ext4"},
    ]
    
    steps = emit_bootstrap_steps(conf, predicted_partition_list, distro="arch")
    
    assert isinstance(steps, list)
    assert len(steps) > 0
    assert all(isinstance(s, Step) for s in steps)


def test_emit_bootstrap_steps_includes_disk_mount_system():
    """Bootstrap sequence includes disk, mount, and system steps."""
    conf = {
        "devices": {"1": {"device": "/dev/sda", "partitions": {
            "1": {"name": "boot", "size": "512M", "type": "esp", "mountpoint": "/boot"},
            "2": {"name": "root", "size": "100%", "type": "ext4", "mountpoint": "/"}
        }}},
        "locale": "en_US.UTF-8",
        "hostname": "testhost",
    }
    predicted_partition_list = [
        {"device": "/dev/sda1", "mountpoint": "/boot", "filesystem": "esp"},
        {"device": "/dev/sda2", "mountpoint": "/", "filesystem": "ext4"},
    ]
    
    steps = emit_bootstrap_steps(conf, predicted_partition_list, distro="arch")
    
    kinds = {s.kind for s in steps}
    assert "disk" in kinds
    assert "system" in kinds
    
    names = {s.name for s in steps}
    assert any("wipe" in n for n in names)
    assert any("mount" in n for n in names)
    assert "locale" in names
    assert "hostname" in names
    assert "bootloader" in names


def test_emit_bootstrap_steps_debian_same_interface():
    """Debian bootstrap uses same interface as Arch."""
    conf = {
        "devices": {"1": {"device": "/dev/sda", "partitions": {
            "1": {"name": "root", "size": "100%", "type": "ext4", "mountpoint": "/"}
        }}},
        "locale": "en_US.UTF-8",
        "hostname": "testhost",
    }
    predicted_partition_list = [
        {"device": "/dev/sda1", "mountpoint": "/", "filesystem": "ext4"},
    ]
    
    # Should not raise; Debian module exists and works
    steps = emit_bootstrap_steps(conf, predicted_partition_list, distro="debian")
    
    assert isinstance(steps, list)
    assert len(steps) > 0


def test_emit_bootstrap_steps_arch_wipe_steps():
    """Arch bootstrap includes wipe steps for each device."""
    conf = {
        "devices": {"1": {"device": "/dev/sda", "partitions": {
            "1": {"name": "root", "size": "100%", "type": "ext4", "mountpoint": "/"}
        }}},
    }
    predicted_partition_list = [
        {"device": "/dev/sda1", "mountpoint": "/", "filesystem": "ext4"},
    ]
    
    steps = emit_bootstrap_steps(conf, predicted_partition_list, distro="arch")
    
    wipe_steps = [s for s in steps if "wipe" in s.name]
    assert len(wipe_steps) == 1
    assert wipe_steps[0].program == "wipefs"
    assert wipe_steps[0].args == ("-a", "/dev/sda")
