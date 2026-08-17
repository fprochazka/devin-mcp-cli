---
name: devin-mcp-cli
description: CLI for the official Devin MCP server (sessions, playbooks, knowledge, schedules, repos). Use when starting or replying to Devin sessions, searching sessions, managing playbooks or knowledge, scheduling runs, or exploring repos. Triggered by requests involving Devin, Cognition, agent sessions, or playbooks.
trigger-keywords: devin, session, sessions, playbook, playbooks, knowledge, cognition, agent
allowed-tools: Bash(devin-mcp --help), Bash(devin-mcp config:*), Bash(devin-mcp list_integrations:*), Bash(devin-mcp list_available_repos:*), Bash(devin-mcp devin_session_search:*), Bash(devin-mcp devin_session_events:*), Bash(devin-mcp devin_session_gather:*), Bash(devin-mcp read_wiki_structure:*), Bash(devin-mcp read_wiki_contents:*), Bash(devin-mcp ask_question:*), Bash(devin-mcp find_setting:*)
---

# Devin MCP CLI

CLI tool providing direct access to Devin via the official Devin MCP server. Each Devin MCP tool is exposed as a command.

## Important: the command list is live

The command set is generated at runtime from the live Devin MCP server. The tool names below are the expected surface from research, but the authoritative list is always:

```bash
devin-mcp --help                 # the real, current command list
devin-mcp <command> --help       # the real, current options for one tool
```

Do not assume a flag exists. Read `devin-mcp <command> --help` for the current options. Tool names or flags that this skill cannot verify are described by purpose only.

## Quick Reference

| Intent | Command | Reference |
|--------|---------|-----------|
| Start a new Devin session from a prompt | `devin_session_create` | [sessions.md](references/sessions.md) |
| List / search existing sessions | `devin_session_search` | [sessions.md](references/sessions.md) |
| Reply into a running session (as me) | `devin_session_interact` | [sessions.md](references/sessions.md) |
| Read a session's events / timeline | `devin_session_events` | [sessions.md](references/sessions.md) |
| Gather a session's outputs / results | `devin_session_gather` | [sessions.md](references/sessions.md) |
| List / get / create / update playbooks | `devin_playbook_manage` | [playbooks.md](references/playbooks.md) |
| List / get / create / update knowledge notes | `devin_knowledge_manage` | [knowledge.md](references/knowledge.md) |
| List / get / create / update scheduled runs | `devin_schedule_manage` | [schedules.md](references/schedules.md) |
| Discover integrations and available repos | `list_integrations`, `list_available_repos` | [repos.md](references/repos.md) |
| Read a repo's wiki / docs, ask a question | `read_wiki_structure`, `read_wiki_contents`, `ask_question` | [repos.md](references/repos.md) |

## Accounts

The user configures accounts (see the project README). To run one command against a non-default account, add `--org <name>`.

## Output

Default output is pretty-printed JSON. Use `--json` for raw, machine-readable JSON:

```bash
devin-mcp devin_session_search --json
```

## Array and object parameters

Pass array or object parameters as JSON strings:

```bash
--tags '["backend", "urgent"]'
--metadata '{"source": "cli"}'
```

## Content preparation workflow (REQUIRED for long content)

For multi-line prompts, playbook bodies, or knowledge notes, do NOT paste the text directly as a shell argument.

1. Write the content to a markdown file first, for example `/tmp/prompt.md`.
2. Pass it with `$(cat file.md)`.

```bash
devin-mcp devin_session_create --prompt "$(cat /tmp/prompt.md)"
```

This avoids shell escaping problems, preserves formatting, and lets the user review the content before submission. Short single-line values (titles, ids, limits) can be passed directly.

## Getting command help

```bash
devin-mcp <command> --help
```
