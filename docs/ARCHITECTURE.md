# Architecture and implementation ledger (15 October 2026)

## Purpose

Git files are the interface between independent agents/scripts/humans and delivery channels. An agent commits an output; it need not know any messenger API or credential.

## Two configuration layers

**Sync:** one YAML per watched source and destination policy, in configs/*.yaml (examples in configs/examples/). Has name, enabled, source.type (local_git/github), source.root or repository, branch, folder, pattern, parser script/null, destinations.telegram true/false.

**Job:** one YAML per operation, in jobs/*.yaml. Has name, enabled, list of sync names, and a declared trigger policy. CLI can run a job; job YAML DOES NOT install a GitHub Actions cron or remote webhook by itself.

### Source and trigger matrix

| Source | On-demand snapshot read | Automatic trigger |
| --- | --- | --- |
| Local Git checkout | Implemented | Optional local post-commit hook installer |
| Remote GitHub repository | Implemented (GitHub API, private token if required) | NOT implemented: remote push event relay / scheduled Action |
| GitHub Actions runner | Can call Python entrypoint | Manual tests only; Telegram auto-run disabled |

Local post-commit hooks don't see commits on other people's clones. Remote GitHub push events require a workflow/webhook in the source repository or a cross-repository repository_dispatch, or periodic polling. GitHub Actions cron is static workflow syntax; a job config cannot itself define that schedule.

## Lifecycle for one file

1. Enabled sync selects committed file snapshots by repository/folder/pattern.
2. Trusted parser returns a string or None. Error => fail closed; no raw-content fallback.
3. SHA-256 hash of parsed content is compared to checkpoint for (config, source, path, destination).
4. Same hash/None/disabled destination => no send.
5. New hash => send via Telegram (document upload if >4096 characters).
6. After Telegram acknowledges success, persist digest to SQLite.

Local checkpoint database is ignored by Git. These checkpoints are **not durable on hosted ephemeral Actions runners**. A GitHub-backed / durable backend with concurrency control is required before unattended hosted scheduling can be enabled. Telegram response and checkpoint save aren't one atomic transaction; an interruption between the two can cause a duplicate on retry.

**Current semantics are snapshot polling**, not historical per-commit replay. Changes overwritten between polls are not sent. Adding per-commit replay requires a persisted cursor and ordered commit traversal, pagination and appropriate GitHub API rate-limit behavior.

## CLI status

- Implemented: add [name], list, edit [name], enable/disable [name], doctor [-n | -y --telegram/--all], run --all/--config/--job [--dry-run], hook install.
- Local parser and transport tests: initial prototype passed seven offline checks; GitHub repository now has a separate regression test suite and an opt-in manual CI workflow. Do not state it passed hosted CI until a real run confirms that.
- No Discord, WhatsApp, email, generic webhook or arbitrary code execution from watched repositories. Only declared trusted local Python parsers.

## Future vertical slices (ordered)

1. Run full unit suite in manual GitHub Actions, fix test/packaging failures and add test coverage for hooks and malformed GitHub API responses.
2. Implement durable state (prefer private checkpoint repository/file or other transaction-safe store) and a single hosted job runner with locking.
3. Add cross-repo GitHub watcher triggers and/or scheduled polling, preserving state and avoiding duplicates.
4. Add configurable retry/backoff, GitHub API pagination, and explicit per-commit replay if users require it.
5. Add destination adapters only once implemented (Discord, etc.); keep registered adapters discoverable by doctor.
6. Release tagged v1 with installation/upgrade documentation and a consciously chosen open-source license.

## Operational constraints

- Source repository names and paths in a PUBLIC sync YAML are public; credentials must remain GitHub Secrets or local environment.
- Public code with privileged secrets needs review of workflow/parser changes before execution.
- This code is currently in public AsapLoso/CommitRelay. The older failing private workflow remains disabled; do not re-enable without explicit approval.
- Do not automatically activate an untested webhook, cron job, message sender, or hosted checkpoint strategy.
