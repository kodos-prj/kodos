"""Tests for kod/config/loader.py (Phase 1)."""

import pytest
from pathlib import Path

EXAMPLE_DIR = Path(__file__).parent.parent.parent / "example" / "testvm"


def test_loader_loads_example_config_as_dict():
    """Loader converts Lua table to Python dict."""
    from kod.config.loader import load_config
    
    config = load_config(str(EXAMPLE_DIR))
    
    # Should be a Python dict, not a lupa LuaTable
    assert isinstance(config, dict)
    assert "hostname" in config.get("network", {})
    assert config["network"]["hostname"] == "testvm"


def test_loader_handles_nested_structures():
    """Loader converts nested Lua tables."""
    from kod.config.loader import load_config
    
    config = load_config(str(EXAMPLE_DIR))
    
    # Check nested dicts
    assert isinstance(config["boot"], dict)
    assert isinstance(config["boot"]["kernel"], dict)
    assert config["boot"]["kernel"]["package"] == "linux-lts"
    
    # Check lists
    assert isinstance(config["boot"]["kernel"]["modules"], list)
    assert "xhci_pci" in config["boot"]["kernel"]["modules"]


def test_loader_handles_lists():
    """Loader converts Lua lists correctly."""
    from kod.config.loader import load_config
    
    config = load_config(str(EXAMPLE_DIR))
    
    # packages is wrapped in list() call in Lua
    assert isinstance(config["packages"], list)
    assert "git" in config["packages"]


def test_loader_preserves_strings_and_numbers():
    """Loader preserves scalar types."""
    from kod.config.loader import load_config
    
    config = load_config(str(EXAMPLE_DIR))
    
    # Strings
    assert isinstance(config["network"]["hostname"], str)
    # Numbers
    assert config["boot"]["loader"]["timeout"] == 10
    # Bools
    assert config["network"]["ipv6"] is True
