# Task 1: Add SECTION_HELP with Nested Field Docs to schema.py

## Requirement

Add a `SECTION_HELP` dictionary to `src/kod/config/schema.py` that documents all 13 configuration sections with:
1. Top-level descriptions
2. Validation rules (required, valid_values, defaults)
3. Nested field documentation (up to 3 levels deep: section → fields → subfields)
4. Examples and error_help messages

## File to Modify

**`src/kod/config/schema.py`**

Currently contains only the `SCHEMA` dict mapping section names to types. Add the new `SECTION_HELP` dict immediately after (same file).

## Schema Structure

```python
SECTION_HELP = {
    "section_name": {
        "description": "What this section does.",
        "type": "dict|list|string",
        "required": True/False,
        "valid_values": [...],        # Optional: for string types with enum values
        "default": ...,               # Optional: default value
        "example": "...",             # Multi-line example (can use triple quotes)
        "error_help": "...",          # Optional: custom help for common errors
        "fields": {                   # Optional: for dict sections
            "field_name": {
                "description": "What this field does.",
                "type": "string|dict|list|boolean|number",
                "required": False,
                "default": ...,       # Optional
                "fields": {...}       # Optional: nested fields (max 3 levels total)
            }
        }
    }
}
```

## Sections to Document

These 13 sections must be in SECTION_HELP:
1. `base_distribution` — required string, enum: ["arch", "debian"]
2. `repos` — optional dict, nested fields: repo identifiers
3. `devices` — optional dict, nested fields: disk identifiers
4. `boot` — optional dict, nested fields: kernel, loader (each with subfields)
5. `hardware` — optional dict, nested fields: pipewire (with enable, extra_packages)
6. `locale` — optional dict, nested fields: locale (with subfields), timezone, keymap
7. `network` — optional dict, nested fields: hostname, ipv6
8. `users` — optional dict, nested fields: USERNAME (with shell, groups, home_programs)
9. `desktop` — optional dict, nested fields: environment, enable
10. `fonts` — optional dict, nested fields: monospace, sans_serif, emoji, enable
11. `packages` — optional list, error_help for common type mistake (list vs dict)
12. `services` — optional dict, nested fields: SERVICE_NAME (with enable, start)
13. `programs` — optional dict, nested fields: PROGRAM_NAME (with enable)

## Example Entry

See `src/kod/config/schema.py` lines 38-87 in the plan document for the full `boot` section example showing correct 3-level nesting.

## Testing

After implementation, write unit tests in `tests/test_schema.py`:
- Test that all 13 SCHEMA keys have SECTION_HELP entries
- Test that SECTION_HELP structure is valid (required keys present, types correct)
- Test that examples are syntactically valid Lua (can be parsed by lupa if available)
- Test nested field lookup function (sample: "boot.kernel.package" resolves correctly)

**Minimum test cases:**
- Assert `len(SECTION_HELP) == len(SCHEMA)`
- Assert each entry has "description" key
- Assert "example" values are non-empty strings
- Parse each example with lupa to verify Lua syntax (optional: skip if lupa unavailable)

## Success Criteria

✅ All 13 sections documented in SECTION_HELP  
✅ Nested fields complete (boot.kernel.*, locale.locale.*, users.USERNAME.*, etc.)  
✅ Examples provided for each section  
✅ Examples are syntactically valid Lua  
✅ Unit tests added and passing  
✅ No changes to existing SCHEMA validation logic  
✅ Code follows existing style in schema.py  

## Notes

- The plan document has detailed SECTION_HELP content for all 13 sections (lines 38-414 in the refined plan)
- This is purely data addition—no validation logic changes here (that's Task 2)
- Descriptions should be 1-2 sentences, examples should be realistic and copy-paste-able
- Keep error_help brief and specific (used when validation fails, not on success path)
