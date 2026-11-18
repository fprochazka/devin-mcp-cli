# Repos, Docs and Organization Reference

These tools discover integrations, settings, users and repositories, and read repository documentation from DeepWiki. They help Devin (and you) understand a codebase before acting. All of them only read, except `generate-wiki`.

Confirm exact options with `devin-mcp <command> --help`.

## list-integrations

List the native integrations and MCP servers of the organization, with status and settings or install URLs.

```bash
devin-mcp list-integrations
devin-mcp list-integrations --filter installed --query github
```

## find-setting

Find a Devin webapp setting and get a deep link to it.

```bash
devin-mcp find-setting --query "api keys"
```

## user-list

List the organization's users, paginated with `--first` and `--after`.

```bash
devin-mcp user-list --email someone@example.com
```

## list-wiki-repos

List the repositories that have a DeepWiki index.

```bash
devin-mcp list-wiki-repos
```

## read-wiki-structure

Read the table of contents of a repository's DeepWiki. A repository without an index fails with exit code 1.

```bash
devin-mcp read-wiki-structure --repo-name <owner/name>
```

## read-wiki-contents

Read the documentation of a repository.

```bash
devin-mcp read-wiki-contents --repo-name <owner/name> > /tmp/wiki.md
```

## ask-wiki-question

Ask a natural-language question about a repository and get an answer grounded in its docs and code.

```bash
devin-mcp ask-wiki-question --repo-name <owner/name> --question "How is auth configured?"

# Long question
devin-mcp ask-wiki-question --repo-name <owner/name> --arg-file question=/tmp/question.md
```

## generate-wiki

Starts wiki generation for a repository. It writes, so it asks for permission.
