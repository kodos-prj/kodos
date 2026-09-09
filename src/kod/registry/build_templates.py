"""Build templates for custom packages (Phase 5).

Defines standard build templates (autotools, cmake, make, python, cargo, meson).
Each template knows the build sequence and how to execute it.

Key components:
- BuildTemplate: Base template class
- AutotoolsTemplate: ./configure && make && make install
- CMakeTemplate: cmake && make && make install
- etc.

Example:
    >>> template = BuildTemplate.get("autotools")
    >>> commands = template.generate_commands(
    ...     src_dir="/tmp/hello",
    ...     build_flags=["--prefix=/usr"]
    ... )
    >>> # commands = [list of shell commands to execute]
"""

# TODO (Phase 5): Implement build templates
#   - Define template base class
#   - Implement 6 standard templates
#   - Allow custom templates via plugins
#   - Generate shell commands to execute
