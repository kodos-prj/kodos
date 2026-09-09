"""Integration tests: validate real example configs end-to-end."""

import sys
from pathlib import Path

EXAMPLE = Path(__file__).parent.parent.parent / "example" / "testvm"


def test_example_testvm_config_is_valid():
    from kod.config.validator import validate_config
    from kod.core import load_config

    conf = load_config(str(EXAMPLE / "configuration.lua"))
    errors = validate_config(conf)
    assert errors == []


def test_broken_lua_config_catches_typo(tmp_path):
    from kod.config.validator import validate_config
    from kod.core import load_config

    bad = tmp_path / "bad.lua"
    bad.write_text('return { packges = { "git" } }\n')
    conf = load_config(str(bad))
    errors = validate_config(conf)
    assert len(errors) == 1
    assert "packges" in str(errors[0])
    assert "packages" in str(errors[0])
