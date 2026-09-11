# Task 4: Create 'kod config init' Command (Template Generator)

## Requirement

Add a new CLI command `kod config init` to generate a starter configuration file with all sections documented as comments, using descriptions and examples from SECTION_HELP.

## Files to Create/Modify

- **`src/kod/config/template.py`** (NEW) — Template generation logic
  - `generate_config_template(distro: str = "arch") -> str` function
  - Returns complete Lua config with comments

- **`src/kod/kod.py`** (MODIFY) — Add CLI command
  - Add `@cli.command()` decorated function `config_init()`
  - Support `--distro` option (arch or debian, default: arch)
  - Support `--output` option (file path to write template, default: stdout)

## Implementation Details

### Template Generation Logic (`src/kod/config/template.py`)

```python
def generate_config_template(distro: str = "arch") -> str:
    """Generate a starter Lua config file with commented sections.
    
    Args:
        distro: Target distribution ("arch" or "debian")
    
    Returns:
        Lua config as string with all sections commented and explained
    """
    from kod.config.schema import SCHEMA, SECTION_HELP
    
    lines = [
        "-- KodOS Configuration Template",
        f"-- Distribution: {distro}",
        "--",
        "-- See 'kod config schema' for full documentation.",
        "-- Uncomment sections below and customize as needed.",
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
        
        if help_entry.get("required"):
            lines.append("    -- Required: Yes")
        
        if help_entry.get("example"):
            lines.append("    --")
            lines.append("    -- Example:")
            for example_line in help_entry["example"].split('\n'):
                lines.append(f"    -- {example_line}")
        
        lines.append(f"    -- {section_name} = ...,")
    
    lines.append("\n}")
    return '\n'.join(lines)
```

### CLI Command (`src/kod/kod.py`)

```python
@cli.command()
@click.option("--distro", type=click.Choice(["arch", "debian"]), default="arch",
              help="Target distribution")
@click.option("--output", type=click.Path(), default=None,
              help="Write to file (default: stdout)")
def config_init(distro, output):
    """Generate a starter configuration file with all sections documented."""
    from kod.config.template import generate_config_template
    
    template = generate_config_template(distro)
    
    if output:
        with open(output, 'w') as f:
            f.write(template)
        click.echo(f"Template written to {output}")
    else:
        click.echo(template)
```

### Output Example

```lua
-- KodOS Configuration Template
-- Distribution: arch
--
-- See 'kod config schema' for full documentation.
-- Uncomment sections below and customize as needed.
--

return {

    -- BASE_DISTRIBUTION
    -- Base Linux distribution to install.
    -- Required: Yes
    --
    -- Example:
    -- base_distribution = "arch"
    -- base_distribution = ...,

    -- REPOS
    -- Repository definitions (package sources).
    --
    -- Example:
    -- repos = {
    --     official = repos.arch_repo("https://mirror.example.com/archlinux"),
    --     aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay.git"),
    -- }
    -- repos = ...,

    -- DEVICES
    -- Disk and partition definitions for system installation.
    --
    -- Example:
    -- devices = {
    --     disk0 = disk.disk_definition("/dev/sda", "50GB"),
    -- }
    -- devices = ...,
    
    ...more sections...
}
```

## Usage Examples

```bash
# Show template on stdout
kod config init

# Show debian template
kod config init --distro debian

# Write to file
kod config init --output ~/.kod/config.lua

# Write debian template to file
kod config init --distro debian --output config-debian.lua
```

## Testing

Add tests in `tests/test_kod_cli.py` or appropriate test file:

```python
def test_config_init_generates_template():
    """config init produces valid Lua syntax."""
    result = runner.invoke(cli, ['config', 'init'])
    assert result.exit_code == 0
    assert 'return {' in result.output
    assert '-- ' in result.output  # Has comments
    # Verify template can be parsed
    assert 'base_distribution' in result.output

def test_config_init_distro_option():
    """config init --distro debian generates debian-specific template."""
    result = runner.invoke(cli, ['config', 'init', '--distro', 'debian'])
    assert result.exit_code == 0
    assert 'Distribution: debian' in result.output

def test_config_init_output_file():
    """config init --output writes to file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        output_path = f.name
    
    try:
        result = runner.invoke(cli, ['config', 'init', '--output', output_path])
        assert result.exit_code == 0
        assert os.path.exists(output_path)
        
        with open(output_path) as f:
            content = f.read()
        assert 'return {' in content
        assert 'base_distribution' in content
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)

def test_config_init_template_is_valid_lua():
    """Template can be parsed as Lua (basic check)."""
    result = runner.invoke(cli, ['config', 'init'])
    assert result.exit_code == 0
    # Basic syntax checks (no brackets mismatches)
    assert result.output.count('{') == result.output.count('}')
    assert result.output.count('[') == result.output.count(']')
```

## Success Criteria

✅ Command exists and generates template  
✅ Template includes all 13 sections  
✅ Template sections have descriptions as comments  
✅ Template sections include examples as comments  
✅ `--distro` option works (arch and debian)  
✅ `--output` option writes to file  
✅ Default (no args) outputs to stdout  
✅ Template has valid Lua syntax (braces match)  
✅ Tests added and passing  
✅ All existing tests still pass  

## Notes

- Template should be copy-paste-able (valid Lua syntax even with all comments)
- Keep line lengths reasonable (comments at 80 chars)
- All sections should be commented out (users uncomment what they need)
- Indentation in template should use 4 spaces (standard Lua convention)
- The `= ...` placeholder makes it clear what to fill in
