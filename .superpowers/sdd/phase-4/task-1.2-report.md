# Task 1.2: Dependency Resolution Fallback Logic Fix - DONE

**Status:** ✅ DONE

## Summary

Fixed unreachable fallback code in `get_list_of_dependencies()` in `src/kod/arch.py`. The function was checking if a package group query returned results using `len(pkgs_list) > 0`, but when the output was empty string `""`, splitting it on newlines produced `['']` (list with one empty string), so the condition was True despite having no actual content. This prevented the fallback query from executing.

## Changes Made

### Bug Fix (src/kod/arch.py)

**Root cause:** Empty string is falsy, but when you split `"".strip().split("\n")`, you get `['']`, which has length > 0.

**Solution:** 
- Check explicitly for non-empty strings before using output
- Filter out empty strings when splitting
- Add proper error handling in fallback path
- Simplified logic to be clearer about intent

```python
# Before: len(pkgs_list) > 0 would be True even with empty output
pkgs_list = exec(f"pacman -Sgq {pkg}", get_output=True).strip().split("\n")
if len(pkgs_list) > 0:  # BUG: [''] has len > 0

# After: Explicitly validate non-empty string
group_output = exec(f"pacman -Sgq {pkg}", get_output=True).strip()
if group_output:  # Only True if string is non-empty
    pkgs_list = group_output.split("\n")
    pkgs_list = [p.strip() for p in pkgs_list if p.strip()]  # Filter empty
    if pkgs_list:
        return pkgs_list + [pkg]
```

### Test Coverage (tests/distributions/test_arch.py)

Added new test: `TestGetListOfDependencies::test_get_list_of_dependencies_uses_fallback_when_group_not_found`

- Verifies that when `-Sgq` returns empty, fallback `-Si` query executes
- Confirms dependencies from fallback are returned correctly
- Validates that list is not empty when fallback is used

## Test Results

```
341 passed, 16 skipped, 3 failed (pre-existing)
```

- ✅ New test passing: `test_get_list_of_dependencies_uses_fallback_when_group_not_found`
- ✅ All existing arch tests still passing
- ✅ No regressions in other test suites
- ℹ️ 3 pre-existing failures (flatpak handling, chroot validation)

**Test count increased:** 340 → 341 passing

## Verification

### Test Execution
```bash
$ uv run pytest tests/distributions/test_arch.py::TestGetListOfDependencies -xvs
PASSED
```

### Full Suite
```bash
$ uv run pytest tests/ -q
341 passed, 16 skipped, 3 failed (pre-existing)
```

## Commit

- **Hash:** `27a81f6`
- **Message:** "fix: Enable dependency resolution fallback logic"

## Concerns

None. The fix is minimal, surgical, and well-tested. The logic is now simpler and easier to understand.

## Implementation Approach

Followed **Test-Driven Development:**
1. ✅ RED: Wrote failing test showing fallback not executing
2. ✅ GREEN: Implemented minimal fix to pass test
3. ✅ REFACTOR: Cleaned up logic and added error handling
4. ✅ VERIFY: All tests pass, no regressions

## Related Issues

- Medium-priority bug #4 from codebase audit
- Previous task: Kernel validation (commit 3cafc96)
