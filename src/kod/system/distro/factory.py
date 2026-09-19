"""Distro adapter factory (strategy pattern for distro selection).

Abstracts distro-specific adapter instantiation so boot.py and kod.py don't 
hardcode distro names or adapter classes. Makes adding new distros easy.

Provides:
- get_distro_adapter(): New API, returns adapter instance (recommended)
- get_distro_module(): Legacy API for backward compatibility
"""

from typing import Any
from kod.system.distro.base import DistroAdapter
from kod.system.distro.adapters.arch import ArchAdapter
from kod.system.distro.adapters.debian import DebianAdapter


def get_distro_adapter(distro_name: str) -> DistroAdapter:
    """Get distro adapter instance based on distro name.
    
    Creates and returns a new adapter instance for the specified distro.
    Each call returns a fresh instance.
    
    Args:
        distro_name: The distro name ("arch", "debian", etc.)
        
    Returns:
        DistroAdapter: A new adapter instance (ArchAdapter, DebianAdapter, etc.)
        
    Raises:
        ValueError: If distro_name is not supported.
    """
    adapters = {
        "arch": ArchAdapter,
        "debian": DebianAdapter,
    }
    
    if distro_name not in adapters:
        raise ValueError(f"Unknown distro: {distro_name}")
    
    return adapters[distro_name]()


def get_distro_module(distro_name: str) -> DistroAdapter:
    """Deprecated: Get distro adapter instance.
    
    This function is kept for backward compatibility with existing callers
    (kod.py, boot.py). New code should use get_distro_adapter() instead.
    
    This function delegates to get_distro_adapter() and returns the same
    adapter instance.
    
    Args:
        distro_name: The distro name ("arch", "debian", etc.)
        
    Returns:
        DistroAdapter: A new adapter instance
        
    Raises:
        ValueError: If distro_name is not supported.
    """
    return get_distro_adapter(distro_name)

