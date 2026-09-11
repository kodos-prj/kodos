# Task 2: Update Validator with Nested Field Validation

## Requirement

Update `src/kod/config/validator.py` to:
1. Include SECTION_HELP descriptions and error_help in validation error messages
2. Add nested field validation (validate field types within dict sections)
3. Improve error readability with field descriptions and examples

## Files to Modify

- **`src/kod/config/validator.py`** — Main changes
  - Add import of SECTION_HELP from schema.py
  - Add `_lookup_field_help()` function for nested field lookup
  - Update `validate_config()` to use descriptions in errors
  - Add `_validate_nested_fields()` helper for field-level validation
  - Update type error messages to include error_help and examples

## Key Changes

### 1. Add SECTION_HELP Import

```python
from kod.config.schema import SCHEMA, SECTION_HELP
```

### 2. Add Field Lookup Function

```python
def _lookup_field_help(section_key: str, field_path: List[str]) -> Optional[Dict]:
    """Look up help for a nested field path: ["boot", "kernel", "package"].
    
    Args:
        section_key: Top-level section name (e.g., "boot")
        field_path: List of nested field names to follow
    
    Returns:
        Dict with field help info, or None if path not found
    """
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
```

### 3. Update Error Messages

Type errors should now include:
1. error_help message (if present in SECTION_HELP)
2. Description (if error_help not present)
3. Example (if present)

Example error output:
```
❌ Invalid type for 'boot': expected dict, got list

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
```

### 4. Add Nested Field Validation (Optional for Phase 5b)

Add basic nested field type checking (not full recursive validation):
- Check that boot.kernel is a dict (if present)
- Check that boot.kernel.modules is a list (if present)
- Check that locale.timezone is a string (if present)
- Generate helpful errors for common mistakes

**Do NOT validate:**
- Enum values (e.g., boot.loader.type must be "systemd-boot" or "grub")
- Dependent fields (e.g., if enable=true then X must be set)
- Those can be added in Phase 5c if needed

## Testing

Update `tests/config/test_validator.py`:
- Test that type errors include error_help message
- Test that type errors include description (when no error_help)
- Test that type errors include examples
- Test nested field validation (boot.kernel, locale.locale, etc.)
- Test that unknown sections still get suggestions (unchanged behavior)
- Test backward compatibility (all 492 existing tests still pass)

**Minimum test cases:**
```python
def test_type_error_includes_error_help():
    """Type errors include error_help from SECTION_HELP."""
    config = {"packages": {"vim": true}}  # Wrong type
    errors = validate_config(config)
    assert len(errors) > 0
    assert "Must be a list" in str(errors[0])  # error_help message

def test_nested_field_validation():
    """Boot kernel is validated as dict."""
    config = {"boot": {"kernel": ["linux"]}}  # Wrong type
    errors = validate_config(config)
    assert len(errors) > 0
    assert "boot.kernel" in str(errors[0])
```

## Success Criteria

✅ Type error messages include error_help or description  
✅ Examples are included in error messages  
✅ Nested field validation works (boot.kernel, locale.locale, etc.)  
✅ Error messages are clear and actionable  
✅ All 492 existing tests still pass  
✅ New tests added and passing  
✅ No changes to existing SCHEMA validation logic  
✅ Backward compatible (existing valid configs still validate)  

## Notes

- SECTION_HELP was added in Task 1, now we use it
- Keep error messages concise (2-3 lines max for type errors)
- Nested validation is best-effort; unknown fields are not errors
- The validator runs after load_config(), so structure is already valid Lua
