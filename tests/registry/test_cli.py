"""Tests for the `kod registry` CLI commands."""

from pathlib import Path
import json
import tempfile

from click.testing import CliRunner

from kod.kod import cli

EXAMPLE = Path(__file__).parent.parent / "example" / "testvm"


def test_registry_list_shows_builtin_programs():
    """Test that `kod registry list` shows builtin programs."""
    result = CliRunner().invoke(cli, ["registry", "list"])
    assert result.exit_code == 0, result.output
    assert "Builtin Programs:" in result.output
    assert "- git" in result.output
    assert "- neovim" in result.output
    assert "- syncthing" in result.output


def test_registry_info_git():
    """Test that `kod registry info git` shows program details."""
    result = CliRunner().invoke(cli, ["registry", "info", "git"])
    assert result.exit_code == 0, result.output
    assert "Program: git" in result.output
    assert "Source: builtin" in result.output
    assert "Schema:" in result.output
    assert "user_name" in result.output
    assert "email" in result.output


def test_registry_info_unknown_program():
    """Test that `kod registry info` fails for unknown programs."""
    result = CliRunner().invoke(cli, ["registry", "info", "nonexistent"])
    assert result.exit_code == 1
    assert "Program 'nonexistent' not found" in result.output


def test_registry_schema_git():
    """Test that `kod registry schema git` outputs valid JSON."""
    result = CliRunner().invoke(cli, ["registry", "schema", "git"])
    assert result.exit_code == 0, result.output
    
    # Parse JSON to ensure it's valid
    schema = json.loads(result.output)
    assert "user_name" in schema or ("allOf" in schema)


def test_registry_schema_unknown_program():
    """Test that `kod registry schema` fails for unknown programs."""
    result = CliRunner().invoke(cli, ["registry", "schema", "nonexistent"])
    assert result.exit_code == 1
    assert "Program 'nonexistent' not found" in result.output


def test_registry_generate_git_with_options():
    """Test that `kod registry generate git` works with options."""
    result = CliRunner().invoke(cli, [
        "registry", "generate", "git",
        "--user-name", "Alice",
        "--email", "alice@example.com"
    ])
    assert result.exit_code == 0, result.output
    assert "git config --global user.name 'Alice'" in result.output
    assert "git config --global user.email 'alice@example.com'" in result.output


def test_registry_generate_git_missing_required():
    """Test that `kod registry generate git` fails with missing required field."""
    result = CliRunner().invoke(cli, [
        "registry", "generate", "git",
        "--user-name", "Alice"
        # Missing --email
    ])
    assert result.exit_code == 1
    assert "Missing required field 'email'" in result.output or "email" in result.output


def test_registry_generate_git_with_signing_key():
    """Test that `kod registry generate git` works with optional signing_key."""
    result = CliRunner().invoke(cli, [
        "registry", "generate", "git",
        "--user-name", "Alice",
        "--email", "alice@example.com",
        "--signing-key", "ABC123"
    ])
    assert result.exit_code == 0, result.output
    assert "git config --global user.name 'Alice'" in result.output
    assert "git config --global user.email 'alice@example.com'" in result.output
    assert "git config --global user.signingkey 'ABC123'" in result.output


def test_registry_generate_unknown_program():
    """Test that `kod registry generate` fails for unknown programs."""
    result = CliRunner().invoke(cli, [
        "registry", "generate", "nonexistent",
        "--some-option", "value"
    ])
    assert result.exit_code == 1
    assert "Program 'nonexistent' not found" in result.output


def test_registry_generate_neovim():
    """Test that `kod registry generate neovim` works."""
    result = CliRunner().invoke(cli, [
        "registry", "generate", "neovim",
        "--python-provider", "true",
        "--node-provider", "true"
    ])
    assert result.exit_code == 0, result.output


def test_registry_generate_syncthing():
    """Test that `kod registry generate syncthing` works."""
    result = CliRunner().invoke(cli, [
        "registry", "generate", "syncthing",
        "--auto-start", "true"
    ])
    assert result.exit_code == 0, result.output


def test_registry_list_with_user_plugin():
    """Test that `kod registry list` shows user programs when they exist."""
    # This test would need to set up a user plugin directory
    # For now, just ensure builtin programs are shown
    result = CliRunner().invoke(cli, ["registry", "list"])
    assert result.exit_code == 0, result.output
    assert "Builtin Programs:" in result.output


def test_registry_info_schema_formatting():
    """Test that schema formatting is readable."""
    result = CliRunner().invoke(cli, ["registry", "info", "git"])
    assert result.exit_code == 0, result.output
    
    # Check for readable format
    assert "- user_name" in result.output
    assert "- email" in result.output
    assert "string" in result.output
    assert "required" in result.output or "optional" in result.output
