# Sessions Reference

Sessions are the core Devin unit of work. A session runs from a prompt, produces events, and can be replied to while it runs.

The exact options come from the live server. Always confirm with `devin-mcp <command> --help`.

## Session IDs and the `devin-` prefix

Web URL format: `https://<host>/sessions/<32-hex>` — the CLI session ID is `devin-<32-hex>` (just prepend `devin-`).

`session-search` returns IDs **without** the prefix in its results. Every other command (`session-interact`, `session-events`, `session-gather`) requires the `devin-` prefix on input. `session-interact` additionally accepts bare IDs when referencing `child_session_ids` values from a `get` response.

## session-create

Start one or more Devin sessions. `--sessions` is an array of session specs; only `prompt` is required in each, and `title`, `playbook_id`, `tags` and `repos` can be set per session. `--repos`, `--tags`, `--platform` and `--devin-mode` apply to all sessions of the call.

```bash
# Short prompt inline: one JSON object per --sessions option
devin-mcp session-create --sessions '{"prompt": "Investigate the failing CI job on main"}' --repos myorg/myrepo

# Long prompt: write the whole call as a JSON file first
#   /tmp/create-sessions.json: {"sessions": [{"prompt": "...long markdown...", "title": "Fix flaky CI job"}], "repos": ["myorg/myrepo"]}
devin-mcp session-create --input-json @/tmp/create-sessions.json
```

## session-search

List or search existing sessions. All filters are optional and combined with AND. The result is one line per session.

```bash
devin-mcp session-search --first 20
devin-mcp session-search --session-ids "devin-<hex>"                    # look up one specific session
devin-mcp session-search --tags knowledge-cleanup --origins automation   # array filters repeat: --tags a --tags b
devin-mcp session-search --query "flaky test" --no-include-bot-sessions
```

**There is no `--limit` flag.** Pagination uses `--first N` (default 20, max 100) and `--after <cursor>`; the result's last line names the cursor of the next page.

Filter flags: `--session-ids`, `--tags`, `--playbook-id`, `--origins`, `--schedule-id`, `--automation-ids`, `--billing-tag-ids`, `--category`, `--query`, `--created-after`, `--created-before`, `--updated-after`, `--updated-before` (Unix timestamps), `--user-ids`, `--parent-session-id`, `--include-bot-sessions` / `--no-include-bot-sessions`, `--has-app` / `--no-has-app`. Check `devin-mcp session-search --help` for the current list and the valid `--origins` values.

## session-interact

Multi-action command — `--action` is required. Covers reading sessions, sending replies, and lifecycle operations. `--session-id` requires the `devin-` prefix.

| Action | What it does |
|---|---|
| `get` | Full session details: title, status, status_detail, ACUs consumed, tags, `child_session_ids`, `pull_requests`, `structured_output` |
| `get_messages` | Paginated message conversation — the initiating prompt plus Devin's status messages. Long bodies are truncated; fetch a full body via `session-events --action details --event-ids <event_id>` |
| `message` | Send a reply into the session (resumes it if sleeping). Requires `--message`. |
| `get_attachments` | List attachments (not paginated — full list returned). |
| `set_tags` | Replace all tags on the session. Requires `--tags tag1 --tags tag2`. Full replacement, not append. |
| `sleep` / `terminate` / `archive` / `unarchive` | Lifecycle actions. |
| `forward_to_slack` | Forward messages of the session to a Slack thread. |

`--action message` marks the session done unless `--no-mark-done` is passed; `--summary` asks `get` for a shorter answer.

Pagination for `get_messages`: `--first N`, `--after <cursor>`.

```bash
# Read a finished session — start here
devin-mcp session-interact --action get --session-id "devin-<hex>"

# Read the message conversation
devin-mcp session-interact --action get_messages --session-id "devin-<hex>"

# Reply into a running session, the reply written to a file first
devin-mcp session-interact --action message --session-id "devin-<hex>" --arg-file message=/tmp/reply.md
```

**Where the content lives:** for automated and playbook sessions, `structured_output` (from `get`) holds the richest machine-readable run manifest — often more information-dense than the message conversation. `get_messages` holds the human-readable narrative (typically 3–5 messages). Use both; events are for deep-dive only.

## session-events

Inspect events within a session. `--action` is required (list/details/search); `--session-id` requires the `devin-` prefix.

### `--action list` — paginated summaries

Filter with `--categories`, repeated for several (`--categories git --categories message`); a comma-separated value is not split. `--event-types` filters by event type instead, and `--direction incoming|outgoing` by direction.

Valid `--categories` values: `shell`, `file`, `search`, `browser`, `mcp`, `git`, `message`, `status`, `secret`, `todo`, `recording`, `knowledge`, `playbook`, `webhook`, `lifecycle`, `other`.

**Avoid `--categories "status"` — 90 %+ of events are `simple_activity_update` noise.** A 30-minute session produces 500+ status events. Useful categories for read tasks: `message`, `playbook`, `git`, `mcp`.

Pagination: `--first N` (default 50, max 100), `--after <cursor>`.

```bash
# Dump to a file and grep/jq — never print raw to the terminal
devin-mcp session-events --action list --session-id "devin-<hex>" \
    --categories playbook --categories git --first 100 > /tmp/events-playbook-git.txt
```

### `--action details` — full event content

Two modes (mutually exclusive):
- `--event-ids <id1> --event-ids <id2>` — fetch up to 20 specific events by ID.
- `--offset N --limit N` — 0-based range fetch (max 50 per call).

`--max-content-length N` bounds large content fields (default 10 000 chars).

### `--action search` — full-text search

Requires `--query <text>`.

## session-gather

**Blocking wait, not an output reader.** Polls up to 50 sessions until each reaches a settled state (exit / suspended / error / waiting_for_user / waiting_for_approval). Use only after spawning child sessions when you need to block until they finish — do not use it to read a finished session's results.

`structured_output` visible in the gather response is stale self-reported JSON and is not authoritative. Use `session-interact --action get` for current state.

It waits up to `--timeout-seconds` (default 300). Keep that below your shell's timeout (the Bash tool's default is 120 s), or raise the Bash timeout for the call.

```bash
devin-mcp session-gather \
    --session-ids "devin-<id1>" --session-ids "devin-<id2>" \
    --timeout-seconds 100 --poll-interval-seconds 30
```

## Recipe: read and summarize a session from its web URL

```bash
# Step 1: convert the URL to a CLI session ID
#   https://<host>/sessions/0123456789abcdef0123456789abcdef
#                                   ↓ prepend "devin-"
SESSION="devin-0123456789abcdef0123456789abcdef"

# Step 2: get metadata + structured output (richest for automated/playbook sessions)
devin-mcp session-interact --action get --session-id "$SESSION" > /tmp/session-get.txt

# Step 3: read the message conversation (initiating prompt + Devin's updates)
devin-mcp session-interact --action get_messages --session-id "$SESSION" > /tmp/session-messages.txt

# Step 4 (optional): dig into events for specific categories
devin-mcp session-events --action list --session-id "$SESSION" \
    --categories playbook --categories git --first 100 > /tmp/session-events.txt
```

**Dead ends to avoid:**
- `session-gather` — blocks waiting for sessions to settle; useless for reading a finished one.
- `--categories "status"` on events — almost entirely `simple_activity_update` noise.
- `--limit N` on search — the flag does not exist; use `--first N`.
- `--categories "message,git"` — a comma-separated value is not split; repeat the option.
- `--include-bot-sessions true` — booleans take no value; use `--include-bot-sessions` or `--no-include-bot-sessions`.

## Output-size warnings

| Command | Typical volume | How to bound it |
|---|---|---|
| `session-interact --action get` | Medium; `structured_output` can be very large for playbook runs | Always redirect to a file |
| `session-interact --action get_messages` | Small (3–10 messages typical) | `--first` if needed |
| `session-events --action list` (unfiltered) | Massive — 500+ events for a 30-min session | Always `--categories` + `--first 100`; dump to file, then `jq`/`grep` |
| `session-events --action details` | Per-event full content | `--limit` (max 50) + `--max-content-length` |
| `session-search` | Small by default (20 results) | `--first` up to 100 |
