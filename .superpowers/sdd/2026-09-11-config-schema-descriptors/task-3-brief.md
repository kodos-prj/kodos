# Task 3: Create 'kod config schema' CLI Command

## Requirement

Add a new CLI command `kod config schema` to display configuration schema with descriptions and nested field documentation.

## Files to Modify

- **`src/kod/kod.py`** — Add new CLI command
  - Add `@cli.command()` decorated function `config_schema()`
  - Support `--section` option to show only one section
  - Support `--format` option (text or json)

## Implementation Details

### Command Signature

```python
@cli.command()
@click.option("--section", default=None, help="Show only this section (e.g., 'boot')")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def config_schema(section, format):
    """Display configuration schema with descriptions and field documentation."""
```

### Text Output Format

For `kod config schema`:
```
BOOT
============================================================
Type: dict
Required: No

Kernel and bootloader configuration.

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

Fields:
  kernel:
    Type: dict
    Required: No
    Kernel package and loadable modules.
    Subfields:
      package: Kernel package name (e.g., 'linux', 'linux-lts', 'linux-hardened').
      modules: List of kernel modules to load at boot (for initramfs).

  loader:
    Type: dict
    Required: No
    Bootloader configuration.
    Subfields:
      type: Bootloader type.
      timeout: Boot menu timeout in seconds.
```

### JSON Output Format

For `kod config schema --format json`:
```json
{
  "boot": {
    "description": "Kernel and bootloader configuration.",
    "type": "dict",
    "required": false,
    "example": "boot = {...}",
    "fields": {
      "kernel": {...},
      "loader": {...}
    }
  },
  ...other sections...
}
```

### Filtering by Section

For `kod config schema --section boot`:
- Show only the "boot" section in text format
- Works with both text and json formats

### Command Placement

Place the function in `src/kod/kod.py` near other config commands (config_validate, etc.)

## Testing

Add tests in `tests/test_kod_cli.py` or `tests/integration/test_cli_commands.py`:

```python
def test_config_schema_text_output():
    """config schema shows all sections in text format."""
    result = runner.invoke(cli, ['config', 'schema'])
    assert result.exit_code == 0
    assert 'BOOT' in result.output
    assert 'LOCALE' in result.output
    assert 'Example:' in result.output

def test_config_schema_filter_section():
    """config schema --section shows only requested section."""
    result = runner.invoke(cli, ['config', 'schema', '--section', 'boot'])
    assert result.exit_code == 0
    assert 'BOOT' in result.output
    assert 'LOCALE' not in result.output

def test_config_schema_json_output():
    """config schema --format json outputs valid JSON."""
    result = runner.invoke(cli, ['config', 'schema', '--format', 'json'])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert 'boot' in data
    assert 'description' in data['boot']
    assert 'type' in data['boot']

def test_config_schema_invalid_section():
    """config schema --section with invalid name shows error."""
    result = runner.invoke(cli, ['config', 'schema', '--section', 'invalid'])
    assert result.exit_code != 0
    assert 'not found' in result.output or 'invalid' in result.output.lower()
```

## Success Criteria

✅ Command exists and runs without errors  
✅ Text output shows all 13 sections by default  
✅ Text output is readable and properly formatted  
✅ JSON output is valid and machine-readable  
✅ `--section` filter works correctly  
✅ `--format` option works for both text and json  
✅ Tests added and passing  
✅ All existing tests still pass (no regressions)  

## Notes

- Use Click's built-in features (no external formatting libraries needed)
- Keep output to 60-80 chars per line for terminal readability
- Indent nested fields for clarity (2-space indent)
- Handle cases where section not found gracefully (error message)
- JSON output should be minifiable (can add --compact option later if needed)
