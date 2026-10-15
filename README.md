# CommitRelay

**Your agent already knows Git. Make a commit; deliver the result.**

CommitRelay converts files from Git repositories into messages **without AI-specific plugins or messaging code in the agent**. A human, a cron job, a local script or any coding agent writes a report, commits it, and CommitRelay reads selected files, transforms them with an optional trusted parser, and delivers changed output to Telegram.

The file is the interface; Git is the audit trail. This makes CommitRelay particularly useful in agentic workflows, without coupling it to one LLM or vendor.

That mysteriously quiet co-author who slips a *"tiny cleanup"* commit under the rug? CommitRelay can notice that too. It won't judge the commit — just what changed.

## Example project: a personal research messenger

*An illustrative use case — not a claim that automatic external triggering works yet.*

Imagine keeping all your work in **one private GitHub repository**, with several independent agents contributing files:

1. **Every evening**, an agent writes tomorrow's Orthodox calendar readings into a dated Markdown report.
2. **Every Saturday**, another agent writes a longer research article. The file contains personal annotations above a `---` divider and the shareable article below.
3. **Whenever either agent commits an update**, you want the relevant content delivered to your Telegram chat — without copying text, giving the agents Telegram credentials, or exposing private annotations.
4. **If only the private annotations change**, no new message should be sent. If the actual article or reading guide changes, deliver the updated content.
5. **If an event is missed**, a scheduled check could catch up using saved delivery history.

The agents only need Git. A CommitRelay installation would use **two sync configurations, two content-selection policies, and one Telegram destination**. It would check the parsed content rather than assuming every changed commit deserves a message.

This illustrates the intended end-to-end experience: *agent writes file → Git tracks it → CommitRelay selects and transforms it → Telegram receives the useful part*. It is also applicable to coding-agent status reports, experiment results, build artifacts and other machine-generated files.

**What works today:** reading committed files from a local or external GitHub repository when the CLI runs, filtering with trusted Python parsers, comparing transformed-content hashes in local SQLite, and sending through the Telegram adapter. **What does not work yet:** automatically reacting to external GitHub pushes from a central installation, maintaining durable checkpoints across GitHub-hosted runners, and automatically scheduling catch-up jobs. See [Architecture and roadmap](docs/ARCHITECTURE.md).

> **Status: v0.1 development, not a release.** CLI, local Git and GitHub snapshot readers, pluggable Python parsers, Telegram delivery and local SQLite checkpoints have been implemented. **Automated hosted dispatch is OFF** while durable state and full end-to-end testing are unfinished.

## Before installing: consider these alternatives

CommitRelay is not necessarily the best choice. If you need something that already works end to end, these established tools may be a better fit **today**:

| Your goal | Consider instead | Why |
| --- | --- | --- |
| Send a Telegram message from an existing GitHub workflow | [appleboy/telegram-action](https://github.com/appleboy/telegram-action) | A purpose-built GitHub Action; no new dispatcher needed. |
| Send notifications to Telegram, Discord, email, and many others from Python | [Apprise](https://github.com/caronc/apprise) | Mature multi-service Python library and CLI; better if delivery integrations are the main requirement. |
| Send notifications from Go or GitHub Actions | [Shoutrrr](https://github.com/containrrr/shoutrrr) | Existing Go notification library and [GitHub Action](https://github.com/containrrr/shoutrrr-action). |
| Send simple phone/desktop push notifications without maintaining a Telegram bot | [ntfy](https://github.com/binwiederhier/ntfy) | A small HTTP POST or CLI command may be all you need. |
| Build a complete automation visually, with GitHub and Telegram connections | [n8n](https://n8n.io/) | Existing workflow editor and integrations; more suitable if you want a visual automation platform. |
| Trigger only when particular files change in GitHub Actions | [dorny/paths-filter](https://github.com/dorny/paths-filter) or [tj-actions/changed-files](https://github.com/tj-actions/changed-files) | They solve path filtering and change detection without another watcher. |

**Where CommitRelay aims to fit:** file-content delivery with trusted transforms, content-level deduplication, a Git-friendly CLI, and configurable sources. This is still early software; its hosted cross-repository workflow is **not ready yet**. We would rather link you to a more suitable tool than have you depend on an unfinished feature.

For a more detailed comparison and other tools, see [Related tools and honest alternatives](docs/RELATED_TOOLS.md).

## Why use it?

- **Agent-agnostic:** any agent or program that commits a file can produce content.
- **YAML-driven:** one sync config defines a local or GitHub source, folder, pattern, parser and Telegram on/off.
- **Privacy-aware:** a parser can redact sections, extract a table, or return `None` (send nothing). Errors never fall back to raw content.
- **Content deduplication:** store a hash of the *parsed result*, not raw file bytes. A private comment edit need not trigger another delivery.
- **Local or hosted:** use a Git post-commit hook locally; GitHub API polling is implemented for remote sources. Hosted cross-repository triggers are planned.
- **CLI-first:** guided setup, diagnose, preview and test delivery, all without a web UI.

## Install

Requires Python 3.10+, Git, and optionally the GitHub CLI (`gh`). A standalone executable is **not** required.

**Option A: clone and develop (recommended at this stage)**

~~~bash
git clone https://github.com/AsapLoso/CommitRelay.git
cd CommitRelay
python -m pip install -e .
commitrelay --help
~~~

`-e` installs the local code in editable mode. Use normal `git add`, `git commit` and `git push` when you change it; there is no special CommitRelay command needed to push.

**Option B: install Python package directly from GitHub**

~~~bash
python -m pip install "git+https://github.com/AsapLoso/CommitRelay.git"
commitrelay --help
~~~

It also works without installing a global command from a checkout using `python -m commitrelay --help`. If you install from GitHub without cloning, create your own working directory containing `configs/` and `jobs/` and run it from there.

## Telegram credentials

Create your bot with [@BotFather](https://t.me/BotFather), open its chat and press **Start**, then obtain the numeric destination chat ID. **Never commit the token or chat ID.**

**Local Bash example** (the token is entered without appearing in shell history):

~~~bash
read -rs -p "Telegram bot token: " TELEGRAM_BOT_TOKEN; echo
export TELEGRAM_BOT_TOKEN
read -r -p "Telegram chat ID: " TELEGRAM_CHAT_ID
export TELEGRAM_CHAT_ID
commitrelay doctor -n
commitrelay doctor -y --telegram
~~~

The first doctor call diagnoses without sending. The second sends exactly one harmless test message, never a private report.

**GitHub Actions: CLI setup** from the repository where an Action would run:

~~~bash
gh auth login
gh secret set TELEGRAM_BOT_TOKEN
gh secret set TELEGRAM_CHAT_ID
gh secret list
~~~

`gh secret set` prompts for the values. `gh secret list` displays secret names, not values. GitHub web alternative (**not tested by this project**): Settings → Secrets and variables → Actions → New repository secret.

Default environment-variable names may be overridden via `COMMITRELAY_TELEGRAM_TOKEN_ENV` and `COMMITRELAY_TELEGRAM_CHAT_ENV`, which contain *names* of credential variables, not their values.

For private GitHub source repos, use a **read-only fine-grained token** in `COMMITRELAY_GITHUB_TOKEN`, scoped only to the needed source repo (or set `source.token_env` in a sync YAML).

## Create your first sync

~~~bash
commitrelay add
commitrelay add orthodox-readings
commitrelay list
commitrelay edit          # Choose an existing name by number
commitrelay enable orthodox-readings
~~~

The wizard asks: source **1. Local Git checkout** or **2. GitHub repo (owner/name)**, branch, watched folder, filename pattern, optional parser script, Telegram on/off, and whether to enable. It writes `configs/<name>.yaml`. Your private installation configuration can live outside the public code repository.

**Minimal example, local Git files:** copy [configs/examples/local.yaml](configs/examples/local.yaml) to `configs/local-notes.yaml` and edit:

~~~yaml
name: local-notes
enabled: true
source:
  type: local_git
  root: /absolute/path/to/your/source-repository
  branch: HEAD
  folder: reports
  pattern: "*.md"
parser: null
destinations:
  telegram: true
~~~

Local Git mode reads *committed content at HEAD*, not uncommitted working-tree changes.

**Fuller example, private GitHub source:** copy [configs/examples/github-article.yaml](configs/examples/github-article.yaml):

~~~yaml
name: weekly-articles
enabled: true
source:
  type: github
  repository: owner/private-repository
  branch: main
  folder: articles
  pattern: "*.md"
parser:
  script: commitrelay/parsers/after_separator.py
  options: {}
destinations:
  telegram: true
~~~

The built-in example parser keeps the content **after the first standalone `---` line** and returns `None` when no delimiter exists. That avoids exposing a private comment block at the top of a Markdown article.

A custom parser is any **trusted local Python script** defining:

~~~python
def parse(content: str, options: dict) -> str | None:
    return content.strip() or None
~~~

You can parse Markdown, JSON, tables, CSV or any other UTF-8 text. If a parser raises, delivery fails for that sync; it does *not* fall back to sending unfiltered content. A `parser: null` sync sends the entire file.

## CLI: preview, diagnose, run

~~~bash
commitrelay --help
commitrelay add [name]
commitrelay list
commitrelay edit [name]
commitrelay enable NAME
commitrelay disable NAME
commitrelay doctor                # Ask whether to test a destination
commitrelay doctor -n             # Never send
commitrelay doctor -y --telegram  # Send a Telegram test
commitrelay doctor -y --all       # Test all implemented destinations
commitrelay run --all --dry-run
commitrelay run --config NAME --dry-run
commitrelay run --all
~~~

`list` distinguishes CONFIGURED, UNCONFIGURED, DISABLED and BROKEN (including missing parser scripts). `doctor` lists available destinations with status; currently only Telegram is implemented.

**Dry-run means:** load and validate configurations, read matched files, run their parsers, compare parsed-content hashes with the checkpoint, and print `WOULD SEND` lines. **No Telegram request or checkpoint write occurs.**

Actual successful sends update a local SQLite state file (`.commitrelay-state/deliveries.db`) keyed by sync/source/file/destination, containing the SHA-256 of the last delivered parsed body. Private-comment-only edits don't resend identical article content.

Global CLI flags (`--configs` and `--state`) go *before* the command, e.g. `commitrelay --configs my-configs doctor -n`. Every subcommand supports `--help`.

## Watcher versus job — separate configurations

A **sync** YAML chooses what to read and publish. A **job** YAML selects which syncs to execute and documents how they should be triggered.

See [jobs/example-local.yaml](jobs/example-local.yaml):

~~~yaml
name: local-commit
enabled: false
configs: [local-notes]
trigger:
  type: local_post_commit
~~~

To use this locally: copy your example sync to `configs/`, set its path, enable it, update the job to `enabled: true`, then install a post-commit hook in the **source** repository:

~~~bash
commitrelay hook install --repo /absolute/path/to/source-repository --job jobs/example-local.yaml
~~~

This installs a *local* `post-commit` hook calling Python. It refuses to overwrite an existing hook. You can instead invoke `commitrelay run --job jobs/example-local.yaml` manually.

### GitHub and external sources

You don't need a local Git hook for GitHub Actions: a remote repository's **push** event is generated on GitHub's servers. A workflow in repository A does **not** automatically receive repository B's pushes. For cross-repository automation use a webhook / `repository_dispatch` mechanism or poll GitHub from a runner.

The remote **GitHub snapshot reader is already implemented**. It can inspect the current matched files when `commitrelay run` executes. Automatic cross-repository event wiring and a durable hosted checkpoint store are **not yet implemented**.

A planned scheduled job is shown in [jobs/example-hosted.yaml](jobs/example-hosted.yaml):

~~~yaml
name: hosted-poll
enabled: false
configs: [weekly-articles]
trigger:
  type: scheduled_poll
  cron_utc: "17 18 * * *"
~~~

**Important:** GitHub Actions cron schedules are declared in a GitHub workflow YAML, not dynamically loaded from this job YAML. This example expresses the desired policy only. It does not schedule itself.

### Delivery history and reliability

Local checkpoints persist on your machine. GitHub-hosted runners are ephemeral: do **not** turn on repeated hosted delivery until a durable state backend has been configured, or the same files may resend every run. Delivery and checkpoint saving aren't atomic across two systems; a crash between them can cause a duplicate on retry. Current polling tracks *latest parsed file state*, not every intermediate commit that happened between polls.

No automatic Telegram workflow has been activated in this repository.

## Extending and contributing

- Destinations: Telegram only right now. Discord and others may be requested, but aren't advertised as working.
- Parsers: trust your own local scripts, return `None` for content that must not leave the source repo.
- Triggers: local hook now, remote GitHub snapshot check now; durable hosted scheduling / webhooks and per-commit replay are future improvements.
- Security: review changes to any workflow that has secrets. Public source code doesn't imply your tokens, private files, or personal configurations should become public.
- Development tests: `python -m unittest discover -s tests -v`.

**Want a new feature?** Open [Issues → New issue → Feature request](https://github.com/AsapLoso/CommitRelay/issues/new?template=feature_request.md). That template is for proposing ideas and describing use cases; it **does not** appear when creating a pull request. If you've already implemented a change, feel free to open a normal PR with the relevant code and tests. No empty PR is needed just to request a feature.

**Similar tools exist.** See [Related tools and positioning](docs/RELATED_TOOLS.md) for an initial, non-exhaustive comparison. CommitRelay's goal is not to claim Git notifications were invented here; it's to make parsed file content a practical, agent-independent delivery boundary.

**Release plan:** first verify the end-to-end Telegram slice and checkpoint behavior; then add persisted hosted state and external trigger automation. No release is claimed until those are working.
