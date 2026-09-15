"""Unit tests for kod.hooks hook collection (VALID_HOOKS, collect_hooks)."""

import pytest
from kod.hooks import VALID_HOOKS, collect_hooks, ValidationError


def test_valid_hooks_set():
    """VALID_HOOKS contains all spec §7 hook names."""
    expected = {
        "pre:package", "post:package",
        "pre:service", "post:service",
        "pre:program", "post:program",
        "pre:user", "post:user",
    }
    assert VALID_HOOKS == expected


def test_collect_hooks_from_programs():
    """collect_hooks extracts hooks from program definitions."""
    mock_post_service_fn = lambda step, ctx: None
    mock_pre_package_fn = lambda step, ctx: None

    programs = {
        "nginx": {
            "hooks": {
                "post:service": mock_post_service_fn,
            }
        },
        "git": {
            "hooks": {
                "pre:package": mock_pre_package_fn,
            }
        },
    }

    hooks = collect_hooks(programs)

    assert "post:service" in hooks
    assert mock_post_service_fn in hooks["post:service"]
    assert "pre:package" in hooks
    assert mock_pre_package_fn in hooks["pre:package"]


def test_collect_hooks_unknown_name_raises():
    """Unknown hook name raises ValidationError."""
    programs = {
        "bad": {
            "hooks": {
                "invalid:hook": lambda step, ctx: None,
            }
        }
    }

    with pytest.raises(ValidationError) as exc_info:
        collect_hooks(programs)

    assert "invalid:hook" in str(exc_info.value) or "unknown" in str(exc_info.value).lower()


def test_collect_hooks_no_hooks_field():
    """Programs without hooks field are skipped."""
    programs = {
        "git": {},
        "vim": {"name": "vim"},
    }

    hooks = collect_hooks(programs)
    assert len(hooks) == 0 or all(len(v) == 0 for v in hooks.values())


def test_collect_hooks_empty_programs():
    """Empty programs dict returns empty hooks."""
    hooks = collect_hooks({})
    assert len(hooks) == 0
