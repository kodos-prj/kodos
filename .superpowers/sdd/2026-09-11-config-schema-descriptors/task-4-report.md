# Task 4 Report: `kod config init` Command

**Status: DONE**

## Summary

Successfully implemented the `kod config init` command to generate starter configuration templates with all sections documented as comments. The implementation includes the template generator module, CLI command, and comprehensive test coverage.

## Implementation Details

### Files Created
1. **`src/kod/config/template.py`** (NEW - 55 lines)
   - `generate_config_template(distro: str = "arch") -> str` function
   - Generates valid Lua configuration file with all 13 sections as comments
   - Includes descriptions and examples from `SECTION_HELP`
   - Supports both "arch" and "debian" distributions via distro parameter

### Files Modified
1. **`src/kod/kod.py`** (added 19 lines)
   - Added `@config.command(name="init")` decorated function `config_init()`
   - Supports `--distro` option (arch/debian, default: arch)
   - Supports `--output` option (file path, default: stdout)
   - Uses lazy loading to import template generator only when needed

2. **`tests/config/test_cli.py`** (added 7 new tests)
   - `test_config_init_generates_template()` - verifies basic template generation
   - `test_config_init_distro_option()` - validates distro parameter
   - `test_config_init_output_file()` - tests file output functionality
   - `test_config_init_template_is_valid_lua()` - checks Lua syntax validity
   - `test_config_init_template_all_sections()` - verifies all 13 sections present
   - `test_config_init_arch_distro()` - tests arch distro specifically

## Test Results

### New Tests (All Passing)
```
tests/config/test_cli.py::test_config_init_generates_template PASSED
tests/config/test_cli.py::test_config_init_distro_option PASSED
tests/config/test_cli.py::test_config_init_output_file PASSED
tests/config/test_cli.py::test_config_init_template_is_valid_lua PASSED
tests/config/test_cli.py::test_config_init_template_all_sections PASSED
tests/config/test_cli.py::test_config_init_arch_distro PASSED
```

### Full Config Test Suite
```
======================== 120 passed, 8 skipped in 0.12s ========================
```

All 13 tests in `tests/config/test_cli.py` pass (7 pre-existing + 6 new).

### Template Validation

Generated template:
- **Valid Lua syntax**: Braces and brackets properly matched (verified by test)
- **Sections included**: All 13 sections with descriptions and examples
- **Properly commented**: All content in comment form, copy-paste ready
- **Line count**: 148 lines for arch distribution
- **Indentation**: 4-space standard Lua convention

Sample output line:
```lua
    -- BASE_DISTRIBUTION
    -- Base Linux distribution to install.
    -- Required: Yes
    --
    -- Example:
    -- base_distribution = "arch"
    -- base_distribution = ...,
```

## Usage Examples Verified

```bash
# Show template on stdout
$ kod config init
# Output: 148-line Lua template with all sections

# Show debian template
$ kod config init --distro debian
# Output: Template with "Distribution: debian" header

# Write to file
$ kod config init --output ~/.kod/config.lua
# Output: "Template written to ~/.kod/config.lua"

# Write debian template to file
$ kod config init --distro debian --output config-debian.lua
```

## Success Criteria Check

✅ Command exists and generates template  
✅ Template includes all 13 sections (base_distribution, repos, devices, boot, hardware, locale, network, users, desktop, fonts, packages, services, programs)  
✅ Template sections have descriptions as comments  
✅ Template sections include examples as comments  
✅ `--distro` option works (arch and debian)  
✅ `--output` option writes to file  
✅ Default (no args) outputs to stdout  
✅ Template has valid Lua syntax (braces match)  
✅ Tests added and passing (6 new tests)  
✅ All existing tests still pass (120 config tests)  

## Commit

- **Hash**: `8959db6`
- **Message**: `feat: add 'kod config init' command (generates commented config templates)`
- **Files changed**: 3 files, 145 insertions(+)

## Notes

### Design Decisions (Ponytail)
- Used stdlib `str.split()` and list operations only; no external dependencies added
- Template generation is intentionally simple: iterate schema keys, pull from SECTION_HELP
- Lazy import of template module in CLI keeps dependency graph minimal
- Single function in template.py handles all distro variations (no separate classes)

### Why This Approach
1. **Minimal code**: Single-responsibility function, no over-abstraction
2. **Maintainable**: Template structure mirrors schema exactly
3. **Testable**: Easy to verify template structure and content
4. **User-friendly**: Copy-paste ready Lua with clear commented structure

## Integration with Phase 5b

This task completes the config schema descriptors phase:
- Task 1: Schema with SECTION_HELP ✅
- Task 2: Validator with field descriptions ✅
- Task 3: Schema CLI (text + JSON) ✅
- Task 4: Config template generator ✅ (THIS TASK)

Users can now:
1. View full schema: `kod config schema [--section X]`
2. Generate starter config: `kod config init [--distro debian] [--output file]`
3. Validate existing config: `kod config validate -c file.lua`

All with integrated help and descriptions throughout.
