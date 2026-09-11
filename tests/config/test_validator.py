"""Tests for kod.config.validator."""

from kod.config.validator import validate_config, _validate_program_service
from kod.exceptions import ValidationError
from unittest.mock import Mock, MagicMock


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


# ===== Service Validation Tests (NEW) =====


def test_validator_service_no_service_returns_none():
    """Program without service field returns None (valid)."""
    program = Mock()
    program.name = "git"
    program.get_service.return_value = None
    
    error = _validate_program_service(program, "system")
    assert error is None


def test_validator_service_system_level_valid():
    """Service at system level with valid fields is OK."""
    program = Mock()
    program.name = "openssh"
    program.get_scope.return_value = "system"
    program.get_service.return_value = {
        "service_name": "sshd",
        "enable": True,
        "restart_policy": "always"
    }
    
    error = _validate_program_service(program, "system")
    assert error is None


def test_validator_service_system_scope_both_valid():
    """Service with scope='both' at system level is valid."""
    program = Mock()
    program.name = "syncthing"
    program.get_scope.return_value = "both"
    program.get_service.return_value = {
        "service_name": "syncthing",
        "enable": True,
        "user_service": True
    }
    
    error = _validate_program_service(program, "system")
    assert error is None


def test_validator_service_user_level_invalid():
    """Service at user level raises error."""
    program = Mock()
    program.name = "openssh"
    program.get_scope.return_value = "system"
    program.get_service.return_value = {
        "service_name": "sshd",
        "enable": True
    }
    
    error = _validate_program_service(program, "user.alice")
    assert error is not None
    assert isinstance(error, ValidationError)
    assert "openssh" in str(error)
    assert "not allowed at user level" in str(error)


def test_validator_service_user_scope_invalid():
    """Program with user scope and service raises error."""
    program = Mock()
    program.name = "git"
    program.get_scope.return_value = "user"
    program.get_service.return_value = {
        "service_name": "git",
        "enable": True
    }
    
    error = _validate_program_service(program, "system")
    assert error is not None
    assert isinstance(error, ValidationError)
    assert "git" in str(error)
    assert "scope='user'" in str(error)


def test_validator_service_missing_service_name():
    """Service without service_name field raises error."""
    program = Mock()
    program.name = "openssh"
    program.get_scope.return_value = "system"
    program.get_service.return_value = {
        "enable": True
        # Missing service_name
    }
    
    error = _validate_program_service(program, "system")
    assert error is not None
    assert isinstance(error, ValidationError)
    assert "openssh" in str(error)
    assert "service_name" in str(error)


def test_validator_service_missing_enable():
    """Service without enable field raises error."""
    program = Mock()
    program.name = "openssh"
    program.get_scope.return_value = "system"
    program.get_service.return_value = {
        "service_name": "sshd"
        # Missing enable
    }
    
    error = _validate_program_service(program, "system")
    assert error is not None
    assert isinstance(error, ValidationError)
    assert "openssh" in str(error)
    assert "enable" in str(error)


def test_validator_service_empty_service_name():
    """Service with empty service_name raises error."""
    program = Mock()
    program.name = "openssh"
    program.get_scope.return_value = "system"
    program.get_service.return_value = {
        "service_name": "",  # Empty
        "enable": True
    }
    
    error = _validate_program_service(program, "system")
    assert error is not None
    assert isinstance(error, ValidationError)
    assert "service_name" in str(error)
    assert "non-empty" in str(error)


def test_validator_service_non_boolean_enable():
    """Service with non-boolean enable raises error."""
    program = Mock()
    program.name = "openssh"
    program.get_scope.return_value = "system"
    program.get_service.return_value = {
        "service_name": "sshd",
        "enable": "yes"  # Should be boolean
    }
    
    error = _validate_program_service(program, "system")
    assert error is not None
    assert isinstance(error, ValidationError)
    assert "enable" in str(error)
    assert "boolean" in str(error)


def test_validator_service_error_message_helpful():
    """Error messages are clear and actionable."""
    program = Mock()
    program.name = "git"
    program.get_scope.return_value = "user"
    program.get_service.return_value = {
        "service_name": "git",
        "enable": True
    }
    
    error = _validate_program_service(program, "system")
    error_msg = str(error)
    
    # Should contain program name, problem, and hint
    assert "git" in error_msg
    assert "scope='user'" in error_msg
    assert ("remove service" in error_msg.lower() or "change scope" in error_msg.lower())


def test_validator_service_with_optional_fields():
    """Service with optional fields validates correctly."""
    program = Mock()
    program.name = "syncthing"
    program.get_scope.return_value = "both"
    program.get_service.return_value = {
        "service_name": "syncthing",
        "enable": True,
        "socket_activation": True,
        "user_service": True,
        "restart_policy": "always",
        "after": ["network.target"],
        "wanted_by": ["multi-user.target"]
    }
    
    error = _validate_program_service(program, "system")
    assert error is None


# ===== Phase 5b: Error Messages with Help Info =====


def test_type_error_includes_error_help():
    """Type errors include error_help from SECTION_HELP."""
    config = {"packages": {"vim": True}}  # Wrong type (dict instead of list)
    errors = validate_config(config)
    assert len(errors) > 0
    error_msg = str(errors[0])
    # Should include the error_help message from SECTION_HELP
    assert "Must be a list" in error_msg


def test_type_error_includes_description_when_no_error_help():
    """Type errors include description when error_help is not present."""
    config = {"boot": ["linux"]}  # Wrong type (list instead of dict)
    errors = validate_config(config)
    assert len(errors) > 0
    error_msg = str(errors[0])
    # Should include description
    assert "Kernel and bootloader" in error_msg or "kernel" in error_msg.lower()


def test_type_error_includes_example():
    """Type errors include examples from SECTION_HELP."""
    config = {"packages": {"vim": True}}
    errors = validate_config(config)
    assert len(errors) > 0
    error_msg = str(errors[0])
    # Should include Example
    assert "Example" in error_msg or "example" in error_msg.lower()


def test_nested_field_validation_boot_kernel():
    """Boot kernel is validated as dict."""
    config = {"boot": {"kernel": ["linux"]}}  # Wrong type
    errors = validate_config(config)
    # Should have an error for boot.kernel
    nested_errors = [e for e in errors if "boot.kernel" in str(e)]
    assert len(nested_errors) > 0


def test_nested_field_validation_boot_kernel_modules():
    """Boot kernel modules is validated as list."""
    config = {"boot": {"kernel": {"modules": "xhci_pci"}}}  # Wrong type (string instead of list)
    errors = validate_config(config)
    nested_errors = [e for e in errors if "boot.kernel.modules" in str(e)]
    assert len(nested_errors) > 0


def test_nested_field_validation_locale_timezone():
    """Locale timezone is validated as string."""
    config = {"locale": {"timezone": 123}}  # Wrong type (number instead of string)
    errors = validate_config(config)
    nested_errors = [e for e in errors if "locale.timezone" in str(e)]
    assert len(nested_errors) > 0


def test_nested_field_validation_network_ipv6():
    """Network ipv6 is validated as boolean."""
    config = {"network": {"ipv6": "yes"}}  # Wrong type (string instead of boolean)
    errors = validate_config(config)
    nested_errors = [e for e in errors if "network.ipv6" in str(e)]
    assert len(nested_errors) > 0


def test_nested_field_validation_hardware_pipewire_enable():
    """Hardware pipewire enable is validated as boolean."""
    config = {"hardware": {"pipewire": {"enable": "on"}}}  # Wrong type
    errors = validate_config(config)
    nested_errors = [e for e in errors if "hardware.pipewire.enable" in str(e)]
    assert len(nested_errors) > 0


def test_nested_field_validation_optional_fields_not_required():
    """Optional nested fields don't need to be present."""
    config = {"boot": {}}  # Empty boot section is OK
    errors = validate_config(config)
    assert len(errors) == 0


def test_nested_field_validation_unknown_fields_ignored():
    """Unknown nested fields are silently ignored."""
    config = {"boot": {"kernel": {"unknown_field": "value"}}}
    errors = validate_config(config)
    # Should not error on unknown_field
    assert len(errors) == 0


def test_backward_compatibility_valid_configs():
    """Existing valid configs still validate."""
    config = {
        "base_distribution": "arch",
        "packages": ["vim", "git"],
        "boot": {
            "kernel": {
                "package": "linux-lts",
                "modules": ["xhci_pci", "virtio_blk"],
            },
            "loader": {
                "type": "systemd-boot",
                "timeout": 10,
            },
        },
        "locale": {
            "timezone": "America/New_York",
        },
    }
    errors = validate_config(config)
    assert errors == []
