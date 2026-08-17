# Knowledge Reference

Knowledge notes give Devin persistent context (conventions, facts, how a codebase works). One tool manages them.

Confirm the exact action names and options with `devin-mcp devin_knowledge_manage --help`.

## devin_knowledge_manage

List, get, create, or update knowledge notes.

```bash
# List knowledge notes
devin-mcp devin_knowledge_manage --action list

# Get one note
devin-mcp devin_knowledge_manage --action get --id <note-id>

# Create a note (write the body to a file first)
devin-mcp devin_knowledge_manage --action create \
  --title "Deploy process" \
  --body "$(cat /tmp/note.md)"

# Update a note
devin-mcp devin_knowledge_manage --action update --id <note-id> \
  --body "$(cat /tmp/note.md)"
```

Use the content-preparation workflow for the body.
