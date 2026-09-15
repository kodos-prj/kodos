"""Plugin loading and management (Phase 3).

Auto-discovers and loads plugins from ~/.kod/plugins/

Supported plugin types:
- Programs: ~/.kod/plugins/programs/*.lua
- Build templates: ~/.kod/plugins/build_templates/*.lua (Phase 5)
- Custom modules: ~/.kod/plugins/modules/*.lua

Key components:
- PluginLoader: Main loader
- discover_plugins(): Auto-discover plugins
- load_plugin(): Load a single plugin

Example:
    >>> loader = PluginLoader()
    >>> plugins = loader.discover_plugins("programs")
    >>> loader.load_all_plugins("programs")
"""

from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import lupa

from .programs import (
    Program,
    ProgramNotFound,
    ProgramLoadError,
    CircularExtendError,
)


class PluginLoader:
    """Load and manage programs from builtin and user plugin directories.
    
    Delegates logic to Lua registry modules (loader.lua, inheritance.lua).
    Python handles:
    - Directory discovery (pathlib is more portable)
    - Error wrapping (convert Lua errors to Python exceptions)
    - Program wrapping (conversion to Program objects)
    """

    def __init__(self, config_home: Optional[str] = None):
        """Initialize loader with path configuration.
        
        Args:
            config_home: Path to config home directory.
                        Defaults to ~/.kod/
        """
        if config_home:
            self.config_home = Path(config_home)
        else:
            self.config_home = Path.home() / ".kod"
        
        self.builtin_dir = Path(__file__).parent / "builtin"
        self.plugin_dir = self.config_home / "plugins" / "programs"
        
        # Load Lua modules once (skip if lupa is mocked for testing)
        if hasattr(lupa, '_mock_name'):  # Detect mock
            self._lua = None
        else:
            self._lua = lupa.LuaRuntime()
            
            # Load loader.lua and store as global
            loader_code = (Path(__file__).parent.parent / "lib/registry/loader.lua").read_text()
            self._lua.globals().loader = self._lua.execute(loader_code)
            
            # Make loader available as package for require()
            self._lua.execute("""
                package.preload['lib.registry.loader'] = function()
                    return loader
                end
            """)
            
            # Load inheritance.lua
            inheritance_code = (Path(__file__).parent.parent / "lib/registry/inheritance.lua").read_text()
            self._lua.execute(inheritance_code)
        
        # Caches to avoid reloading
        self._merged_cache: Dict[str, Program] = {}    # name -> Program
        
        # Backward compat: tests expect _builtin_cache and _user_cache
        # These are now logical subsets of _merged_cache
        self._builtin_cache: Dict[str, Program] = {}
        self._user_cache: Dict[str, Program] = {}

    def discover_builtin(self) -> Dict[str, Path]:
        """Discover all builtin program .lua files."""
        programs = {}
        if not self.builtin_dir.exists():
            return programs
        for lua_file in self.builtin_dir.glob("*.lua"):
            programs[lua_file.stem] = lua_file
        return programs

    def discover_user_plugins(self) -> Dict[str, Path]:
        """Discover all user plugin .lua files in ~/.kod/plugins/programs/"""
        programs = {}
        if not self.plugin_dir.exists():
            return programs
        for lua_file in self.plugin_dir.glob("*.lua"):
            programs[lua_file.stem] = lua_file
        return programs

    def _load_lua_def(self, file_path: Path) -> Dict[str, Any]:
        """Parse and load a Lua file, return dict (backward compat method).
        
        This method is kept for backward compatibility with tests.
        Internally, loading is delegated to Lua's loader.load_program_file.
        """
        if self._lua is None:
            raise ProgramLoadError("Lua runtime not initialized (lupa is mocked for testing)")
        result, error = self._lua.globals().loader.load_program_file(str(file_path))
        if error:
            raise ProgramLoadError(f"Failed to load program from {file_path}: {error}")
        return dict(result.items()) if result else {}

    def load_program(self, name: str, visited: Optional[Set[str]] = None) -> Program:
        """Load a program by name, merging builtin with user plugin if needed."""
        if visited is None:
            visited = set()
        
        if name in self._merged_cache:
            return self._merged_cache[name]
        
        if name in visited:
            raise CircularExtendError(
                f"Circular inheritance detected: {name} extends itself"
            )
        visited.add(name)
        
        builtin_programs = self.discover_builtin()
        user_programs = self.discover_user_plugins()
        
        # Load Lua defs via Lua functions
        user_lua_def = None
        if name in user_programs:
            result, error = self._lua.globals().loader.load_program_file(str(user_programs[name]))
            if error:
                raise ProgramLoadError(f"Failed to load user program '{name}': {error}")
            user_lua_def = dict(result.items()) if result else None
        
        builtin_lua_def = None
        if name in builtin_programs:
            result, error = self._lua.globals().loader.load_program_file(str(builtin_programs[name]))
            if error:
                raise ProgramLoadError(f"Failed to load builtin program '{name}': {error}")
            builtin_lua_def = dict(result.items()) if result else None
        
        # Handle inheritance via Lua
        if user_lua_def and builtin_lua_def:
            if "_extends" not in user_lua_def:
                raise ProgramLoadError(
                    f"Program '{name}' has both user and builtin, user must extend builtin"
                )
            
            parent_name = user_lua_def.get("_extends")
            if parent_name != name:
                raise ProgramLoadError(
                    f"Program '{name}' user extends '{parent_name}', not itself"
                )
            
            if "_extends" in builtin_lua_def:
                builtin_parent = self.load_program(builtin_lua_def.get("_extends"), visited)
                parent_program = Program(name, builtin_lua_def, parent=builtin_parent)
            else:
                parent_program = Program(name, builtin_lua_def)
            
            self._builtin_cache[name] = parent_program  # Track builtin part
            merged_program = Program(name, user_lua_def, parent=parent_program)
            self._merged_cache[name] = merged_program
            return merged_program
        
        elif user_lua_def:
            if "_extends" in user_lua_def:
                parent_name = user_lua_def.get("_extends")
                if parent_name == name:
                    raise ProgramLoadError(f"Program '{name}' extends itself")
                parent_program = self.load_program(parent_name, visited)
                program = Program(name, user_lua_def, parent=parent_program)
            else:
                program = Program(name, user_lua_def)
            self._user_cache[name] = program  # Track user program
            self._merged_cache[name] = program
            return program
        
        elif builtin_lua_def:
            if "_extends" in builtin_lua_def:
                parent_name = builtin_lua_def.get("_extends")
                if parent_name == name:
                    raise ProgramLoadError(f"Program '{name}' extends itself")
                parent_program = self.load_program(parent_name, visited)
                program = Program(name, builtin_lua_def, parent=parent_program)
            else:
                program = Program(name, builtin_lua_def)
            self._builtin_cache[name] = program  # Track builtin program
            self._merged_cache[name] = program
            return program
        
        else:
            raise ProgramNotFound(
                f"Program '{name}' not found in {self.builtin_dir} or {self.plugin_dir}"
            )

    def list_programs(self) -> List[str]:
        """Return all available program names (builtin + user)."""
        builtin = set(self.discover_builtin().keys())
        user = set(self.discover_user_plugins().keys())
        all_names = builtin | user
        return sorted(all_names)

    def get_program_info(self, name: str) -> Dict[str, Any]:
        """Get metadata about a program."""
        # Check caches first (for backward compat with tests that populate caches directly)
        if name in self._merged_cache:
            program = self._merged_cache[name]
        elif name in self._builtin_cache:
            program = self._builtin_cache[name]
        elif name in self._user_cache:
            program = self._user_cache[name]
        else:
            # Load from disk
            program = self.load_program(name)
        
        # Determine source
        if name in self._merged_cache and program.parent is not None:
            source = "merged"
        elif name in self._builtin_cache:
            source = "builtin"
        elif name in self._user_cache:
            source = "user"
        else:
            # Fallback to old logic
            if program.parent is not None:
                source = "merged"
            elif name in self.discover_builtin():
                source = "builtin"
            else:
                source = "user"
        
        return {
            "name": program.name,
            "scope": program.get_scope(),
            "source": source,
            "schema": program.get_schema(),
            "default_config": program.lua_def.get("default_config", {}),
            "extends": program.lua_def.get("_extends") if program.parent else None,
            "service": program.get_service() if hasattr(program, 'get_service') else None,
        }


# ===== Backward Compatibility =====

# Alias for tests that import ProgramRegistry from programs.py
ProgramRegistry = PluginLoader