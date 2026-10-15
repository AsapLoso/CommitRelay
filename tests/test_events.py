import json
from pathlib import Path
import tempfile
import unittest
from commitrelay.events import event_route, matching_syncs
from commitrelay.app import Sync, ConfigError


class EventTests(unittest.TestCase):
    def setUp(self):
        self.sync = Sync(Path("x.yaml"), "x", True, {"type": "github", "repository": "owner/source", "branch": "main"}, None, {"telegram": True})
        self.other = Sync(Path("y.yaml"), "y", True, {"type": "github", "repository": "someone/else", "branch": "main"}, None, {"telegram": True})
        self.local = Sync(Path("z.yaml"), "z", True, {"type": "local_git", "root": ".", "folder": "notes"}, None, {"telegram": True})

    def test_matches_exact_repository_branch(self):
        self.assertEqual(matching_syncs([self.sync, self.other, self.local], "OWNER/source", "refs/heads/main"), [self.sync])
        self.assertEqual(matching_syncs([self.sync], "owner/source", "refs/heads/feature"), [])
        self.assertEqual(matching_syncs([self.sync], "attacker/source", "refs/heads/main"), [])

    def test_untrusted_event_payload_cannot_select_other_repo(self):
        with tempfile.TemporaryDirectory() as dir_:
            p = Path(dir_) / "event.json"
            p.write_text(json.dumps({"client_payload": {"repository": "attacker/repo", "ref": "refs/heads/main"}}))
            repo, ref = event_route(p)
            self.assertEqual(matching_syncs([self.sync], repo, ref), [])

    def test_malformed_ref_fails(self):
        with tempfile.TemporaryDirectory() as dir_:
            p = Path(dir_) / "event.json"
            p.write_text(json.dumps({"client_payload": {"repository": "owner/source", "ref": "not-a-ref"}}))
            with self.assertRaises(ConfigError):
                event_route(p)
