---
name: devin-mcp-cli
description: CLI for the official Devin MCP server (sessions, playbooks, knowledge, schedules, repos). Use when starting or replying to Devin sessions, searching sessions, managing playbooks or knowledge, scheduling runs, or exploring repos. Triggered by requests involving Devin, Cognition, agent sessions, or playbooks.
trigger-keywords: devin, session, sessions, playbook, playbooks, knowledge, cognition, agent
allowed-tools: Bash(devin-mcp --help), Bash(devin-mcp --version), Bash(devin-mcp * --help), Bash(devin-mcp config:*), Bash(devin-mcp org list:*), Bash(devin-mcp schema:*), Bash(devin-mcp session-search:*), Bash(devin-mcp devin_session_search:*), Bash(devin-mcp session-events:*), Bash(devin-mcp devin_session_events:*), Bash(devin-mcp session-gather:*), Bash(devin-mcp devin_session_gather:*), Bash(devin-mcp list-integrations:*), Bash(devin-mcp devin_list_integrations:*), Bash(devin-mcp find-setting:*), Bash(devin-mcp devin_find_setting:*), Bash(devin-mcp user-list:*), Bash(devin-mcp devin_user_list:*), Bash(devin-mcp bot-templates:*), Bash(devin-mcp devin_bot_templates:*), Bash(devin-mcp list-wiki-repos:*), Bash(devin-mcp list_wiki_repos:*), Bash(devin-mcp read-wiki-structure:*), Bash(devin-mcp read_wiki_structure:*), Bash(devin-mcp read-wiki-contents:*), Bash(devin-mcp read_wiki_contents:*), Bash(devin-mcp ask-wiki-question:*), Bash(devin-mcp ask_wiki_question:*)
---

# Devin MCP CLI

CLI tool providing direct access to Devin via the official Devin MCP server. Each Devin MCP tool is a command, named in kebab case without the `devin_` prefix: the tool `devin_session_search` is `devin-mcp session-search`. The tool's own name (`devin-mcp devin_session_search`) still works as an alias; prefer the short name.

## Important: the command list is live

The command set comes from the live Devin MCP server (cached for an hour). The authoritative list is always:

```bash
devin-mcp --help                 # the real, current command list
devin-mcp <command> --help       # the real, current options for one tool
devin-mcp schema <command>       # the tool's raw JSON input schema
```

Do not assume a flag exists. A wrong option fails with exit code 2 and a usage error that lists the tool's parameters, so read it and retry instead of guessing again.

## Quick Reference

| Intent | Command | Reference |
|--------|---------|-----------|
| Start new Devin sessions from prompts | `session-create` | [sessions.md](references/sessions.md) |
| List / search existing sessions | `session-search` | [sessions.md](references/sessions.md) |
| Read a session (metadata, structured output, messages) | `session-interact --action get` / `--action get_messages` | [sessions.md](references/sessions.md) |
| Reply into a running session (as me) | `session-interact --action message` | [sessions.md](references/sessions.md) |
| Read a session's events / timeline | `session-events --action list` | [sessions.md](references/sessions.md) |
| Block until several sessions settle | `session-gather` | [sessions.md](references/sessions.md) |
| Playbooks | `playbook-manage` | [playbooks.md](references/playbooks.md) |
| Knowledge notes | `knowledge-manage` | [knowledge.md](references/knowledge.md) |
| Scheduled runs (deprecated, see automations) | `schedule-manage`, `automation-manage` | [schedules.md](references/schedules.md) |
| Integrations, settings, users | `list-integrations`, `find-setting`, `user-list` | [repos.md](references/repos.md) |
| Read a repo's DeepWiki, ask a question about it | `list-wiki-repos`, `read-wiki-structure`, `read-wiki-contents`, `ask-wiki-question` | [repos.md](references/repos.md) |

## Accounts and configuration

The user configures accounts (see the project README). To run one command against a non-default account, put `--org <alias>` before the command: `devin-mcp --org <alias> session-search`. A command with `--org` in front does not match the auto-approved patterns, so it asks for permission.

- `devin-mcp org list` shows the accounts with masked keys, the default and the account in use now.
- `devin-mcp config` shows the effective configuration as JSON with the key masked.

Never run `org add`, `org use` or `org remove` unless the user asks: they change the user's config file.

## Options

- Booleans are `--flag` / `--no-flag`. `--flag true` is a usage error.
- Arrays take repeated options (`--tags backend --tags urgent`) or one JSON array (`--tags '["backend","urgent"]'`).
- Objects take a JSON literal (`--structured-output-schema '{"type": "object"}'`).
- An option left out is not sent; the server applies its own default.
- `--input-json @/path/args.json` passes all arguments as one JSON object from a file; `--arg-file NAME=PATH` reads one argument's value from a file.

## Output and exit codes

Under an AI agent the result is printed exactly as the server sent it (often plain text, sometimes JSON). `--pretty` indents JSON. Dump large results to a file and read them with `jq` or `grep`.

| Exit code | Meaning |
|---|---|
| 0 | Success |
| 1 | The tool reported an error; its text is on stderr |
| 2 | Usage or configuration error (wrong option, unknown account) |
| 3 | Devin could not be reached, refused the credentials, or timed out |

## Long-running tools and the shell timeout

`session-gather` waits up to its `--timeout-seconds` (default 300) for sessions to settle, and `blueprint-test` up to 600 s. The Bash tool kills a command after 120 s by default. Pass `--timeout-seconds` below your shell limit, or run the command with a raised Bash timeout.

## Content preparation workflow (REQUIRED for long content)

For multi-line prompts, playbook bodies, knowledge notes or replies, do NOT paste the text into the command line. Write it to a file, then pass the file:

```bash
# One string argument from a file
devin-mcp session-interact --action message --session-id "devin-<hex>" --arg-file message=/tmp/reply.md

# Several arguments, or array/object arguments such as session-create's sessions, as one JSON file
devin-mcp session-create --input-json @/tmp/create-sessions.json
```

This avoids shell escaping problems, preserves formatting, keeps the content out of the permission prompt, and lets the user review the content before submission. Short single-line values (titles, ids, limits) can be passed directly.
