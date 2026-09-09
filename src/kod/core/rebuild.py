"""Rebuild workflow orchestration (Phase 2).

Manages system snapshots (generations), updates, and rollback.

Workflow flow:
1. Get current generation
2. Create snapshot of current system
3. Prepare next generation
4. Update packages
5. Commit or rollback based on success
"""

from typing import Any

from kod._core import (
    create_next_generation as _create_next_generation,
    get_generation as _get_generation,
    get_max_generation as _get_max_generation,
)
from kod.system.packages import update_all_packages as _update_all_packages


def create_next_generation(boot_part: str, root_part: str, generation: int) -> str:
    """Create next generation snapshot.
    
    Wrapper for kod.core.create_next_generation().
    """
    return _create_next_generation(boot_part, root_part, generation)


def get_generation(mount_point: str) -> int:
    """Get current generation number.
    
    Wrapper for kod.core.get_generation().
    """
    return _get_generation(mount_point)


def get_max_generation() -> int:
    """Get maximum generation number.
    
    Wrapper for kod.core.get_max_generation().
    """
    return _get_max_generation()
