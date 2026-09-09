"""Tests for the `kod config` CLI commands."""

from pathlib import Path

from click.testing import CliRunner

from kod.kod import cli

EXAMPLE = Path(__file__).parent.parent.parent / "example" / "testvm"


def test_cli_validate_accepts_example_config():
    result = CliRunner().invoke(cli, ["config", "validate", "-c", str(EXAMPLE)])
    assert result.exit_code == 0, result.output


def test_cli_validate_reports_typo(tmp_path):
    bad = tmp_path / "bad.lua"
    bad.write_text('return { packges = { "git" } }\n')
    result = CliRunner().invoke(cli, ["config", "validate", "-c", str(bad)])
    assert result.exit_code == 1
    assert "packges" in result.output
    assert "packages" in result.output
