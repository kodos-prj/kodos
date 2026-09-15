"""Tests for distro module factory abstraction."""

import pytest


def test_get_distro_module_returns_arch():
    """Factory should return arch module when requested."""
    from kod.system.distro.factory import get_distro_module
    
    distro = get_distro_module("arch")
    
    assert hasattr(distro, 'get_kernel_file')
    assert hasattr(distro, 'get_base_packages')
    assert hasattr(distro, 'proc_repos')


def test_get_distro_module_returns_debian():
    """Factory should return debian module when requested."""
    from kod.system.distro.factory import get_distro_module
    
    distro = get_distro_module("debian")
    
    assert hasattr(distro, 'get_kernel_file')
    assert hasattr(distro, 'get_base_packages')
    assert hasattr(distro, 'proc_repos')


def test_get_distro_module_raises_on_unknown():
    """Factory should raise ValueError on unknown distro."""
    from kod.system.distro.factory import get_distro_module
    
    with pytest.raises(ValueError, match="Unknown distro"):
        get_distro_module("unknown_distro")


def test_distro_factory_exported_from_package():
    """Factory should be exported from kod.system.distro package."""
    from kod.system.distro import get_distro_module
    
    distro = get_distro_module("arch")
    assert distro is not None
