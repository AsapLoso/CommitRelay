# Related tools: choose what fits

_Reviewed 15 October 2026. This is not an exhaustive market survey, and linked projects may evolve._

**Please use a different tool if it already solves your problem better.** CommitRelay is an experimental, Git-native file-to-message bridge. The point is to reduce glue code in agentic workflows, not to reinvent every notification or automation library.

## When another tool is a better choice

| Alternative | Best when | What it already provides | How it differs from CommitRelay |
| --- | --- | --- | --- |
| [appleboy/telegram-action](https://github.com/appleboy/telegram-action) | You already have a GitHub Actions workflow and only want to send Telegram messages | A ready-made Action accepting Telegram token, destination and message | It handles delivery directly; for arbitrary file-content filtering or deduplication, compose it with other tools. |
| [Apprise](https://github.com/caronc/apprise) | Your main need is a Python **notification library** supporting many destinations | Unified API and CLI covering Telegram, Discord, Slack and many more; attachments | It is a strong option to use **inside** a custom dispatcher instead of writing adapters yourself. |
| [Shoutrrr](https://github.com/containrrr/shoutrrr) and [Shoutrrr Action](https://github.com/containrrr/shoutrrr-action) | You work in Go or prefer URL-configured notification endpoints from Actions | Multi-service notification library, CLI and GitHub Action | Prefer it for general notifications; CommitRelay's extra concern is source selection and parsed file content. |
| [ntfy](https://github.com/binwiederhier/ntfy) | You only want a push notification on your phone or desktop | HTTP PUT/POST, CLI, mobile apps, self-hosting option | Often far simpler than managing a Telegram bot or full dispatcher. Pay attention to topic privacy and authentication. |
| [n8n](https://n8n.io/) | You want a visual workflow builder or complex multi-service integrations | Workflow editor with [Telegram message sending](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.telegram/message-operations/) and many other integrations | Prefer it when the workflow as a whole matters more than minimal Git/Python configuration. |
| [Pipedream](https://pipedream.com/) | You want a managed event-driven integration service | Hosted integration and workflow building | Consider it if you'd rather use hosted orchestration than maintain this repository. Check its pricing and provider support for your use case. |
| [tj-actions/changed-files](https://github.com/tj-actions/changed-files) | You need lists of added/modified/deleted files inside GitHub Actions | Path and change-status detection | Combine it with a normal Action to send changed files; CommitRelay shouldn't duplicate its job unnecessarily. |
| [dorny/paths-filter](https://github.com/dorny/paths-filter) | You only want certain jobs/steps to run for selected paths | Path-based conditional execution | Often enough if you don't need custom parsing, checkpoints, or external source polling. |
| [GitHub Actions itself](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) | All you need is a job on push or a schedule in the same repository | Native `on: push`, path filters, scheduling and workflows | A small shell/Python step can be simpler and more reliable than installing a new framework. |

**These are alternatives, not claimed drop-in equivalents.** Some are libraries, some GitHub Actions, and some hosted automation products. Requirements such as private-repository access, attachment size, privacy filters, rate limits, storage and hosting can change the trade-offs.

## When CommitRelay may be worth trying

The particular combination we are developing is:

1. An independent program or AI agent creates a report as a committed file; it never needs Telegram credentials or a model-specific hook.
2. A declarative sync selects a repository, folder and filename pattern.
3. A **trusted local Python parser** optionally emits publishable content or returns `None`. A parser error fails closed rather than sending the original file.
4. A stored digest of the **parsed** result prevents sending the same content again when only private comments or other excluded material change.
5. A destination adapter sends content (currently only Telegram).

This can help when the *files themselves* are the integration contract. It is not required when GitHub Actions plus a Telegram Action, or Apprise, already meets the need.

## Implementation status and limitations

**Present in the project:** Python CLI, local Git and GitHub snapshot readers, trusted parsers, Telegram transport, local SQLite-based parsed-content hash checkpoints and manual diagnostics.

**Not production-ready:** persistent hosted state across ephemeral runners, automatic external GitHub repository triggers, commit-by-commit replay, robust retry/locking and exactly-once guarantees. Automatic hosted Telegram delivery remains disabled.

If you need automatic, production-ready hosted delivery now, use an established workflow product or Actions combination above instead of relying on these unfinished capabilities.

## Feature suggestions

If you find a tool doing this better, or want an interoperability adapter, please [open a feature-request issue](https://github.com/AsapLoso/CommitRelay/issues/new?template=feature_request.md) with your use case and a link. An actual code change belongs in a normal pull request, not the feature-request issue template.
