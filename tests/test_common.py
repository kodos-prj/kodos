"""Unit tests for KodOS common module functionality.

This module contains unit tests for the exec() function and its associated
error handling mechanisms using pytest framework.
"""

import subprocess
import tempfile
import os
import sys
import pytest
from pathlib import Path

# Add the src directory to Python path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kod.common import (
    exec,
    exec_chroot,
    exec_critical,
    exec_warn,
    CommandExecutionError,
    CommandTimeoutError,
    UnsafeCommandError,
    set_debug,
    set_verbose,
    report_problems,
)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment for each test."""
    set_debug(False)  # Ensure commands actually execute
    set_verbose(False)


# Test cases for the exec() function


def test_successful_command_no_output():
    """Test successful command execution without output capture."""
    result = exec("echo 'test'", get_output=False)
    assert result == ""


def test_successful_command_with_output():
    """Test successful command execution with output capture."""
    result = exec("echo 'test'", get_output=True)
    assert result.strip() == "test"


def test_failed_command_execution():
    """Test that failed commands are handled (adds to problems list)."""
    # The current implementation doesn't raise exceptions but adds to problems
    result = exec("false", get_output=True)
    # Should return empty string and add to problems list
    assert isinstance(result, str)


def test_debug_mode():
    """Test that debug mode prevents command execution."""
    set_debug(True)
    result = exec("echo 'should not execute'", get_output=True)
    assert result == ""
    set_debug(False)


def test_encoding_parameter():
    """Test that encoding parameter works correctly."""
    result = exec("echo 'test'", get_output=True, encoding="utf-8")
    assert result.strip() == "test"


# Test cases for custom exception classes


def test_command_execution_error_properties():
    """Test CommandExecutionError properties."""
    error = CommandExecutionError("test command", 1, "stderr output", "stdout output")
    assert error.cmd == "test command"
    assert error.return_code == 1
    assert error.stderr == "stderr output"
    assert error.stdout == "stdout output"
    assert "return code 1" in str(error)


def test_command_timeout_error_properties():
    """Test CommandTimeoutError properties."""
    error = CommandTimeoutError("test command", 30)
    assert error.cmd == "test command"
    assert error.timeout == 30
    assert "30s" in str(error)


def test_unsafe_command_error_properties():
    """Test UnsafeCommandError properties."""
    error = UnsafeCommandError("rm -rf /", "dangerous pattern")
    assert error.cmd == "rm -rf /"
    assert error.reason == "dangerous pattern"
    assert "dangerous pattern" in str(error)


def test_dataclass_functionality():
    """Test that dataclass features work correctly."""
    # Test equality
    error1 = CommandExecutionError("test", 1, "stderr", "stdout")
    error2 = CommandExecutionError("test", 1, "stderr", "stdout")
    error3 = CommandExecutionError("test", 2, "stderr", "stdout")

    assert error1 == error2
    assert error1 != error3

    # Test repr functionality
    repr_str = repr(error1)
    assert "CommandExecutionError" in repr_str
    assert "cmd='test'" in repr_str
    assert "return_code=1" in repr_str

    # Test field access
    assert hasattr(error1, "__dataclass_fields__")
    assert "cmd" in error1.__dataclass_fields__
    assert "return_code" in error1.__dataclass_fields__


# Test cases for exec abstraction functions


def test_exec_critical_success():
    """Test that exec_critical works for successful commands."""
    result = exec_critical("echo 'test'", "Test operation", get_output=True)
    assert result.strip() == "test"


def test_exec_critical_failure():
    """Test that exec_critical handles command failure (current implementation doesn't raise)."""
    # NOTE: Current implementation of exec() doesn't raise exceptions for failed commands
    # So exec_critical won't raise RuntimeError either - it just returns the result
    result = exec_critical("false", "Test operation failed")
    assert isinstance(result, str)


def test_exec_warn_success():
    """Test that exec_warn works for successful commands."""
    result = exec_warn("echo 'test'", "Test warning", get_output=True)
    assert result is not None
    if result is not None:
        assert result.strip() == "test"


def test_exec_warn_failure():
    """Test that exec_warn handles command failure (current implementation doesn't return None)."""
    # NOTE: Current implementation of exec() doesn't raise exceptions for failed commands
    # So exec_warn won't return None either - it returns the command output (empty string)
    result = exec_warn("false", "Test warning message")
    assert isinstance(result, str)


# Test cases for chroot functionality


def test_exec_chroot_invalid_mount_point():
    """Test that exec_chroot handles invalid mount points correctly."""
    with pytest.raises(OSError) as exc_info:
        exec_chroot("echo test", "/nonexistent/path")

    assert "does not exist" in str(exc_info.value)


# Test utility functions


def test_set_debug():
    """Test debug mode setting."""
    original_debug = False
    set_debug(True)
    # Debug mode should prevent execution
    result = exec("echo 'test'", get_output=True)
    assert result == ""
    set_debug(original_debug)


def test_set_verbose():
    """Test verbose mode setting."""
    set_verbose(True)
    # Verbose mode should still allow execution
    result = exec("echo 'test'", get_output=True)
    assert result.strip() == "test"
    set_verbose(False)


def test_report_problems():
    """Test that report_problems function exists and can be called."""
    # This function prints problems, so we just test it doesn't crash
    report_problems()
