import json
import tempfile
import unittest
from pathlib import Path

from agentden import cli
from agentden.systemd import generate, load_config, validate

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample-config.json"


def sample():
    return json.loads(SAMPLE.read_text())


class TestGenerator(unittest.TestCase):
    def test_sample_is_valid(self):
        self.assertEqual(len(load_config(SAMPLE)["agents"]), 4)

    def test_generates_six_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate(load_config(SAMPLE), tmp)
            self.assertEqual(len(paths), 6)
            service = Path(tmp, "agentden-guardian.service").read_text()
            timer = Path(tmp, "agentden-guardian.timer").read_text()
            self.assertNotIn("--run", service)  # never emitted, not even in comments
            self.assertIn("Type=oneshot", service)
            self.assertIn("SuccessExitStatus=5 6", service)
            self.assertIn("OnCalendar=*:0/5", timer)
            self.assertNotIn("\nOnBootSec=", timer)
            kuro = Path(tmp, "agentden-kuro.service").read_text()
            self.assertIn("ExecStart=/home/ubuntu/agent-team/.venv/bin/python /home/ubuntu/agent-team/kuro_bot.py", kuro)
            self.assertIn("Restart=on-failure", kuro)

    def test_interval_configurable(self):
        cfg = sample()
        cfg["guardian"]["interval_minutes"] = 15
        with tempfile.TemporaryDirectory() as tmp:
            generate(validate(cfg), tmp)
            self.assertIn("OnCalendar=*:0/15", Path(tmp, "agentden-guardian.timer").read_text())

    def test_rejects_bad_interval(self):
        for bad in (7, 0, True, "5"):
            cfg = sample()
            cfg["guardian"]["interval_minutes"] = bad
            with self.assertRaises(ValueError):
                validate(cfg)

    def test_rejects_injection(self):
        cases = [
            ("agents", 0, "entrypoint", "bot.py;rm -rf /"),
            ("agents", 0, "entrypoint", "../bot.py"),
            ("agents", 0, "name", "Dudu\nExecStartPre=/bin/sh"),
        ]
        for top, idx, key, value in cases:
            cfg = sample()
            cfg[top][idx][key] = value
            with self.assertRaises(ValueError, msg=value):
                validate(cfg)
        for key, value in (("remote_directory", "/home/ubuntu/../root"),
                           ("python_path", "/usr/bin/python3 -c 'x'"),
                           ("remote_directory", "relative/path")):
            cfg = sample()
            cfg[key] = value
            with self.assertRaises(ValueError, msg=value):
                validate(cfg)

    def test_rejects_real_guardian(self):
        cfg = sample()
        cfg["guardian"]["real_operations"] = True
        with self.assertRaises(ValueError):
            validate(cfg)

    def test_rejects_duplicate_and_reserved(self):
        cfg = sample()
        cfg["agents"].append({"name": "dudu", "entrypoint": "x.py"})
        with self.assertRaises(ValueError):
            validate(cfg)
        cfg = sample()
        cfg["agents"][0]["name"] = "guardian"
        with self.assertRaises(ValueError):
            validate(cfg)

    def test_cli_exit_codes(self):
        self.assertEqual(cli.main(["validate", str(SAMPLE)]), 0)
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp, "bad.json")
            bad.write_text("{not json")
            self.assertEqual(cli.main(["validate", str(bad)]), 2)


if __name__ == "__main__":
    unittest.main()
