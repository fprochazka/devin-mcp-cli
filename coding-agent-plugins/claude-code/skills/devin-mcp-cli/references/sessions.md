# Sessions Reference

Sessions are the core Devin unit of work. A session runs from a prompt, produces events, and can be replied to while it runs.

The exact options come from the live server. Always confirm with `devin-mcp <command> --help`.

## devin_session_create

Start a new Devin session from a prompt.

```bash
# Short prompt inline
devin-mcp devin_session_create --prompt "Investigate the failing CI job on main"

# Long prompt: write to a file first, then pass with $(cat ...)
devin-mcp devin_session_create --prompt "$(cat /tmp/prompt.md)"
```

Purpose of common inputs (confirm names with `--help`):

| Input | Purpose |
|-------|---------|
| prompt | The task description Devin starts from. Use the file workflow for long prompts. |
| (optional) repo / context | Point the session at a repository or extra context, if the server supports it. |

## devin_session_search

List or search existing sessions. Useful before interacting with or gathering from a session, to find its id.

```bash
devin-mcp devin_session_search --limit 20
devin-mcp devin_session_search --json
```

Sessions can be filtered, for example by origin (`webapp`, `slack`, `api`, `linear`, `jira`). Check `--help` for the current filter flags.

## devin_session_interact

Send a message or prompt INTO an existing running session. This is the "reply in the session as me" operation.

```bash
devin-mcp devin_session_interact --session-id <id> --message "Also add a test for the null case"

# Long reply
devin-mcp devin_session_interact --session-id <id> --message "$(cat /tmp/reply.md)"
```

Get the session id from `devin_session_search` first.

## devin_session_events

Read a session's events, messages, and timeline.

```bash
devin-mcp devin_session_events --session-id <id>
devin-mcp devin_session_events --session-id <id> --json
```

## devin_session_gather

Gather a session's outputs and results (the produced artifacts, summary, or final state).

```bash
devin-mcp devin_session_gather --session-id <id>
```
