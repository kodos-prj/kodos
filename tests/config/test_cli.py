"""Tests for the `kod config` CLI commands."""

import json
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


def test_config_schema_text_output():
    """config schema shows all sections in text format."""
    result = CliRunner().invoke(cli, ['config', 'schema'])
    assert result.exit_code == 0, result.output
    assert 'BOOT' in result.output
    assert 'LOCALE' in result.output
    assert 'Example:' in result.output
    assert 'Fields:' in result.output


def test_config_schema_filter_section():
    """config schema --section shows only requested section."""
    result = CliRunner().invoke(cli, ['config', 'schema', '--section', 'boot'])
    assert result.exit_code == 0, result.output
    assert 'BOOT' in result.output
    assert 'LOCALE' not in result.output
    assert 'Example:' in result.output


def test_config_schema_json_output():
    """config schema --format json outputs valid JSON."""
    result = CliRunner().invoke(cli, ['config', 'schema', '--format', 'json'])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert 'boot' in data
    assert 'description' in data['boot']
    assert 'type' in data['boot']
    assert data['boot']['type'] == 'dict'
    assert 'fields' in data['boot']


def test_config_schema_json_section_filter():
    """config schema --format json with --section shows only that section."""
    result = CliRunner().invoke(cli, ['config', 'schema', '--section', 'boot', '--format', 'json'])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert list(data.keys()) == ['boot']
    assert 'description' in data['boot']


def test_config_schema_invalid_section():
    """config schema --section with invalid name shows error."""
    result = CliRunner().invoke(cli, ['config', 'schema', '--section', 'invalid_section_xyz'])
    assert result.exit_code != 0
    assert 'not found' in result.output or 'invalid' in result.output.lower()

