"""One Guardian pass per agent. Designed to run from a systemd oneshot timer.

State machine (the only legal path):

    ok --(due, --run)--> uncertain --(valid new receipt)--> restart_pending
     ^                                                          |
     +------(fresh heartbeat from the NEW MainPID, connected)---+

Rules:
  * Dry run by default. Nothing is refreshed or restarted without run=True.
  * `uncertain` is persisted BEFORE the refresh request. If the process dies or
    the provider answer is unclear, we stay `uncertain` forever: refresh tokens
    can be single-use, so a blind retry may lock you out. A human decides.
  * Exactly one restart attempt per rotation, guarded by a marker file that is
    written before the restart is requested.
  * Every outcome maps to an explicit exit code (worst one wins).
"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from .receipt import check_receipt, new_receipt
from .store import Store, TransitionError, parse_utc

EXIT_OK = 0          # nothing to do, or a step completed
EXIT_ERROR = 1       # unexpected exception
EXIT_USAGE = 2       # bad config / arguments
EXIT_BLOCKED = 3     # incident marker, inconsistent files: human needed
EXIT_UNCERTAIN = 4   # refresh may have happened: do NOT retry, human needed
EXIT_PENDING = 5     # restart requested/awaiting proof (transient)
EXIT_DUE = 6         # rotation due but dry run (transient)

# Severity order for combining several agents into one process exit code.
_SEVERITY = [EXIT_OK, EXIT_DUE, EXIT_PENDING, EXIT_BLOCKED, EXIT_UNCERTAIN, EXIT_ERROR]

HEARTBEAT_MAX_AGE = 30.0


@dataclass(frozen=True)
class Result:
    code: int
    message: str

    def __str__(self):
        return self.message


def worst(codes):
    codes = list(codes) or [EXIT_OK]
    return max(codes, key=_SEVERITY.index)


def _utcnow():
    return datetime.now(timezone.utc)


class Guardian:
    """`rotator.rotate(agent) -> expires_in seconds` does the provider refresh
    and stores the new secrets itself. Raising anything means "outcome unknown".
    """

    def __init__(self, base, services, rotator, systemd, clock=_utcnow):
        self.base = base
        self.services = dict(services)  # agent -> "agentden-<agent>.service"
        self.rotator = rotator
        self.systemd = systemd
        self.clock = clock

    # -- public -----------------------------------------------------------
    def run_once(self, run=False):
        results = {}
        for agent in self.services:
            try:
                results[agent] = self.cycle(agent, run=run)
            except BlockingIOError:
                results[agent] = Result(EXIT_PENDING, "PENDING: another Guardian run holds the lock")
            except Exception as exc:  # never crash the loop for other agents
                results[agent] = Result(EXIT_ERROR, f"ERROR: {type(exc).__name__}; manual review")
        return results

    def cycle(self, agent, run=False):
        store = Store(self.base, agent)
        with store.lock():
            if store.incident_path.exists():
                return Result(EXIT_BLOCKED, "BLOCKED: incident marker present")
            try:
                state = store.load_state()
            except (OSError, ValueError):
                return Result(EXIT_BLOCKED, "BLOCKED: state missing or unreadable")
            status = state.get("status")
            if status == "uncertain":
                return Result(EXIT_UNCERTAIN, "UNCERTAIN: previous refresh outcome unknown; never retried automatically")
            if status == "restart_pending":
                return self._restart_step(store, state, run)
            if status != "ok":
                return Result(EXIT_BLOCKED, f"BLOCKED: unknown status {status!r}")
            return self._ok_step(store, state, run)

    # -- steps ------------------------------------------------------------
    def _consistent_receipt(self, store, state):
        try:
            receipt = store.load_receipt()
        except (OSError, ValueError):
            return None, "receipt missing or unreadable"
        reason = check_receipt(receipt, store.agent, self.clock())
        if reason:
            return None, reason
        if state.get("rotation_id") != receipt["rotation_id"]:
            return None, "state/receipt rotation_id mismatch"
        if state.get("next_rotation_at") != receipt["next_rotation_at"]:
            return None, "state/receipt schedule mismatch"
        return receipt, None

    def _ok_step(self, store, state, run):
        receipt, reason = self._consistent_receipt(store, state)
        if reason:
            return Result(EXIT_BLOCKED, f"BLOCKED: {reason}")
        now = self.clock()
        if now < parse_utc(receipt["next_rotation_at"]):
            return Result(EXIT_OK, "WAIT: not due; no refresh request")
        if not run:
            return Result(EXIT_DUE, "DUE: dry run; rerun with --run to refresh")

        # Persist BEFORE touching the provider. From here on, any failure is UNCERTAIN.
        store.transition("ok", "uncertain", now, rotation_started_at=now.isoformat())
        try:
            expires_in = self.rotator.rotate(store.agent)
            fresh = new_receipt(store.agent, expires_in, self.clock())
            store.save_receipt(fresh)
            store.transition("uncertain", "restart_pending", self.clock(),
                             rotation_id=fresh["rotation_id"],
                             next_rotation_at=fresh["next_rotation_at"])
        except Exception as exc:
            return Result(EXIT_UNCERTAIN, f"UNCERTAIN: {type(exc).__name__} during refresh; do not retry")
        restart = self._restart_step(store, store.load_state(), run)
        return Result(restart.code, "RENEWED | " + restart.message)

    def _restart_step(self, store, state, run):
        receipt, reason = self._consistent_receipt(store, state)
        if reason:
            return Result(EXIT_BLOCKED, f"BLOCKED: {reason}")
        service = self.services[store.agent]
        marker = store.restart_marker(receipt["rotation_id"])
        if not marker.exists():
            if not run:
                return Result(EXIT_PENDING, "PENDING: restart authorized (dry run)")
            with open(marker, "x", encoding="utf-8") as fh:  # O_EXCL: one attempt only
                fh.write(self.clock().isoformat() + "\n")
            try:
                self.systemd.restart(service)
            except Exception as exc:
                store.mark_incident(f"restart failed: {type(exc).__name__}")
                return Result(EXIT_BLOCKED, f"BLOCKED: restart failed ({type(exc).__name__}); no blind retry")
            return Result(EXIT_PENDING, "PENDING: restart requested; awaiting heartbeat proof")
        if self._fresh_proof(store, service, marker):
            store.transition("restart_pending", "ok", self.clock())
            return Result(EXIT_OK, "OK: fresh connected heartbeat from new process")
        return Result(EXIT_PENDING, "PENDING: no fresh post-restart heartbeat yet")

    def _fresh_proof(self, store, service, marker):
        try:
            beat = json.loads(store.heartbeat_path.read_text(encoding="utf-8"))
            pid = self.systemd.main_pid(service)
            ts = beat.get("timestamp")
            now = self.clock().timestamp()
            return (
                pid is not None
                and beat.get("agent") == store.agent
                and beat.get("pid") == pid
                and beat.get("connected") is True
                and isinstance(ts, (int, float)) and not isinstance(ts, bool)
                and parse_utc(marker.read_text(encoding="utf-8").strip()).timestamp() < ts <= now + 5
                and now - ts <= HEARTBEAT_MAX_AGE
            )
        except (OSError, ValueError, TypeError, AttributeError):
            return False


def initial_state(store, receipt):
    """Bootstrap helper: write a matching ok state for a hand-made first receipt."""
    store.save_receipt(receipt)
    store.save_state({"agent": store.agent, "status": "ok",
                      "rotation_id": receipt["rotation_id"],
                      "next_rotation_at": receipt["next_rotation_at"]})


__all__ = ["Guardian", "Result", "worst", "initial_state", "TransitionError"]
