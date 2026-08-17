# Playbooks Reference

Playbooks are reusable instructions Devin can follow. One tool manages them through an action parameter.

Confirm the exact action names and options with `devin-mcp devin_playbook_manage --help`.

## devin_playbook_manage

List, get, create, or update playbooks. The operation is usually chosen by an `action` (or similar) input.

```bash
# List playbooks
devin-mcp devin_playbook_manage --action list

# Get one playbook
devin-mcp devin_playbook_manage --action get --id <playbook-id>

# Create a playbook (write the body to a file first)
devin-mcp devin_playbook_manage --action create \
  --title "Release checklist" \
  --body "$(cat /tmp/playbook.md)"

# Update a playbook
devin-mcp devin_playbook_manage --action update --id <playbook-id> \
  --body "$(cat /tmp/playbook.md)"
```

Use the content-preparation workflow for the body. Short fields (title, id, action) can be passed inline.
