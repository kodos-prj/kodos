"""Distro module factory (strategy pattern for distro selection).

Abstracts distro-specific imports so boot.py and packages.py don't hardcode
distro module names. Makes adding new distros easy.
"""

from typing import Any
import importlib


def get_distro_module(distro_name: str) -> Any:
    """Get the distro-specific module for the given distro.
    
    Args:
        distro_name: The distro name ("arch", "debian", etc.)
        
    Returns:
        The distro module (kod.system.distro.arch or kod.system.distro.debian)
        
    Raises:
        ValueError: If distro_name is not supported.
    """
    supported = {"arch", "debian"}
    
    if distro_name not in supported:
        raise ValueError(f"Unknown distro: {distro_name}. Supported: {supported}")
    
    # Use importlib to dynamically import the distro module
    module = importlib.import_module(f"kod.system.distro.{distro_name}")
    return module


def set_base_distribution(distro_name: str) -> Any:
    """Set the base distribution and return the distro module.
    
    Selects the distribution-specific implementation (Arch, Debian, etc.)
    to use for system operations. Currently defaults to Arch.
    
    Args:
        distro_name: The base distribution name ("arch", "debian", etc.)
        
    Returns:
        The distribution-specific module.
        
    Raises:
        ValueError: If distro_name is not supported.
    """
    return get_distro_module(distro_name)

