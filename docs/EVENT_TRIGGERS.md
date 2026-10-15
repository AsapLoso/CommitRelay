# Automatic external triggering: build less, reuse more

_Research and architecture notes — 15 October 2026. No webhook or automatic dispatch has been enabled._

## Desired user experience

- A local or hosted Git repository is watched without polling GitHub every five minutes.
- On a push event, a central CommitRelay installation checks enabled syncs and their branch/path rules.
- For article-style syncs, send parsed publishable text only if it differs from the last successful delivery.
- For code review notifications (planned), send specific changed paths and a readable diff, not a full snapshot. Private code must only be sent to destinations authorized for it.
- Quiet hours (planned): capture events at night without sending immediately, and deliver a morning digest. Merely not delivering at night does not eliminate incoming webhook events; implement a durable queue before offering this.
- Retry/reconcile missed events without resending already delivered content.

## Existing systems worth reusing first

1. [GithubBot](https://github.com/AshokShau/GithubBot): GitHub-webhook-powered Telegram bot for pushes, PRs, issues and interactive `/files`, `/diff`, and `/compare` commands. Evaluate whether this already solves code-change notifications; **do not grant private repo access without reviewing its deployment, authentication, privacy and maintenance requirements**.
2. [Probot](https://github.com/probot/probot): established GitHub App framework. Receives webhook events and supports GitHub App authorization. Requires a receiver deployment; Node.js rather than Python.
3. [Hookdeck](https://hookdeck.com/) / [Hookdeck CLI](https://github.com/hookdeck/hookdeck-cli): managed webhook ingress, filtering, queues and retries. A suitable building block if we want to avoid operating webhook infrastructure.
4. [GitHub's native webhooks](https://docs.github.com/en/webhooks/using-webhooks) and [GitHub Apps](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/using-webhooks-with-github-apps): push events delivered to a registered HTTPS receiver.
5. [Cloudflare's GitHub-webhook tutorial](https://developers.cloudflare.com/workers/tutorials/build-a-slackbot/) and [GitHub App/Worker example](https://github.com/gr2m/cloudflare-worker-github-app-example): patterns for a lightweight event-driven receiver. **The latter example warns that it doesn't verify signatures; do not copy that behavior.**
6. [GitHub Actions `repository_dispatch`](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows): lets an authenticated external integration request a workflow run. Useful as a second-stage receiver handoff, but causes an Actions run per event unless batched.

## Three routes, from simplest to more scalable

| Mechanism | What needs installation? | Runner usage | Constraints |
| --- | --- | --- | --- |
| Source-repo `on: push` GitHub Actions calling an existing Telegram Action or external dispatcher | A workflow in each source repo, Telegram/API secrets | One runner on qualifying pushes | Easy to set up, but contrary to the long-term single-central-installation goal |
| **Repository webhook** pointing to a lightweight HTTPS endpoint | One hook configured per source repo, an HTTPS receiver, shared webhook secret | No GitHub Actions runner needed just to receive pushes | GitHub needs access to that endpoint; receiver needs reliable state and content credentials for private repositories |
| **GitHub App webhook** installed on selected repositories | Register an App once, install it with appropriately restricted repo permissions, host its receiver | No GitHub Actions runner needed for webhook receipt | Best general central-installation UX; requires App authentication, permissions, installation/token lifecycle |

A polling job remains a **low-frequency optional reconciliation mechanism**, not the primary trigger. It can catch up after missed events or outages. No need to run every five minutes or wake hosted Actions overnight solely to check for nothing.

## Credentials and privacy

- **Incoming webhook:** GitHub sends an HTTP POST to the registered endpoint. Authenticate it with a *random webhook secret* and HMAC-SHA256 signature verification (`X-Hub-Signature-256`). An API token is not required merely to *receive* a signed webhook.
- **Reading private files or diffs:** requires a credential with repository content read permission, preferably short-lived installation tokens issued to a GitHub App with access restricted to selected repositories.
- **Sending Telegram messages:** requires the bot token and destination chat ID, stored as host secrets.
- **Dispatching GitHub Actions elsewhere:** needs a credential authorized for the target repository's `repository_dispatch` endpoint.
- Verify the *raw webhook request body*, reject invalid signatures, validate repository/branch/path, and never fetch/forward private code solely because an unauthenticated payload names a repository. Keep secrets out of URLs and Git-tracked config.

See [GitHub webhook security recommendations](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks) for verification, HTTPS, short response times, replay handling, and recovery of failed deliveries.

## Engineering milestones before switching anything on

1. **Decide whether to integrate an existing GitHub bot** for code-change notifications rather than implementing diff messaging in CommitRelay.
2. Prototype a signed webhook handler using existing, maintained libraries; add fixture-based push-event and invalid-signature tests.
3. Persist delivery/event IDs and per-sync parsed-output hashes; protect against duplicate pushes and concurrent processing.
4. Add optional quiet hours and a durable outbox, with a morning digest job triggered only when useful.
5. Support private GitHub content via least-privilege App installation credentials; prevent leaking file content in logs.
6. Test with a private sandbox repository and synthetic content; inspect both notification and checkpoint before considering unattended operation.

## What is not done

CommitRelay currently has **no automatic external webhook listener**, **no GitHub App**, **no code-diff formatter**, **no morning digest/quiet-hours queue**, and **no durable hosted checkpoint system**. The existing external GitHub **snapshot reader** runs only when someone invokes the CLI or another runner calls it.

**Do not activate any automatic Actions or delivery triggers until a verified end-to-end test demonstrates correct permissions, privacy filtering and checkpoint behavior.**
