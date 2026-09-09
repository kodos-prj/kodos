# Phase 3: Program Registry Design Specification

**Goal:** Implement a Lua-based, user-extensible program registry that allows users to define, configure, and install packages with composable, schema-validated configurations.

**Architecture:** Two-layer system: builtin programs (bundled Lua definitions) + user plugins (home directory overrides/extensions). Loader merges user definitions onto builtins, supporting full inheritance via `_extends` field.

**Tech Stack:** Python 3.9+, Lua/lupa, JSON schema, existing `kod.config` system

---

## Part 1: Core Concepts & Data Model

### Program Definition

A **Program** is a self-contained, configurable application installable by Kodos. Each program has:

1. **Identity**: `name` (e.g., "git", "neovim")
2. **Schema**: JSON schema describing valid config options
3. **Config Template**: Shell commands or Lua code to execute (with placeholders)
4. **Lifecycle Hooks**: Optional functions for pre/post-install, validation

### Program Sources

Programs come from two sources (in priority order):

1. **Builtin Programs** (`kod/registry/builtin/*.lua`)
   - Shipped with Kodos package
   - Read-only, canonical definitions
   - Define base contract/schema

2. **User Plugins** (`~/.kod/plugins/programs/*.lua`)
   - User-provided or third-party
   - Can extend builtins or define new programs standalone
   - Merged onto builtins at load time

### Inheritance Model (`_extends` Field)

A user plugin can inherit from a builtin program using the `_extends` field:

```lua
-- ~/.kod/plugins/programs/git.lua
return {
    _extends = "git",  -- Inherit from builtin git program
    
    -- Add or override fields
    schema = {
        custom_signing_key = {type = "string", required = false}
    },
    
    generate_config = function(self, options)
        -- Call parent (builtin) implementation
        local base = self:_parent_method("generate_config", options)
        
        -- Extend with custom logic
        if options.custom_signing_key then
            base = base .. "\ngit config --global user.signingkey '" .. options.custom_signing_key .. "'"
        end
        return base
    end
}
```

**Schema Composition:** User schema extends builtin schema using JSON schema `allOf`:

```python
# When loaded:
merged_schema = {
    "allOf": [
        builtin_schema,  # Base contract
        user_schema      # User extensions
    ]
}
```

---

## Part 2: Lua Program Interface

### Standard Program Definition Structure

**Minimum program definition:**
```lua
return {
    name = "git",
    schema = {
        user_name = {type = "string", required = true},
        email = {type = "string", required = true}
    },
    default_config = {
        user_name = "User",
        email = "user@example.com"
    },
    generate_config = function(self, options)
        -- Returns shell commands (string) or config dict
        return string.format(
            "git config --global user.name '%s'\n" ..
            "git config --global user.email '%s'",
            options.user_name,
            options.email
        )
    end
}
```

### Optional Lifecycle Hooks

```lua
return {
    name = "neovim",
    -- ... schema, default_config, generate_config ...
    
    -- Pre-install validation (optional)
    validate = function(self, options)
        if options.python_provider and not options.python_path then
            error("python_path required when python_provider=true")
        end
    end,
    
    -- Post-install hook (optional, runs after package installed)
    post_install = function(self, options, mount_point)
        -- Could create directories, set permissions, etc.
        os.execute("mkdir -p " .. mount_point .. "/home/user/.config/nvim")
    end,
    
    -- Pre-uninstall hook (optional)
    pre_uninstall = function(self, mount_point)
        -- Cleanup logic
    end
}
```

### Inheritance Helpers

When a program extends another, these methods are available:

```lua
-- Access parent program object
parent = self:_get_parent()

-- Call parent's method and wrap result
base_config = self:_parent_method("generate_config", options)

-- Get merged schema (for validation)
merged = self:_get_merged_schema()
```

---

## Part 3: Python Loader & Registry

### PluginLoader Class

**Responsibility**: Discover, load, merge, and validate programs from both sources.

```python
class PluginLoader:
    """Load and manage programs from builtin and user plugin directories."""
    
    def __init__(self, config_home: str = None):
        """Initialize loader.
        
        Args:
            config_home: Home directory for plugin discovery.
                         Defaults to ~/.kod/
        """
        self.config_home = Path(config_home) or Path.home() / ".kod"
        self.builtin_dir = Path(__file__).parent / "builtin"
        self.plugin_dir = self.config_home / "plugins" / "programs"
        
        self._builtin_cache = {}  # name -> Program
        self._user_cache = {}     # name -> Program
        self._merged_cache = {}   # name -> Program (builtin + user merged)
    
    def discover_builtin(self) -> Dict[str, str]:
        """Find all builtin program .lua files.
        
        Returns:
            {program_name: file_path} dict
        """
        
    def discover_user_plugins(self) -> Dict[str, str]:
        """Find all user plugin .lua files in ~/.kod/plugins/programs/
        
        Returns:
            {program_name: file_path} dict
        """
        
    def load_program(self, name: str) -> "Program":
        """Load a program by name.
        
        Priority:
        1. Check merged cache
        2. Load builtin (if exists)
        3. Load user plugin (if exists)
        4. Merge if both exist (user extends builtin)
        5. Return merged or individual program
        
        Args:
            name: Program name (e.g., "git", "neovim")
            
        Returns:
            Program object with full interface
            
        Raises:
            ProgramNotFound: If neither builtin nor user plugin exists
            ProgramLoadError: If Lua parsing/loading fails
        """
        
    def list_programs(self) -> List[str]:
        """Return all available program names (builtin + user)."""
        
    def get_program_info(self, name: str) -> Dict:
        """Get metadata about a program.
        
        Returns:
            {
                "name": "git",
                "source": "builtin" | "user" | "merged",
                "schema": {...},
                "default_config": {...},
                "extends": "parent_name" if inherited else None
            }
        """
```

### Program Class (Python Wrapper)

```python
class Program:
    """Wraps a Lua program definition with Python interface."""
    
    def __init__(self, name: str, lua_def: Dict, parent: "Program" = None):
        """
        Args:
            name: Program name
            lua_def: Lua return value (dict from loaded .lua file)
            parent: Parent Program if this extends another
        """
        
    def get_schema(self) -> Dict:
        """Return merged JSON schema (builtin + user extensions).
        
        If this program extends another:
            {"allOf": [parent_schema, user_schema]}
        Otherwise:
            Raw schema from definition
        """
        
    def validate_config(self, options: Dict) -> bool:
        """Validate options against schema.
        
        Raises:
            ConfigValidationError: If options don't match schema
        """
        
    def generate_config(self, options: Dict) -> str:
        """Generate shell commands or config content.
        
        Args:
            options: User-provided config options
            
        Returns:
            Shell commands (string) or config file content
        """
        
    def run_hook(self, hook_name: str, *args) -> Any:
        """Run a lifecycle hook (validate, post_install, etc).
        
        Args:
            hook_name: "validate", "post_install", "pre_uninstall"
            *args: Arguments to pass to hook
            
        Returns:
            Hook result (typically None or error)
        """
```

---

## Part 4: Builtin Programs (Examples)

Three starter builtin programs (Phase 3):

### 1. git.lua

```lua
return {
    name = "git",
    
    schema = {
        user_name = {
            type = "string",
            required = true,
            description = "Git committer name"
        },
        email = {
            type = "string",
            format = "email",
            required = true,
            description = "Git committer email"
        },
        signing_key = {
            type = "string",
            required = false,
            description = "GPG key ID for signing commits"
        }
    },
    
    default_config = {
        user_name = "Default User",
        email = "user@localhost",
        signing_key = nil
    },
    
    generate_config = function(self, options)
        local config = string.format(
            "git config --global user.name '%s'\n" ..
            "git config --global user.email '%s'",
            options.user_name,
            options.email
        )
        
        if options.signing_key then
            config = config .. "\n" ..
                string.format("git config --global user.signingkey '%s'",
                    options.signing_key)
        end
        
        return config
    end
}
```

### 2. neovim.lua

```lua
return {
    name = "neovim",
    
    schema = {
        python_provider = {type = "boolean", default = false},
        ruby_provider = {type = "boolean", default = false},
        node_provider = {type = "boolean", default = true}
    },
    
    default_config = {
        python_provider = false,
        ruby_provider = false,
        node_provider = true
    },
    
    generate_config = function(self, options)
        local packages = {"neovim"}
        
        if options.python_provider then
            table.insert(packages, "python-pynvim")
        end
        if options.ruby_provider then
            table.insert(packages, "ruby-neovim")
        end
        if options.node_provider then
            table.insert(packages, "nodejs-neovim")
        end
        
        return "pacman -S " .. table.concat(packages, " ")
    end
}
```

### 3. syncthing.lua

```lua
return {
    name = "syncthing",
    
    schema = {
        auto_start = {type = "boolean", default = true},
        listen_address = {type = "string", default = "127.0.0.1:8384"}
    },
    
    default_config = {
        auto_start = true,
        listen_address = "127.0.0.1:8384"
    },
    
    generate_config = function(self, options)
        local config = "systemctl enable syncthing"
        
        if options.auto_start then
            config = config .. "\nsystemctl start syncthing"
        end
        
        return config
    end
}
```

---

## Part 5: User Plugin Example

User extends git with custom signing key:

```lua
-- ~/.kod/plugins/programs/git.lua
return {
    _extends = "git",  -- Inherit from builtin
    
    schema = {
        -- Add custom field to schema
        sign_commits = {
            type = "boolean",
            default = false,
            description = "Automatically sign all commits"
        }
    },
    
    generate_config = function(self, options)
        -- Get builtin git config
        local base = self:_parent_method("generate_config", options)
        
        -- Add custom logic
        if options.sign_commits then
            base = base .. "\ngit config --global commit.gpgsign true"
        end
        
        return base
    end,
    
    validate = function(self, options)
        if options.sign_commits and not options.signing_key then
            error("signing_key required when sign_commits=true")
        end
    end
}
```

---

## Part 6: CLI Interface

**New commands for Phase 3:**

```bash
# List all available programs (builtin + user)
kod registry list

# Get detailed info about a program
kod registry info git
kod registry info neovim

# Show schema for a program
kod registry schema git

# Generate config for a program (dry-run)
kod registry generate git --user-name "Alice" --email "alice@example.com"
```

**Example output:**
```
$ kod registry list
builtin:
  - git
  - neovim
  - syncthing
user:
  - git (extends builtin)
  - my_custom_tool

$ kod registry info git
Name: git
Source: merged (builtin + user)
Schema:
  - user_name (string, required)
  - email (string, required, format=email)
  - signing_key (string, optional)
  - sign_commits (boolean, optional) [user extension]

$ kod registry generate git --user-name "Alice" --email "alice@example.com"
git config --global user.name 'Alice'
git config --global user.email 'alice@example.com'
```

---

## Part 7: Integration with Config System

**In user's `~/.kod/config.lua`:**

```lua
return {
    -- ... existing config ...
    
    programs = {
        -- Define which programs to install
        git = {
            user_name = "Alice",
            email = "alice@example.com",
            signing_key = "ABC123DEF456"
        },
        neovim = {
            python_provider = true,
            node_provider = true
        }
    }
}
```

**During installation:**
1. Config validator reads `programs` section
2. For each program, loads it via `PluginLoader.load_program()`
3. Validates program options against merged schema
4. Calls `program.generate_config(options)`
5. Executes generated shell commands in chroot

---

## Part 8: Error Handling & Validation

### Error Types

```python
class ProgramError(Exception):
    """Base exception for program registry errors."""

class ProgramNotFound(ProgramError):
    """Program name not found in builtin or user plugins."""

class ProgramLoadError(ProgramError):
    """Lua parsing or loading failed."""
    
    # Includes: syntax errors, missing required fields, circular extends

class CircularExtendError(ProgramLoadError):
    """Program extends itself (directly or indirectly)."""

class ConfigValidationError(ProgramError):
    """User config doesn't match program schema."""
    
    # Includes: missing required fields, wrong types, format violations

class SchemaError(ProgramError):
    """Program schema is malformed."""
    
    # Includes: invalid JSON schema, conflicting field names between parent/child
```

### Validation Strategy

1. **Load-time validation**:
   - Check syntax of .lua files
   - Check required fields (name, schema, default_config, generate_config)
   - Check for circular extends
   - Validate schema format (JSON schema spec)

2. **Merge-time validation**:
   - Verify parent program exists (if `_extends` specified)
   - Merge schemas without conflicts
   - Check for method overrides consistency

3. **Config-time validation**:
   - Validate user options against merged schema
   - Run custom `validate()` hook if present
   - Report all validation errors with clear messages

---

## Part 9: Testing Strategy

**Unit tests:**
- Load builtin programs (syntax, structure)
- Load user plugins (discovery, parsing)
- Schema merging (no conflicts, correct composition)
- Program extension (inheritance, method chaining)
- Config validation (against merged schema)
- Error cases (circular extends, missing fields, bad schema)

**Integration tests:**
- Full workflow: load git builtin + user plugin extension
- Generate config with merged options
- Execute generated commands in chroot
- List and info commands (CLI)

**Example test:**
```python
def test_program_extension():
    loader = PluginLoader()
    
    # Load builtin
    git_builtin = loader.load_program("git")
    assert git_builtin.name == "git"
    
    # Create temp user plugin
    user_plugin = {
        "_extends": "git",
        "schema": {"sign_commits": {"type": "boolean"}}
    }
    
    # Load and merge (if user plugin exists)
    git_merged = loader.load_program("git")
    
    # Validate merged config
    options = {
        "user_name": "Alice",
        "email": "alice@example.com",
        "signing_key": "ABC123",
        "sign_commits": True
    }
    git_merged.validate_config(options)
    
    # Generate config
    config = git_merged.generate_config(options)
    assert "git config --global commit.gpgsign true" in config
```

---

## Part 10: Success Criteria

✅ **Functionality:**
- Builtin programs (git, neovim, syncthing) loadable and configurable
- User plugins discoverable from `~/.kod/plugins/programs/`
- Program extension via `_extends` works correctly
- Schema merging handles all cases without conflicts
- CLI commands (list, info, schema, generate) functional

✅ **User Experience:**
- Users can customize builtins without rewriting them
- Error messages are clear (show which program, which field, why it failed)
- Documentation explains how to write custom programs
- Example custom program included

✅ **Code Quality:**
- Full test coverage for loader, merging, validation
- Clean separation: Lua loading logic ≠ program logic
- No circular dependencies
- Type hints throughout

✅ **Integration:**
- Config system recognizes `programs` section
- Validation happens before installation
- Generated config executed correctly in chroot

---

## Global Constraints

- **Python 3.9+**: All code must support Python 3.9 minimum
- **Lua/lupa**: Requires lupa library (already used by kod.config)
- **JSON Schema**: Use JSON schema draft 7 for validation
- **File paths**: Use `pathlib.Path` consistently
- **No external dependencies**: Only use stdlib + existing deps
- **Backward compatibility**: Config system must continue working

---
