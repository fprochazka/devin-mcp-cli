# Sessions Reference

Sessions are the core Devin unit of work. A session runs from a prompt, produces events, and can be replied to while it runs.

The exact options come from the live server. Always confirm with `devin-mcp <command> --help`.

## Session IDs and the `devin-` prefix

Web URL format: `https://<host>/sessions/<32-hex>` — the CLI session ID is `devin-<32-hex>` (just prepend `devin-`).

`devin_session_search` returns IDs **without** the prefix in its results. Every other command (`devin_session_interact`, `devin_session_events`, `devin_session_gather`) requires the `devin-` prefix on input. `devin_session_interact` additionally accepts bare IDs when referencing `child_session_ids` values from a `get` response.

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

List or search existing sessions. All filters are optional and combined with AND.

```bash
devin-mcp devin_session_search --first 20 --json
devin-mcp devin_session_search --session-ids "devin-<hex>" --json   # look up one specific session
devin-mcp devin_session_search --tags "knowledge-cleanup" --origins "scheduled"
```

**There is no `--limit` flag.** Pagination uses `--first N` (default 20, max 100) and `--after <cursor>` from the previous page's `end_cursor`.

Verified filter flags: `--session-ids`, `--tags`, `--playbook-id`, `--origins`, `--schedule-id`, `--created-after`, `--created-before`, `--updated-after`, `--updated-before` (Unix timestamps), `--user-ids`, `--parent-session-id`.

Valid `--origins` values: `webapp`, `slack`, `teams`, `api`, `linear`, `jira`, `scheduled`, `cli`, `other`.

## devin_session_interact

Multi-action command — `--action` is required. Covers reading sessions, sending replies, and lifecycle operations. `--session-id` requires the `devin-` prefix.

| Action | What it does |
|---|---|
| `get` | Full session details: title, status, status_detail, ACUs consumed, tags, `child_session_ids`, `pull_requests`, `structured_output` |
| `get_messages` | Paginated message conversation — the initiating prompt plus Devin's status messages. Long bodies are truncated; fetch a full body via `devin_session_events --action details --event-ids <event_id>` |
| `message` | Send a reply into the session (resumes it if sleeping). Requires `--message`. |
| `get_attachments` | List attachments (not paginated — full list returned). |
| `set_tags` | Replace all tags on the session. Requires `--tags '["tag1","tag2"]'`. Full replacement, not append. |
| `sleep` / `terminate` / `archive` / `unarchive` | Lifecycle actions. |

Pagination for `get_messages`: `--first N`, `--after <cursor>`.

```bash
# Read a finished session — start here
devin-mcp devin_session_interact --action get --session-id "devin-<hex>" --json

# Read the message conversation
devin-mcp devin_session_interact --action get_messages --session-id "devin-<hex>" --json

# Reply into a running session
devin-mcp devin_session_interact --action message --session-id "devin-<hex>" \
    --message "$(cat /tmp/reply.md)"
```

**Where the content lives:** for automated and playbook sessions, `structured_output` (from `get`) holds the richest machine-readable run manifest — often more information-dense than the message conversation. `get_messages` holds the human-readable narrative (typically 3–5 messages). Use both; events are for deep-dive only.

## devin_session_events

Inspect events within a session. `--action` is required (list/details/search); `--session-id` requires the `devin-` prefix.

### `--action list` — paginated summaries

Filter with `--categories` (single value per call — a comma-separated list is rejected with an error):

Valid `--categories` values: `shell`, `file`, `search`, `browser`, `mcp`, `git`, `message`, `status`, `secret`, `todo`, `recording`, `knowledge`, `playbook`, `webhook`, `lifecycle`, `other`.

**Avoid `--categories "status"` — 90 %+ of events are `simple_activity_update` noise.** A 30-minute session produces 500+ status events. Useful categories for read tasks: `message`, `playbook`, `git`, `mcp`.

Pagination: `--first N` (default 50, max 100), `--after <cursor>`.

```bash
# One category per call; dump to a file and grep/jq — never print raw to the terminal
devin-mcp devin_session_events --action list --session-id "devin-<hex>" \
    --categories "playbook" --first 100 --json | tee /tmp/events-playbook.json

devin-mcp devin_session_events --action list --session-id "devin-<hex>" \
    --categories "git" --first 100 --json | tee /tmp/events-git.json
```

### `--action details` — full event content

Two modes (mutually exclusive):
- `--event-ids <id1> <id2>` — fetch up to 20 specific events by ID.
- `--offset N --limit N` — 0-based range fetch (max 50 per call).

`--max-content-length N` bounds large content fields (default 10 000 chars).

### `--action search` — full-text search

Requires `--query <text>`.

## devin_session_gather

**Blocking wait, not an output reader.** Polls up to 50 sessions until each reaches a settled state (exit / suspended / error / waiting_for_user / waiting_for_approval). Use only after spawning child sessions when you need to block until they finish — do not use it to read a finished session's results.

`structured_output` visible in the gather response is stale self-reported JSON and is not authoritative. Use `devin_session_interact --action get` for current state.

```bash
devin-mcp devin_session_gather \
    --session-ids "devin-<id1>" "devin-<id2>" \
    --timeout-seconds 300 --poll-interval-seconds 30
```

## Recipe: read and summarize a session from its web URL

```bash
# Step 1: convert the URL to a CLI session ID
#   https://<host>/sessions/0123456789abcdef0123456789abcdef
#                                   ↓ prepend "devin-"
SESSION="devin-0123456789abcdef0123456789abcdef"

# Step 2: get metadata + structured output (richest for automated/playbook sessions)
devin-mcp devin_session_interact --action get --session-id "$SESSION" --json \
    | tee /tmp/session-get.json

# Step 3: read the message conversation (initiating prompt + Devin's updates)
devin-mcp devin_session_interact --action get_messages --session-id "$SESSION" --json \
    | tee /tmp/session-messages.json

# Step 4 (optional): dig into events for specific categories — one category per call
devin-mcp devin_session_events --action list --session-id "$SESSION" \
    --categories "playbook" --first 100 --json | tee /tmp/session-events-playbook.json

devin-mcp devin_session_events --action list --session-id "$SESSION" \
    --categories "git" --first 100 --json | tee /tmp/session-events-git.json
```

**Dead ends to avoid:**
- `devin_session_gather` — blocks waiting for sessions to settle; useless for reading a finished one.
- `--categories "status"` on events — almost entirely `simple_activity_update` noise.
- `--limit N` on search — the flag does not exist; use `--first N`.
- `--categories "message,git"` — comma-separated list is rejected; make one call per category.

## Output-size warnings

| Command | Typical volume | How to bound it |
|---|---|---|
| `devin_session_interact --action get` | Medium; `structured_output` can be very large for playbook runs | Always `tee` to a file |
| `devin_session_interact --action get_messages` | Small (3–10 messages typical) | `--first` if needed |
| `devin_session_events --action list` (unfiltered) | Massive — 500+ events for a 30-min session | Always `--categories` + `--first 100`; dump to file, then `jq`/`grep` |
| `devin_session_events --action details` | Per-event full content | `--limit` (max 50) + `--max-content-length` |
| `devin_session_search` | Small by default (20 results) | `--first` up to 100 |
