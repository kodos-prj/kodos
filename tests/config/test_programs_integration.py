"""Tests for Program Registry integration with config system (Phase 3, Task 4).

Tests the integration of Programs into:
- Config validator: validating programs section
- Config compiler: compiling programs to intermediate format
"""

import pytest
from kod.config.validator import validate_config
from kod.config.compiler import compile_config
from kod.exceptions import ValidationError


# ===== Validator Tests =====

@pytest.mark.phase3
class TestValidatorProgramsSection:
    """Test config validator with programs section."""

    def test_config_without_programs_section_passes(self):
        """Config without programs section validates fine (backward compatible)."""
        config = {"base_distribution": "arch", "packages": ["git"]}
        errors = validate_config(config)
        assert errors == []

    def test_config_with_empty_programs_section_passes(self):
        """Config with empty programs dict validates fine."""
        config = {"programs": {}}
        errors = validate_config(config)
        assert errors == []

    def test_config_with_unknown_program_reports_error(self):
        """Config with unknown program name reports clear error."""
        config = {
            "programs": {
                "nonexistent_program_xyz": {"some_option": "value"}
            }
        }
        errors = validate_config(config)
        
        # Should have exactly one error
        assert len(errors) == 1
        error = errors[0]
        
        # Error message should mention the program name
        assert "nonexistent_program_xyz" in str(error)
        assert "Unknown program" in str(error)
        
        # Error location should be programs.nonexistent_program_xyz
        assert error.location == "programs.nonexistent_program_xyz"

    def test_error_lists_available_programs(self):
        """Error message includes list of available programs."""
        config = {
            "programs": {
                "bad_program_name": {}
            }
        }
        errors = validate_config(config)
        
        assert len(errors) == 1
        error_msg = str(errors[0])
        
        # Should mention Available and list some programs
        assert "Available:" in error_msg
        # Should mention at least one builtin program
        assert any(prog in error_msg for prog in ["git", "neovim", "syncthing"])

    def test_config_with_valid_git_program_passes(self):
        """Config with valid git program options passes validation."""
        config = {
            "programs": {
                "git": {
                    "user_name": "Alice",
                    "email": "alice@example.com"
                }
            }
        }
        errors = validate_config(config)
        assert errors == []

    def test_config_with_invalid_git_program_options_fails(self):
        """Config with invalid git program options is caught."""
        config = {
            "programs": {
                "git": {
                    # Missing required field: email
                    "user_name": "Alice"
                }
            }
        }
        errors = validate_config(config)
        
        # Should have error about missing field
        assert len(errors) == 1
        error = errors[0]
        assert "git" in str(error)
        assert error.location == "programs.git"

    def test_multiple_program_errors_all_reported(self):
        """Multiple program validation errors are all collected."""
        config = {
            "programs": {
                "git": {
                    # Missing email
                    "user_name": "Alice"
                },
                "unknown_prog": {
                    "some_option": "value"
                }
            }
        }
        errors = validate_config(config)
        
        # Should have 2 errors (one for git, one for unknown_prog)
        assert len(errors) == 2
        
        # Check locations
        locations = {e.location for e in errors}
        assert "programs.git" in locations
        assert "programs.unknown_prog" in locations

    def test_programs_mixed_with_other_config_options(self):
        """Programs section integrates with other config options."""
        config = {
            "base_distribution": "arch",
            "packages": ["git", "vim"],
            "programs": {
                "git": {
                    "user_name": "Alice",
                    "email": "alice@example.com"
                }
            }
        }
        errors = validate_config(config)
        assert errors == []

    def test_programs_mixed_with_invalid_config_option(self):
        """Both config and program errors are reported together."""
        config = {
            "invalid_option": "value",  # Config error
            "programs": {
                "git": {
                    "user_name": "Alice"
                    # Missing email - program error
                }
            }
        }
        errors = validate_config(config)
        
        # Should have 2 errors
        assert len(errors) == 2
        
        # One about invalid_option, one about git
        error_msgs = [str(e) for e in errors]
        assert any("invalid_option" in msg for msg in error_msgs)
        assert any("git" in msg for msg in error_msgs)


# ===== Compiler Tests =====

@pytest.mark.phase3
class TestCompilerProgramsSection:
    """Test config compiler with programs section."""

    def test_compiler_passes_through_config_without_programs(self):
        """Compiler passes through unchanged configs without programs."""
        config = {"base_distribution": "arch", "packages": ["git"]}
        compiled = compile_config(config)
        
        # Should be unchanged (except deep copy)
        assert compiled["base_distribution"] == "arch"
        assert compiled["packages"] == ["git"]

    def test_compiler_compiles_programs_section(self):
        """Compiler transforms programs section into compiled format."""
        config = {
            "programs": {
                "git": {
                    "user_name": "Alice",
                    "email": "alice@example.com"
                }
            }
        }
        compiled = compile_config(config)
        
        # programs section should be transformed
        assert "programs" in compiled
        assert "git" in compiled["programs"]
        
        # Should have the compiled structure
        git_compiled = compiled["programs"]["git"]
        assert "program" in git_compiled  # Program object
        assert "options" in git_compiled  # User options
        assert "config" in git_compiled   # Generated config

    def test_compiled_program_has_program_object(self):
        """Compiled program includes loaded Program object."""
        config = {
            "programs": {
                "git": {
                    "user_name": "Alice",
                    "email": "alice@example.com"
                }
            }
        }
        compiled = compile_config(config)
        
        program_obj = compiled["programs"]["git"]["program"]
        
        # Should be a Program object
        from kod.registry.programs import Program
        assert isinstance(program_obj, Program)
        assert program_obj.name == "git"

    def test_compiled_program_has_generated_config(self):
        """Compiled program includes generated config string."""
        config = {
            "programs": {
                "git": {
                    "user_name": "Alice",
                    "email": "alice@example.com"
                }
            }
        }
        compiled = compile_config(config)
        
        generated_config = compiled["programs"]["git"]["config"]
        
        # Should be a string with git config commands
        assert isinstance(generated_config, str)
        assert "git config" in generated_config
        assert "Alice" in generated_config
        assert "alice@example.com" in generated_config

    def test_compiled_program_preserves_options(self):
        """Compiled program preserves original user options."""
        config = {
            "programs": {
                "git": {
                    "user_name": "Alice",
                    "email": "alice@example.com",
                    "signing_key": "ABC123"
                }
            }
        }
        compiled = compile_config(config)
        
        options = compiled["programs"]["git"]["options"]
        
        # Should have all original options
        assert options["user_name"] == "Alice"
        assert options["email"] == "alice@example.com"
        assert options["signing_key"] == "ABC123"

    def test_compiler_handles_multiple_programs(self):
        """Compiler handles multiple programs in config."""
        config = {
            "programs": {
                "git": {
                    "user_name": "Alice",
                    "email": "alice@example.com"
                },
                "neovim": {
                    "python_provider": True,
                    "node_provider": True
                }
            }
        }
        compiled = compile_config(config)
        
        # Both programs should be compiled
        assert "git" in compiled["programs"]
        assert "neovim" in compiled["programs"]
        
        # Each should have proper structure
        for prog_name in ["git", "neovim"]:
            assert "program" in compiled["programs"][prog_name]
            assert "options" in compiled["programs"][prog_name]
            assert "config" in compiled["programs"][prog_name]

    def test_compiler_with_programs_and_other_config(self):
        """Compiler handles programs mixed with other config options."""
        config = {
            "base_distribution": "arch",
            "packages": ["git", "vim"],
            "programs": {
                "git": {
                    "user_name": "Alice",
                    "email": "alice@example.com"
                }
            }
        }
        compiled = compile_config(config)
        
        # Other options should be preserved
        assert compiled["base_distribution"] == "arch"
        assert compiled["packages"] == ["git", "vim"]
        
        # Programs should be compiled
        assert "git" in compiled["programs"]
        assert "program" in compiled["programs"]["git"]

    def test_compiler_deep_copies_config(self):
        """Compiler deep copies config without mutating original."""
        original_options = {
            "user_name": "Alice",
            "email": "alice@example.com"
        }
        config = {
            "programs": {
                "git": original_options
            }
        }
        
        compiled = compile_config(config)
        
        # Original should still be dict with options
        assert isinstance(config["programs"]["git"], dict)
        assert config["programs"]["git"]["user_name"] == "Alice"
        
        # Compiled should have structured format
        assert isinstance(compiled["programs"]["git"], dict)
        assert "program" in compiled["programs"]["git"]

    def test_neovim_program_compilation(self):
        """Compiler correctly compiles neovim program."""
        config = {
            "programs": {
                "neovim": {
                    "python_provider": True,
                    "ruby_provider": False,
                    "node_provider": True
                }
            }
        }
        compiled = compile_config(config)
        
        nvim = compiled["programs"]["neovim"]
        
        # Should have proper structure
        assert "program" in nvim
        assert "options" in nvim
        assert "config" in nvim
        
        # Generated config should be string
        assert isinstance(nvim["config"], str)

    def test_syncthing_program_compilation(self):
        """Compiler correctly compiles syncthing program."""
        config = {
            "programs": {
                "syncthing": {
                    "auto_start": True,
                    "listen_address": "127.0.0.1:8384"
                }
            }
        }
        compiled = compile_config(config)
        
        syncthing = compiled["programs"]["syncthing"]
        
        # Should have proper structure
        assert "program" in syncthing
        assert "options" in syncthing
        assert "config" in syncthing
        
        # Generated config should be string with systemctl commands
        assert isinstance(syncthing["config"], str)


# ===== Integration Tests =====

@pytest.mark.phase3
class TestValidatorCompilerIntegration:
    """Test validator and compiler working together."""

    def test_full_workflow_valid_config(self):
        """Full workflow: validate then compile valid config with programs."""
        config = {
            "base_distribution": "arch",
            "programs": {
                "git": {
                    "user_name": "Bob",
                    "email": "bob@example.com"
                },
                "neovim": {
                    "python_provider": False,
                    "node_provider": True
                }
            }
        }
        
        # Step 1: Validate
        errors = validate_config(config)
        assert errors == []
        
        # Step 2: Compile
        compiled = compile_config(config)
        
        # Check result
        assert "programs" in compiled
        assert "git" in compiled["programs"]
        assert "neovim" in compiled["programs"]
        
        # Each program should have proper structure
        for prog_name in ["git", "neovim"]:
            prog = compiled["programs"][prog_name]
            assert "program" in prog
            assert "options" in prog
            assert "config" in prog

    def test_full_workflow_invalid_config(self):
        """Full workflow: validation catches errors before compilation."""
        config = {
            "programs": {
                "git": {
                    # Missing required email
                    "user_name": "Bob"
                }
            }
        }
        
        # Validation should catch error
        errors = validate_config(config)
        assert len(errors) == 1
        assert "git" in str(errors[0])
        
        # User should fix this before compiling
        # (Compiler assumes validated config)


# ===== Backward Compatibility Tests =====

@pytest.mark.phase3
class TestBackwardCompatibility:
    """Ensure Phase 3 doesn't break existing Phase 1/2 functionality."""

    def test_validator_still_validates_base_distribution(self):
        """Validator still enforces base_distribution field."""
        config = {"base_distribution": "arch"}
        errors = validate_config(config)
        assert errors == []

    def test_validator_still_rejects_wrong_types(self):
        """Validator still rejects wrong types for other fields."""
        config = {"packages": "should_be_a_list"}
        errors = validate_config(config)
        assert len(errors) == 1
        assert "packages" in str(errors[0])

    def test_compiler_still_applies_desktop_dependencies(self):
        """Compiler still resolves desktop manager dependencies."""
        config = {
            "desktop": {
                "desktop_manager": {
                    "gnome": {"enable": True}
                }
            }
        }
        compiled = compile_config(config)
        
        # GNOME should have gdm as display_manager
        gnome = compiled["desktop"]["desktop_manager"]["gnome"]
        assert gnome.get("display_manager") == "gdm"

    def test_programs_section_optional(self):
        """Programs section is completely optional."""
        config = {
            "base_distribution": "arch",
            "packages": ["git"],
            "users": {"alice": {}}
            # No programs section
        }
        
        # Should validate fine
        errors = validate_config(config)
        assert errors == []
        
        # Should compile fine
        compiled = compile_config(config)
        assert "programs" not in compiled or compiled.get("programs") == {}
