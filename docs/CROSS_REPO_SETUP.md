# Connect a different GitHub repository

**Opt-in instructions — no hosted messaging has been activated or verified end to end yet.** You do not need to understand rebasing, Git submodules or repository mirroring. A sync's `source.repository: OWNER/REPO` is simply a GitHub API reference.

## Three roles

1. **Public library:** [AsapLoso/CommitRelay](https://github.com/AsapLoso/CommitRelay) contains the Python package. Install it using `pip`; do not copy its source into every watched repo.
2. **Private installation:** create or reuse a **private** repo (e.g. `YOURNAME/commitrelay-installation`) for your sync YAMLs, receiver workflow and checkpoint hashes. A private repository is important because even source locations and state metadata may be sensitive.
3. **Watched source:** another repository identified by `OWNER/SOURCE`, read through GitHub's REST API. A read-only source token is needed for private sources.

The first working trigger option uses [peter-evans/repository-dispatch](https://github.com/peter-evans/repository-dispatch), an existing GitHub Action. The watched repository forwards push events to your installation. This **does require one small workflow in each watched source repository**. A central GitHub App webhook (not implemented) would avoid that later.

## 1. Create private installation

Run in your terminal (replace example owner/name):

~~~bash
gh auth login
gh repo create YOURNAME/commitrelay-installation --private --clone
cd commitrelay-installation
mkdir -p configs .github/workflows
git clone https://github.com/AsapLoso/CommitRelay.git ../CommitRelay
cp ../CommitRelay/examples/private-receiver.yml .github/workflows/commitrelay.yml
cp ../CommitRelay/configs/examples/github-article.yaml configs/weekly-articles.yaml
~~~

Edit `configs/weekly-articles.yaml` and specify the actual source repository/branch/folder. Set `enabled: true` **only after reviewing the trusted parser**:

~~~yaml
name: weekly-articles
enabled: true
source:
  type: github
  repository: OWNER/SOURCE
  branch: main
  folder: articles
  pattern: "*.md"
parser:
  script: commitrelay/parsers/after_separator.py
  options: {}
destinations:
  telegram: true
~~~

The built-in parser lives in the installed Python package. It returns only content after the first standalone `---` line, suppressing files without a separator. For your own parser, use an explicitly trusted Python file. No content from the source repository is executed.

Commit normally:

~~~bash
git add configs .github/workflows
git commit -m 'Configure private CommitRelay installation'
git push
~~~

**Simply pushing this receiver file does not initiate a Telegram send:** the example listens to explicit dispatch events and manual runs, not ordinary pushes or a schedule.

## 2. Install credentials in the private installation

Create a Telegram bot, start its chat, and find its numeric chat ID. Create a fine-grained read-only GitHub token scoped to any private source repository (Contents: read). Then set **these secrets in the private installation repo**:

~~~bash
gh secret set TELEGRAM_BOT_TOKEN --repo YOURNAME/commitrelay-installation
gh secret set TELEGRAM_CHAT_ID --repo YOURNAME/commitrelay-installation
gh secret set COMMITRELAY_SOURCE_TOKEN --repo YOURNAME/commitrelay-installation
gh secret list --repo YOURNAME/commitrelay-installation
~~~

For public source repositories you can omit `COMMITRELAY_SOURCE_TOKEN`; private repos need it.

The receiver uses its own `GITHUB_TOKEN` with Contents:write **only for its private installation repository**. After confirmed delivery it commits opaque SHA-256 state files under `.commitrelay-state/` on the private installation's `main` branch. The files contain a hash of the transformed content, not the message or credentials. Change `COMMITRELAY_STATE_BRANCH` in the workflow for another writable private branch.

## 3. Preview, then baseline existing files

~~~bash
gh workflow run commitrelay.yml --repo YOURNAME/commitrelay-installation -f operation=preview
gh run list --repo YOURNAME/commitrelay-installation --limit 5
~~~

A preview reads and parses but **never sends** or changes checkpoints. Inspect the run's log. Before enabling the external trigger, **baseline** old files so you do not send an entire historical article archive:

~~~bash
gh workflow run commitrelay.yml --repo YOURNAME/commitrelay-installation -f operation=baseline
~~~

This saves hashes with **zero Telegram sends**. Only do this deliberately for an initial installation; doing it after missed pushes would suppress legitimately pending messages.

## 4. Add one push-event bridge to the source repository

Cross-repo `repository_dispatch` requires a token authorized to dispatch to the **target private installation**. The default `GITHUB_TOKEN` of the watched repo cannot dispatch to another repo. Create a fine-grained token with **Contents:write on the installation repo**, then set these values **in the watched source**:

~~~bash
gh secret set COMMITRELAY_DISPATCH_TOKEN --repo OWNER/SOURCE
gh variable set COMMITRELAY_TARGET_REPO --body 'YOURNAME/commitrelay-installation' --repo OWNER/SOURCE
~~~

**Security trade-off:** that dispatch token grants Contents:write on the private installation. Never place it in source repositories with untrusted workflow maintainers. For a future multi-user release, prefer a GitHub App or secure webhook relay using narrower short-lived permissions.

Install the source workflow only after the preview and baseline:

~~~bash
gh repo clone OWNER/SOURCE ../source-checkout
mkdir -p ../source-checkout/.github/workflows
cp ../CommitRelay/examples/source-push.yml ../source-checkout/.github/workflows/notify-commitrelay.yml
# Edit branches: [main] in the new workflow if the watched branch differs.
cd ../source-checkout
git add .github/workflows/notify-commitrelay.yml
git commit -m 'Request CommitRelay dispatch on source pushes'
git push
~~~

This watches pushes to its configured branch, forwards a small event with the repository and branch, and starts the receiver workflow. The receiver checks those values against *your own enabled sync YAMLs*: event data cannot make it read an arbitrary unconfigured repo. The receiver then parses the current matching files, compares output hashes, sends only changed output and records a successful delivery.

**Runner cost:** one small Actions run in the source repo and another in the private receiver for each push. No five-minute cron or idle polling; a midnight push still uses those two runs. The event's commit SHA is **not** used to replay all intermediate revisions: currently CommitRelay checks the latest file snapshots.

## 5. Check operation and limitations

Test by changing the *published portion* of one safe test Markdown file, committing and pushing it. Check source Actions, private receiver Actions, Telegram and the new private checkpoint. Then change only the ignored comments: the workflows may run, but no Telegram message should be sent.

An event from an unconfigured source/branch is ignored. A missing secret or failed parser must not fall back to sending unfiltered content. A failure after Telegram delivery but before the checkpoint write can cause a duplicate on retry; exactly-once semantics are not promised.

**No integration is actually active until you install the two example workflows and credentials.** The public CommitRelay repository has not enabled an automatic sender. See [External trigger research](EVENT_TRIGGERS.md) for alternatives (GitHub App, signed webhook endpoint, scheduled reconciliation).
