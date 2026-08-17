# Schedules Reference

Schedules run Devin sessions on a recurring basis. One tool manages them.

Confirm the exact action names and options with `devin-mcp devin_schedule_manage --help`.

## devin_schedule_manage

List, get, create, or update scheduled runs.

```bash
# List schedules
devin-mcp devin_schedule_manage --action list

# Get one schedule
devin-mcp devin_schedule_manage --action get --id <schedule-id>

# Create a schedule (the prompt body can come from a file)
devin-mcp devin_schedule_manage --action create \
  --name "Nightly dependency check" \
  --prompt "$(cat /tmp/schedule-prompt.md)"

# Update a schedule
devin-mcp devin_schedule_manage --action update --id <schedule-id> \
  --prompt "$(cat /tmp/schedule-prompt.md)"
```

Cron or interval fields, if supported, appear in `--help`. Use the content-preparation workflow for long prompts.
