# Knowledge Reference

Knowledge notes give Devin persistent context (conventions, facts, how a codebase works). One tool manages them through `--action`: `list`, `get`, `create`, `update`, `delete`, `folders`, and the suggestion actions `list_suggestions`, `view_suggestion`, `dismiss_suggestions`.

Confirm the exact options with `devin-mcp knowledge-manage --help`.

## knowledge-manage

```bash
# List knowledge notes, optionally filtered
devin-mcp knowledge-manage --action list --search deploy

# Get one note
devin-mcp knowledge-manage --action get --note-id <note-id>

# Create a note (write the content to a file first); --trigger says when Devin should recall it
devin-mcp knowledge-manage --action create --name "Deploy process" \
  --trigger "When deploying the backend" --arg-file content=/tmp/note.md

# Update a note
devin-mcp knowledge-manage --action update --note-id <note-id> --arg-file content=/tmp/note.md
```

Use the content-preparation workflow for the content. `--body` is a deprecated alias of `--content`.
