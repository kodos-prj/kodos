# Task 5: Write Configuration Schema Reference Guide

## Requirement

Create comprehensive documentation file `docs/kod/configuration-schema.md` that explains the KodOS configuration system, including all sections, nested fields, examples, and common errors.

## File to Create

**`docs/kod/configuration-schema.md`** (NEW, estimated 1500-2000 lines)

## Documentation Structure

### Section 1: Introduction (100-150 lines)

- What is KodOS configuration?
- Configuration file location and format (Lua)
- Quick start: how to create your first config
- How to get help: `kod config schema`, `kod config init`, etc.

**Example intro:**
```markdown
# KodOS Configuration Schema

KodOS uses Lua configuration files to describe system setup, including:
- Base distribution and repositories
- Hardware configuration and boot settings
- User accounts and system services
- Installed packages and programs
- Desktop environment and localization

Configuration files are pure Lua, executed in a sandboxed environment.
```

### Section 2: Getting Started (150-200 lines)

**Subsections:**
- Generating a starter template: `kod config init`
- Understanding the template structure
- Running a plan: `kod install -c config.lua`
- Testing without installing: `kod plan -c config.lua`

### Section 3: Configuration Sections Reference (60-80 lines per section × 13 = 780-1040 lines)

For each section, provide:

**1. base_distribution**
- Description
- Required: Yes
- Valid values: arch, debian
- Example
- Notes

**2. repos**
- Description
- Functions available (arch_repo, aur_repo, flatpak_repo, apt_repo, etc.)
- Examples for each distro
- Common mistakes

**3. devices**
- Description
- Functions (disk.disk_definition, disk.partition, etc.)
- Partition scheme examples
- LVM/RAID examples (if supported)

**4. boot**
- Description
- Nested fields: kernel, loader
- Kernel packages and modules
- Bootloader types (systemd-boot, grub)
- Examples

**5. hardware**
- Description
- Pipewire audio configuration
- Other hardware options
- Examples

**6. locale**
- Description
- Locale formatting (POSIX)
- Timezone database
- Keymap options
- Locale environment variables
- Examples

**7. network**
- Description
- Hostname configuration
- IPv6 support
- Examples

**8. users**
- Description
- User fields: shell, groups, home_programs
- Group membership
- Home program installation
- Shell options
- Examples

**9. desktop**
- Description
- Available environments (GNOME, Plasma, XFCE, Cosmic, etc.)
- Environment-specific options
- Examples

**10. fonts**
- Description
- Font categories (monospace, sans-serif, emoji)
- Available font packages
- Examples

**11. packages**
- Description
- Package lists (how to find packages)
- Package managers (pacman for Arch, apt for Debian)
- Common packages
- Examples

**12. services**
- Description
- Service fields: enable, start
- Common services (ssh, nginx, docker, etc.)
- Service management
- Examples

**13. programs**
- Description
- Program definitions (from registry)
- Program-specific configuration
- Scoping (system vs user)
- Examples

### Section 4: Common Errors & Solutions (200-300 lines)

**Subsections (each with problem, cause, solution, example):**
- "Unknown configuration section" (typos)
- Type errors (expected dict, got list)
- Invalid enumeration values (boot.loader.type)
- Missing required fields
- Invalid repository URLs
- Partition scheme errors
- Timezone not found
- Invalid shell path
- Desktop environment not available
- Locale not available

### Section 5: Advanced Topics (200-300 lines)

**Subsections:**
- Custom programs and modules
- Lua functions and macros (disk.*, repos.*, etc.)
- Conditional configuration (if/else in Lua)
- Reusing configuration across machines
- Managing multiple system configs
- Configuration validation and testing

### Section 6: Examples (300-400 lines)

Complete, real-world example configurations:

**Example 1: Minimal Arch Install**
- base_distribution only
- Minimal packages

**Example 2: Desktop GNOME (Arch)**
- Full desktop setup
- Keyboard/locale
- Development tools

**Example 3: Server (Debian)**
- ssh, nginx, docker services
- Headless (no desktop)
- Network configuration

**Example 4: Development Workstation (Arch)**
- Multiple users
- Development tools (git, neovim, etc.)
- Custom programs
- Full feature set

### Section 7: Command Reference (50-100 lines)

- `kod config init [--distro {arch,debian}] [--output FILE]`
- `kod config schema [--section SECTION] [--format {text,json}]`
- `kod config validate --config FILE`
- `kod install --config FILE`
- `kod plan --config FILE`

## Style Guidelines

- Use GitHub-flavored Markdown
- Include code blocks with language hints (```lua, ```bash)
- Use admonitions for tips/warnings (blockquotes with **Note:**,  **Warning:**)
- Cross-reference sections with `[Section name](#section-name)` links
- Keep line length under 80 characters where possible
- Use consistent formatting for field descriptions

## Example Structure

```markdown
## users

User accounts and login configuration.

**Type:** dict  
**Required:** No  
**Example:**

\`\`\`lua
users = {
    alice = {
        shell = "/bin/bash",
        groups = {"wheel", "docker"},
    },
}
\`\`\`

### Fields

#### shell
Default login shell for the user. Common options:
- `/bin/bash` — Bash (default)
- `/bin/zsh` — Zsh
- `/bin/fish` — Fish shell

#### groups
List of Unix groups to add the user to. Common groups:
- `wheel` — Administrative access (sudo)
- `docker` — Docker container access
- `video` — Video/graphics access

### Common Mistakes

**Problem:** User can't run sudo
```lua
users = {
    alice = {
        groups = {"sudoers"}  -- Wrong!
    }
}
```

**Solution:** Use `wheel` group on Arch, `sudo` group on Debian
```lua
users = {
    alice = {
        groups = {"wheel"}    -- Arch
    }
}
```

### See Also
- [locale](#locale) — User's locale settings
- [desktop](#desktop) — Desktop environment
```

## Success Criteria

✅ File created at `docs/kod/configuration-schema.md`  
✅ All 13 sections documented with examples  
✅ Common errors section addresses real user mistakes  
✅ Examples are complete and copy-paste-able  
✅ Cross-references work (links within document)  
✅ Markdown is valid (renders properly)  
✅ Line lengths reasonable for readability  
✅ Consistent formatting and style throughout  

## Estimated Size

- Introduction: ~150 lines
- Getting Started: ~200 lines
- 13 Sections × 70 lines avg: ~910 lines
- Common Errors: ~250 lines
- Advanced Topics: ~250 lines
- Examples: ~400 lines
- Command Reference: ~80 lines

**Total: ~2,240 lines (~8-10 KB)**

## Notes

- This is documentation, not code—no tests needed
- Can reference Task 3 output (`kod config schema`) in examples
- Link to existing docs (ARCHITECTURE.md, plan files) where relevant
- Distro-specific variations should be clearly marked (Arch vs Debian)
