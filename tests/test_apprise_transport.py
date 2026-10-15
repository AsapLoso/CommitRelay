"""Tests for the Apprise transport adapter, with no network or real credentials."""
import os
import sys
import types
import unittest
from unittest.mock import patch

from commitrelay.app import ConfigError, telegram_send


class FakeNotifyFormat:
    TEXT = "text"


class FakeAttachMemory:
    def __init__(self, content, name, mimetype):
        self.content = content
        self.name = name
        self.mimetype = mimetype


class FakeApprise:
    created = []

    def __init__(self):
        self.urls = []
        self.notifications = []
        self.ok = True
        type(self).created.append(self)

    def add(self, url):
        self.urls.append(url)
        return True

    def notify(self, **kwargs):
        self.notifications.append(kwargs)
        return self.ok


class AppriseTransportTests(unittest.TestCase):
    def setUp(self):
        FakeApprise.created.clear()
        apprise = types.ModuleType("apprise")
        apprise.Apprise = FakeApprise
        apprise.NotifyFormat = FakeNotifyFormat
        attachments = types.ModuleType("apprise.attachment")
        attachments.AttachMemory = FakeAttachMemory
        mock_modules = patch.dict(sys.modules, {"apprise": apprise, "apprise.attachment": attachments})
        mock_modules.start()
        self.addCleanup(mock_modules.stop)
        mock_env = patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "123:secret", "TELEGRAM_CHAT_ID": "100"})
        mock_env.start()
        self.addCleanup(mock_env.stop)

    def test_short_message(self):
        telegram_send("Weekly article", "some.md", "Actual article")
        obj = FakeApprise.created[-1]
        self.assertEqual(obj.urls[0], "tgram://123:secret/100/")
        self.assertIn("Actual article", obj.notifications[0]["body"])
        self.assertNotIn("attach", obj.notifications[0])

    def test_long_message_becomes_markdown_attachment(self):
        telegram_send("Weekly article", "article.md", "Content " * 1000)
        msg = FakeApprise.created[-1].notifications[-1]
        self.assertEqual(msg["attach"].name, "article.md")
        self.assertEqual(msg["attach"].mimetype, "text/markdown")
        self.assertGreater(len(msg["attach"].content), 4096)
        self.assertNotIn("Content ", msg["body"])

    def test_harmless_test_message(self):
        telegram_send("", "", "", test=True)
        self.assertEqual(FakeApprise.created[-1].notifications[0]["body"], "CommitRelay test message")

    def test_failed_delivery_does_not_claim_success(self):
        old = FakeApprise.notify
        FakeApprise.notify = lambda self, **kw: False
        self.addCleanup(setattr, FakeApprise, "notify", old)
        with self.assertRaisesRegex(ConfigError, "not confirmed"):
            telegram_send("A", "a.md", "Hello")

    def test_missing_credentials(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            with self.assertRaises(ConfigError):
                telegram_send("A", "a.md", "Hello")
        self.assertFalse(FakeApprise.created)


if __name__ == "__main__":
    unittest.main()
