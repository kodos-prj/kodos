"""Rebuild workflow orchestration (Phase 2).

Manages system snapshots (generations), updates, and rollback.

Workflow flow:
1. Get current generation
2. Create snapshot of current system
3. Prepare next generation
4. Update packages
5. Commit or rollback based on success
"""

import glob

from kod.system.filesystem import create_next_generation as _create_next_generation
from kod.system.packages import update_all_packages as _update_all_packages


def create_next_generation(boot_part: str, root_part: str, generation: int) -> str:
    """Create next generation snapshot.
    
    Wrapper for kod.system.filesystem.create_next_generation().
    """
    return _create_next_generation(boot_part, root_part, generation)


def get_generation(mount_point: str) -> int:
    """Retrieve the generation number from a specified mount point.

    Args:
        mount_point (str): The mount point to read the generation number from.

    Returns:
        int: The generation number as an integer.
    """
    with open(f"{mount_point}/.generation", "r") as f:
        return int(f.read().strip())


def get_max_generation() -> int:
    """Retrieve the highest numbered generation directory in /kod/generations.

    If no generation directories exist, return 0.

    Returns:
        int: The highest numbered generation directory.
    """
    generations = glob.glob("/kod/generations/*")
    generations = [p.split("/")[-1] for p in generations]
    generations = [int(p) for p in generations if p != "current"]
    print(f"{generations=}")
    if generations:
        generation = max(generations)
    else:
        generation = 0
    print(f"{generation=}")
    return generation
