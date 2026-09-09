"""Installation workflow (Phase 2).

Main entry point for `kod install` command.
Orchestrates: partition, filesystem setup, package installation, users, services.

Key components:
- InstallWorkflow: Main class
- execute(): Run full installation

Example:
    >>> workflow = InstallWorkflow(plan, config)
    >>> workflow.execute()
"""

# TODO (Phase 2): Refactor installation from core.py
#   - Extract install logic from core.py
#   - Use new module structure (packages, services, users, boot, fs)
#   - Implement error handling with exceptions (not global problems list)
#   - Add progress reporting
