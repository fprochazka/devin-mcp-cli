"""Account selection, the headers it gives the kit, the org commands and the result classifier. No network."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner
from mcp import types
from mcp_to_cli_kit.config import ConfigError, LoadedConfig, expand_server, load_config, read_config_file, save_config

from devin_mcp import accounts
from devin_mcp.accounts import CONSUMER_KEYS, Account, Selection, headers, mask_key, select
from devin_mcp.cli import BIN, DEFAULT_CONFIG, DEVIN_MCP_URL, build, is_transport_error_content, main

KEY_WORK = "cog_" + "w" * 28 + "1111"
KEY_HOME = "cog_" + "h" * 28 + "2222"
KEY_ENV = "cog_" + "e" * 28 + "3333"
ORG_ID = "00000000-0000-0000-0000-000000000001"

TWO_ACCOUNTS: dict[str, Any] = {
    "default_org": "work",
    "orgs": {"work": {"api_key": KEY_WORK, "org_id": ORG_ID}, "home": {"api_key": KEY_HOME}},
}


@pytest.fixture(autouse=True)
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in (
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "CLAUDECODE",
        "DEVIN_ORG",
        "DEVIN_API_KEY",
        "DEVIN_ORG_ID",
        "DEVIN_MCP_CONFIG",
    ):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def config_path(home: Path) -> Path:
    return home / ".config" / "devin-mcp" / "config.yaml"


def config_file(home: Path, content: dict[str, Any]) -> Path:
    return save_config(config_path(home), content)


def invoke(*args: str, env: dict[str, str] | None = None, stdin: str | None = None) -> tuple[int, str, str]:
    result = CliRunner().invoke(build(), ["--pretty", *args], env=env, input=stdin)
    return result.exit_code, result.stdout, result.stderr


def loaded(org: str | None = None, environ: dict[str, str] | None = None) -> LoadedConfig:
    """The kit config as a command sees it, with the layer called as the kit calls it."""
    ctx = click.Context(click.Command("devin-mcp"))
    ctx.params = {"org": org}
    return load_config(
        BIN,
        default=DEFAULT_CONFIG,
        environ=environ or {},
        consumer_keys=CONSUMER_KEYS,
        layer=lambda consumer: accounts.config_layer(ctx, consumer),
    )


def sent_headers(org: str | None = None, environ: dict[str, str] | None = None) -> dict[str, str]:
    server = loaded(org, environ).config.servers["devin"]
    return {k: v for k, v in expand_server("devin", server, environ or {}).headers.items() if k != "X-Mcp-Client"}


def test_default_config_validates() -> None:
    server = loaded().config.servers["devin"]

    assert server.url == DEVIN_MCP_URL
    assert server.timeout == 30
    assert server.sse_read_timeout == 660
    assert server.strip_prefixes == ["devin_"]


@pytest.mark.parametrize(
    ("content", "org", "expected"),
    [
        (TWO_ACCOUNTS, "home", Selection(Account("home", KEY_HOME), "--org / DEVIN_ORG")),
        (TWO_ACCOUNTS, None, Selection(Account("work", KEY_WORK, ORG_ID), "default_org")),
        ({"orgs": {"home": {"api_key": KEY_HOME}}}, None, Selection(Account("home", KEY_HOME), "the only account")),
    ],
)
def test_account_precedence(content: dict[str, Any], org: str | None, expected: Selection) -> None:
    assert select(content, org, {"DEVIN_API_KEY": KEY_ENV}) == expected


def test_environment_is_the_fallback_when_no_account_is_chosen() -> None:
    content = {"orgs": {"work": {"api_key": KEY_WORK}, "home": {"api_key": KEY_HOME}}}

    assert select(content, None, {"DEVIN_API_KEY": KEY_ENV}) == Selection(None, "DEVIN_API_KEY")
    assert select({}, None, {}) == Selection(None, "DEVIN_API_KEY")


def test_several_accounts_without_a_choice_list_the_aliases() -> None:
    content = {"orgs": {"work": {"api_key": KEY_WORK}, "home": {"api_key": KEY_HOME}}}

    with pytest.raises(ConfigError, match="No account selected. Pass --org <alias> \\(accounts: home, work\\)"):
        select(content, None, {})


def test_unknown_selection_and_default_list_the_aliases() -> None:
    with pytest.raises(ConfigError, match="No account 'nope' in the config file. Accounts: home, work."):
        select(TWO_ACCOUNTS, "nope", {})
    with pytest.raises(ConfigError, match="default_org 'gone' names no account"):
        select({**TWO_ACCOUNTS, "default_org": "gone"}, None, {})


def test_an_account_without_a_key_is_a_config_error() -> None:
    with pytest.raises(ConfigError, match="Account 'work' in orgs has no api_key."):
        select({"orgs": {"work": {"org_id": ORG_ID}}}, None, {})


def test_x_org_id_is_sent_only_with_an_org_id(home: Path) -> None:
    config_file(home, TWO_ACCOUNTS)

    assert sent_headers() == {"Authorization": f"Bearer {KEY_WORK}", "X-Org-Id": ORG_ID}
    assert sent_headers("home") == {"Authorization": f"Bearer {KEY_HOME}"}


def test_environment_credentials_reach_the_headers_through_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    assert headers(Selection(None, "DEVIN_API_KEY"), {}) == {"Authorization": "Bearer ${DEVIN_API_KEY}"}
    environ = {"DEVIN_API_KEY": KEY_ENV, "DEVIN_ORG_ID": ORG_ID}
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    assert sent_headers(environ=environ) == {"Authorization": f"Bearer {KEY_ENV}", "X-Org-Id": ORG_ID}


def test_a_missing_key_names_the_variable() -> None:
    server = loaded().config.servers["devin"]

    with pytest.raises(ConfigError, match="DEVIN_API_KEY, which is not set"):
        expand_server("devin", server, {})


def test_a_dollar_brace_in_a_key_is_sent_as_written(home: Path) -> None:
    key = "cog_abc${NOT_A_VARIABLE}xyz"
    config_file(home, {"orgs": {"odd": {"api_key": key}}})

    assert sent_headers() == {"Authorization": f"Bearer {key}"}


def test_the_old_file_shape_loads_and_keeps_its_timeouts(home: Path) -> None:
    config_file(home, {**TWO_ACCOUNTS, "mcp_server": {"timeout": 45, "sse_read_timeout": 300}})

    server = loaded().config.servers["devin"]

    assert (server.timeout, server.sse_read_timeout) == (45, 300)


def test_servers_devin_in_the_file_wins_over_the_account(home: Path) -> None:
    config_file(home, {**TWO_ACCOUNTS, "servers": {"devin": {"headers": {"Authorization": "Bearer other-key-1234"}}}})

    assert sent_headers() == {"Authorization": "Bearer other-key-1234", "X-Org-Id": ORG_ID}


def test_config_masks_the_key_and_lists_the_account_keys_by_name(home: Path) -> None:
    config_file(home, TWO_ACCOUNTS)

    code, stdout, stderr = invoke("config")

    assert code == 0, stderr
    shown = json.loads(stdout)
    assert shown["consumer_keys"] == ["default_org", "orgs"]
    assert shown["config"]["servers"]["devin"]["headers"]["Authorization"] == "Bearer ***1111"
    assert KEY_WORK not in stdout + stderr
    assert KEY_HOME not in stdout + stderr


def test_unknown_org_exits_2_with_the_aliases(home: Path) -> None:
    config_file(home, TWO_ACCOUNTS)

    code, _, stderr = invoke("config", env={"DEVIN_ORG": "nope"})

    assert code == 2
    assert "No account 'nope' in the config file. Accounts: home, work." in stderr


def test_devin_mcp_config_names_the_file(home: Path) -> None:
    other = save_config(home / "elsewhere.yaml", {"orgs": {"home": {"api_key": KEY_HOME}}})

    code, stdout, stderr = invoke("org", "list", env={"DEVIN_MCP_CONFIG": str(other)})

    assert code == 0, stderr
    assert json.loads(stdout)["config_file"] == str(other)


def test_org_list_masks_keys_and_shows_the_active_account(home: Path) -> None:
    path = config_file(home, TWO_ACCOUNTS)

    code, stdout, stderr = invoke("--org", "home", "org", "list")

    assert code == 0, stderr
    assert json.loads(stdout) == {
        "config_file": str(path),
        "default_org": "work",
        "active": {"account": "home", "source": "--org / DEVIN_ORG"},
        "accounts": {
            "work": {"api_key": "cog_***1111", "org_id": ORG_ID, "default": True},
            "home": {"api_key": "cog_***2222", "org_id": None, "default": False},
        },
    }


def test_org_list_reports_a_selection_error_instead_of_failing(home: Path) -> None:
    config_file(home, TWO_ACCOUNTS)

    code, stdout, _ = invoke("--org", "nope", "org", "list")

    assert code == 0
    assert json.loads(stdout)["active"]["account"] is None
    assert "No account 'nope'" in json.loads(stdout)["active"]["error"]


def test_org_add_use_remove_round_trip(home: Path) -> None:
    path = config_path(home)

    assert invoke("org", "add", "work", "--api-key", KEY_WORK, "--org-id", ORG_ID)[0] == 0
    assert invoke("org", "add", "home", stdin=f"{KEY_HOME}\n\n")[0] == 0
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert select(_read(path), None, {}).account == Account("work", KEY_WORK, ORG_ID)

    assert invoke("org", "use", "home")[0] == 0
    assert select(_read(path), None, {}).account == Account("home", KEY_HOME)

    assert invoke("org", "remove", "home")[0] == 0
    assert _read(path) == {"orgs": {"work": {"api_key": KEY_WORK, "org_id": ORG_ID}}, "default_org": "work"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_org_add_keeps_the_kit_keys_of_the_file(home: Path) -> None:
    path = config_file(home, {"servers": {"devin": {"timeout": 60}}})

    assert invoke("org", "add", "work", "--api-key", KEY_WORK, "--org-id", "")[0] == 0

    expected = {"servers": {"devin": {"timeout": 60}}, "orgs": {"work": {"api_key": KEY_WORK}}, "default_org": "work"}
    assert _read(path) == expected


def test_org_use_of_an_unknown_account_exits_2(home: Path) -> None:
    config_file(home, TWO_ACCOUNTS)

    code, _, stderr = invoke("org", "use", "nope")

    assert code == 2
    assert "No account 'nope' in the config file. Accounts: home, work." in stderr


def test_main_exits_with_the_kit_exit_codes(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file(home, TWO_ACCOUNTS)
    monkeypatch.setattr("sys.argv", ["devin-mcp", "org", "use", "nope"])

    with pytest.raises(SystemExit) as exited:
        main()

    assert exited.value.code == 2


def test_mask_key() -> None:
    assert mask_key(KEY_WORK) == "cog_***1111"
    assert mask_key("x" * 16 + "abcd") == "***abcd"
    assert mask_key("cog_short") == "***"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Error: HTTP 404 Not Found", True),
        ("  Error: HTTP 500", True),
        ('{"error": "Error: HTTP 404"}', False),
        ("Error: HTTP status unknown", False),
        ("[]", False),
    ],
)
def test_classifier_flags_backing_api_errors(text: str, expected: bool) -> None:
    result = types.CallToolResult(content=[types.TextContent(type="text", text=text)])

    assert is_transport_error_content("devin", "devin_session_search", result) is expected


def test_classifier_ignores_results_without_text() -> None:
    assert is_transport_error_content("devin", "x", types.CallToolResult(content=[])) is False


def _read(path: Path) -> dict[str, Any]:
    return read_config_file(path)
