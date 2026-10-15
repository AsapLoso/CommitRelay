"""Hosted checkpoint tests with no real HTTP calls or secrets."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from commitrelay.hosted_state import GitHubCheckpoints, StateError, checkpoints_from_environment


class HostedStateTests(unittest.TestCase):
    def setUp(self):
        self.state = GitHubCheckpoints("owner/private-installation", "fake-token")
        self.remote = {}
        self.calls = []

        def fake_request(method, path, body=None):
            self.calls.append((method, path))
            if method == "GET":
                return self.remote.get(path)
            prior = self.remote.get(path)
            if prior is not None and body.get("sha") != prior["sha"]:
                raise StateError("Concurrent checkpoint update")
            sha = "sha" + str(len(self.calls))
            self.remote[path] = {"sha": sha, "content": body["content"]}
            return {"content": {"sha": sha}}
        self.patch = patch.object(self.state, "_request", side_effect=fake_request)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_create_and_reopen_checkpoint(self):
        key = ("weekly", "github:owner/source@main", "articles/post.md", "telegram")
        self.assertFalse(self.state.same(key, "hash1"))
        self.state.mark(key, "hash1")
        self.assertTrue(self.state.same(key, "hash1"))
        self.assertNotIn("articles", next(iter(self.remote)))
        self.state._cache.clear()
        self.assertTrue(self.state.same(key, "hash1"))
        self.state.mark(key, "hash2")
        self.assertTrue(self.state.same(key, "hash2"))

    def test_no_write_when_only_checking(self):
        self.assertFalse(self.state.same(("k",), "hash"))
        self.assertFalse(any(method == "PUT" for method, _ in self.calls))

    def test_hosted_fail_closed_without_backend(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            with self.assertRaises(StateError):
                checkpoints_from_environment(Path("ignored.db"))

    def test_hosted_selects_repo_backend(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_TOKEN": "test", "COMMITRELAY_STATE_REPOSITORY": "owner/installation"}, clear=True):
            result = checkpoints_from_environment(Path("ignored.db"))
            self.assertIsInstance(result, GitHubCheckpoints)
