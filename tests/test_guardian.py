import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from agentden.guardian import supervisor as sv
from agentden.guardian.receipt import new_receipt
from agentden.guardian.store import Store, TransitionError
from tests.fakes import FakeClock, FakeRotator, FakeSystemd

SERVICES = {"kuro": "agentden-kuro.service"}


class GuardianTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.clock = FakeClock()
        self.rotator = FakeRotator()
        self.systemd = FakeSystemd()
        self.store = Store(self.base, "kuro")
        # Bootstrap: a receipt from 12 h ago, due 1 h ago.
        receipt = new_receipt("kuro", 13 * 3600, self.clock() - timedelta(hours=12, minutes=1))
        sv.initial_state(self.store, receipt)
        self.g = sv.Guardian(self.base, SERVICES, self.rotator, self.systemd, clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def status(self):
        return self.store.load_state()["status"]

    def beat(self, pid=4242, connected=True, age=1.0):
        self.store.heartbeat_path.write_text(json.dumps({
            "agent": "kuro", "pid": pid, "connected": connected,
            "timestamp": self.clock().timestamp() - age}))

    # -- dry run ------------------------------------------------------------
    def test_dry_run_due_touches_nothing(self):
        r = self.g.cycle("kuro")
        self.assertEqual(r.code, sv.EXIT_DUE)
        self.assertEqual(self.rotator.calls, [])
        self.assertEqual(self.systemd.restarts, [])
        self.assertEqual(self.status(), "ok")

    def test_wait_when_not_due(self):
        sv.initial_state(self.store, new_receipt("kuro", 13 * 3600, self.clock()))
        r = self.g.cycle("kuro", run=True)
        self.assertEqual((r.code, self.rotator.calls), (sv.EXIT_OK, []))

    # -- full happy path ------------------------------------------------------
    def test_full_cycle_ok_to_ok(self):
        r = self.g.cycle("kuro", run=True)
        self.assertEqual(r.code, sv.EXIT_PENDING, r.message)
        self.assertEqual(self.status(), "restart_pending")
        self.assertEqual(self.rotator.calls, ["kuro"])
        self.assertEqual(self.systemd.restarts, ["agentden-kuro.service"])

        self.clock.advance(seconds=10)
        self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_PENDING)  # no heartbeat yet
        self.beat()
        r = self.g.cycle("kuro", run=True)
        self.assertEqual(r.code, sv.EXIT_OK, r.message)
        self.assertEqual(self.status(), "ok")
        self.assertEqual(self.systemd.restarts, ["agentden-kuro.service"])  # exactly one restart
        self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_OK)  # next pass: WAIT

    # -- uncertainty is sticky -----------------------------------------------
    def test_rotator_failure_is_uncertain_and_never_retried(self):
        self.rotator.error = TimeoutError("network")
        r = self.g.cycle("kuro", run=True)
        self.assertEqual(r.code, sv.EXIT_UNCERTAIN)
        self.assertEqual(self.status(), "uncertain")
        for _ in range(3):
            self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_UNCERTAIN)
        self.assertEqual(self.rotator.calls, ["kuro"])  # one call, ever
        self.assertEqual(self.systemd.restarts, [])

    def test_bad_lifetime_is_uncertain(self):
        self.rotator.expires_in = 60
        self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_UNCERTAIN)

    def test_crash_after_uncertain_persisted(self):
        # Simulates the process dying mid-request: state already says uncertain.
        self.store.transition("ok", "uncertain", self.clock())
        self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_UNCERTAIN)
        self.assertEqual(self.rotator.calls, [])

    # -- restart guard ----------------------------------------------------------
    def test_restart_failure_blocks_without_retry(self):
        self.systemd.fail = True
        self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_BLOCKED)
        self.assertTrue(self.store.incident_path.exists())
        self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_BLOCKED)
        self.assertEqual(len(self.systemd.restarts), 1)

    def test_heartbeat_rejections(self):
        self.g.cycle("kuro", run=True)
        self.clock.advance(seconds=5)
        for kwargs in ({"pid": 1}, {"connected": False}, {"age": 120}, {"age": 30}):
            self.beat(**kwargs)
            self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_PENDING, kwargs)
        self.systemd.pid = None
        self.beat()
        self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_PENDING)
        self.assertEqual(self.status(), "restart_pending")

    def test_dry_run_in_restart_pending_does_not_restart(self):
        self.store.transition("ok", "uncertain", self.clock())
        receipt = new_receipt("kuro", 13 * 3600, self.clock())
        self.store.save_receipt(receipt)
        self.store.transition("uncertain", "restart_pending", self.clock(),
                              rotation_id=receipt["rotation_id"], next_rotation_at=receipt["next_rotation_at"])
        self.assertEqual(self.g.cycle("kuro").code, sv.EXIT_PENDING)
        self.assertEqual(self.systemd.restarts, [])

    # -- fail closed on bad files -------------------------------------------------
    def test_incident_marker_blocks(self):
        self.store.mark_incident("test")
        self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_BLOCKED)
        self.assertEqual(self.rotator.calls, [])

    def test_receipt_tampering_blocks(self):
        for mutate in (lambda r: r.update(rotation_id="00000000-0000-0000-0000-000000000000"),
                       lambda r: r.update(rotated_at=12345),
                       lambda r: r.update(status="started"),
                       lambda r: r.update(agent="mimi")):
            receipt = self.store.load_receipt()
            original = dict(receipt)
            mutate(receipt)
            self.store.save_receipt(receipt)
            self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_BLOCKED)
            self.store.save_receipt(original)
        self.assertEqual(self.rotator.calls, [])

    def test_missing_state_blocks(self):
        self.store.state_path.unlink()
        self.assertEqual(self.g.cycle("kuro", run=True).code, sv.EXIT_BLOCKED)

    def test_illegal_transitions(self):
        with self.assertRaises(TransitionError):
            self.store.transition("ok", "restart_pending", self.clock())
        with self.assertRaises(TransitionError):
            self.store.transition("uncertain", "restart_pending", self.clock())

    def test_files_are_private(self):
        self.assertEqual(self.store.state_path.stat().st_mode & 0o777, 0o600)

    def test_exit_code_aggregation(self):
        self.assertEqual(sv.worst([]), sv.EXIT_OK)
        self.assertEqual(sv.worst([sv.EXIT_OK, sv.EXIT_DUE, sv.EXIT_PENDING]), sv.EXIT_PENDING)
        self.assertEqual(sv.worst([sv.EXIT_PENDING, sv.EXIT_UNCERTAIN, sv.EXIT_BLOCKED]), sv.EXIT_UNCERTAIN)
        self.assertEqual(sv.worst([sv.EXIT_UNCERTAIN, sv.EXIT_ERROR]), sv.EXIT_ERROR)

    def test_run_once_isolates_agents(self):
        g = sv.Guardian(self.base, {"kuro": "agentden-kuro.service", "mimi": "agentden-mimi.service"},
                        self.rotator, self.systemd, clock=self.clock)
        res = g.run_once()
        self.assertEqual(res["kuro"].code, sv.EXIT_DUE)
        self.assertEqual(res["mimi"].code, sv.EXIT_BLOCKED)  # no state for mimi


if __name__ == "__main__":
    unittest.main()
