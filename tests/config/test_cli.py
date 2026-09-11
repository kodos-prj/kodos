"""Tests for the `kod config` CLI commands."""

import json
import os
import tempfile
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


def test_config_init_generates_template():
    """config init produces valid Lua syntax."""
    result = CliRunner().invoke(cli, ['config', 'init'])
    assert result.exit_code == 0, result.output
    assert 'return {' in result.output
    assert '-- ' in result.output  # Has comments
    # Verify template can be parsed
    assert 'base_distribution' in result.output


def test_config_init_distro_option():
    """config init --distro debian generates debian-specific template."""
    result = CliRunner().invoke(cli, ['config', 'init', '--distro', 'debian'])
    assert result.exit_code == 0, result.output
    assert 'Distribution: debian' in result.output


def test_config_init_output_file():
    """config init --output writes to file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        output_path = f.name
    
    try:
        result = CliRunner().invoke(cli, ['config', 'init', '--output', output_path])
        assert result.exit_code == 0, result.output
        assert os.path.exists(output_path)
        
        with open(output_path) as f:
            content = f.read()
        assert 'return {' in content
        assert 'base_distribution' in content
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_config_init_template_is_valid_lua():
    """Template can be parsed as Lua (basic check)."""
    result = CliRunner().invoke(cli, ['config', 'init'])
    assert result.exit_code == 0, result.output
    # Basic syntax checks (no brackets mismatches)
    assert result.output.count('{') == result.output.count('}')
    assert result.output.count('[') == result.output.count(']')


def test_config_init_template_all_sections():
    """Template includes all 13 sections."""
    result = CliRunner().invoke(cli, ['config', 'init'])
    assert result.exit_code == 0, result.output
    
    # Check that all schema sections are referenced
    expected_sections = [
        'base_distribution', 'repos', 'devices', 'boot', 'hardware',
        'locale', 'network', 'users', 'desktop', 'fonts', 'packages',
        'services', 'programs'
    ]
    for section in expected_sections:
        assert section in result.output, f"Section '{section}' not found in template"


def test_config_init_arch_distro():
    """config init --distro arch generates arch-specific template."""
    result = CliRunner().invoke(cli, ['config', 'init', '--distro', 'arch'])
    assert result.exit_code == 0, result.output
    assert 'Distribution: arch' in result.output


