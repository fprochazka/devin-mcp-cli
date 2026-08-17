# Repos and Docs Reference

These tools discover integrations and repositories, and read repository documentation. They help Devin (and you) understand a codebase before acting.

Confirm exact options with `devin-mcp <command> --help`.

## list_integrations

List the integrations connected to the account (source control, issue trackers, and so on).

```bash
devin-mcp list_integrations
```

## list_available_repos

List repositories Devin can access for the selected account.

```bash
devin-mcp list_available_repos
devin-mcp list_available_repos --json
```

## read_wiki_structure

Read the structure (table of contents) of a repository's generated wiki or docs.

```bash
devin-mcp read_wiki_structure --repo <owner/name>
```

## read_wiki_contents

Read the contents of a repository's wiki or docs.

```bash
devin-mcp read_wiki_contents --repo <owner/name>
```

## ask_question

Ask a natural-language question about a repository and get an answer grounded in its docs and code.

```bash
devin-mcp ask_question --repo <owner/name> --question "How is auth configured?"

# Long question
devin-mcp ask_question --repo <owner/name> --question "$(cat /tmp/question.md)"
```
