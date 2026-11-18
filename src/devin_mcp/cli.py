"""``devin-mcp``: the tools of the Devin MCP server as commands, run by mcp-to-cli-kit, plus the account commands."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from mcp_to_cli_kit.cli import build_cli
from mcp_to_cli_kit.config import ConfigError, read_config_file, resolve_config_path, save_config
from mcp_to_cli_kit.lazy import run
from mcp_to_cli_kit.output import echo_json

from devin_mcp import DISTRIBUTION
from devin_mcp.accounts import CONSUMER_KEYS, ORG_OPTION, SERVER, accounts, config_layer, mask_key, select

if TYPE_CHECKING:
    from mcp import types

BIN = "devin-mcp"

DEVIN_MCP_URL = "https://mcp.devin.ai/mcp"

DEFAULT_CONFIG: dict[str, Any] = {
    "help": (
        "Devin MCP CLI - Call the tools of the Devin MCP server. Each tool is a command; use "
        "'devin-mcp <command> --help' for its options. Accounts live in ~/.config/devin-mcp/config.yaml "
        "(see 'devin-mcp org --help'), or set DEVIN_API_KEY."
    ),
    "servers": {
        SERVER: {
            "url": DEVIN_MCP_URL,
            "timeout": 30,
            # devin_session_gather waits up to 590 s and devin_blueprint_test 600 s by design.
            "sse_read_timeout": 660,
            "strip_prefixes": ["devin_"],
        }
    },
}

ORG = click.Option(
    ["-o", "--org", ORG_OPTION],
    envvar="DEVIN_ORG",
    show_envvar=True,
    is_eager=True,
    help="The account alias from the config file to use.",
)

_HTTP_ERROR_CONTENT = re.compile(r"^Error: HTTP \d{3}\b")


def is_transport_error_content(server: str, tool: str, result: types.CallToolResult) -> bool:
    """Report whether a result the server did not mark as an error is really a failed backing API call.

    The Devin MCP server returns a non-2xx response of its backing API as plain text content with ``isError`` false.
    The match is anchored and needs a status code, so an ordinary JSON result cannot trigger it.
    """
    first = next((item.text for item in result.content if item.type == "text"), "")
    return bool(_HTTP_ERROR_CONTENT.match(first.strip()))


def _global(ctx: click.Context, name: str) -> Any:
    """A global option of the bin, from the nearest enclosing context that has it."""
    current: click.Context | None = ctx
    while current is not None:
        if name in current.params:
            return current.params[name]
        current = current.parent
    return None


def _config_path(ctx: click.Context) -> Path:
    return resolve_config_path(BIN, _global(ctx, "config"))


def _read(path: Path) -> dict[str, Any]:
    """The config file as a mapping, empty when there is none. A broken file ends the command with exit code 2."""
    try:
        return read_config_file(path)
    except ConfigError as error:
        raise _ConfigFailure(str(error)) from error


class _ConfigFailure(click.ClickException):
    exit_code = 2


def _no_account(name: str, orgs: Mapping[str, Any]) -> click.BadParameter:
    available = ", ".join(sorted(orgs)) or "none"
    return click.BadParameter(f"No account {name!r} in the config file. Accounts: {available}.", param_hint="NAME")


@click.group("org", help="Manage the named accounts (aliases) in the config file. Run without contacting Devin.")
def org_group() -> None:
    pass


@org_group.command("add")
@click.argument("name", required=False)
@click.option("--api-key", help="Devin API key (cog_...). Prompted for, hidden, when left out.")
@click.option("--org-id", help="Devin organization UUID, sent as X-Org-Id. Optional; prompted for when left out.")
@click.pass_context
def org_add(ctx: click.Context, name: str | None, api_key: str | None, org_id: str | None) -> None:
    """Add or replace one account. Other accounts stay; the first account becomes the default."""
    path = _config_path(ctx)
    data = _read(path)
    if not name:
        name = click.prompt("Account alias (a local nickname, e.g. work)")
    if not api_key:
        click.echo("Get a 'cog_' key from Devin (Settings -> Service users, or a Personal Access Token).", err=True)
        api_key = click.prompt("Devin API key", hide_input=True)
    if org_id is None:
        org_id = click.prompt("Devin org UUID for X-Org-Id (optional, Enter to skip)", default="", show_default=False)

    orgs = data.get("orgs") or {}
    entry: dict[str, str] = {"api_key": str(api_key)}
    if org_id:
        entry["org_id"] = org_id
    orgs[name] = entry
    data["orgs"] = orgs
    became_default = not data.get("default_org")
    if became_default:
        data["default_org"] = name

    written = save_config(path, data)
    click.echo(f"Saved account {name!r} to {written}.")
    if became_default:
        click.echo(f"It is the default account (default_org: {name}).")


@org_group.command("list")
@click.pass_context
def org_list(ctx: click.Context) -> None:
    """List the accounts with masked keys, the default, and the account a command would use now."""
    path = _config_path(ctx)
    consumer = {key: value for key, value in _read(path).items() if key in CONSUMER_KEYS}
    try:
        known = accounts(consumer)
    except ConfigError as error:
        raise _ConfigFailure(str(error)) from error

    default = consumer.get("default_org")
    active: dict[str, Any]
    try:
        selection = select(consumer, _global(ctx, ORG_OPTION))
        name = selection.account.name if selection.account else None
        active = {"account": name, "source": selection.source}
    except ConfigError as error:
        active = {"account": None, "error": str(error)}

    echo_json(
        ctx,
        {
            "config_file": str(path),
            "default_org": default,
            "active": active,
            "accounts": {
                alias: {"api_key": mask_key(account.api_key), "org_id": account.org_id, "default": alias == default}
                for alias, account in known.items()
            },
        },
    )


@org_group.command("use")
@click.argument("name")
@click.pass_context
def org_use(ctx: click.Context, name: str) -> None:
    """Make NAME the default account."""
    path = _config_path(ctx)
    data = _read(path)
    orgs = data.get("orgs") or {}
    if name not in orgs:
        raise _no_account(name, orgs)
    data["default_org"] = name
    save_config(path, data)
    click.echo(f"The default account is now {name!r}.")


@org_group.command("remove")
@click.argument("name")
@click.pass_context
def org_remove(ctx: click.Context, name: str) -> None:
    """Remove the account NAME. When it was the default, another remaining account becomes the default."""
    path = _config_path(ctx)
    data = _read(path)
    orgs = data.get("orgs") or {}
    if name not in orgs:
        raise _no_account(name, orgs)
    del orgs[name]
    data["orgs"] = orgs
    if data.get("default_org") == name:
        data["default_org"] = next(iter(orgs), None)
    save_config(path, data)
    click.echo(f"Removed account {name!r}.")
    if data.get("default_org"):
        click.echo(f"The default account is now {data['default_org']!r}.")


def build() -> click.Group:
    """The ``devin-mcp`` command group."""
    return build_cli(
        BIN,
        DEFAULT_CONFIG,
        distribution=DISTRIBUTION,
        result_classifier=is_transport_error_content,
        extra_params=[ORG],
        extra_commands=[org_group],
        consumer_keys=CONSUMER_KEYS,
        config_layer=config_layer,
    )


def main() -> None:
    run(build(), prog_name=BIN)
