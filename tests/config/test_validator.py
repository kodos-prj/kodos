"""Tests for kod.config.validator."""

from kod.config.validator import validate_config


def test_valid_minimal_config_passes():
    errors = validate_config({"packages": ["git", "htop"]})
    assert errors == []


def test_empty_config_passes():
    errors = validate_config({})
    assert errors == []


def test_unknown_top_level_key_is_flagged_with_suggestion():
    errors = validate_config({"packges": ["git"]})  # typo of "packages"
    assert len(errors) == 1
    message = str(errors[0])
    assert "packges" in message
    assert "packages" in message


def test_wrong_type_is_flagged():
    errors = validate_config({"packages": "git"})  # should be a list
    assert len(errors) == 1
    assert "packages" in str(errors[0])


def test_multiple_errors_all_reported():
    errors = validate_config({"packges": ["git"], "servics": {}})
    assert len(errors) == 2


class FakeLuaTable:
    """Mimics lupa _LuaTable: mapping with keys(), not a dict or list."""

    def __init__(self, data):
        self._data = data

    def keys(self):
        return list(self._data.keys())

    def items(self):
        return self._data.items()


def test_lua_table_array_passes_for_list_option():
    config = {"packages": FakeLuaTable({1: "git", 2: "htop"})}
    errors = validate_config(config)
    assert errors == []


def test_lua_table_hash_fails_for_list_option():
    config = {"packages": FakeLuaTable({"foo": "bar"})}
    errors = validate_config(config)
    assert len(errors) == 1


def test_lua_table_top_level_keys_checked():
    config = FakeLuaTable({"packges": {}})
    errors = validate_config(config)
    assert len(errors) == 1


def test_base_distribution_accepted():
    errors = validate_config({"base_distribution": "arch"})
    assert errors == []
