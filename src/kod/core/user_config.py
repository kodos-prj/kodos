"""User configuration application (Phase 2).

Handles creation, modification, and configuration of user accounts.

Key components:
- UserManager: Main class
- apply_users(): Apply user config from plan

Example:
    >>> manager = UserManager(root_path)
    >>> manager.apply_users(config.users, chroot=True)
"""

# TODO (Phase 2): Refactor user management from core.py
#   - Use structured exceptions
#   - Clean separation of concerns (create vs configure)
