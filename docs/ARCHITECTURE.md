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
| Remote GitHub repository | Implemented (GitHub API, private token if required) | Example source push / repository_dispatch receiver workflows and event allowlisting committed; opt-in, not deployed or live-tested |
| GitHub Actions runner | Can call Python entrypoint | Manual-only CI in public repo. Opt-in private installation workflow provided in `examples/`, not installed |

Local post-commit hooks don't see commits on other people's clones. Remote GitHub push events require a workflow/webhook in the source repository or a cross-repository repository_dispatch, or periodic polling. GitHub Actions cron is static workflow syntax; a job config cannot itself define that schedule.

## Lifecycle for one file

1. Enabled sync selects committed file snapshots by repository/folder/pattern.
2. Trusted parser returns a string or None. Error => fail closed; no raw-content fallback.
3. SHA-256 hash of parsed content is compared to checkpoint for (config, source, path, destination).
4. Same hash/None/disabled destination => no send.
5. New hash => deliver via **Apprise's Telegram integration** (Markdown attachment if >4096 characters).
6. After Telegram acknowledges success, persist digest to SQLite.

Local checkpoint database is ignored by Git. Opt-in `GitHubCheckpoints` stores opaque hashed identifiers and output digests through the GitHub Contents API **in a private installation repository**; the receiver workflow serializes runs. External end-to-end delivery has not yet been tested. Existing files can be marked via `--baseline` without sending them. Telegram response and checkpoint save aren't one atomic transaction; an interruption between the two can cause a duplicate on retry.

**Current semantics are snapshot polling**, not historical per-commit replay. Changes overwritten between polls are not sent. Adding per-commit replay requires a persisted cursor and ordered commit traversal, pagination and appropriate GitHub API rate-limit behavior.

## CLI status

- Implemented: add [name], list, edit [name], enable/disable [name], doctor [-n | -y --telegram/--all], run --all/--config/--job [--dry-run], hook install.
- Local parser and transport tests: initial prototype passed seven offline checks; GitHub repository now has a separate regression test suite and an opt-in manual CI workflow. Do not state it passed hosted CI until a real run confirms that.
- Apprise is installed as the Telegram transport dependency. Other Apprise services (Discord, email, etc.) are **not exposed** as CommitRelay destinations yet. No webhook listener or arbitrary code execution from watched repositories; only explicitly configured trusted local Python parsers.

## Future vertical slices (ordered)

1. Run full unit suite in manual GitHub Actions, fix test/packaging failures and add test coverage for hooks and malformed GitHub API responses.
2. Validate the new private GitHub Contents API checkpoint backend and the serial receiver workflow on GitHub; review branch protection and token permissions.
3. Validate the opt-in `repository_dispatch` bridge and tighten the source-workflow token trust model; later add a signed GitHub App webhook receiver needing no Actions workflow in watched repositories.
4. Add configurable retry/backoff, GitHub API pagination, and explicit per-commit replay if users require it.
5. Where useful, expose additional Apprise-supported destinations through safe explicit configuration; avoid reimplementing their protocols. Keep available destinations discoverable by doctor.
6. Release tagged v1 with installation/upgrade documentation and a consciously chosen open-source license.

## Operational constraints

- Source repository names and paths in a PUBLIC sync YAML are public; credentials must remain GitHub Secrets or local environment.
- Public code with privileged secrets needs review of workflow/parser changes before execution.
- This code is currently in public AsapLoso/CommitRelay. The older failing private workflow remains disabled; do not re-enable without explicit approval.
- Do not automatically activate an untested webhook, cron job, message sender, or hosted checkpoint strategy.

## 15 October 2026 — Cross-repository integration slice

Added `commitrelay/events.py` for configured repo/branch event routing, `commitrelay/hosted_state.py` for GitHub Contents API delivery checkpoints, `run --all --event-file`, and `run --all --baseline` to avoid first-run archive floods. Reused `peter-evans/repository-dispatch@v4` in the **example**, not in an active source workflow. The sender and receiver templates are under `examples/`; see [setup](CROSS_REPO_SETUP.md). New offline tests cover event routing, checkpoint creation/updates and baselining, but **actual Actions/Telegram runs remain unverified**. No private repositories or active workflows were changed.
