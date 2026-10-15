# CommitRelay

**Turn Git commits and file changes into messages and actions. No AI-specific hooks required.**

CommitRelay is an emerging, CLI-first, agent-friendly automation tool. An AI agent, a script, or a human can produce a file and commit it to a repository; CommitRelay is intended to detect the change, optionally transform its content, and dispatch it to a destination such as Telegram.

## Why this is useful for agentic work

Your agent already knows how to write files and use Git. It should not need to know Telegram APIs, webhook payloads, or your credentials. **The repository becomes the integration boundary.**

- **Git-native:** commits and paths can act as signals; no LLM-specific SDK or custom AI hooks.
- **Agent-independent:** works with any agent, IDE, CI process, script, or human that produces repository changes.
- **Configurable:** one YAML per sync, selected source folder, parser and enabled destinations.
- **Privacy-aware:** run a trusted parser before sending anything; a parser may intentionally return no output.
- **Extensible:** start with Telegram; add other destinations as they are actually implemented.
- **Self-hostable:** Python-based CLI and GitHub Actions integration, without a proprietary hosted service.

A local Git `post-commit` or `post-push` hook can invoke the CLI **when configured**. For hosted repositories, GitHub Actions can react to pushes without installing local hooks. A commit on a local branch does *not* automatically become a GitHub Actions event until pushed.

## Project status

**Work in progress.** This repository currently contains project documentation; the CLI, watchers, checkpoint store, parsers and Telegram adapter are being implemented. No automatic deliveries are enabled. Do not put credentials or private content in this public repository.

## Planned CLI

```sh
commitrelay --help
commitrelay add [name]              # Guided setup
commitrelay list                    # Configurations and validation status
commitrelay edit [name]             # Pick from a numbered menu if omitted
commitrelay doctor                  # Diagnostics; optionally test messaging
commitrelay doctor -n               # Diagnostics, never send
commitrelay doctor -y --telegram    # Test only configured Telegram
commitrelay doctor -y --all         # Test all configured implemented destinations
commitrelay run --all --dry-run     # Preview what would be sent
```

The interface is designed to support both a local clone and unattended GitHub Actions. Each configuration will live in `configs/`, with distinct source and destination settings, and each successfully sent parsed content hash will be checkpointed.

## CLI-first credential setup

Using GitHub CLI (commands to be run from the repository where Actions executes):

```sh
gh auth login
gh secret set TELEGRAM_BOT_TOKEN
gh secret set TELEGRAM_CHAT_ID
gh secret list
```

GitHub web alternative (**not tested by this project**): repository **Settings → Secrets and variables → Actions → New repository secret**.

Secrets never belong in repository files. GitHub Actions runs require explicit permission to read any private source repositories.

## Architecture (target)

```text
Git commit / push / external repository watcher
                  |
             Sync YAML
                  |
         Python dispatcher
           /           \
  content parser    checkpoint
           \           /
          Telegram adapter
```

GitHub Actions is the scheduler/runner; Python owns routing, parsing, retries and dispatch. A persistent state store is needed for deduplication on ephemeral GitHub-hosted runners.

## Contributing

This project is at an early stage. The initial goal is a working, tested Telegram vertical slice; other integrations and external repository watchers follow after that.
