"""Named Devin accounts in the config file, and the request headers of the selected one.

The config file holds several accounts under ``orgs``, keyed by a local alias (``work``, ``personal``). The alias is
not the Devin ``org_id``: that is the Devin organization UUID, sent as the ``X-Org-Id`` header only when the account
has one.

These keys belong to devin-mcp-cli, not to mcp-to-cli-kit. The kit takes them out of the file before it validates the
rest, and ``config_layer`` turns the selected account into the kit's ``servers.devin`` headers on every run.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import click
from mcp_to_cli_kit.config import ConfigError

SERVER = "devin"

ORG_OPTION = "org"
"""The ``ctx.params`` name of the global ``--org`` option."""

CONSUMER_KEYS = frozenset({"orgs", "default_org", "mcp_server"})
"""The top-level keys of the config file that devin-mcp-cli reads itself."""

API_KEY_VARIABLE = "DEVIN_API_KEY"
ORG_ID_VARIABLE = "DEVIN_ORG_ID"

# Keys of the old ``mcp_server`` section, which mean the same as the kit's keys of the same name under servers.devin.
_MCP_SERVER_KEYS = ("timeout", "sse_read_timeout")


@dataclass(frozen=True)
class Account:
    """The credentials of one account. ``name`` is the local alias, ``org_id`` the optional Devin organization UUID."""

    name: str
    api_key: str
    org_id: str | None = None


@dataclass(frozen=True)
class Selection:
    """The account a command uses, and why.

    ``account`` is None when no account of the file is selected and the credentials come from ``DEVIN_API_KEY`` (and
    ``DEVIN_ORG_ID``) instead.
    """

    account: Account | None
    source: str


def accounts(consumer: Mapping[str, Any]) -> dict[str, Account]:
    """The accounts of the file's ``orgs`` key, by alias.

    Raises:
        ConfigError: ``orgs`` is not a mapping, or an account is not a mapping or has no ``api_key``.
    """
    orgs = consumer.get("orgs") or {}
    if not isinstance(orgs, Mapping):
        raise ConfigError("The config key orgs must map account aliases to their api_key and org_id.")
    result: dict[str, Account] = {}
    for name, entry in orgs.items():
        if not isinstance(entry, Mapping):
            raise ConfigError(f"Account {name!r} in orgs must be a mapping with api_key and an optional org_id.")
        api_key = entry.get("api_key")
        if not api_key:
            raise ConfigError(f"Account {name!r} in orgs has no api_key.")
        org_id = entry.get("org_id")
        result[str(name)] = Account(str(name), str(api_key), str(org_id) if org_id else None)
    return result


def select(consumer: Mapping[str, Any], selected: str | None, environ: Mapping[str, str] | None = None) -> Selection:
    """Choose the account, first match wins.

    1. ``selected``, from ``--org`` or ``DEVIN_ORG``.
    2. ``default_org`` of the file.
    3. The only account of the file.
    4. ``DEVIN_API_KEY`` (and an optional ``DEVIN_ORG_ID``) from the environment.
    5. With accounts in the file but none of them selected, an error that lists them. Without any account, the
       environment variables still, so that the kit names ``DEVIN_API_KEY`` when it contacts the server.

    Raises:
        ConfigError: ``selected`` or ``default_org`` names no account, or several accounts and no choice among them.
    """
    environ = os.environ if environ is None else environ
    known = accounts(consumer)
    available = ", ".join(sorted(known)) or "none"

    if selected:
        if selected not in known:
            raise ConfigError(f"No account {selected!r} in the config file. Accounts: {available}.")
        return Selection(known[selected], "--org / DEVIN_ORG")

    default = consumer.get("default_org")
    if default:
        if default not in known:
            raise ConfigError(f"default_org {default!r} names no account in the config file. Accounts: {available}.")
        return Selection(known[default], "default_org")

    if len(known) == 1:
        return Selection(next(iter(known.values())), "the only account")

    if known and not environ.get(API_KEY_VARIABLE):
        raise ConfigError(
            f"No account selected. Pass --org <alias> (accounts: {available}) or run 'devin-mcp org use <alias>'."
        )
    return Selection(None, API_KEY_VARIABLE)


def headers(selection: Selection, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """The request headers of the selection, in the kit's template syntax.

    A file account gives its key as a literal, escaped so that a ``${`` in it is not read as a variable. Without one,
    the headers refer to ``${DEVIN_API_KEY}`` and ``${DEVIN_ORG_ID}``: the kit expands them when it contacts the server,
    names a missing variable, and keeps the values out of its output and log. ``X-Org-Id`` is left out when there is
    no org_id, since an org-scoped key needs none.
    """
    environ = os.environ if environ is None else environ
    if selection.account is None:
        result = {"Authorization": f"Bearer ${{{API_KEY_VARIABLE}}}"}
        if environ.get(ORG_ID_VARIABLE):
            result["X-Org-Id"] = f"${{{ORG_ID_VARIABLE}}}"
        return result
    result = {"Authorization": f"Bearer {_literal(selection.account.api_key)}"}
    if selection.account.org_id:
        result["X-Org-Id"] = _literal(selection.account.org_id)
    return result


def config_layer(ctx: click.Context, consumer: Mapping[str, Any]) -> Mapping[str, Any]:
    """The kit config computed from the account keys: the selected account's headers and the old ``mcp_server`` keys.

    The kit merges it over the code default and under the file's own ``servers.devin``, so headers written there win.
    """
    server: dict[str, Any] = {"headers": headers(select(consumer, ctx.params.get(ORG_OPTION)))}
    mcp_server = consumer.get("mcp_server") or {}
    if not isinstance(mcp_server, Mapping):
        raise ConfigError("The config key mcp_server must be a mapping with timeout and sse_read_timeout.")
    server.update({key: mcp_server[key] for key in _MCP_SERVER_KEYS if key in mcp_server})
    return {"servers": {SERVER: server}}


def mask_key(api_key: str) -> str:
    """The key for display: the ``cog_`` prefix and the last 4 characters, or only ``***`` for a short key."""
    if len(api_key) < 12:
        return "***"
    prefix = "cog_" if api_key.startswith("cog_") else ""
    return f"{prefix}***{api_key[-4:]}"


def _literal(value: str) -> str:
    return value.replace("${", "$${")
