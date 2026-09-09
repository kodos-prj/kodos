# Phase 3: Plugin System Design

**Document:** Architecture redesign support
**Phase:** 3
**Status:** Design - Review Required
**Last Updated:** 2026-09-09

---

## Overview

Phase 3 implements a plugin system allowing users to define custom programs without modifying Kodos source.

**Plugin types:**
- Programs: `~/.kod/plugins/programs/*.lua`
- Build templates: `~/.kod/plugins/build_templates/*.lua` (Phase 5)
- Custom modules: `~/.kod/plugins/modules/*.lua` (future)

---

## Plugin Loading Strategy

### Discovery

1. User creates plugin file: `~/.kod/plugins/programs/myapp.lua`
2. PluginLoader discovers during startup
3. Plugin is loaded and merged with builtin registry

### Validation

Before loading, plugin must:
- [ ] Be valid Lua syntax
- [ ] Define required fields (name, version, etc.)
- [ ] Have no name conflicts with builtins
- [ ] Have no circular dependencies

### Error Handling

**Scenario 1: Syntax Error**
```lua
-- ~/.kod/plugins/programs/bad.lua
return {
  name = "badapp"  -- missing comma!
}
```

**Expected behavior:**
- Lua parse fails
- Warning printed: "Plugin 'bad.lua' has syntax error on line X: ..."
- Plugin skipped (not loaded)
- System continues (degraded but working)

**Code:**
```python
try:
    plugin = lua.load_plugin(path)
except LuaSyntaxError as e:
    print(f"Warning: Plugin {path} syntax error: {e.line}: {e.message}")
    continue  # Skip this plugin
```

**Scenario 2: Missing Required Fields**
```lua
-- ~/.kod/plugins/programs/incomplete.lua
return {
  -- missing 'name' field!
  version = "1.0",
}
```

**Expected behavior:**
- Validation fails
- Error printed: "Plugin 'incomplete.lua' missing required field 'name'"
- Plugin skipped

**Scenario 3: Name Conflict**
```lua
-- ~/.kod/plugins/programs/git.lua (conflicts with builtin!)
return {
  name = "git",  -- Already defined in builtins!
  version = "2.0",
  schema = { ... }
}
```

**Expected behavior:**
- Conflict detected
- Warning printed: "Plugin 'git.lua' conflicts with builtin 'git'. Skipping."
- Builtin takes precedence

**Scenario 4: Circular Dependency**
```lua
-- ~/.kod/plugins/programs/app-a.lua
return {
  name = "app-a",
  depends = { "app-b" },
}

-- ~/.kod/plugins/programs/app-b.lua
return {
  name = "app-b",
  depends = { "app-a" },  -- Circular!
}
```

**Expected behavior:**
- Detected during loading
- Both plugins skipped
- Error printed: "Circular dependency: app-a → app-b → app-a"

---

## Plugin Schema

### Program Plugin
```lua
-- ~/.kod/plugins/programs/myapp.lua
return {
  name = "myapp",
  version = "1.0",
  description = "My custom application",
  
  -- Schema defining what config options are available
  schema = {
    enable = {
      type = "bool",
      default = false,
      description = "Enable myapp",
    },
    config_file = {
      type = "string",
      default = "/etc/myapp/config",
      description = "Config file location",
    },
  },
  
  -- Optional: config generator
  generate_config = function(user_options)
    return {
      -- Generated configuration
    }
  end,
}
```

### Build Template Plugin (Phase 5)
```lua
-- ~/.kod/plugins/build_templates/ninja.lua
return {
  name = "ninja",
  version = "1.0",
  description = "Ninja build system template",
  
  -- Function that generates build commands
  generate_commands = function(src_dir, options)
    local prefix = options.prefix or "/usr"
    return {
      "cd " .. src_dir,
      "cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=" .. prefix,
      "ninja",
      "ninja install",
    }
  end,
}
```

---

## Loading Process

### Flowchart
```
PluginLoader.load_all("programs")
  │
  ├─→ Discover: ~/.kod/plugins/programs/*.lua
  │
  ├─→ For each file:
  │    ├─→ Parse Lua (catch SyntaxError)
  │    ├─→ Validate schema (catch ValidationError)
  │    ├─→ Check for conflicts (with builtins)
  │    ├─→ Check dependencies (detect cycles)
  │    └─→ Add to registry OR log error + skip
  │
  └─→ Return: loaded plugins + errors
```

### Code Structure
```python
# kod/registry/loader.py

class PluginLoader:
    def load_all(self, plugin_type: str) -> Tuple[Dict, List[str]]:
        """Load all plugins of given type.
        
        Returns:
            (loaded_plugins, errors)
        """
        plugins = {}
        errors = []
        
        # 1. Discover
        plugin_files = self.discover(plugin_type)
        
        # 2. Load each
        for path in plugin_files:
            try:
                plugin = self.load_one(path)
                plugins[plugin['name']] = plugin
            except Exception as e:
                errors.append(str(e))
        
        return plugins, errors
    
    def load_one(self, path: str) -> Dict:
        """Load a single plugin.
        
        Raises:
            PluginSyntaxError
            PluginValidationError
            PluginConflictError
        """
        # Parse Lua
        data = self.parse_lua(path)
        
        # Validate
        self.validate_schema(data)
        
        # Check conflicts
        self.check_conflicts(data)
        
        return data
```

---

## Error Messages

### For Users
Clear, actionable error messages:

```
Warning: Plugin at ~/.kod/plugins/programs/bad.lua has syntax error:
  Line 5: unexpected symbol near '}'
  
  Plugin will be skipped. Check the file and try again.

Warning: Plugin 'myapp' conflicts with builtin program. Using builtin.

Error: Circular dependency detected in plugins:
  app-a → app-b → app-a
  
  These plugins will be skipped.
```

### For Logs
Include full context for debugging:

```
[WARNING] Plugin load error: /home/user/.kod/plugins/programs/test.lua
  Type: PluginValidationError
  Message: Missing required field 'name'
  Stack: ...
```

---

## Logging Strategy

Plugins should not cause silent failures.

```python
# Levels:
# - INFO: Plugin loaded successfully
# - WARNING: Plugin skipped (validation failed, conflict, etc.)
# - ERROR: Critical failure (can't load plugin system)

logger.info(f"Loaded plugin 'git' from ~/.kod/plugins/programs/git.lua")
logger.warning(f"Skipped plugin 'bad.lua': syntax error on line 5")
logger.error(f"Failed to load plugins: {reason}")
```

---

## Testing Strategy

### Unit Tests
- Plugin parsing (valid, invalid Lua)
- Validation (missing fields, wrong types)
- Conflict detection
- Circular dependency detection

### Integration Tests
- Load real plugins
- Verify plugin configuration generators work
- Test with missing/broken plugins

### Example Test Cases
```python
def test_plugin_syntax_error():
    """Skips plugin with syntax error."""
    # Given a broken plugin file
    # When loading plugins
    # Then plugin is skipped and warning is logged

def test_plugin_name_conflict():
    """Skips plugin conflicting with builtin."""
    # Given a plugin named 'git' (same as builtin)
    # When loading plugins
    # Then builtin is used, plugin is skipped

def test_circular_dependency():
    """Detects circular plugin dependencies."""
    # Given plugins: a→b, b→a
    # When loading
    # Then both skipped and error logged
```

---

## Security Considerations

**Risk:** Malicious plugins executing arbitrary code

**Mitigations:**
1. **No execution at load time** — Plugins are data (tables), not executable
2. **Validation before use** — Config generators are functions, but only called when used
3. **User awareness** — Clear warning when loading plugins from untrusted sources
4. **Sandboxing** — Future: run plugin functions in isolated Lua context

**Not implemented initially; can be added in Phase 5 or later**

---

## Implementation Checklist (Phase 3)

- [ ] `kod/registry/loader.py`: PluginLoader class
- [ ] `discover()`: Find plugin files
- [ ] `parse_lua()`: Load and parse Lua
- [ ] `validate_schema()`: Check required fields
- [ ] `check_conflicts()`: Detect name conflicts
- [ ] `check_dependencies()`: Detect cycles
- [ ] Error handling for all above
- [ ] Logging for load success/failure
- [ ] Tests for each scenario
- [ ] User documentation

---

## Future Enhancements

- Semantic versioning for plugin dependencies
- Plugin version compatibility checking
- Sandboxed plugin execution (Phase 5+)
- Plugin marketplace/registry
- Plugin development tools (scaffolding, testing)

