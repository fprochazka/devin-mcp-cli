"""CLI entry point for Devin MCP CLI."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import click
import httpx
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

from .client import DevinMcpClient, format_tool_result, get_tools
from .config import (
    DEVIN_MCP_URL,
    ConfigError,
    OrgConfig,
    get_config_path,
    load_config,
    read_config_dict,
    save_config,
)


def unwrap_exception(exc: BaseException) -> BaseException:
    """Unwrap ExceptionGroup/BaseExceptionGroup to get the root cause."""
    while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        exc = exc.exceptions[0]
    return exc


def format_error(exc: BaseException) -> str:
    """Format an exception into a user-friendly error message."""
    exc = unwrap_exception(exc)

    # Handle common HTTP/connection errors
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 401:
            return "Authentication failed. Check your API key or run 'devin-mcp org add <name>'."
        if status == 403:
            return "Access denied. Your API key may lack required permissions, or X-Org-Id may be missing/wrong."
        if status == 404:
            return "Resource not found. The MCP server endpoint may have changed."
        if status == 429:
            return "Rate limited. Please wait before making more requests."
        if status >= 500:
            return f"Devin server error ({status}). Try again later."
        return f"HTTP error {status}: {exc.response.text[:200] if exc.response.text else 'No details'}"

    if isinstance(exc, httpx.ConnectError):
        return "Connection failed. Check your internet connection or Devin server status."

    if isinstance(exc, httpx.TimeoutException):
        return "Request timed out. The server may be slow or unresponsive."

    if isinstance(exc, asyncio.TimeoutError):
        return "Operation timed out. Try increasing the timeout in your config."

    # Handle ExceptionGroup with multiple exceptions
    if isinstance(exc, BaseExceptionGroup):
        messages = [format_error(e) for e in exc.exceptions]
        return "; ".join(messages)

    # Default: use the exception message
    msg = str(exc)
    if not msg or msg == str(type(exc).__name__):
        return f"{type(exc).__name__}"
    return msg


console = Console()
error_console = Console(stderr=True)


def mask_key(api_key: str | None) -> str:
    """Mask an API key for display, keeping the ``cog_`` prefix and last 4 chars."""
    if not api_key:
        return "(not set)"
    tail = api_key[-4:]
    if api_key.startswith("cog_"):
        return f"cog_...{tail}"
    return f"***{tail}"


def _argv_option_value(names: tuple[str, ...]) -> str | None:
    """Read a global option's value straight from ``sys.argv``.

    Click resolves subcommands during argument parsing, before the group
    callback populates ``ctx.obj``. The dynamic tool fetch runs at that point, so
    it must read ``--org`` / ``--config`` from argv (and env) itself.
    """
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        for name in names:
            if arg == name:
                return argv[i + 1] if i + 1 < len(argv) else None
            if arg.startswith(f"{name}="):
                return arg[len(name) + 1 :]
    return None


def _effective_selection(ctx: click.Context) -> tuple[Path | None, str | None]:
    """Resolve the config path and account name from context, argv, then env.

    A flag beats the env var. The context wins once the group callback has run.
    """
    obj = ctx.obj or {}

    config_path = obj.get("config_path")
    if config_path is None:
        raw = _argv_option_value(("-c", "--config")) or os.getenv("DEVIN_MCP_CONFIG")
        config_path = Path(raw) if raw else None

    org_name = obj.get("org_name")
    if org_name is None:
        org_name = _argv_option_value(("-o", "--org")) or os.getenv("DEVIN_ORG")

    return config_path, org_name


def resolve_config_path(ctx: click.Context) -> Path:
    """Get the config path from the context, or the default location."""
    config_path, _ = _effective_selection(ctx)
    return config_path or get_config_path()


def resolve_org(ctx: click.Context) -> OrgConfig:
    """Resolve the selected account, raising on failure."""
    config_path, org_name = _effective_selection(ctx)
    config = load_config(config_path)
    return config.get_org(org_name)


def json_type_to_click_type(json_type: str | list | None) -> click.ParamType:
    """Convert JSON schema type to Click type."""
    if json_type is None:
        return click.STRING

    if isinstance(json_type, list):
        # Handle nullable types like ["string", "null"]
        non_null_types = [t for t in json_type if t != "null"]
        if non_null_types:
            json_type = non_null_types[0]
        else:
            return click.STRING

    type_map = {
        "string": click.STRING,
        "integer": click.INT,
        "number": click.FLOAT,
        "boolean": click.BOOL,
    }
    return type_map.get(json_type, click.STRING)


def parse_value(value: str, json_type: str | list | None) -> Any:
    """Parse a string value according to JSON schema type."""
    if value is None:
        return None

    # Handle arrays and objects - parse as JSON
    if isinstance(json_type, str) and json_type in ("array", "object"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    # Handle nullable types
    if isinstance(json_type, list):
        non_null_types = [t for t in json_type if t != "null"]
        if non_null_types:
            json_type = non_null_types[0]

    if json_type == "boolean":
        return value.lower() in ("true", "1", "yes")
    if json_type == "integer":
        return int(value)
    if json_type == "number":
        return float(value)

    return value


class DynamicGroup(click.Group):
    """A Click group that dynamically loads commands from MCP tools."""

    STATIC_COMMANDS = {"init", "config", "org"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tools_cache: dict[str, Any] | None = None

    def _resolve_org(self, ctx: click.Context) -> OrgConfig | None:
        """Resolve the selected account, returning None if none is available.

        Command building must degrade gracefully. A missing key or config never
        raises here, so static commands stay listed.
        """
        try:
            return resolve_org(ctx)
        except Exception:
            return None

    def _fetch_tools(self, ctx: click.Context) -> dict[str, dict[str, Any]]:
        """Get tools as a dict keyed by name."""
        if self._tools_cache is not None:
            return self._tools_cache

        org = self._resolve_org(ctx)
        if org is None:
            return {}

        config_path, _ = _effective_selection(ctx)
        try:
            config = load_config(config_path)
            tools = get_tools(org, config.mcp_server)
        except BaseException as e:
            error_console.print(f"[red]Error fetching tools: {format_error(e)}[/red]")
            error_console.print("[dim]Using cached tools if available, or run with -v for details.[/dim]")
            return {}

        self._tools_cache = {t["name"]: t for t in tools}
        return self._tools_cache

    def list_commands(self, ctx: click.Context) -> list[str]:
        """List all available commands."""
        static_commands = list(self.STATIC_COMMANDS)
        try:
            tools = self._fetch_tools(ctx)
            tool_commands = list(tools.keys())
            return sorted(set(static_commands + tool_commands))
        except Exception:
            return sorted(static_commands)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Get a command by name."""
        # Check static commands first
        if cmd_name in self.commands:
            return self.commands[cmd_name]

        # Try to get dynamic command from MCP tools
        try:
            tools = self._fetch_tools(ctx)
            if cmd_name in tools:
                return self._create_tool_command(tools[cmd_name])
        except Exception:
            pass

        return None

    def _create_tool_command(self, tool: dict[str, Any]) -> click.Command:
        """Create a Click command from an MCP tool dict."""
        params = []
        schema = tool.get("inputSchema") or {}
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        # Map from Click's lowercased param name back to original MCP property name
        param_name_map = {}

        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get("type")
            prop_desc = prop_def.get("description", "")
            default = prop_def.get("default")
            is_required = prop_name in required

            # Handle array and object types as JSON strings
            click_type = click.STRING if prop_type in ("array", "object") else json_type_to_click_type(prop_type)

            # For array/object defaults, serialize to JSON string for CLI display
            cli_default = None
            if default is not None and prop_type in ("array", "object"):
                cli_default = json.dumps(default)
            elif default is not None:
                cli_default = default

            # Click lowercases parameter names, so we need to map back
            cli_param_name = prop_name.replace("_", "-")
            click_internal_name = cli_param_name.replace("-", "_").lower()
            param_name_map[click_internal_name] = prop_name

            # Create option
            option = click.Option(
                param_decls=[f"--{cli_param_name}"],
                type=click_type,
                required=is_required and default is None,
                default=cli_default,
                help=prop_desc[:200] if prop_desc else None,  # Truncate long descriptions
            )
            params.append(option)

        # Add output format option
        params.append(
            click.Option(
                param_decls=["--json", "as_json"],
                is_flag=True,
                default=False,
                help="Output raw JSON",
            )
        )

        def make_callback(tool_name: str, prop_defs: dict, name_map: dict):
            @click.pass_context
            def callback(ctx: click.Context, **kwargs):
                as_json = kwargs.pop("as_json", False)
                verbose = ctx.obj.get("verbose", False) if ctx.obj else False

                # Parse values according to their types
                arguments = {}
                for key, value in kwargs.items():
                    if value is not None:
                        # Map Click's lowercased param name back to original MCP property name
                        original_key = name_map.get(key, key)
                        prop_type = prop_defs.get(original_key, {}).get("type")
                        if prop_type in ("array", "object"):
                            arguments[original_key] = parse_value(str(value), prop_type)
                        else:
                            arguments[original_key] = value

                try:
                    org = resolve_org(ctx)
                    config_path, _ = _effective_selection(ctx)
                    config = load_config(config_path)
                except ConfigError as e:
                    error_console.print(f"[red]{e}[/red]")
                    sys.exit(1)

                async def _call():
                    client = DevinMcpClient(org, config.mcp_server)
                    async with client.connect():
                        return await client.call_tool(tool_name, arguments)

                try:
                    with console.status(f"[bold green]Calling {tool_name}...[/bold green]"):
                        result = asyncio.run(_call())
                except BaseException as e:
                    error_console.print(f"[red]Error: {format_error(e)}[/red]")
                    if verbose:
                        error_console.print_exception()
                    sys.exit(1)

                if result.isError:
                    error_console.print("[red]Tool returned an error:[/red]")
                    error_console.print(format_tool_result(result), markup=False)
                    sys.exit(1)

                output = format_tool_result(result)

                if as_json:
                    print(output)  # Use plain print to avoid Rich's text wrapping
                else:
                    try:
                        data = json.loads(output)
                        console.print(JSON(json.dumps(data)))
                    except json.JSONDecodeError:
                        console.print(output, markup=False)

            return callback

        tool_name = tool["name"]
        return click.Command(
            name=tool_name,
            callback=make_callback(tool_name, properties, param_name_map),
            params=params,
            help=tool.get("description"),
        )


@click.group(cls=DynamicGroup)
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=False, path_type=Path),
    envvar="DEVIN_MCP_CONFIG",
    help="Path to configuration file",
)
@click.option(
    "--org",
    "-o",
    "org_name",
    envvar="DEVIN_ORG",
    help="Account alias from config to use (env: DEVIN_ORG)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable debug logging and show full tracebacks on error",
)
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None, org_name: str | None, verbose: bool):
    """Devin MCP CLI - Query Devin using the MCP Server.

    Each Devin MCP tool is exposed as a CLI command. The command list comes from
    the live server, so it reflects whatever tools Devin currently exposes.
    Use 'devin-mcp <command> --help' for details on each command.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["org_name"] = org_name
    ctx.obj["verbose"] = verbose

    # Configure logging level based on verbose flag
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)


def _add_org(config_path: Path, name: str, api_key: str, org_id: str | None) -> bool:
    """Merge one account into the config file, preserving the others.

    Returns True if this account became the default (first account added).
    """
    data = read_config_dict(config_path)
    data.setdefault("orgs", {})

    org_entry: dict[str, str] = {"api_key": api_key}
    if org_id:
        org_entry["org_id"] = org_id
    data["orgs"][name] = org_entry

    became_default = False
    if not data.get("default_org"):
        data["default_org"] = name
        became_default = True

    save_config(config_path, data)
    return became_default


@cli.command("init")
@click.pass_context
def init_config(ctx: click.Context):
    """Add a first account (shortcut for 'org add')."""
    ctx.invoke(org_add, name=None, api_key=None, org_id=None)


@cli.group("org")
def org_group():
    """Manage named accounts (aliases) in the config file."""


@org_group.command("add")
@click.argument("name", required=False)
@click.option("--api-key", help="Devin API key (cog_...). Prompted if omitted.")
@click.option("--org-id", help="Devin organization UUID for X-Org-Id (optional).")
@click.pass_context
def org_add(ctx: click.Context, name: str | None, api_key: str | None, org_id: str | None):
    """Add or replace one account, merging into the existing config."""
    config_path = resolve_config_path(ctx)

    console.print("[bold]Devin MCP CLI - add account[/bold]\n")
    if not name:
        name = click.prompt("Account alias (local nickname, e.g. work)")
    if not api_key:
        console.print("Get a 'cog_' key from Devin (Settings -> Service users, or a Personal Access Token).")
        api_key = click.prompt("Devin API key", hide_input=True)
    if org_id is None:
        org_id = click.prompt(
            "Devin org UUID for X-Org-Id (optional, press Enter to skip)",
            default="",
            show_default=False,
        )
    org_id = org_id or None

    became_default = _add_org(config_path, name, api_key, org_id)

    console.print(f"\n[green]Saved account '{name}' to:[/green] {config_path}")
    if became_default:
        console.print(f"[dim]Set as default account (default_org={name}).[/dim]")


@org_group.command("list")
@click.pass_context
def org_list(ctx: click.Context):
    """List configured accounts with masked keys."""
    config_path = resolve_config_path(ctx)
    try:
        config = load_config(config_path)
    except ConfigError as e:
        error_console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)

    if not config.orgs:
        console.print("[yellow]No accounts configured.[/yellow]")
        console.print("[dim]Run 'devin-mcp org add <name>' or set DEVIN_API_KEY in the environment.[/dim]")
        console.print(f"[dim]Config file: {config_path}[/dim]")
        return

    display = {}
    for name, org in config.orgs.items():
        marker = " (default)" if name == config.default_org else ""
        display[f"{name}{marker}"] = {
            "api_key": mask_key(org.api_key),
            "org_id": org.org_id or "(none)",
        }

    console.print(Panel(JSON(json.dumps(display)), title="Configured accounts"))

    # Show which account the current selection would resolve to, and the source.
    org_name = ctx.obj.get("org_name") if ctx.obj else None
    try:
        resolved = config.get_org(org_name)
        if org_name:
            source = "--org / DEVIN_ORG"
        elif config.default_org:
            source = "default_org"
        elif len(config.orgs) == 1:
            source = "sole account"
        else:
            source = "environment fallback"
        console.print(f"[dim]Active selection: {resolved.name} (source: {source})[/dim]")
    except ConfigError as e:
        console.print(f"[dim]Active selection: none ({e})[/dim]")
    console.print(f"[dim]Config file: {config_path}[/dim]")


@org_group.command("use")
@click.argument("name")
@click.pass_context
def org_use(ctx: click.Context, name: str):
    """Set the default account, preserving everything else."""
    config_path = resolve_config_path(ctx)
    data = read_config_dict(config_path)
    orgs = data.get("orgs", {}) or {}

    if name not in orgs:
        available = ", ".join(sorted(orgs)) if orgs else "(none)"
        error_console.print(f"[red]Account '{name}' not found. Available: {available}[/red]")
        sys.exit(1)

    data["default_org"] = name
    save_config(config_path, data)
    console.print(f"[green]Default account set to:[/green] {name}")


@org_group.command("remove")
@click.argument("name")
@click.pass_context
def org_remove(ctx: click.Context, name: str):
    """Remove one account. Repoints the default if needed."""
    config_path = resolve_config_path(ctx)
    data = read_config_dict(config_path)
    orgs = data.get("orgs", {}) or {}

    if name not in orgs:
        available = ", ".join(sorted(orgs)) if orgs else "(none)"
        error_console.print(f"[red]Account '{name}' not found. Available: {available}[/red]")
        sys.exit(1)

    del orgs[name]
    data["orgs"] = orgs

    if data.get("default_org") == name:
        # Repoint to another account if one remains, else clear the pointer.
        data["default_org"] = next(iter(orgs), None)

    save_config(config_path, data)
    console.print(f"[green]Removed account:[/green] {name}")
    if data.get("default_org"):
        console.print(f"[dim]Default account is now: {data['default_org']}[/dim]")


@cli.command("config")
@click.pass_context
def show_config(ctx: click.Context):
    """Show the resolved active account (with the key masked)."""
    config_path = resolve_config_path(ctx)
    try:
        config = load_config(config_path)
    except ConfigError as e:
        error_console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)

    org_name = ctx.obj.get("org_name") if ctx.obj else None
    active: OrgConfig | None
    try:
        active = config.get_org(org_name)
    except ConfigError:
        active = None

    config_display: dict[str, Any] = {
        "active_account": active.name if active else "(none)",
        "api_key": mask_key(active.api_key) if active else "(not configured)",
        "org_id": (active.org_id or "(none)") if active else "(none)",
        "default_org": config.default_org or "(none)",
        "accounts": sorted(config.orgs),
        "mcp_server": {
            "url": DEVIN_MCP_URL,
            "timeout": config.mcp_server.timeout,
            "sse_read_timeout": config.mcp_server.sse_read_timeout,
        },
    }

    console.print(Panel(JSON(json.dumps(config_display)), title="Current Configuration"))
    console.print(f"\n[dim]Config file: {config_path}[/dim]")


def main():
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
