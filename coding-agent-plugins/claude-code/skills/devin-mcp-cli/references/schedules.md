# Schedules Reference

Schedules run Devin sessions on a recurring basis. `schedule-manage` is deprecated in favour of `automation-manage`, which runs sessions fired by schedules, webhooks and integrations. Prefer automations for new work; use `schedule-manage` to read or change existing schedules.

Confirm the exact options with `devin-mcp schedule-manage --help` and `devin-mcp automation-manage --help`.

## schedule-manage

`--action`: `list`, `get`, `create`, `update`, `delete`.

```bash
# List schedules
devin-mcp schedule-manage --action list

# Get one schedule
devin-mcp schedule-manage --action get --schedule-id <schedule-id>

# Create a schedule (the prompt body can come from a file)
devin-mcp schedule-manage --action create --name "Nightly dependency check" \
  --frequency "0 3 * * *" --arg-file prompt=/tmp/schedule-prompt.md

# Disable a schedule
devin-mcp schedule-manage --action update --schedule-id <schedule-id> --no-enabled
```

## automation-manage

`--action` has many values (`list`, `get`, `templates`, `create`, `validate_create`, `update`, `run`, ...); read `devin-mcp automation-manage --help` before using it. Triggers, actions and settings are JSON objects, so pass a create or update as one JSON file with `--input-json @/tmp/automation.json`, and check it with `validate_create` / `validate_update` first.

```bash
devin-mcp automation-manage --action list
devin-mcp automation-manage --action get --automation-id <automation-id>
```
