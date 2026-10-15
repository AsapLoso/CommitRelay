# Why CommitRelay exists

## A specific problem, not a new messaging protocol

We wanted an AI agent to generate a weekly Markdown article, store it in a private Git repository, and let a Telegram bot deliver **only the article**, never the personal notes above its `---` separator. Revising those private notes should not resend the article.

A second possible use case is monitoring a collaborator's changes in selected code directories. That would require per-commit diffs and push-event handling, **not implemented yet**.

## Research before implementation

The ecosystem already contains stronger solutions for many individual tasks:

- **[Git](https://git-scm.com/)** for versioned files and local hooks.
- **[GitHub Actions](https://docs.github.com/en/actions)** for triggers within the repository hosting a workflow.
- **[Apprise](https://github.com/caronc/apprise)** for sending notifications to many services without writing Telegram/Discord HTTP clients.
- **[tj-actions/changed-files](https://github.com/tj-actions/changed-files)** and **[dorny/paths-filter](https://github.com/dorny/paths-filter)** for change and path detection within GitHub Actions.
- **[Probot](https://github.com/probot/probot)** for building hosted GitHub Apps and receiving webhooks.
- **[n8n](https://n8n.io/)** if a visual general-purpose automation system fits better.

See [Related tools](RELATED_TOOLS.md) and [External trigger research](EVENT_TRIGGERS.md) for fuller comparisons.

## The integration we chose to write

CommitRelay is intended to be the small, configuration-driven piece **between** source control and a notification library:

1. Select files from a source repo and folder.
2. Execute an explicitly trusted local parser (or no parser).
3. Suppress delivery if it returns `None`, fails, or produces the same publishable content as the previous successful delivery.
4. Delegate transport to **Apprise**, rather than manually implementing provider protocols.
5. Record a success checkpoint so later checks can skip unchanged results.

This is also a hands-on learning project. Integrating reliable existing tools, reading documentation, understanding their limitations, writing small adapters and tests, and documenting the trade-offs are valid engineering work. We should **credit the upstream projects** and avoid implying that they were authored here.

## What has been built vs. what remains

**Built in the current repository:** Python CLI and YAML examples; local Git and GitHub snapshot readers; trusted parser interface; parsed-output hashing and local SQLite checkpoints; an **Apprise-backed Telegram transport** with offline adapter tests.

**Unverified or unfinished:** actual Telegram end-to-end delivery, automatic external push notifications, a secure hosted webhook receiver, durable hosted checkpoints, quiet-hours queue, per-commit diff forwarding, and a release. No automatic hosted message sender has been activated.

## Portfolio-friendly one-sentence description

> CommitRelay is a small open-source integration project born from an agentic writing workflow: it combines Git-based file monitoring, configurable Python content filtering, delivery checkpoints and Apprise notifications—reusing established tools instead of rewriting them.

This accurately describes the intent and implementation stage, without inflating authorship or production readiness.
