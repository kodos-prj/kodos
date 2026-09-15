"""Test that kod.core exports are available at load time without lazy imports."""

import pytest


def test_core_imports_all_exports_at_load_time():
    """Verify all exports from kod.core are available without __getattr__."""
    from kod.core import (
        # Phase 2b re-exports from kod.system.packages
        get_packages_to_install,
        load_repos,
        load_package_lock,
        store_packages_services,
        get_packages_updates,
        update_all_packages,
        get_pending_packages,
        manage_packages_shell,
        # Phase 2b re-exports from kod.system.services
        enable_services,
        enable_user_services,
        get_services_to_enable,
        proc_desktop_services,
        proc_services,
        proc_services_to_enable,
        # Phase 2b re-exports from kod.system.boot
        create_boot_entry_hook,
        get_kernel_version,
        update_kernel_hook,
        update_initramfs_hook,
    )
    
    # Verify they are callable
    assert callable(get_packages_to_install)
    assert callable(enable_services)
    assert callable(create_boot_entry_hook)


def test_core_module_has_no_getattr():
    """Verify kod.core module does not use __getattr__."""
    import kod.core
    assert not hasattr(kod.core, '__getattr__'), \
        "kod.core should not have __getattr__ after refactoring"
