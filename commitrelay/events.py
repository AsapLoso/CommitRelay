"""Validate external dispatch routing hints against local allowlisted syncs."""
from __future__ import annotations
import json
from pathlib import Path
from .app import ConfigError


def event_route(file: Path):
    try:
        event = json.loads(Path(file).read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ConfigError("Could not parse GitHub dispatch event") from exc
    payload = event.get("client_payload")
    if not isinstance(payload, dict):
        raise ConfigError("Expected repository_dispatch.client_payload")
    repo = payload.get("repository")
    if not isinstance(repo, str) or repo.count("/") != 1 or not all(repo.split("/")):
        raise ConfigError("Expected client_payload.repository as owner/repo")
    ref = payload.get("ref")
    if ref is not None and (not isinstance(ref, str) or not ref.startswith("refs/heads/")):
        raise ConfigError("Expected optional ref as refs/heads/BRANCH")
    return repo, ref


def matching_syncs(syncs, repo, ref=None):
    allowed = []
    for sync in syncs:
        src = sync.source
        if src["type"] != "github" or src["repository"].casefold() != repo.casefold():
            continue
        if ref is not None and src.get("branch", "main") != ref.removeprefix("refs/heads/"):
            continue
        allowed.append(sync)
    return allowed
