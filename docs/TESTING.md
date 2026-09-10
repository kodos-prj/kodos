# Testing Guide

This document describes how to run and understand the KodOS test suite.

## Quick Start

```bash
# Install development dependencies
uv sync --dev

# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/distributions/test_arch_proc_repos.py -v

# Run with coverage report
uv run pytest tests/ --cov=src/kod --cov-report=html
```

## Test Structure

The test suite is organized by component:

```
tests/
├── conftest.py                          # Pytest configuration and shared fixtures
├── test_common.py                       # Core exec() and error handling tests
├── config/                              # Configuration validation tests
├── core/                                # Core system functionality tests
├── distributions/                       # Distribution-specific tests
│   ├── test_arch_proc_repos.py         # Arch Linux repo processing (30 tests)
│   ├── test_debian_proc_repos.py       # Debian repo processing (23 tests)
│   ├── test_arch_installer.py          # Arch Linux installation tests
│   └── test_debian_installer.py        # Debian installation tests
├── registry/                            # Program registry tests
├── system/                              # System management tests
└── integration/                         # Integration tests (Phase 4)
    └── test_phase4_vm.py               # All Phase 4 bug fixes verified
```

## Test Categories

### Unit Tests (by module)

These test individual functions and modules in isolation using mocks.

- **test_common.py:** Core exec() function, error handling, command safety
- **test_arch_proc_repos.py:** Arch Linux repository processing
- **test_debian_proc_repos.py:** Debian repository processing
- **config/:** Configuration validation and schema enforcement
- **registry/:** Program registry functionality
- **system/:** System installation and generation management

### Integration Tests

These test bug fixes work correctly together in realistic scenarios.

- **test_phase4_vm.py:** Verifies all 7 Phase 4 bug fixes:
  1. Kernel version parsing validation
  2. Dependency resolution fallback
  3. Flatpak availability checking
  4. Package installation verification
  5. Build dependencies installation
  6. Privilege escalation levels
  7. Comprehensive proc_repos coverage

## Running Specific Tests

```bash
# Run all tests in a file
uv run pytest tests/distributions/test_arch_proc_repos.py -v

# Run a specific test class
uv run pytest tests/distributions/test_arch_proc_repos.py::TestArchProcReposAUR -v

# Run a specific test function
uv run pytest tests/distributions/test_arch_proc_repos.py::TestArchProcReposAUR::test_aur_basic -v

# Run tests matching a pattern
uv run pytest tests/ -k "privilege" -v

# Run tests marked with a specific marker
uv run pytest tests/ -m "integration" -v
```

## Test Output

Successful tests show:

```
tests/distributions/test_arch_proc_repos.py::TestArchProcReposAUR::test_aur_basic PASSED
```

Failed tests show:

```
tests/distributions/test_arch_proc_repos.py::TestArchProcReposAUR::test_aur_basic FAILED

    def test_aur_basic(self):
        result = proc_repos({"aur": []})
        assert result == ["aur"]
>       AssertionError: assert ["aur", "system"] == ["aur"]
```

## Coverage Report

Generate a coverage report to see which lines are tested:

```bash
# Generate coverage report
uv run pytest tests/ --cov=src/kod --cov-report=html

# View the report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

**Current Coverage:** 95%+ for modified code (Phase 4)

## Adding New Tests

### Template for Unit Tests

```python
"""Test description."""
import pytest
from unittest.mock import Mock, patch


class TestMyFeature:
    """Test suite for my feature."""
    
    def test_basic_functionality(self):
        """Test basic scenario."""
        # Arrange
        input_data = {"key": "value"}
        
        # Act
        result = my_function(input_data)
        
        # Assert
        assert result == {"result": "expected"}
    
    def test_error_handling(self):
        """Test error scenario."""
        with pytest.raises(ValueError):
            my_function(None)


class TestWithMocks:
    """Test suite using mocks."""
    
    @patch('module.external_function')
    def test_with_mock(self, mock_external):
        """Test with mocked external dependency."""
        mock_external.return_value = "mocked"
        
        result = my_function()
        
        mock_external.assert_called_once()
        assert result == "mocked"
```

### Template for Integration Tests

```python
"""Integration test for feature scenario."""
import pytest


class TestFeatureIntegration:
    """Integration test combining multiple components."""
    
    def test_complete_workflow(self):
        """Test complete workflow from start to finish."""
        # Step 1: Setup
        config = load_config()
        
        # Step 2: Execute
        result = feature.process(config)
        
        # Step 3: Verify all steps work together
        assert result.success
        assert result.data is not None
```

### Running New Tests

```bash
# Run your new test immediately
uv run pytest tests/my_test_file.py -v

# Add to CI/CD pipeline
# Update .github/workflows/test.yml to include your test
```

## Continuous Integration (CI/CD)

Tests run automatically on:

1. **Push to any branch** - Full test suite (uses GitHub Actions)
2. **Pull requests** - Full test suite before merge
3. **Releases** - Full test suite before tagging

See `.github/workflows/test.yml` for CI configuration.

## Troubleshooting

### Tests won't run - ModuleNotFoundError

```bash
# Make sure dependencies are installed
uv sync --dev

# Or reinstall them
uv sync --dev --upgrade
```

### Tests hang or timeout

```bash
# Run with timeout (fail if test takes > 10 seconds)
uv run pytest tests/ --timeout=10 -v

# Run with verbose output to see where it hangs
uv run pytest tests/ -vv
```

### Mock objects not working as expected

```python
# Make sure to use full module path
@patch('src.kod.arch.execute')  # Correct
# NOT:
@patch('execute')  # Wrong - won't find it
```

### Test file not discovered

```bash
# Test file must be named test_*.py or *_test.py
# Test classes must start with Test
# Test functions must start with test_

# Check discovery with --collect-only
uv run pytest tests/ --collect-only
```

## Performance Tips

```bash
# Run tests in parallel (faster)
uv run pytest tests/ -n auto

# Run only changed tests
uv run pytest tests/ --lf

# Stop on first failure
uv run pytest tests/ -x

# Show slowest tests
uv run pytest tests/ --durations=10
```

## Phase 4 Testing

Phase 4 added comprehensive testing for all bug fixes:

**Test Summary:**
- **7 bugs fixed** with tests for each
- **60+ new tests** added
- **422+ total tests** in suite
- **95%+ coverage** for modified code

**Each bug has dedicated tests:**

1. **Kernel version parsing (Bug #3):** 4 tests for malformed input, empty strings, valid versions
2. **Dependency fallback (Bug #4):** 1 test for fallback execution
3. **Flatpak availability (Bug #5):** 2 tests for installed/unavailable scenarios
4. **Package verification (Bug #6):** 2 tests for success/failure detection
5. **Build dependencies (Bug #2):** 5 tests for install, verify, idempotent behavior
6. **Privilege levels (Bug #1):** 22 tests for user/sudo/root levels
7. **proc_repos coverage (Bug #7):** 53 tests for all repo combinations

Run Phase 4 tests specifically:

```bash
uv run pytest tests/integration/test_phase4_vm.py -v
```

## Known Limitations

1. **VM Testing:** Integration tests simulate VM behavior with mocks, not actual VMs
2. **External Dependencies:** Tests mock external commands (pacman, apt, flatpak)
3. **Network Tests:** No real network calls; all network operations are mocked
4. **Performance Tests:** Performance characteristics not extensively tested

## Next Steps

- Add performance benchmarks for critical paths
- Add VM-based integration tests using QEMU
- Add end-to-end tests with actual package installation
- Add stress tests for concurrent operations

---

For detailed Phase 4 completion information, see [PHASE_4_COMPLETION.md](../docs/PHASE_4_COMPLETION.md).
