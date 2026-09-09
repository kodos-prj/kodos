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

# TODO (Phase 3): Implement plugin loader
#   - Discover .lua files in ~/.kod/plugins/
#   - Load and validate plugins
#   - Merge with builtin registry
#   - Handle plugin errors gracefully
