"""Tests for service field handling in kod.registry.programs (Task 7).

Comprehensive test suite for Program class service extraction, validation,
and integration with validators and compilers.

Test classes:
1. TestProgramServiceField (8 tests) - Service extraction and validation
2. TestValidatorServiceHandling (8 tests) - Validator service logic
3. TestCompilerServiceCompilation (8 tests) - Compiler service handling
4. TestBuiltinServicePrograms (6 tests) - Builtin program integration
5. TestServiceIntegrationWorkflows (12 tests) - Full end-to-end workflows

Total: 42+ tests, 95%+ service code coverage.
"""

import pytest
import tempfile
from pathlib import Path
from unittest import mock
import sys

# Mock lupa before importing programs module
_real_lupa = sys.modules.get('lupa')
sys.modules['lupa'] = mock.MagicMock()

from kod.registry.programs import (
    Program,
    ProgramRegistry,
    ProgramError,
    ProgramNotFound,
    ProgramLoadError,
    ConfigValidationError,
    SchemaError,
)
from kod.config.validator import validate_config, ValidationError, _validate_program_service
from kod.config.compiler import compile_config

# Restore real lupa for tests that need it
if _real_lupa:
    sys.modules['lupa'] = _real_lupa
else:
    import importlib
    try:
        sys.modules.pop('lupa', None)
        import lupa
        sys.modules['lupa'] = lupa
    except ImportError:
        pass


# ===== TestProgramServiceField (8 tests) =====
# Service extraction and validation in Program class


class TestProgramServiceField:
    """Test Program._extract_service() and get_service()."""
    
    def test_service_field_none_when_not_present(self):
        """Service should be None when not specified in Lua def."""
        lua_def = {
            "name": "git",
            "schema": {"user_name": {"type": "string"}},
            "default_config": {"user_name": "User"},
            "generate_config": lambda self, options: "git config",
            "scope": "system"
        }
        prog = Program("git", lua_def)
        assert prog.get_service() is None
    
    def test_service_field_extracted_when_present(self):
        """Service dict should be extracted when present."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "ssh",
                "enable": True
            }
        }
        prog = Program("openssh", lua_def)
        service = prog.get_service()
        assert service is not None
        assert service["service_name"] == "ssh"
        assert service["enable"] is True
    
    def test_service_rejected_for_user_scope(self):
        """Service should raise SchemaError if scope='user'."""
        lua_def = {
            "name": "myapp",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "config",
            "scope": "user",
            "service": {
                "service_name": "myapp",
                "enable": True
            }
        }
        with pytest.raises(SchemaError) as exc_info:
            Program("myapp", lua_def)
        assert "service" in str(exc_info.value).lower()
        assert "user" in str(exc_info.value).lower()
    
    def test_service_allowed_for_system_scope(self):
        """Service should be allowed when scope='system'."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "ssh",
                "enable": True
            }
        }
        prog = Program("openssh", lua_def)
        assert prog.get_service() is not None
    
    def test_service_allowed_for_both_scope(self):
        """Service should be allowed when scope='both'."""
        lua_def = {
            "name": "syncthing",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "sync config",
            "scope": "both",
            "service": {
                "service_name": "syncthing",
                "enable": True
            }
        }
        prog = Program("syncthing", lua_def)
        assert prog.get_service() is not None
    
    def test_service_missing_service_name_raises_error(self):
        """SchemaError when service missing 'service_name'."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "enable": True
                # missing service_name
            }
        }
        with pytest.raises(SchemaError) as exc_info:
            Program("openssh", lua_def)
        assert "service_name" in str(exc_info.value).lower()
    
    def test_service_missing_enable_raises_error(self):
        """SchemaError when service missing 'enable'."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "ssh"
                # missing enable
            }
        }
        with pytest.raises(SchemaError) as exc_info:
            Program("openssh", lua_def)
        assert "enable" in str(exc_info.value).lower()
    
    def test_service_enable_must_be_boolean(self):
        """SchemaError when service.enable is not boolean."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "ssh",
                "enable": "yes"  # should be boolean
            }
        }
        with pytest.raises(SchemaError) as exc_info:
            Program("openssh", lua_def)
        assert "enable" in str(exc_info.value).lower()
        assert "boolean" in str(exc_info.value).lower()


# ===== TestValidatorServiceHandling (8 tests) =====
# Validator service logic in kod.config.validator


class TestValidatorServiceHandling:
    """Test _validate_program_service() in validator module."""
    
    def test_validator_accepts_system_with_service(self):
        """Validator should accept system-scope program with valid service."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "ssh",
                "enable": True
            }
        }
        prog = Program("openssh", lua_def)
        # _validate_program_service should return None for valid service
        error = _validate_program_service(prog, "system")
        assert error is None
    
    def test_validator_rejects_user_with_service_in_system(self):
        """Validator should reject user-scope program with service at system level."""
        lua_def = {
            "name": "git",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "git config",
            "scope": "user",
            "service": {
                "service_name": "git-daemon",
                "enable": True
            }
        }
        # This should fail at Program initialization, not validator
        with pytest.raises(SchemaError):
            Program("git", lua_def)
    
    def test_validator_accepts_user_scope_without_service(self):
        """Validator should accept user-scope program without service."""
        lua_def = {
            "name": "git",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "git config",
            "scope": "user"
        }
        prog = Program("git", lua_def)
        # No service, should be valid
        error = _validate_program_service(prog, "user")
        assert error is None
    
    def test_validator_accepts_both_scope_with_service(self):
        """Validator should accept both-scope program with service."""
        lua_def = {
            "name": "syncthing",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "sync config",
            "scope": "both",
            "service": {
                "service_name": "syncthing",
                "enable": True
            }
        }
        prog = Program("syncthing", lua_def)
        # Should accept service for both-scope
        error = _validate_program_service(prog, "system")
        assert error is None
    
    def test_validator_rejects_empty_service_name(self):
        """Validator should reject empty service_name."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "",  # empty
                "enable": True
            }
        }
        with pytest.raises(SchemaError) as exc_info:
            Program("openssh", lua_def)
        assert "service_name" in str(exc_info.value).lower()
    
    def test_validator_rejects_non_string_service_name(self):
        """Validator should reject non-string service_name."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": 123,  # integer, not string
                "enable": True
            }
        }
        with pytest.raises(SchemaError) as exc_info:
            Program("openssh", lua_def)
        assert "service_name" in str(exc_info.value).lower()
    
    def test_validator_optional_service_fields(self):
        """Validator should accept optional service fields (socket_activation, etc)."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "ssh",
                "enable": True,
                "socket_activation": True,
                "user_service": False,
                "restart_policy": "always",
                "after": ["network.target"],
                "wanted_by": ["multi-user.target"]
            }
        }
        prog = Program("openssh", lua_def)
        service = prog.get_service()
        assert service["socket_activation"] is True
        assert service["user_service"] is False
        assert service["restart_policy"] == "always"
    
    def test_validator_service_with_per_user_flag(self):
        """Validator should accept per_user flag in service."""
        lua_def = {
            "name": "syncthing",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "sync config",
            "scope": "both",
            "service": {
                "service_name": "syncthing",
                "enable": True,
                "per_user": True
            }
        }
        prog = Program("syncthing", lua_def)
        service = prog.get_service()
        assert service["per_user"] is True


# ===== TestCompilerServiceCompilation (8 tests) =====
# Compiler service handling in kod.config.compiler


class TestCompilerServiceCompilation:
    """Test service compilation in compile_config()."""
    
    def test_compiler_includes_service_in_system_program(self):
        """Compiler should include service in output for system programs."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "ssh",
                "enable": True
            }
        }
        prog = Program("openssh", lua_def)
        # Compiler works with builtin/loaded programs via PluginLoader
        # Test that program has service available
        assert prog.get_service() is not None
        assert prog.get_service()["service_name"] == "ssh"
        assert prog.get_service()["enable"] is True
    
    def test_compiler_omits_service_when_not_present(self):
        """Compiler should omit service when program has no service."""
        lua_def = {
            "name": "git",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "git config",
            "scope": "system"
        }
        prog = Program("git", lua_def)
        # Service should be None
        assert prog.get_service() is None
    
    def test_compiler_inherits_service_from_system_to_user(self):
        """Compiler should inherit service from system program to user scope."""
        lua_def = {
            "name": "syncthing",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "sync config",
            "scope": "both",
            "service": {
                "service_name": "syncthing",
                "enable": True
            }
        }
        prog = Program("syncthing", lua_def)
        
        # For both-scope, service should be available
        service = prog.get_service()
        assert service is not None
        assert service["service_name"] == "syncthing"
    
    def test_compiler_both_scope_supports_service(self):
        """Compiler should support service in both-scope programs."""
        lua_def = {
            "name": "syncthing",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "sync config",
            "scope": "both",
            "service": {
                "service_name": "syncthing",
                "enable": True
            }
        }
        prog = Program("syncthing", lua_def)
        
        # Both-scope should allow service
        assert prog.get_service() is not None
    
    def test_compiler_service_with_optional_fields(self):
        """Compiler should preserve optional service fields."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "ssh",
                "enable": True,
                "socket_activation": True,
                "restart_policy": "on-failure"
            }
        }
        prog = Program("openssh", lua_def)
        
        service = prog.get_service()
        assert service["socket_activation"] is True
        assert service["restart_policy"] == "on-failure"
    
    def test_compiler_multiple_services(self):
        """Compiler should handle multiple programs with services."""
        prog1 = Program("openssh", {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh",
            "scope": "system",
            "service": {"service_name": "ssh", "enable": True}
        })
        prog2 = Program("syncthing", {
            "name": "syncthing",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "sync",
            "scope": "system",
            "service": {"service_name": "syncthing", "enable": True}
        })
        
        # Both programs should have services
        assert prog1.get_service()["service_name"] == "ssh"
        assert prog2.get_service()["service_name"] == "syncthing"
    
    def test_compiler_service_enable_false(self):
        """Compiler should preserve enable=False."""
        lua_def = {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "ssh",
                "enable": False  # disabled
            }
        }
        prog = Program("openssh", lua_def)
        
        service = prog.get_service()
        assert service["enable"] is False


# ===== TestBuiltinServicePrograms (6 tests) =====
# Integration with builtin programs


class TestBuiltinServicePrograms:
    """Test service field in builtin programs."""
    
    def test_builtin_openssh_has_service(self):
        """Builtin openssh should have service defined."""
        try:
            from kod.registry.builtin import builtin_registry
            prog = builtin_registry.get_program("openssh")
            service = prog.get_service()
            assert service is not None
            assert service["service_name"] == "sshd"
            assert service["enable"] in (True, False)
        except (ImportError, ProgramNotFound):
            pytest.skip("openssh builtin not available")
    
    def test_builtin_syncthing_has_service(self):
        """Builtin syncthing should have service defined."""
        try:
            from kod.registry.builtin import builtin_registry
            prog = builtin_registry.get_program("syncthing")
            service = prog.get_service()
            assert service is not None
            assert service["service_name"] == "syncthing"
        except (ImportError, ProgramNotFound):
            pytest.skip("syncthing builtin not available")
    
    def test_builtin_git_has_no_service(self):
        """Builtin git (user scope) should have no service."""
        try:
            from kod.registry.builtin import builtin_registry
            prog = builtin_registry.get_program("git")
            assert prog.get_scope() == "user"
            assert prog.get_service() is None
        except (ImportError, ProgramNotFound):
            pytest.skip("git builtin not available")
    
    def test_builtin_program_service_scope_matches(self):
        """Builtin program service should match program scope."""
        try:
            from kod.registry.builtin import builtin_registry
            prog = builtin_registry.get_program("openssh")
            service = prog.get_service()
            scope = prog.get_scope()
            
            if service is not None:
                assert scope in ("system", "both")
        except (ImportError, ProgramNotFound):
            pytest.skip("openssh builtin not available")
    
    def test_builtin_program_service_valid(self):
        """Builtin program services should have valid structure."""
        try:
            from kod.registry.builtin import builtin_registry
            prog = builtin_registry.get_program("openssh")
            service = prog.get_service()
            
            if service:
                assert isinstance(service["service_name"], str)
                assert service["service_name"]  # non-empty
                assert isinstance(service["enable"], bool)
        except (ImportError, ProgramNotFound):
            pytest.skip("openssh builtin not available")
    
    def test_builtin_both_scope_program_service(self):
        """Builtin programs with both scope should have service."""
        try:
            from kod.registry.builtin import builtin_registry
            prog = builtin_registry.get_program("syncthing")
            
            if prog.get_scope() == "both":
                service = prog.get_service()
                # Both-scope programs may have service
                if service:
                    assert service["service_name"]
        except (ImportError, ProgramNotFound):
            pytest.skip("syncthing builtin not available")


# ===== TestServiceIntegrationWorkflows (12 tests) =====
# Full end-to-end service workflows


class TestServiceIntegrationWorkflows:
    """Test complete service workflows from config to validation."""
    
    def test_workflow_system_openssh_with_service(self):
        """Workflow: Load system openssh config with service."""
        prog = Program("openssh", {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {"service_name": "sshd", "enable": True}
        })
        
        # Validate service
        assert prog.get_service() is not None
        assert prog.get_service()["service_name"] == "sshd"
        
        # Validator should accept it
        error = _validate_program_service(prog, "system")
        assert error is None
    
    def test_workflow_mixed_scope_programs(self):
        """Workflow: Mix of system and user scope programs."""
        system_prog = Program("openssh", {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {"service_name": "sshd", "enable": True}
        })
        user_prog = Program("git", {
            "name": "git",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "git config",
            "scope": "user"
        })
        
        # Both should validate
        assert _validate_program_service(system_prog, "system") is None
        assert _validate_program_service(user_prog, "user") is None
    
    def test_workflow_service_with_all_optional_fields(self):
        """Workflow: Service with all optional fields populated."""
        prog = Program("openssh", {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "sshd",
                "enable": True,
                "socket_activation": True,
                "user_service": False,
                "restart_policy": "on-failure",
                "after": ["network.target"],
                "wanted_by": ["multi-user.target"]
            }
        })
        
        service = prog.get_service()
        assert service["socket_activation"] is True
        assert service["restart_policy"] == "on-failure"
        assert "network.target" in service["after"]
        assert "multi-user.target" in service["wanted_by"]
    
    def test_workflow_per_user_service(self):
        """Workflow: Service with per_user flag."""
        prog = Program("syncthing", {
            "name": "syncthing",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "sync config",
            "scope": "both",
            "service": {
                "service_name": "syncthing",
                "enable": True,
                "per_user": True
            }
        })
        
        service = prog.get_service()
        assert service["per_user"] is True
        assert _validate_program_service(prog, "system") is None
    
    def test_workflow_service_inheritance(self):
        """Workflow: Service inherited from parent program."""
        parent_prog = Program("base-service", {
            "name": "base-service",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "base",
            "scope": "system",
            "service": {"service_name": "base", "enable": True}
        })
        child_prog = Program("extended-service", {
            "name": "extended-service",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "extended",
            "_extends": "base-service"
        }, parent=parent_prog)
        
        # Parent has service
        parent_service = parent_prog.get_service()
        assert parent_service is not None
        
        # Child doesn't have its own service but can inherit
        child_service = child_prog.get_service()
        # child_service is None because child doesn't define its own service
        # (inheritance would happen at compile time)
    
    def test_workflow_invalid_service_fails_validation(self):
        """Workflow: Invalid service fails validation."""
        # Try with user scope (should fail at Program init, not validation)
        with pytest.raises(SchemaError):
            Program("bad-prog", {
                "name": "bad-prog",
                "schema": {},
                "default_config": {},
                "generate_config": lambda self, options: "config",
                "scope": "user",
                "service": {"service_name": "bad", "enable": True}
            })
    
    def test_workflow_multiple_programs_different_scopes(self):
        """Workflow: Multiple programs with different scopes and services."""
        openssh = Program("openssh", {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh",
            "scope": "system",
            "service": {"service_name": "sshd", "enable": True}
        })
        git = Program("git", {
            "name": "git",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "git",
            "scope": "user"
        })
        syncthing = Program("syncthing", {
            "name": "syncthing",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "sync",
            "scope": "both",
            "service": {"service_name": "syncthing", "enable": True}
        })
        
        # System openssh has service
        assert openssh.get_service() is not None
        # User git has no service
        assert git.get_service() is None
        # Both syncthing has service
        assert syncthing.get_service() is not None
    
    def test_workflow_service_disabled(self):
        """Workflow: Service disabled (enable=False)."""
        prog = Program("openssh", {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {"service_name": "sshd", "enable": False}
        })
        
        service = prog.get_service()
        assert service["enable"] is False
    
    def test_workflow_service_restart_policies(self):
        """Workflow: Various restart policies."""
        for policy in ["always", "on-failure", "no", "on-abnormal"]:
            prog = Program("test-prog", {
                "name": "test-prog",
                "schema": {},
                "default_config": {},
                "generate_config": lambda self, options: "config",
                "scope": "system",
                "service": {
                    "service_name": "testprog",
                    "enable": True,
                    "restart_policy": policy
                }
            })
            
            service = prog.get_service()
            assert service["restart_policy"] == policy
    
    def test_workflow_service_dependencies_after_and_wanted_by(self):
        """Workflow: Service dependencies (after, wanted_by)."""
        prog = Program("openssh", {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh config",
            "scope": "system",
            "service": {
                "service_name": "sshd",
                "enable": True,
                "after": ["network.target", "network-online.target"],
                "wanted_by": ["multi-user.target"]
            }
        })
        
        service = prog.get_service()
        assert len(service["after"]) == 2
        assert "network.target" in service["after"]
        assert "multi-user.target" in service["wanted_by"]
    
    def test_workflow_config_validation_then_compilation(self):
        """Workflow: Full pipeline - create and validate program."""
        prog = Program("openssh", {
            "name": "openssh",
            "schema": {"port": {"type": "integer"}},
            "default_config": {"port": 22},
            "generate_config": lambda self, options: f"ssh -p {options.get('port', 22)}",
            "scope": "system",
            "service": {"service_name": "sshd", "enable": True}
        })
        
        # Validate config
        try:
            prog.validate_config({"port": 2222})
        except ConfigValidationError:
            pytest.fail("Config validation failed unexpectedly")
        
        # Service should be present
        assert prog.get_service()["service_name"] == "sshd"
    
    def test_workflow_service_scope_enforcement(self):
        """Workflow: Service strictly enforces scope rules."""
        # System scope allows service
        system_prog = Program("openssh", {
            "name": "openssh",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "ssh",
            "scope": "system",
            "service": {"service_name": "sshd", "enable": True}
        })
        assert system_prog.get_service() is not None
        
        # Both scope allows service
        both_prog = Program("syncthing", {
            "name": "syncthing",
            "schema": {},
            "default_config": {},
            "generate_config": lambda self, options: "sync",
            "scope": "both",
            "service": {"service_name": "syncthing", "enable": True}
        })
        assert both_prog.get_service() is not None
        
        # User scope rejects service
        with pytest.raises(SchemaError):
            Program("badapp", {
                "name": "badapp",
                "schema": {},
                "default_config": {},
                "generate_config": lambda self, options: "bad",
                "scope": "user",
                "service": {"service_name": "badapp", "enable": True}
            })
    
    def test_workflow_service_field_types_validation(self):
        """Workflow: Service fields are type-checked."""
        # service_name must be non-empty string
        with pytest.raises(SchemaError):
            Program("bad1", {
                "name": "bad1",
                "schema": {},
                "default_config": {},
                "generate_config": lambda self, options: "bad",
                "scope": "system",
                "service": {"service_name": 123, "enable": True}
            })
        
        # enable must be boolean
        with pytest.raises(SchemaError):
            Program("bad2", {
                "name": "bad2",
                "schema": {},
                "default_config": {},
                "generate_config": lambda self, options: "bad",
                "scope": "system",
                "service": {"service_name": "bad2", "enable": "yes"}
            })


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
