"""Additional regression for first-installation baselining."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml
from commitrelay.app import Checkpoints, load_sync, run_sync


class BaselineTests(unittest.TestCase):
    def test_baseline_does_not_send_old_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            (repo / "articles").mkdir()
            (repo / "articles" / "one.md").write_text("Old article")
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
            configs = root / "configs"
            configs.mkdir()
            file = configs / "test.yaml"
            file.write_text(yaml.safe_dump({"name": "test", "enabled": True,
                "source": {"type": "local_git", "root": str(repo), "branch": "HEAD",
                    "folder": "articles", "pattern": "*.md"},
                "parser": None, "destinations": {"telegram": True}}))
            cp = Checkpoints(root / "checkpoint.db")
            try:
                with patch("commitrelay.app.telegram_send") as send:
                    n, _ = run_sync(load_sync(file), cp, baseline=True)
                    self.assertEqual(n, 1)
                    send.assert_not_called()
                    run_sync(load_sync(file), cp)
                    send.assert_not_called()
                    (repo / "articles" / "one.md").write_text("New article")
                    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
                    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "update"], check=True)
                    run_sync(load_sync(file), cp)
                    send.assert_called_once()
            finally:
                cp.close()
