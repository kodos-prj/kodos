# Kodos Architecture Redesign Specification

**Date:** 2026-09-09  
**Status:** Approved for Implementation  
**Author:** Architecture Review  
**Priority:** High

---

## Executive Summary

Restructure Kodos from a monolithic Python core (2,038 lines in core.py) into a **layered, modular system** with:

1. **NixOS-style configuration system** — modular Lua imports, declarative schema, implicit dependency resolution
2. **Focused Python modules** — split core.py by responsibility (packages, users, boot, services, filesystem)
3. **Declarative program registry** — extensible, no-code way to add configurable programs
4. **Compile phase** — validate config before execution, catch errors in seconds not hours
5. **Structured error handling** — replace fragile global state with proper exceptions

**Goals:**
- Improve code maintainability (clear module boundaries)
- Reduce configuration errors (upfront validation)
- Enable extensibility (program registry, plugin system)
- Maintain backward compatibility with existing Lua configs (via deprecation path)

---

## Part 1: Problem Analysis

### 1.1 Python Structure Issues

**Current state:**
- `src/kod/core.py`: 2,038 lines handling install, rebuild, user config, package mgmt, boot, services
- No clear module boundaries; functions call across concerns
- Hard to test individual operations in isolation
- Distribution-specific logic mixed with generic orchestration

**Impact:**
- Difficult to understand code flow
- High cognitive load to modify safely
- Tests are integration-level, not unit-level
- Adding Debian support requires grepping and modifying in multiple places

### 1.2 Configuration System Issues

**Current state:**
- Single `configuration.lua` file; no module system
- No upfront validation; errors caught during installation (hours later)
- Program configurations are ad-hoc Lua helper functions
- No schema or type information

**Impact:**
- User can't introspect available options
- Typos in config aren't caught until execution starts
- Config copy-paste; hard to maintain across machines
- Adding a new program requires Lua coding

### 1.3 Program Configuration Issues

**Current state:**
- Programs configured via Lua helper functions (e.g., `configs.git()`, `configs.syncthing()`)
- No central list of available programs or their options
- Program options not discoverable

**Impact:**
- Users must read source code to find available programs
- Can't validate program options upfront
- Hard to add new programs without touching Kodos source

### 1.4 Error Handling Issues

**Current state:**
- Global `problems` list to track command failures
- Dead exception classes (`CommandTimeoutError`, `UnsafeCommandError`)
- Errors logged twice (logger + global list)
- No structured error recovery

**Impact:**
- Errors are silent/hidden in global state
- Hard to debug; unclear what failed
- Can't test error paths cleanly

---

## Part 2: Proposed Architecture

### 2.1 Layered Design

```
┌─────────────────────────────────────────┐
│        CLI Layer (kod.py)               │
│   Commands: install, rebuild, etc.     │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     Orchestration Layer (core/)         │
│  - install workflow                     │
│  - rebuild workflow                     │
│  - user-config workflow                 │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     System Operations (system/)         │
│  - packages                             │
│  - services                             │
│  - users                                │
│  - boot                                 │
│  - filesystem                           │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Distribution Layer (distributions/)    │
│  - arch.py (Arch-specific impl)         │
│  - debian.py (Debian-specific impl)     │
│  - base.py (abstract interface)         │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│     Config Layer (config/)              │
│  - loader (Lua parsing)                 │
│  - compiler (module resolution)         │
│  - validator (schema checking)          │
│  - schema (option definitions)          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│    Registry Layer (registry/)           │
│  - programs (program definitions)       │
│  - loader (plugin discovery)            │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   Common Layer (common.py)              │
│  - exec() (command execution)           │
│  - logging                              │
│  - errors                               │
└─────────────────────────────────────────┘
```

### 2.2 Directory Structure

```
src/kod/
├── __init__.py
├── kod.py                    # CLI entry point
├── common.py                 # Execution, logging, errors
│
├── core/                     # Orchestration workflows
│   ├── __init__.py
│   ├── install.py            # Install workflow
│   ├── rebuild.py            # Rebuild workflow
│   ├── user_config.py        # User dotfiles/services workflow
│   └── helpers.py            # Shared helpers
│
├── config/                   # Configuration loading & validation
│   ├── __init__.py
│   ├── schema.py             # Option definitions, types, defaults
│   ├── loader.py             # Parse Lua, load files
│   ├── compiler.py           # Resolve modules, flatten, compute deps
│   └── validator.py          # Type-check against schema
│
├── system/                   # System-level operations
│   ├── __init__.py
│   ├── packages.py           # Package management
│   ├── services.py           # Service management
│   ├── users.py              # User/group management
│   ├── boot.py               # Bootloader, kernel, initramfs
│   └── filesystem.py         # Partitions, mounts, fstab
│
├── distributions/            # Distribution-specific implementations
│   ├── __init__.py
│   ├── base.py               # Abstract base class
│   ├── arch.py               # Arch Linux
│   └── debian.py             # Debian/Ubuntu
│
├── registry/                 # Program & option registry
│   ├── __init__.py
│   ├── programs.py           # Builtin program definitions
│   └── loader.py             # Plugin discovery
│
└── lib/                      # Lua standard library (existing)
    ├── configs.lua
    ├── disk.lua
    ├── repos.lua
    └── ...
```

---

## Part 3: Configuration System Redesign

### 3.1 Module System (Lua)

**Current:**
```lua
-- example/testvm/configuration.lua (one file, ~300 lines)
local disk = require("disk")
local repos = require("repos")
local configs = require("configs")

return {
  repos = { ... },
  devices = { ... },
  boot = { ... },
  -- ... 50+ options in one file
}
```

**Proposed:**
```lua
-- example/testvm/configuration.lua (entry point, ~50 lines)
return {
  imports = {
    "modules/base",           -- base system
    "modules/hardware",       -- hardware features
    "modules/desktop/gnome",  -- desktop environment
    "modules/users/demo",     -- user configurations
  },
  
  config = {
    -- System-level overrides
    hostname = "my-vm",
    locale.timezone = "America/Edmonton",
  }
}

-- example/testvm/modules/base/default.lua
return {
  config = {
    boot.kernel.package = "linux-lts",
    boot.loader.type = "systemd-boot",
    network.ipv6 = false,
  }
}

-- example/testvm/modules/desktop/gnome.lua
return {
  config = {
    desktop.gnome.enable = true,
    desktop.gnome.extra_packages = { "gnome-tweaks" },
    -- display_manager auto-set to "gdm" by compiler
  }
}
```

**Benefits:**
- Configs are modular and reusable
- Clear structure: base, hardware, desktop, users are separate
- Easier to maintain across multiple machines

### 3.2 Schema & Option Registry

All configurable options defined upfront in Python.

**Structure:**

```python
# kod/config/schema.py

SCHEMA = {
  # Boot configuration
  "boot.kernel.package": {
    "type": "string",
    "default": "linux",
    "description": "Kernel package to install",
    "enum": ["linux", "linux-lts", "linux-zen"],
  },
  "boot.loader.type": {
    "type": "enum",
    "values": ["systemd-boot", "grub"],
    "default": "systemd-boot",
    "description": "Bootloader to use",
  },
  
  # Desktop configuration
  "desktop.gnome.enable": {
    "type": "bool",
    "default": False,
    "description": "Enable GNOME desktop environment",
  },
  "desktop.gnome.extra_packages": {
    "type": "list(string)",
    "default": [],
    "description": "Additional GNOME packages to install",
  },
  
  # Network configuration
  "network.hostname": {
    "type": "string",
    "default": "kodos",
    "description": "System hostname",
  },
  "network.ipv6": {
    "type": "bool",
    "default": True,
    "description": "Enable IPv6 networking",
  },
  
  # ... more options
}
```

**Validator logic:**

```python
# kod/config/validator.py

def validate(config: dict) -> dict:
  """Validate config against schema."""
  errors = []
  
  for key, value in flatten(config).items():
    if key not in SCHEMA:
      errors.append(f"Unknown option: {key}")
      continue
    
    option_def = SCHEMA[key]
    
    # Type check
    if not type_check(value, option_def["type"]):
      errors.append(f"{key}: expected {option_def['type']}, got {type(value)}")
    
    # Enum check
    if "enum" in option_def and value not in option_def["enum"]:
      errors.append(f"{key}: must be one of {option_def['enum']}")
  
  # Cross-option constraints
  if config.get("desktop.gnome.enable") and config.get("desktop.plasma.enable"):
    errors.append("Cannot enable both GNOME and Plasma")
  
  if errors:
    raise ConfigError("\n".join(errors))
  
  return config
```

**Benefits:**
- Type-safe configuration
- Clear error messages
- Self-documenting options
- Enables CLI introspection: `kod config --schema`

### 3.3 Compilation Phase

**Goal:** Resolve module imports, flatten structure, compute implicit dependencies.

```python
# kod/config/compiler.py

def compile(config: dict) -> dict:
  """Compile raw config into flattened, resolved form."""
  
  # 1. Resolve imports
  config = resolve_imports(config, base_path)
  
  # 2. Flatten nested dicts into "key.subkey" format
  flat = flatten(config)
  
  # 3. Compute implicit dependencies
  flat = resolve_dependencies(flat)
  
  # 4. Apply defaults for unset options
  flat = apply_defaults(flat)
  
  # 5. Return nested dict (ready for validation)
  return unflatten(flat)


def resolve_dependencies(flat: dict) -> dict:
  """Auto-enable features when dependencies are satisfied."""
  
  # If GNOME is enabled, auto-set display manager
  if flat.get("desktop.gnome.enable"):
    if "display_manager" not in flat:
      flat["display_manager"] = "gdm"
    
    # Auto-add recommended packages
    packages = flat.get("packages", [])
    gnome_fonts = [
      "ttf-liberation", "noto-fonts", "ttf-fira-sans"
    ]
    flat["packages"] = list(set(packages + gnome_fonts))
  
  # If Plasma is enabled, auto-set display manager
  if flat.get("desktop.plasma.enable"):
    if "display_manager" not in flat:
      flat["display_manager"] = "sddm"
  
  return flat
```

**Three-phase flow:**

```python
# kod/core/install.py (simplified)

def install(config_path: str, mount_point: str):
  """Install KodOS."""
  
  # Phase 1: Load
  print("Loading configuration...")
  raw_config = config.loader.load(config_path)
  
  # Phase 2: Compile
  print("Compiling configuration...")
  compiled = config.compiler.compile(raw_config)
  
  # Phase 3: Validate
  print("Validating configuration...")
  validated = config.validator.validate(compiled)
  
  # Now ready to execute
  print("Starting installation...")
  # ... rest of install logic
```

**Errors caught before touching the system:**
- Missing required options
- Conflicting settings
- Invalid types
- Unknown programs

---

## Part 4: Python Module Redesign

### 4.1 Core Orchestration

**kod/core/install.py** — Install workflow, ~150 lines

```python
def install(config_path: str, mount_point: str) -> None:
  """Install KodOS from configuration."""
  
  # Load & validate config (from config layer)
  conf = config.loader.load(config_path)
  conf = config.compiler.compile(conf)
  config.validator.validate(conf)
  
  # Get distribution implementation
  dist = get_distribution(conf.get("base_distribution", "arch"))
  
  # Phase 1: Partition & filesystem
  logger.info("Setting up partitions and filesystems...")
  partitions = system.filesystem.create_partitions(conf["devices"])
  partitions = system.filesystem.create_filesystems(partitions)
  partitions = system.filesystem.mount_all(partitions, mount_point)
  
  # Phase 2: Install base system
  logger.info("Installing base packages...")
  base_pkgs = dist.get_base_packages(conf)
  dist.install_packages(base_pkgs, mount_point)
  
  # Phase 3: Configure system
  logger.info("Configuring system...")
  system.boot.setup_bootloader(conf, partitions, dist, mount_point)
  system.users.create_users(conf["users"], mount_point)
  system.services.enable_services(conf.get("services", {}), mount_point)
  
  # Phase 4: Install packages
  logger.info("Installing configured packages...")
  repos = dist.load_repos(conf)
  pkgs = conf.get("packages", [])
  system.packages.install(pkgs, repos, mount_point)
  
  # Phase 5: Generate & store metadata
  logger.info("Storing generation metadata...")
  generation = store_generation_metadata(mount_point, conf)
  
  logger.info(f"Installation complete. Generation: {generation}")
```

**kod/core/rebuild.py** — Rebuild workflow, ~150 lines

```python
def rebuild(config_path: str, new_generation: bool = False, update: bool = False) -> None:
  """Rebuild system (install updates, modify config)."""
  
  # Load & validate config
  conf = config.loader.load(config_path)
  conf = config.compiler.compile(conf)
  config.validator.validate(conf)
  
  # Load current state
  current_gen = load_current_generation()
  current_conf = load_generation_config(current_gen)
  
  # Determine changes
  changes = compute_changes(current_conf, conf)
  
  # Apply changes
  if changes.get("packages_to_install"):
    system.packages.install(changes["packages_to_install"], mount_point="/")
  
  if changes.get("services_to_enable"):
    system.services.enable(changes["services_to_enable"], mount_point="/")
  
  if changes.get("services_to_disable"):
    system.services.disable(changes["services_to_disable"], mount_point="/")
  
  # Store new generation (or update current)
  if new_generation:
    new_gen = current_gen + 1
    store_generation_metadata("/", conf, gen=new_gen)
  else:
    update_generation_metadata("/", conf, gen=current_gen)
```

**kod/core/user_config.py** — User dotfiles/services, ~100 lines

```python
def rebuild_user(config_path: str, user: str) -> None:
  """Rebuild user-level configuration."""
  
  # Load & validate
  conf = config.loader.load(config_path)
  conf = config.compiler.compile(conf)
  config.validator.validate(conf)
  
  # Get user config
  if user not in conf.get("users", {}):
    raise ConfigError(f"User {user} not found in configuration")
  
  user_conf = conf["users"][user]
  
  # Setup dotfile manager
  if "dotfile_manager" in user_conf:
    mgr = user_conf["dotfile_manager"]
    system.users.setup_dotfiles(user, mgr)
  
  # Enable user services
  if "services" in user_conf:
    system.services.enable_user_services(user, user_conf["services"])
  
  # Deploy program configs
  if "programs" in user_conf:
    deploy_program_configs(user, user_conf["programs"])
```

### 4.2 System Operations

**kod/system/packages.py** — Package management, ~100 lines

```python
def install(packages: list[str], repos: dict, mount_point: str = "/") -> None:
  """Install packages."""
  
  # Group by repo (arch:pkg → arch repo, etc.)
  by_repo = {}
  for pkg in packages:
    repo, name = parse_package(pkg)  # "aur:foo" → ("aur", "foo")
    by_repo.setdefault(repo, []).append(name)
  
  # Install per-repo
  for repo, names in by_repo.items():
    if repo not in repos:
      raise DistributionError(f"Repository {repo} not found")
    
    repo_impl = repos[repo]
    repo_impl.install(names, mount_point)


def remove(packages: list[str], mount_point: str = "/") -> None:
  """Remove packages."""
  dist = get_distribution()
  dist.remove_packages(packages, mount_point)


def update(mount_point: str = "/") -> None:
  """Update all packages."""
  dist = get_distribution()
  dist.update_packages(mount_point)
```

**kod/system/services.py** — Service management, ~80 lines

```python
def enable(services: dict[str, dict], mount_point: str = "/") -> None:
  """Enable system services."""
  
  for service_name, service_config in services.items():
    if not service_config.get("enable"):
      continue
    
    # Resolve service name
    actual_name = service_config.get("service_name", service_name)
    
    logger.info(f"Enabling service: {actual_name}")
    exec_chroot(f"systemctl enable {actual_name}", mount_point=mount_point)
    
    # Apply custom configuration if needed
    if "config" in service_config:
      apply_service_config(actual_name, service_config["config"])


def disable(services: list[str], mount_point: str = "/") -> None:
  """Disable services."""
  for service in services:
    logger.info(f"Disabling service: {service}")
    exec_chroot(f"systemctl disable {service}", mount_point=mount_point)


def enable_user_services(user: str, services: dict) -> None:
  """Enable user-level services (systemd --user)."""
  for service_name, service_config in services.items():
    if not service_config.get("enable"):
      continue
    
    logger.info(f"Enabling user service: {service_name} for {user}")
    exec(f"sudo -u {user} systemctl --user enable {service_name}")
```

**kod/system/users.py** — User management, ~120 lines

```python
def create_users(users: dict[str, dict], mount_point: str = "/") -> None:
  """Create users and groups."""
  
  for username, user_config in users.items():
    # Skip root; already exists
    if username == "root":
      configure_root_user(user_config, mount_point)
      continue
    
    # Create user
    logger.info(f"Creating user: {username}")
    shell = user_config.get("shell", "/bin/bash")
    
    if user_config.get("no_password"):
      exec_chroot(
        f"useradd -m -s {shell} {username}",
        mount_point=mount_point
      )
    else:
      password = user_config.get("password")
      hashed = user_config.get("hashed_password")
      
      if hashed:
        exec_chroot(
          f"useradd -m -s {shell} -p {hashed} {username}",
          mount_point=mount_point
        )
      elif password:
        exec_chroot(
          f"useradd -m -s {shell} {username}",
          mount_point=mount_point
        )
        set_password(username, password, mount_point)


def setup_dotfiles(user: str, dotfile_manager: dict) -> None:
  """Setup dotfile manager (stow, yadm, etc.)."""
  # Implementation depends on manager type
  pass
```

**kod/system/boot.py** — Boot/kernel management, ~150 lines

```python
def setup_bootloader(conf: dict, partitions: list, dist, mount_point: str) -> None:
  """Setup bootloader."""
  
  boot_conf = conf.get("boot", {})
  loader_type = boot_conf.get("loader", {}).get("type", "systemd-boot")
  
  logger.info(f"Setting up {loader_type}...")
  
  if loader_type == "systemd-boot":
    setup_systemd_boot(conf, partitions, dist, mount_point)
  elif loader_type == "grub":
    setup_grub(conf, partitions, dist, mount_point)
  else:
    raise ConfigError(f"Unknown bootloader: {loader_type}")


def setup_systemd_boot(conf: dict, partitions: list, dist, mount_point: str) -> None:
  """Setup systemd-boot."""
  boot_part = get_boot_partition(partitions)
  
  # Install systemd-boot
  exec_chroot(
    f"bootctl --esp-path=/boot install",
    mount_point=mount_point
  )
  
  # Generate loader entries
  generate_boot_entries(conf, partitions, mount_point)
```

### 4.3 Distribution Layer

**kod/distributions/base.py** — Abstract interface

```python
from abc import ABC, abstractmethod

class Distribution(ABC):
  """Abstract base for distribution-specific operations."""
  
  @abstractmethod
  def get_base_packages(self, conf: dict) -> list[str]:
    """Return list of base packages for this distro."""
    pass
  
  @abstractmethod
  def install_packages(self, packages: list[str], mount_point: str) -> None:
    """Install packages via distro package manager."""
    pass
  
  @abstractmethod
  def remove_packages(self, packages: list[str], mount_point: str) -> None:
    """Remove packages."""
    pass
  
  @abstractmethod
  def get_repos(self, conf: dict) -> dict:
    """Load repository definitions from config."""
    pass
  
  @abstractmethod
  def setup_linux(self, mount_point: str) -> None:
    """Distro-specific kernel/bootloader setup."""
    pass
```

**kod/distributions/arch.py** — Arch-specific implementation

```python
class ArchDistribution(Distribution):
  def get_base_packages(self, conf: dict) -> list[str]:
    """Get base packages for Arch Linux."""
    microcode = detect_cpu_microcode()
    kernel = conf.get("boot", {}).get("kernel", {}).get("package", "linux")
    
    return [
      "base",
      "base-devel",
      microcode,
      kernel,
      "linux-firmware",
      "btrfs-progs",
      "dracut",
      # ... more base packages
    ]
  
  def install_packages(self, packages: list[str], mount_point: str) -> None:
    """Use pacstrap to install packages."""
    cmd = f"pacstrap {mount_point} {' '.join(packages)}"
    exec(cmd)
  
  def remove_packages(self, packages: list[str], mount_point: str) -> None:
    """Remove packages using pacman."""
    for pkg in packages:
      exec_chroot(f"pacman -R --noconfirm {pkg}", mount_point=mount_point)
```

**kod/distributions/debian.py** — Debian-specific implementation

```python
class DebianDistribution(Distribution):
  def get_base_packages(self, conf: dict) -> list[str]:
    """Get base packages for Debian."""
    # Similar to Arch, but with Debian packages
    return ["base-files", "base-passwd", "bash", ...]
  
  def install_packages(self, packages: list[str], mount_point: str) -> None:
    """Use debootstrap + apt."""
    # Implementation for Debian
    pass
```

---

## Part 5: Program Registry

### 5.1 Builtin Program Definitions

**kod/registry/programs.py**

```python
PROGRAMS = {
  "git": {
    "description": "Git version control system",
    "packages": ["git"],
    "options": {
      "user_name": {
        "type": "string",
        "default": "",
        "description": "Git user name",
      },
      "user_email": {
        "type": "string",
        "default": "",
        "description": "Git user email",
      },
    },
    "config_generator": generate_gitconfig,
  },
  
  "neovim": {
    "description": "Neovim text editor",
    "packages": ["neovim"],
    "options": {
      "deploy_config": {
        "type": "bool",
        "default": False,
        "description": "Deploy config from dotfiles",
      },
    },
    "config_generator": None,  # Config from dotfiles
  },
  
  "syncthing": {
    "description": "File synchronization service",
    "packages": ["syncthing"],
    "options": {
      "gui_address": {
        "type": "string",
        "default": "127.0.0.1:8384",
        "description": "Web UI address",
      },
      "no_browser": {
        "type": "bool",
        "default": True,
        "description": "Don't open browser on startup",
      },
    },
    "config_generator": generate_syncthing_config,
  },
  
  # ... more programs
}


def generate_gitconfig(user: str, options: dict) -> str:
  """Generate .gitconfig content."""
  return f"""
[user]
  name = {options['user_name']}
  email = {options['user_email']}
[core]
  editor = nvim
"""


def generate_syncthing_config(user: str, options: dict) -> str:
  """Generate syncthing service options."""
  flags = []
  flags.append(f"--gui-address={options['gui_address']}")
  if options['no_browser']:
    flags.append("--no-browser")
  return " ".join(flags)
```

### 5.2 Plugin System

Users can extend program registry by dropping `.py` files in `~/.kod/plugins/programs/`.

**~/.kod/plugins/programs/myapp.py**

```python
# Custom program definition
PROGRAM_DEFINITION = {
  "myapp": {
    "description": "My custom application",
    "packages": ["myapp-bin"],
    "options": {
      "enable_feature_x": {
        "type": "bool",
        "default": False,
        "description": "Enable feature X",
      },
    },
    "config_generator": generate_myapp_config,
  }
}

def generate_myapp_config(user: str, options: dict) -> str:
  if options["enable_feature_x"]:
    return "feature_x=true\n"
  return ""
```

**kod/registry/loader.py**

```python
def load_programs() -> dict:
  """Load builtin and plugin program definitions."""
  programs = PROGRAMS.copy()  # Start with builtins
  
  # Load user plugins
  plugin_dirs = [
    Path.home() / ".kod" / "plugins" / "programs",
    Path("/etc/kod/plugins/programs"),
  ]
  
  for plugin_dir in plugin_dirs:
    if not plugin_dir.exists():
      continue
    
    for plugin_file in plugin_dir.glob("*.py"):
      logger.info(f"Loading plugin: {plugin_file}")
      spec = importlib.util.spec_from_file_location("plugin", plugin_file)
      module = importlib.util.module_from_spec(spec)
      spec.loader.exec_module(module)
      
      if hasattr(module, "PROGRAM_DEFINITION"):
        programs.update(module.PROGRAM_DEFINITION)
  
  return programs
```

---

## Part 6: Error Handling

### 6.1 Structured Exceptions

Replace global `problems` list with proper exception hierarchy.

**kod/common.py**

```python
class KodError(Exception):
  """Base exception for Kodos."""
  pass


class ConfigError(KodError):
  """Configuration error (validation, parsing, schema)."""
  
  def __init__(self, message: str, key: str = None, value: Any = None):
    self.message = message
    self.key = key
    self.value = value
    super().__init__(self._format())
  
  def _format(self) -> str:
    if self.key:
      return f"Config error at '{self.key}': {self.message}"
    return f"Config error: {self.message}"


class CommandError(KodError):
  """System command failed."""
  
  def __init__(self, cmd: str, returncode: int, stderr: str = ""):
    self.cmd = cmd
    self.returncode = returncode
    self.stderr = stderr
    super().__init__(
      f"Command failed with exit code {returncode}:\n  {cmd}\n{stderr}"
    )


class DistributionError(KodError):
  """Distribution-specific operation failed."""
  pass


class ValidationError(ConfigError):
  """Config validation failed."""
  pass
```

### 6.2 Logging Strategy

Replace global problems list with structured logging.

```python
import logging

logger = logging.getLogger("kod")

# In each module:
logger.info(f"Setting up {service}...")
logger.warning(f"Package {pkg} not found in {repo}")
logger.error(f"Failed to create user: {stderr}")

# Errors are raised, not silently logged
if result.returncode != 0:
  raise CommandError(cmd, result.returncode, result.stderr)
```

---

## Part 7: Testing Strategy

### 7.1 Unit Tests

**tests/unit/test_config_loader.py** — Lua parsing

```python
def test_load_simple_config():
  config = config.loader.load("example/testvm")
  assert config["hostname"] == "testvm"

def test_load_with_imports():
  config = config.loader.load("tests/fixtures/with_imports")
  assert "modules/base" in config["_imports"]

def test_parse_error_handling():
  with pytest.raises(ConfigError):
    config.loader.load("tests/fixtures/invalid.lua")
```

**tests/unit/test_config_validator.py** — Schema validation

```python
def test_validate_simple():
  config = {"boot.kernel.package": "linux"}
  result = config.validator.validate(config)
  assert result["boot"]["kernel"]["package"] == "linux"

def test_validate_type_error():
  config = {"boot.kernel.package": 123}  # Should be string
  with pytest.raises(ValidationError) as exc:
    config.validator.validate(config)
  assert "expected string" in str(exc.value)

def test_validate_enum():
  config = {"boot.loader.type": "unknown"}
  with pytest.raises(ValidationError) as exc:
    config.validator.validate(config)
  assert "must be one of" in str(exc.value)
```

**tests/unit/test_config_compiler.py** — Dependency resolution

```python
def test_gnome_auto_enables_gdm():
  config = {"desktop.gnome.enable": True}
  compiled = config.compiler.compile(config)
  assert compiled.get("display_manager") == "gdm"

def test_gnome_adds_fonts():
  config = {"desktop.gnome.enable": True, "packages": ["firefox"]}
  compiled = config.compiler.compile(config)
  assert "ttf-liberation" in compiled["packages"]
  assert "firefox" in compiled["packages"]

def test_conflicting_desktops_detected():
  config = {
    "desktop.gnome.enable": True,
    "desktop.plasma.enable": True,
  }
  with pytest.raises(ValidationError):
    config.compiler.compile(config)
```

**tests/unit/test_packages.py** — Package management

```python
def test_parse_package_name():
  repo, name = system.packages.parse_package("aur:yay")
  assert repo == "aur"
  assert name == "yay"

def test_install_mixed_repos(mocker):
  mock_exec = mocker.patch("kod.common.exec")
  
  packages = ["firefox", "aur:yay", "flatpak:vscode"]
  repos = {
    "arch": MockArchRepo(),
    "aur": MockAurRepo(),
    "flatpak": MockFlatpakRepo(),
  }
  
  system.packages.install(packages, repos, "/")
  
  # Each repo's install should be called
  assert mock_exec.call_count >= 3
```

### 7.2 Integration Tests

**tests/integration/test_install_flow.py** — Full install (mocked)

```python
def test_install_flow(tmp_path, mocker):
  """Test full install flow with mocked execution."""
  
  # Mock exec() and chroot execution
  mocker.patch("kod.common.exec")
  mocker.patch("kod.common.exec_chroot")
  
  # Mock distribution detection
  mocker.patch("kod.distributions.get_distribution", return_value=MockArchDistribution())
  
  # Run install
  core.install.install(
    config_path="tests/fixtures/simple.lua",
    mount_point=str(tmp_path / "mnt")
  )
  
  # Verify key calls were made
  assert exec.called  # Partition setup
  assert exec_chroot.called  # Package install
```

---

## Part 8: Implementation Phases

### Phase 1: Configuration System (Weeks 1-2)

1. **Schema & validator** (`kod/config/schema.py`, `validator.py`)
   - Define core option types
   - Implement type checking, enum validation
   - Add schema lookup CLI: `kod config --schema`

2. **Loader & compiler** (`kod/config/loader.py`, `compiler.py`)
   - Load Lua files, resolve imports
   - Implement dependency resolution (GNOME → gdm)
   - Add compile CLI: `kod config compile -c config.lua`

3. **Tests**
   - Unit tests for schema, validator, loader, compiler
   - Fixtures: sample configs with various features

4. **Backward compatibility**
   - Keep existing Lua interface working
   - Deprecate unused helper functions

**Validation:** `kod config validate -c example/testvm` works and catches errors upfront

### Phase 2: Python Refactoring (Weeks 3-5)

1. **Split core.py** into focused modules:
   - `kod/core/install.py`
   - `kod/core/rebuild.py`
   - `kod/core/user_config.py`
   - `kod/system/packages.py`
   - `kod/system/services.py`
   - `kod/system/users.py`
   - `kod/system/boot.py`

2. **Update distributions** (arch.py, debian.py)
   - Implement Distribution base class interface
   - Move distro-specific logic into implementations

3. **Refactor error handling**
   - Replace global `problems` list
   - Implement structured exceptions

4. **Tests**
   - Unit tests for each module
   - Integration tests for workflows

**Validation:** All existing functionality works; tests pass; code is clearer

### Phase 3: Program Registry (Week 6)

1. **Builtin programs** (`kod/registry/programs.py`)
   - Define git, neovim, syncthing, etc.
   - Implement config generators

2. **Plugin loader** (`kod/registry/loader.py`)
   - Auto-discover plugins from `~/.kod/plugins/`
   - Load and merge program definitions

3. **Tests**
   - Plugin loading, config generation

**Validation:** Users can define custom programs without modifying Kodos source

### Phase 4: Polish & Docs (Week 7)

1. **Documentation**
   - Update README with new config examples
   - Write extending guide (adding programs, modules)
   - Add CLI help for new commands

2. **Cleanup**
   - Remove dead code (unused exceptions, global problems list)
   - Simplify error messages

3. **Full test suite**
   - Integration tests for real workflows
   - Example configs to verify

**Validation:** All tests pass; docs are clear; `kod install` and `kod rebuild` work as before

---

## Part 9: Backward Compatibility

### Migration Path

**Phase 1:** Implement new system alongside old code
- New config loader works in parallel
- Old core.py still handles execution (initially)

**Phase 2:** Gradually migrate execution to new modules
- Replace install workflow incrementally
- Test each step

**Phase 3:** Deprecate old code
- Mark old functions with `@deprecated`
- Guide users to new patterns in error messages

### Lua Config Backward Compatibility

Existing Lua configs (single file, helper functions) will continue to work:
- No module imports required (single-file configs still valid)
- Helper functions (`configs.git()`, etc.) can stay or deprecate gradually
- Config schema validates both old and new formats

**Example: Old config still works**
```lua
-- Old style (still works)
return {
  repos = { ... },
  boot = { ... },
  packages = { ... },
  -- ... all options in one file
}

-- New style (recommended)
return {
  imports = { "modules/base", "modules/desktop" },
  config = { hostname = "myvm" },
}
```

---

## Part 10: Success Criteria

### Before Implementation Starts

- [ ] This spec is approved by maintainer
- [ ] Specification is committed to git
- [ ] Development branch is created

### Phase 1 (Config System)

- [ ] `kod config --schema` shows all available options
- [ ] `kod config validate -c example/testvm` catches typos
- [ ] Module imports work (example/testvm splits into modules/)
- [ ] Compilation resolves dependencies (GNOME → gdm auto-set)
- [ ] Unit tests cover schema, validator, loader, compiler

### Phase 2 (Python Refactoring)

- [ ] core.py is split; each module < 400 lines
- [ ] `kod install` and `kod rebuild` work end-to-end (test on VM)
- [ ] Error handling uses exceptions (no global problems list)
- [ ] Unit tests for each module (packages, services, users, boot, fs)
- [ ] Integration tests for workflows

### Phase 3 (Program Registry)

- [ ] Users can define custom programs in `~/.kod/plugins/programs/`
- [ ] Built-in programs (git, neovim, syncthing, etc.) have schemas
- [ ] Program options validated upfront

### Phase 4 (Polish)

- [ ] All tests pass (unit + integration)
- [ ] README updated with new examples
- [ ] Extending guide written
- [ ] No regressions: old configs still work
- [ ] Performance is unchanged or improved

---

## Part 11: Risk Analysis

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Lua compilation adds overhead | Performance regression | Profile before/after; should be sub-second |
| Breaking existing configs | Users can't upgrade | Maintain backward compatibility; deprecation path |
| Scope creep in refactoring | Project takes too long | Strict phase gates; merge and ship phase 1 before starting 2 |
| Plugin system is unused | Wasted effort | Can be added later if demand emerges; defer if time-constrained |
| Schema validation too strict | Users frustrated | Make it helpful, not pedantic; clear error messages |

---

## Part 12: Future Possibilities

(Out of scope for this redesign, but enabled by new architecture)

- **Config documentation generator:** Auto-generate docs from schema
- **Config GUI:** Web UI to build configuration interactively
- **Incremental builds:** Only rebuild changed packages (big performance win)
- **Remote deployment:** Copy config to remote machines, rebuild there
- **Version control:** Track config changes, branch/merge configs
- **Binary caching:** Cache built generations, share across machines

---

## Appendix: Example New Config Structure

```lua
-- example/testvm/configuration.lua
return {
  imports = {
    "modules/base",
    "modules/hardware/vm",
    "modules/desktop/gnome",
    "modules/users/demo",
  },
  
  config = {
    hostname = "testvm",
    locale = {
      timezone = "America/Edmonton",
      keymap = "us",
    },
  }
}

-- example/testvm/modules/base/default.lua
return {
  config = {
    network = { ipv6 = false },
    boot = {
      kernel.package = "linux-lts",
      loader.type = "systemd-boot",
    },
    packages = {
      "base", "git", "neovim", "htop",
    },
  }
}

-- example/testvm/modules/desktop/gnome.lua
return {
  config = {
    desktop.gnome = {
      enable = true,
      extra_packages = { "gnome-tweaks" },
    },
    -- display_manager auto-set to "gdm"
  }
}

-- example/testvm/modules/users/demo/default.lua
return {
  config = {
    users.demo = {
      name = "Demo User",
      shell = "/bin/bash",
      programs = {
        git = {
          enable = true,
          user_name = "Demo User",
          user_email = "demo@example.com",
        },
      },
    },
  }
}
```

---

## Document Review Checklist

- [x] Purpose and scope are clear
- [x] Architecture diagram is understandable
- [x] All four major components are specified (config, Python, program registry, error handling)
- [x] Testing strategy is realistic
- [x] Implementation phases are concrete and gated
- [x] Backward compatibility path is clear
- [x] Success criteria are measurable
- [x] No contradictions between sections
- [x] Scope is appropriate for ~7 weeks of work

---

**Approved for implementation:** [awaiting maintainer review]
