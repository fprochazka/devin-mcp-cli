# Devin MCP CLI

A command-line interface for the official [Devin MCP server](https://mcp.devin.ai/mcp), built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). Each Devin MCP tool is exposed as a direct CLI command, generated at runtime from the live server.

## Features

- One CLI command per Devin MCP tool (sessions, playbooks, knowledge, schedules, repos, and whatever else the server exposes).
- Auto-generated options from each tool's JSON input schema, with type handling.
- Multi-account config: one file holds several named accounts, selected per command.
- 1-hour cache for tool schemas to speed up subsequent invocations.
- Rich terminal output with JSON pretty-printing, plus `--json` for raw machine-readable output.

The command set is generated from the live server, so it reflects whatever tools Devin currently exposes. Run `devin-mcp --help` for the authoritative list and `devin-mcp <command> --help` for a tool's current options.

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

There is no PyPI release or tagged version yet, so install from a local clone as an editable uv tool. The `devin-mcp` command lands on your PATH, and edits in the clone take effect with no reinstall.

```bash
git clone https://github.com/fprochazka/devin-mcp-cli.git
cd devin-mcp-cli

# Install as an editable user tool (devin-mcp goes on your PATH)
uv tool install --editable .

# Then add an account
devin-mcp org add work
```

To update later, pull the clone. To uninstall, run `uv tool uninstall devin-mcp-cli`.

For development in the clone without installing, use `uv run`:

```bash
uv sync
uv run devin-mcp --help
```

## Authentication

Get a `cog_` key from Devin. A **Personal Access Token** acts as you. A **Service User** key acts as a bot (Settings -> Service users).

The CLI always sends `Authorization: Bearer <key>`. Some key types also need an `X-Org-Id` header:

- Org-scoped service-user keys auto-resolve the org, so they need **no** `X-Org-Id`.
- Personal Access Tokens and enterprise-scoped keys **require** `X-Org-Id: <org_id>`, the Devin organization UUID.

Each account stores the `api_key` plus an optional `org_id`. The `X-Org-Id` header is sent only when `org_id` is present.

## Two meanings of "org"

The two ideas are separate. Do not conflate them.

| Term | Meaning |
|------|---------|
| Account **alias** (`work`, `personal`) | A local nickname you pick for a set of credentials. Used with `--org`. |
| `org_id` | The Devin organization UUID, sent as the `X-Org-Id` header. |

An account alias is local to your config file. The `org_id` is a Devin identifier.

## Multi-account configuration

One config file holds several named accounts under `orgs`. A `default_org` pointer names the active one.

```yaml
default_org: work
orgs:
  work:
    api_key: cog_xxx
    org_id: "1111-uuid"      # optional; sent as X-Org-Id when present
  personal:
    api_key: cog_yyy         # org_id omitted -> no X-Org-Id header for this account
mcp_server:
  timeout: 30
  sse_read_timeout: 300
```

### Account commands

```bash
devin-mcp org add <name>        # add or replace one account (merges, never wipes others)
devin-mcp org list              # list accounts with masked keys, mark the default
devin-mcp org use <name>        # set default_org to <name>
devin-mcp org remove <name>     # remove one account, repoint the default if needed
devin-mcp config                # show the resolved active account + masked key + config path
```

`org add` prompts for the `api_key` (hidden) and an optional `org_id`. It merges into the existing file, so adding a second account never removes the first. The first account added becomes the default. For non-interactive use, pass `--api-key` and `--org-id`.

### Selecting an account per command

```bash
devin-mcp --org personal <command> ...
DEVIN_ORG=personal devin-mcp <command> ...
```

Selection precedence, highest first:

1. `--org` / `-o` (shares its slot with the `DEVIN_ORG` env var, so the flag wins over the env).
2. `default_org` in the config file.
3. The sole configured account, if exactly one exists.
4. Environment fallback: `DEVIN_API_KEY` (and optional `DEVIN_ORG_ID`) synthesize a single account named `env`. This makes the CLI work from env vars alone, with no config file.
5. Otherwise an error that lists the available account names.

### Config file precedence

1. `./.devin-mcp.yaml` in the current directory.
2. `~/.config/devin-mcp/config.yaml`.

Override the path with `--config <path>` or the `DEVIN_MCP_CONFIG` env var. The file is written with `0600` permissions because it holds plaintext secrets.

### Environment variables

| Variable | Purpose |
|----------|---------|
| `DEVIN_ORG` | Select the account alias (same slot as `--org`). |
| `DEVIN_API_KEY` | Env-only single-account fallback key. |
| `DEVIN_ORG_ID` | Optional `X-Org-Id` for the env-only account. |
| `DEVIN_MCP_CONFIG` | Config file path (same slot as `--config`). |
| `DEVIN_MCP_*` | MCP server timeouts via the config file (`mcp_server.timeout`, `mcp_server.sse_read_timeout`). |

## Usage

```bash
# List the live auto-generated commands
devin-mcp --help

# Show the options for one tool (live, from the server schema)
devin-mcp devin_session_search --help

# Call a tool
devin-mcp devin_session_search --limit 10

# Raw JSON output
devin-mcp devin_session_search --limit 10 --json
```

Array and object parameters are passed as JSON strings, for example `--tags '["a","b"]'`.

## Claude Code Plugin

This repository is also a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin marketplace. The plugin ships a skill that teaches Claude how to use the `devin-mcp` CLI.

```bash
# Install the devin-mcp CLI first (see Installation above)
uv tool install --editable .

# Add the marketplace and install the plugin
claude plugin marketplace add fprochazka/devin-mcp-cli
claude plugin install devin-mcp-cli@fprochazka-devin-mcp-cli
```

To upgrade after new commits land:

```bash
claude plugin marketplace update fprochazka-devin-mcp-cli
claude plugin update devin-mcp-cli@fprochazka-devin-mcp-cli
```

Once installed, the skill auto-approves read-only commands (`config`, `org list`, `list_integrations`, `devin_session_search`, `devin_session_events`, the wiki/`ask_question` tools). Write operations (`devin_session_create`, `devin_session_interact`, the `*_manage` tools, `org add`/`use`/`remove`) still require manual approval.

## Caching

Tool schemas are cached for 1 hour at `~/.cache/devin-mcp/`. Delete the cache directory to force a refresh.

## Project Structure

```
src/devin_mcp/
├── __init__.py   # Package metadata
├── cache.py      # Tool schema caching
├── cli.py        # CLI with dynamic command generation and account commands
├── client.py     # MCP client with Bearer auth and optional X-Org-Id
└── config.py     # Multi-account configuration and resolution

.claude-plugin/marketplace.json                       # Claude Code plugin marketplace
coding-agent-plugins/claude-code/                      # the plugin
├── .claude-plugin/plugin.json
└── skills/devin-mcp-cli/{SKILL.md, references/}       # the skill (single source)
```

## Development

```bash
uv sync
uv run ruff check .
uv run ruff format .
```

## Releasing the plugin

The plugin version lives in two files and must stay in lockstep. Bump both when you change the plugin:

- `.claude-plugin/marketplace.json` (`plugins[0].version`)
- `coding-agent-plugins/claude-code/.claude-plugin/plugin.json` (`version`)

This version is independent of the Python package version in `pyproject.toml`.

## License

MIT
