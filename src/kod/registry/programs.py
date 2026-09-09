"""Builtin program definitions (Phase 3).

Defines standard programs with their configurations and schemas.

Programs include: git, neovim, syncthing, ssh, etc.

Key components:
- ProgramRegistry: Main registry
- Program: Program definition class
- get_program(): Lookup a program

Example:
    >>> registry = ProgramRegistry()
    >>> git_prog = registry.get_program("git")
    >>> config = git_prog.generate_config({"user_name": "Alice"})
"""

# TODO (Phase 3): Define builtin programs
#   - Create Program class with schema
#   - Implement config generator for each program
#   - Document program options
