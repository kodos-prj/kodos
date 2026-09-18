# KodOS Python Codebase Analysis

**Project Location:** `/home/abuss/Work/devel/analysis/kodos/src/kod/`

---

## Directory Structure Overview

```
kod/
├── bootstrap.py           # Lua bootstrap bridge
├── common.py              # Core utilities (exec, logging, colors)
├── context.py             # Execution context wrapper
├── exceptions.py          # Custom exception hierarchy
├── executor.py            # Step execution runtime
├── hooks.py               # Lifecycle hook collection
├── kod.py                 # Main CLI interface (Click)
├── lua_runtime.py         # Singleton Lua runtime manager
├── planner.py             # Execution plan builder
├── registry_wrapper.py    # Phase 1/2 registry orchestration
│
├── cli/                   # CLI command modules
│   ├── __init__.py
│   └── registry.py        # Registry CLI commands
│
├── config/                # Configuration system
│   ├── __init__.py
│   ├── schema.py          # Schema loading from Lua
│   ├── loader.py          # Config file parsing
│   ├── validator.py       # Config validation
│   ├── compiler.py        # Dependency resolution
│   └── template.py        # Template generation
│
├── core/                  # Core workflows (Phase 3)
│   ├── __init__.py        # Main re-export module
│   └── user_config.py     # User dotfiles/scripts
│
├── registry/              # Program registry system
│   ├── __init__.py
│   ├── loader.py          # Plugin discovery and loading
│   ├── programs.py        # Program class and errors
│   └── util.py            # Shared utilities
│
├── lib/                   # Lua code directory
│
└── system/                # System operations
    ├── __init__.py
    ├── boot.py            # Bootloader management
    ├── filesystem.py      # Partitioning, fstab, mounts
    ├── packages.py        # Package management
    ├── services.py        # Service management
    ├── users.py           # User management
    └── distro/            # Distro-specific modules
        ├── __init__.py
        ├── factory.py     # Distro selection strategy
        ├── arch.py        # Arch Linux specific
        └── debian.py      # Debian specific
```

---

## Module-by-Module Analysis

### ROOT LEVEL MODULES

#### `bootstrap.py`
- **Purpose:** Bridge between Lua bootstrap modules and Python Step objects
- **Key Functions:**
  - `emit_bootstrap_steps(conf, partition_list, distro)` - Converts Lua bootstrap modules to Step objects
  - `_convert_to_lua_table(lua, value)` - Recursively converts Python to Lua tables
  - `_lua_table_to_dict(lua_table)` - Recursively converts Lua tables to Python dicts
- **Dependencies:** `kod.planner.Step`, `kod.lua_runtime`
- **Usage:** Called during install/rebuild to generate filesystem bootstrap steps

#### `common.py`
- **Purpose:** Core utilities for command execution, logging, and debug output
- **Key Classes:**
  - `color` - ANSI color codes for terminal output
- **Key Functions:**
  - `exec(cmd, get_output, encoding)` - Execute shell commands with error handling
  - `exec_chroot(cmd, mount_point, ...)` - Execute commands in chroot environment
  - `exec_critical(cmd, error_msg)` - Execute commands that must succeed
  - `exec_warn(cmd, warning_msg)` - Execute commands with non-fatal failure handling
  - `set_debug(val)`, `set_verbose(val)` - Configure global debug/verbose modes
- **Global State:**
  - `use_debug`, `use_verbose` - Debug flags (affects `exec()` behavior)
  - `problems` - List of execution problems encountered
- **Usage:** Foundational utility used throughout system

#### `context.py`
- **Purpose:** Execution context management for command operations
- **Key Classes:**
  - `Context` - Represents execution environment (user, mount point, chroot mode, stage)
- **Key Methods:**
  - `execute(command, get_output)` - Execute commands in context (with chroot or su wrapping)
- **Dependencies:** `kod.common.exec`, `kod.common.exec_chroot`
- **Usage:** Used in user configuration and rebuild workflows

#### `exceptions.py`
- **Purpose:** Custom exception hierarchy for KodOS
- **Key Classes:**
  - `KodosError` - Base exception with context dict
  - `ValidationError` - Configuration validation failures (with location and suggestion fields)
- **Usage:** Used in config validation pipeline

#### `executor.py`
- **Purpose:** Execute step-based rebuild/install workflows via Lua runner
- **Key Classes:**
  - `StepError` - Raised when step fails with on_error='abort'
  - `StepResult` - Result of executing a single step
- **Key Functions:**
  - `execute_steps(steps, env, mount_point, use_chroot, repos, hooks)` - Run steps via Lua executor
- **Dependencies:** `kod.planner.Step`, `kod.bootstrap._convert_to_lua_table`, `kod.lua_runtime`
- **Usage:** Core execution engine for install/rebuild; dispatches to Lua handler

#### `hooks.py`
- **Purpose:** Lifecycle hook collection and validation
- **Key Constants:**
  - `VALID_HOOKS` - Fixed set: pre:package, post:package, pre:service, post:service, etc.
- **Key Functions:**
  - `collect_hooks(programs)` - Extract and validate hooks from program definitions
- **Usage:** Collects hooks before plan execution for firing during steps

#### `kod.py`
- **Purpose:** Main CLI interface (Click framework)
- **Key Commands:**
  - `config validate` - Validate configuration file
  - `config compile` - Compile config and resolve dependencies
  - `config schema` - Display schema with documentation
  - `config init` - Generate starter config template
  - `registry list/info/schema/generate` - Program registry commands
  - `install` - Full install workflow
  - `plan` - Preview execution plan
  - `rebuild` - Rebuild system with current/new generation
  - `rebuild_user` - Rebuild user configuration
  - `shell` - Run shell with schroot
- **Key Functions:**
  - `_wrap_text(text, width, indent)` - Text wrapping utility
  - `_print_section_text(name, data, level)` - Pretty-print schema sections
  - `_load_current_state()` - Resolve current generation state
  - `_cleanup_failed_generation(generation_id, new_root_path)` - Cleanup on failure
- **Dependencies:** All major modules (config, core, planner, executor, hooks, system)
- **Usage:** Entrypoint for all user interactions

#### `lua_runtime.py`
- **Purpose:** Singleton Lua runtime manager for all Lua integration
- **Key Classes:**
  - `LuaRuntimeManager` - Singleton manager using `__new__` pattern
- **Key Functions:**
  - `get_lua_runtime()` - Get global persistent Lua runtime
  - `cleanup_lua_runtime()` - Clean up global runtime
- **Features:**
  - Prevents "cannot mix objects from different Lua runtimes" errors
  - Auto-preloads common modules for backward compatibility
  - Registers cleanup on exit via atexit
- **Usage:** All Lua integration depends on this (bootstrap, planner, executor)

#### `planner.py`
- **Purpose:** Read-only execution plan builder
- **Key Classes:**
  - `Step` - Immutable step definition (frozen dataclass)
- **Key Functions:**
  - `compose_steps_lua(config, distro)` - Call Lua planner for install
  - `compose_rebuild_steps_lua(state)` - Call Lua planner for rebuild diff
  - `build_plan(conf, dist, baseline, current_packages, current_services, ...)` - Route to correct planner
  - `plan_install(conf)` - Full install preview
  - `plan_rebuild(conf, dist, current_packages, current_services, ...)` - Rebuild preview
  - `predict_partition_list(conf)` - Pre-compute partitions without execution
  - `plan_disk_steps(conf)` - Disk wipe/partition/format steps
  - `render_plan(steps, baseline, config_path)` - Text render for golden-file testing
  - `_convert_lua_step_to_step(lua_step)` - Convert Lua step to Python Step
  - `_attach_hooks_to_steps(steps, hooks_map)` - Attach hook metadata to steps
- **Dependencies:** `kod.lua_runtime`, `kod.bootstrap._convert_to_lua_table`, `kod.hooks.collect_hooks`
- **Usage:** Called by `kod plan` and `kod install/rebuild` to build execution plan

#### `registry_wrapper.py`
- **Purpose:** Thin orchestration wrapper; Python delegates to Lua
- **Key Classes:**
  - `PluginLoader` - Inherits from Python registry (Phase 1 fallback)
  - `Program` - Inherits from Python Program (Phase 1 fallback)
- **Re-exports:** All exception classes for backward compatibility
- **Phase Transition:** Phase 1 uses Python registry as fallback; Phase 2+ will call Lua directly
- **Usage:** Main API for registry operations; used by CLI and config system

---

### CLI MODULE

#### `cli/__init__.py`
- **Purpose:** CLI command module initialization
- **Exports:** `registry_group` for CLI registration

#### `cli/registry.py`
- **Purpose:** CLI commands for program registry
- **Key Commands:**
  - `registry list` - List all available programs
  - `registry info <name>` - Show program details
  - `registry schema <name>` - Show program schema as JSON
  - `registry generate <name>` - Generate config for program
- **Key Functions:**
  - `_display_schema(schema, indent)` - Pretty-print schema
- **Dependencies:** `kod.registry_wrapper`, `kod.registry.util`
- **Usage:** Called via `kod registry` CLI group

---

### CONFIG MODULE

#### `config/__init__.py`
- **Purpose:** Configuration subsystem initialization
- **Version:** 2.0.0-alpha

#### `config/schema.py`
- **Purpose:** Load Lua schema as single source of truth
- **Key Functions:**
  - `get_lua_schema()` - Load Lua schema and cache it
  - `_lua_table_to_dict(lua_table)` - Convert Lua table to Python dict
- **Features:**
  - Lazy loading with caching
  - Detects array vs hash tables by key types
- **Dependencies:** `kod.lua_runtime`
- **Usage:** Called by validator, compiler, template generator

#### `config/loader.py`
- **Purpose:** Configuration file parsing and loading
- **Key Functions:**
  - `load_config(config_path)` - Load Lua config and convert to Python dict
  - `_lua_to_python(value)` - Recursively convert Lua to Python
- **Features:**
  - Handles Lua require() statements
  - Detects Lua arrays (1-indexed) vs dicts
- **Dependencies:** `kod.core.load_config` (Lua-based)
- **Usage:** Called by `kod config compile` and validation pipeline

#### `config/validator.py`
- **Purpose:** Configuration validation against Lua schema
- **Key Functions:**
  - `validate_config(config)` - Main validation entry point (called by kod.py)
  - `_validate_against_lua_schema(config)` - Validate against Lua schema
  - `_validate_section_recursive(field_name, schema_def, value, path)` - Recursive validation
  - `_lookup_field_help(section_key, field_path)` - Look up field help
  - `_suggest(key)` - Suggest close matches for typos
- **Features:**
  - Phase 5c: Uses Lua schema as single source of truth
  - Validates required fields, types, enums, nested structures
  - Phase 3: Loads and validates programs section
- **Dependencies:** `kod.config.schema`, `kod.exceptions.ValidationError`
- **Usage:** Called by `kod config validate` and `kod config compile`

#### `config/compiler.py`
- **Purpose:** Configuration compilation and dependency resolution
- **Key Functions:**
  - `compile_config(config)` - Main compilation entry point
  - `_apply_desktop_manager_dependencies(config)` - Resolve desktop env → display manager
  - `_compile_programs(config)` - Phase 3: Compile programs section
  - `_deep_copy(value)` - Deep copy nested structures
- **Features:**
  - Resolves implicit dependencies (GNOME → gdm, etc.)
  - Phase 3: Compiles programs from system + user levels
- **Dependencies:** `kod.registry_wrapper`
- **Usage:** Called by `kod config compile` after validation

#### `config/template.py`
- **Purpose:** Generate starter configuration templates
- **Key Functions:**
  - `generate_config_template(distro)` - Generate template Lua config
- **Features:**
  - Generates Lua config with all sections documented
  - Uses Lua schema descriptions
- **Dependencies:** `kod.config.schema`
- **Usage:** Called by `kod config init`

---

### CORE MODULE

#### `core/__init__.py`
- **Purpose:** Main re-export module for core workflows (Phase 3 complete)
- **Key Sections:**
  1. **Base Distribution Selection:**
     - `set_base_distribution(base_dist)` - Set distro and return distro module
  2. **Path Helper Functions:** `is_dir()`, `is_file()`, `home_dir()`, `exists()`, `absolute()`, `expanduser()`
  3. **Configuration Loading:**
     - `load_config(config_filename)` - Load Lua config as table
  4. **User Configuration Processing:**
     - `user_dotfile_manager(info)` - Get dotfile manager config
     - `user_configs(user, info)` - Get user configs
     - `user_services(user, info)` - Get user services
  5. **Re-exports from System Modules:**
     - From `kod.system.filesystem`: `generate_fstab`, `load_fstab`, `change_subvol`
     - From `kod.system.users`: `proc_user_home`
     - From `kod.system.packages`: `get_packages_to_install`, `load_repos`, `load_package_lock`, `store_packages_services`, etc.
     - From `kod.system.services`: `enable_services`, `enable_user_services`, `get_services_to_enable`, etc.
     - From `kod.system.boot`: `create_boot_entry_hook`, `get_kernel_version`, `update_kernel_hook`, `update_initramfs_hook`
- **Usage:** Central hub for system workflows; high-level orchestration

#### `core/user_config.py`
- **Purpose:** User configuration workflow orchestration
- **Key Functions:**
  - `configure_user_dotfiles(ctx, user, user_configs, dotfile_mngrs)` - Deploy dotfiles
  - `configure_user_scripts(ctx, user, user_configs)` - Execute user scripts
- **Features:**
  - Temporarily changes context user during configuration
  - Calls dotfile manager command and script executables
- **Dependencies:** `kod.context.Context`
- **Usage:** Called by `kod rebuild_user`

---

### REGISTRY MODULE

#### `registry/__init__.py`
- **Purpose:** Registry subsystem initialization
- **Note:** Main API is via `kod.registry_wrapper` to avoid circular imports

#### `registry/loader.py`
- **Purpose:** Plugin auto-discovery and loading
- **Key Classes:**
  - `PluginLoader` - Auto-discovers and loads programs
- **Key Methods:**
  - `discover_builtin()` - Discover builtin programs from `kod/registry/builtin/`
  - `discover_user_plugins()` - Discover user plugins from `~/.kod/plugins/programs/`
  - `load_program(name, visited)` - Load program (with inheritance resolution)
- **Features:**
  - Delegates compute logic to Lua (loader.lua, inheritance.lua)
  - Caches loaded programs
  - Detects circular inheritance
- **Dependencies:** `lupa.LuaRuntime`, `kod.registry.programs`
- **Usage:** Called by CLI and config compilation

#### `registry/programs.py`
- **Purpose:** Program definitions and error hierarchy
- **Key Classes:**
  - `Program` - Wraps Lua program definition with Python interface
  - Exception hierarchy: `ProgramError`, `ProgramNotFound`, `ProgramLoadError`, `CircularExtendError`, `ConfigValidationError`, `SchemaError`
- **Key Methods:**
  - `Program.__init__(name, lua_def, parent)` - Initialize from Lua definition
  - `Program.get_scope()` - Return scope (system/user/both)
  - `Program.get_schema()` - Return merged JSON schema
  - `Program.validate_config(user_config)` - Validate config against schema
  - `Program.generate_config(user_config)` - Call Lua function to generate
- **Features:**
  - Validates required fields and scope
  - Supports inheritance via parent programs
  - Service field validation (optional, depends on scope)
- **Usage:** Wraps loaded programs for validation and generation

#### `registry/util.py`
- **Purpose:** Shared registry utilities
- **Key Functions:**
  - `lua_to_dict(obj)` - Convert lupa Lua objects to Python dicts/lists
- **Re-exports:** All exception classes
- **Usage:** Used by CLI and registry modules

---

### SYSTEM MODULE

#### `system/__init__.py`
- **Purpose:** System operations subsystem initialization

#### `system/boot.py`
- **Purpose:** Bootloader and kernel management
- **Key Functions:**
  - `get_kernel_version(mount_point)` - Get kernel version from chroot
  - `get_kernel_file(mount_point, package)` - Re-export from distro module
  - `_read_root_device(fstab_path)` - Read root device UUID from fstab
  - `create_boot_entry_hook(generation, kernel_package, mount_point)` - Create systemd-boot entry
  - `update_kernel_hook(kernel_package, mount_point)` - Update kernel files
  - `update_initramfs_hook(kernel_package, mount_point)` - Regenerate initramfs
- **Features:**
  - Supports multiple generations with different kernel versions
  - Generates systemd-boot entries with proper root device UUIDs
  - Derives kernel version and initramfs filenames from installed packages
- **Dependencies:** `kod.common.exec`, `kod.common.exec_chroot`, `kod.system.distro.factory`
- **Usage:** Called during install/rebuild as plan steps

#### `system/filesystem.py`
- **Purpose:** Filesystem operations (partitioning, mounts, fstab)
- **Key Classes:**
  - `FsEntry` - Filesystem entry for fstab configuration
- **Key Functions:**
  - `get_partition_devices(conf)` - Get boot and root partition devices
  - `generate_fstab(partition_list, mount_point)` - Generate fstab file
  - `load_fstab(mount_point)` - Load and parse fstab
  - `change_subvol(partition_list, subvol, mount_points)` - Update subvolume references
  - `create_next_generation(boot_partition, root_partition, generation_id)` - Create new generation
  - `get_max_generation()` - Get highest generation number
- **Data:**
  - `_filesystem_cmd` - Filesystem type → mkfs command mappings
  - `_filesystem_type` - Filesystem type → GPT type ID mappings
- **Dependencies:** `kod.common.exec`
- **Usage:** Called during partition/mount setup and generation management

#### `system/packages.py`
- **Purpose:** Package management (installation, updates, repos)
- **Key Functions:**
  - `get_base_packages(conf)` - Re-export from distro module
  - `get_list_of_dependencies(pkg)` - Re-export from distro module
  - `get_packages_to_install(conf)` - Extract packages from config
  - `load_repos()` - Load repository configuration
  - `load_package_lock(state_path)` - Load package lock file
  - `store_packages_services(state_path, packages, services)` - Store state
  - `manage_packages_shell(repos, action, packages, chroot)` - Execute package actions
  - `get_packages_updates(mount_point)` - Get available updates
  - `update_all_packages(mount_point, generation_id)` - Update all packages
  - `get_pending_packages(mount_point)` - Get pending installs/removals
- **Key Privilege Functions:**
  - `_get_privilege_level(repo)` - Determine privilege level (user/sudo/root)
  - `_build_privilege_command(base_cmd, privilege_level)` - Add privilege escalation
- **Dependencies:** `kod.common.exec`, `kod.common.exec_chroot`, `kod.system.distro.factory`, `kod.system.services`
- **Usage:** Called during install/rebuild for package operations

#### `system/services.py`
- **Purpose:** Service management (enablement, configuration)
- **Key Functions:**
  - `proc_desktop_services(conf)` - Extract desktop services
  - `proc_services(conf)` - Extract services to install packages for
  - `proc_services_to_enable(ctx, conf)` - Extract services to enable
  - `get_services_to_enable(ctx, conf)` - Combine desktop + system services
  - `enable_services(ctx, services, mount_point)` - Enable systemd services
  - `enable_user_services(ctx, user, services)` - Enable user services
- **Dependencies:** `kod.common.exec`, `kod.common.exec_chroot`
- **Usage:** Called during install/rebuild for service setup

#### `system/users.py`
- **Purpose:** User management
- **Key Functions:**
  - `proc_user_home(ctx, user, info)` - Process user home configuration
- **Features:**
  - Calls "build" functions for home-related configs
- **Dependencies:** `kod.context.Context`
- **Usage:** Called during user configuration setup

#### `system/distro/factory.py`
- **Purpose:** Distro module factory (strategy pattern)
- **Key Functions:**
  - `get_distro_module(distro_name)` - Dynamically import distro module
- **Supported:** "arch", "debian"
- **Usage:** Used by boot.py and packages.py for distro-agnostic operations

#### `system/distro/arch.py` (summary)
- **Purpose:** Arch Linux specific operations
- **Provides:** Package management, boot, kernel, AUR support
- **Distro-specific implementations:**
  - `get_base_packages(conf)` - Base Arch packages
  - `get_list_of_dependencies(pkg)` - Query pacman dependencies
  - `get_kernel_file(mount_point, package)` - Find kernel in /boot
  - `proc_repos(conf, current_repos, update, mount_point)` - Process Arch repos (AUR, etc.)
  - `refresh_package_db(mount_point, generation_id)` - Update pacman cache
  - `generale_package_lock(mount_point, state_path)` - Generate pacman lock file
  - `kernel_update_required(current_kernel, next_kernel, lock, mount_point)` - Detect kernel changes

#### `system/distro/debian.py` (summary)
- **Purpose:** Debian Linux specific operations
- **Provides:** APT-based package management equivalent to Arch module

---

## Dependency Graph

### Core Dependencies
```
kod.common (base utilities)
    ↓ used by
kod.context, kod.executor, kod.bootstrap, kod.planner
    ↓
kod.lua_runtime (Lua integration singleton)
    ↓ used by
kod.bootstrap, kod.planner, kod.executor, kod.config.schema, kod.core
    ↓
kod.planner (execution plan builder)
    ↓ used by
kod.kod (main CLI)
    ↓
kod.executor (step execution)
    ↓
kod.hooks (lifecycle hooks)
```

### Configuration Pipeline
```
kod.config.loader (load Lua files)
    ↓
kod.config.schema (get schema from Lua)
    ↓
kod.config.validator (validate against schema)
    ↓
kod.config.compiler (resolve dependencies)
    ↓
kod.registry (load programs)
```

### System Operations
```
kod.core (main orchestration)
    ↓
kod.system.packages (package management)
kod.system.services (service management)
kod.system.boot (bootloader)
kod.system.filesystem (partitions/mounts)
kod.system.users (user config)
    ↓
kod.system.distro.factory (distro selection)
    ↓
kod.system.distro.arch or debian (distro-specific)
```

---

## Module Classification

### CORE vs UTILITY

**CORE MODULES** (Essential, heavy logic):
- `kod.planner` - Plan generation
- `kod.executor` - Step execution
- `kod.bootstrap` - Lua bridge for bootstrap
- `kod.config.validator` - Config validation
- `kod.config.compiler` - Dependency resolution
- `kod.registry` - Program registry
- `kod.system.*` - System operations
- `kod.core` - Orchestration hub

**UTILITY MODULES** (Support functions):
- `kod.common` - Command execution and logging
- `kod.exceptions` - Exception classes
- `kod.hooks` - Hook collection
- `kod.context` - Execution context wrapper
- `kod.lua_runtime` - Lua runtime manager
- `kod.config.schema` - Schema loading
- `kod.config.loader` - Config parsing
- `kod.config.template` - Template generation
- `kod.registry.util` - Utility functions
- `kod.system.distro.factory` - Distro selection

**INTERFACE MODULES** (CLI/Orchestration):
- `kod.kod` - Main CLI interface
- `kod.cli.registry` - Registry CLI commands
- `kod.registry_wrapper` - Registry orchestration (Phase 1/2)
- `kod.core` - System workflows

---

## Phase Transitions & Architecture Notes

### Phase 1/2 Transition (Registry)
- `kod.registry_wrapper` - Thin orchestration layer
- Currently wraps existing Python registry
- Will transition to calling Lua registry (kod/lib/registry/registry.lua)
- No change to public API

### Phase 3 (Programs)
- Config compiler loads and validates programs
- Programs stored in compiled config for install workflow
- Program hooks attached to steps before execution

### Phase 5c (Lua Schema)
- `kod.config.schema` loads Lua schema as single source of truth
- All validators read from Lua schema
- Schema used by config compiler and template generator

### Plan Preview (Read-only)
- `kod.planner` builds execution plans without side effects
- Output matches actual execution (same functions, no actual exec)
- Used by `kod plan` command for preview

---

## Key Design Patterns

1. **Singleton Pattern:** `LuaRuntimeManager` - Ensures single Lua runtime
2. **Strategy Pattern:** `system.distro.factory` - Runtime distro selection
3. **Frozen Dataclass:** `Step` - Immutable step representation
4. **Phase Transition:** Orchestration wrappers (registry, config) for gradual Lua migration
5. **Re-export Pattern:** `kod.core` re-exports from submodules for clean API
6. **Hook Pattern:** Lifecycle hooks collected before execution, fired during steps
7. **Error Aggregation:** Validator collects all errors before reporting

---

## Important Global State

- `kod.common.use_debug` - Debug mode flag (affects `exec()`)
- `kod.common.use_verbose` - Verbose mode flag (affects output)
- `kod.common.problems` - List of execution problems encountered
- `kod.lua_runtime._manager` - Global Lua runtime singleton
- `kod.config.schema._lua_schema_cache` - Cached Lua schema

---

## File Statistics

```
Total Python files: 36
Total lines: ~6,500+ (excluding comments and blanks)

Largest modules:
- kod.py: 748 lines (main CLI)
- kod.planner.py: 412 lines (plan builder)
- kod.registry/programs.py: 527 lines (program definitions)
- kod.system/packages.py: 582 lines (package management)
- kod.registry/loader.py: 254 lines (plugin loading)
- kod.executor.py: 104 lines (step execution)
```

