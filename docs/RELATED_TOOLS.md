# Related projects and positioning

_Initial landscape check: 15 October 2026. Non-exhaustive; verify the current feature sets before making comparisons in releases or marketing._

CommitRelay is **not** the first Git-triggered notification tool. Several mature and specialized solutions already solve overlapping problems. The design opportunity is to expose **committed file content as an integration interface**, with a user-defined parser and a checkpoint of the **transformed output** rather than only a notification about a commit or CI job.

| Tool | What it already does | What CommitRelay is trying to make simpler |
| --- | --- | --- |
| [an3park/telegram-action](https://github.com/marketplace/actions/telegram-notification-action) | Sends texts and documents to Telegram from GitHub Actions, usually for workflow notifications | Monitor configured source folders, parse files safely, compare delivered content hashes |
| [tj-actions/changed-files](https://github.com/tj-actions/changed-files) | Detects changed paths and file statuses in GitHub Actions | Read **file contents** and deliver transformed bodies rather than only producing lists of paths |
| [n8n](https://n8n.io/) | Connects GitHub events and Telegram via customizable workflow nodes | Small Python/CLI-first alternative with Git-native configuration; n8n is a viable existing solution |
| [Pipedream](https://pipedream.com/apps/github/integrations/slack-v2) | Offers GitHub commit triggers and many destination integrations | Local/self-operated agent-output pipeline with trusted custom parsers and file-content checkpoints |
| [ntfy](https://github.com/binwiederhier/ntfy) | Lightweight notifications and GitHub webhook integration | Focus on translating repository artifacts, not just generic notifications |

**Useful existing building blocks:** Don't reinvent file-change detection or Telegram transport unnecessarily. Consider interoperating with existing GitHub Actions, or offering a reusable action that can be invoked in the originating repository.

## What is actually implemented today?

- Python CLI and YAML sync configuration examples
- Local Git and GitHub **snapshot** reading (not per-commit replay)
- Optional trusted local parser; `None` means no delivery
- Parsed-content SHA-256 tracking in **local SQLite**
- Telegram sending; diagnostics/test pathway

**Not yet production-ready:** durable checkpoint backend for hosted runners, cross-repository event triggers, webhook installation, robust retries and exactly-once guarantees. The existing GitHub workflow is manual-only. Comparisons must not describe these as completed features.

## Specific product distinction to test

A weekly article may have private comments at the beginning and publishable Markdown after a separator. A bot should send the **publishable article only**; a later edit to private comments should not trigger a new message. CommitRelay's parser + output hash supports this scenario locally today.

Another worthwhile use case is an AI agent creating a report in Git and not needing to know credentials or provider-specific messaging APIs. A native Git hook can invoke CommitRelay locally; hosted external-repo watching remains planned.

## Feature requests

Found an alternative doing this better? Please [open a feature request](https://github.com/AsapLoso/CommitRelay/issues/new?template=feature_request.md) with a link and a concrete example. This will help avoid duplicating functionality already well served elsewhere.
