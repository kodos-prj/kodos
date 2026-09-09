"""Configuration validation (Phase 1).

Validates a loaded Kodos configuration against the schema.
Returns a list of ValidationError objects; empty list means valid.
"""

from difflib import get_close_matches
from typing import List, Optional

from kod.config.schema import SCHEMA
from kod.exceptions import ValidationError


def _suggest(key: str) -> Optional[str]:
    match = get_close_matches(key, SCHEMA.keys(), n=1)
    if match:
        return f"Did you mean '{match[0]}'?"
    return None


def _type_ok(value, expected) -> bool:
    """Check value against expected type, handling lupa LuaTables.

    Lua has one table type; array-ness is detected from int keys 1..n.
    ponytail: empty tables are ambiguous and accepted for either type.
    """
    if isinstance(value, expected):
        return True
    if expected not in (dict, list):
        return False
    try:
        keys = list(value.keys())
    except (AttributeError, TypeError):
        return False
    if not keys:
        return True
    int_keys = all(isinstance(k, int) for k in keys)
    return int_keys if expected is list else not int_keys


def validate_config(config: dict) -> List[ValidationError]:
    errors: List[ValidationError] = []
    for key, value in config.items():
        if key not in SCHEMA:
            suggestion = _suggest(key)
            message = f"Unknown option '{key}'"
            if suggestion:
                message += f". {suggestion}"
            errors.append(ValidationError(message, location=key))
            continue
        expected = SCHEMA[key]
        if not _type_ok(value, expected):
            kind = "list" if expected is list else "table"
            errors.append(
                ValidationError(
                    f"Option '{key}' must be a {kind}, "
                    f"got {type(value).__name__}",
                    location=key,
                )
            )
    return errors
