# CLI Architecture Design

**Document:** Architecture redesign support
**Phase:** 1-5 (spans all phases)
**Status:** Design - Review Required
**Last Updated:** 2026-09-09

---

## Overview

The Kodos CLI needs to support a growing set of commands across all 5 phases:

**Phase 1:** Config system commands
- `kod config --schema` — Show available config options
- `kod config validate -c FILE` — Validate a config file
- `kod config compile -c FILE` — Compile config to plan

**Phase 2:** Installation commands (existing)
- `kod install -c FILE` — Install system
- `kod rebuild` — Rebuild existing system

**Phase 3:** Registry commands
- `kod registry list` — List programs
- `kod registry info <name>` — Show program info

**Phase 5:** Package commands
- `kod package build -n <name>` — Build custom package
- `kod package list` — List available packages
- `kod package info <name>` — Show package info
- `kod package cache --clean` — Clear cache

---

## Design Decision: Subcommand Structure

### Option A: Flat Commands (Current)
```
kod install
kod rebuild
kod config ...
kod registry ...
kod package ...
```

**Pros:**
- Simple CLI
- Easy to type
- Works well with short command names

**Cons:**
- Command namespace pollution
- Hard to organize help

**Verdict:** ❌ Not recommended for 20+ commands

### Option B: Subcommand Groups (Recommended)
```
kod config [--schema|validate|compile]
kod install [--help]
kod registry [list|info]
kod package [build|list|info|cache]
```

**Pros:**
- Organized by domain
- Extensible (can add to each group)
- Good help structure (`kod config --help`)
- Matches distro tools (pacman, apt)

**Cons:**
- Slightly more typing

**Verdict:** ✅ Recommended

### Option C: Nested Subcommands
```
kod config schema
kod config validate
kod install system
kod package build custom hello
```

**Pros:**
- Very organized
- Scales to many commands

**Cons:**
- Too verbose
- Overhead for simple operations

**Verdict:** ❌ Over-engineered

---

## Recommended Structure

### Command Groups

```
kod config [SUBCOMMAND]
  schema         Show available config options
  validate       Validate a config file
  compile        Compile config to installation plan

kod install [OPTIONS]
  -c FILE        Config file (default: /etc/kodos/configuration.lua)
  -i             Ignore validation errors (not recommended)

kod rebuild [OPTIONS]
  -r ROOT        Root path (default: current system)

kod registry [SUBCOMMAND]
  list           List available programs
  info NAME      Show program schema

kod package [SUBCOMMAND]
  build          Build a custom package
  list           List all available packages
  info NAME      Show package info
  cache          Manage package cache
    --clean      Remove unused cached packages
```

### Implementation Approach

**Option 1: Click Framework (Recommended)**
```python
import click

@click.group()
def cli():
    """Kodos - Reproducible Linux system configuration."""
    pass

@cli.group()
def config():
    """Configuration management."""
    pass

@config.command()
def schema():
    """Show available configuration options."""
    pass

@config.command()
@click.argument("config_file")
def validate(config_file):
    """Validate a configuration file."""
    pass

@cli.command()
@click.option("-c", "--config", default="/etc/kodos/configuration.lua")
def install(config):
    """Install Kodos system."""
    pass
```

**Pros:**
- Clean, readable code
- Auto-generates help
- Handles argument parsing
- Type validation built-in

**Cons:**
- New dependency

**Verdict:** ✅ Recommended if adding Click; otherwise use argparse

**Option 2: Argparse (No New Dependencies)**
```python
import argparse

parser = argparse.ArgumentParser(prog="kod")
subparsers = parser.add_subparsers(dest="command")

# config subcommand
config_parser = subparsers.add_parser("config")
config_subs = config_parser.add_subparsers(dest="subcommand")
config_subs.add_parser("schema")
config_subs.add_parser("validate").add_argument("file")

# install command
install_parser = subparsers.add_parser("install")
install_parser.add_argument("-c", "--config", default="/etc/kodos/configuration.lua")
```

**Pros:**
- No new dependencies
- Works well for CLI

**Cons:**
- More boilerplate

**Verdict:** ✅ Alternative if avoiding Click

---

## File Structure

```
src/kod/cli/
├── __init__.py          Main CLI entry point
├── commands/
│   ├── config.py        Config commands
│   ├── install.py       Install command
│   ├── rebuild.py       Rebuild command
│   ├── registry.py      Registry commands
│   └── package.py       Package commands (Phase 5)
└── utils.py             CLI utilities (formatting, etc.)
```

---

## Error Handling

CLI should:
1. Catch exceptions from modules
2. Format errors for human readability
3. Suggest fixes when possible
4. Exit with appropriate status codes

```python
# Example
try:
    config = loader.load(config_file)
except ValidationError as e:
    print(f"Configuration error at {e.location}:")
    print(f"  {e.message}")
    if e.suggestion:
        print(f"  Suggestion: {e.suggestion}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(2)
```

---

## Exit Codes

- 0: Success
- 1: Configuration error (user's fault)
- 2: System error (not user's fault)
- 3: Permission denied

---

## Implementation Timeline

- **Phase 1:** Implement `kod config` commands
- **Phase 2:** Update `kod install` and `kod rebuild` (if needed)
- **Phase 3:** Add `kod registry` commands
- **Phase 4:** Polish all CLI help and error messages
- **Phase 5:** Add `kod package` commands

---

## Decision

**Recommended:**
- Structure: Subcommand groups (Option B)
- Framework: Click or Argparse (your preference)
- File structure: Separate module per command group
- Phase 1 deliverable: Implement `kod config` commands using chosen framework

**To proceed:**
1. Choose framework (Click or Argparse)
2. Create `src/kod/cli/` directory structure
3. Implement during Phase 1 as new CLI is tested

