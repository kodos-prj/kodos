"""Tests for distro module factory abstraction and adapter integration."""

import pytest


# ==== Backward Compatibility Tests (old API) ====

def test_get_distro_module_returns_arch():
    """Factory should return arch adapter when requested."""
    from kod.system.distro.factory import get_distro_module
    
    distro = get_distro_module("arch")
    
    assert hasattr(distro, 'get_kernel_file')
    assert hasattr(distro, 'get_base_packages')
    assert hasattr(distro, 'proc_repos')


def test_get_distro_module_returns_debian():
    """Factory should return debian adapter when requested."""
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


# ==== New Adapter Interface Tests ====

def test_get_distro_adapter_returns_arch_adapter_instance():
    """New factory function should return ArchAdapter instance."""
    from kod.system.distro.factory import get_distro_adapter
    from kod.system.distro.base import DistroAdapter
    from kod.system.distro.adapters.arch import ArchAdapter
    
    adapter = get_distro_adapter("arch")
    
    assert isinstance(adapter, DistroAdapter)
    assert isinstance(adapter, ArchAdapter)


def test_get_distro_adapter_returns_debian_adapter_instance():
    """New factory function should return DebianAdapter instance."""
    from kod.system.distro.factory import get_distro_adapter
    from kod.system.distro.base import DistroAdapter
    from kod.system.distro.adapters.debian import DebianAdapter
    
    adapter = get_distro_adapter("debian")
    
    assert isinstance(adapter, DistroAdapter)
    assert isinstance(adapter, DebianAdapter)


def test_get_distro_adapter_raises_on_unsupported_distro():
    """New factory should raise on unsupported distro."""
    from kod.system.distro.factory import get_distro_adapter
    
    with pytest.raises(ValueError, match="Unsupported distro"):
        get_distro_adapter("fedora")


def test_adapter_has_all_public_methods():
    """Adapter instance should have all required public methods."""
    from kod.system.distro.factory import get_distro_adapter
    
    adapter = get_distro_adapter("arch")
    
    # Public methods that should exist
    required_methods = [
        'get_base_packages',
        'install_essentials_pkgs',
        'get_kernel_file',
        'get_list_of_dependencies',
        'proc_repos',
        'refresh_package_db',
        'kernel_update_required',
        'generate_package_lock',
    ]
    
    for method in required_methods:
        assert hasattr(adapter, method), f"Adapter missing method: {method}"
        assert callable(getattr(adapter, method)), f"Not callable: {method}"


def test_adapter_has_package_manager_property():
    """Adapter should have package_manager property."""
    from kod.system.distro.factory import get_distro_adapter
    
    arch_adapter = get_distro_adapter("arch")
    debian_adapter = get_distro_adapter("debian")
    
    assert arch_adapter.package_manager == "pacman"
    assert debian_adapter.package_manager == "apt"


def test_arch_adapter_returns_correct_base_packages():
    """ArchAdapter should return Arch-specific base packages."""
    from kod.system.distro.factory import get_distro_adapter
    from unittest.mock import MagicMock
    
    adapter = get_distro_adapter("arch")
    
    # Mock config
    conf = MagicMock()
    conf.boot = None
    
    packages = adapter.get_base_packages(conf)
    
    assert 'kernel' in packages
    assert 'base' in packages
    assert isinstance(packages['base'], list)
    # Arch should have base-devel
    assert 'base-devel' in packages['base']


def test_debian_adapter_returns_correct_base_packages():
    """DebianAdapter should return Debian-specific base packages."""
    from kod.system.distro.factory import get_distro_adapter
    from unittest.mock import MagicMock
    
    adapter = get_distro_adapter("debian")
    
    # Mock config
    conf = MagicMock()
    conf.boot = None
    
    packages = adapter.get_base_packages(conf)
    
    assert 'kernel' in packages
    assert 'base' in packages
    assert isinstance(packages['base'], list)
    # Debian should use linux-image-amd64
    assert 'linux-image-amd64' in packages['kernel']


def test_adapter_respects_config_kernel_override():
    """Adapter should override kernel package from config."""
    from kod.system.distro.factory import get_distro_adapter
    from unittest.mock import MagicMock
    
    adapter = get_distro_adapter("arch")
    
    # Mock config with kernel override
    conf = MagicMock()
    conf.boot.kernel.package = "linux-zen"
    
    packages = adapter.get_base_packages(conf)
    
    assert packages['kernel'] == 'linux-zen'


def test_adapters_are_distinct_instances():
    """Each call to factory should return a new adapter instance."""
    from kod.system.distro.factory import get_distro_adapter
    
    adapter1 = get_distro_adapter("arch")
    adapter2 = get_distro_adapter("arch")
    
    # Should be different instances (fresh instantiation)
    assert adapter1 is not adapter2
    # But same type
    assert type(adapter1) is type(adapter2)


def test_backward_compat_get_distro_module_delegates_to_adapter():
    """Old get_distro_module should still work via get_distro_adapter."""
    from kod.system.distro.factory import get_distro_module, get_distro_adapter
    from kod.system.distro.base import DistroAdapter
    
    old_result = get_distro_module("arch")
    new_result = get_distro_adapter("arch")
    
    # Both should be DistroAdapter instances
    assert isinstance(old_result, DistroAdapter)
    assert isinstance(new_result, DistroAdapter)
    # Both should have same public interface
    assert type(old_result) is type(new_result)


def test_adapters_exported_from_package():
    """Adapters and base should be exportable from distro package."""
    from kod.system.distro import DistroAdapter, ArchAdapter, DebianAdapter
    
    assert DistroAdapter is not None
    assert ArchAdapter is not None
    assert DebianAdapter is not None
    
    # Should be able to instantiate
    arch = ArchAdapter()
    debian = DebianAdapter()
    
    assert arch.package_manager == "pacman"
    assert debian.package_manager == "apt"
