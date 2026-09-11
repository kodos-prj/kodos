# Task 6: Full Test Coverage and Verification

## Requirement

Complete Phase 5c by running comprehensive tests to verify all work integrates correctly:
1. All 541+ existing tests still pass (no regressions)
2. New tests for Tasks 1-5 all pass
3. System end-to-end test: config → validator → planner → bootstrap
4. Document test results and any issues found

## Current State

### Completed Tasks
- ✅ Task 1: Lua schema defined (`src/kod/lib/schema.lua`)
- ✅ Task 2: 13 section modules created (`src/kod/sections/*.lua`)
- ✅ Task 3: Planner refactored to composition (`src/kod/lib/planner.lua`)
- ✅ Task 4: Bootstrap integrated Lua planner (`src/kod/planner.py`)
- ✅ Task 5: Validator reads Lua schema (`src/kod/config/validator.py`)

### Test Status (Before Task 6)
- Phase 5b: 541 passing tests, 5 pre-existing failures, 17 skipped
- Phase 5c Tasks 1-4: ~40 new tests added by subagents
- Phase 5c Task 5: Validator changes (fallback to SECTION_HELP, should be safe)
- **Expected:** All 541+ tests still pass, 40+ new tests pass

## Files to Test

### New Files (Phase 5c)
- `src/kod/lib/schema.lua` (Task 1)
- `src/kod/sections/*.lua` — 13 modules (Task 2)
- `src/kod/lib/planner.lua` (Task 3)
- `tests/lua/test_schema.lua` (new, Task 1)
- `tests/lua/test_sections.lua` (new, Task 2)
- `tests/lua/test_composition.lua` (new, Task 2)
- `tests/lua/test_planner.lua` (new, Task 3)
- `tests/test_bootstrap_lua.py` (new, Task 4)
- `tests/test_lua_schema.py` (new, Task 5)

### Modified Files (Phase 5c)
- `src/kod/config/validator.py` (Task 5)
- `src/kod/planner.py` (Task 4)
- `tests/config/test_validator.py` (should add tests for Lua schema)
- `tests/test_bootstrap.py` (should verify Lua planner integration)

### Unchanged (Should Still Pass)
- All Phase 1 tests (config system)
- All Phase 3 tests (program registry)
- All Phase 5b tests (config schema descriptors)

## Test Execution Strategy

### Step 1: Python Unit Tests

Run all Python tests:
```bash
pytest tests/ -v --tb=short
```

Expected results:
- ✅ 541+ existing tests pass (with potential new tests from Tasks 4-5)
- ⚠️ 5 pre-existing failures unchanged (not our responsibility)
- ✅ 17 skipped tests unchanged

### Step 2: Lua Unit Tests

If test runner available:
```bash
lua tests/lua/test_schema.lua
lua tests/lua/test_sections.lua
lua tests/lua/test_composition.lua
lua tests/lua/test_planner.lua
```

Expected results:
- ✅ All Lua tests pass (40+ tests total)
- ✅ All modules load without errors
- ✅ All functions work as expected

### Step 3: Integration Tests

Create/run integration test:
```python
# tests/test_phase5c_integration.py
def test_full_phase5c_integration():
    """Test Phase 5c chain: config → validator → planner → bootstrap"""
    
    # Load config
    config = load_config("tests/fixtures/sample.kod")
    
    # Validate with Lua schema
    errors = validate_config(config)
    assert len(errors) == 0, f"Validation failed: {errors}"
    
    # Compose steps with Lua planner
    planner = lua.require('kod.lib.planner')
    steps, err = planner.compose(config, "arch")
    assert not err, f"Planner failed: {err}"
    assert len(steps) > 0, "No steps generated"
    
    # Verify step format
    for step in steps:
        assert 'name' in step
        assert 'description' in step
        assert 'command' in step
    
    # Bootstrap would execute steps here
    print(f"Generated {len(steps)} steps successfully")
```

### Step 4: Regression Testing

Verify no existing functionality broken:
```bash
# Run with specific markers for Phase 1-5
pytest tests/ -m "phase1 or phase3 or phase5" -v
```

Expected: All 541+ tests pass unchanged.

### Step 5: Coverage Analysis

Check test coverage:
```bash
pytest tests/ --cov=src/kod --cov-report=html
```

Expected:
- Core modules (validator, planner, schema, bootstrap) > 80% coverage
- New Lua code adequately tested by new test files

## Test Checklist

### Lua Schema Tests (Task 1)
- [ ] All 13 sections defined
- [ ] Each section has type, description, required fields
- [ ] Nested fields accessible (3 levels)
- [ ] validate_field() works for all types
- [ ] get_default() returns correct defaults
- [ ] Validation catches type mismatches
- [ ] Validation catches enum violations

### Section Module Tests (Task 2)
- [ ] All 13 modules load without errors
- [ ] Each module has schema reference
- [ ] Each module has emit_steps() function
- [ ] emit_steps() returns Step array
- [ ] emit_steps() handles nil config
- [ ] emit_steps() generates correct distro-specific steps
- [ ] All modules independent (no cross-imports)
- [ ] No duplicate step names across modules

### Planner Tests (Task 3)
- [ ] Planner loads all 13 sections
- [ ] Planner composes steps from all sections
- [ ] Planner sorts steps by order field
- [ ] Planner validates required fields
- [ ] Planner handles missing sections
- [ ] Planner respects distro parameter
- [ ] Planner error handling works

### Bootstrap Integration Tests (Task 4)
- [ ] Lua runtime initialized
- [ ] Planner module loads from Python
- [ ] compose_steps_lua() called correctly
- [ ] Lua steps converted to Python correctly
- [ ] Fallback to Python planner works
- [ ] Environment variable KOD_USE_LUA_PLANNER works
- [ ] No performance regression

### Validator Tests (Task 5)
- [ ] Lua schema loads and caches
- [ ] Validator validates all 13 sections
- [ ] Type validation works (all types)
- [ ] Enum validation works
- [ ] Required field checking works
- [ ] Nested field validation works (3 levels)
- [ ] Fallback to SECTION_HELP works if Lua fails
- [ ] Error messages include paths
- [ ] Backward compatible with Phase 5b tests

### System Integration Test
- [ ] Config loads → validator validates → planner composes → bootstrap ready
- [ ] All distros (arch, debian) work
- [ ] Error messages are clear
- [ ] No crashes or unhandled exceptions

## Test Fixtures

Create/use test configs:

### Minimal Config (Base Only)
```lua
base_distribution = "arch"
```

### Partial Config (Boot + Packages)
```lua
base_distribution = "arch"
boot = {
    kernel = {package = "linux"}
}
packages = {"git", "vim"}
```

### Full Config (All Sections)
```lua
base_distribution = "arch"
repos = {...}
devices = {...}
boot = {...}
hardware = {...}
locale = {...}
network = {...}
users = {...}
desktop = {...}
fonts = {...}
packages = {...}
services = {...}
programs = {...}
```

### Invalid Configs (For Error Testing)
- Missing base_distribution (required)
- Invalid base_distribution value (not in enum)
- Wrong type for field (e.g., boot as string instead of dict)
- Missing required nested field

## Success Criteria

### All Tests Pass
✅ 541+ existing tests pass (no regressions)  
✅ 40+ new Phase 5c tests pass  
✅ 5 pre-existing failures unchanged  
✅ 17 skipped tests unchanged  

### All Modules Load
✅ Lua schema loads  
✅ 13 section modules load  
✅ Planner loads  
✅ Bootstrap integration works  
✅ Validator loads Lua schema  

### Integration Works
✅ Config → Validator → Planner → Bootstrap chain works  
✅ All distros (arch, debian) generate steps  
✅ Error handling works gracefully  
✅ Performance acceptable (no regression)  

### Code Quality
✅ No new warnings or errors  
✅ Clear error messages  
✅ Well-documented code  
✅ Backward compatible  

## Reporting

Create final report: `task-6-report.md`

Include:
- Test execution results (all test runs)
- Test count: passing, failing, skipped
- Any regressions or new issues
- Performance metrics (if applicable)
- Code coverage summary
- Recommendation for Phase 5c completion
- Issues for follow-up work
- Commit hashes for all Phase 5c tasks

## Expected Outcome

**Phase 5c Complete** with:
- ✅ Lua schema as single source of truth
- ✅ 13 composable section modules
- ✅ Schema-driven planner (90% code reduction)
- ✅ Lua-aware bootstrap integration
- ✅ Python validator reads Lua schema
- ✅ Full test coverage (600+ tests passing)
- ✅ Zero regressions
- ✅ Ready for Phase 5d or next major work

## Next Steps After Task 6

1. **Immediate:**
   - Review test results
   - Fix any regressions found
   - Document any issues

2. **Short-term:**
   - Remove SECTION_HELP if confidence high (full cleanup)
   - Add schema versioning
   - Optimize Lua schema caching

3. **Future:**
   - Phase 5a: Custom packages support
   - Phase 5d: User-defined sections
   - Full Python → Lua migration planning

## Related

- Lua Schema: `src/kod/lib/schema.lua` (Task 1)
- Section Modules: `src/kod/sections/*.lua` (Task 2)
- Planner: `src/kod/lib/planner.lua` (Task 3)
- Bootstrap: `src/kod/planner.py` (Task 4)
- Validator: `src/kod/config/validator.py` (Task 5)
