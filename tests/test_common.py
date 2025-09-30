"""Unit tests for KodOS common module error handling functionality.

This module contains comprehensive unit tests for the enhanced exec() function
and its associated error handling mechanisms using pytest framework.
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
    exec_safe,
    exec_chroot,
    exec_with_retry,
    exec_critical,
    exec_warn,
    exec_collect_errors,
    exec_batch_with_fallback,
    CommandExecutionError,
    CommandTimeoutError,
    UnsafeCommandError,
    set_debug,
    set_verbose,
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


def test_command_execution_error():
    """Test that CommandExecutionError is raised for failed commands."""
    with pytest.raises(CommandExecutionError) as exc_info:
        exec("false", check_return_code=True)

    assert exc_info.value.return_code == 1
    assert "false" in exc_info.value.cmd


def test_command_execution_error_disabled():
    """Test that failed commands don't raise errors when check_return_code=False."""
    result = exec("false", check_return_code=False, get_output=True)
    # Should not raise an exception


def test_command_timeout():
    """Test that CommandTimeoutError is raised for commands that timeout."""
    with pytest.raises(CommandTimeoutError) as exc_info:
        exec("sleep 2", timeout=1)

    assert exc_info.value.timeout == 1
    assert "sleep 2" in exc_info.value.cmd


def test_unsafe_command_detection():
    """Test that unsafe commands are detected and blocked."""
    unsafe_commands = [
        "rm -rf /",
        "rm -rf /*",
        ";rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
    ]

    for cmd in unsafe_commands:
        with pytest.raises(UnsafeCommandError) as exc_info:
            exec(cmd, allow_unsafe=False)
        assert cmd in exc_info.value.cmd


def test_unsafe_command_allowed():
    """Test that unsafe commands can be executed when explicitly allowed."""
    result = exec("echo 'rm -rf /'", allow_unsafe=True, get_output=True)
    assert "rm -rf /" in result


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


# Test cases for the exec_safe() function


def test_safe_command_execution():
    """Test that exec_safe properly escapes arguments."""
    result = exec_safe("echo", "hello world", get_output=True)
    assert result.strip() == "hello world"


def test_safe_argument_escaping():
    """Test that exec_safe properly escapes dangerous characters."""
    result = exec_safe("echo", "hello & echo world", get_output=True)
    assert "hello & echo world" in result


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
    """Test that exec_critical raises RuntimeError on command failure."""
    with pytest.raises(RuntimeError) as exc_info:
        exec_critical("false", "Test operation failed")

    assert "Test operation failed" in str(exc_info.value)


def test_exec_warn_success():
    """Test that exec_warn works for successful commands."""
    result = exec_warn("echo 'test'", "Test warning", get_output=True)
    assert result is not None
    if result is not None:
        assert result.strip() == "test"


def test_exec_warn_failure():
    """Test that exec_warn returns None on failure and continues."""
    result = exec_warn("false", "Test warning message")
    assert result is None


def test_exec_collect_errors_all_success():
    """Test exec_collect_errors when all commands succeed."""
    commands = [("echo 'test1'", "cmd1"), ("echo 'test2'", "cmd2")]
    failures = exec_collect_errors(commands)
    assert failures == []


def test_exec_collect_errors_some_failures():
    """Test exec_collect_errors when some commands fail."""
    commands = [("echo 'test1'", "cmd1"), ("false", "cmd2"), ("echo 'test3'", "cmd3"), ("false", "cmd4")]
    failures = exec_collect_errors(commands)
    assert failures == ["cmd2", "cmd4"]


def test_exec_batch_with_fallback_batch_success():
    """Test exec_batch_with_fallback when batch operation succeeds."""
    items = ["item1", "item2", "item3"]
    batch_template = "echo 'processing {items}'"
    single_template = "echo 'processing {item}'"

    failures = exec_batch_with_fallback(items, batch_template, single_template)
    assert failures == []


def test_exec_batch_with_fallback_batch_fails_individual_succeed():
    """Test exec_batch_with_fallback when batch fails but individuals succeed."""
    items = ["item1", "item2"]
    batch_template = "false"  # This will fail
    single_template = "echo 'processing {item}'"

    failures = exec_batch_with_fallback(items, batch_template, single_template)
    assert failures == []


def test_exec_batch_with_fallback_some_individual_failures():
    """Test exec_batch_with_fallback when some individual operations fail."""
    items = ["good", "error_item", "good2"]
    batch_template = "false"  # Force fallback to individual
    single_template = "test '{item}' != 'error_item'"  # This will fail for 'error_item'

    failures = exec_batch_with_fallback(items, batch_template, single_template)
    assert failures == ["error_item"]


def test_exec_batch_with_fallback_empty_items():
    """Test exec_batch_with_fallback with empty items list."""
    items = []
    batch_template = "echo 'processing {items}'"
    single_template = "echo 'processing {item}'"

    failures = exec_batch_with_fallback(items, batch_template, single_template)
    assert failures == []
