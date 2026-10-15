"""GitHub Contents API checkpoint storage for a PRIVATE installation repository.

State changes are committed only after a destination accepts a delivery.
No source content is stored: only opaque key hashes and output digests.
"""
from __future__ import annotations

import base64
from hashlib import sha256
import json
import os
from urllib import error, parse, request


class StateError(RuntimeError):
    pass


class GitHubCheckpoints:
    """Remote checkpoint with SHA conditional updates and per-entry files.

    Requires repository Contents:write on a private repository. Workflow
    concurrency must serialize runs for any potentially overlapping sources.
    """

    def __init__(self, repository: str, token: str, branch: str = "main", prefix: str = ".commitrelay-state"):
        if not token:
            raise StateError("Missing GitHub state token")
        if repository.count("/") != 1 or any(c.isspace() for c in repository):
            raise StateError("Expected state repository as owner/name")
        self.repository, self.token, self.branch = repository, token, branch
        self.prefix = prefix.strip("/")
        if not self.prefix or ".." in self.prefix.split("/"):
            raise StateError("Invalid state prefix")
        self._cache = {}

    @staticmethod
    def _identifier(key):
        canonical = json.dumps(key, ensure_ascii=False, separators=(",", ":"))
        return sha256(canonical.encode("utf-8")).hexdigest()

    def _path(self, key):
        return f"{self.prefix}/{self._identifier(key)}.json"

    def _request(self, method, path, obj=None):
        url = "https://api.github.com/repos/" + self.repository + "/contents/" + parse.quote(path, safe="/")
        if method == "GET":
            url += "?ref=" + parse.quote(self.branch, safe="")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "CommitRelay",
            "Authorization": "Bearer " + self.token,
        }
        payload = None if obj is None else json.dumps(obj).encode("utf-8")
        if payload is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=payload, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=25) as resp:
                return json.load(resp)
        except error.HTTPError as exc:
            if exc.code == 404 and method == "GET":
                return None
            if exc.code in (409, 422):
                raise StateError("Concurrent checkpoint update or rejected branch; retry after checking state") from None
            raise StateError(f"GitHub state API returned HTTP {exc.code}; check private repository permissions") from None
        except error.URLError:
            raise StateError("GitHub state API unavailable; delivery checkpoint not saved") from None

    def _load(self, key):
        if key not in self._cache:
            obj = self._request("GET", self._path(key))
            if obj is None:
                self._cache[key] = (None, None)
            else:
                try:
                    record = json.loads(base64.b64decode(obj["content"]).decode("utf-8"))
                    self._cache[key] = (record["hash"], obj["sha"])
                except (KeyError, ValueError, UnicodeError):
                    raise StateError("Invalid remote checkpoint format; refusing to resend") from None
        return self._cache[key]

    def same(self, key, digest):
        value, _ = self._load(key)
        return value == digest

    def mark(self, key, digest):
        _, sha = self._load(key)
        record = {"hash": digest}
        contents = base64.b64encode((json.dumps(record, sort_keys=True) + "\n").encode()).decode()
        body = {
            "message": "state: record CommitRelay delivery " + self._identifier(key)[:12],
            "branch": self.branch,
            "content": contents,
        }
        if sha:
            body["sha"] = sha
        obj = self._request("PUT", self._path(key), body)
        self._cache[key] = (digest, obj["content"]["sha"])

    def close(self):
        pass


def checkpoints_from_environment(local_state):
    """Opt-in hosted backend. Never silently fall back to ephemeral state."""
    state_repo = os.getenv("COMMITRELAY_STATE_REPOSITORY")
    if state_repo:
        token = os.getenv("COMMITRELAY_STATE_TOKEN") or os.getenv("GITHUB_TOKEN")
        return GitHubCheckpoints(
            repository=state_repo,
            token=token,
            branch=os.getenv("COMMITRELAY_STATE_BRANCH", "main"),
            prefix=os.getenv("COMMITRELAY_STATE_PREFIX", ".commitrelay-state"),
        )
    if os.getenv("GITHUB_ACTIONS") == "true":
        raise StateError("Hosted Actions require COMMITRELAY_STATE_REPOSITORY; refusing ephemeral checkpoints")
    from .app import Checkpoints
    return Checkpoints(local_state)
