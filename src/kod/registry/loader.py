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
    
    Handles:
    - Discovering .lua files in builtin and user plugin directories
    - Loading and parsing .lua program definitions
    - Merging user programs with builtins via _extends field
    - Validating program structure and inheritance chains
    - Caching loaded programs to avoid reloading
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
        
        # Caches to avoid reloading
        self._builtin_cache: Dict[str, Program] = {}  # name -> Program
        self._user_cache: Dict[str, Program] = {}      # name -> Program
        self._merged_cache: Dict[str, Program] = {}    # name -> Program (builtin + user merged)

    def discover_builtin(self) -> Dict[str, Path]:
        """Discover all builtin program .lua files.
        
        Returns:
            {program_name: file_path} dict
            
        Example:
            {"git": Path(".../builtin/git.lua"), ...}
        """
        programs = {}
        
        if not self.builtin_dir.exists():
            return programs
        
        for lua_file in self.builtin_dir.glob("*.lua"):
            program_name = lua_file.stem  # filename without .lua extension
            programs[program_name] = lua_file
        
        return programs

    def discover_user_plugins(self) -> Dict[str, Path]:
        """Discover all user plugin .lua files in ~/.kod/plugins/programs/
        
        Returns:
            {program_name: file_path} dict
            
        Example:
            {"git": Path(".../.kod/plugins/programs/git.lua"), ...}
        """
        programs = {}
        
        if not self.plugin_dir.exists():
            return programs
        
        for lua_file in self.plugin_dir.glob("*.lua"):
            program_name = lua_file.stem  # filename without .lua extension
            programs[program_name] = lua_file
        
        return programs

    def _load_lua_def(self, file_path: Path) -> Dict[str, Any]:
        """Parse and load a Lua file, return dict.
        
        Executes Lua code: `return {...}`
        Returns the dict value.
        
        Args:
            file_path: Path to .lua file
            
        Returns:
            Dict from Lua return statement
            
        Raises:
            ProgramLoadError: If Lua syntax error or return not a dict
        """
        try:
            with open(file_path, "r") as f:
                lua_code = f.read()
        except OSError as e:
            raise ProgramLoadError(
                f"Failed to read program file {file_path}: {e}"
            )
        
        try:
            lua = lupa.LuaRuntime()
            result = lua.execute(lua_code)
            
            # Lua return statement should return a dict/table
            if result is None:
                raise ProgramLoadError(
                    f"Program file {file_path} must return a dict (got None)"
                )
            
            # Convert lupa LuaTable to dict if needed
            if isinstance(result, dict):
                return result
            
            # Try to convert lupa LuaTable to dict
            try:
                return dict(result.items())
            except (AttributeError, TypeError):
                raise ProgramLoadError(
                    f"Program file {file_path} must return a dict (got {type(result).__name__})"
                )
        except lupa.LuaError as e:
            raise ProgramLoadError(
                f"Lua syntax error in {file_path}: {e}"
            )
        except ProgramLoadError:
            raise
        except Exception as e:
            raise ProgramLoadError(
                f"Failed to load program from {file_path}: {e}"
            )

    def load_program(self, name: str, visited: Optional[Set[str]] = None) -> Program:
        """Load a program by name, merging builtin with user plugin if needed.
        
        Priority:
        1. Check merged cache
        2. Discover all builtin and user programs
        3. Load user program if exists
        4. Load builtin program if exists
        5. If both exist:
           - If user has `_extends` field: merge (user extends builtin)
           - Else: error (can't have both without inheritance)
        6. If only one exists: wrap in Program
        7. If neither exists: raise ProgramNotFound
        8. Cache and return Program
        
        Args:
            name: Program name (e.g., "git", "neovim")
            visited: Set of visited program names (for circular detection)
            
        Returns:
            Program object with full interface
            
        Raises:
            ProgramNotFound: If neither builtin nor user plugin exists
            ProgramLoadError: If Lua parsing/loading fails
            CircularExtendError: If circular inheritance detected
        """
        # Initialize visited set on first call
        if visited is None:
            visited = set()
        
        # Check merged cache first
        if name in self._merged_cache:
            return self._merged_cache[name]
        
        # Check for circular extends
        if name in visited:
            raise CircularExtendError(
                f"Circular inheritance detected: {name} extends itself"
            )
        visited.add(name)
        
        # Discover all programs
        builtin_programs = self.discover_builtin()
        user_programs = self.discover_user_plugins()
        
        # Try to load user program first
        user_lua_def = None
        if name in user_programs:
            user_lua_def = self._load_lua_def(user_programs[name])
        
        # Try to load builtin program
        builtin_lua_def = None
        if name in builtin_programs:
            builtin_lua_def = self._load_lua_def(builtin_programs[name])
        
        # Handle different cases
        if user_lua_def and builtin_lua_def:
            # Both exist: user must extend builtin
            if "_extends" not in user_lua_def:
                raise ProgramLoadError(
                    f"Program '{name}' has both user plugin and builtin definition, "
                    f"but user plugin doesn't extend builtin. "
                    f"Add '_extends: \"{name}\"' to user plugin or rename it."
                )
            
            # Verify user extends the right parent
            parent_name = user_lua_def.get("_extends")
            if parent_name != name:
                raise ProgramLoadError(
                    f"Program '{name}' user plugin extends '{parent_name}', "
                    f"not itself. Check _extends field."
                )
            
            # If builtin also has _extends, follow the chain first
            if "_extends" in builtin_lua_def:
                builtin_parent_name = builtin_lua_def.get("_extends")
                builtin_parent = self.load_program(builtin_parent_name, visited)
                parent_program = Program(name, builtin_lua_def, parent=builtin_parent)
            else:
                # Create builtin Program without parent
                parent_program = Program(name, builtin_lua_def)
            
            self._builtin_cache[name] = parent_program
            
            # Now create merged Program with parent
            merged_program = Program(name, user_lua_def, parent=parent_program)
            self._merged_cache[name] = merged_program
            return merged_program
        
        elif user_lua_def:
            # Only user plugin exists
            if "_extends" in user_lua_def:
                # User plugin extends builtin, load parent
                parent_name = user_lua_def.get("_extends")
                if parent_name == name:
                    raise ProgramLoadError(
                        f"Program '{name}' user plugin tries to extend itself"
                    )
                
                parent_program = self.load_program(parent_name, visited)
                program = Program(name, user_lua_def, parent=parent_program)
            else:
                # Standalone user program
                program = Program(name, user_lua_def)
            
            self._user_cache[name] = program
            self._merged_cache[name] = program
            return program
        
        elif builtin_lua_def:
            # Only builtin exists
            # Check if it extends something
            if "_extends" in builtin_lua_def:
                parent_name = builtin_lua_def.get("_extends")
                if parent_name == name:
                    raise ProgramLoadError(
                        f"Program '{name}' tries to extend itself"
                    )
                
                parent_program = self.load_program(parent_name, visited)
                program = Program(name, builtin_lua_def, parent=parent_program)
            else:
                program = Program(name, builtin_lua_def)
            
            self._builtin_cache[name] = program
            self._merged_cache[name] = program
            return program
        
        else:
            # Neither exists
            raise ProgramNotFound(
                f"Program '{name}' not found in builtin programs or user plugins. "
                f"Checked: {self.builtin_dir}, {self.plugin_dir}"
            )

    def list_programs(self) -> List[str]:
        """Return all available program names (builtin + user).
        
        Returns:
            Sorted list of program names
        """
        builtin = set(self.discover_builtin().keys())
        user = set(self.discover_user_plugins().keys())
        all_names = builtin | user
        return sorted(all_names)

    def get_program_info(self, name: str) -> Dict[str, Any]:
        """Get metadata about a program.
        
        Args:
            name: Program name
            
        Returns:
            Dict with keys:
            - name: program name
            - source: "builtin" | "user" | "merged"
            - schema: program schema dict
            - default_config: default config dict
            - extends: parent program name if inherited, else None
            
        Raises:
            ProgramNotFound: If program not found
        """
        program = self.load_program(name)
        
        # Determine source
        if name in self._merged_cache and program.parent is not None:
            source = "merged"
        elif name in self._builtin_cache:
            source = "builtin"
        else:
            source = "user"
        
        return {
            "name": program.name,
            "source": source,
            "schema": program.get_schema(),
            "default_config": program.lua_def.get("default_config", {}),
            "extends": program.lua_def.get("_extends") if program.parent else None,
        }
