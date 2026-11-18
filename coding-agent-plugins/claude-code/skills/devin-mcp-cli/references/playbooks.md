# Playbooks Reference

Playbooks are reusable instructions Devin can follow. One tool manages them through `--action` (`list`, `get`, `create`, `update`, `delete`).

Confirm the exact options with `devin-mcp playbook-manage --help`.

## playbook-manage

```bash
# List playbooks
devin-mcp playbook-manage --action list

# Get one playbook
devin-mcp playbook-manage --action get --playbook-id <playbook-id>

# Create a playbook (write the content to a file first)
devin-mcp playbook-manage --action create --title "Release checklist" --arg-file content=/tmp/playbook.md

# Update a playbook (a full replace: pass the whole content)
devin-mcp playbook-manage --action update --playbook-id <playbook-id> --arg-file content=/tmp/playbook.md
```

Use the content-preparation workflow for the content. `--body` is a deprecated alias of `--content`. Short fields (title, id, action) can be passed inline.
