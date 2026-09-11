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

## Solution: Section Descriptors with Validation & Nested Fields

Add a `SECTION_HELP` dict with:
1. **Top-level descriptions** — What the section does
2. **Validation rules** — Required fields, valid values, constraints
3. **Nested field docs** — Descriptions for each field inside the section

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
        "type": "string",
        "required": True,
        "valid_values": ["arch", "debian"],
        "example": 'base_distribution = "arch"',
        "error_help": "Must be 'arch' or 'debian', e.g.: base_distribution = \"arch\"",
    },
    
    "boot": {
        "description": "Kernel and bootloader configuration.",
        "type": "dict",
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
        "fields": {
            "kernel": {
                "description": "Kernel package and loadable modules.",
                "type": "dict",
                "required": False,
                "fields": {
                    "package": {
                        "description": "Kernel package name (e.g., 'linux', 'linux-lts', 'linux-hardened').",
                        "type": "string",
                        "required": False,
                        "default": "linux",
                    },
                    "modules": {
                        "description": "List of kernel modules to load at boot (for initramfs).",
                        "type": "list",
                        "required": False,
                        "example": '{"xhci_pci", "virtio_blk", "ahci"}',
                    },
                },
            },
            "loader": {
                "description": "Bootloader configuration.",
                "type": "dict",
                "required": False,
                "fields": {
                    "type": {
                        "description": "Bootloader type.",
                        "type": "string",
                        "required": False,
                        "valid_values": ["systemd-boot", "grub"],
                        "default": "systemd-boot",
                    },
                    "timeout": {
                        "description": "Boot menu timeout in seconds.",
                        "type": "number",
                        "required": False,
                        "default": 10,
                    },
                },
            },
        },
    },
    
    "hardware": {
        "description": "Hardware features and configurations.",
        "type": "dict",
        "required": False,
        "example": '''hardware = {
    pipewire = {
        enable = true,
        extra_packages = {"pipewire-alsa", "pipewire-pulse"},
    },
}''',
        "fields": {
            "pipewire": {
                "description": "PipeWire audio system (replaces PulseAudio).",
                "type": "dict",
                "required": False,
                "fields": {
                    "enable": {
                        "description": "Enable PipeWire.",
                        "type": "boolean",
                        "required": False,
                        "default": False,
                    },
                    "extra_packages": {
                        "description": "Additional PipeWire packages (e.g., ALSA/PulseAudio compatibility).",
                        "type": "list",
                        "required": False,
                        "example": '{"pipewire-alsa", "pipewire-pulse"}',
                    },
                },
            },
        },
    },
    
    "locale": {
        "description": "Localization settings (language, timezone, environment variables).",
        "type": "dict",
        "required": False,
        "example": '''locale = {
    locale = {
        default = "en_US.UTF-8 UTF-8",
        extra_generate = {"en_GB.UTF-8 UTF-8"},
    },
    timezone = "America/New_York",
    keymap = "us",
}''',
        "fields": {
            "locale": {
                "description": "Locale settings.",
                "type": "dict",
                "required": False,
                "fields": {
                    "default": {
                        "description": "Default system locale (format: 'en_US.UTF-8 UTF-8').",
                        "type": "string",
                        "required": False,
                        "default": "en_US.UTF-8 UTF-8",
                    },
                    "extra_generate": {
                        "description": "Additional locales to generate.",
                        "type": "list",
                        "required": False,
                    },
                },
            },
            "timezone": {
                "description": "System timezone (IANA format: 'America/New_York', 'Europe/London').",
                "type": "string",
                "required": False,
                "example": '"America/New_York"',
            },
            "keymap": {
                "description": "Console keyboard layout.",
                "type": "string",
                "required": False,
                "default": "us",
            },
        },
    },
    
    "network": {
        "description": "Network configuration (hostname, IPv6).",
        "type": "dict",
        "required": False,
        "example": '''network = {
    hostname = "mycomputer",
    ipv6 = true,
}''',
        "fields": {
            "hostname": {
                "description": "System hostname (computer name on network).",
                "type": "string",
                "required": False,
            },
            "ipv6": {
                "description": "Enable IPv6 support.",
                "type": "boolean",
                "required": False,
                "default": True,
            },
        },
    },
    
    "users": {
        "description": "User accounts (login, shell, groups, home configuration).",
        "type": "dict",
        "required": False,
        "example": '''users = {
    alice = {
        shell = "/bin/bash",
        groups = {"wheel"},
        home_programs = {neovim = true},
    },
}''',
        "fields": {
            "USERNAME": {
                "description": "Username (key in users dict). Fields inside each user:",
                "type": "dict",
                "required": False,
                "fields": {
                    "shell": {
                        "description": "Login shell (e.g., '/bin/bash', '/bin/fish').",
                        "type": "string",
                        "required": False,
                        "default": "/bin/bash",
                    },
                    "groups": {
                        "description": "Groups to add user to (e.g., 'wheel', 'sudo').",
                        "type": "list",
                        "required": False,
                        "example": '{"wheel", "docker"}',
                    },
                    "home_programs": {
                        "description": "User-scoped programs to install (key = program name, value = config).",
                        "type": "dict",
                        "required": False,
                        "example": '{neovim = true, git = true}',
                    },
                },
            },
        },
    },
    
    "packages": {
        "description": "List of system packages to install (package manager names).",
        "type": "list",
        "required": False,
        "example": '''packages = {"vim", "tmux", "git", "htop", "neofetch"}''',
        "error_help": "Must be a list of strings (package names), not a dict.",
    },
    
    "services": {
        "description": "System services to enable/start (e.g., ssh, nginx, docker).",
        "type": "dict",
        "required": False,
        "example": '''services = {
    ssh = { enable = true },
    nginx = { enable = true, start = true },
}''',
        "fields": {
            "SERVICE_NAME": {
                "description": "Service name (key in services dict). Config options:",
                "type": "dict",
                "required": False,
                "fields": {
                    "enable": {
                        "description": "Enable service to start on boot.",
                        "type": "boolean",
                        "required": False,
                    },
                    "start": {
                        "description": "Start service immediately (after install).",
                        "type": "boolean",
                        "required": False,
                    },
                },
            },
        },
    },
    
    "repos": {
        "description": "Repository definitions (package sources).",
        "type": "dict",
        "required": False,
        "example": '''repos = {
    official = repos.arch_repo("https://mirror.example.com/archlinux"),
    aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay.git"),
}''',
        "fields": {
            "REPO_NAME": {
                "description": "Repository identifier (key). Use repo.* functions (arch_repo, aur_repo, flatpak_repo) as values.",
                "type": "dict or string",
                "required": False,
            },
        },
    },
    
    "devices": {
        "description": "Disk and partition definitions for system installation.",
        "type": "dict",
        "required": False,  # Required for install, not for rebuild
        "example": '''devices = {
    disk0 = disk.disk_definition("/dev/sda", "50GB"),
}''',
        "fields": {
            "DISK_NAME": {
                "description": "Disk identifier (key). Use disk.disk_definition() to define.",
                "type": "result of disk.disk_definition()",
                "required": False,
            },
        },
    },
    
    "desktop": {
        "description": "Desktop environment selection (GNOME, KDE Plasma, XFCE, etc.).",
        "type": "dict",
        "required": False,
        "example": '''desktop = {
    environment = "plasma",
    enable = true,
}''',
        "fields": {
            "environment": {
                "description": "Desktop environment (e.g., 'gnome', 'plasma', 'xfce', 'cosmic').",
                "type": "string",
                "required": False,
            },
            "enable": {
                "description": "Enable desktop environment installation.",
                "type": "boolean",
                "required": False,
                "default": True,
            },
        },
    },
    
    "fonts": {
        "description": "Font packages to install (monospace, sans-serif, CJK, emoji).",
        "type": "dict",
        "required": False,
        "example": '''fonts = {
    monospace = {"noto-fonts-cjk"},
    enable = true,
}''',
        "fields": {
            "monospace": {
                "description": "Monospace font packages.",
                "type": "list",
                "required": False,
                "example": '{"noto-fonts-cjk", "liberation-fonts"}',
            },
            "sans_serif": {
                "description": "Sans-serif font packages.",
                "type": "list",
                "required": False,
            },
            "emoji": {
                "description": "Emoji font packages.",
                "type": "list",
                "required": False,
            },
            "enable": {
                "description": "Enable font installation.",
                "type": "boolean",
                "required": False,
                "default": True,
            },
        },
    },
    
    "programs": {
        "description": "Program configurations at system level (custom programs with install logic).",
        "type": "dict",
        "required": False,
        "example": '''programs = {
    neovim = { enable = true },
    git = { enable = true, config = {} },
}''',
        "fields": {
            "PROGRAM_NAME": {
                "description": "Program name (key). Value is program config (passed to program's schema).",
                "type": "dict",
                "required": False,
                "fields": {
                    "enable": {
                        "description": "Enable program installation.",
                        "type": "boolean",
                        "required": False,
                    },
                },
            },
        },
    },
}
```

---

## Implementation

### Task 1: Add SECTION_HELP to schema.py

**File:** `src/kod/config/schema.py`

Add `SECTION_HELP` dict with:
- Top-level descriptions and validation rules
- Nested field documentation (3 levels deep: section → fields → subfields)
- Examples and error_help messages

**Schema structure:**
```python
SECTION_HELP = {
    "section_name": {
        "description": "What this section does.",
        "type": "dict|list|string",
        "required": True/False,
        "valid_values": [...],  # Optional: for string types
        "default": ...,         # Optional: default value
        "example": "...",       # Multi-line example
        "error_help": "...",    # Custom help for common errors
        "fields": {             # Optional: for dict sections
            "field_name": {
                "description": "What this field does.",
                "type": "string|dict|list|boolean|number",
                "required": False,
                "default": ...,
                "fields": {...}  # Optional: nested fields (3 levels max)
            }
        }
    }
}
```

**Testing:**
- Unit test to verify all SCHEMA keys have SECTION_HELP entries
- Unit test that SECTION_HELP structure is valid (required keys, no circular refs)
- Unit test that examples are syntactically valid Lua
- Test nested field lookup (find field docs by path: "boot.kernel.package")

**Commit:** `feat: add section descriptions with nested field docs to config schema`

---

### Task 2: Update Validator to Use Descriptions

**File:** `src/kod/config/validator.py`

Update validation error messages to include descriptions and nested field docs:

```python
def _lookup_field_help(section_key: str, field_path: List[str]) -> Optional[Dict]:
    """Look up help for a nested field path: ["boot", "kernel", "package"]."""
    help_entry = SECTION_HELP.get(section_key)
    if not help_entry:
        return None
    
    current = help_entry
    for field_name in field_path:
        if "fields" not in current:
            return None
        current = current["fields"].get(field_name)
        if not current:
            return None
    
    return current

def validate_config(config: dict) -> List[ValidationError]:
    """Validate config against schema. Include descriptions in errors."""
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
            error_help = help_entry.get("error_help", "")
            
            error_msg = f"Invalid type for '{key}': expected {SCHEMA[key].__name__}, got {type(value).__name__}."
            if error_help:
                error_msg += f"\n  {error_help}"
            elif description:
                error_msg += f"\n  {description}"
            if example:
                error_msg += f"\n  Example:\n    {example}"
            
            errors.append(ValidationError(error_msg, location=key))
    
    # Validate nested fields if present (e.g., boot.kernel.package)
    # This runs after type checking, so we know the structure is correct
    for section_key, section_value in config.items():
        if section_key not in SECTION_HELP:
            continue
        help_entry = SECTION_HELP[section_key]
        if "fields" not in help_entry or not isinstance(section_value, dict):
            continue
        
        # Validate each field in this section
        _validate_nested_fields(section_key, section_value, help_entry["fields"], errors)
    
    # ... rest of validation ...
```

**Testing:**
- Test that error messages include descriptions
- Test nested field validation (boot.kernel type check, etc.)
- Test error_help messages in type errors
- Test example formatting in error output

**Commit:** `feat: validator includes field descriptions and nested validation`

---

### Task 3: Add `kod config schema` Command

**File:** `src/kod/kod.py`

Add CLI command to display schema with descriptions and nested fields:

```python
@cli.command()
@click.option("--section", help="Show only this section")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def config_schema(section, format):
    """Display configuration schema with descriptions and field documentation."""
    from kod.config.schema import SCHEMA, SECTION_HELP
    
    if format == "json":
        import json
        # Return SECTION_HELP as JSON
        data = {k: SECTION_HELP.get(k) for k in SCHEMA.keys()}
        print(json.dumps(data, indent=2))
        return
    
    # Text format with nested field display
    sections_to_show = [section] if section else SCHEMA.keys()
    
    for section_name in sections_to_show:
        if section_name not in SECTION_HELP:
            continue
        
        help_entry = SECTION_HELP[section_name]
        print(f"\n{section_name.upper()}")
        print("=" * 60)
        print(f"Type: {help_entry.get('type', 'unknown')}")
        print(f"Required: {'Yes' if help_entry.get('required') else 'No'}")
        print(f"\n{help_entry.get('description', 'No description')}")
        
        if help_entry.get("example"):
            print(f"\nExample:")
            for line in help_entry["example"].split('\n'):
                print(f"  {line}")
        
        # Show nested fields
        if "fields" in help_entry:
            print(f"\nFields:")
            for field_name, field_info in help_entry["fields"].items():
                print(f"  {field_name}:")
                print(f"    Type: {field_info.get('type', 'unknown')}")
                print(f"    Required: {'Yes' if field_info.get('required') else 'No'}")
                if field_info.get("default"):
                    print(f"    Default: {field_info['default']}")
                print(f"    {field_info.get('description', 'No description')}")
                
                # Show nested subfields
                if "fields" in field_info:
                    print(f"    Subfields:")
                    for subfield_name, subfield_info in field_info["fields"].items():
                        print(f"      {subfield_name}: {subfield_info.get('description', '')}")
```

**Usage:**
```bash
kod config schema                    # Show all sections
kod config schema --section boot     # Show boot section with nested fields
kod config schema --format json      # Machine-readable JSON output
```

**Testing:**
- Test text output is human-readable with proper indentation
- Test JSON output is valid and complete
- Test filtering by section works
- Test nested fields are displayed correctly

**Commit:** `feat: kod config schema command with nested field documentation`

---

### Task 4: Create Config Template Generator

**File:** `src/kod/config/template.py` (new)

Generate a starter config file with sections, descriptions, and examples as comments:

```python
def generate_config_template(distro: str = "arch") -> str:
    """Generate a starter Lua config with comments from SECTION_HELP."""
    from kod.config.schema import SECTION_HELP, SCHEMA
    
    lines = [
        "-- KodOS Configuration Template",
        f"-- Distribution: {distro}",
        "--",
        "-- See 'kod config schema' for full documentation and field descriptions.",
        "-- Each section below has a description; uncomment and customize as needed.",
        "--",
        "",
        "return {",
    ]
    
    for section_name in SCHEMA.keys():
        help_entry = SECTION_HELP.get(section_name, {})
        if not help_entry:
            continue
        
        lines.append("")
        lines.append(f"    -- {section_name.upper()}")
        lines.append(f"    -- {help_entry.get('description', '')}")
        
        if help_entry.get("example"):
            lines.append("    --")
            lines.append("    -- Example:")
            for line in help_entry["example"].split('\n'):
                lines.append(f"    -- {line}")
        
        lines.append(f"    -- {section_name} = ...,")
    
    lines.append("\n}")
    return '\n'.join(lines)
```

**Usage:**
```bash
kod config init --template > ~/.kod/config.lua
kod config init --distro debian --template > config-debian.lua
```

**Integration:**
- Add `kod config init` subcommand
- Option to write to file directly: `kod config init -o config.lua`

**Testing:**
- Test template is valid Lua syntax (can be parsed by lupa)
- Test all SCHEMA sections are included
- Test examples render correctly in comments
- Test distro parameter changes comments appropriately

**Commit:** `feat: config init command generates commented template`

---

### Task 5: Update Docs

**File:** `docs/kod/configuration-schema.md` (NEW)

Create comprehensive reference guide:

**Sections:**
1. **Quick Start** — Minimal example config
2. **Schema Overview** — All 13 top-level sections
3. **Field Reference** — Full documentation for each section + nested fields
4. **Common Errors** — FAQ with solutions
   - "Unknown configuration section" (typo suggestions)
   - Type errors (expected dict, got list)
   - Missing required fields
   - Invalid enum values (e.g., desktop environment)
5. **Examples** — Real-world configs (minimal, desktop, server, etc.)
6. **Validation Rules** — What makes a valid config

**Commit:** `docs: configuration schema reference guide (60-80 lines per section)`

---

### Task 6: Run Tests & Verify

**Testing checklist:**
- [ ] All SCHEMA sections have SECTION_HELP entries
- [ ] SECTION_HELP structure validation passes
- [ ] Examples are syntactically valid Lua
- [ ] Validator tests pass (type checks, nested field docs in errors)
- [ ] `kod config schema` output is readable
- [ ] `kod config init` generates valid template
- [ ] Template can be loaded as Lua without errors
- [ ] Documentation renders correctly

**Commit:** `test: config schema validation and template tests`

---

## Refined Benefits

1. **Structured descriptions** — Not just strings, but schema with types, defaults, examples
2. **Nested field docs** — Know what goes inside boot.kernel, locale.locale, etc.
3. **Validation rules** — Know valid values, constraints, required fields
4. **Self-documenting** — `kod config schema` replaces need for separate docs
5. **Better errors** — Validation errors include relevant field descriptions
6. **Easy onboarding** — `kod config init` generates a commented template
7. **Machine-readable** — JSON export for tools/IDEs

---

## Example: Enhanced Error Messages

### Before
```
❌ Invalid type for 'boot': expected dict, got list
```

### After
```
❌ Invalid type for 'boot': expected dict, got list

  Kernel and bootloader configuration.
  
  Error help: boot should be a dict with optional keys: kernel, loader
  
  Example:
    boot = {
        kernel = {
            package = "linux-lts",
            modules = {"xhci_pci", "virtio_blk"},
        },
        loader = {
            type = "systemd-boot",
            timeout = 10,
        },
    }
  
  For detailed field docs, run: kod config schema --section boot
```

---

## What's Different from Previous Version

| Aspect | Before | After |
|--------|--------|-------|
| Descriptions | Basic text | Text + validation rules |
| Nested fields | No docs | Full 3-level nested docs |
| Validation | Type-only | Type + field-level rules |
| Error help | Generic | Section-specific with examples |
| Schema export | No | JSON export available |
| Template | Manual | Generated with comments |

This is **lazy-effective:** no over-engineering, but adds real value for users.

---

---

## Example: Enhanced Error Messages

### Before
```
❌ Invalid type for 'boot': expected dict, got list
```

### After
```
❌ Invalid type for 'boot': expected dict, got list

  Kernel and bootloader configuration.
  
  Error help: boot should be a dict with optional keys: kernel, loader
  
  Example:
    boot = {
        kernel = {
            package = "linux-lts",
            modules = {"xhci_pci", "virtio_blk"},
        },
        loader = {
            type = "systemd-boot",
            timeout = 10,
        },
    }
  
  For detailed field docs, run: kod config schema --section boot
```

---

## What's Different from Previous Version

| Aspect | Before | After |
|--------|--------|-------|
| Descriptions | Basic text | Text + validation rules |
| Nested fields | No docs | Full 3-level nested docs |
| Validation | Type-only | Type + field-level rules |
| Error help | Generic | Section-specific with examples |
| Schema export | No | JSON export available |
| Template | Manual | Generated with comments |

This is **lazy-effective:** no over-engineering, but adds real value for users.

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

**Phase 5b Tasks (all in scope for this plan):**

- [ ] Task 1: Add SECTION_HELP to schema.py (all 13 sections with validation rules, nested fields)
- [ ] Task 2: Update validator with nested field validation and better error messages
- [ ] Task 3: Create `kod config schema` command (text + JSON output, section filtering)
- [ ] Task 4: Create `kod config init` command (generates commented template)
- [ ] Task 5: Write comprehensive configuration schema reference guide
- [ ] Task 6: Run full test suite (unit tests + validation + template parsing)

**Total effort:** ~6-8 hours implementation + testing

---

## Success Criteria

✅ All SCHEMA sections have SECTION_HELP entries  
✅ Nested field docs (3 levels deep) are complete and accurate  
✅ Validator uses descriptions in type error messages  
✅ `kod config schema` command works (text and JSON output)  
✅ `kod config init` generates valid Lua template  
✅ All tests pass (validation, template parsing, command output)  
✅ Documentation guide is comprehensive (60-80 lines per section)  
✅ Zero breaking changes to existing configs or validation logic  

---

## Open Questions

1. **Validation strictness:** Should we validate nested field types (e.g., ensure boot.kernel.modules is a list), or just top-level?
   - **Answer:** Yes, validate nested fields (helps users catch typos early)

2. **Required fields:** Should we track which nested fields are required vs optional?
   - **Answer:** Yes, include in schema (helps with template generation)

3. **Version tracking:** Should we mark which fields are new in which version?
   - **Answer:** Not in Phase 5b (can add in later phase if needed)

---

## Decision: Implement This Plan?

**Recommendation:** Yes, this is **Phase 5b** (optional enhancement, but valuable for users).

- Improves config authoring experience significantly
- Minimal code complexity (structured data + validation logic)
- No breaking changes
- Builds on existing validation infrastructure
- Ready to implement after Phase 5a (custom packages) or in parallel

**When:** After Phase 5a, or next iteration.
