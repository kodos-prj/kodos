"""CLI commands for the Program Registry.

Provides four subcommands:
- kod registry list: List all available programs
- kod registry info <name>: Show program details
- kod registry schema <name>: Show program schema as JSON
- kod registry generate <name> [OPTIONS]: Generate config for a program
"""

import json
import sys
from typing import Optional, Dict, Any

import click

from kod.registry.loader import PluginLoader
from kod.registry.programs import (
    ProgramNotFound,
    ProgramLoadError,
    ConfigValidationError,
)


@click.group("registry")
def registry_group():
    """Manage programs in the Kodos registry."""
    pass


@registry_group.command("list")
def list_programs():
    """List all available programs."""
    try:
        loader = PluginLoader()
        builtin_programs = loader.discover_builtin()
        user_programs = loader.discover_user_plugins()
        
        # Show builtin programs
        if builtin_programs:
            click.echo("Builtin Programs:")
            for name in sorted(builtin_programs.keys()):
                click.echo(f"  - {name}")
        
        # Show user programs
        if user_programs:
            click.echo("\nUser Programs:")
            for name in sorted(user_programs.keys()):
                # Check if extends a builtin
                if name in builtin_programs:
                    click.echo(f"  - {name} (extends builtin)")
                else:
                    click.echo(f"  - {name}")
        
        if not builtin_programs and not user_programs:
            click.echo("No programs found.")
    
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@registry_group.command("info")
@click.argument("name")
def info_program(name: str):
    """Show detailed information about a program."""
    try:
        loader = PluginLoader()
        
        # Try to load the program
        try:
            program = loader.load_program(name)
        except ProgramNotFound:
            builtin = loader.discover_builtin()
            user = loader.discover_user_plugins()
            available = sorted(set(builtin.keys()) | set(user.keys()))
            click.echo(f"Error: Program '{name}' not found.", err=True)
            if available:
                click.echo(f"Available programs: {', '.join(available)}", err=True)
            sys.exit(1)
        
        # Determine source
        builtin = loader.discover_builtin()
        user = loader.discover_user_plugins()
        if name in user and name in builtin:
            source = "merged (builtin + user)"
        elif name in user:
            source = "user"
        else:
            source = "builtin"
        
        # Show basic info
        click.echo(f"Program: {name}")
        click.echo(f"Source: {source}")
        
        # Show parent if present
        if program.parent:
            click.echo(f"Parent: {program.parent.name}")
        
        # Show schema
        click.echo("\nSchema:")
        from kod.registry.programs import Program as ProgramClass
        schema = program.get_schema()
        schema_dict = ProgramClass._lua_to_dict(schema)
        _display_schema(schema_dict, indent=2)
        
        # Show default config
        default_config_raw = program.lua_def.get("default_config", {})
        default_config = ProgramClass._lua_to_dict(default_config_raw)
        if default_config:
            click.echo("\nDefault Config:")
            for key, value in default_config.items():
                click.echo(f"  {key}: {value}")
    
    except ProgramLoadError as e:
        click.echo(f"Error loading program: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _display_schema(schema: Dict[str, Any], indent: int = 0) -> None:
    """Display schema in a readable format."""
    from kod.registry.programs import Program as ProgramClass
    
    prefix = " " * indent
    
    # Convert Lua tables to dicts
    schema = ProgramClass._lua_to_dict(schema)
    
    # Handle allOf (merged schema from inheritance)
    if isinstance(schema, dict) and "allOf" in schema:
        for sub_schema in schema["allOf"]:
            _display_schema(sub_schema, indent)
        return
    
    # Handle normal schema
    if isinstance(schema, dict):
        properties = schema.get("properties", schema)
        if not isinstance(properties, dict):
            return
        
        for field_name, field_schema in properties.items():
            if field_name.startswith("$") or field_name in ("properties", "allOf", "type"):
                continue
            
            if not isinstance(field_schema, dict):
                continue
            
            # Build field display
            field_type = field_schema.get("type", "unknown")
            is_required = field_schema.get("required", False)
            required_marker = ", required" if is_required else ", optional"
            
            field_format = field_schema.get("format")
            format_str = f", format={field_format}" if field_format else ""
            
            description = field_schema.get("description", "")
            desc_str = f" - {description}" if description else ""
            
            click.echo(f"{prefix}- {field_name} ({field_type}{required_marker}{format_str}){desc_str}")


@registry_group.command("schema")
@click.argument("name")
def schema_program(name: str):
    """Show program schema as formatted JSON."""
    try:
        loader = PluginLoader()
        
        # Try to load the program
        try:
            program = loader.load_program(name)
        except ProgramNotFound:
            builtin = loader.discover_builtin()
            user = loader.discover_user_plugins()
            available = sorted(set(builtin.keys()) | set(user.keys()))
            click.echo(f"Error: Program '{name}' not found.", err=True)
            if available:
                click.echo(f"Available programs: {', '.join(available)}", err=True)
            sys.exit(1)
        
        # Get schema and convert from Lua to dict
        from kod.registry.programs import Program as ProgramClass
        schema = program.get_schema()
        schema_dict = ProgramClass._lua_to_dict(schema)
        click.echo(json.dumps(schema_dict, indent=2))
    
    except ProgramLoadError as e:
        click.echo(f"Error loading program: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@registry_group.command("generate", context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.argument("name")
@click.pass_context
def generate_program(ctx, name: str):
    """Generate configuration for a program.
    
    Pass options as --key value pairs.
    
    Example:
        kod registry generate git --user-name "Alice" --email "alice@example.com"
    """
    try:
        loader = PluginLoader()
        
        # Try to load the program
        try:
            program = loader.load_program(name)
        except ProgramNotFound:
            builtin = loader.discover_builtin()
            user = loader.discover_user_plugins()
            available = sorted(set(builtin.keys()) | set(user.keys()))
            click.echo(f"Error: Program '{name}' not found.", err=True)
            if available:
                click.echo(f"Available programs: {', '.join(available)}", err=True)
            sys.exit(1)
        
        # Parse command-line options from remaining arguments
        parsed_options = _parse_cli_options(ctx.args)
        
        # Validate options against schema
        try:
            program.validate_config(parsed_options)
        except ConfigValidationError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        
        # Generate config
        try:
            config = program.generate_config(parsed_options)
            click.echo(config)
        except Exception as e:
            click.echo(f"Error generating config: {e}", err=True)
            sys.exit(1)
    
    except ProgramLoadError as e:
        click.echo(f"Error loading program: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _parse_cli_options(options: tuple) -> Dict[str, Any]:
    """Parse command-line options (--key value pairs).
    
    Args:
        options: Tuple of CLI arguments like ("--user-name", "Alice", "--email", "alice@example.com")
    
    Returns:
        Dict like {"user_name": "Alice", "email": "alice@example.com"}
    
    Raises:
        click.BadParameter: If options are malformed
    """
    parsed = {}
    i = 0
    while i < len(options):
        arg = options[i]
        
        # Check if it's a flag
        if not arg.startswith("--"):
            raise click.BadParameter(f"Expected option to start with --, got: {arg}")
        
        # Remove -- and convert to underscore
        key = arg[2:].replace("-", "_")
        
        # Get value
        if i + 1 < len(options) and not options[i + 1].startswith("--"):
            # Has value
            value = options[i + 1]
            
            # Try to parse as boolean
            if value.lower() in ("true", "false"):
                parsed[key] = value.lower() == "true"
            # Try to parse as number
            elif value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
                parsed[key] = int(value)
            else:
                parsed[key] = value
            
            i += 2
        else:
            # Boolean flag
            parsed[key] = True
            i += 1
    
    return parsed
