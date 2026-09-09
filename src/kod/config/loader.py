"""Configuration loading and parsing (Phase 1).

Loads Lua configuration files and resolves module imports.

Key components:
- ConfigLoader: Main loader class
- load_config(): Public API to load a config file
- resolve_imports(): Handle module imports and merging

Example:
    >>> loader = ConfigLoader()
    >>> config = loader.load("configuration.lua")
    >>> # config now has all imports resolved and merged
"""

# TODO (Phase 1): Implement config loader
#   - Parse Lua configuration files
#   - Resolve imports (relative paths, module search)
#   - Merge configs from multiple files
#   - Handle circular dependency detection
#   - Provide helpful error messages on parse failure
