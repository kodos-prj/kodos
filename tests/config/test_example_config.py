"""Integration tests: validate real example configs end-to-end."""

from pathlib import Path

EXAMPLE = Path(__file__).parent.parent.parent / "example" / "testvm"


def test_example_testvm_config_is_valid():
    from kod.config.loader import load_config_lua as load_config
    from kod.config.validator import validate_config

    conf = load_config(str(EXAMPLE / "configuration.lua"))
    errors = validate_config(conf)
    assert errors == []


def test_broken_lua_config_catches_typo(tmp_path):
    from kod.config.loader import load_config_lua as load_config
    from kod.config.validator import validate_config

    bad = tmp_path / "bad.lua"
    bad.write_text('return { packges = { "git" } }\n')
    conf = load_config(str(bad))
    errors = validate_config(conf)
    typo_errors = [e for e in errors if "packges" in str(e)]
    assert len(typo_errors) == 1
    assert "packages" in str(typo_errors[0])
