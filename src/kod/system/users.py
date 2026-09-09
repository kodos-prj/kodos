"""User account management (Phase 2).

Handles creation, modification, and configuration of user accounts.
Low-level user operations: create users, set shells, manage groups.

Note: Distinguished from kod/core/user_config.py which handles user-specific
configuration generation (dotfiles, programs, services).

Key components:
- UserManager: Main class for user account operations
- create_user(): Create a user account
- configure_user(): Apply configuration to existing user
- delete_user(): Remove user account

Example:
    >>> manager = UserManager(root_path="/mnt/newroot")
    >>> manager.create_user("alice", shell="/bin/bash", groups=["wheel"])
    >>> manager.configure_user("alice", home_dotfiles={...})
"""

# TODO (Phase 2): Implement user account management
#   - Extract from core.py: create_user(), create_kod_user()
#   - Create UserManager class
#   - Support chroot operations
#   - Handle group membership
#   - Manage shell selection
#   - Use structured exceptions
