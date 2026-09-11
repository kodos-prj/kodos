# Task 5: Python Validator Reads Lua Schema

## Requirement

Update the Python validator (`src/kod/config/validator.py`) to read the Lua schema as the single source of truth for validation, instead of using the Python SECTION_HELP dict.

## Current State

Phase 5b created:
- Python SECTION_HELP dict with schema information
- Python validator using SECTION_HELP for validation
- CLI commands (`kod config schema`, `kod config init`) using SECTION_HELP

## Target State (After Task 5)

- **Lua schema** is the single source of truth (`src/kod/lib/schema.lua`)
- **Python validator** reads Lua schema (not SECTION_HELP)
- **SECTION_HELP** becomes a derived view or is removed (no duplication)
- All validation rules enforced consistently

## File to Update

**`src/kod/config/validator.py`** (REFACTOR)

## Implementation Details

### 1. Load Lua Schema in Python

```python
import lupa

def get_lua_schema():
    """Load Lua schema as Python-usable data structure"""
    lua = get_lua_runtime()  # Reuse singleton from bootstrap
    schema_module = lua.require('kod.lib.schema')
    
    # Convert Lua schema to Python dict
    schema = {}
    for section_name in schema_module._fields:
        section_def = schema_module[section_name]
        schema[section_name] = lua_table_to_dict(section_def)
    
    return schema
```

### 2. Validation Using Lua Schema

Update `validate_field()` in validator.py to use Lua schema:

```python
def validate_field(self, schema_def, value, path=""):
    """Validate value against Lua schema definition"""
    
    if not schema_def:
        return []  # No schema, no validation
    
    errors = []
    
    # Type validation
    if not value and schema_def.get('required'):
        errors.append(f"{path}: Required field is missing")
        return errors
    
    if value is None:
        return []  # Optional field can be None
    
    # Get expected type from Lua schema
    schema_type = schema_def.get('type')
    
    if schema_type == 'string':
        if not isinstance(value, str):
            errors.append(f"{path}: Expected string, got {type(value).__name__}")
    
    elif schema_type == 'dict':
        if not isinstance(value, dict):
            errors.append(f"{path}: Expected dict, got {type(value).__name__}")
        else:
            # Validate nested fields
            if 'fields' in schema_def:
                for field_name, field_schema in schema_def['fields'].items():
                    field_path = f"{path}.{field_name}" if path else field_name
                    field_errors = self.validate_field(
                        field_schema,
                        value.get(field_name),
                        field_path
                    )
                    errors.extend(field_errors)
    
    elif schema_type == 'list':
        if not isinstance(value, list):
            errors.append(f"{path}: Expected list, got {type(value).__name__}")
    
    # Enum validation
    if schema_def.get('enum'):
        if value not in schema_def['enum']:
            errors.append(f"{path}: Must be one of {schema_def['enum']}")
    
    return errors
```

### 3. Initialize Validator with Lua Schema

```python
class ConfigValidator:
    def __init__(self):
        # Load Lua schema once at startup
        self.schema = self._load_lua_schema()
    
    def _load_lua_schema(self):
        """Load schema from Lua (Task 1)"""
        try:
            return get_lua_schema()
        except Exception as e:
            logger.warning(f"Failed to load Lua schema: {e}")
            # Fallback to hardcoded schema if needed
            return self._get_fallback_schema()
    
    def validate(self, config):
        """Validate config against Lua schema"""
        errors = []
        
        # Required field: base_distribution
        if 'base_distribution' not in config:
            errors.append("base_distribution: Required field is missing")
        
        # Validate each section against its schema
        for section_name, section_schema in self.schema.items():
            if section_name in config:
                section_errors = self.validate_field(
                    section_schema,
                    config[section_name],
                    section_name
                )
                errors.extend(section_errors)
        
        return errors
```

### 4. Update CLI Commands

Ensure `kod config schema` and `kod config init` use Lua schema:

```python
@click.command()
def config_schema():
    """Display configuration schema"""
    validator = ConfigValidator()
    schema = validator.schema
    
    for section_name, section_def in schema.items():
        print(f"\n{section_name.upper()}")
        print(f"  Type: {section_def.get('type')}")
        print(f"  Required: {section_def.get('required')}")
        print(f"  Description: {section_def.get('description')}")
        
        if 'fields' in section_def:
            print("  Fields:")
            for field_name, field_def in section_def['fields'].items():
                print(f"    - {field_name}: {field_def.get('type')}")
```

### 5. Remove Redundancy

After validator reads Lua schema:
- **Option A:** Remove SECTION_HELP from Python (clean, no duplication)
- **Option B:** Keep SECTION_HELP as cached copy (backward compat)
- **Recommended:** Remove SECTION_HELP, use Lua schema everywhere

## Caching Strategy

Schema is read once at validator initialization:

```python
# Global validator instance
_validator_instance = None

def get_validator():
    """Get or create singleton validator"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ConfigValidator()
    return _validator_instance
```

This avoids repeatedly loading Lua schema on every validation call.

## Error Handling

- If Lua schema fails to load → use fallback hardcoded schema
- Log warnings for schema loading failures
- Ensure validation still works even if Lua unavailable

## Lua↔Python Data Conversion

Helper function to convert Lua table to Python dict:

```python
def lua_table_to_dict(lua_table):
    """Convert Lua table to Python dict recursively"""
    if not isinstance(lua_table, dict):
        return lua_table
    
    result = {}
    for key, value in lua_table.items():
        if isinstance(value, dict):
            result[key] = lua_table_to_dict(value)
        elif isinstance(value, (list, tuple)):
            result[key] = [lua_table_to_dict(v) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value
    
    return result
```

## Testing

Update `tests/config/test_validator.py`:

```python
# Test Lua schema loading
def test_validator_loads_lua_schema():
    validator = ConfigValidator()
    assert 'base_distribution' in validator.schema
    assert len(validator.schema) == 13  # All 13 sections
    assert validator.schema['base_distribution']['type'] == 'string'

# Test validation against Lua schema
def test_validate_against_lua_schema():
    validator = ConfigValidator()
    config = {'base_distribution': 'arch'}
    errors = validator.validate(config)
    assert len(errors) == 0

# Test type validation
def test_type_validation_from_lua_schema():
    validator = ConfigValidator()
    config = {'base_distribution': 123}  # Wrong type
    errors = validator.validate(config)
    assert len(errors) > 0
    assert 'Expected string' in errors[0]

# Test enum validation
def test_enum_validation_from_lua_schema():
    validator = ConfigValidator()
    config = {'base_distribution': 'ubuntu'}  # Not in enum
    errors = validator.validate(config)
    assert len(errors) > 0

# Test nested field validation
def test_nested_field_validation():
    validator = ConfigValidator()
    config = {
        'base_distribution': 'arch',
        'boot': {
            'kernel': {
                'package': 123  # Wrong type
            }
        }
    }
    errors = validator.validate(config)
    assert any('boot.kernel.package' in e for e in errors)

# Test required field validation
def test_required_field_validation():
    validator = ConfigValidator()
    config = {}  # Missing base_distribution
    errors = validator.validate(config)
    assert any('base_distribution' in e for e in errors)
```

Also add compatibility tests:

```python
# Ensure Lua schema matches Phase 5b expectations
def test_lua_schema_has_all_13_sections():
    validator = ConfigValidator()
    expected_sections = {
        'base_distribution', 'repos', 'devices', 'boot', 'hardware',
        'locale', 'network', 'users', 'desktop', 'fonts',
        'packages', 'services', 'programs'
    }
    assert set(validator.schema.keys()) == expected_sections

def test_base_distribution_is_required():
    validator = ConfigValidator()
    assert validator.schema['base_distribution']['required'] == True

def test_packages_is_list():
    validator = ConfigValidator()
    assert validator.schema['packages']['type'] == 'list'
```

## Success Criteria

✅ Lua schema loads successfully in Python  
✅ Validator uses Lua schema (not SECTION_HELP)  
✅ All validation rules work (type, enum, required, nested)  
✅ All 541+ existing tests pass  
✅ 20+ new validator tests pass  
✅ No performance regression  
✅ Caching prevents repeated Lua loads  
✅ Error handling graceful (fallback available)  
✅ CLI commands still work  
✅ SECTION_HELP removed (no duplication) OR preserved (backward compat)  

## File Changes

- **`src/kod/config/validator.py`** — refactor to use Lua schema
- **`src/kod/config/schema.py`** — optionally remove SECTION_HELP if moving to Lua
- **`tests/config/test_validator.py`** — add 20+ tests
- **`src/kod/kod.py`** — update CLI if needed

## File Size Expectation

- Validator refactor: ~50-100 lines modified
- New validation functions: ~50-100 lines
- Tests: ~300+ lines
- Total: ~400-500 lines

## Integration Chain

1. **Lua schema** defined (Task 1, completed)
2. **Lua planner** uses schema (Task 3, completed)
3. **Python validator** reads Lua schema (Task 5, current)
4. **Bootstrap** calls validator + planner (Task 4, completed)
5. **Full system test** (Task 6, upcoming)

## Notes

- Lua schema is the source of truth (Python derives from it)
- Validation happens in Python (faster than calling Lua)
- Schema is cached to avoid repeated Lua loads
- Fallback mechanism ensures robustness
- Consider versioning schema as it evolves
- Document schema changes for users

## Related

- Lua Schema: `src/kod/lib/schema.lua` (Task 1, completed)
- Lua Planner: `src/kod/lib/planner.lua` (Task 3, completed)
- Bootstrap: `src/kod/bootstrap.py` (Task 4, completed)
