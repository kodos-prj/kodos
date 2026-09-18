"""Thin orchestration wrapper for registry (Python delegates to Lua).

Architecture: Python = orchestration only, all compute logic in Lua.

This module provides the Python interface for registry operations while
delegating all compute logic to Lua registry modules. During Phase 1, this
wrapper calls the existing Python registry as a fallback while Lua is being
enhanced. In Phase 2+, it will call Lua directly.

Key components:
- PluginLoader: wrapper that calls Lua registry
- Program: wrapper that provides Python interface to Lua program tables
- Exception hierarchy: unchanged from original (backward compatible)

Example:
    >>> from kod.registry_wrapper import PluginLoader
    >>> loader = PluginLoader()
    >>> prog = loader.load_program("git")
    >>> prog.validate_config({"user": "alice"})
    >>> config = prog.generate_config({"user": "alice"})
"""

from typing import Dict, List, Any, Optional, Set
from pathlib import Path

# Phase 1: Import from existing Python registry (will be removed in Phase 2)
from kod.registry.loader import PluginLoader as _PythonPluginLoader
from kod.registry.programs import (
    Program as _PythonProgram,
    ProgramError,
    ProgramNotFound,
    ProgramLoadError,
    ConfigValidationError,
    SchemaError,
    CircularExtendError,
)


# ===== Public API (unchanged from original) =====

class PluginLoader(_PythonPluginLoader):
    """Orchestration wrapper for program registry.
    
    Delegates all compute logic to Lua registry modules.
    Currently Phase 1: calls existing Python registry as fallback.
    Phase 2: will call Lua registry directly.
    
    Architecture:
    - Python (this wrapper): orchestration, CLI, error handling
    - Lua: all registry compute logic
    
    Interface: unchanged from original Python registry
    """
    
    # For Phase 1, just inherit from Python registry
    # Once Phase 2 is complete, this class will:
    # 1. Initialize Lua runtime
    # 2. Load src/kod/lib/registry/registry.lua
    # 3. Delegate all operations to Lua functions
    # 4. Convert Lua results to Python objects
    # 5. Convert Lua errors to Python exceptions
    pass


class Program(_PythonProgram):
    """Orchestration wrapper for program definitions.
    
    Wraps Lua program tables with Python interface.
    Currently Phase 1: wraps Python Program object.
    Phase 2: will wrap Lua table directly.
    
    Architecture:
    - Python (this wrapper): interface, error handling, data conversion
    - Lua: all program logic (validation, generation, hooks)
    """
    
    # For Phase 1, just inherit from Python Program
    # Once Phase 2 is complete, this class will:
    # 1. Store Lua program table
    # 2. Call Lua functions for all operations
    # 3. Convert Lua results to Python types
    # 4. Convert Lua errors to Python exceptions
    pass


# ===== Exception Hierarchy (unchanged from original) =====

# Re-export all exceptions so consumers don't need to change imports
__all__ = [
    "PluginLoader",
    "Program",
    "ProgramError",
    "ProgramNotFound",
    "ProgramLoadError",
    "ConfigValidationError",
    "SchemaError",
    "CircularExtendError",
]
