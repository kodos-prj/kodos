# Config Sections Schema Descriptors (Phase 5b Enhancement)

**Goal:** Add simple text descriptions to each top-level config section to help users validate their configuration and understand what each section does.

**User Choice:** Basic descriptions only (not full structured schemas like program modules)

---

## Current State

**schema.py:**
```python
SCHEMA = {
    "base_distribution": str,
    "repos": dict,
    "devices": dict,
    "boot": dict,
    "hardware": dict,
    "locale": dict,
    "network": dict,
    "users": dict,
    "desktop": dict,
    "fonts": dict,
    "packages": list,
    "services": dict,
    "programs": dict,
}
```

**Problem:** No descriptions. Users don't know:
- What each section does
- What fields are required/optional
- What values are valid
- Examples of valid configurations

---

## Solution: Section Descriptors

Add a `SECTION_HELP` dict with descriptions for each section:

```python
# src/kod/config/schema.py

SCHEMA = {
    "base_distribution": str,
    "repos": dict,
    "devices": dict,
    # ... etc
}

SECTION_HELP = {
    "base_distribution": {
        "description": "Base Linux distribution to install.",
        "valid_values": ["arch", "debian"],
        "required": True,
        "example": 'base_distribution = "arch"',
    },
    "repos": {
        "description": "Repository definitions (Arch: official/AUR, Debian: apt sources).",
        "required": False,
        "example": '''repos = {
    official = repos.arch_repo("https://mirror.example.com/archlinux"),
    aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay.git"),
}''',
    },
    "devices": {
        "description": "Disk and partition definitions for system installation.",
        "required": True,  # if doing install (not rebuild)
        "example": '''devices = {
    disk0 = disk.disk_definition("/dev/sda", "50GB"),
}''',
    },
    "boot": {
        "description": "Kernel and bootloader configuration (kernel version, modules, boot timeout).",
        "required": False,
        "example": '''boot = {
    kernel = {
        package = "linux-lts",
        modules = {"xhci_pci", "virtio_blk"},
    },
    loader = {
        type = "systemd-boot",
        timeout = 10,
    },
}''',
    },
    "hardware": {
        "description": "Hardware features (audio via pipewire, etc.).",
        "required": False,
        "example": '''hardware = {
    pipewire = {
        enable = true,
        extra_packages = {"pipewire-alsa", "pipewire-pulse"},
    },
}''',
    },
    "locale": {
        "description": "Localization settings (language, timezone, locale environment variables).",
        "required": False,
        "example": '''locale = {
    locale = {
        default = "en_US.UTF-8 UTF-8",
    },
    timezone = "America/New_York",
    keymap = "us",
}''',
    },
    "network": {
        "description": "Network configuration (hostname, IPv6 support).",
        "required": False,
        "example": '''network = {
    hostname = "mycomputer",
    ipv6 = true,
}''',
    },
    "users": {
        "description": "User accounts (username, shell, groups, home directory configuration).",
        "required": False,
        "example": '''users = {
    alice = {
        shell = "/bin/bash",
        groups = {"wheel"},
    },
}''',
    },
    "desktop": {
        "description": "Desktop environment selection (GNOME, KDE Plasma, XFCE, etc.).",
        "required": False,
        "example": '''desktop = {
    environment = "plasma",
    enable = true,
}''',
    },
    "fonts": {
        "description": "Font packages to install (monospace fonts, noto fonts, etc.).",
        "required": False,
        "example": '''fonts = {
    monospace = {"noto-fonts-cjk"},
    enable = true,
}''',
    },
    "packages": {
        "description": "List of system packages to install (strings: pacman/apt package names).",
        "required": False,
        "example": '''packages = {"vim", "tmux", "git", "htop"}''',
    },
    "services": {
        "description": "System services to enable/start (string keys: service names).",
        "required": False,
        "example": '''services = {
    ssh = { enable = true },
    nginx = { enable = true },
}''',
    },
    "programs": {
        "description": "User program definitions and options (custom programs with install logic).",
        "required": False,
        "example": '''programs = {
    neovim = { enable = true },
    git = { enable = true },
}''',
    },
}
```

---

## Implementation

### Task 1: Add SECTION_HELP to schema.py

**File:** `src/kod/config/schema.py`

Add `SECTION_HELP` dict with descriptions for all 13 sections (see above).

**Testing:**
- Unit test to verify all SCHEMA keys have SECTION_HELP entries
- Unit test that SECTION_HELP structure is valid (has "description" key, etc.)

**Commit:** `feat: add section descriptions to config schema`

---

### Task 2: Update Validator to Use Descriptions

**File:** `src/kod/config/validator.py`

Update validation error messages to include descriptions:

```python
def validate_config(config: dict) -> List[ValidationError]:
    """Validate config against schema. Include helpful descriptions in errors."""
    errors = []
    
    for key, value in config.items():
        if key not in SCHEMA:
            errors.append(ValidationError(
                f"Unknown configuration section '{key}'.",
                suggestion=_suggest(key),
                location=key,
            ))
            continue
        
        if not _type_ok(value, SCHEMA[key]):
            help_entry = SECTION_HELP.get(key, {})
            description = help_entry.get("description", "")
            example = help_entry.get("example", "")
            
            error_msg = f"Invalid type for '{key}': expected {SCHEMA[key].__name__}, got {type(value).__name__}."
            if description:
                error_msg += f"\n  {description}"
            if example:
                error_msg += f"\n  Example:\n    {example}"
            
            errors.append(ValidationError(error_msg, location=key))
    
    # ... rest of validation ...
```

**Testing:**
- Test that error messages include descriptions
- Test example formatting in error output

**Commit:** `feat: validator includes section descriptions in error messages`

---

### Task 3: Add `kod config schema` Command

**File:** `src/kod/kod.py`

Add CLI command to display schema with descriptions:

```python
@cli.command()
def config_schema():
    """Display configuration schema with descriptions and examples."""
    from kod.config.schema import SCHEMA, SECTION_HELP
    
    print("KodOS Configuration Schema\n")
    print("=" * 60)
    
    for section in SCHEMA.keys():
        help_entry = SECTION_HELP.get(section, {})
        description = help_entry.get("description", "No description available.")
        required = help_entry.get("required", False)
        example = help_entry.get("example", "")
        
        print(f"\n{section}")
        print("-" * 40)
        print(f"Type: {SCHEMA[section].__name__}")
        print(f"Required: {'Yes' if required else 'No'}")
        print(f"\n{description}")
        
        if example:
            print(f"\nExample:")
            for line in example.split('\n'):
                print(f"  {line}")
        
        print()
```

**Usage:**
```bash
kod config schema                          # Show all sections
kod config schema --format json            # Machine-readable
kod config schema --section boot           # Show one section
```

**Testing:**
- Test output is human-readable
- Test JSON output is valid
- Test filtering by section

**Commit:** `feat: kod config schema command displays full schema with examples`

---

### Task 4: Create Config Template Generator

**File:** `src/kod/config/template.py` (new)

Generate a starter config file with all sections and descriptions as comments:

```python
def generate_config_template(distro: str = "arch") -> str:
    """Generate a starter configuration file with descriptions and examples."""
    from kod.config.schema import SECTION_HELP
    
    template = f'''-- KodOS Configuration
-- Generated template for {distro}
-- See 'kod config schema' for detailed documentation
-- 
-- Each section has a description and example usage below

return {{
'''
    
    for section in ["base_distribution", "repos", "devices", "boot", ...]:
        help_entry = SECTION_HELP.get(section, {})
        description = help_entry.get("description", "")
        example = help_entry.get("example", "")
        
        template += f"\n    -- {section.upper()}\n"
        template += f"    -- {description}\n"
        if example:
            template += f"    -- Example:\n"
            for line in example.split('\n'):
                template += f"    -- {line}\n"
        template += f"    -- {section} = ...,\n"
    
    template += "\n}}"
    return template
```

**Usage:**
```bash
kod config new --template > ~/.kod/config.lua
kod config new --distro debian --template > config-debian.lua
```

**Testing:**
- Test template is valid Lua syntax (can be parsed)
- Test all sections are included
- Test examples are syntactically valid

**Commit:** `feat: config template generator with comments and examples`

---

### Task 5: Update Docs

**File:** `docs/cod/configuration-schema.md` (new)

Create a reference guide showing:
- All sections, their descriptions, examples
- Required vs optional
- Valid values for each field
- Common errors and how to fix them

**Commit:** `docs: configuration schema reference guide`

---

## Benefits

1. **Self-documenting** — `kod config schema` shows what each section does
2. **Better errors** — Validation errors include descriptions and examples
3. **Easier onboarding** — Users can generate a template with comments
4. **Single source of truth** — Descriptions live in code, easy to keep in sync
5. **No breaking changes** — Just adds descriptions, doesn't change validation logic

---

## Example: Before vs After

### Before (no help)
```
$ kod install -c bad-config.lua
❌ Error: Unknown configuration section 'locales'
Did you mean 'locale'?
```

### After (with help)
```
$ kod install -c bad-config.lua
❌ Error: Unknown configuration section 'locales'
Did you mean 'locale'?
  
  locale: Localization settings (language, timezone, locale environment variables).
  Example:
    locale = {
        locale = {
            default = "en_US.UTF-8 UTF-8",
        },
        timezone = "America/New_York",
        keymap = "us",
    }
```

### Before (type error)
```
$ kod install -c config.lua
❌ Error: Invalid type for 'users': expected dict, got list
```

### After (with help)
```
$ kod install -c config.lua
❌ Error: Invalid type for 'users': expected dict, got list

  users: User accounts (username, shell, groups, home directory configuration).
  Example:
    users = {
        alice = {
            shell = "/bin/bash",
            groups = {"wheel"},
        },
    }
```

---

## Tasks Summary

- [ ] Task 1: Add SECTION_HELP to schema.py
- [ ] Task 2: Update validator to use descriptions
- [ ] Task 3: Create `kod config schema` command
- [ ] Task 4: Config template generator
- [ ] Task 5: Update docs
- [ ] Task 6: Full regression & test

---

## Is This the Right Approach?

**Pros:**
- Minimal, focused improvement (just descriptions)
- No changes to existing validation logic
- Easy to maintain (all in one dict)
- Helps users understand config structure
- No new dependencies

**Cons:**
- Not as rich as full structured schemas (like program modules)
- Descriptions are static strings (no validation rules)
- Examples can get out of sync with actual valid configs

**Decision:** This hits the user's request for "basic descriptions" without over-engineering. If we need more later (validation rules, type hints, etc.), we can extend SECTION_HELP to a full schema at that point.
