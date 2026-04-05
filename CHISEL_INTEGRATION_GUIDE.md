# Chisel Module Integration Guide

## Overview

The new `chisel.py` module provides a drop-in replacement for `arch.py` that uses Chisel as the package manager instead of Pacman. Chisel brings Arch Linux packages to any Linux distribution with complete dependency isolation, making Kodos truly cross-distribution.

## File Location

```
src/kod/chisel.py
```

## Module Structure

The chisel.py module provides 10 main functions that mirror the functionality of arch.py:

### Core Functions

1. **prepare_for_installation()** - Verify Chisel is installed
2. **get_base_packages(conf)** - Get base packages for installation
3. **install_essentials_pkgs(base_pkgs, mount_point)** - Install essential packages
4. **refresh_package_db(mount_point, new_generation)** - Refresh package database

### Kernel Management

5. **get_kernel_file(mount_point, package)** - Get kernel file path and version
6. **setup_linux(kernel_package)** - Set up kernel for boot
7. **kernel_update_required(...)** - Check if kernel update needed

### Repository & Package Management

8. **proc_repos(conf, ...)** - Process repository configuration
9. **get_list_of_dependencies(pkg)** - Get package dependencies
10. **generale_package_lock(mount_point, state_path)** - Generate package lock file

## Integration with Kodos

### Using Chisel Instead of Arch

To use the chisel module in Kodos, you need to:

1. **In kod.py**, modify the distribution setup:

```python
# Current code in kod.py (around line 61):
from kod.arch import (
    get_base_packages,
    install_essentials_pkgs,
    # ... other functions
)

# Change to:
from kod.chisel import (
    get_base_packages,
    install_essentials_pkgs,
    # ... other functions
)
```

2. **Or use dynamic import**:

```python
if base_distribution == "arch":
    from kod import arch as dist_module
elif base_distribution == "chisel":
    from kod import chisel as dist_module

dist = dist_module
```

### Configuration

The chisel module uses the same configuration format as arch.py. Your Lua configuration file remains unchanged:

```lua
return {
    repos = { ... },
    devices = { ... },
    boot = { ... },
    -- ... rest of configuration
}
```

## How Chisel Package Management Works

### Installation Flow

1. **Prepare**: `prepare_for_installation()` verifies chisel is available
2. **Sync**: `refresh_package_db()` syncs Arch databases via `chisel sync`
3. **Install**: `install_essentials_pkgs()` uses `chisel install` command
4. **Store**: Packages are extracted to `/kod/store/<package>/<version>/`
5. **Wrappers**: Chisel automatically creates wrapper scripts
6. **Lock**: `generale_package_lock()` records installed packages

### Package Store Structure

Chisel stores all packages in `/kod/store/`:

```
/kod/
├── store/
│   ├── linux/
│   │   └── 6.1.45-1/
│   │       ├── boot/
│   │       ├── lib/
│   │       ├── usr/
│   │       └── ...
│   ├── bash/
│   │   └── 5.2.21-1/
│   │       └── ...
│   └── ...
├── wrappers/
│   ├── linux
│   ├── bash
│   └── ...
├── db/
│   ├── core.db
│   ├── extra.db
│   └── community.db
└── registry.json
```

### Wrapper Scripts

Chisel automatically creates wrapper scripts that set `LD_LIBRARY_PATH` to ensure packages use their own dependencies:

```bash
#!/bin/bash
export LD_LIBRARY_PATH=/kod/store/glibc/2.37-1/lib:$LD_LIBRARY_PATH
exec /kod/store/bash/5.2.21-1/usr/bin/bash "$@"
```

## Key Differences from arch.py

### Command Replacements

| Operation | arch.py | chisel.py |
|-----------|---------|-----------|
| Install packages | pacstrap | chisel install |
| Sync databases | pacman -Syy | chisel sync |
| List packages | pacman -Q | chisel list |
| Query package | pacman -Ql | chisel list / /kod/store/ |
| Get dependencies | pacman -Si | chisel search / registry |

### Advantages of Chisel

1. **Cross-Distribution**: Works on any Linux distro (Ubuntu, Fedora, Debian, etc.)
2. **Dependency Isolation**: Complete isolation prevents conflicts
3. **No Host Contamination**: System packages remain untouched
4. **Universal Packages**: Use Arch packages everywhere
5. **Easy Rollback**: Since packages are isolated, rollback is simpler

### Important Notes

1. **Chisel Must Be Pre-installed**: Kodos assumes chisel is already installed
2. **Sudo May Be Required**: Some chisel operations require root access
3. **Mount Point Handling**: Packages install to `/kod/`, then can be copied elsewhere
4. **Database Files**: Located in `/kod/db/` instead of `/var/lib/pacman/`
5. **Package Registry**: Stored in JSON format at `/kod/registry.json`

## Function Details

### prepare_for_installation()

Verifies that Chisel is installed and available:

```python
from kod.chisel import prepare_for_installation

try:
    prepare_for_installation()
    print("Chisel is ready")
except RuntimeError as e:
    print(f"Error: {e}")
```

### get_base_packages(conf)

Returns the base packages needed for a minimal Kodos installation:

```python
from kod.chisel import get_base_packages

packages = get_base_packages(conf)
# Returns:
# {
#     "kernel": "linux",
#     "base": ["base", "base-devel", "intel-ucode", "btrfs-progs", ...]
# }
```

### install_essentials_pkgs(base_pkgs, mount_point)

Installs essential packages:

```python
from kod.chisel import get_base_packages, install_essentials_pkgs

base_pkgs = get_base_packages(conf)
install_essentials_pkgs(base_pkgs, "/mnt")
```

### get_kernel_file(mount_point, package)

Retrieves kernel file path and version:

```python
from kod.chisel import get_kernel_file

kernel_file, version = get_kernel_file("/mnt", "linux")
# Returns: ("/kod/store/linux/6.1.45-1/boot/vmlinuz-6.1.45-1", "6.1.45-1")
```

### refresh_package_db(mount_point, new_generation)

Syncs Arch package databases:

```python
from kod.chisel import refresh_package_db

# For new generation (inside chroot):
refresh_package_db("/mnt", new_generation=True)

# For current system:
refresh_package_db("/", new_generation=False)
```

### generale_package_lock(mount_point, state_path)

Generates a lock file with installed packages:

```python
from kod.chisel import generale_package_lock

generale_package_lock("/mnt", "/kod/generations/0")
# Creates /kod/generations/0/packages.lock with installed packages
```

## Troubleshooting

### Chisel Not Found

**Error**: `RuntimeError: Chisel is not installed or not in PATH`

**Solution**: Install chisel first:
```bash
go build -o chisel ./cmd/chisel
sudo mv chisel /usr/local/bin/
```

### Permission Denied

**Error**: When running chisel install

**Solution**: Run with sudo or configure sudoers:
```bash
sudo chisel install package_name
```

### Package Not Found

**Error**: When trying to install a package

**Solution**: 
1. Ensure databases are synced: `chisel sync`
2. Check package name matches Arch repositories
3. Verify internet connection

### Mount Point Issues

**Error**: Packages installing to wrong location

**Solution**: Chisel installs to `/kod/` by default. Copy packages to mount point after installation if needed.

## Migration from arch.py to chisel.py

### Step 1: Update Imports

In `kod.py`, change:
```python
from kod.arch import (
    prepare_for_installation,
    get_base_packages,
    # ... other functions
)
```

To:
```python
from kod.chisel import (
    prepare_for_installation,
    get_base_packages,
    # ... other functions
)
```

### Step 2: Update Distribution Detection

Change the distribution detection logic to support both:
```python
if base_distribution == "arch":
    from kod import arch as dist
elif base_distribution == "chisel" or base_distribution != "arch":
    from kod import chisel as dist
```

### Step 3: Test

Test the new module with:
```bash
python3 -m pytest tests/ -v
```

## Performance Considerations

- **Initial Setup**: Chisel may take longer on first install (downloading Arch databases)
- **Package Installation**: Comparable to Arch, possibly faster due to parallel extraction
- **Disk Space**: Packages stored in `/kod/` (typically 2-3x uncompressed vs pacman)
- **Memory**: Similar memory footprint to pacman

## Security Considerations

- **Isolation**: Complete dependency isolation prevents library conflicts
- **No System Modification**: Host system packages remain untouched
- **Wrapper Scripts**: Set explicit LD_LIBRARY_PATH, preventing library hijacking
- **Verification**: All packages from trusted Arch mirrors

## Future Enhancements

Potential improvements for future versions:

1. **Custom Mirrors**: Support for custom Arch mirror configuration
2. **Dependency Resolution**: More sophisticated dependency management
3. **Package Compression**: Better compression for reduced disk usage
4. **Partial Installation**: Install only specific package components
5. **Multi-Version Support**: Run multiple versions of same package

## References

- Chisel Repository: https://github.com/kodos-prj/chisel
- Chisel Documentation: See README.md in chisel repo
- Kodos Repository: https://github.com/kodos-prj/kodos
- Arch Linux Packages: https://archlinux.org/packages/

