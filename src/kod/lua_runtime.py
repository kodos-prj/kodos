"""Singleton Lua runtime manager for bootstrap and other Lua integration.

Ensures all Lua code runs in the same runtime to avoid object mixing issues.
Provides centralized Lua environment management and cleanup.
"""

from typing import Optional
from lupa import LuaRuntime
import atexit
import logging

logger = logging.getLogger(__name__)


class LuaRuntimeManager:
    """Singleton manager for persistent Lua runtime."""
    
    _instance: Optional["LuaRuntimeManager"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.lua: Optional[LuaRuntime] = None
        self._initialized = True
        self._init_lua()
        
        # Register cleanup on exit
        atexit.register(self.cleanup)
    
    def _init_lua(self):
        """Initialize the Lua runtime."""
        try:
            self.lua = LuaRuntime()
            
            # Preload modules for backward compatibility
            # (so unqualified `require('module_name')` works for moved modules)
            from pathlib import Path
            base_path = Path(__file__).parent.parent
            # Include both src/ (for kod.* modules) and src/lua/ (for Lua implementations)
            lua_path = f"{base_path}/?.lua;{base_path}/?/init.lua;{base_path}/lua/?.lua;{base_path}/lua/?/init.lua"
            self.lua.execute(f"package.path = '{lua_path}' .. package.path")
            
            # Preload modules that were moved to subdirectories
            # so legacy `require('module_name')` calls still work
            self.lua.execute("""
                -- Utility modules
                package.preload['utils'] = function()
                    return require('kod.lib.utils')
                end
                package.preload['configs'] = function()
                    return require('kod.lib.configs')
                end
                
                -- Core modules
                package.preload['schema'] = function()
                    return require('kod.core.schema')
                end
                
                -- System modules
                package.preload['repos'] = function()
                    return require('kod.system.repos')
                end
                package.preload['disk'] = function()
                    return require('kod.system.disk')
                end
            """)
            
            logger.debug("Lua runtime initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Lua runtime: {e}")
            raise
    
    def get_lua(self) -> LuaRuntime:
        """Get the persistent Lua runtime."""
        if self.lua is None:
            self._init_lua()
        return self.lua
    
    def reload_modules(self, module_patterns: Optional[list] = None):
        """Clear Lua's module cache for specified modules to force reload.
        
        Args:
            module_patterns: List of module name patterns to reload (e.g., ['kod.planning.*']).
                           If None, clears all 'kod.*' modules.
        """
        if self.lua is None:
            return
        
        patterns = module_patterns or ['kod\\..*']
        try:
            # Clear matching entries from Lua's package.loaded table
            self.lua.execute(f"""
                local patterns = {repr(patterns)}
                for module_name in pairs(package.loaded) do
                    for _, pattern in ipairs(patterns) do
                        if module_name:match(pattern) then
                            package.loaded[module_name] = nil
                            break
                        end
                    end
                end
            """)
            logger.debug(f"Lua module cache cleared for patterns: {patterns}")
        except Exception as e:
            logger.warning(f"Error clearing Lua module cache: {e}")
    
    def cleanup(self):
        """Clean up Lua runtime resources."""
        if self.lua is not None:
            try:
                # Lupa handles finalizers automatically
                self.lua = None
                logger.debug("Lua runtime cleaned up")
            except Exception as e:
                logger.warning(f"Error during Lua cleanup: {e}")


# Global singleton accessor
_manager: Optional[LuaRuntimeManager] = None


def get_lua_runtime() -> LuaRuntime:
    """Get the global persistent Lua runtime."""
    global _manager
    if _manager is None:
        _manager = LuaRuntimeManager()
    return _manager.get_lua()


def cleanup_lua_runtime():
    """Clean up the global Lua runtime."""
    global _manager
    if _manager is not None:
        _manager.cleanup()
        _manager = None
