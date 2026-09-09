"""Top-level configuration schema (Phase 1).

Maps each valid top-level config option to its expected type.
"""

SCHEMA = {
    "base_distribution": str,
    "repos": dict,
    "devices": dict,
    "boot": dict,
    "hardware": dict,
    "locale": dict,
    "network": dict,
    "users": dict,
    "desktop": dict,
    "fonts": dict,
    "packages": list,
    "services": dict,
}
