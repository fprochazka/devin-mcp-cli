# Devin MCP CLI

A command-line interface for the official [Devin MCP server](https://mcp.devin.ai/mcp), built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) and [mcp-to-cli-kit](https://github.com/fprochazka/mcp-to-cli-kit). Each Devin MCP tool is exposed as a direct CLI command, generated at runtime from the live server.

## Features

- One CLI command per Devin MCP tool (sessions, playbooks, knowledge, schedules, repos, and whatever else the server exposes), named in kebab case without the `devin_` prefix: `devin_session_search` is `devin-mcp session-search`. The tool's own name keeps working as an alias.
- Options compiled from each tool's JSON input schema: `--flag` / `--no-flag` booleans, enums as choices, repeated options for arrays, `--input-json` and `--arg-file`, validated before the call.
- Multi-account config: one file holds several named accounts, selected per command.
- 1-hour cache for tool schemas, so `--help` needs no server round trip.
- Machine output under an AI agent or with `--json`, indented JSON for a person or with `--pretty`.

The command set is generated from the live server, so it reflects whatever tools Devin currently exposes. Run `devin-mcp --help` for the authoritative list and `devin-mcp <command> --help` for a tool's current options.

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

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

The kit's own settings of the Devin server go under `servers.devin` (for example `servers.devin.sse_read_timeout`). The older `mcp_server.timeout` and `mcp_server.sse_read_timeout` keep working and mean the same. The default read timeout is 660 seconds, because `session-gather` waits up to 590 seconds and `blueprint-test` up to 600 by design.

### Account commands

```bash
devin-mcp org add <name>        # add or replace one account (merges, never wipes others)
devin-mcp org list              # list accounts with masked keys, the default, and the account in use now
devin-mcp org use <name>        # set default_org to <name>
devin-mcp org remove <name>     # remove one account, repoint the default if needed
devin-mcp config                # the effective configuration as JSON, with the key masked
```

The `org` commands never contact Devin.

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
4. Environment fallback: `DEVIN_API_KEY` (and optional `DEVIN_ORG_ID`). This makes the CLI work from env vars alone, with no config file.
5. Otherwise, with several accounts and none chosen, an error that lists the account names. Without any account, the command fails naming `DEVIN_API_KEY`.

An unknown `--org` or `default_org` is a configuration error (exit code 2) that lists the account names.

### Config file

The file is `~/.config/devin-mcp/config.yaml` (`$XDG_CONFIG_HOME/devin-mcp/config.yaml` when that is set). Override the path with `--config <path>` or the `DEVIN_MCP_CONFIG` env var. The file is written with `0600` permissions because it holds plaintext secrets.

### Environment variables

| Variable | Purpose |
|----------|---------|
| `DEVIN_ORG` | Select the account alias (same slot as `--org`). |
| `DEVIN_API_KEY` | Env-only single-account fallback key. |
| `DEVIN_ORG_ID` | Optional `X-Org-Id` for the env-only account. |
| `DEVIN_MCP_CONFIG` | Config file path (same slot as `--config`). |
| `DEVIN_MCP_SERVERS__DEVIN__*` | Any kit setting of the Devin server, for example `DEVIN_MCP_SERVERS__DEVIN__SSE_READ_TIMEOUT`. |

## Usage

```bash
# List the live auto-generated commands
devin-mcp --help

# Show the options for one tool (from the cached server schema)
devin-mcp session-search --help
devin-mcp schema session-search          # the raw JSON input schema

# Call a tool; the old name devin_session_search works too
devin-mcp session-search --first 10

# The server's result exactly as sent
devin-mcp session-search --first 10 --json

# A long value from a file
devin-mcp session-create --arg-file prompt=/path/to/prompt.md
```

Arrays take repeated options (`--tags a --tags b`) or one JSON array (`--tags '["a","b"]'`); objects take a JSON literal. An option left out is not sent, and the server applies its own default.

Exit codes: 0 success, 1 the tool reported an error (its text is on stderr), 2 usage or configuration error, 3 Devin could not be reached or refused the credentials, 130 interrupted.

## Changes from the previous version

devin-mcp 0.2.0 runs on mcp-to-cli-kit instead of its own MCP client. Most command lines keep working; these changed:

- Commands are kebab case without the `devin_` prefix (`session-search`, `ask-wiki-question`). The old names stay aliases.
- Booleans are `--flag` / `--no-flag` instead of `--flag true`.
- `--json` prints the server's text exactly, and several content items become one JSON array. `--pretty` indents.
- Exit codes are 2 for usage and configuration errors and 3 for transport errors, instead of 1 for everything.
- `config` prints the kit's JSON view of the effective configuration; the active account and the masked keys are in `org list`.
- `init` is gone; use `org add`. The `-c` short option is gone; use `--config`.
- `./.devin-mcp.yaml` in the current directory is no longer read; pass it with `--config`.
- Schema defaults are no longer sent; the server applies the same defaults.
- The default read timeout is 660 seconds instead of 300.
- The tool cache moved from `~/.cache/devin-mcp/tools.json` to `~/.cache/devin-mcp/devin.json`; the old file can be deleted.

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

Once installed, the skill auto-approves read-only commands under both the new and the old names (`config`, `org list`, `schema`, `session-search`, `session-events`, `list-integrations`, the wiki tools, and `--help` of any tool). Write operations (`session-create`, `session-interact`, the `*-manage` tools, `org add`/`use`/`remove`) still require manual approval.

## Caching

Tool schemas are cached for 1 hour in `~/.cache/devin-mcp/devin.json`, shared by all accounts. `--refresh-tools` fetches them again.

## Project Structure

```
src/devin_mcp/
├── __init__.py   # Package metadata
├── accounts.py   # Account selection and the headers it gives the kit
└── cli.py        # The kit configuration, the result classifier and the org commands

.claude-plugin/marketplace.json                       # Claude Code plugin marketplace
coding-agent-plugins/claude-code/                      # the plugin
├── .claude-plugin/plugin.json
└── skills/devin-mcp-cli/{SKILL.md, references/}       # the skill (single source)
```

## Development

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

CI runs the same checks on every push to master and on pull requests, with the tests on Python 3.12 to 3.15. `uv run ruff format .` fixes the formatting.

### Commit hooks

Configs, test fixtures and captured output can carry private identifiers such as account aliases, organization IDs, session names or paths. `scripts/hooks` holds a pre-commit and a commit-msg hook that refuse a commit when a staged line or the commit message matches a private identifier. The identifiers live in a file outside the repository, because listing them here would publish the very strings the hooks exist to keep out. Set it up once per clone:

```bash
git config core.hooksPath scripts/hooks
git config hooks.forbiddenPatternsFile ~/.config/git/forbidden-patterns.txt  # any path outside the repo
```

The file holds one extended regex per line, matched case-insensitively; blank lines and `#` comments are ignored. Until `hooks.forbiddenPatternsFile` points at a file with at least one pattern, both hooks refuse every commit and print how to fix it. The hooks check only the lines a commit adds.

## Releasing the plugin

The plugin version lives in two files and must stay in lockstep. Bump both when you change the plugin:

- `.claude-plugin/marketplace.json` (`plugins[0].version`)
- `coding-agent-plugins/claude-code/.claude-plugin/plugin.json` (`version`)

This version is independent of the Python package version in `pyproject.toml`.

## License

MIT
