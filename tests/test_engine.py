"""Offline regression tests. No network, no Telegram credentials required."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml
from commitrelay.app import (
    Checkpoints, ConfigError, credential_status, discover, load_sync,
    parsed_content, run_sync
)
from commitrelay.cli import main


class EngineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        (self.repo / "reports").mkdir()
        self.source = self.repo / "reports" / "one.md"
        self.source.write_text("Private comment\n---\nPublic article", encoding="utf-8")
        self.commit()
        self.configs = self.tmp / "configs"
        self.configs.mkdir()
        (self.tmp / "extract.py").write_text(
            'def parse(content, options):\n'
            '    return content.split("\\n---\\n", 1)[1].strip() if "\\n---\\n" in content else None\n',
            encoding="utf-8",
        )
        self.data = {
            "name": "sample", "enabled": True,
            "source": {"type": "local_git", "root": str(self.repo), "branch": "HEAD",
                       "folder": "reports", "pattern": "*.md"},
            "parser": {"script": "extract.py"},
            "destinations": {"telegram": True},
        }
        self.cfg = self.configs / "sample.yaml"
        self.save()

    def commit(self):
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-m", "test", "-q"], check=True)

    def save(self):
        self.cfg.write_text(yaml.safe_dump(self.data), encoding="utf-8")

    def test_config_list_and_broken_yaml(self):
        self.assertEqual(load_sync(self.cfg).name, "sample")
        (self.configs / "broken.yaml").write_text("bad: [yaml", encoding="utf-8")
        rows = discover(self.configs)
        self.assertEqual(len(rows), 2)
        self.assertTrue(any(error for _, _, error in rows))

    def test_privacy_and_deduplication(self):
        checkpoint = Checkpoints(self.tmp / "data" / "checkpoint.db")
        try:
            with patch("commitrelay.app.telegram_send") as send:
                run_sync(load_sync(self.cfg), checkpoint)
                send.assert_called_once()
                self.assertNotIn("Private", str(send.call_args))
                run_sync(load_sync(self.cfg), checkpoint)
                send.assert_called_once()
                self.source.write_text("Changed private comment\n---\nPublic article")
                self.commit()
                run_sync(load_sync(self.cfg), checkpoint)
                send.assert_called_once()
                self.source.write_text("Private\n---\nDifferent article")
                self.commit()
                run_sync(load_sync(self.cfg), checkpoint)
                self.assertEqual(send.call_count, 2)
        finally:
            checkpoint.close()

    def test_dry_run_never_sends_or_updates(self):
        cp = Checkpoints(self.tmp / "dry.db")
        try:
            with patch("commitrelay.app.telegram_send") as send:
                planned, _ = run_sync(load_sync(self.cfg), cp, dry_run=True)
                self.assertEqual(planned, 1)
                send.assert_not_called()
                self.assertIsNone(cp.db.execute("SELECT hash FROM delivered").fetchone())
        finally:
            cp.close()

    def test_parser_failure_closed(self):
        (self.tmp / "extract.py").write_text('def parse(content, options):\n    raise ValueError("unsafe")\n')
        cp = Checkpoints(self.tmp / "fail.db")
        try:
            with patch("commitrelay.app.telegram_send") as send:
                with self.assertRaises(ConfigError):
                    run_sync(load_sync(self.cfg), cp)
                send.assert_not_called()
        finally:
            cp.close()

    def test_disable_enable(self):
        self.assertEqual(main(["--configs", str(self.configs), "disable", "sample"]), 0)
        self.assertFalse(load_sync(self.cfg).enabled)
        self.assertEqual(main(["--configs", str(self.configs), "enable", "sample"]), 0)
        self.assertTrue(load_sync(self.cfg).enabled)

    def test_doctor_n_never_sends(self):
        with patch("commitrelay.cli.telegram_send") as send:
            self.assertEqual(main(["--configs", str(self.configs), "doctor", "-n"]), 0)
            send.assert_not_called()

    def test_doctor_y_telegram_only(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "dummy", "TELEGRAM_CHAT_ID": "123"}):
            with patch("commitrelay.cli.telegram_send") as send:
                self.assertEqual(main(["--configs", str(self.configs), "doctor", "-y", "--telegram"]), 0)
                send.assert_called_once()

    def test_github_reader_without_network(self):
        self.data["source"] = {
            "type": "github", "repository": "owner/repo", "branch": "main",
            "folder": "reports", "pattern": "*.md",
        }
        self.save()
        from commitrelay.app import github_files
        with patch("commitrelay.app.github_api") as api:
            import base64
            api.side_effect = [
                {"tree": [{"path": "reports/one.md", "type": "blob"},
                          {"path": "other/ignore.md", "type": "blob"}]},
                {"encoding": "base64", "content": base64.b64encode(b"Hello").decode()},
            ]
            rows = list(github_files(load_sync(self.cfg).source))
            self.assertEqual(rows[0][1:], ("reports/one.md", "Hello"))
            self.assertEqual(api.call_count, 2)


if __name__ == "__main__":
    unittest.main()
