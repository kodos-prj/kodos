"""Execution context for command operations.

Provides the Context class for executing commands in a specific environment,
tracking user and mount point information for system operations.
"""

import os
from kod.common import exec, exec_chroot


class Context:
    """Context class for executing commands in a specific environment.

    This class represents the context in which commands are executed. It stores
    information about the user, mount point, and execution stage used to execute commands.
    
    The stage parameter and use_chroot flag control behavior:
    
    Stages:
    - "install": Fresh installation (always uses chroot to new generation)
    - "rebuild": System rebuild with two modes:
      - new_generation=True: Create new generation snapshot, use chroot to it
      - new_generation=False: Reuse current system, no chroot (run directly)
    - "rebuild-user": User-level rebuild operations after swap (never uses chroot)
    """

    user: str
    mount_point: str
    use_chroot: bool
    stage: str

    def __init__(self, user: str, mount_point: str = "/mnt", use_chroot: bool = True, stage: str = "install") -> None:
        """Initialize the Context object.

        Parameters
        ----------
        user : str
            The user name to use for executing commands.
        mount_point : str
            The mount point of the root filesystem to use for executing commands.
            Defaults to "/mnt".
        use_chroot : bool
            If True, commands will be executed using chroot into mount_point.
            Defaults to True. In rebuild mode:
            - new_generation=True: use_chroot=True (execute in new snapshot)
            - new_generation=False: use_chroot=False (execute on current system)
        stage : str
            The execution stage. Valid values:
            - "install": Fresh installation (uses chroot=True)
            - "rebuild": System rebuild with two modes:
              - new_generation=True: use_chroot=True (snapshot-based rebuild)
              - new_generation=False: use_chroot=False (in-place rebuild on current system)
            - "rebuild-user": User-level operations after rebuild (uses chroot=False)
            Used to conditionally enable user services (system/services.py:102).
            Defaults to "install".
        """
        self.user = user
        self.mount_point = mount_point
        self.use_chroot = use_chroot
        self.stage = stage

    def execute(self, command: str, get_output: bool = False) -> str:
        """Execute a command in the specified context.

        Args:
            command (str): The command to execute.
            get_output (bool): Whether to return command output. Defaults to False.

        Returns:
            str: Command output if get_output=True, empty string otherwise.
        """
        if self.user == os.environ["USER"]:
            exec_prefix = ""
        else:
            exec_prefix = f" su {self.user} -c "

        def wrap(s: str) -> str:
            if self.user == os.environ["USER"]:
                return s
            else:
                return f"'{s}'"

        print(f"[Contex] Command: {command}")
        if self.use_chroot:
            print(f"##> {exec_prefix} {wrap(command)}")
            result = exec_chroot(f"{exec_prefix} {wrap(command)}", mount_point=self.mount_point, get_output=get_output)
        else:
            result = exec(f"{exec_prefix} {wrap(command)}", get_output=get_output)

        if get_output:
            return result
        else:
            return ""
