import tempfile
import unittest
from pathlib import Path

from agentden.slack_oauth import OAUTH_URL, SlackRotator, read_env

ENV = ("SLACK_ACCESS_TOKEN_KURO=old-access\nSLACK_REFRESH_TOKEN_KURO=old-refresh\n"
       "SLACK_CLIENT_ID_KURO=cid\nSLACK_CLIENT_SECRET_KURO=csecret\nOTHER=keep\n")


class FakePost:
    def __init__(self, response):
        self.response, self.calls = response, []

    def __call__(self, url, form):
        self.calls.append((url, form))
        return self.response


class TestSlackRotator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = Path(self.tmp.name, ".env")
        self.env.write_text(ENV)

    def tearDown(self):
        self.tmp.cleanup()

    def test_success_updates_env_and_recovery(self):
        post = FakePost({"ok": True, "access_token": "new-a", "refresh_token": "new-r", "expires_in": 43200})
        self.assertEqual(SlackRotator(self.env, post).rotate("kuro"), 43200)
        url, form = post.calls[0]
        self.assertEqual((url, form["grant_type"], form["refresh_token"]), (OAUTH_URL, "refresh_token", "old-refresh"))
        env = read_env(self.env)
        self.assertEqual((env["SLACK_ACCESS_TOKEN_KURO"], env["SLACK_REFRESH_TOKEN_KURO"], env["OTHER"]),
                         ("new-a", "new-r", "keep"))
        self.assertEqual(self.env.stat().st_mode & 0o777, 0o600)
        self.assertTrue(Path(self.tmp.name, ".token_recovery_kuro").exists())

    def test_rejection_raises_and_keeps_env(self):
        post = FakePost({"ok": False, "error": "invalid_refresh_token"})
        with self.assertRaises(RuntimeError):
            SlackRotator(self.env, post).rotate("kuro")
        self.assertEqual(self.env.read_text(), ENV)

    def test_missing_expiry_still_saves_tokens_then_raises(self):
        post = FakePost({"ok": True, "access_token": "new-a", "refresh_token": "new-r"})
        with self.assertRaises(RuntimeError):
            SlackRotator(self.env, post).rotate("kuro")
        self.assertEqual(read_env(self.env)["SLACK_REFRESH_TOKEN_KURO"], "new-r")  # not lost

    def test_missing_credentials_never_calls_provider(self):
        self.env.write_text("OTHER=1\n")
        post = FakePost({})
        with self.assertRaises(RuntimeError) as ctx:
            SlackRotator(self.env, post).rotate("kuro")
        self.assertEqual(post.calls, [])
        self.assertNotIn("old", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
